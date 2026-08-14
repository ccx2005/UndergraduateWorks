"""JPG/PNG → ICO 转换工具（PyQt5 前端 · 深色工作室风 · 自适应缩放）。

设计遵循项目根 .impeccable.md 的 Design Context：
- 深色工作室风：炭黑（非纯黑）基底 + 暖琥珀单一强调色。
- 精准工程感：信息密度优先、克制圆角、真实反馈、不打断流程。
- 自适应缩放：所有字号/间距/预览区随窗口尺寸等比缩放；
  文字相对 UI 的比例增强（TEXT_BOOST，当前 1.5）。

功能：
- 拖拽或点击选择源图片（JPG/PNG），棋盘格底实时预览（直观展示透明通道）。
- 指定输出 .ico 路径（默认与源同目录同名）。
- 可选：选择 .lnk 快捷方式，转换完成后自动应用图标。
- 转换结果以内联状态面板反馈，并展示真实嵌入的尺寸档位。

运行：python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from converter import convert_to_ico, get_ico_sizes, set_shortcut_icon

IMAGE_FILTER = "图片文件 (*.jpg *.jpeg *.png);;所有文件 (*.*)"
ICO_FILTER = "ICO 文件 (*.ico);;所有文件 (*.*)"
LNK_FILTER = "快捷方式 (*.lnk);;所有文件 (*.*)"

ACCENT = "#E8A33D"  # 暖琥珀——唯一强调色

# ---------------------------------------------------------------- 缩放体系
TEXT_BOOST = 1.5    # 文字相对 UI 的比例增强系数（用户要求进一步增大）
BASE_W, BASE_H = 680, 880   # 设计基准窗口尺寸（scale == 1.0 时的状态）
SCALE_MIN, SCALE_MAX = 0.72, 1.6


def build_qss(scale: float) -> str:
    """按缩放系数生成完整 QSS：字号/内边距/控件高度全部随 scale 等比变化。

    Args:
        scale: 窗口缩放系数，>= 1 表示比基准更大。字号额外乘 TEXT_BOOST。

    Returns:
        可直接 setStyleSheet 的样式表字符串。
    """

    def s(n: float) -> int:
        """字号：基准值 × 文字增强 × 窗口缩放。"""
        return max(1, round(n * TEXT_BOOST * scale))

    def d(n: float) -> int:
        """非字号尺寸（内边距/高度等）：仅随窗口缩放。"""
        return max(1, round(n * scale))

    return f"""
* {{
    font-family: "Segoe UI Variable Text", "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
}}

QWidget {{
    background-color: #1B1E23;
    color: #E8EAED;
    font-size: {s(12)}px;
}}

/* ---------- 头部 ---------- */
QLabel#Title {{
    color: #F0F2F4;
    font-size: {s(18)}px;
    font-weight: 600;
    font-family: "Microsoft YaHei UI", "Segoe UI Variable Text";
}}
QLabel#Subtitle {{
    color: #8A939F;
    font-size: {s(10)}px;
    font-family: "Bahnschrift", "Segoe UI";
}}

/* ---------- 分区与提示 ---------- */
QLabel#Section {{
    color: #9AA3AE;
    font-size: {s(11)}px;
    font-weight: 600;
    font-family: "Microsoft YaHei UI", "Segoe UI";
}}
QLabel#Hint {{
    color: #6B7480;
    font-size: {s(11)}px;
}}
QLabel#Meta {{
    color: #6B7480;
    font-size: {s(11)}px;
}}

/* ---------- 输入框 ---------- */
QLineEdit#PathEdit {{
    background-color: #14171B;
    color: #DDE1E6;
    border: 1px solid #2E343D;
    border-radius: 6px;
    padding: {d(8)}px {d(10)}px;
    font-size: {s(12)}px;
    font-family: "Cascadia Code", "Consolas", "Microsoft YaHei UI";
    selection-background-color: #E8A33D;
    selection-color: #14171B;
}}
QLineEdit#PathEdit:focus {{ border: 1px solid #E8A33D; }}
QLineEdit#PathEdit:disabled {{ color: #5A6270; background-color: #171A1F; }}

