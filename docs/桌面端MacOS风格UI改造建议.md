# AllahPan 桌面端：MacOS 风格 UI 改造建议

> 针对注册/登录页、文件页、设置页的「简约、微微 Q 弹、轻微渐变」MacOS 风格改造，给出**可落地的修改建议**（含具体 QSS、布局与代码位置）。

---

## 一、设计原则（目标风格）

- **简约**：减少视觉噪音，留白适中，主次分明。
- **微微 Q 弹**：大圆角（10px–14px）、轻微阴影、hover/pressed 有过渡动画。
- **轻微渐变**：主按钮用自上而下的浅渐变替代纯色块，避免「一块蓝」的观感。
- **MacOS 感**：毛玻璃/半透明（深色下尤为重要）、统一圆角与字重、避免过宽/过高的控件。

---

## 二、注册/登录页（`login_page.py`）

### 2.1 现状问题

- 表单**随窗口拉满宽度**，输入框和登录按钮过宽，比例失调。
- 输入框、按钮仅有全局 QSS（`theme/light.py`、`theme/dark.py`），无登录页专属约束。
- 主按钮纯色 `#007AFF`，无渐变、无柔和阴影。

### 2.2 修改建议

#### （1）固定表单宽度，居中卡片

- 在 `_setup_ui` 中，不要直接把 `card_layout` 加进 `main_layout`，而是先包一层**固定宽度容器**：
  - 使用一个 `QWidget` 作为「卡片容器」，设置 `setFixedWidth(360)`（或 340–380 之间），`main_layout` 将该容器水平居中。
  - 这样输入框和按钮的宽度由 360px 限制，不会随窗口拉伸。

**代码位置**：`frontend_desktop/pages/login_page.py` 的 `_setup_ui`，约 110–161 行。

**示例结构**：

```python
# 卡片容器：固定宽度，视觉居中
card_container = QWidget()
card_container.setFixedWidth(360)
card_inner_layout = QVBoxLayout(card_container)
card_inner_layout.setSpacing(20)

# 将 username_input, email_input, password_input, submit_button, switch_button, error_label 都加在 card_inner_layout 里
# ...
main_layout.addWidget(card_container)  # 已有 setAlignment(Qt.AlignCenter)，会居中
```

#### （2）输入框比例与圆角

- 高度保持 44–48px 即可，不要更高。
- 圆角在主题里已 8px，可改为 **10–12px** 以更「Q」一点（见第三节全局 QSS）。
- 登录页若需单独覆盖，可对 `self.username_input` 等设置 `setMaximumHeight(48)`，并给登录页的 `#LoginPage QLineEdit` 设 `border-radius: 12px;`。

#### （3）主按钮：渐变 + 圆角 + 阴影

- 主按钮「登录/注册」建议使用**线性渐变** + **稍大圆角** + **轻微阴影**，且宽度由卡片限制，不会拉满屏。
- 渐变示例（浅色主题）：从上 `#0088FF` 到下 `#0066DD`；深色：`#0A84FF` → `#0066CC`。
- 圆角：`border-radius: 12px`（或 14px）。
- 阴影：`box-shadow` 在 QSS 中可用（Qt5.9+），例如 `0 2px 8px rgba(0,122,255,0.35)`。

**登录页专属 QSS 示例**（在 `LoginPage` 的 `setStyleSheet` 或通过 `objectName` 在主题中写）：

```css
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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0088FF, stop:1 #0066DD);
    border: none;
    color: white;
    font-weight: 500;
}
#LoginPage QPushButton#LoginSubmitButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0099FF, stop:1 #0077EE);
}
#LoginPage QPushButton#LoginSubmitButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0066CC, stop:1 #0055BB);
}
```

- 为「登录/注册」按钮设置 `setObjectName("LoginSubmitButton")`，以便上面选择器生效。
- 深色主题可再写一份 `#LoginPage QPushButton#LoginSubmitButton`，使用 `#0A84FF` → `#0066CC` 的渐变。

#### （4）「没有账号？立即注册」链接

- 保持透明背景、主色文字即可，可适当减小字号（如 13px），避免与主按钮视觉权重冲突。

---

## 三、文件页（工具栏大蓝色按钮）（`file_browser.py`）

### 3.1 现状问题

- 「下载」「刷新」使用 `QPushButton`，继承全局主色，**大块纯蓝**，与「上传」的 `QToolButton` 风格不统一且过重。
- 工具栏按钮高度、圆角未做区分，缺乏层次。

### 3.2 修改建议

#### （1）统一为「工具栏按钮」风格（推荐）

