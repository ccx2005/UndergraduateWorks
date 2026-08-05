import sys
import json
import os
import httpx
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QComboBox, QMessageBox, QFileDialog,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt, QFileInfo, QSize, QThread, pyqtSignal, QTimer, QEvent
from PyQt5.QtGui import QFont, QPalette, QColor, QLinearGradient, QBrush, QPainter, QTextCursor

# 数据存储路径
DATA_FILE = "job_guide_data.json"
# 历史记录存储文件
HISTORY_FILE = "history_data.json"
# 对话记录存储文件
CHAT_HISTORY_FILE = "chat_history.json"

# ---- AI 就业助手系统提示词 ----
AGENT_SYSTEM_PROMPT = """你是一位资深的AI就业顾问，名叫"小智"。你拥有以下专业能力：

1. **职业规划**：根据用户专业、技能、经验，制定短期/中期/长期职业发展路径
2. **简历优化**：分析简历中的问题，提供"职责+成果+数据"的STAR法则优化建议
3. **岗位匹配**：对比用户简历与目标岗位，计算匹配度并给出提升方案
4. **面试辅导**：提供常见面试题解析、模拟面试、行为面试技巧
5. **行业洞察**：分析当前科技行业就业趋势、热门技术栈、薪资水平
6. **技能提升**：推荐学习路径、认证考试、实战项目

**交互规则**：
- 回复风格：专业、温暖、务实，用中文，适当使用emoji增加亲和力
- 先了解用户情况再给建议，不要一上来就长篇大论
- 回答要具体可执行，避免空洞的理论
- 如果用户描述不清，主动追问关键信息
- 对于复杂问题（如职业规划），分阶段给出建议
- 在适当时候引导用户使用左侧的"职业规划"、"简历优化"、"岗位匹配"等功能页面获取更详细的AI分析报告
- 每次回答控制在合理长度，避免信息过载

**用户画像**（如果用户已填写则参考）：
{user_profile}

请以"小智"的身份开始对话。"""

# 获取程序运行目录（兼容开发/打包环境）
def get_app_path():
    if getattr(sys, 'frozen', False):
        app_path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        app_path = os.path.dirname(os.path.abspath(__file__))
    return app_path

# 科技蓝主题样式表（美化版）
STYLE_SHEET = """
/* ==================== 全局 ==================== */
QWidget {
    font-family: "幼圆", "YouYuan", "Microsoft YaHei", sans-serif;
    font-size: 22px;
    color: #2C3E50;
}

QMainWindow {
    background-color: #F0F4FC;
}

/* ==================== 标题 ==================== */
QLabel#title_label {
    font-size: 48px;
    font-weight: bold;
    color: #165DFF;
    padding: 14px 0 8px 0;
    letter-spacing: 3px;
}

/* ==================== 标签页 ==================== */
QTabWidget {
    background-color: transparent;
    border: none;
}

QTabWidget::pane {
    border: 1px solid #D6E4FF;
    border-radius: 14px;
    background-color: #FFFFFF;
    padding: 20px;
    margin-top: -1px;
}

QTabBar::tab {
    background-color: #EAF2FF;
    color: #165DFF;
    padding: 12px 28px;
    margin: 0 3px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    font-weight: 600;
    font-size: 21px;
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #165DFF, stop:1 #2979FF);
    color: white;
}

QTabBar::tab:hover:!selected {
    background-color: #D6E4FF;
    color: #0E42C7;
}

/* ==================== 标签 ==================== */
QLabel {
    color: #1A3F7F;
    font-weight: 500;
    font-size: 22px;
}

QLabel#section_label {
    color: #0E42C7;
    font-weight: 700;
    font-size: 24px;
    padding: 6px 0 2px 0;
}

/* ==================== 输入控件 ==================== */
QLineEdit, QComboBox {
    border: 2px solid #D6E4FF;
    border-radius: 10px;
    padding: 10px 16px;
    background-color: #FFFFFF;
    selection-background-color: #165DFF;
    selection-color: white;
    font-size: 22px;
    min-height: 20px;
}

QLineEdit:focus, QComboBox:focus {
    border-color: #165DFF;
    background-color: #FAFBFF;
}

QComboBox {
    padding: 10px 14px;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox QAbstractItemView {
    border: 1px solid #D6E4FF;
    border-radius: 8px;
    background-color: white;
    selection-background-color: #EAF2FF;
    selection-color: #165DFF;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    padding: 8px 14px;
    border-radius: 6px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #F0F4FC;
}

/* ==================== 文本编辑框 ==================== */
QTextEdit {
    border: 2px solid #D6E4FF;
    border-radius: 12px;
    padding: 12px 16px;
    background-color: #FFFFFF;
    selection-background-color: #165DFF;
    selection-color: white;
    font-size: 22px;
    line-height: 1.6;
}

QTextEdit:focus {
    border-color: #165DFF;
    background-color: #FAFBFF;
}

QTextEdit[readOnly="true"] {
    background-color: #F7F9FE;
    color: #2C3E50;
}

/* ==================== 主按钮（科技蓝） ==================== */
QPushButton#primary_btn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2979FF, stop:1 #165DFF);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 14px 30px;
    font-weight: 700;
    font-size: 22px;
    min-width: 180px;
    min-height: 22px;
}

QPushButton#primary_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #448AFF, stop:1 #2979FF);
}

QPushButton#primary_btn:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #165DFF, stop:1 #0E42C7);
}

QPushButton#primary_btn:disabled {
    background: #B0C4DE;
    color: #E8E8E8;
}

/* ==================== 次要按钮（浅蓝边框） ==================== */
QPushButton#secondary_btn {
    background-color: #FFFFFF;
    color: #165DFF;
    border: 2px solid #165DFF;
    border-radius: 10px;
    padding: 14px 30px;
    font-weight: 600;
    font-size: 22px;
    min-width: 180px;
    min-height: 22px;
}

QPushButton#secondary_btn:hover {
    background-color: #EAF2FF;
    border-color: #2979FF;
    color: #0E42C7;
}

QPushButton#secondary_btn:pressed {
    background-color: #D6E4FF;
}

/* ==================== 危险按钮（红色） ==================== */
QPushButton#danger_btn {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF6B6B, stop:1 #FF4D4F);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 14px 30px;
    font-weight: 700;
    font-size: 22px;
    min-width: 180px;
    min-height: 22px;
}

QPushButton#danger_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #FF8787, stop:1 #FF6B6B);
}

QPushButton#danger_btn:pressed {
    background: #D9363E;
}

/* ==================== 列表控件 ==================== */
QListWidget {
    border: 2px solid #D6E4FF;
    border-radius: 12px;
    background-color: white;
    font-size: 21px;
    padding: 4px;
    outline: none;
}

QListWidget::item {
    padding: 10px 14px;
    border-bottom: 1px solid #EEF3FF;
    border-radius: 6px;
}

QListWidget::item:selected {
    background-color: #EAF2FF;
    color: #165DFF;
    font-weight: 600;
}

QListWidget::item:hover {
    background-color: #F5F8FF;
}

/* ==================== 滚动条美化 ==================== */
QScrollBar:vertical {
    border: none;
    background: #F0F4FC;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #C5D5F0;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #A0B8E0;
}

QScrollBar::handle:vertical:pressed {
    background: #7A9AD4;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #F0F4FC;
    height: 10px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background: #C5D5F0;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background: #A0B8E0;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ==================== 分割线 ==================== */
QFrame#separator {
    background-color: #D6E4FF;
    max-height: 2px;
    min-height: 2px;
    border-radius: 1px;
}

/* ==================== 提示框 ==================== */
QMessageBox {
    background-color: white;
    border-radius: 12px;
}

QMessageBox QPushButton {
    padding: 8px 20px;
    border-radius: 8px;
    min-width: 80px;
    font-size: 20px;
}
"""

