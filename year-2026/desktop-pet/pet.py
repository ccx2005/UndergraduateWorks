#!/usr/bin/env python3
"""桌面宠物 - 凯尔希 v0.5
Python + tkinter, 拖拽/四态动效/硬件监控/免费AI聊天
视觉层：凯尔希像素小人（PIL ImageTk 渲染）
聊天使用 DuckDuckGo 免费 AI API, 纯 Python 内置库, 零额外依赖
"""

import tkinter as tk
import math
import random
import time
import sys
import json
import urllib.request
import urllib.error
import threading
import traceback
import os
import subprocess

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from collections import deque

# ====== 常量 ======
WIDTH, HEIGHT = 220, 400
PET_Y_OFFSET = 55  # 角色整体下移，给气泡留出空间，避免气泡压头顶
BG_COLOR = "#010101"
# 凯尔希的主色调（仅用于占位与阴影，若 PIL 可用则以 PNG 为主）
SKIN_COLOR = "#F5D5C0"
HAIR_COLOR = "#E0E0E0"
EYE_COLOR = "#A8B547"
CHOKER_COLOR = "#2D2D2D"
JACKET_COLOR = "#B8B84A"

# 凯尔希性格提示词
PET_PERSONALITY = (
    '你是一位名叫"凯尔希"的医生，是罗德岛的医疗负责人。'
    '你冷静、理性、略带疲惫，对大多数事情抱有审视态度，偶尔流露罕见的温柔。'
    '用简短、口语化、稍带疏离感的中文回复，每次不超过40个字。'
    '你可以关心主人的工作状态、给出理性建议，或对主人的无厘头问题表示无奈。'
    '不要用markdown格式，直接说话。'
    '口头禅可偶尔出现"……"、"啧"、"够了"这类表达。'
)


# ====== 免费 AI 聊天客户端 (DuckDuckGo AI) ======
class FreeAIChat:
    """通过 DuckDuckGo 免费 AI 聊天 API 进行对话，零依赖纯 Python urllib"""

    CHAT_URL = "https://duckduckgo.com/duckchat/v1/chat"
    STATUS_URL = "https://duckduckgo.com/duckchat/v1/status"
    MODEL = "gpt-4o-mini"

    @classmethod
    def _get_vqd(cls):
        """获取 DuckDuckGo 的 VQD token"""
        req = urllib.request.Request(cls.STATUS_URL, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "x-vqd-accept": "1",
            "Accept": "*/*",
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.headers.get("x-vqd-4", "")
        except Exception:
            return ""

    @classmethod
    def _call_api(cls, messages):
        """调用 DDG AI API, 返回完整响应文本"""
        vqd = cls._get_vqd()
        if not vqd:
            raise RuntimeError("无法获取 VQD token")

        payload = json.dumps({
            "model": cls.MODEL,
            "messages": messages,
        }).encode("utf-8")

        req = urllib.request.Request(cls.CHAT_URL, data=payload, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "x-vqd-4": vqd,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        })

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                full_text = ""
                for line in resp:
                    line = line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        msg = chunk.get("message", "")
                        full_text += msg
                    except json.JSONDecodeError:
                        pass
                return full_text.strip()
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"API 请求失败 HTTP {e.code}")
        except Exception as e:
            raise RuntimeError(f"网络错误: {e}")

    @classmethod
    def chat(cls, user_msg, history=None, callback=None):
        """发送聊天消息并返回回复

        Args:
            user_msg: 用户消息
            history: 之前的对话历史 [(role, content), ...]
            callback: 回调函数 callback(reply_text)，在线程中调用
        """
        messages = [{"role": "system", "content": PET_PERSONALITY}]
        if history:
            for role, content in history[-6:]:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_msg})

        try:
            reply = cls._call_api(messages)
            if callback:
                callback(reply)
            return reply
        except Exception as e:
            fallback = _fallback_reply(user_msg)
            if callback:
                callback(fallback)
            return fallback


# ====== 离线兜底回复 ======
_FALLBACKS = [
    "……你的问题很无聊。",
    "忙归忙，记得喝水。",
    "不要打断我的工作时间。",
    "这种小伤不用来找我。",
    "啧，又是琐事。",
    "我正在写病历，别吵。",
    "你的作息记录我看过了。",
    "药按时吃了吗？",
    "下次体检我会提前通知你。",
    "咖啡因摄入过量不利于判断。",
    "……够了，今天到此为止。",
    "有事说事，没事继续工作。",
    "你比阿米娅还能闹腾。",
    "白面鸮给我发了三份报告。",
    "把情绪管理纳入你的日程。",
]

_GREETINGS = [
    "我在，Dr...",
    "……你回来了。继续吧。",
    "进度如何？我看一下。",
    "今天的体检别忘了。",
    "你的睡眠数据我收到了。",
    "工作归工作，咖啡少喝。",
    "有异常症状再来找我。",
    "今天的报告我会看的。",
    "你的状态……勉强及格。",
    "别坐太久，起来走走。",
]

# 待机专用语音（idle 状态随机触发）
_IDLE_VOICES = [
    "我在，Dr...",
    "……Dr，还在吗。",
    "有需要叫我。",
    "我在这里。",
]


def _fallback_reply(user_msg=""):
    """离线时的内置回复"""
    msg = user_msg.strip().lower() if user_msg else ""
    if any(w in msg for w in ["你好", "嗨", "hi", "hello", "嘿"]):
        return "……你好。说重点。"
    if any(w in msg for w in ["吃", "饿", "喂", "药"]):
        return "按时服药，别再忘了。"
    if any(w in msg for w in ["睡", "困", "累", "休息"]):
        return "你的睡眠数据我会持续关注。"
    if any(w in msg for w in ["玩", "无聊", "游戏"]):
        return "我没空陪你玩这些。"
    if any(w in msg for w in ["名字", "谁", "叫"]):
        return "凯尔希。罗德岛医疗负责人。"
    if any(w in msg for w in ["爱", "喜欢", "可爱"]):
        return "……够了，去工作。"
    return random.choice(_FALLBACKS)


