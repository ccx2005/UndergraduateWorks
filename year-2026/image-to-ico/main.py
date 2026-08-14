"""JPG/PNG → ICO 转换工具（PyQt5 前端 · 深色工作室风 · 自适应缩放 · 批量 + 各尺寸预览）。

设计遵循项目根 .impeccable.md 的 Design Context：
- 深色工作室风：炭黑（非纯黑）基底 + 暖琥珀单一强调色。
- 精准工程感：信息密度优先、克制圆角、真实反馈、不打断流程。
- 自适应缩放：所有字号/间距/预览区随窗口尺寸等比缩放；
  文字相对 UI 的比例增强（TEXT_BOOST，当前 1.5）。

新增能力（相对初版）：
- 批量队列：多选图片 / 拖入多张，一次性全部转 ICO，状态逐条反馈、末尾汇总。
- 各尺寸预览：转换后按选中项渲染 ICO 内每个嵌入尺寸（16/32/48/…）的透明缩略图，
  棋盘格底直观验证清晰度与透明通道。

运行：python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from converter import (
    convert_to_ico,
    get_ico_sizes,
    set_shortcut_icon,
)

IMAGE_FILTER = "图片文件 (*.jpg *.jpeg *.png);;所有文件 (*.*)"
LNK_FILTER = "快捷方式 (*.lnk);;所有文件 (*.*)"

ACCENT = "#E8A33D"  # 暖琥珀——唯一强调色

# ---------------------------------------------------------------- 缩放体系
TEXT_BOOST = 1.5    # 文字相对 UI 的比例增强系数
BASE_W, BASE_H = 700, 940   # 设计基准窗口尺寸（scale == 1.0 时的状态）
SCALE_MIN, SCALE_MAX = 0.72, 1.6


def build_qss(scale: float) -> str:
    """按缩放系数生成完整 QSS：字号/内边距/控件高度全部随 scale 等比变化。"""

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

/* ---------- 队列列表 ---------- */
QListWidget#Queue {{
    background-color: #14171B;
    border: 1px solid #2E343D;
    border-radius: 8px;
    padding: {d(4)}px;
    font-size: {s(12)}px;
    outline: 0;
}}
QListWidget#Queue::item {{
    background-color: #1B1E23;
    border-radius: 5px;
    padding: {d(7)}px {d(10)}px;
    color: #DDE1E6;
}}
QListWidget#Queue::item:selected {{
    background-color: #2A2F37;
    border: 1px solid {ACCENT};
}}
QListWidget#Queue::item:hover {{
    background-color: #22262D;
}}

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

/* ---------- 尺寸 chips / 缩略图标签 ---------- */
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


def pil_to_pixmap(pil_img: Image.Image) -> QPixmap:
    """把 PIL 图像（RGBA）转为 QPixmap，保持原始尺寸。"""
    im = pil_img.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    qimg = QImage(data, im.width, im.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class SizePreviewWidget(QWidget):
    """单个 ICO 尺寸的缩略图：棋盘格底 + 该尺寸帧（等比居中放在固定显示框内）。"""

    def __init__(self, pil_img: Image.Image, box: int) -> None:
        super().__init__()
        self._box = box
        self.setFixedSize(box, box)
        self._pix = pil_to_pixmap(pil_img)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tile = 8
        for y in range(0, self.height(), tile):
            for x in range(0, self.width(), tile):
                light = (x // tile + y // tile) % 2 == 0
                p.fillRect(x, y, tile, tile, QColor("#1F242B" if light else "#272D36"))
        if self._pix and not self._pix.isNull():
            # 等比缩放放进 box（contain），避免非正方形帧被拉伸变形
            scaled = self._pix.scaled(
                self._box, self._box, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            x = (self._box - scaled.width()) // 2
            y = (self._box - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
        p.end()


class PreviewWidget(QWidget):
    """棋盘格底预览区：透明通道一目了然；支持点击选择与拖拽导入。"""

    clicked = pyqtSignal()
    files_dropped = pyqtSignal(list)

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
    def _collect_images(urls) -> list[str]:
        out: list[str] = []
        for url in urls:
            p = url.toLocalFile()
            if p and Path(p).suffix.lower() in PreviewWidget._IMAGE_EXTS:
                out.append(p)
        return out

    def _droppable(self, event) -> bool:
        return bool(PreviewWidget._collect_images(event.mimeData().urls()))

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
        paths = PreviewWidget._collect_images(event.mimeData().urls())
        if paths:
            self.files_dropped.emit(paths)
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
    """主窗口：图片队列（批量）→ 预览 → 各尺寸预览 → 快捷方式应用 → 转换反馈。"""

    def __init__(self) -> None:
        super().__init__()
        self._items: list[dict] = []   # 队列模型：{path,name,out,status,converted}
        self._lnk_path: str | None = None
        self._scale = 1.0
        self.setWindowTitle("图标工坊 · 图片转 ICO")
        self.setMinimumSize(620, 840)
        self.resize(BASE_W, BASE_H)
        self.setAcceptDrops(True)
        self._build_ui()
        self._apply_scale(1.0)
        self._set_status("添加或拖入一张 / 多张 JPG / PNG，批量生成可直接用于快捷方式的 ICO。", "info")

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
        subtitle = QLabel("IMAGE → ICO · BATCH & MULTI-SIZE PREVIEW")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addWidget(self._mark)
        header.addLayout(title_box)
        header.addStretch(1)
        layout.addLayout(header)

        # ---- 图片队列
        layout.addWidget(self._section("图片队列  JPG / PNG"))
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        add_btn = QPushButton("添加图片…")
        add_btn.setObjectName("Ghost")
        add_btn.clicked.connect(self._choose_sources)
        clear_btn = QPushButton("清空")
        clear_btn.setObjectName("Ghost")
        clear_btn.clicked.connect(self._clear_queue)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.queue = QListWidget()
        self.queue.setObjectName("Queue")
        self.queue.setSelectionMode(QListWidget.SingleSelection)
        self.queue.currentRowChanged.connect(self._on_select)
        layout.addWidget(self.queue, stretch=1)

        # ---- 预览（棋盘格 + 拖拽）
        self.preview = PreviewWidget()
        self.preview.setFixedSize(round(230 * self._scale), round(230 * self._scale))
        self.preview.clicked.connect(self._choose_sources)
        self.preview.files_dropped.connect(self._add_files)
        layout.addWidget(self.preview, alignment=Qt.AlignHCenter)
        self.meta_label = QLabel("未载入图片")
        self.meta_label.setObjectName("Meta")
        self.meta_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.meta_label)

        layout.addWidget(self._make_divider())

        # ---- 各尺寸预览（转换后展示选中项的嵌入档位缩略图）
        self.size_box = QWidget()
        size_outer = QVBoxLayout(self.size_box)
        size_outer.setContentsMargins(0, 0, 0, 0)
        size_outer.setSpacing(6)
        size_outer.addWidget(self._section("嵌入尺寸预览"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.size_content = QWidget()
        self.size_layout = QHBoxLayout(self.size_content)
        self.size_layout.setContentsMargins(0, 0, 0, 0)
        self.size_layout.setSpacing(10)
        self.size_layout.addStretch(1)
        scroll.setWidget(self.size_content)
        size_outer.addWidget(scroll)
        self.size_box.hide()
        layout.addWidget(self.size_box)

        # ---- 快捷方式应用（作用于当前选中项）
        self.apply_chk = QCheckBox("转换后把选中项的图标应用到快捷方式 (.lnk)")
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

        layout.addStretch(1)

        # ---- 主操作
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setObjectName("Primary")
        self.convert_btn.setMinimumHeight(round(42 * self._scale))
        self.convert_btn.setEnabled(False)
        self.convert_btn.clicked.connect(self._convert)
        layout.addWidget(self.convert_btn)

        # ---- 状态面板
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
        hint = QLabel("提示：输出 ICO 默认与源图片同目录、同名；生成后右键 .lnk → 属性 → 更改图标 即可替换。")
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
        """按新缩放系数整体重排：样式表、边距、预览、Logo、各尺寸缩略图。"""
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

        # 各尺寸缩略图随缩放重建（保持选中项的预览不丢）
        sel = self.queue.currentRow()
        if 0 <= sel < len(self._items) and self._items[sel].get("converted"):
            it = self._items[sel]
            self._render_size_preview(it["path"], it["out"])
        else:
            self._clear_size_preview()

    # ------------------------------------------------------------ 队列模型
    def _choose_sources(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", IMAGE_FILTER)
        if paths:
            self._add_files(paths)

    def _add_files(self, paths: list[str]) -> None:
        existing = {it["path"] for it in self._items}
        added = 0
        for p in paths:
            if p in existing:
                continue
            self._items.append(
                {
                    "path": p,
                    "name": Path(p).name,
                    "out": None,
                    "status": "待转换",
                    "converted": False,
                }
            )
            added += 1
        if added:
            self._refresh_queue()
            self.queue.setCurrentRow(len(self._items) - 1)
            self._set_status(f"已加入 {added} 张，共 {len(self._items)} 张待转换。", "info")
        self.convert_btn.setEnabled(bool(self._items))

    def _clear_queue(self) -> None:
        self._items.clear()
        self.queue.clear()
        self.preview.clear_image()
        self.meta_label.setText("未载入图片")
        self._clear_size_preview()
        self.convert_btn.setEnabled(False)
        self._set_status("队列已清空。", "info")

    def _refresh_queue(self) -> None:
        self.queue.blockSignals(True)
        self.queue.clear()
        for it in self._items:
            item = QListWidgetItem(self._queue_text(it))
            item.setData(Qt.UserRole, it["path"])
            self.queue.addItem(item)
        self.queue.blockSignals(False)

    @staticmethod
    def _queue_text(it: dict) -> str:
        if it["converted"]:
            return f"{it['name']}    ✓ 已生成"
        return f"{it['name']}    · {it['status']}"

    def _on_select(self, row: int) -> None:
        if not (0 <= row < len(self._items)):
            self.preview.clear_image()
            self.meta_label.setText("未载入图片")
            self._clear_size_preview()
            return
        it = self._items[row]
        self.preview.set_image(it["path"])
        self._update_meta(it["path"])
        if it.get("converted") and it.get("out"):
            self._render_size_preview(it["path"], it["out"])
        else:
            self._clear_size_preview()

    def _update_meta(self, path: str) -> None:
        pix = QPixmap(path)
        if pix.isNull():
            self.meta_label.setText("无法预览此文件")
            return
        alpha = pix.toImage().hasAlphaChannel()
        mode = "RGBA · 含透明" if alpha else "RGB · 无透明"
        self.meta_label.setText(f"源图 {pix.width()} × {pix.height()} · {mode}")

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

    # ------------------------------------------------------------ 各尺寸预览
    def _clear_size_preview(self) -> None:
        while self.size_layout.count():
            item = self.size_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.size_layout.addStretch(1)
        self.size_box.hide()

    def _render_size_preview(self, src_path: str, ico_path: str) -> None:
        """按 ICO 实际嵌入的尺寸，从源图缩放出每个档位的透明缩略图。

        直接读 ICO 目录（get_ico_sizes）拿到真实嵌入档位，再用源图 resize 到该
        尺寸渲染——这正是 Pillow 写入 ICO 的内容，且绕开了部分 Pillow 版本下
        ICO seek 无法遍历多帧的限制。
        """
        # 清空（含末尾 stretch）
        while self.size_layout.count():
            item = self.size_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        try:
            sizes = get_ico_sizes(ico_path)
            src = Image.open(src_path).convert("RGBA")
        except Exception:  # noqa: BLE001 - 读取失败不致命
            self.size_layout.addStretch(1)
            self.size_box.hide()
            return

        box = max(40, round(56 * self._scale))
        for (w, h) in sizes:
            cell = QWidget()
            cv = QVBoxLayout(cell)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(round(4 * self._scale))
            thumb = src.resize((w, h), Image.LANCZOS)
            pv = SizePreviewWidget(thumb, box)
            cv.addWidget(pv, alignment=Qt.AlignCenter)
            lbl = QLabel(str(w))
            lbl.setObjectName("Chip")
            lbl.setAlignment(Qt.AlignCenter)
            cv.addWidget(lbl)
            self.size_layout.addWidget(cell)

        self.size_layout.addStretch(1)
        self.size_box.show()

    # ------------------------------------------------------------ 转换
    def _convert(self) -> None:
        if not self._items:
            self._set_status("队列为空，请先添加图片。", "err")
            return

        self.convert_btn.setEnabled(False)
        self._set_status(f"正在转换 {len(self._items)} 张…", "info")
        QApplication.processEvents()

        ok = 0
        fail = 0
        first_ico: str | None = None
        for idx, it in enumerate(self._items):
            try:
                out = convert_to_ico(it["path"], None)
                it["out"] = str(out)
                it["converted"] = True
                it["status"] = "已生成"
                ok += 1
                if first_ico is None:
                    first_ico = str(out)
            except Exception as exc:  # noqa: BLE001
                it["converted"] = False
                it["status"] = f"失败：{exc}"
                fail += 1
            # 实时刷新该行文本
            self.queue.item(idx).setText(self._queue_text(it))
            self.queue.item(idx).setData(Qt.UserRole, it["path"])
            QApplication.processEvents()

        msgs = [f"批量完成：成功 {ok} 张，失败 {fail} 张。"]
        if first_ico and ok:
            msgs.append(f"示例输出：{first_ico}")

        # 应用到选中项的快捷方式
        if self.apply_chk.isChecked():
            sel = self.queue.currentRow()
            if not (0 <= sel < len(self._items)) or not self._items[sel].get("converted"):
                msgs.append("已勾选应用快捷方式，但当前选中项未成功生成 ICO，已跳过。")
            elif not self._lnk_path:
                msgs.append("已勾选应用快捷方式，但未选择 .lnk 文件，已跳过。")
            elif set_shortcut_icon(self._lnk_path, self._items[sel]["out"]):
                msgs.append(f"已应用到快捷方式：{self._lnk_path}")
            else:
                msgs.append("未能自动设置快捷方式图标（缺少 pywin32 或权限不足）；可手动更改图标。")

        self.convert_btn.setEnabled(True)
        kind = "ok" if fail == 0 else "err"
        self._set_status("\n".join(msgs), kind)

        # 重新渲染选中项的各尺寸预览
        sel = self.queue.currentRow()
        if 0 <= sel < len(self._items) and self._items[sel].get("converted"):
            it = self._items[sel]
            self._render_size_preview(it["path"], it["out"])
        else:
            self._clear_size_preview()

    # ------------------------------------------------------------ 拖拽（窗口级多文件）
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if any(Path(u.toLocalFile()).suffix.lower() in PreviewWidget._IMAGE_EXTS for u in urls):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = PreviewWidget._collect_images(event.mimeData().urls())
        if paths:
            self._add_files(paths)
            event.acceptProposedAction()


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