/* ---------- 按钮 ---------- */
QPushButton {{
    background-color: #2A2F37;
    color: #DDE1E6;
    border: 1px solid #3A4148;
    border-radius: 6px;
    padding: {d(8)}px {d(14)}px;
    font-size: {s(12)}px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: #333A44; border-color: #4A5460; }}
QPushButton:pressed {{ background-color: #23272E; }}
QPushButton:disabled {{ color: #5A6270; background-color: #20242A; border-color: #2E343D; }}

QPushButton#Primary {{
    background-color: #E8A33D;
    color: #1B1E23;
    border: none;
    border-radius: 7px;
    padding: {d(11)}px {d(16)}px;
    font-size: {s(13)}px;
    font-weight: 700;
    font-family: "Microsoft YaHei UI", "Segoe UI";
}}
QPushButton#Primary:hover {{ background-color: #F6B352; }}
QPushButton#Primary:pressed {{ background-color: #C98A1E; }}
QPushButton#Primary:disabled {{ background-color: #3A4148; color: #6B7480; }}

QPushButton#Ghost {{
    background: transparent;
    border: 1px solid #3A4148;
    color: #B9C1CA;
}}
QPushButton#Ghost:hover {{ background-color: #22262D; border-color: #5A6270; color: #E8EAED; }}

/* ---------- 复选框 ---------- */
QCheckBox {{
    color: #DDE1E6;
    font-size: {s(12)}px;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: {d(16)}px;
    height: {d(16)}px;
    border-radius: 4px;
    border: 1px solid #4A5460;
    background: #14171B;
}}
QCheckBox::indicator:hover {{ border-color: #E8A33D; }}
QCheckBox::indicator:checked {{
    background: #E8A33D;
    border-color: #E8A33D;
}}
QCheckBox:disabled {{ color: #5A6270; }}
QCheckBox:disabled::indicator {{ border-color: #2E343D; }}

/* ---------- 状态面板 ---------- */
QFrame#StatusPanel {{
    background-color: #14171B;
    border: 1px solid #2E343D;
    border-radius: 8px;
}}
QLabel#StatusText {{ font-size: {s(12)}px; }}
QLabel#StatusText[kind="info"] {{ color: #9AA3AE; }}
QLabel#StatusText[kind="ok"]   {{ color: #7ED3A6; }}
QLabel#StatusText[kind="err"]  {{ color: #E8846B; }}

/* ---------- 尺寸 chips ---------- */
QLabel#Chip {{
    background-color: #22262D;
    border: 1px solid #333A44;
    border-radius: 4px;
    color: #9AA3AE;
    padding: {d(2)}px {d(8)}px;
    font-size: {s(11)}px;
    font-family: "Bahnschrift", "Cascadia Code", "Consolas";
}}

/* ---------- 分隔线 ---------- */
QFrame#Divider {{
    background-color: #2E343D;
    max-height: 1px;
    border: none;
}}
"""


def _make_mark(size: int = 34) -> QPixmap:
    """生成头部 Logo：琥珀圆角方块内嵌深色菱形（芯片意象，工程感）。"""
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ACCENT))
    p.drawRoundedRect(0, 0, size, size, 8, 8)
    p.setBrush(QColor("#1B1E23"))
    p.save()
    p.translate(size / 2, size / 2)
    p.rotate(45)
    p.drawRect(-7, -7, 14, 14)
    p.restore()
    p.end()
    return pix


class PreviewWidget(QWidget):
    """棋盘格底预览区：透明通道一目了然；支持点击选择与拖拽导入。"""

    clicked = pyqtSignal()
    file_dropped = pyqtSignal(str)

    _IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._dragging = False
        self._scale = 1.0
        self.setCursor(Qt.PointingHandCursor)
        self.setAcceptDrops(True)
        self.setToolTip("拖入图片或点击选择")

    def set_scale(self, scale: float) -> None:
        self._scale = scale
        self.update()

    def set_image(self, path: str) -> None:
        self._pixmap = QPixmap(path) if path else None
        self.update()

    def clear_image(self) -> None:
        self._pixmap = None
        self.update()

    # ------------------------------------------------------------ 绘制
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        pad = max(6, round(16 * self._scale))

        # 8px 灰阶交替棋盘格，模拟透明背景（图标工具的领域细节）
        tile = 8
        for y in range(0, rect.height(), tile):
            for x in range(0, rect.width(), tile):
                light = (x // tile + y // tile) % 2 == 0
                painter.fillRect(
                    x, y, tile, tile, QColor("#1F242B" if light else "#272D36")
                )

        if self._dragging:
            painter.setPen(QPen(QColor(ACCENT), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 10, 10)
            font = QFont()
            font.setPixelSize(max(12, round(13 * TEXT_BOOST * self._scale)))
            painter.setFont(font)
            painter.setPen(QColor(ACCENT))
            painter.drawText(rect, Qt.AlignCenter, "松开以载入图片")
        elif self._pixmap and not self._pixmap.isNull():
            inner = rect.size() - QSize(pad, pad)
            scaled = self._pixmap.scaled(
                inner, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (rect.width() - scaled.width()) // 2
            y = (rect.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.setPen(QPen(QColor("#2E343D"), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 10, 10)
        else:
            font = QFont()
            font.setPixelSize(max(12, round(13 * TEXT_BOOST * self._scale)))
            painter.setFont(font)
            painter.setPen(QColor("#6B7480"))
            painter.drawText(rect, Qt.AlignCenter, "拖入图片 / 点击选择")

        painter.end()

    # ------------------------------------------------------------ 拖拽
    @staticmethod
    def _first_image(urls) -> str | None:
        for url in urls:
            p = url.toLocalFile()
            if p and Path(p).suffix.lower() in PreviewWidget._IMAGE_EXTS:
                return p
        return None

    def _droppable(self, event) -> bool:
        return PreviewWidget._first_image(event.mimeData().urls()) is not None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._droppable(event):
            self._dragging = True
            event.acceptProposedAction()
        else:
            event.ignore()
        self.update()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        self.update()

    def dropEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        path = PreviewWidget._first_image(event.mimeData().urls())
        if path:
            self.file_dropped.emit(path)
            event.acceptProposedAction()
        else:
            event.ignore()
        self.update()

    # ------------------------------------------------------------ 点击
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MainWindow(QWidget):
    """主窗口：源图选择/预览 → 输出设置 → 快捷方式应用 → 转换反馈。"""

    def __init__(self) -> None:
        super().__init__()
        self._src_path: str | None = None
        self._ico_path: str | None = None
        self._lnk_path: str | None = None
        self._scale = 1.0
        self.setWindowTitle("图标工坊 · 图片转 ICO")
        self.setMinimumSize(600, 800)
        self.resize(BASE_W, BASE_H)
        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_scale(1.0)
        self._set_status("拖入或选择一张 JPG / PNG 图片，生成可直接用于快捷方式的 ICO。", "info")

    # ------------------------------------------------------------ UI
    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Section")
        return label

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        self._root = layout

        # ---- 头部
        header = QHBoxLayout()
        header.setSpacing(12)
        self._mark = QLabel()
        mark_size = round(34 * self._scale)
        self._mark.setFixedSize(mark_size, mark_size)
        self._mark.setPixmap(_make_mark(mark_size))
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("图标工坊")
        title.setObjectName("Title")
        subtitle = QLabel("IMAGE → ICO · SHORTCUT-READY ICONS")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(self._mark)
        header.addLayout(title_box)
        header.addStretch(1)
        layout.addLayout(header)

        # ---- 源图片
        layout.addWidget(self._section("源图片  JPG / PNG"))
        src_row = QHBoxLayout()
        src_row.setSpacing(8)
        self.src_edit = QLineEdit()
        self.src_edit.setObjectName("PathEdit")
        self.src_edit.setReadOnly(True)
        self.src_edit.setPlaceholderText("点击下方预览区，或将图片拖入窗口")
        src_btn = QPushButton("选择图片…")
        src_btn.setObjectName("Ghost")
        src_btn.clicked.connect(self._choose_source)
        src_row.addWidget(self.src_edit, 1)
        src_row.addWidget(src_btn)
        layout.addLayout(src_row)

        # ---- 预览（棋盘格 + 拖拽）
        self.preview = PreviewWidget()
        self.preview.setFixedSize(round(230 * self._scale), round(230 * self._scale))
        self.preview.clicked.connect(self._choose_source)
        self.preview.file_dropped.connect(self._load_source)
        layout.addWidget(self.preview, alignment=Qt.AlignHCenter)
        self.meta_label = QLabel("未载入图片")
        self.meta_label.setObjectName("Meta")
        self.meta_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.meta_label)

        layout.addWidget(self._make_divider())

        # ---- 输出 ICO
        layout.addWidget(self._section("输出 ICO"))
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self.out_edit = QLineEdit()
        self.out_edit.setObjectName("PathEdit")
        self.out_edit.setReadOnly(True)
        self.out_edit.setPlaceholderText("默认与源图片同目录、同名 .ico")
        out_btn = QPushButton("浏览…")
        out_btn.setObjectName("Ghost")
        out_btn.clicked.connect(self._choose_output)
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(out_btn)
        layout.addLayout(out_row)

        # ---- 快捷方式应用
        self.apply_chk = QCheckBox("转换后同时应用到快捷方式 (.lnk)")
        self.apply_chk.stateChanged.connect(self._on_apply_toggled)
        layout.addWidget(self.apply_chk)
        lnk_row = QHBoxLayout()
        lnk_row.setSpacing(8)
        self.lnk_edit = QLineEdit()
        self.lnk_edit.setObjectName("PathEdit")
        self.lnk_edit.setReadOnly(True)
        self.lnk_edit.setPlaceholderText("勾选后选择 .lnk 快捷方式")
        lnk_btn = QPushButton("选择 .lnk…")
        lnk_btn.setObjectName("Ghost")
        lnk_btn.clicked.connect(self._choose_lnk)
        lnk_row.addWidget(self.lnk_edit, 1)
        lnk_row.addWidget(lnk_btn)
        layout.addLayout(lnk_row)
        self._lnk_row_widgets = (self.lnk_edit, lnk_btn)
        self._set_lnk_enabled(False)

        # ---- 嵌入尺寸 chips（转换后展示真实档位）
        chips_row = QHBoxLayout()
        chips_row.setSpacing(6)
        self.chips_label = self._section("嵌入尺寸")
        self.chips_layout = QHBoxLayout()
        self.chips_layout.setSpacing(6)
        chips_row.addWidget(self.chips_label)
        chips_row.addLayout(self.chips_layout)
        chips_row.addStretch(1)
        self.chips_box = QWidget()
        self.chips_box.setLayout(chips_row)
        self.chips_box.hide()
        layout.addWidget(self.chips_box)

        layout.addStretch(1)

        # ---- 主操作
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setObjectName("Primary")
        self.convert_btn.setMinimumHeight(round(42 * self._scale))
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self._convert)
        layout.addWidget(self.convert_btn)

        # ---- 状态面板（内联反馈，不弹窗打断）
        self.status_panel = QFrame()
        self.status_panel.setObjectName("StatusPanel")
        panel_l = QHBoxLayout(self.status_panel)
        panel_l.setContentsMargins(12, 10, 12, 10)
        self.status = QLabel()
        self.status.setObjectName("StatusText")
        self.status.setWordWrap(True)
        panel_l.addWidget(self.status)
        layout.addWidget(self.status_panel)

        # ---- 底部提示
        hint = QLabel("提示：生成后右键快捷方式 → 属性 → 更改图标，即可替换。")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

    @staticmethod
    def _make_divider() -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        line.setFixedHeight(1)
        return line

    def _set_lnk_enabled(self, enabled: bool) -> None:
        for w in self._lnk_row_widgets:
            w.setEnabled(enabled)

    def _set_status(self, text: str, kind: str = "info") -> None:
        self.status.setText(text)
        self.status.setProperty("kind", kind)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    # ------------------------------------------------------------ 自适应缩放
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not hasattr(self, "preview"):
            return
        size = event.size()
        s = min(size.width() / BASE_W, size.height() / BASE_H)
        s = max(SCALE_MIN, min(SCALE_MAX, s))
        if abs(s - self._scale) > 0.005:
            self._apply_scale(s)

    def _apply_scale(self, scale: float) -> None:
        """按新缩放系数整体重排：样式表、边距、预览、Logo、chips。"""
        self._scale = scale
        self.setStyleSheet(build_qss(scale))

        m = round(22 * scale)
        sp = round(12 * scale)
        self._root.setContentsMargins(m, m, m, m)
        self._root.setSpacing(sp)

        ps = round(230 * scale)
        self.preview.set_scale(scale)
        self.preview.setFixedSize(ps, ps)

        ms = round(34 * scale)
        self._mark.setFixedSize(ms, ms)
        self._mark.setPixmap(_make_mark(ms))

        self.convert_btn.setMinimumHeight(round(42 * scale))

        for i in range(self.chips_layout.count()):
            chip = self.chips_layout.itemAt(i).widget()
            if chip:
                chip.setFixedHeight(round(22 * TEXT_BOOST * scale))

    # ------------------------------------------------------------ 交互
    def _choose_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", IMAGE_FILTER)
        if path:
            self._load_source(path)

    def _load_source(self, path: str) -> None:
        """统一入口：对话框选择、拖拽、点击预览都会走到这里。"""
        self._src_path = path
        self.src_edit.setText(path)
        self.preview.set_image(path)
        self._update_meta(path)
        default_out = str(Path(path).with_suffix(".ico"))
        self.out_edit.setText(default_out)
        self._ico_path = default_out
        self.chips_box.hide()
        self.convert_btn.setEnabled(True)
        self._set_status(f"已载入 {path}，点击「开始转换」。", "ok")

    def _update_meta(self, path: str) -> None:
        pix = QPixmap(path)
        if pix.isNull():
            self.meta_label.setText("无法预览此文件")
            return
        alpha = pix.toImage().hasAlphaChannel()
        mode = "RGBA · 含透明" if alpha else "RGB · 无透明"
        self.meta_label.setText(f"源图 {pix.width()} × {pix.height()} · {mode}")

    def _choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存 ICO", "", ICO_FILTER)
        if path:
            if not path.lower().endswith(".ico"):
                path += ".ico"
            self.out_edit.setText(path)
            self._ico_path = path

    def _choose_lnk(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择快捷方式", "", LNK_FILTER)
        if path:
            self._lnk_path = path
            self.lnk_edit.setText(path)

    def _on_apply_toggled(self, state: int) -> None:
        self._set_lnk_enabled(state == Qt.Checked)
        if state != Qt.Checked:
            self._lnk_path = None
            self.lnk_edit.clear()

    # ------------------------------------------------------------ 转换
    def _convert(self) -> None:
        if not self._src_path:
            self._set_status("请先选择一张源图片。", "err")
            return

        out_path = self._ico_path or str(Path(self._src_path).with_suffix(".ico"))
        self.convert_btn.setEnabled(False)
        self._set_status("正在转换…", "info")
        QApplication.processEvents()  # 先刷新一次界面

        try:
            ico = convert_to_ico(self._src_path, out_path)
        except Exception as exc:  # noqa: BLE001
            self.convert_btn.setEnabled(True)
            self._set_status(f"转换失败：{exc}", "err")
            return

        # 真实嵌入档位
        try:
            embedded = get_ico_sizes(ico)
            self._render_chips([s[0] for s in embedded])
        except Exception:  # noqa: BLE001 - 读档位失败不影响主流程
            embedded = []

        msgs = [f"已生成 ICO：{ico}"]

        if self.apply_chk.isChecked():
            if not self._lnk_path:
                msgs.append("已勾选应用快捷方式，但未选择 .lnk 文件，已跳过。")
            elif set_shortcut_icon(self._lnk_path, str(ico)):
                msgs.append(f"已应用到快捷方式：{self._lnk_path}")
            else:
                msgs.append(
                    "未能自动设置快捷方式图标（缺少 pywin32 或权限不足）；"
                    "可右键 .lnk → 属性 → 更改图标 手动选择该 ICO。"
                )

        if embedded:
            joined = " / ".join(str(s[0]) for s in embedded)
            msgs.append(f"已嵌入尺寸：{joined}")

        self.convert_btn.setEnabled(True)
        self._set_status("\n".join(msgs), "ok")

    def _render_chips(self, sizes: list[int]) -> None:
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for px in sizes:
            chip = QLabel(str(px))
            chip.setObjectName("Chip")
            chip.setAlignment(Qt.AlignCenter)
            chip.setFixedHeight(round(22 * TEXT_BOOST * self._scale))
            self.chips_layout.addWidget(chip)
        self.chips_box.show()

    # ------------------------------------------------------------ 拖拽（窗口级）
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if PreviewWidget._first_image(event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        path = PreviewWidget._first_image(event.mimeData().urls())
        if path:
            self._load_source(path)
            event.acceptProposedAction()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 跨平台一致的控件绘制，深色主题更稳
    win = MainWindow()  # 窗口自身持有完整 QSS，随缩放重生成
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
