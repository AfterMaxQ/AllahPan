"""
浅色主题 QSS 样式表。

macOS 风格 + 百度网盘模式
配色参考: #007AFF (macOS 蓝), #F5F5F7 (背景)
"""

LIGHT_QSS = """
/* ==================== 全局基础样式 ==================== */
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: #1D1D1F;
}

QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #EEF2FA, stop:0.45 #E8ECF6, stop:1 #E2E8F3);
}

#MainShell {
    background-color: transparent;
}

#MainContentColumn {
    background-color: transparent;
}

#MainHeaderBar {
    background-color: rgba(255, 255, 255, 0.58);
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

#StackedGlassPanel {
    background-color: rgba(255, 255, 255, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.75);
    border-radius: 20px;
}

/* ==================== 滚动条样式 ==================== */
QScrollBar:vertical {
    width: 10px;
    background: transparent;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #C7C7CC;
    min-height: 30px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: #8E8E93;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    subcontrol-origin: margin;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}

QScrollBar:horizontal {
    height: 10px;
    background: transparent;
    margin: 0px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #C7C7CC;
    min-width: 30px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background: #8E8E93;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    subcontrol-origin: margin;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

/* ==================== 输入框样式 ==================== */
QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    color: #1D1D1F;
    selection-background-color: #007AFF;
}

QLineEdit:hover {
    border-color: #AEAEB2;
}

QLineEdit:focus {
    border-color: #007AFF;
    outline: none;
}

QLineEdit:disabled {
    background-color: #F5F5F7;
    color: #86868B;
}

/* ==================== 按钮样式 ==================== */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0080FF, stop:1 #0066DD);
    color: #FFFFFF;
    border: none;
    border-radius: 12px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
    min-width: 80px;
    min-height: 36px;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0090FF, stop:1 #0070E6);
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0056CC, stop:1 #004499);
}

QPushButton:disabled {
    background-color: #D2D2D7;
    color: #86868B;
}

QPushButton.QPushButton__secondary {
    background: transparent;
    color: #007AFF;
    border: 1px solid #007AFF;
    border-radius: 10px;
}

QPushButton.QPushButton__secondary:hover {
    background-color: #E8F4FD;
}

QPushButton.QPushButton__secondary:pressed {
    background-color: #D0E8FC;
}

QPushButton.QPushButton__danger {
    background-color: #FF3B30;
}

QPushButton.QPushButton__danger:hover {
    background-color: #D92F2A;
}

/* ==================== 工具栏按钮 ==================== */
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 10px;
    padding: 8px 12px;
    color: #1D1D1F;
}

QToolButton:hover {
    background-color: #F5F5F7;
}

QToolButton:pressed {
    background-color: #E5E5EA;
}

QToolButton:disabled {
    color: #86868B;
}

/* ==================== 侧边栏样式 ==================== */
#SidebarWidget {
    background-color: rgba(250, 251, 253, 0.82);
    border-right: 1px solid rgba(0, 0, 0, 0.06);
}

QListWidget#SidebarList {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget#SidebarList::item {
    background-color: transparent;
    border: none;
    border-radius: 12px;
    padding: 10px 10px;
    margin: 3px 6px;
    color: #1D1D1F;
}

QListWidget#SidebarList::item:selected {
    background-color: #E8F4FD;
    border-left: 3px solid #007AFF;
    padding-left: 9px;
    color: #007AFF;
    font-weight: 500;
}

QListWidget#SidebarList::item:hover:!selected {
    background-color: #E8E8ED;
}

QListWidget#SidebarList::item:selected:active {
    background-color: #D0E8FC;
}

/* 侧边栏标题 */
#SidebarTitle {
    font-size: 11px;
    font-weight: 600;
    color: #86868B;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 16px 16px 8px 16px;
}

/* ==================== 主内容区域 ==================== */
#ContentWidget {
    background-color: rgba(255, 255, 255, 0.78);
    border-radius: 14px;
}

#ToolbarWidget {
    background-color: rgba(255, 255, 255, 0.42);
    border-bottom: 1px solid rgba(0, 0, 0, 0.05);
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}

/* ==================== 设置页分组框 ==================== */
QGroupBox {
    background-color: rgba(250, 250, 252, 0.92);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 18px;
    margin-top: 16px;
    padding: 20px 20px 14px 20px;
    font-weight: 500;
    color: #1D1D1F;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 10px;
    background-color: transparent;
    color: #6E6E73;
}

#SettingsPage QPushButton.QPushButton__secondary {
    max-width: 280px;
}

/* ==================== 搜索栏样式 ==================== */
#SearchBarWidget {
    background-color: rgba(245, 245, 247, 0.9);
    border-radius: 14px;
    border: 1px solid rgba(0, 0, 0, 0.05);
    padding: 8px 12px;
}

#SearchLineEdit {
    background-color: transparent;
    border: none;
    font-size: 14px;
    color: #1D1D1F;
    padding: 0px;
}

#SearchLineEdit:focus {
    outline: none;
}

#SearchLineEdit::placeholder {
    color: #86868B;
}

#SearchModeButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    color: #86868B;
}

#SearchModeButton:hover {
    background-color: #E8E8ED;
    color: #1D1D1F;
}

/* ==================== 网格视图样式 ==================== */
#FileGridView {
    background-color: #FFFFFF;
    border: none;
    outline: none;
}

#FileGridView::item {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px;
}

#FileGridView::item:selected {
    background-color: #E8F4FD;
    border: 2px solid #007AFF;
}

#FileGridView::item:hover {
    background-color: #F5F5F7;
}

/* ==================== 列表视图样式 ==================== */
#FileTableView {
    background-color: #FFFFFF;
    border: none;
    outline: none;
    gridline-color: #E5E5EA;
    alternate-background-color: #FAFAFC;
}

#FileTableView::item {
    background-color: transparent;
    border: none;
    border-bottom: 1px solid #F5F5F7;
    padding: 8px 12px;
    min-height: 36px;
}

#FileTableView::item:selected {
    background-color: #E8F4FD;
    color: #007AFF;
}

#FileTableView::item:hover:!selected {
    background-color: #F5F5F7;
}

/* 表头样式 */
QHeaderView::section {
    background-color: #F5F5F7;
    color: #86868B;
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid #D2D2D7;
    border-right: 1px solid #E5E5EA;
}

QHeaderView::section:only-one {
    border-right: none;
}

QHeaderView::section:hover {
    background-color: #E8E8ED;
}

/* ==================== 上传队列样式 ==================== */
#UploadQueueWidget {
    background-color: rgba(255, 255, 255, 0.55);
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    padding: 12px 16px;
}

#UploadItemWidget {
    background-color: rgba(255, 255, 255, 0.92);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 14px;
    padding: 10px 14px;
    margin-bottom: 8px;
}

QProgressBar#UploadProgressBar {
    background-color: #E5E5EA;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}

QProgressBar#UploadProgressBar::chunk {
    background-color: #007AFF;
    border-radius: 4px;
}

/* ==================== 状态栏样式 ==================== */
#StatusBarWidget {
    background-color: rgba(255, 255, 255, 0.5);
    border-top: 1px solid rgba(0, 0, 0, 0.06);
    padding: 8px 16px;
    color: #86868B;
    font-size: 12px;
}

#StatusBarWidget QLabel {
    color: #86868B;
}

/* 存储空间进度条 */
QProgressBar#StorageProgressBar {
    background-color: #E5E5EA;
    border: none;
    border-radius: 4px;
    height: 6px;
    min-width: 120px;
    text-align: center;
}

QProgressBar#StorageProgressBar::chunk {
    background-color: #007AFF;
    border-radius: 4px;
}

/* 状态指示灯 */
#StatusIndicator {
    width: 8px;
    height: 8px;
    border-radius: 4px;
    background-color: #34C759;
}

#StatusIndicator#StatusIndicator__warning {
    background-color: #FF9500;
}

#StatusIndicator#StatusIndicator__danger {
    background-color: #FF3B30;
}

/* ==================== 对话框样式 ==================== */
QDialog {
    background-color: #FFFFFF;
}

QDialog QLabel {
    color: #1D1D1F;
}

QDialog QPushButton {
    min-width: 100px;
}

/* ==================== 消息提示样式 ==================== */
QMessageBox {
    background-color: #FFFFFF;
}

QMessageBox QLabel {
    color: #1D1D1F;
    padding: 10px;
}

/* ==================== 工具提示样式 ==================== */
QToolTip {
    background-color: #1D1D1F;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ==================== 菜单样式 ==================== */
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 8px 24px 8px 12px;
    color: #1D1D1F;
}

QMenu::item:selected {
    background-color: #E8F4FD;
    color: #007AFF;
}

QMenu::separator {
    height: 1px;
    background-color: #E5E5EA;
    margin: 6px 0px;
}

/* ==================== 空状态样式 ==================== */
#EmptyStateWidget {
    background-color: transparent;
}

#EmptyStateWidget QLabel {
    color: #86868B;
    font-size: 15px;
}

/* ==================== 拖拽高亮样式 ==================== */
#DropZoneOverlay {
    background-color: rgba(0, 122, 255, 0.1);
    border: 2px dashed #007AFF;
    border-radius: 12px;
}

/* 文件主页拖拽毛玻璃（覆盖工具栏+列表区域） */
QWidget#DropOverlayFrosted {
    background-color: rgba(255, 255, 255, 0.52);
    border: 2px dashed rgba(0, 122, 255, 0.5);
    border-radius: 18px;
}

QWidget#DropOverlayFrosted QLabel#DropOverlayTitle {
    font-size: 22px;
    font-weight: 600;
    color: rgba(29, 29, 31, 0.92);
    background: transparent;
}

QWidget#DropOverlayFrosted QLabel#DropOverlayHint {
    font-size: 13px;
    color: rgba(60, 60, 67, 0.75);
    background: transparent;
    max-width: 420px;
}

/* ==================== 登录页 ==================== */
#LoginPage QLineEdit {
    border-radius: 12px;
    padding: 12px 16px;
    min-height: 44px;
    max-height: 48px;
}

#LoginPage QPushButton#LoginSubmitButton {
    border-radius: 12px;
    min-height: 44px;
    max-height: 48px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0088FF, stop:1 #0066DD);
    border: none;
    color: white;
    font-weight: 500;
}

#LoginPage QPushButton#LoginSubmitButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0099FF, stop:1 #0077EE);
}

#LoginPage QPushButton#LoginSubmitButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0066CC, stop:1 #0055BB);
}

#LoginPage QPushButton#LoginSubmitButton:disabled {
    background: #D2D2D7;
    color: #86868B;
}

/* ==================== 组合框样式 ==================== */
QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    color: #1D1D1F;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #AEAEB2;
}

QComboBox:focus {
    border-color: #007AFF;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: right center;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
    border: none;
    background-color: transparent;
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #86868B;
    margin-right: 8px;
}

QComboBox QAbstractItemView, QComboBox QListView {
    background-color: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 12px;
    padding: 8px;
    selection-background-color: #E8F4FD;
    selection-color: #007AFF;
    color: #1D1D1F;
    outline: none;
}

QComboBox QAbstractItemView::item {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 2px 4px;
    color: #1D1D1F;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #F5F5F7;
}

QComboBox QAbstractItemView::item:selected {
    background-color: #E8F4FD;
    color: #007AFF;
}

/* ==================== 登录毛玻璃卡片 ==================== */
#LoginGlassCard {
    background-color: rgba(255, 255, 255, 0.58);
    border-radius: 22px;
    border: 1px solid rgba(255, 255, 255, 0.85);
}

#LoginPage QPushButton#LoginSwitchLink {
    background: transparent;
    color: #007AFF;
    border: none;
    font-size: 13px;
    font-weight: 500;
}

#LoginPage QPushButton#LoginSwitchLink:hover {
    text-decoration: underline;
    color: #0056CC;
}

/* ==================== 设置页容器 ==================== */
#SettingsPageContainer {
    background-color: rgba(255, 255, 255, 0.42);
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.7);
}

/* ==================== 运维看板（分段 Tab + 卡片） ==================== */
#OpsDashboardPage QLabel#OpsPageTitle {
    color: #007AFF;
    letter-spacing: -0.3px;
}

#OpsDashboardPage QLabel#OpsPageSubtitle,
#OpsDashboardPage QLabel#OpsHintLabel,
#OpsDashboardPage QLabel#OpsLogPathLabel {
    color: #86868B;
    font-size: 12px;
}

#OpsDashboardPage QFrame#OpsMetricCard {
    background-color: rgba(255, 255, 255, 0.72);
    border-radius: 16px;
    border: 1px solid rgba(0, 0, 0, 0.05);
}

#OpsDashboardPage QLabel#OpsCardTitle {
    color: #86868B;
    font-size: 11px;
    font-weight: 500;
}

#OpsDashboardPage QLabel#OpsCardValue {
    font-size: 20px;
    font-weight: 600;
    color: #1D1D1F;
}

QTabWidget#OpsDashboardTabs::pane {
    border: none;
    background: transparent;
    top: 2px;
}

QTabWidget#OpsDashboardTabs QTabBar::tab {
    background-color: rgba(0, 0, 0, 0.04);
    color: #636366;
    border: none;
    padding: 10px 22px;
    margin-right: 6px;
    border-radius: 12px;
    min-width: 76px;
    font-weight: 500;
}

QTabWidget#OpsDashboardTabs QTabBar::tab:selected {
    background-color: #007AFF;
    color: #FFFFFF;
    font-weight: 600;
}

QTabWidget#OpsDashboardTabs QTabBar::tab:hover:!selected {
    background-color: rgba(0, 122, 255, 0.12);
    color: #1D1D1F;
}

QTextEdit#OpsLogView {
    background-color: rgba(255, 255, 255, 0.65);
    border: 1px solid rgba(0, 0, 0, 0.06);
    border-radius: 14px;
    padding: 10px;
    selection-background-color: #007AFF;
    selection-color: #FFFFFF;
}
"""