- 将 **下载**、**刷新** 改为 `QToolButton`，与「上传」一致，这样会走 `QToolButton` 的 QSS：透明/浅灰底、hover 才显色，不会出现大块蓝。
- **代码位置**：`frontend_desktop/widgets/file_browser.py` 的 `_create_toolbar`（约 112–171 行），把 `self.download_button` 和 `self.refresh_button` 从 `QPushButton` 改为 `QToolButton`，并保留 `clicked` 等信号连接。
- 若希望「下载」在语义上更突出，可单独给该 `QToolButton` 设置 `setObjectName("DownloadToolButton")`，在主题里为其设置**轻微填充**（如浅蓝背景 + 主色文字），而不是整块深蓝。

#### （2）若保留 QPushButton：改为「次要按钮」样式

- 给两个按钮设置：`setProperty("class", "secondary")` 或 `setObjectName`，并在主题中为工具栏内的 `QPushButton` 使用 **secondary** 样式（透明底 + 主色边框 + 主色文字），例如已有：

```css
QPushButton.QPushButton__secondary { ... }
```

- 在 `file_browser.py` 里：
  - `self.download_button.setProperty("class", "QPushButton__secondary"); self.download_button.style().unpolish(self.download_button); self.download_button.style().polish(self.download_button);`
  - 或直接 `self.download_button.setObjectName("")` 并添加 class 后刷新样式。
- 这样按钮变为描边样式，不会「一大块蓝」。

#### （3）工具栏整体圆角与间距

- 在 `theme/light.py` 和 `theme/dark.py` 的 `#ToolbarWidget` 中可增加：
  - `border-radius: 0`（或与侧边栏一致的 0），保持简洁；
  - 对 `#ToolbarWidget QToolButton` 使用 `border-radius: 10px`，padding 一致（如 8px 12px），使图标+文字更「Q」。

---

## 四、设置页（大蓝色按钮 + 深色下展开矩形纯色）（`settings_page.py` + `theme/dark.py`）

### 4.1 现状问题

- 「修改存储路径」「配置远程访问」「退出登录」「查看系统日志」以及 Ollama「启动」「停止」等，均为**全宽或大块**的 `QPushButton`，主色实心，视觉过重。
- 深色主题下，**QComboBox 下拉列表**（主题选择等）和 **QGroupBox** 使用**纯色背景**（如 `#2C2C2E`），展开后一块矩形，与 MacOS 的毛玻璃/半透明不符，观感「硬」。

### 4.2 按钮修改建议

#### （1）设置页内主操作改为「次要按钮」

- 对以下按钮使用**次要样式**（透明底 + 主色边框 + 主色文字）：
  - 修改存储路径、配置远程访问、退出登录、查看系统日志、Ollama 启动/停止等。
- 实现方式：
  - 在 `settings_page.py` 中为上述按钮统一设置：  
    `btn.setProperty("class", "QPushButton__secondary")`  
    并在添加进布局后调用一次 `style().unpolish(btn); style().polish(btn)`（或对父控件刷新），确保 QSS 中的 `QPushButton.QPushButton__secondary` 生效。
  - 或为设置页内这类按钮设统一 `objectName`，例如 `SettingsActionButton`，在主题里写：

```css
#SettingsPage QPushButton#SettingsActionButton {
    background-color: transparent;
    color: /* primary */;
    border: 1px solid /* primary */;
    border-radius: 10px;
    padding: 8px 16px;
    min-height: 36px;
}
#SettingsPage QPushButton#SettingsActionButton:hover {
    background-color: /* primary_light 或 半透明 primary */;
}
```

- 「退出登录」若需强调，可单独用 `QPushButton__danger` 的描边版（红边框+红字），避免大块红。

#### （2）按钮宽度

- 不要 `setMinimumWidth(很大)`；让按钮由文字 + padding 决定宽度，或设 `setMaximumWidth(240)` 一类上限，避免整行一大条。

### 4.3 深色主题下「展开矩形纯色」修改建议（QGroupBox + QComboBox 下拉）

#### （1）QGroupBox：半透明 + 大圆角

- **文件**：`frontend_desktop/theme/dark.py`
- 将 `QGroupBox` 的 `background-color: #2C2C2E` 改为**半透明**，并配合整体背景，形成层次感：
  - 例如：`background-color: rgba(44, 44, 46, 0.6);` 或 `rgba(28, 28, 30, 0.8)`。
  - 若主内容区是 `#1C1C1E`，可用 `rgba(44, 44, 46, 0.5)`，边框 `border: 1px solid rgba(58, 58, 60, 0.8);`。
- 圆角调大：`border-radius: 12px;`，与「Q 弹」一致。
- `QGroupBox::title` 的 `background-color` 与 QGroupBox 一致为半透明，避免标题后出现色块接缝。

**注意**：Qt 在部分平台上对半透明控件与重叠绘制有坑，若发现闪烁或裁切，可退一步用「略浅于页面背景的实色」代替纯黑，例如 `#252528`，视觉上仍比纯 #2C2C2E 柔和。

#### （2）QComboBox 下拉列表：半透明 + 圆角