class GradientBackgroundWidget(QWidget):
    """带科技蓝渐变背景的自定义控件"""
    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, QColor(22, 93, 255, 10))
        gradient.setColorAt(1, QColor(22, 93, 255, 0))
        painter.fillRect(self.rect(), QBrush(gradient))
        super().paintEvent(event)


class AgentStreamWorker(QThread):
    """后台线程：流式调用DeepSeek API"""
    new_token = pyqtSignal(str)      # 每收到一个token就发射
    finished = pyqtSignal(str)       # 完成后发射完整文本
    error = pyqtSignal(str)          # 出错时发射错误信息

    def __init__(self, api_key, base_url, messages, model="deepseek-chat"):
        super().__init__()
        self.api_key = api_key
        self.base_url = base_url
        self.messages = messages
        self.model = model
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            stream = client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=0.7,
                max_tokens=2000,
                stream=True
            )
            full_text = ""
            for chunk in stream:
                if self._is_cancelled:
                    break
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_text += token
                    self.new_token.emit(token)
            self.finished.emit(full_text)
        except Exception as e:
            self.error.emit(str(e))


class JobGuideApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.user_data = self.load_user_data()
        self.history_data = self.load_history_data()  # 加载历史记录
        self.init_ui()

    def init_ui(self):
        # 主窗口设置
        self.setWindowTitle("精准就业辅助系统")
        self.setGeometry(100, 100, 1600, 1150)  # 初始尺寸：宽1600，高1150
        self.setMinimumSize(1200, 880)  # 最小尺寸限制
        self.center_window()  # 窗口居中
        
        # 中心部件（使用渐变背景）
        central_widget = GradientBackgroundWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        # 标题
        title_frame = QFrame()
        title_frame.setStyleSheet("""
            QFrame {
                background-color: transparent;
                border: none;
            }
        """)
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 4)
        title_layout.setSpacing(2)
        title_label = QLabel("精准就业辅助系统")
        title_label.setObjectName("title_label")
        title_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(title_label)
        subtitle = QLabel("AI-Powered Career Assistant · 智能就业顾问")
        subtitle.setStyleSheet("color: #7A9AD4; font-size: 18px; background: transparent;")
        subtitle.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(subtitle)
        main_layout.addWidget(title_frame)

        # 标签页
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setTabShape(QTabWidget.Rounded)
        main_layout.addWidget(self.tab_widget)

        # ---- 新增：主标签页 - AI智能就业助手 ----
        self.agent_tab = QWidget()
        self.init_agent_tab()
        self.tab_widget.addTab(self.agent_tab, "🤖 AI智能就业助手")

        # 1. 职业规划标签页
        self.career_plan_tab = QWidget()
        self.init_career_plan_tab()
        self.tab_widget.addTab(self.career_plan_tab, "📋 个性化职业规划")

        # 2. 简历优化标签页
        self.resume_opt_tab = QWidget()
        self.init_resume_opt_tab()
        self.tab_widget.addTab(self.resume_opt_tab, "📝 简历优化")

        # 3. 岗位匹配标签页
        self.job_match_tab = QWidget()
        self.init_job_match_tab()
        self.tab_widget.addTab(self.job_match_tab, "🎯 岗位匹配分析")

        # 4. 数据管理标签页
        self.data_manage_tab = QWidget()
        self.init_data_manage_tab()
        self.tab_widget.addTab(self.data_manage_tab, "⚙️ 数据管理")

        # 5. 历史记录标签页
        self.history_tab = QWidget()
        self.init_history_tab()
        self.tab_widget.addTab(self.history_tab, "📜 历史搜索数据")

        # 加载对话历史
        self.conversation_history = self.load_chat_history()
        # 恢复聊天显示
        self.restore_chat_display()

        # 应用样式表
        self.setStyleSheet(STYLE_SHEET)

    def center_window(self):
        """窗口居中显示"""
        screen_geo = QApplication.desktop().screenGeometry()
        win_geo = self.frameGeometry()
        win_geo.moveCenter(screen_geo.center())
        self.move(win_geo.topLeft())

    # ============ AI智能就业助手（Agent核心）============
    def init_agent_tab(self):
        """初始化AI智能就业助手对话页面"""
        layout = QVBoxLayout(self.agent_tab)
        layout.setSpacing(12)
        layout.setContentsMargins(5, 5, 5, 5)

        # 对话显示区域
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setObjectName("chat_display")
        self.chat_display.setStyleSheet("""
            QTextEdit#chat_display {
                background-color: #F8FAFE;
                border: 2px solid #D6E4FF;
                border-radius: 14px;
                padding: 16px;
                font-size: 24px;
                line-height: 1.7;
            }
        """)
        layout.addWidget(self.chat_display, stretch=1)

        # 快捷提问按钮行（两行布局）
        quick_wrapper = QVBoxLayout()
        quick_wrapper.setSpacing(6)

        quick_label = QLabel("💡 快捷提问")
        quick_label.setStyleSheet("color: #165DFF; font-weight: 700; font-size: 22px; background: transparent;")
        quick_wrapper.addWidget(quick_label)

        quick_questions = [
            ("📋 职业规划", "请根据我的专业和技能，帮我制定一份详细的职业发展规划"),
            ("📝 简历优化", "帮我分析一下，一份好的技术简历应该包含哪些要点？"),
            ("🎤 面试辅导", "请帮我模拟一次后端开发岗位的技术面试"),
            ("📊 行业分析", "2025年科技行业哪些技术方向最有前景？"),
            ("💪 技能提升", "我是一名计算机专业学生，应该学习哪些技术来提升就业竞争力？"),
            ("💰 薪资谈判", "面试中如何合理地谈薪资？有什么技巧？"),
        ]

        self.quick_buttons = []
        # 第一行：前3个
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        for text, question in quick_questions[:3]:
            btn = self._make_quick_btn(text, question)
            self.quick_buttons.append(btn)
            row1.addWidget(btn)
        row1.addStretch()
        quick_wrapper.addLayout(row1)

        # 第二行：后3个
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        for text, question in quick_questions[3:]:
            btn = self._make_quick_btn(text, question)
            self.quick_buttons.append(btn)
            row2.addWidget(btn)
        row2.addStretch()
        quick_wrapper.addLayout(row2)

        layout.addLayout(quick_wrapper)

        # 输入区域：水平布局（输入框 + 右侧按钮列）
        input_frame = QFrame()
        input_frame.setObjectName("input_frame")
        input_frame.setStyleSheet("""
            QFrame#input_frame {
                background-color: #FFFFFF;
                border: 2px solid #D6E4FF;
                border-radius: 14px;
                padding: 6px;
            }
            QFrame#input_frame:hover {
                border-color: #B0C8F0;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setSpacing(8)
        input_layout.setContentsMargins(10, 6, 6, 6)

        self.agent_input = QTextEdit()
        self.agent_input.setPlaceholderText("输入你的问题，Ctrl+Enter 发送...")
        self.agent_input.setMaximumHeight(72)
        self.agent_input.setMinimumHeight(44)
        self.agent_input.setStyleSheet("""
            QTextEdit {
                border: none;
                border-radius: 8px;
                padding: 8px 4px;
                font-size: 24px;
                background-color: transparent;
            }
            QTextEdit:focus {
                border: none;
                background-color: transparent;
            }
        """)
        self.agent_input.installEventFilter(self)
        self.agent_input.setAcceptRichText(False)
        input_layout.addWidget(self.agent_input, stretch=1)

        # 右侧按钮列
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)

        send_btn = QPushButton("🚀 发送")
        send_btn.setObjectName("primary_btn")
        send_btn.setFixedSize(90, 36)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2979FF, stop:1 #165DFF);
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 700;
                font-size: 22px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #448AFF, stop:1 #2979FF);
            }
        """)
        send_btn.clicked.connect(lambda: self.send_agent_message())
        btn_col.addWidget(send_btn)

        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setFixedSize(90, 30)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F5F5;
                color: #999;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #FFF0F0;
                color: #FF4D4F;
                border-color: #FFB0B0;
            }
        """)
        clear_btn.clicked.connect(self.clear_agent_chat)
        btn_col.addWidget(clear_btn)

        input_layout.addLayout(btn_col)
        layout.addWidget(input_frame)

        # 状态标签
        self.agent_status = QLabel("✅ 就绪，随时为你服务")
        self.agent_status.setStyleSheet("color: #A0AEC0; font-size: 16px; background: transparent; padding: 2px 8px;")
        self.agent_status.setAlignment(Qt.AlignRight)
        layout.addWidget(self.agent_status)

        self.agent_worker = None

    def _make_quick_btn(self, text, question):
        """创建快捷提问按钮"""
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #165DFF;
                border: 1.5px solid #B3D4FF;
                border-radius: 20px;
                padding: 8px 18px;
                font-size: 18px;
            }
            QPushButton:hover {
                background-color: #EAF2FF;
                border-color: #165DFF;
                color: #0E42C7;
            }
            QPushButton:pressed {
                background-color: #D6E4FF;
            }
        """)
        btn.clicked.connect(lambda checked, q=question: self.send_agent_message(q))
        return btn

    def eventFilter(self, obj, event):
        """捕获Ctrl+Enter发送消息"""
        if obj == self.agent_input and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
                self.send_agent_message()
                return True
        return super().eventFilter(obj, event)

    def get_user_profile_text(self):
        """获取当前用户画像文本"""
        major = self.major_edit.text().strip() if hasattr(self, 'major_edit') else ""
        skills = self.skills_edit.text().strip() if hasattr(self, 'skills_edit') else ""
        intention = self.intention_edit.currentText() if hasattr(self, 'intention_edit') else ""
        experience = self.exp_edit.text().strip() if hasattr(self, 'exp_edit') else ""
        parts = []
        if major: parts.append(f"- 专业：{major}")
        if skills: parts.append(f"- 核心技能：{skills}")
        if intention: parts.append(f"- 求职意向：{intention}")
        if experience: parts.append(f"- 工作经验：{experience}年")
        return "\n".join(parts) if parts else "用户尚未填写个人资料"

    def restore_chat_display(self):
        """恢复已保存的对话显示"""
        if not self.conversation_history:
            # 无历史记录时显示欢迎语
            self.append_chat_bubble("🤖 小智",
                "你好！我是你的专属AI就业顾问「小智」👋\n\n"
                "我能帮到你的事情：\n"
                "📋 制定个性化职业发展规划\n"
                "📝 分析和优化你的简历\n"
                "🎯 精准匹配目标岗位\n"
                "🎤 模拟技术面试辅导\n"
                "📊 行业趋势与薪资分析\n"
                "💪 学习路径与技能提升建议\n\n"
                "你可以先在左侧「职业规划」页面填写你的基本资料，\n"
                "然后随时回来和我聊天！输入问题或点击下方的快捷提问开始吧~", "#333")
        else:
            for msg in self.conversation_history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    self.append_chat_bubble("🧑 你", content, "#165DFF")
                elif role == "assistant":
                    self.append_chat_bubble("🤖 小智", content, "#333")

    def append_chat_bubble(self, sender, text, color):
        """向聊天区域添加气泡消息"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)

        # 发送者标签
        fmt = cursor.charFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontWeight(QFont.Bold if sender.startswith("🧑") else QFont.Bold)
        cursor.insertText(f"\n{sender}\n", fmt)

        # 消息内容
        fmt2 = cursor.charFormat()
        fmt2.setForeground(QColor("#333"))
        fmt2.setFontWeight(QFont.Normal)
        cursor.insertText(f"{text}\n", fmt2)
        cursor.insertText("─" * 50 + "\n")

        self.chat_display.setTextCursor(cursor)
        # 滚动到底部
        self.chat_display.ensureCursorVisible()

    def send_agent_message(self, preset_text=None):
        """发送消息给AI Agent"""
        user_text = preset_text if preset_text else self.agent_input.toPlainText().strip()
        if not user_text:
            return

        # 如果有输入框内容（非预设），清空输入框
        if not preset_text:
            self.agent_input.clear()

        # 显示用户消息
        self.append_chat_bubble("🧑 你", user_text, "#165DFF")

        # 添加到对话历史
        self.conversation_history.append({"role": "user", "content": user_text})
        self.save_chat_history()

        # 构建完整消息列表
        system_prompt = AGENT_SYSTEM_PROMPT.format(user_profile=self.get_user_profile_text())
        messages = [{"role": "system", "content": system_prompt}]
        # 加入最近20条历史（避免token过长）
        recent_history = self.conversation_history[-20:]
        messages.extend(recent_history)

        # 放置一个"正在输入..."占位
        self.append_chat_bubble("🤖 小智", "⏳ 思考中...", "#999")
        self.agent_status.setText("⏳ 小智正在思考...")
        self.chat_display.repaint()

        # 读取配置
        config_path = os.path.join(get_app_path(), "config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except:
            QMessageBox.warning(self, "配置错误", "无法读取config.json")
            return

        api_key = config.get("DEEPSEEK_API_KEY", "").strip()
        base_url = config.get("BASE_URL", "https://api.deepseek.com")
        if not api_key:
            QMessageBox.warning(self, "配置错误", "API Key未配置")
            return

        # 启动流式工作线程
        self.agent_streaming_buffer = ""
        self.agent_worker = AgentStreamWorker(api_key, base_url, messages)
        self.agent_worker.new_token.connect(self.on_agent_token)
        self.agent_worker.finished.connect(self.on_agent_finished)
        self.agent_worker.error.connect(self.on_agent_error)
        self.agent_worker.start()

        # 禁用发送按钮（避免重复发送）
        self.agent_input.setEnabled(False)
        for btn in self.quick_buttons:
            btn.setEnabled(False)

    def on_agent_token(self, token):
        """收到流式token - 实时更新最后一条消息"""
        self.agent_streaming_buffer += token

        # 获取全文并替换最后一条消息
        full_html = self.chat_display.toPlainText()
        # 找到最后一个"🤖 小智"的位置，替换其后的内容
        last_assistant = full_html.rfind("🤖 小智\n")
        if last_assistant >= 0:
            new_content = full_html[:last_assistant]
            new_content += f"🤖 小智\n{self.agent_streaming_buffer}\n{'─' * 50}\n"
            self.chat_display.setPlainText(new_content)
            # 滚动到底部
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.chat_display.setTextCursor(cursor)
            self.chat_display.ensureCursorVisible()

    def on_agent_finished(self, full_text):
        """流式输出完成"""
        # 移除"思考中..."占位并显示最终内容
        text = self.chat_display.toPlainText()
        # 处理可能的"思考中..."残留
        text = text.replace("⏳ 思考中...", "")
        last_assistant = text.rfind("🤖 小智\n")
        if last_assistant >= 0:
            final_content = text[:last_assistant]
            final_content += f"🤖 小智\n{full_text}\n{'─' * 50}\n"
            self.chat_display.setPlainText(final_content)
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.chat_display.setTextCursor(cursor)
            self.chat_display.ensureCursorVisible()

        # 保存对话
        self.conversation_history.append({"role": "assistant", "content": full_text})
        self.save_chat_history()

        # 恢复UI
        self.agent_status.setText("✅ 就绪，随时为你服务")
        self.agent_input.setEnabled(True)
        for btn in self.quick_buttons:
            btn.setEnabled(True)
        self.agent_worker = None

    def on_agent_error(self, error_msg):
        """流式输出出错"""
        self.append_chat_bubble("🤖 小智", f"❌ 出错了：{error_msg}\n请检查网络连接或API配置后重试。", "#FF4D4F")
        self.agent_status.setText(f"❌ 错误：{error_msg}")
        self.agent_input.setEnabled(True)
        for btn in self.quick_buttons:
            btn.setEnabled(True)
        self.agent_worker = None

    def clear_agent_chat(self):
        """清空对话"""
        reply = QMessageBox.question(self, "确认", "确定清空所有对话记录吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.conversation_history = []
            self.save_chat_history()
            self.chat_display.clear()
            self.append_chat_bubble("🤖 小智",
                "对话已清空！我是你的AI就业顾问，有什么可以帮助你的吗？😊", "#333")

    def load_chat_history(self):
        """加载对话历史"""
        chat_path = os.path.join(get_app_path(), CHAT_HISTORY_FILE)
        if os.path.exists(chat_path):
            try:
                with open(chat_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_chat_history(self):
        """保存对话历史"""
        chat_path = os.path.join(get_app_path(), CHAT_HISTORY_FILE)
        try:
            # 最多保留最近50条消息
            save_data = self.conversation_history[-50:]
            with open(chat_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存对话历史失败：{e}")

    def init_career_plan_tab(self):
        """初始化职业规划标签页"""
        layout = QVBoxLayout(self.career_plan_tab)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        # 输入区域
        input_layout = QHBoxLayout()
        input_layout.setSpacing(20)

        # 左侧：基础信息卡片
        left_card = QFrame()
        left_card.setObjectName("info_card")
        left_card.setStyleSheet("""
            QFrame#info_card {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 14px;
                padding: 16px;
            }
        """)
        left_layout = QVBoxLayout(left_card)
        left_layout.setSpacing(14)

        # 专业输入
        sec1 = QLabel("📚 专业")
        sec1.setObjectName("section_label")
        left_layout.addWidget(sec1)
        self.major_edit = QLineEdit()
        self.major_edit.setPlaceholderText("例如：计算机科学与技术")
        self.major_edit.setText(self.user_data.get("major", ""))
        self.major_edit.setMinimumHeight(36)
        left_layout.addWidget(self.major_edit)

        # 核心技能
        sec2 = QLabel("💻 核心技能")
        sec2.setObjectName("section_label")
        left_layout.addWidget(sec2)
        self.skills_edit = QLineEdit()
        self.skills_edit.setPlaceholderText("逗号分隔，例如：Python, Django, MySQL")
        self.skills_edit.setText(self.user_data.get("skills", ""))
        self.skills_edit.setMinimumHeight(36)
        left_layout.addWidget(self.skills_edit)

        # 求职意向
        sec3 = QLabel("🎯 求职意向")
        sec3.setObjectName("section_label")
        left_layout.addWidget(sec3)
        self.intention_edit = QComboBox()
        intentions = ["后端开发", "前端开发", "数据分析", "测试开发", "产品经理", "运营", "人工智能/算法", "嵌入式开发", "运维/DevOps", "其他"]
        self.intention_edit.addItems(intentions)
        if self.user_data.get("intention") in intentions:
            self.intention_edit.setCurrentText(self.user_data.get("intention"))
        self.intention_edit.setMinimumHeight(36)
        left_layout.addWidget(self.intention_edit)

        # 工作经验
        sec4 = QLabel("📅 工作经验（年）")
        sec4.setObjectName("section_label")
        left_layout.addWidget(sec4)
        self.exp_edit = QLineEdit()
        self.exp_edit.setPlaceholderText("0")
        self.exp_edit.setText(self.user_data.get("experience", "0"))
        self.exp_edit.setMinimumHeight(36)
        left_layout.addWidget(self.exp_edit)

        left_layout.addStretch()
        input_layout.addWidget(left_card, stretch=2)

        # 右侧：规划建议输出卡片
        right_card = QFrame()
        right_card.setObjectName("result_card")
        right_card.setStyleSheet("""
            QFrame#result_card {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 14px;
                padding: 16px;
            }
        """)
        right_layout = QVBoxLayout(right_card)
        right_layout.setSpacing(10)
        right_layout.addWidget(QLabel("📝 个性化职业规划建议"))
        self.plan_result_edit = QTextEdit()
        self.plan_result_edit.setReadOnly(True)
        self.plan_result_edit.setText(self.user_data.get("career_plan", ""))
        font = QFont()
        font.setPointSize(22)
        self.plan_result_edit.setFont(font)
        right_layout.addWidget(self.plan_result_edit, stretch=1)

        input_layout.addWidget(right_card, stretch=3)
        layout.addLayout(input_layout)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)
        btn_layout.setContentsMargins(0, 4, 0, 0)

        self.gen_career_btn = QPushButton("🚀 生成职业规划")
        self.gen_career_btn.setObjectName("primary_btn")
        self.gen_career_btn.setCursor(Qt.PointingHandCursor)
        self.gen_career_btn.clicked.connect(self.generate_career_plan)

        self.gen_resume_btn = QPushButton("📄 生成适配简历模板")
        self.gen_resume_btn.setObjectName("secondary_btn")
        self.gen_resume_btn.setCursor(Qt.PointingHandCursor)
        self.gen_resume_btn.clicked.connect(self.generate_matched_resume)

        btn_layout.addWidget(self.gen_career_btn)
        btn_layout.addWidget(self.gen_resume_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
            

    def init_resume_opt_tab(self):
        """初始化简历优化标签页"""
        layout = QVBoxLayout(self.resume_opt_tab)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        # 上半部分：简历输入
        input_card = QFrame()
        input_card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 14px;
                padding: 16px;
            }
        """)
        input_layout = QVBoxLayout(input_card)
        input_layout.setSpacing(10)
        input_layout.addWidget(QLabel("📄 输入 / 粘贴简历内容"))
        self.resume_edit = QTextEdit()
        self.resume_edit.setPlaceholderText("在此粘贴你的简历内容，或点击下方按钮从文件导入...")
        self.resume_edit.setText(self.user_data.get("resume", ""))
        self.resume_edit.setMinimumHeight(160)
        input_layout.addWidget(self.resume_edit)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        upload_btn = QPushButton("📂 从文件导入简历")
        upload_btn.setObjectName("secondary_btn")
        upload_btn.setCursor(Qt.PointingHandCursor)
        upload_btn.clicked.connect(self.upload_resume)
        btn_layout.addWidget(upload_btn)

        opt_btn = QPushButton("✨ 智能优化简历")
        opt_btn.setObjectName("primary_btn")
        opt_btn.setCursor(Qt.PointingHandCursor)
        opt_btn.clicked.connect(self.optimize_resume)
        btn_layout.addWidget(opt_btn)
        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)

        layout.addWidget(input_card, stretch=2)

        # 下半部分：优化结果
        result_card = QFrame()
        result_card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 14px;
                padding: 16px;
            }
        """)
        result_layout = QVBoxLayout(result_card)
        result_layout.setSpacing(10)
        result_layout.addWidget(QLabel("✅ 简历优化建议"))
        self.resume_opt_result = QTextEdit()
        self.resume_opt_result.setReadOnly(True)
        self.resume_opt_result.setText(self.user_data.get("resume_opt", ""))
        font = QFont()
        font.setPointSize(22)
        self.resume_opt_result.setFont(font)
        self.resume_opt_result.setMinimumHeight(160)
        result_layout.addWidget(self.resume_opt_result, stretch=1)

        layout.addWidget(result_card, stretch=3)

    def init_job_match_tab(self):
        """初始化岗位匹配标签页"""
        layout = QVBoxLayout(self.job_match_tab)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        # 上半部分：岗位描述输入
        input_card = QFrame()
        input_card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 14px;
                padding: 16px;
            }
        """)
        input_layout = QVBoxLayout(input_card)
        input_layout.setSpacing(10)
        input_layout.addWidget(QLabel("🔍 输入目标岗位描述"))
        self.job_desc_edit = QTextEdit()
        self.job_desc_edit.setPlaceholderText("粘贴招聘JD（岗位描述），包括岗位职责、技术要求、任职资格等...")
        self.job_desc_edit.setMinimumHeight(140)
        input_layout.addWidget(self.job_desc_edit)

        match_btn = QPushButton("📊 智能分析匹配度")
        match_btn.setObjectName("primary_btn")
        match_btn.setCursor(Qt.PointingHandCursor)
        match_btn.clicked.connect(self.analyze_job_match)
        input_layout.addWidget(match_btn, alignment=Qt.AlignCenter)

        layout.addWidget(input_card, stretch=2)

        # 下半部分：匹配结果
        result_card = QFrame()
        result_card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 14px;
                padding: 16px;
            }
        """)
        result_layout = QVBoxLayout(result_card)
        result_layout.setSpacing(10)
        result_layout.addWidget(QLabel("📈 岗位匹配分析结果"))
        self.match_result_edit = QTextEdit()
        self.match_result_edit.setReadOnly(True)
        font = QFont()
        font.setPointSize(22)
        self.match_result_edit.setFont(font)
        self.match_result_edit.setMinimumHeight(160)
        result_layout.addWidget(self.match_result_edit, stretch=1)

        layout.addWidget(result_card, stretch=3)

    def init_data_manage_tab(self):
        """初始化数据管理标签页"""
        layout = QVBoxLayout(self.data_manage_tab)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignCenter)

        manage_card = QFrame()
        manage_card.setFixedWidth(500)
        manage_card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 16px;
                padding: 30px;
            }
        """)
        card_layout = QVBoxLayout(manage_card)
        card_layout.setSpacing(18)
        card_layout.setAlignment(Qt.AlignCenter)

        title = QLabel("⚙️ 数据管理中心")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #165DFF; background: transparent;")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        desc = QLabel("管理你的个人资料、AI生成结果和对话记录")
        desc.setStyleSheet("font-size: 20px; color: #888; background: transparent;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        card_layout.addSpacing(10)

        save_btn = QPushButton("💾 保存所有数据")
        save_btn.setObjectName("primary_btn")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setMinimumHeight(44)
        save_btn.clicked.connect(self.save_user_data)
        card_layout.addWidget(save_btn)

        clear_btn = QPushButton("🗑️ 清空所有数据（含对话）")
        clear_btn.setObjectName("danger_btn")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setMinimumHeight(44)
        clear_btn.clicked.connect(self.clear_user_data)
        card_layout.addWidget(clear_btn)

        layout.addWidget(manage_card, alignment=Qt.AlignCenter)

    def init_history_tab(self):
        """初始化历史搜索数据页面"""
        layout = QVBoxLayout(self.history_tab)
        layout.setSpacing(14)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel("📜 历史搜索记录"))

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #D6E4FF;
                border-radius: 2px;
            }
        """)

        # 左侧：历史记录列表
        left_card = QFrame()
        left_card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 14px;
                padding: 10px;
            }
        """)
        left_layout = QVBoxLayout(left_card)
        left_layout.setSpacing(8)
        self.history_list = QListWidget()
        self.history_list.setMinimumWidth(280)
        self.load_history_to_list()
        self.history_list.itemClicked.connect(self.show_history_detail)
        left_layout.addWidget(self.history_list)
        splitter.addWidget(left_card)

        # 右侧：详情展示
        right_card = QFrame()
        right_card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFE;
                border: 1px solid #D6E4FF;
                border-radius: 14px;
                padding: 16px;
            }
        """)
        right_layout = QVBoxLayout(right_card)
        right_layout.setSpacing(10)

        self.history_detail_title = QLabel("选中记录查看详情")
        self.history_detail_title.setStyleSheet("font-weight: 700; font-size: 24px; color: #165DFF; background: transparent;")
        right_layout.addWidget(self.history_detail_title)

        self.history_detail_content = QTextEdit()
        self.history_detail_content.setReadOnly(True)
        self.history_detail_content.setMinimumHeight(300)
        font = QFont()
        font.setPointSize(22)
        self.history_detail_content.setFont(font)
        right_layout.addWidget(self.history_detail_content, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        del_selected_btn = QPushButton("🗑️ 删除选中记录")
        del_selected_btn.setObjectName("danger_btn")
        del_selected_btn.setCursor(Qt.PointingHandCursor)
        del_selected_btn.clicked.connect(self.delete_selected_history)
        btn_layout.addWidget(del_selected_btn)

        clear_all_btn = QPushButton("🧹 清空全部记录")
        clear_all_btn.setObjectName("danger_btn")
        clear_all_btn.setCursor(Qt.PointingHandCursor)
        clear_all_btn.clicked.connect(self.clear_all_history)
        btn_layout.addWidget(clear_all_btn)
        btn_layout.addStretch()

        right_layout.addLayout(btn_layout)
        splitter.addWidget(right_card)

        layout.addWidget(splitter, stretch=1)

    def init_deepseek_client(self):
        """初始化DeepSeek客户端（含配置文件读取，带缓存）"""
        # 使用缓存避免重复弹窗
        config = self._load_config_cached()
        if not config:
            return None

        # 校验API Key
        api_key = config.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            QMessageBox.warning(self, "配置错误", "config.json中DEEPSEEK_API_KEY不能为空！")
            return None

        # 初始化客户端
        try:
            client_kwargs = {
                "api_key": api_key,
                "base_url": config.get("BASE_URL", "https://api.deepseek.com")
            }
            proxy_url = config.get("PROXY_URL", "").strip()
            if proxy_url:
                client_kwargs["http_client"] = httpx.Client(
                    proxies=proxy_url,
                    timeout=30.0
                )
            from openai import OpenAI
            client = OpenAI(**client_kwargs)
            return client
        except Exception as e:
            QMessageBox.critical(self, "客户端初始化失败", f"错误原因：{str(e)}")
            return None

    def _load_config_cached(self):
        """读取配置文件（带缓存，避免重复弹窗）"""
        if hasattr(self, '_config_cache'):
            return self._config_cache

        app_path = get_app_path()
        config_path = os.path.join(app_path, "config.json")

        default_config = {
            "DEEPSEEK_API_KEY": "",
            "BASE_URL": "https://api.deepseek.com",
            "PROXY_URL": ""
        }

        config = default_config.copy()
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    config.update(user_config)
            except json.JSONDecodeError:
                QMessageBox.warning(self, "配置错误", "config.json格式错误！请检查JSON语法。")
                return None
            except Exception as e:
                QMessageBox.warning(self, "配置错误", f"读取配置文件失败：{str(e)}")
                return None
        else:
            QMessageBox.warning(
                self, "配置缺失",
                f"未找到config.json文件！\n请在程序同目录创建该文件，内容示例：\n{json.dumps(default_config, ensure_ascii=False, indent=4)}"
            )
            return None

        self._config_cache = config
        return config

    def generate_career_plan(self):
        """生成个性化职业规划（调用DeepSeek API）"""
        major = self.major_edit.text().strip()
        skills = self.skills_edit.text().strip().split(",")
        intention = self.intention_edit.currentText()
        experience = self.exp_edit.text().strip()

        if not major or not skills or intention == "":
            QMessageBox.warning(self, "输入错误", "请完善所有基础信息！")
            return

        # 获取DeepSeek客户端
        client = self.init_deepseek_client()
        if not client:
            return

        # 构造Prompt
        prompt = f"""
        你是一位资深职业规划师，基于以下信息为用户生成精准的个性化职业规划：
        - 专业：{major}
        - 核心技能：{', '.join(skills)}
        - 求职意向：{intention}
        - 工作经验：{experience}年

        要求：
        1. 分短期（1-3个月）、中期（3-6个月）、长期（6-12个月）给出可执行路径；
        2. 结合当前就业市场趋势，推荐3个高匹配的岗位方向；
        3. 输出格式清晰，分点列出，语言专业简洁，适配国内就业环境；
        4. 整体风格贴合科技行业求职者的需求，突出技能提升和岗位适配性。
        """

        try:
            # 调用API
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是专业的职业规划顾问，专注于科技行业就业指导，输出内容仅包含规划建议，无多余客套话"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1200
            )
            plan = response.choices[0].message.content
            self.plan_result_edit.setText(plan)
            self.user_data["career_plan"] = plan
            self.user_data["major"] = major
            self.user_data["skills"] = ",".join(skills)
            self.user_data["intention"] = intention
            self.user_data["experience"] = experience
            
            # 添加历史记录
            self.add_history_record(
                record_type="个性化职业规划",
                content=plan,
                params={
                    "专业": major,
                    "核心技能": ",".join(skills),
                    "求职意向": intention,
                    "工作经验": experience
                }
            )
            
            QMessageBox.information(self, "成功", "AI个性化职业规划已生成！")
        except Exception as e:
            QMessageBox.critical(self, "API调用失败", f"错误原因：{str(e)}")
    def generate_matched_resume(self):
            """
            根据职业规划 → 自动生成适配的简历模板（联动功能）
            """
            # 1. 获取用户信息
            major = self.major_edit.text().strip()
            skills = self.skills_edit.text().strip()
            intention = self.intention_edit.currentText()
            experience = self.exp_edit.text().strip()
            career_plan = self.plan_result_edit.toPlainText().strip()

            if not major or not skills or not intention:
                QMessageBox.warning(self, "提示", "请先生成职业规划！")
                return

            # 2. 自动生成名片式简历模板
            resume_template = f"""
