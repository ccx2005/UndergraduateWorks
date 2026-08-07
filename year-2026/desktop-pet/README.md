# Desktop Pet · 桌面宠物

凯尔希/银白发像素小人桌面宠物（Python tkinter + Electron 双版本）。

## 功能

- 像素立绘桌面宠物（PNG 透明背景，跟随鼠标拖拽）
- 状态机动画：待机浮动 / 开心 / 睡觉（Zzz）
- 待机语音：「我在，Dr...」等
- 右键菜单：
  - **体检报告**：CPU / 内存 / 磁盘 / GPU（Intel 核显）/ 运行时长 / 温度 + 诊断意见
  - **询问**：与凯尔希 AI 对话（DuckDuckGo API，免费无需 Key）
  - **休息**
- 硬件监控面板：CPU / MEM / GPU 三行进度条

## 运行方式

### Python 版（推荐）

```bat
启动桌宠.bat
```

依赖：Python 3.8+（需带 tkinter）+ Pillow + psutil + requests

```bash
pip install pillow psutil requests
python pet.py
```

### Electron 版

```bash
npm install
npm start
```

## 文件结构

| 文件 | 说明 |
|------|------|
| `pet.py` | Python tkinter 主程序 |
| `src/` | Electron 版（index.html + renderer.js） |
| `assets/` | 立绘：`kaltist.png`（主图）、`kaltist-2x.png`（缩图） |
| `kaltsit.jpg` | 角色参考图 |
| `target.jpg` | 立绘参考图（WEBP 格式，银白发） |
| `启动桌宠.bat` | Windows 一键启动脚本 |

## 立绘说明

- 立绘为 AI 生成的像素画（ImageGen, pixel-art 风格），以 `kaltsit.jpg` / `target.jpg` 为参考
- 发色：银白色（#F7F8E8）；眼睛：橄榄绿；外套：卡其色 + 黑色条纹
- 立绘按宽高比自适应缩放（`pet.py` 中 `PET_DRAW_W/H` 可调大小）
