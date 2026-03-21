"""
深色主题 QSS 样式表。

macOS 风格深色模式
配色参考: #0A84FF (深色主题蓝), #1C1C1E (背景)
"""

DARK_QSS = """
/* ==================== 全局基础样式 ==================== */
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: #FFFFFF;
}

QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #121214, stop:0.5 #1A1A1C, stop:1 #1C1C1F);
}

#MainShell {
    background-color: transparent;
}

#MainContentColumn {
    background-color: transparent;
}

#MainHeaderBar {
    background-color: rgba(44, 44, 46, 0.55);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

#StackedGlassPanel {
    background-color: rgba(36, 36, 38, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.09);
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
    background: #545458;
    min-height: 30px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background: #636366;
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
    background: #545458;
    min-width: 30px;
    border-radius: 5px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background: #636366;
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
    background-color: #2C2C2E;
    border: 1px solid #3A3A3C;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    color: #FFFFFF;
    selection-background-color: #0A84FF;
}

QLineEdit:hover {
    border-color: #545458;
}

QLineEdit:focus {
    border-color: #0A84FF;
    outline: none;
}

QLineEdit:disabled {
    background-color: #1C1C1E;
    color: #636366;
}

/* ==================== 按钮样式 ==================== */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A84FF, stop:1 #0066CC);
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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #409CFF, stop:1 #2080E0);
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0066CC, stop:1 #0050A0);
}

QPushButton:disabled {
    background-color: #3A3A3C;
    color: #636366;
}

QPushButton.QPushButton__secondary {
    background: transparent;
    color: #0A84FF;
    border: 1px solid #0A84FF;
    border-radius: 10px;
}

QPushButton.QPushButton__secondary:hover {
    background-color: #1A3A5C;
}

QPushButton.QPushButton__secondary:pressed {
    background-color: #0A3A5C;
}

QPushButton.QPushButton__danger {
    background-color: #FF453A;
}

QPushButton.QPushButton__danger:hover {
    background-color: #FF6961;
}

/* ==================== 工具栏按钮 ==================== */
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 10px;
    padding: 8px 12px;
    color: #FFFFFF;
}

QToolButton:hover {
    background-color: #3A3A3C;
}

QToolButton:pressed {
    background-color: #48484A;
}

QToolButton:disabled {
    color: #636366;
}

/* ==================== 侧边栏样式 ==================== */
#SidebarWidget {
    background-color: rgba(28, 28, 30, 0.88);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
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
    color: #FFFFFF;
}

QListWidget#SidebarList::item:selected {
    background-color: #1A3A5C;
    border-left: 3px solid #0A84FF;
    padding-left: 9px;
    color: #0A84FF;
    font-weight: 500;
}

QListWidget#SidebarList::item:hover:!selected {
    background-color: #2C2C2E;
}

QListWidget#SidebarList::item:selected:active {
    background-color: #0A3A5C;
}

/* 侧边栏标题 */
#SidebarTitle {
    font-size: 11px;
    font-weight: 600;
    color: #636366;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 16px 16px 8px 16px;
}

/* ==================== 主内容区域 ==================== */
#ContentWidget {
    background-color: rgba(28, 28, 30, 0.82);
    border-radius: 14px;
}

#ToolbarWidget {
    background-color: rgba(44, 44, 46, 0.45);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}

/* ==================== 设置页 ==================== */
#SettingsPage {
    background-color: #1C1C1E;
}

QScrollArea#SettingsPageScroll {
    background-color: #1C1C1E;
    border: none;
    outline: none;
}

QScrollArea#SettingsPageScroll::viewport {
    background-color: #1C1C1E;
}

#SettingsPageContainer {
    background-color: rgba(36, 36, 38, 0.65);
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.08);
}

#SettingsPage QPushButton.QPushButton__secondary {
    max-width: 280px;
}

QGroupBox {
    background-color: rgba(38, 38, 40, 0.55);
    border: 1px solid rgba(58, 58, 60, 0.55);
    border-radius: 18px;
    margin-top: 16px;
    padding: 20px 20px 14px 20px;
    font-weight: 500;
    color: #FFFFFF;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 10px;
    background-color: transparent;
    color: #E5E5EA;
}

/* ==================== 搜索栏样式 ==================== */
#SearchBarWidget {
    background-color: rgba(44, 44, 46, 0.92);
    border-radius: 14px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 8px 12px;
}

#SearchLineEdit {
    background-color: transparent;
    border: none;
    font-size: 14px;
    color: #FFFFFF;
    padding: 0px;
}

#SearchLineEdit:focus {
    outline: none;
}

#SearchLineEdit::placeholder {
    color: #636366;
}

#SearchModeButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
    color: #636366;
}

#SearchModeButton:hover {
    background-color: #3A3A3C;
    color: #FFFFFF;
}

/* ==================== 网格视图样式 ==================== */
#FileGridView {
    background-color: #1C1C1E;
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
    background-color: #1A3A5C;
    border: 2px solid #0A84FF;
}

#FileGridView::item:hover {
    background-color: #2C2C2E;
}

/* ==================== 列表视图样式 ==================== */
#FileTableView {
    background-color: #1C1C1E;
    border: none;
    outline: none;
    gridline-color: #3A3A3C;
}

#FileTableView::item {
    background-color: transparent;
    border: none;
    border-bottom: 1px solid #2C2C2E;
    padding: 8px 12px;
    color: #FFFFFF;
}

#FileTableView::item:selected {
    background-color: #1A3A5C;
    color: #0A84FF;
}

#FileTableView::item:hover:!selected {
    background-color: #2C2C2E;
}

/* 表头样式 */
QHeaderView::section {
    background-color: #2C2C2E;
    color: #636366;
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid #3A3A3C;
    border-right: 1px solid #3A3A3C;
}

QHeaderView::section:only-one {
    border-right: none;
}

QHeaderView::section:hover {
    background-color: #3A3A3C;
}

/* ==================== 上传队列样式 ==================== */
#UploadQueueWidget {
    background-color: rgba(28, 28, 30, 0.65);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding: 12px 16px;
}

#UploadItemWidget {
    background-color: rgba(44, 44, 46, 0.88);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 10px 14px;
    margin-bottom: 8px;
}

QProgressBar#UploadProgressBar {
    background-color: #3A3A3C;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}

QProgressBar#UploadProgressBar::chunk {
    background-color: #0A84FF;
    border-radius: 4px;
}

/* ==================== 状态栏样式 ==================== */
#StatusBarWidget {
    background-color: rgba(28, 28, 30, 0.6);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding: 8px 16px;
    color: #636366;
    font-size: 12px;
}

#StatusBarWidget QLabel {
    color: #636366;
}

/* 存储空间进度条 */
QProgressBar#StorageProgressBar {
    background-color: #3A3A3C;
    border: none;
    border-radius: 4px;
    height: 6px;
    min-width: 120px;
    text-align: center;
}

QProgressBar#StorageProgressBar::chunk {
    background-color: #0A84FF;
    border-radius: 4px;
}

/* 状态指示灯 */
#StatusIndicator {
    width: 8px;
    height: 8px;
    border-radius: 4px;
    background-color: #30D158;
}

#StatusIndicator#StatusIndicator__warning {
    background-color: #FF9F0A;
}

#StatusIndicator#StatusIndicator__danger {
    background-color: #FF453A;
}

/* ==================== 对话框样式 ==================== */
QDialog {
    background-color: #2C2C2E;
}

QDialog QLabel {
    color: #FFFFFF;
}

QDialog QPushButton {
    min-width: 100px;
}

/* ==================== 消息提示样式 ==================== */
QMessageBox {
    background-color: #2C2C2E;
}

QMessageBox QLabel {
    color: #FFFFFF;
    padding: 10px;
}

/* ==================== 工具提示样式 ==================== */
QToolTip {
    background-color: #3A3A3C;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}

/* ==================== 组合框样式 ==================== */
QComboBox {
    background-color: rgba(44, 44, 46, 0.9);
    border: 1px solid #3A3A3C;
    border-radius: 12px;
    padding: 10px 14px;
    font-size: 14px;
    color: #FFFFFF;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #545458;
}

QComboBox:focus {
    border-color: #0A84FF;
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
    border-top: 6px solid #636366;
    margin-right: 8px;
}

QComboBox QAbstractItemView, QComboBox QListView {
    background-color: #2C2C2E;
    border: 1px solid #3A3A3C;
    border-radius: 12px;
    padding: 8px;
    selection-background-color: #1A3A5C;
    selection-color: #0A84FF;
    color: #FFFFFF;
    outline: none;
}

QComboBox QAbstractItemView::item {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    margin: 2px 4px;
    color: #FFFFFF;
}

QComboBox QAbstractItemView::item:hover {
    background-color: rgba(58, 58, 60, 0.8);
}

QComboBox QAbstractItemView::item:selected {
    background-color: #1A3A5C;
    color: #0A84FF;
}

/* ==================== 菜单样式 ==================== */
QMenu {
    background-color: #2C2C2E;
    border: 1px solid #3A3A3C;
    border-radius: 8px;
    padding: 6px;
}

QMenu::item {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 8px 24px 8px 12px;
    color: #FFFFFF;
}

QMenu::item:selected {
    background-color: #1A3A5C;
    color: #0A84FF;
}

QMenu::separator {
    height: 1px;
    background-color: #3A3A3C;
    margin: 6px 0px;
}

/* ==================== 空状态样式 ==================== */
#EmptyStateWidget {
    background-color: transparent;
}

#EmptyStateWidget QLabel {
    color: #636366;
    font-size: 15px;
}

/* ==================== 拖拽高亮样式 ==================== */
#DropZoneOverlay {
    background-color: rgba(10, 132, 255, 0.2);
    border: 2px dashed #0A84FF;
    border-radius: 12px;
}

QWidget#DropOverlayFrosted {
    background-color: rgba(44, 44, 46, 0.62);
    border: 2px dashed rgba(10, 132, 255, 0.55);
    border-radius: 18px;
}

QWidget#DropOverlayFrosted QLabel#DropOverlayTitle {
    font-size: 22px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.92);
    background: transparent;
}

QWidget#DropOverlayFrosted QLabel#DropOverlayHint {
    font-size: 13px;
    color: rgba(235, 235, 245, 0.72);
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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A84FF, stop:1 #0066CC);
    border: none;
    color: white;
    font-weight: 500;
}

#LoginPage QPushButton#LoginSubmitButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #409CFF, stop:1 #2080E0);
}

#LoginPage QPushButton#LoginSubmitButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0066CC, stop:1 #0050A0);
}

#LoginPage QPushButton#LoginSubmitButton:disabled {
    background: #3A3A3C;
    color: #636366;
}

/* ==================== 登录毛玻璃卡片 ==================== */
#LoginGlassCard {
    background-color: rgba(44, 44, 46, 0.72);
    border-radius: 22px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

#LoginPage QPushButton#LoginSwitchLink {
    background: transparent;
    color: #0A84FF;
    border: none;
    font-size: 13px;
    font-weight: 500;
}

#LoginPage QPushButton#LoginSwitchLink:hover {
    text-decoration: underline;
    color: #409CFF;
}

/* ==================== 运维看板 ==================== */
#OpsDashboardPage QLabel#OpsPageTitle {
    color: #0A84FF;
    letter-spacing: -0.3px;
}

#OpsDashboardPage QLabel#OpsPageSubtitle,
#OpsDashboardPage QLabel#OpsHintLabel,
#OpsDashboardPage QLabel#OpsLogPathLabel {
    color: #98989D;
    font-size: 12px;
}

#OpsDashboardPage QFrame#OpsMetricCard {
    background-color: rgba(255, 255, 255, 0.07);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

#OpsDashboardPage QLabel#OpsCardTitle {
    color: #98989D;
    font-size: 11px;
    font-weight: 500;
}

#OpsDashboardPage QLabel#OpsCardValue {
    font-size: 20px;
    font-weight: 600;
    color: #FFFFFF;
}

QTabWidget#OpsDashboardTabs::pane {
    border: none;
    background: transparent;
    top: 2px;
}

QTabWidget#OpsDashboardTabs QTabBar::tab {
    background-color: rgba(255, 255, 255, 0.06);
    color: #AEAEB2;
    border: none;
    padding: 10px 22px;
    margin-right: 6px;
    border-radius: 12px;
    min-width: 76px;
    font-weight: 500;
}

QTabWidget#OpsDashboardTabs QTabBar::tab:selected {
    background-color: #0A84FF;
    color: #FFFFFF;
    font-weight: 600;
}

QTabWidget#OpsDashboardTabs QTabBar::tab:hover:!selected {
    background-color: rgba(10, 132, 255, 0.2);
    color: #FFFFFF;
}

QTextEdit#OpsLogView {
    background-color: rgba(28, 28, 30, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 10px;
    color: #E5E5EA;
    selection-background-color: #0A84FF;
    selection-color: #FFFFFF;
}
"""
