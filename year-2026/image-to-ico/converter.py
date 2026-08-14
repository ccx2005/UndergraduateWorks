"""图片转 ICO 核心逻辑。

负责把 JPG / PNG 转换为 Windows 快捷方式可直接使用的多分辨率 ICO 文件，
并可选地为一个 .lnk 快捷方式设置该图标。

设计要点：
- 嵌入多分辨率（16/24/32/48/64/128/256），保证在任务栏、桌面、资源管理器
  不同缩放下都清晰，不会因单尺寸被拉伸而模糊。
- 统一转成 RGBA，保留 PNG 的透明通道；JPG 无透明则背景不透明。
- .lnk 图标设置依赖 pywin32（Windows only），缺失时优雅降级。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from PIL import Image

# Windows 快捷方式图标常用标准尺寸。256 用于高分屏/大图标视图。
DEFAULT_ICON_SIZES: list[tuple[int, int]] = [
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]


def convert_to_ico(
    source_path: str | os.PathLike,
    output_path: str | os.PathLike | None = None,
    sizes: Iterable[tuple[int, int]] = DEFAULT_ICON_SIZES,
) -> Path:
    """把 JPG/PNG 图片转换为多分辨率 ICO 文件。

    Args:
        source_path: 源图片路径（JPG / PNG）。
        output_path: 输出 .ico 路径。为 None 时默认与源同目录、同名 .ico。
        sizes: 要嵌入 ICO 的 (宽, 高) 尺寸列表。

    Returns:
        生成的 .ico 文件路径。

    Raises:
        FileNotFoundError: 源文件不存在。
        ValueError: 图片无法打开或解码。
    """
    src = Path(source_path)
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {src}")

    out = Path(output_path) if output_path is not None else src.with_suffix(".ico")

    try:
        img = Image.open(src)
    except Exception as exc:  # noqa: BLE001 - 统一兜底为 ValueError
        raise ValueError(f"无法打开图片 {src}: {exc}") from exc

    # 转 RGBA 以保留/补齐 alpha 通道，ICO 才能正确支持透明。
    img = img.convert("RGBA")

    # 按面积降序排列：Pillow 会以原图重采样出每个尺寸，
    # 从大图缩小通常比从小图放大质量更好。
    size_list = sorted(set(sizes), key=lambda s: s[0] * s[1], reverse=True)

    out.parent.mkdir(parents=True, exist_ok=True)
    # format="ICO" + sizes 让 Pillow 把每个尺寸编码进同一个 .ico 容器。
    img.save(out, format="ICO", sizes=size_list)
    return out


def get_ico_sizes(ico_path: str | os.PathLike) -> list[tuple[int, int]]:
    """读取 ICO 文件中实际嵌入的尺寸列表（按面积降序）。

    Args:
        ico_path: 已生成的 .ico 文件路径。

    Returns:
        形如 [(256, 256), (128, 128), ...] 的尺寸列表。源图过小时
        Pillow 会跳过超出源尺寸的档位，这里返回的是真实嵌入结果。
    """
    with Image.open(ico_path) as img:
        sizes = img.info.get("sizes")
    if not sizes:
        return [(img.width, img.height)]
    return sorted(sizes, key=lambda s: s[0] * s[1], reverse=True)


def set_shortcut_icon(
    lnk_path: str | os.PathLike,
    ico_path: str | os.PathLike,
) -> bool:
    """把 ICO 设为 Windows .lnk 快捷方式的图标。

    依赖 pywin32（仅 Windows）。缺失或失败时返回 False，由调用方决定降级行为。

    Args:
        lnk_path: 目标 .lnk 快捷方式路径。
        ico_path: 已生成的 .ico 文件路径。

    Returns:
        True 表示设置成功；False 表示不可用或失败。
    """
    lnk = Path(lnk_path)
    ico = Path(ico_path)
    if not lnk.exists() or not ico.exists():
        return False

    # 惰性导入：仅在确实要设置时才加载 pywin32，避免无谓依赖与 COM 初始化。
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError:
        return False

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(lnk))
        # ",0" 表示使用 ICO 文件中的第 0 个图标。
        shortcut.IconLocation = f"{ico},0"
        shortcut.Save()
        return True
    except Exception:  # noqa: BLE001 - 任何 COM/权限错误都视为失败
        return False


if __name__ == "__main__":
    # 命令行兜底用法：python converter.py input.png [output.ico]
    import sys

    if len(sys.argv) < 2:
        print("用法: python converter.py <输入图片> [输出.ico]")
        raise SystemExit(1)
    result = convert_to_ico(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"已生成: {result}")