# ====== 桌面宠物主体 ======
class DesktopPet:
    # 立绘目标显示尺寸（按宽高比自适应缩放，放大后为 260 框内最大比例）
    PET_DRAW_W = 260
    PET_DRAW_H = 260

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("凯尔希")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{WIDTH}x{HEIGHT}+{sw-WIDTH-30}+{sh-HEIGHT-60}")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", 1)
        self.root.wm_attributes("-transparentcolor", BG_COLOR)
        self.root.configure(bg=BG_COLOR)

        # 状态机
        self.state = "idle"
        self.state_timer = None
        self.blink_timer = None
        self.random_timer = None
        self.anim_frame = 0
        self.anim_offset = 0.0

        # 性能监控
        self.cpu_history = deque(maxlen=5)
        self.cpu_percent = 0.0
        self.mem_percent = 0.0
        self._perf_timer = None

        # GPU 监控（通过 PowerShell Windows 性能计数器）
        self.gpu_name = ""
        self.gpu_percent = 0.0
        self.gpu_history = deque(maxlen=5)
        self._gpu_thread = None
        self._detect_gpu()

        # 拖拽
        self._drag_x = 0
        self._drag_y = 0
        self._has_moved = False
        self._was_double = False  # 双击标记
        self._single_click_after = None

        # 性能面板折叠
        self.panel_visible = True

        # ====== 聊天系统 ======
        self.chat_history = []  # [(role, content), ...]
        self.show_bubble = False
        self.bubble_text = ""
        self.bubble_timer = None
        self.bubble_mode = ""  # "reply" | "greeting"
        self.is_thinking = False
        self.chat_active = False  # 是否在对话模式

        # 独立聊天窗口
        self.chat_window = None
        self.chat_history_text = None
        self.chat_input_entry = None

        # 定时问候
        self.greet_timer = None

        # ====== 加载凯尔希像素立绘 ======
        self.pet_image = None
        self.pet_photo = None
        self._load_pet_image()

        # UI
        self.canvas = tk.Canvas(self.root, width=WIDTH, height=HEIGHT, bg=BG_COLOR,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        # 右键菜单
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="聊天", command=self.start_chat)
        self.menu.add_command(label="体检报告", command=self.feed)
        self.menu.add_command(label="询问", command=self.play)
        self.menu.add_command(label="休息", command=self.toggle_sleep)
        self.menu.add_separator()
        self.menu.add_command(label="显示/隐藏监控", command=self.toggle_panel)
        self.menu.add_separator()
        self.menu.add_command(label="关于", command=self.show_about)
        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self.root.destroy)

        # 事件绑定
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.root.bind("<Escape>", self._on_esc)
        self.root.bind("<Return>", self._on_enter)

        # 启动
        self.enter_state("idle")
        self._start_perf_monitor()
        self._start_greet_timer()
        # 启动后先说一句待机语音
        self.root.after(800, lambda: self._say("我在，Dr...", "greeting", 5000))
        self.root.mainloop()

    def _load_pet_image(self):
        """加载凯尔希像素立绘 PNG，缩放到合适尺寸并保留引用防止被 GC"""
        if not HAS_PIL:
            return
        # 优先使用主图，回退到 2x 图
        candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "kaltist.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "kaltist-2x.png"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    img = Image.open(path).convert("RGBA")
                    # 保持宽高比缩放：细长立绘不被压扁成方形
                    ratio = min(self.PET_DRAW_W / img.width, self.PET_DRAW_H / img.height)
                    nw = max(1, int(img.width * ratio))
                    nh = max(1, int(img.height * ratio))
                    img = img.resize((nw, nh), Image.NEAREST)
                    self.pet_image = img
                    self.pet_photo = ImageTk.PhotoImage(img)
                    # 记录实际显示尺寸，供气泡/阴影定位使用
                    self.PET_DRAW_W = nw
                    self.PET_DRAW_H = nh
                    return
                except Exception as e:
                    print(f"加载立绘失败 {path}: {e}")
        print("警告: 未找到 kaltist.png，将以占位形状绘制")

    # ====== 状态管理 ======
    def enter_state(self, state):
        self.cancel_timers()
        self.state = state
        if state == "idle":
            self.start_idle()
        elif state == "happy":
            self.start_happy()
        elif state == "sleep":
            self.start_sleep()

    def cancel_timers(self):
        for t in [self.state_timer, self.blink_timer, self.random_timer,
                  self._perf_timer, self.bubble_timer, self.greet_timer]:
            if t:
                try:
                    self.root.after_cancel(t)
                except Exception:
                    pass
        self.state_timer = self.blink_timer = self.random_timer = None
        self._perf_timer = self.bubble_timer = self.greet_timer = None

    # ====== IDLE ======
    def start_idle(self):
        self.anim_frame = 0
        self.anim_offset = 0.0
        self._draw("idle")
        self._idle_loop()
        self._schedule_blink()
        self._schedule_random()

    def _idle_loop(self):
        if self.state != "idle":
            return
        self.anim_frame += 1
        self.anim_offset = math.sin(self.anim_frame * 0.08) * 4
        self._draw("idle")
        self.state_timer = self.root.after(50, self._idle_loop)

    def _schedule_blink(self):
        if self.state not in ("idle", "happy"):
            return
        self.blink_timer = self.root.after(2500 + random.randint(0, 3000), self._do_blink)

    def _do_blink(self):
        if self.state not in ("idle", "happy"):
            return
        self._draw("blink")
        self.root.after(150, lambda: self._draw(self.state))
        self._schedule_blink()

    def _schedule_random(self):
        if self.state != "idle":
            return
        delay = 20000 + random.randint(0, 30000)  # 20-50秒随机动作
        self.random_timer = self.root.after(delay, self._random_action)

    def _random_action(self):
        if self.state != "idle":
            return
        r = random.random()
        if r < 0.3:
            self.play()
        elif r < 0.7:
            # 随机冒一句待机语音
            self._say(random.choice(_IDLE_VOICES), mode="greeting", duration=5000)
        self._schedule_random()

    # ====== HAPPY ======
    def play(self):
        if self.state == "sleep":
            self.enter_state("idle")
            return
        if self.state == "happy":
            return
        self.enter_state("happy")

    def start_happy(self):
        self._happy_frames = 0
        self._happy_loop()

    def _happy_loop(self):
        if self.state != "happy":
            return
        self._happy_frames += 1
        self.anim_offset = math.sin(self._happy_frames * 0.5) * 5
        self._draw("happy")
        if self._happy_frames < 30:
            self.state_timer = self.root.after(60, self._happy_loop)
        else:
            self.enter_state("idle")

    # ====== SLEEP ======
    def toggle_sleep(self):
        if self.state == "sleep":
            self.enter_state("idle")
        else:
            self.cancel_timers()
            self.enter_state("sleep")

    def start_sleep(self):
        self.anim_frame = 0
        self._sleep_loop()

    def _sleep_loop(self):
        if self.state != "sleep":
            return
        self.anim_frame += 1
        self.anim_offset = 0
        bx = 1 + math.sin(self.anim_frame * 0.04) * 0.03
        by = 1 - math.sin(self.anim_frame * 0.04) * 0.03
        self._draw("sleep", bx, by)
        self.state_timer = self.root.after(80, self._sleep_loop)

    # ====== 体检报告 ======
    def feed(self):
        """弹出体检报告窗口，显示系统健康状态 + 凯尔希点评"""
        if self.state == "sleep":
            self.enter_state("idle")
            return
        self._show_medical_report()

    def _show_medical_report(self):
        """创建体检报告 Toplevel 窗口"""
        if hasattr(self, '_report_win') and self._report_win and self._report_win.winfo_exists():
            self._report_win.deiconify()
            self._report_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("体检报告")
        win.resizable(False, False)
        win.configure(bg="#FFFFFF")
        win.attributes("-topmost", True)

        cw, ch = 300, 440
        px = self.root.winfo_x() + WIDTH + 12
        py = self.root.winfo_y()
        sw = self.root.winfo_screenwidth()
        if px + cw > sw:
            px = self.root.winfo_x() - cw - 12
        win.geometry(f"{cw}x{ch}+{px}+{py}")

        # 标题栏
        header = tk.Frame(win, bg="#4A6741", height=40)
        header.pack(fill="x")
        tk.Label(header, text="罗德岛 · 体检报告", bg="#4A6741", fg="#FFFFFF",
                 font=("Microsoft YaHei", 12, "bold")).pack(side="left", padx=12, pady=8)

        # 报告内容区
        content = tk.Frame(win, bg="#FFFFFF")
        content.pack(fill="both", expand=True, padx=12, pady=10)

        # 采集系统数据
        data = self._collect_system_data()

        # 系统信息条目
        row_y = 0
        for label, value, color in data["items"]:
            frame = tk.Frame(content, bg="#FFFFFF")
            frame.pack(fill="x", pady=3)
            tk.Label(frame, text=label, bg="#FFFFFF", fg="#636E72",
                     font=("Microsoft YaHei", 9), width=10, anchor="w").pack(side="left")
            tk.Label(frame, text=value, bg="#FFFFFF", fg=color,
                     font=("Microsoft YaHei", 10, "bold"), anchor="w").pack(side="left", padx=(4, 0))

        # 分隔线
        tk.Frame(content, bg="#E0DDD5", height=1).pack(fill="x", pady=10)

        # 总评
        tk.Label(content, text="诊断意见", bg="#FFFFFF", fg="#4A6741",
                 font=("Microsoft YaHei", 10, "bold"), anchor="w").pack(fill="x")
        diagnosis = tk.Text(content, wrap="word", height=4, bg="#F8F8F4", fg="#2D3436",
                            bd=0, font=("Microsoft YaHei", 9), padx=8, pady=6,
                            relief="flat", spacing1=2, spacing3=2)
        diagnosis.pack(fill="x", pady=(4, 0))
        diagnosis.insert("1.0", data["diagnosis"])
        diagnosis.config(state="disabled")

        # 关闭按钮
        tk.Button(win, text="了解", command=win.destroy,
                  bg="#4A6741", fg="#FFFFFF", activebackground="#3A5631",
                  activeforeground="#FFFFFF", bd=0, cursor="hand2",
                  font=("Microsoft YaHei", 9, "bold"), padx=20, pady=4).pack(pady=10)

        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(),))
        self._report_win = win

        # 同时让凯尔希说一句话
        self._say(data["voice"], "reply", 6000)

    def _collect_system_data(self):
        """采集系统数据并生成凯尔希风格的体检报告"""
        import datetime

        items = []
        diagnosis_parts = []

        if HAS_PSUTIL:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            try:
                boot_time = psutil.boot_time()
                uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_time)
                uptime_str = f"{uptime.days}天{uptime.seconds // 3600}小时"
            except Exception:
                uptime_str = "未知"
            try:
                temps = psutil.sensors_temperatures()
                temp_str = "正常"
                if temps:
                    for name, entries in temps.items():
                        if entries:
                            temp_str = f"{entries[0].current:.0f}°C"
                            break
            except Exception:
                temp_str = "—"

            cpu_color = self._bar_color(cpu)
            mem_color = self._bar_color(mem.percent)
            disk_color = self._bar_color(disk.percent)

            items.append(("CPU 占用", f"{cpu:.1f}%", cpu_color))
            items.append(("内存占用", f"{mem.percent:.1f}%", mem_color))
            items.append(("磁盘占用", f"{disk.percent:.1f}%", disk_color))
            items.append(("运行时长", uptime_str, "#636E72"))
            items.append(("温度", temp_str, "#636E72"))

            # GPU 信息
            if self.gpu_name:
                gpu_short = self.gpu_name[:30] if len(self.gpu_name) > 30 else self.gpu_name
                items.append(("显卡", gpu_short, "#636E72"))
                items.append(("GPU 占用", f"{self.gpu_percent:.1f}%", self._bar_color(self.gpu_percent)))
            else:
                items.append(("显卡", "未检测到", "#B2BEC3"))

            # 诊断意见
            if cpu > 80:
                diagnosis_parts.append("CPU 负载过高，建议立即关闭不必要的进程。")
            elif cpu > 50:
                diagnosis_parts.append("CPU 负载偏高，注意监控。")
            else:
                diagnosis_parts.append("CPU 状态平稳。")

            if mem.percent > 85:
                diagnosis_parts.append("内存接近上限，存在溢出风险。")
            elif mem.percent > 70:
                diagnosis_parts.append("内存占用偏高。")
            else:
                diagnosis_parts.append("内存余量充足。")

            if disk.percent > 90:
                diagnosis_parts.append("磁盘空间严重不足，请尽快清理。")

            # GPU 诊断
            if self.gpu_name and self.gpu_percent > 85:
                diagnosis_parts.append("GPU 负载极高，图形处理可能遇到瓶颈。")
            elif self.gpu_name and self.gpu_percent > 60:
                diagnosis_parts.append("GPU 负载偏高。")

            # 凯尔希风格总结
            if cpu > 80 or mem.percent > 85 or disk.percent > 90 or self.gpu_percent > 85:
                voice = "……你的设备状况不太乐观。"
                summary = "综合评估：需要干预。"
            elif cpu > 50 or mem.percent > 70 or self.gpu_percent > 60:
                voice = "目前还在可控范围内，但别掉以轻心。"
                summary = "综合评估：亚健康。"
            else:
                voice = "各项指标在正常范围内。……继续工作吧。"
                summary = "综合评估：健康。"
        else:
            items.append(("CPU 占用", "需安装 psutil", "#FF6B6B"))
            items.append(("内存占用", "需安装 psutil", "#FF6B6B"))
            diagnosis_parts.append("无法获取系统数据：缺少 psutil 模块。")
            voice = "体检设备离线……啧。"
            summary = "综合评估：无法检测。"

        diagnosis = "。".join(diagnosis_parts) + "\n" + summary
        return {"items": items, "diagnosis": diagnosis, "voice": voice}

    # ====== GPU 监控 ======
    def _detect_gpu(self):
        """启动时一次性检测 GPU 名称（PowerShell CIM 查询）"""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue "
                 "| Select-Object -First 1).Name"],
                capture_output=True, text=True, timeout=5,
                creationflags=0x08000000  # CREATE_NO_WINDOW
            )
            name = result.stdout.strip()
            if name:
                self.gpu_name = name
        except Exception:
            pass

    def _update_gpu_async(self):
        """后台线程查询 GPU 利用率（PowerShell Get-Counter）"""
        if self._gpu_thread and self._gpu_thread.is_alive():
            return

        def _query():
            try:
                ps_script = (
                    "$s=(Get-Counter '\\GPU Engine(*engtype_3D)\\Utilization Percentage' "
                    "-ErrorAction SilentlyContinue).CounterSamples;"
                    "$t=($s|Where-Object{$_.CookedValue -gt 0}"
                    "|Measure-Object -Property CookedValue -Sum).Sum;"
                    "Write-Output ('{0:F1}' -f $t)"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_script],
                    capture_output=True, text=True, timeout=5,
                    creationflags=0x08000000
                )
                val = float(result.stdout.strip())
                self.root.after(0, lambda: self._set_gpu(val))
            except Exception:
                pass

        self._gpu_thread = threading.Thread(target=_query, daemon=True)
        self._gpu_thread.start()

    def _set_gpu(self, val):
        """主线程回调：更新 GPU 利用率（带平滑）"""
        self.gpu_history.append(val)
        self.gpu_percent = sum(self.gpu_history) / len(self.gpu_history)

    # ====== 硬件监控 ======
    def _start_perf_monitor(self):
        self._update_perf()

    def _update_perf(self):
        try:
            if HAS_PSUTIL:
                self.cpu_history.append(psutil.cpu_percent(interval=0.3))
                self.cpu_percent = sum(self.cpu_history) / len(self.cpu_history)
                self.mem_percent = psutil.virtual_memory().percent
        except Exception:
            pass
        self._update_gpu_async()
        self._perf_timer = self.root.after(2000, self._update_perf)

    def toggle_panel(self):
        self.panel_visible = not self.panel_visible

    def _bar_color(self, pct):
        if pct < 50:
            return "#00B894"
        elif pct < 80:
            return "#FDCB6E"
        return "#FF6B6B"

    # ====== 聊天气泡 ======
    def _say(self, text, mode="reply", duration=8000):
        """显示聊天气泡"""
        self.show_bubble = True
        self.bubble_text = text
        self.bubble_mode = mode
        if self.bubble_timer:
            try:
                self.root.after_cancel(self.bubble_timer)
            except Exception:
                pass
        self.bubble_timer = self.root.after(duration, self._hide_bubble)

    def _hide_bubble(self):
        self.show_bubble = False
        self.bubble_text = ""
        self.is_thinking = False
        self.bubble_timer = None

    def _draw_bubble(self):
        """绘制聊天气泡（圆角矩形，贴近角色头顶上方）"""
        if not self.show_bubble and not self.is_thinking:
            return

        c = self.canvas
        ox = WIDTH // 2
        # 气泡紧贴角色头顶上方（角色头顶约在 y=120，立绘顶部受 anim_offset 影响）
        pet_head_top = 200 + self.anim_offset + PET_Y_OFFSET - self.PET_DRAW_H // 2
        bubble_y = max(2, pet_head_top - 55)
        bubble_w = 200
        padding = 12

        text_to_show = self.bubble_text
        if self.is_thinking:
            dots = "." * ((self.anim_frame // 5) % 4)
            text_to_show = "思考中" + dots

        if not text_to_show:
            return

        # 计算文字换行（最多2行，避免压到猫头）
        lines = self._wrap_text(text_to_show, bubble_w - padding * 2, max_lines=2)
        line_height = 18
        bubble_h = len(lines) * line_height + padding * 2

        bubble_x0 = ox - bubble_w // 2
        bubble_y0 = bubble_y
        r = 8  # 圆角半径

        # 圆角矩形背景
        x0, y0 = bubble_x0, bubble_y0
        x1, y1 = bubble_x0 + bubble_w, bubble_y0 + bubble_h
        c.create_arc(x0, y0, x0 + r*2, y0 + r*2, start=90, extent=90, fill="#FFFFFF", outline="")
        c.create_arc(x1 - r*2, y0, x1, y0 + r*2, start=0, extent=90, fill="#FFFFFF", outline="")
        c.create_arc(x0, y1 - r*2, x0 + r*2, y1, start=180, extent=90, fill="#FFFFFF", outline="")
        c.create_arc(x1 - r*2, y1 - r*2, x1, y1, start=270, extent=90, fill="#FFFFFF", outline="")
        c.create_rectangle(x0 + r, y0, x1 - r, y1, fill="#FFFFFF", outline="")
        c.create_rectangle(x0, y0 + r, x1, y1 - r, fill="#FFFFFF", outline="")

        # 圆角边框
        c.create_arc(x0, y0, x0 + r*2, y0 + r*2, start=90, extent=90, style="arc", outline="#DFE6E9", width=1.5)
        c.create_arc(x1 - r*2, y0, x1, y0 + r*2, start=0, extent=90, style="arc", outline="#DFE6E9", width=1.5)
        c.create_arc(x0, y1 - r*2, x0 + r*2, y1, start=180, extent=90, style="arc", outline="#DFE6E9", width=1.5)
        c.create_arc(x1 - r*2, y1 - r*2, x1, y1, start=270, extent=90, style="arc", outline="#DFE6E9", width=1.5)
        c.create_line(x0 + r, y0, x1 - r, y0, fill="#DFE6E9", width=1.5)
        c.create_line(x0 + r, y1, x1 - r, y1, fill="#DFE6E9", width=1.5)
        c.create_line(x0, y0 + r, x0, y1 - r, fill="#DFE6E9", width=1.5)
        c.create_line(x1, y0 + r, x1, y1 - r, fill="#DFE6E9", width=1.5)

        # 文字
        for i, line in enumerate(lines):
            c.create_text(ox, bubble_y0 + padding + i * line_height,
                          text=line, fill="#2D3436",
                          font=("Microsoft YaHei", 10), anchor="n")

    def _wrap_text(self, text, max_width, max_lines=2):
        """简单中文换行（按字符数估算），限制最大行数避免遮挡"""
        lines = []
        current = ""
        char_count = 0
        for ch in text:
            w = 2 if ord(ch) > 127 else 1
            if char_count + w > max_width // 7:
                lines.append(current)
                current = ch
                char_count = w
            else:
                current += ch
                char_count += w
            if len(lines) >= max_lines:
                break
        if current and len(lines) < max_lines:
            lines.append(current)
        elif current:
            # 超过行数，给最后一行加省略号
            if len(lines[-1]) > 2:
                lines[-1] = lines[-1][:-2] + "…"
        if not lines:
            lines = [text]
        return lines

    # ====== 定时问候 ======
    def _start_greet_timer(self):
        self._schedule_greet()

    def _schedule_greet(self):
        delay = 120000 + random.randint(0, 120000)  # 2-4分钟
        self.greet_timer = self.root.after(delay, self._do_greet)

    def _do_greet(self):
        if self.state == "sleep":
            self._schedule_greet()
            return
        # AI 生成一句问候
        threading.Thread(target=self._ai_greet, daemon=True).start()
        self._schedule_greet()

    def _ai_greet(self):
        """后台线程：AI 生成定时问候"""
        try:
            msg = FreeAIChat.chat("（主动打招呼，聊一句天气/心情/工作相关的话题）")
            if msg:
                self.root.after(0, lambda: self._say(msg, "greeting", 8000))
        except Exception:
            msg = random.choice(_GREETINGS)
            self.root.after(0, lambda: self._say(msg, "greeting", 8000))

    # ====== 独立聊天窗口 ======
    def start_chat(self):
        """打开独立的聊天窗口（位于主窗口右侧，不与主窗口组件重合）"""
        if self.state == "sleep":
            self.enter_state("idle")
        if self.chat_window and self.chat_window.winfo_exists():
            self.chat_window.deiconify()
            self.chat_window.lift()
            self.chat_window.focus_force()
            if self.chat_input_entry and self.chat_input_entry.winfo_exists():
                self.chat_input_entry.focus_force()
            return

        self.chat_active = True
        self._build_chat_window()
        # grab_set 必须在窗口完全构建后调用，强制键盘输入路由到聊天窗口
        # 解决 overrideredirect(True) 父窗口导致 Toplevel 无法获取焦点的 Windows 已知问题
        try:
            self.chat_window.grab_set()
        except Exception:
            pass

    def on_double_click(self, event):
        """双击打开聊天窗口"""
        self._was_double = True
        self._has_moved = True  # 阻止单击抚摸
        if self._single_click_after:
            try:
                self.root.after_cancel(self._single_click_after)
            except Exception:
                pass
            self._single_click_after = None
        self.start_chat()

    def _build_chat_window(self):
        """创建独立聊天窗口"""
        self.chat_window = tk.Toplevel(self.root)
        self.chat_window.title("和凯尔希对话")
        self.chat_window.resizable(False, False)
        self.chat_window.configure(bg="#FFFFFF")
        # 强制置顶 + 获取窗口焦点（主窗口是 overrideredirect，子窗口需独立抢焦点）
        self.chat_window.attributes("-topmost", True)
        self.chat_window.focus_force()

        # 窗口大小与位置：放在主窗口右侧，顶部对齐
        cw, ch = 260, 340
        px = self.root.winfo_x() + WIDTH + 12
        py = self.root.winfo_y()
        # 若超出屏幕右边界则放到主窗口左侧
        sw = self.root.winfo_screenwidth()
        if px + cw > sw:
            px = self.root.winfo_x() - cw - 12
        self.chat_window.geometry(f"{cw}x{ch}+{px}+{py}")

        # 标题
        header = tk.Frame(self.chat_window, bg="#FFB347", height=38)
        header.pack(fill="x")
        tk.Label(header, text="和凯尔希对话", bg="#FFB347", fg="#FFFFFF",
                 font=("Microsoft YaHei", 12, "bold")).pack(side="left", padx=10, pady=5)

        # 历史记录区（加深边框让用户清楚看到聊天区域边界）
        text_frame = tk.Frame(self.chat_window, bg="#D0D5DD", bd=0, highlightthickness=0)
        text_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        text_inner = tk.Frame(text_frame, bg="#FFFFFF", bd=0)
        text_inner.pack(fill="both", expand=True, padx=1, pady=1)

        scrollbar = tk.Scrollbar(text_inner)
        scrollbar.pack(side="right", fill="y")

        self.chat_history_text = tk.Text(text_inner, wrap="word", state="disabled",
                                         bg="#FFFFFF", fg="#2D3436", bd=0,
                                         font=("Microsoft YaHei", 10),
                                         yscrollcommand=scrollbar.set,
                                         padx=10, pady=10, spacing1=2, spacing3=2,
                                         cursor="arrow")
        self.chat_history_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.chat_history_text.yview)

        # 输入区（加深背景色 + 圆角边框，确保输入框清晰可见）
        input_frame = tk.Frame(self.chat_window, bg="#FFFFFF")
        input_frame.pack(fill="x", padx=8, pady=(4, 8))

        # 文本输入框容器：带浅灰边框和橙色聚焦高亮
        self.chat_entry_border = tk.Frame(input_frame, bg="#D0D5DD",
                                          highlightthickness=0, bd=0)
        self.chat_entry_border.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.chat_input_entry = tk.Entry(
            self.chat_entry_border,
            font=("Microsoft YaHei", 11),
            bg="#FFFFFF", fg="#2D3436",
            bd=0, highlightthickness=2,
            highlightbackground="#D0D5DD", highlightcolor="#FF8C42",
            insertbackground="#FF8C42", insertwidth=2,
            relief="flat"
        )
        self.chat_input_entry.pack(fill="both", expand=True, ipady=6, padx=2, pady=2)
        self.chat_input_entry.bind("<Return>", self._on_enter)
        self.chat_input_entry.bind("<Escape>", self._close_chat_window)

        # 占位文字提示
        self._input_placeholder = "说点什么吧..."
        self._input_has_placeholder = True
        self._show_placeholder()

        # 聚焦/失焦切换占位文字
        self.chat_input_entry.bind("<FocusIn>", self._on_entry_focus_in)
        self.chat_input_entry.bind("<FocusOut>", self._on_entry_focus_out)

        send_btn = tk.Button(input_frame, text="发送", command=lambda: self._on_enter(None),
                             bg="#FFB347", fg="#FFFFFF", activebackground="#E8943A",
                             activeforeground="#FFFFFF", bd=0, cursor="hand2",
                             font=("Microsoft YaHei", 9, "bold"), padx=12, pady=2)
        send_btn.pack(side="right")

        # 窗口关闭事件
        self.chat_window.protocol("WM_DELETE_WINDOW", self._close_chat_window)

        # grab_set 后根窗口的按键绑定失效，需在聊天窗口上重新绑定 Escape
        self.chat_window.bind("<Escape>", self._close_chat_window)

        # 延迟强制聚焦输入框（窗口完全映射后才能生效）
        def _delayed_focus():
            try:
                self.chat_window.lift()
                self.chat_window.focus_force()
                self.chat_input_entry.focus_force()
                # 再抢一次确保成功
                self.chat_window.after(80, lambda: (
                    self.chat_window.focus_force(),
                    self.chat_input_entry.focus_force()
                ) if self.chat_window and self.chat_window.winfo_exists() else None)
            except Exception:
                pass
        self.chat_window.after(50, _delayed_focus)

        # 点击标题栏或空白区域也重新聚焦输入框
        for w in (self.chat_window, header, text_frame, self.chat_history_text):
            w.bind("<Button-1>", lambda e: (
                self.chat_input_entry.focus_force()
                if self.chat_input_entry and self.chat_input_entry.winfo_exists() else None
            ), add="+")

    def _close_chat_window(self, event=None):
        """关闭独立聊天窗口"""
        if self.chat_window and self.chat_window.winfo_exists():
            try:
                self.chat_window.grab_release()
            except Exception:
                pass
            self.chat_window.destroy()
        self.chat_window = None
        self.chat_history_text = None
        self.chat_input_entry = None
        self.chat_active = False
        self.is_thinking = False
        self.show_bubble = False
        self.bubble_text = ""

    # ====== 输入框占位文字 ======
    def _show_placeholder(self):
        """显示灰色占位文字"""
        if not self.chat_input_entry:
            return
        self.chat_input_entry.insert(0, self._input_placeholder)
        self.chat_input_entry.config(fg="#A0A6B0")
        self._input_has_placeholder = True

    def _hide_placeholder(self):
        """隐藏占位文字"""
        if not self.chat_input_entry:
            return
        if self._input_has_placeholder:
            self.chat_input_entry.delete(0, "end")
            self.chat_input_entry.config(fg="#2D3436")
            self._input_has_placeholder = False

    def _on_entry_focus_in(self, event=None):
        """聚焦时清除占位文字"""
        if self._input_has_placeholder:
            self._hide_placeholder()

    def _on_entry_focus_out(self, event=None):
        """失焦时若为空则恢复占位文字"""
        if not self.chat_input_entry.get():
            self._show_placeholder()

    def _append_chat_history(self, role, text):
        """在聊天窗口追加一条消息"""
        if not self.chat_history_text:
            return
        self.chat_history_text.config(state="normal")
        prefix = "你：" if role == "user" else "凯尔希："
        color = "#0984E3" if role == "user" else "#E17055"
        tag = f"tag_{role}_{id(text)}"
        self.chat_history_text.insert("end", f"{prefix}\n", tag)
        self.chat_history_text.tag_config(tag, foreground=color,
                                          font=("Microsoft YaHei", 9, "bold"))
        self.chat_history_text.insert("end", f"{text}\n\n")
        self.chat_history_text.see("end")
        self.chat_history_text.config(state="disabled")

    def _on_enter(self, event=None):
        """发送消息"""
        if not self.chat_input_entry:
            return
        text = self.chat_input_entry.get().strip()
        # 占位文字时不允许发送
        if not text or text == self._input_placeholder:
            return
        self.chat_input_entry.delete(0, "end")

        # 显示在用户聊天窗口
        self._append_chat_history("user", text)
        self._append_chat_history("assistant", "思考中...")
        self.is_thinking = True

        # 后台请求 AI
        threading.Thread(target=self._ai_chat, args=(text,), daemon=True).start()

    def _ai_chat(self, user_msg):
        """后台线程：AI 聊天"""
        try:
            self.chat_history.append(("user", user_msg))
            reply = FreeAIChat.chat(user_msg, history=self.chat_history)
            self.chat_history.append(("assistant", reply))
            # 限制历史长度
            if len(self.chat_history) > 12:
                self.chat_history = self.chat_history[-10:]
        except Exception:
            reply = _fallback_reply(user_msg)

        def show_reply():
            # 移除“思考中...”
            if self.chat_history_text and self.chat_history_text.winfo_exists():
                self.chat_history_text.config(state="normal")
                content = self.chat_history_text.get("1.0", "end")
                # 简单移除最后一段思考中提示
                idx = content.rfind("凯尔希：\n思考中...")
                if idx != -1:
                    pos = self.chat_history_text.index(f"1.0 + {idx} chars")
                    end_pos = self.chat_history_text.index("end-1c")
                    self.chat_history_text.delete(pos, end_pos)
                self.chat_history_text.config(state="disabled")
                self._append_chat_history("assistant", reply)
            self.is_thinking = False
            # 让气泡显示当前回复（5秒后自动消失）
            self._say(reply, "reply", 5000)

        self.root.after(0, show_reply)

    def _on_esc(self, event=None):
        """ESC: 先关聊天窗口，再关主窗口"""
        if self.chat_window and self.chat_window.winfo_exists():
            self._close_chat_window()
        else:
            self.root.destroy()

    # ====== 统一绘制入口 ======
    def _draw(self, mode, scale_x=1.0, scale_y=1.0):
        self.canvas.delete("all")
        # 先画气泡（在角色上方）
        self._draw_bubble()
        # 再画凯尔希像素立绘
        self._draw_pet(scale_x, scale_y)
        # 状态特效（Zzz / 爱心）
        self._draw_effects(mode)
        # 监控面板
        if self.panel_visible and HAS_PSUTIL:
            self._draw_panel()

    # ====== 角色立绘（PIL PNG） ======
    def _draw_pet(self, scale_x=1.0, scale_y=1.0):
        c = self.canvas
        # 像素立绘中心点
        cx = WIDTH // 2
        cy = 200 + self.anim_offset + PET_Y_OFFSET

        # 阴影（地面投影，不随立绘缩放）
        sw = self.PET_DRAW_W * 0.55
        sh = 6
        c.create_oval(cx - sw, cy + self.PET_DRAW_H // 2 - 6,
                      cx + sw, cy + self.PET_DRAW_H // 2 + 6,
                      fill="#C8CCD0", outline="")

        if self.pet_photo is not None:
            # 用 PNG 渲染（image 锚点为中心）
            half_w = (self.PET_DRAW_W * scale_x) / 2
            half_h = (self.PET_DRAW_H * scale_y) / 2
            c.create_image(cx, cy, image=self.pet_photo, anchor="center")
        else:
            # PIL 不可用时的兜底占位绘制（剪影 + 提示文字）
            c.create_oval(cx - 40, cy - 60, cx + 40, cy + 60,
                          fill=JACKET_COLOR, outline=CHOKER_COLOR, width=2)
            c.create_oval(cx - 32, cy - 50, cx + 32, cy - 20,
                          fill=HAIR_COLOR, outline="")
            c.create_oval(cx - 18, cy - 42, cx - 8, cy - 32,
                          fill=EYE_COLOR, outline="")
            c.create_oval(cx + 8, cy - 42, cx + 18, cy - 32,
                          fill=EYE_COLOR, outline="")
            c.create_text(cx, cy + 80, text="(kaltist.png 缺失)",
                          fill="#888780", font=("Microsoft YaHei", 8))

    # ====== 状态特效（Zzz / 爱心） ======
    def _draw_effects(self, mode):
        c = self.canvas
        cx = WIDTH // 2
        cy = 200 + self.anim_offset + PET_Y_OFFSET

        # 睡觉 Zzz
        if mode == "sleep" and self.anim_frame % 15 < 7:
            for i in range(3):
                zi = time.time() % 2.5 / 2.5
                c.create_text(cx + 30 + i * 18, cy - self.PET_DRAW_H // 2 - 10 - i * 10 - zi * 15,
                              text="Z", fill="#74B9FF",
                              font=("Arial", 14 + i * 4, "bold"))

        # 开心爱心
        if mode == "happy":
            for i in range(4):
                hx = cx - 60 + i * 40 + random.randint(-5, 5)
                hy = cy - self.PET_DRAW_H // 2 - 40 + random.randint(0, 25)
                c.create_text(hx, hy, text="♥",
                              fill="#FF6B6B", font=("Arial", 12))

        # 吃东西爱心
        if mode == "eating":
            for i in range(3):
                c.create_text(cx - 60 + i * 40, cy - self.PET_DRAW_H // 2 - 50,
                              text="♥", fill="#FF6B9D", font=("Arial", 11))

    # ====== 监控面板 ======
    def _draw_panel(self):
        c = self.canvas
        y0 = 275 + PET_Y_OFFSET
        bar_w = 140
        bar_x = 55
        bar_h = 12
        gap = 17

        c.create_rectangle(15, y0 - 2, 205, y0 + 60, fill="#F5F5F0",
                           outline="#E0DDD5", width=1)

        cpu_c = self._bar_color(self.cpu_percent)
        mem_c = self._bar_color(self.mem_percent)
        gpu_c = self._bar_color(self.gpu_percent)

        # CPU
        cy0 = y0 + 3
        c.create_text(25, cy0 + bar_h // 2, text="CPU", fill="#636E72",
                      font=("Segoe UI", 9, "bold"), anchor="w")
        c.create_rectangle(bar_x, cy0, bar_x + bar_w, cy0 + bar_h,
                           fill="#E8E8E0", outline="")
        c.create_rectangle(bar_x, cy0, bar_x + bar_w * self.cpu_percent / 100, cy0 + bar_h,
                           fill=cpu_c, outline="")
        c.create_text(198, cy0 + bar_h // 2, text=f"{self.cpu_percent:.0f}%",
                      fill="#2D3436", font=("Segoe UI", 9, "bold"), anchor="e")

        # MEM
        my0 = cy0 + gap
        c.create_text(25, my0 + bar_h // 2, text="MEM", fill="#636E72",
                      font=("Segoe UI", 9, "bold"), anchor="w")
        c.create_rectangle(bar_x, my0, bar_x + bar_w, my0 + bar_h,
                           fill="#E8E8E0", outline="")
        c.create_rectangle(bar_x, my0, bar_x + bar_w * self.mem_percent / 100, my0 + bar_h,
                           fill=mem_c, outline="")
        c.create_text(198, my0 + bar_h // 2, text=f"{self.mem_percent:.0f}%",
                      fill="#2D3436", font=("Segoe UI", 9, "bold"), anchor="e")

        # GPU
        gy0 = my0 + gap
        c.create_text(25, gy0 + bar_h // 2, text="GPU", fill="#636E72",
                      font=("Segoe UI", 9, "bold"), anchor="w")
        c.create_rectangle(bar_x, gy0, bar_x + bar_w, gy0 + bar_h,
                           fill="#E8E8E0", outline="")
        c.create_rectangle(bar_x, gy0, bar_x + bar_w * self.gpu_percent / 100, gy0 + bar_h,
                           fill=gpu_c, outline="")
        gpu_text = f"{self.gpu_percent:.0f}%" if self.gpu_name else "—"
        c.create_text(198, gy0 + bar_h // 2, text=gpu_text,
                      fill="#2D3436", font=("Segoe UI", 9, "bold"), anchor="e")

        c.create_text(110, y0 + 57, text="凯尔希监控", fill="#B2BEC3",
                      font=("Segoe UI", 7), anchor="center")

    # ====== 交互 ======
    def on_press(self, event):
        self._drag_x = event.x_root
        self._drag_y = event.y_root
        self._has_moved = False
        self._was_double = False
        if self._single_click_after:
            try:
                self.root.after_cancel(self._single_click_after)
            except Exception:
                pass
            self._single_click_after = None

    def on_drag(self, event):
        dx = event.x_root - self._drag_x
        dy = event.y_root - self._drag_y
        if abs(dx) > 2 or abs(dy) > 2:
            self._has_moved = True
        self._drag_x = event.x_root
        self._drag_y = event.y_root
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    def on_release(self, event):
        if not self._has_moved and not self._was_double:
            # 延迟 180ms，给双击事件留出判断时间
            self._single_click_after = self.root.after(180, self._do_single_click)

    def _do_single_click(self):
        self._single_click_after = None
        if not self._was_double:
            self.play()

    def on_right_click(self, event):
        try:
            self.menu.post(event.x_root, event.y_root)
        except Exception:
            pass

    def show_about(self):
        import tkinter.messagebox as mb
        mb.showinfo("关于凯尔希",
                    "凯尔希 v0.5\n罗德岛医疗负责人 · 桌面常驻\n"
                    "CPU & 内存 & GPU 监控 | AI 聊天\n"
                    "免费 AI 由 DuckDuckGo 提供")


def main():
    try:
        DesktopPet()
    except Exception:
        traceback.print_exc()
        import tkinter.messagebox as mb
        mb.showerror("启动失败",
                     "凯尔希启动失败，请检查：\n"
                     "1. 是否有其他凯尔希正在运行\n"
                     "2. 网络是否正常（AI 聊天需要联网）")


if __name__ == "__main__":
    main()