- **文件**：`frontend_desktop/theme/dark.py` 中 `QComboBox QAbstractItemView` 部分。
- 将下拉列表背景改为半透明 + 圆角，减少「白/灰矩形块」感：
  - `background-color: rgba(44, 44, 46, 0.95);` 或 `rgba(30, 30, 32, 0.98);`
  - `border: 1px solid rgba(58, 58, 60, 0.9);`
  - `border-radius: 10px;`
- 若系统绘制下拉时带有自己的背景，可能仍需用较高不透明度（如 0.98）以保证可读性。
- **浅色主题**：在 `theme/light.py` 中**补充** `QComboBox` 与 `QComboBox QAbstractItemView` 的样式，与深色风格对齐（白/浅灰底、圆角、细边框），避免未定义时出现系统默认的直角白块。

#### （3）毛玻璃（backdrop-filter）说明

- Qt StyleSheet **不支持** `backdrop-filter`。若要做真正的毛玻璃，需要：
  - 用 `QGraphicsEffect` 或自定义 `paintEvent` 在控件上绘制模糊背景，或
  - 使用 Qt Quick / QML。
- 作为折中，上述「半透明背景 + 圆角」已能明显减弱「矩形纯色」的观感；若后续要更强毛玻璃效果，再考虑在设置页容器上单独挂自定义绘制。

---

## 五、全局主题 QSS 的通用微调（`theme/light.py`、`theme/dark.py`）

以下在**全局**做小改动，即可统一「微微 Q 弹 + 轻微渐变」：

### 5.1 主按钮渐变（可选）

- 在 `QPushButton` 中把 `background-color: #007AFF` 改为：

```css
background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #0080FF, stop:1 #0066DD);
```

- 深色主题同理：`stop:0 #0A84FF, stop:1 #0066CC`。
- 若某处希望保持纯色，可用 `objectName` 或 property 排除。

### 5.2 圆角统一加大

- `QPushButton`：`border-radius: 10px` → **12px**。
- `QLineEdit`：`border-radius: 8px` → **10px 或 12px**。
- `#ToolbarWidget QToolButton`：`border-radius: 6px` → **10px**。
- 侧边栏 `#SidebarList::item`、`#FileGridView::item` 等已 6–8px，可酌情改为 10px。

### 5.3 轻微阴影（主按钮）

- 在 `QPushButton` 上增加（仅部分 Qt 版本支持 box-shadow，需实测）：
  - `box-shadow: 0 2px 8px rgba(0, 122, 255, 0.25);`
- 若不支持，可保持无阴影，仅用渐变 + 圆角也能明显改善。

### 5.4 浅色主题补充 QComboBox

- 在 `theme/light.py` 中增加与 `dark.py` 结构一致的 `QComboBox`、`QComboBox::drop-down`、`QComboBox QAbstractItemView` 等，背景用 `#FFFFFF` 或 `#F5F5F7`，边框 `#D2D2D7`，圆角 8–10px，避免设置页主题下拉在浅色下使用系统默认样式。

---

## 六、实施顺序建议

| 优先级 | 项目 | 文件/位置 |
|--------|------|-----------|
| 高 | 登录页固定宽度卡片（360px） | `login_page.py` `_setup_ui` |
| 高 | 登录页主按钮渐变+圆角+objectName | `login_page.py` + 主题 QSS |
| 高 | 文件页「下载」「刷新」改为 QToolButton 或 secondary | `file_browser.py` `_create_toolbar` |
| 高 | 设置页所有操作按钮改为 secondary / 小尺寸 | `settings_page.py` 各 `_create_*_group` |
| 中 | 深色 QGroupBox 半透明 + 大圆角 | `theme/dark.py` |
| 中 | 深色 QComboBox 下拉半透明 + 圆角 | `theme/dark.py` |
| 中 | 浅色主题补充 QComboBox 样式 | `theme/light.py` |
| 低 | 全局 QPushButton 渐变 + 圆角 12px | `theme/light.py`、`theme/dark.py` |
| 低 | 工具栏 QToolButton 圆角 10px | 同上 |

---

## 七、小结

- **登录页**：固定宽度卡片（约 360px）+ 输入框/主按钮比例约束 + 主按钮渐变与 12px 圆角，即可解决「比例不行、一块蓝」。
- **文件页**：工具栏「下载」「刷新」改为 QToolButton 或 secondary 样式，避免大蓝块，与「上传」统一。
- **设置页**：所有大蓝按钮改为次要/描边样式；深色下 QGroupBox、QComboBox 下拉使用半透明+大圆角，减少矩形纯色块感。
- **全局**：主按钮可选用轻微渐变、统一 10–12px 圆角，浅色主题补全 QComboBox，整体即趋向「简约、微微 Q 弹、轻微渐变」的 MacOS 风格。

按上述顺序在现有 PySide6 + QSS 架构下即可逐步落地，无需引入新依赖。
