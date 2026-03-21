"""
运维看板页面：流量、数据体量、日志监看（对接后端 /api/v1/system 运维接口）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QLineSeries,
    QPieSeries,
    QPieSlice,
    QValueAxis,
)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from api.system import SystemAPI
from api.ollama import get_system_summary
from pages.settings_page import SettingsWorker

_GROUP_LABELS = {
    "files": "文件 API",
    "auth": "认证",
    "ai": "AI",
    "system": "系统",
    "tunnel": "远程",
    "api_other": "其他 API",
    "web": "Web/静态",
}

_GROUP_COLORS = {
    "files": "#0A84FF",
    "auth": "#BF5AF2",
    "ai": "#30D158",
    "system": "#FF9F0A",
    "tunnel": "#64D2FF",
    "api_other": "#FF375F",
    "web": "#8E8E93",
}


class OpsDashboardPage(QWidget):
    """带多 Tab 的运维看板（Qt Charts 可视化）。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("OpsDashboardPage")
        self._traffic_timer = QTimer(self)
        self._traffic_timer.timeout.connect(self._refresh_traffic_async)
        self._data_timer = QTimer(self)
        self._data_timer.timeout.connect(self._refresh_data_async)
        self._logs_timer = QTimer(self)
        self._logs_timer.timeout.connect(self._refresh_logs_async)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        title = QLabel("运维看板")
        title.setObjectName("OpsPageTitle")
        tf = QFont()
        tf.setPointSize(20)
        tf.setBold(True)
        title.setFont(tf)
        layout.addWidget(title)

        sub = QLabel("流量趋势、数据体量与日志（数据来自当前登录的后端进程）")
        sub.setObjectName("OpsPageSubtitle")
        layout.addWidget(sub)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("OpsDashboardTabs")
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        layout.addWidget(self._tabs, 1)

        self._traffic_tab = self._build_traffic_tab()
        self._data_tab = self._build_data_tab()
        self._logs_tab = self._build_logs_tab()
        self._tabs.addTab(self._traffic_tab, "流量")
        self._tabs.addTab(self._data_tab, "数据")
        self._tabs.addTab(self._logs_tab, "日志监看")

    def _card(self, title: str, value: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("OpsMetricCard")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        vl = QVBoxLayout(frame)
        vl.setContentsMargins(14, 12, 14, 12)
        vl.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("OpsCardTitle")
        v = QLabel(value)
        v.setObjectName("OpsCardValue")
        vl.addWidget(t)
        vl.addWidget(v)
        return frame

    def _build_traffic_tab(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        vl.setSpacing(12)

        self._traffic_summary_row = QHBoxLayout()
        self._traffic_summary_row.setSpacing(10)
        vl.addLayout(self._traffic_summary_row)

        self._traffic_chart = QChart()
        self._traffic_chart.setTheme(QChart.ChartTheme.ChartThemeLight)
        self._traffic_chart.setBackgroundVisible(True)
        self._traffic_chart.setTitle("每分钟请求数（按后端分类聚合）")
        self._traffic_chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._traffic_chart.setBackgroundRoundness(14)
        self._traffic_chart_view = QChartView(self._traffic_chart)
        self._traffic_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._traffic_chart_view.setMinimumHeight(320)
        self._traffic_chart_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        vl.addWidget(self._traffic_chart_view, 1)

        hint = QLabel(
            "说明：统计自当前后端进程启动以来；"
            "默认排除 /health、/favicon.ico（可用 ALLAHPAN_METRICS_EXCLUDE_PREFIXES 调整）。"
        )
        hint.setObjectName("OpsHintLabel")
        hint.setWordWrap(True)
        vl.addWidget(hint)
        return w

    def _build_data_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        vl = QVBoxLayout(inner)
        vl.setSpacing(14)

        self._data_cards_row = QHBoxLayout()
        self._data_cards_row.setSpacing(10)
        vl.addLayout(self._data_cards_row)

        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        self._disk_chart = QChart()
        self._disk_chart.setTheme(QChart.ChartTheme.ChartThemeLight)
        self._disk_chart.setBackgroundVisible(True)
        self._disk_chart.setTitle("磁盘空间分布（摘要）")
        self._disk_chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
        dv = QChartView(self._disk_chart)
        dv.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        dv.setMinimumHeight(280)
        dv.setMinimumWidth(320)

        self._volume_chart = QChart()
        self._volume_chart.setTheme(QChart.ChartTheme.ChartThemeLight)
        self._volume_chart.setBackgroundVisible(True)
        self._volume_chart.setTitle("数据体量（SQLite / Chroma / 目录）")
        self._volume_chart.legend().setVisible(False)
        vv = QChartView(self._volume_chart)
        vv.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        vv.setMinimumHeight(280)
        vv.setMinimumWidth(320)

        charts_row.addWidget(dv, 1)
        charts_row.addWidget(vv, 1)
        vl.addLayout(charts_row)

        self._data_extra_label = QLabel()
        self._data_extra_label.setObjectName("OpsHintLabel")
        self._data_extra_label.setWordWrap(True)
        vl.addWidget(self._data_extra_label)
        vl.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_logs_tab(self) -> QWidget:
        w = QWidget()
        vl = QVBoxLayout(w)
        bar = QHBoxLayout()
        refresh_btn = QPushButton("立即刷新")
        refresh_btn.clicked.connect(lambda: self._refresh_logs_async(force=True))
        bar.addWidget(refresh_btn)
        self._log_auto = QCheckBox("自动刷新")
        self._log_auto.setChecked(True)
        bar.addWidget(self._log_auto)
        bar.addStretch()
        path_lbl = QLabel()
        path_lbl.setObjectName("OpsLogPathLabel")
        path_lbl.setWordWrap(True)
        bar.addWidget(path_lbl, 1)
        self._log_path_label = path_lbl
        vl.addLayout(bar)

        self._log_view = QTextEdit()
        self._log_view.setObjectName("OpsLogView")
        self._log_view.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._log_view.setReadOnly(True)
        self._log_view.setFont(QFont("Consolas", 10))
        self._log_view.setPlaceholderText("正在加载日志…")
        vl.addWidget(self._log_view, 1)
        return w

    def on_show(self) -> None:
        """由主窗口在进入本页时调用，立即拉取一轮数据。"""
        self._sync_chart_themes()
        self._refresh_traffic_async()
        self._refresh_data_async()
        self._refresh_logs_async()

    def _sync_chart_themes(self) -> None:
        """随浅色/深色界面切换 Qt Charts 主题。"""
        pal = QApplication.palette()
        dark = pal.color(QPalette.ColorRole.Window).lightness() < 128
        theme = QChart.ChartTheme.ChartThemeDark if dark else QChart.ChartTheme.ChartThemeLight
        for ch in (self._traffic_chart, self._disk_chart, self._volume_chart):
            ch.setTheme(theme)
            ch.setBackgroundRoundness(14)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync_chart_themes()
        self._traffic_timer.start(5000)
        self._data_timer.start(15000)
        self._logs_timer.start(4000)

    def hideEvent(self, event) -> None:
        self._traffic_timer.stop()
        self._data_timer.stop()
        self._logs_timer.stop()
        super().hideEvent(event)

    def _group_label(self, gid: str) -> str:
        return _GROUP_LABELS.get(gid, gid)

    def _refresh_traffic_async(self) -> None:
        def fetch():
            return SystemAPI().get_metrics_traffic()

        w = SettingsWorker(fetch, parent=self)
        w.finished.connect(self._on_traffic_ready, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(self._on_traffic_failed, Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_traffic_failed(self, err: str) -> None:
        self._traffic_chart.setTitle(f"加载失败: {err[:80]}")

    def _on_traffic_ready(self, data: object) -> None:
        if not isinstance(data, dict):
            self._traffic_chart.setTitle(f"流量数据格式异常: {type(data).__name__}")
            return
        ss = data.get("since_start") or {}
        total = int(ss.get("total_requests", 0))
        by_g = ss.get("by_group") or {}
        while self._traffic_summary_row.count():
            item = self._traffic_summary_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._traffic_summary_row.addWidget(self._card("累计请求（自启动）", f"{total:,}"))
        for gid in (data.get("groups_order") or []):
            c = int(by_g.get(gid, 0)) if isinstance(by_g, dict) else 0
            if c == 0:
                continue
            self._traffic_summary_row.addWidget(self._card(self._group_label(gid), f"{c:,}"))
        self._traffic_summary_row.addStretch()

        series_list: List[Dict[str, Any]] = data.get("series") or []
        groups_order: List[str] = data.get("groups_order") or list(_GROUP_LABELS.keys())
        chart = self._traffic_chart
        chart.removeAllSeries()
        for ax in list(chart.axes()):
            chart.removeAxis(ax)
        n = len(series_list)
        if n == 0:
            chart.setTitle("暂无流量数据（等待请求进入）")
            return
        chart.setTitle("每分钟请求数（按分类）")
        max_y = 1.0
        for gid in groups_order:
            ls = QLineSeries()
            ls.setName(self._group_label(gid))
            for i, bucket in enumerate(series_list):
                bg = bucket.get("by_group") or {}
                v = float(bg.get(gid, 0)) if isinstance(bg, dict) else 0.0
                ls.append(float(i), v)
                max_y = max(max_y, v)
            col = QColor(_GROUP_COLORS.get(gid, "#888888"))
            pen = QPen(col)
            pen.setWidth(2)
            ls.setPen(pen)
            chart.addSeries(ls)

        ax_x = QValueAxis()
        ax_x.setRange(0.0, float(max(0, n - 1)))
        ax_x.setLabelFormat("%i")
        ax_x.setTitleText("时间 →（序号越大越新）")
        ax_y = QValueAxis()
        ax_y.setRange(0.0, max_y * 1.15 if max_y > 0 else 1.0)
        ax_y.setLabelFormat("%i")
        ax_y.setTitleText("请求数 / 分钟")
        chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)
        for s in chart.series():
            s.attachAxis(ax_x)
            s.attachAxis(ax_y)
        chart.legend().setVisible(True)
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

    def _refresh_data_async(self) -> None:
        def fetch():
            api = SystemAPI()
            vol = api.get_metrics_data_volumes()
            summary = get_system_summary()
            storage = api.get_storage_info()
            return {"vol": vol, "summary": summary, "storage": storage}

        w = SettingsWorker(fetch, parent=self)
        w.finished.connect(self._on_data_ready, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(self._on_data_failed, Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_data_failed(self, err: str) -> None:
        self._data_extra_label.setText(f"加载失败: {err}")

    def _on_data_ready(self, payload: object) -> None:
        if not isinstance(payload, dict):
            self._data_extra_label.setText(f"数据加载结果格式异常: {type(payload).__name__}")
            return
        vol = payload.get("vol")
        summary = payload.get("summary")
        storage = payload.get("storage")
        if not isinstance(vol, dict):
            vol = {}
        if not isinstance(summary, dict):
            summary = {}
        if not isinstance(storage, dict):
            storage = {}

        while self._data_cards_row.count():
            item = self._data_cards_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        def fmt_bytes(b: int) -> str:
            return config.format_file_size(int(b))

        db_b = int(vol.get("database_bytes", 0))
        ch_b = int(vol.get("chroma_bytes", 0))
        st_b = int(vol.get("storage_dir_bytes", 0))
        dd_b = int(vol.get("data_dir_bytes", 0))
        self._data_cards_row.addWidget(self._card("SQLite", fmt_bytes(db_b)))
        self._data_cards_row.addWidget(self._card("Chroma 向量库", fmt_bytes(ch_b)))
        self._data_cards_row.addWidget(self._card("数据目录", fmt_bytes(dd_b)))
        self._data_cards_row.addWidget(self._card("网盘存储目录", fmt_bytes(st_b)))
        self._data_cards_row.addStretch()

        # 饼图：磁盘维度（与状态栏摘要一致）
        total = int(storage.get("total_space", 0))
        used_dir = int(storage.get("used_space", 0))
        free = int(storage.get("free_space", 0))
        other = max(0, total - used_dir - free)
        pie = QPieSeries()
        pie.setHoleSize(0.42)
        if total > 0:
            s1 = pie.append("网盘目录", float(used_dir))
            s2 = pie.append("可用空间", float(free))
            s3 = pie.append("其他占用", float(other))
            for sl in (s1, s2, s3):
                if isinstance(sl, QPieSlice):
                    sl.setLabelVisible(True)
                    sl.setLabel(f"{sl.label()} {config.format_file_size(int(sl.value()))}")
        else:
            sl = pie.append("暂无磁盘数据", 1.0)
            if isinstance(sl, QPieSlice):
                sl.setLabelVisible(True)
        for ax in list(self._disk_chart.axes()):
            self._disk_chart.removeAxis(ax)
        self._disk_chart.removeAllSeries()
        self._disk_chart.addSeries(pie)

        vals = [
            db_b / (1024**3),
            ch_b / (1024**3),
            dd_b / (1024**3),
            st_b / (1024**3),
        ]
        m = max(vals) if vals else 0.0
        for ax in list(self._volume_chart.axes()):
            self._volume_chart.removeAxis(ax)
        self._volume_chart.removeAllSeries()
        bar_set = QBarSet("GiB")
        for v in vals:
            bar_set << float(v)
        bar_series = QBarSeries()
        bar_series.append(bar_set)
        self._volume_chart.addSeries(bar_series)
        axis_x = QBarCategoryAxis()
        axis_x.append(["SQLite", "Chroma", "数据目录", "网盘目录"])
        axis_y = QValueAxis()
        axis_y.setRange(0.0, max(m * 1.2, 0.001))
        axis_y.setTitleText("GiB")
        self._volume_chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        self._volume_chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        bar_series.attachAxis(axis_x)
        bar_series.attachAxis(axis_y)
        self._volume_chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        ip = summary.get("image_parser") or {}
        w = summary.get("watcher") or {}
        ol = summary.get("ollama") or {}
        lines = [
            f"目录监听: {'运行中' if w.get('running') else '未运行'} · 路径 {w.get('watch_path', '')}",
            f"图片队列: 待处理 {ip.get('queue_size', 0)} · "
            f"已处理 {ip.get('total_processed', 0)} · 失败 {ip.get('total_failed', 0)}",
            f"Ollama: {ol.get('status', '?')} · 服务可用: {'是' if ol.get('service_available') else '否'}",
        ]
        self._data_extra_label.setText("\n".join(lines))

    def _refresh_logs_async(self, force: bool = False) -> None:
        if not force and not self._log_auto.isChecked():
            return

        def fetch():
            return SystemAPI().get_logs_tail(lines=500)

        w = SettingsWorker(fetch, parent=self)
        w.finished.connect(self._on_logs_ready, Qt.ConnectionType.QueuedConnection)
        w.failed.connect(self._on_logs_failed, Qt.ConnectionType.QueuedConnection)
        w.start()

    def _on_logs_failed(self, err: str) -> None:
        self._log_view.setPlainText(f"拉取日志失败:\n{err}")

    def _on_logs_ready(self, data: object) -> None:
        if not isinstance(data, dict):
            self._log_view.setPlainText(
                f"日志接口返回格式异常: {type(data).__name__}，请确认后端已更新。"
            )
            self._log_path_label.setText("")
            return
        path = data.get("path")
        msg = data.get("message")
        if msg:
            self._log_path_label.setText(str(msg))
            self._log_view.setPlainText(str(msg))
            return
        self._log_path_label.setText(path or "")
        raw = data.get("raw") or "\n".join(data.get("lines") or [])
        self._log_view.setPlainText(raw)
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())