╔══════════════════════════════════════════════════╗
║            个 人 简 历                            ║
╚══════════════════════════════════════════════════╝

┏━━━━━━━━━━━━ 基本信息 ━━━━━━━━━━━━
  专　　业： {major}
  求职意向： {intention}
  工作经验： {experience} 年
  核心技能： {skills}

┏━━━━━━━━━━━━ AI 职业规划摘要 ━━━━━━━━━━━━
  {career_plan[:400]}...

┏━━━━━━━━━━━━ 专业技能 ━━━━━━━━━━━━
  {skills}

┏━━━━━━━━━━━━ 项目经历 ━━━━━━━━━━━━
  （请根据你的实际项目经历补充，建议使用 STAR 法则）

┏━━━━━━━━━━━━ 自我评价 ━━━━━━━━━━━━
  本人具备 {skills.split(',')[0] if ',' in skills else skills} 等相关技能，
  专业方向为 {major}，意向岗位为 {intention}，
  具备良好的学习能力、团队协作精神与岗位适配度。
            """

            # 3. 自动填入【简历优化】页面
            self.resume_edit.setText(resume_template.strip())

            # 4. 自动切换到简历优化标签页
            self.tab_widget.setCurrentIndex(2)

            QMessageBox.information(self, "成功", "已根据职业规划生成简历模板！\n请切换到「简历优化」页面查看并优化。")
    def upload_resume(self):
        """从文件导入简历"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择简历文件", "", "文本文件 (*.txt);;所有文件 (*.*)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    resume_content = f.read()
                    self.resume_edit.setText(resume_content)
                    self.user_data["resume"] = resume_content
                    QMessageBox.information(self, "成功", "简历导入完成！")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导入失败：{str(e)}")

    def optimize_resume(self):
        """优化简历（调用DeepSeek API）"""
        resume = self.resume_edit.toPlainText().strip()
        if not resume:
            QMessageBox.warning(self, "输入错误", "请输入简历内容！")
            return

        # 获取DeepSeek客户端
        client = self.init_deepseek_client()
        if not client:
            return

        intention = self.user_data.get("intention", "目标岗位")
        # 构造Prompt
        prompt = f"""
        你是资深简历优化专家，基于以下简历内容和求职意向，提供专业的优化建议：
        求职意向：{intention}
        简历内容：
        {resume}

        优化要求：
        1. 分析简历中缺失的核心关键词（适配{intention}岗位）；
        2. 给出具体的格式优化建议（采用「职责+成果+数据」结构）；
        3. 指出冗余内容并建议删减；
        4. 突出与求职意向匹配的技能和经验；
        5. 输出格式清晰，分点列出，语言简洁，可直接落地修改。
        """

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是简历优化专家，专注于科技行业简历优化，建议实用、具体、可落地"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1200
            )
            opt_suggest = response.choices[0].message.content
            self.resume_opt_result.setText(opt_suggest)
            self.user_data["resume_opt"] = opt_suggest
            
            # 添加历史记录
            self.add_history_record(
                record_type="简历优化",
                content=opt_suggest,
                params={
                    "求职意向": intention,
                    "简历内容摘要": resume[:100] + "..." if len(resume) > 100 else resume
                }
            )
            
            QMessageBox.information(self, "成功", "AI简历优化建议已生成！")
        except Exception as e:
            QMessageBox.critical(self, "API调用失败", f"错误原因：{str(e)}")

    def analyze_job_match(self):
        """分析岗位匹配度（调用DeepSeek API）"""
        resume = self.resume_edit.toPlainText().strip()
        job_desc = self.job_desc_edit.toPlainText().strip()

        if not resume or not job_desc:
            QMessageBox.warning(self, "输入错误", "请完善简历和岗位描述！")
            return

        # 获取DeepSeek客户端
        client = self.init_deepseek_client()
        if not client:
            return

        # 构造Prompt
        prompt = f"""
        你是岗位匹配分析专家，请基于用户简历和岗位描述，分析匹配度并给出提升建议：
        简历内容：
        {resume}

        岗位描述：
        {job_desc}

        分析要求：
        1. 计算精准的匹配度百分比；
        2. 列出匹配的核心关键词和缺失的关键要求；
        3. 根据匹配度给出针对性的提升建议；
        4. 输出格式清晰，分点列出，语言专业简洁。
        """

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是岗位匹配分析专家，专注于科技行业岗位匹配，分析结果客观、精准"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1200
            )
            match_result = response.choices[0].message.content
            self.match_result_edit.setText(match_result)
            
            # 添加历史记录
            self.add_history_record(
                record_type="岗位匹配分析",
                content=match_result,
                params={
                    "简历内容摘要": resume[:100] + "..." if len(resume) > 100 else resume,
                    "岗位描述摘要": job_desc[:100] + "..." if len(job_desc) > 100 else job_desc
                }
            )
            
        except Exception as e:
            QMessageBox.critical(self, "API调用失败", f"错误原因：{str(e)}")

    def load_user_data(self):
        """加载用户数据"""
        data_path = os.path.join(get_app_path(), DATA_FILE)
        if os.path.exists(data_path):
            try:
                with open(data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_user_data(self):
        """保存用户数据"""
        data_path = os.path.join(get_app_path(), DATA_FILE)
        try:
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump(self.user_data, f, ensure_ascii=False, indent=4)
            QMessageBox.information(self, "成功", "所有数据已保存！")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")

    def clear_user_data(self):
        """清空用户数据"""
        reply = QMessageBox.question(self, "确认", "是否确定清空所有数据(含对话记录)？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.user_data = {}
            self.major_edit.clear()
            self.skills_edit.clear()
            self.intention_edit.setCurrentIndex(0)
            self.exp_edit.setText("0")
            self.plan_result_edit.clear()
            self.resume_edit.clear()
            self.resume_opt_result.clear()
            self.match_result_edit.clear()
            data_path = os.path.join(get_app_path(), DATA_FILE)
            if os.path.exists(data_path):
                os.remove(data_path)
            # 同时清空对话记录
            self.conversation_history = []
            self.save_chat_history()
            self.chat_display.clear()
            QMessageBox.information(self, "成功", "所有数据(含对话记录)已清空！")

    def load_history_data(self):
        """加载历史记录数据"""
        history_path = os.path.join(get_app_path(), HISTORY_FILE)
        if os.path.exists(history_path):
            try:
                with open(history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_history_data(self):
        """保存历史记录数据"""
        history_path = os.path.join(get_app_path(), HISTORY_FILE)
        try:
            with open(history_path, "w", encoding="utf-8") as f:
                json.dump(self.history_data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存历史记录失败：{str(e)}")
            return False

    def add_history_record(self, record_type, content, params=None):
        """添加历史记录"""
        record = {
            "id": len(self.history_data) + 1,
            "type": record_type,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "params": params if params else {},
            "content": content
        }
        self.history_data.append(record)
        self.save_history_data()
        self.load_history_to_list()

    def load_history_to_list(self):
        """加载历史记录到列表控件"""
        self.history_list.clear()
        for record in self.history_data:
            item_text = f"[{record['time']}] {record['type']}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, record)
            self.history_list.addItem(item)

    def show_history_detail(self, item):
        """展示选中记录的详情"""
        record = item.data(Qt.UserRole)
        if not record:
            return
        
        # 拼接详情文本
        detail = f"""
            📌 记录类型：{record['type']}
            🕒 生成时间：{record['time']}
            {"-"*50}
            """
        # 显示输入参数
        if record.get("params"):
            detail += "🔧 输入参数：\n"
            for k, v in record["params"].items():
                detail += f"  - {k}：{v}\n"
            detail += "\n" + "-"*50 + "\n"
        
        # 显示生成内容
        detail += f"📝 生成内容：\n{record['content']}"
        
        self.history_detail_title.setText(f"[{record['time']}] {record['type']}")
        self.history_detail_content.setText(detail)

    def delete_selected_history(self):
        """删除选中的历史记录"""
        current_item = self.history_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "提示", "请先选中要删除的记录！")
            return
        
        reply = QMessageBox.question(self, "确认", "是否确定删除该记录？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            record = current_item.data(Qt.UserRole)
            # 从列表中移除
            self.history_data = [r for r in self.history_data if r["id"] != record["id"]]
            # 重新分配ID
            for i, r in enumerate(self.history_data):
                r["id"] = i + 1
            self.save_history_data()
            self.load_history_to_list()
            self.history_detail_title.setText("选中记录查看详情")
            self.history_detail_content.clear()
            QMessageBox.information(self, "成功", "记录已删除！")

    def clear_all_history(self):
        """清空全部历史记录"""
        if not self.history_data:
            QMessageBox.warning(self, "提示", "暂无历史记录可清空！")
            return
        
        reply = QMessageBox.question(self, "确认", "是否确定清空所有历史记录？此操作不可恢复！", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.history_data = []
            self.save_history_data()
            self.load_history_to_list()
            self.history_detail_title.setText("选中记录查看详情")
            self.history_detail_content.clear()
            QMessageBox.information(self, "成功", "所有历史记录已清空！")

if __name__ == "__main__":
    # 确保中文显示正常
    QApplication.setStyle("Fusion")
    app = QApplication(sys.argv)
    font = QFont("幼圆")
    font.setPointSize(22)
    app.setFont(font)
    window = JobGuideApp()
    window.show()
    sys.exit(app.exec_())