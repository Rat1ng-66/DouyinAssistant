
import sys
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QMessageBox,
    QGroupBox,
    QGridLayout,
    QSpinBox,
    QCheckBox,
    QDockWidget,
    QComboBox,
)

from favorites_panel import FavoritesPanel

from browser_manager import (
    BrowserManager,
    validate_live_url,
)

from message_config import (
    load_config,
    save_config,
)

class DouyinAssistant(QMainWindow):

    def __init__(self):
        super().__init__()

        self.config = load_config()

        self.worker = None
        self.browser_running = False
        self.task_status = "stopped"
        self.closing = False
        self.current_room_name = ""

        self.init_ui()
        self.restore_config()
        self.update_buttons()

    def make_button(self, name, callback):
        button = QPushButton(name)
        button.clicked.connect(callback)
        return button

    def init_ui(self):
        self.setWindowTitle(
            "直播间弹幕助手 V0.4.6"
        )

        self.resize(1100, 900)
        self.setMinimumSize(850, 600)

        # 主界面添加滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        self.setCentralWidget(scroll)

        center = QWidget()
        scroll.setWidget(center)

        layout = QVBoxLayout(center)

        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)


        title = QLabel("直播间弹幕助手")
        title.setObjectName("mainTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Live Message Assistant | V0.4.6"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # 浏览器控制
        browser_group = QGroupBox("浏览器与直播间")
        browser_layout = QVBoxLayout(browser_group)

        self.browser_status = QLabel("● 未启动")

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "请输入抖音或虎牙直播间地址"
        )
        self.url_input.textChanged.connect(
            lambda _text: self.update_buttons()
        )

        browser_layout.addWidget(self.browser_status)
        browser_layout.addWidget(self.url_input)

        browser_buttons = QHBoxLayout()

        self.start_browser_button = self.make_button(
            "启动 Edge", self.start_browser
        )
        self.connect_button = self.make_button(
            "连接直播间", self.connect_room
        )
        self.stop_browser_button = self.make_button(
            "关闭 Edge", self.stop_browser
        )
        self.favorite_current_button = self.make_button(
            "收藏当前直播间", self.add_current_favorite
        )

        for button in (
            self.start_browser_button,
            self.connect_button,
            self.stop_browser_button,
            self.favorite_current_button,
        ):
            browser_buttons.addWidget(button)

        browser_layout.addLayout(browser_buttons)

        layout.addWidget(browser_group)

        # 当前直播间
        room_group = QGroupBox("当前直播间")
        room_layout = QHBoxLayout(room_group)

        self.anchor_label = QLabel("主播：未识别")
        self.page_label = QLabel("页面：未连接")

        self.page_label.setWordWrap(True)

        room_layout.addWidget(self.anchor_label)
        room_layout.addWidget(self.page_label, 1)

        layout.addWidget(room_group)

        # 弹幕管理
        message_group = QGroupBox("弹幕内容管理")
        message_layout = QVBoxLayout(message_group)

        tip = QLabel(
            "每行一条弹幕，按照顺序发送；"
            "到列表末尾后从第一条继续。"
        )
        tip.setObjectName("hintLabel")

        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText(
            "欢迎来到直播间！\n"
            "大家可以在评论区交流。\n"
            "感谢大家的支持！"
        )

        self.message_edit.setFixedHeight(190)

        self.message_edit.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        message_layout.setSpacing(12)

        message_layout.addWidget(tip)
        message_layout.addWidget(self.message_edit)

        self.message_count = QLabel("共 0 条弹幕")

        message_layout.addWidget(self.message_count)

        self.message_edit.textChanged.connect(
            self.update_message_count
        )

        layout.addWidget(message_group)

        # 发送设置
        settings_group = QGroupBox("定时发送设置")
        settings_layout = QGridLayout(settings_group)

        self.interval_spin = QSpinBox()

        # 允许 1～600 秒
        self.interval_spin.setRange(1, 600)

        # 每次点击箭头增加或减少 1 秒
        self.interval_spin.setSingleStep(1)

        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setValue(60)

        # 允许直接输入间隔
        self.interval_spin.setKeyboardTracking(False)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 20)
        self.limit_spin.setSuffix(" 条")

        settings_layout.addWidget(
            QLabel("发送间隔："), 0, 0
        )
        settings_layout.addWidget(
            self.interval_spin, 0, 1
        )

        settings_layout.addWidget(
            QLabel("本次最多发送："), 0, 2
        )
        settings_layout.addWidget(
            self.limit_spin, 0, 3
        )

        # V0.4.6: 可选择按条数或按时长结束任务
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("按条数结束", "count")
        self.mode_combo.addItem("按时长结束", "duration")

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 525600)
        self.duration_spin.setValue(5)
        self.duration_spin.setKeyboardTracking(False)

        self.duration_unit = QComboBox()
        self.duration_unit.addItem("分钟", 60)
        self.duration_unit.addItem("小时", 3600)
        self.duration_unit.addItem("天", 86400)

        settings_layout.addWidget(QLabel("任务结束方式："), 1, 0)
        settings_layout.addWidget(self.mode_combo, 1, 1)
        settings_layout.addWidget(QLabel("运行时长："), 1, 2)

        duration_row = QHBoxLayout()
        duration_row.addWidget(self.duration_spin)
        duration_row.addWidget(self.duration_unit)
        settings_layout.addLayout(duration_row, 1, 3)

        self.duration_hint = QLabel(
            "持续模式到时自动停止；暂停期间不计时，最长365天。"
        )
        self.duration_hint.setWordWrap(True)
        settings_layout.addWidget(self.duration_hint, 2, 0, 1, 4)

        self.mode_combo.currentIndexChanged.connect(
            self.update_mode_fields
        )
        self.duration_unit.currentIndexChanged.connect(
            self.update_duration_unit
        )
        self.update_mode_fields()

        layout.addWidget(settings_group)

        # 使用确认
        self.authorization_check = QCheckBox(
            "我确认已获准在当前直播间发送这些消息，"
            "并会遵守直播间和平台规则"
        )

        layout.addWidget(self.authorization_check)

        # 发送操作
        task_group = QGroupBox("弹幕发送控制")
        task_layout = QVBoxLayout(task_group)

        task_buttons = QHBoxLayout()

        self.start_task_button = self.make_button(
            "开始发送", self.start_task
        )
        self.pause_task_button = self.make_button(
            "暂停", self.pause_task
        )
        self.resume_task_button = self.make_button(
            "继续", self.resume_task
        )
        self.stop_task_button = self.make_button(
            "停止发送", self.stop_task
        )

        task_buttons.addWidget(self.start_task_button)
        task_buttons.addWidget(self.pause_task_button)
        task_buttons.addWidget(self.resume_task_button)
        task_buttons.addWidget(self.stop_task_button)

        task_layout.addLayout(task_buttons)

        self.task_status_label = QLabel(
            "发送状态：未启动"
        )

        self.task_count_label = QLabel(
            "尝试提交：0 条 | 已执行提交：0 条"
        )

        task_layout.addWidget(self.task_status_label)
        task_layout.addWidget(self.task_count_label)

        layout.addWidget(task_group)

        # 日志
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        self.log_output.setMinimumHeight(220)

        self.log_output.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        clear_button = self.make_button(
            "清空日志", self.log_output.clear
        )

        log_layout.addWidget(self.log_output)
        log_layout.addWidget(clear_button)

        layout.addWidget(log_group)

        # 收藏面板是 QMainWindow 的右侧停靠面板；
        # 不依赖浏览器进程已经启动。
        self.favorites_panel = FavoritesPanel(self)
        self.favorites_dock = QDockWidget("收藏直播间", self)
        self.favorites_dock.setObjectName("favoritesDock")
        self.favorites_dock.setWidget(self.favorites_panel)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self.favorites_dock
        )
        self.favorites_panel.room_selected.connect(
            self.open_favorite_room
        )

        self.apply_style()

        self.add_log("弹幕助手 V0.4.6 已启动")
        self.add_log("请先启动 Edge 并连接直播间")

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #F5F7FB;
            }

            QWidget {
                font-family: "Microsoft YaHei";
                font-size: 13px;
                color: #243247;
            }

            QLabel#mainTitle {
                font-size: 26px;
                font-weight: bold;
                color: #18283B;
            }

            QLabel#subtitle {
                font-size: 12px;
                color: #8491A5;
            }

            QLabel#hintLabel {
                color: #64748B;
                font-size: 12px;
            }

            QGroupBox {
                background: white;
                border: 1px solid #E0E5EE;
                border-radius: 9px;
                margin-top: 12px;
                padding: 13px;
                font-weight: bold;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 5px;
            }

            QLineEdit, QSpinBox {
                padding: 8px;
                border: 1px solid #D6DFEB;
                border-radius: 6px;
                background: white;
            }

            QTextEdit {
                border: 1px solid #D6DFEB;
                border-radius: 6px;
                padding: 8px;
                background: white;
            }

            QPushButton {
                padding: 10px 12px;
                border-radius: 6px;
                background: #E8EDF5;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #D7E0ED;
            }

            QPushButton:disabled {
                background: #EDF0F3;
                color: #9CA3AF;
            }

            QPushButton {
                min-height: 24px;
            }

            QTextEdit[readOnly="true"] {
                background: #111827;
                color: #D1FAE5;
                border: none;
                font-family: Consolas;
                font-size: 12px;
            }
        """)

    def update_duration_unit(self):
        old = self.duration_spin.value()
        unit_seconds = self.duration_unit.currentData()
        maximum = 31536000 // unit_seconds
        self.duration_spin.setMaximum(maximum)
        self.duration_spin.setValue(min(old, maximum))

    def update_mode_fields(self):
        duration_mode = self.mode_combo.currentData() == "duration"
        self.limit_spin.setEnabled(not duration_mode)
        self.duration_spin.setEnabled(duration_mode)
        self.duration_unit.setEnabled(duration_mode)

    def restore_config(self):
        config = self.config

        self.message_edit.setPlainText(
            "\n".join(config["messages"])
        )

        self.interval_spin.setValue(
            config["interval"]
        )

        self.limit_spin.setValue(
            config["limit"]
        )

        self.url_input.setText(
            config["room_url"]
        )

        mode = config.get("task_mode", "count")
        self.mode_combo.setCurrentIndex(1 if mode == "duration" else 0)

        unit_seconds = int(config.get("duration_unit_seconds", 60))
        unit_index = self.duration_unit.findData(unit_seconds)
        self.duration_unit.setCurrentIndex(
            unit_index if unit_index >= 0 else 0
        )
        self.update_duration_unit()
        self.duration_spin.setValue(
            int(config.get("duration_value", 5))
        )
        self.update_mode_fields()
        self.update_message_count()

    def save_current_config(self):
        messages = [
            line.strip()
            for line in self.message_edit.toPlainText().splitlines()
            if line.strip()
        ]

        config = {
            "messages": messages,
            "interval": self.interval_spin.value(),
            "limit": self.limit_spin.value(),
            "room_url": self.url_input.text().strip(),
            "task_mode": self.mode_combo.currentData(),
            "duration_value": self.duration_spin.value(),
            "duration_unit_seconds": self.duration_unit.currentData(),
        }

        try:
            save_config(config)
        except OSError as exc:
            self.add_log(f"配置保存失败：{exc}")

    def update_message_count(self):
        messages = [
            line for line in
            self.message_edit.toPlainText().splitlines()
            if line.strip()
        ]

        self.message_count.setText(
            f"共 {len(messages)} 条弹幕"
        )

    def add_log(self, message):
        timestamp = datetime.now().strftime(
            "%H:%M:%S"
        )

        self.log_output.append(
            f"[{timestamp}] {message}"
        )

    def update_browser_status(self, status):
        self.browser_status.setText(
            "● " + status
        )

    def update_buttons(self):
        active = (
            self.worker is not None
            and self.worker.isRunning()
        )

        idle = not active and not self.closing

        self.start_browser_button.setEnabled(idle)

        self.connect_button.setEnabled(
            self.browser_running
            and self.task_status not in ("running", "paused")
        )

        self.stop_browser_button.setEnabled(
            active and not self.closing
        )

        self.favorite_current_button.setEnabled(
            bool(self.url_input.text().strip()) and not self.closing
        )

        stopped = self.task_status in (
            "stopped", "completed"
        )

        self.start_task_button.setEnabled(
            self.browser_running and stopped
            and not self.closing
        )

        self.pause_task_button.setEnabled(
            self.task_status == "running"
        )

        self.resume_task_button.setEnabled(
            self.task_status == "paused"
        )

        self.stop_task_button.setEnabled(
            self.task_status in ("running", "paused")
        )

    def start_browser(self):
        if self.worker is not None and self.worker.isRunning():
            return

        self.browser_running = False
        self.update_browser_status("启动中")

        worker = BrowserManager(self)
        self.worker = worker

        worker.log_signal.connect(self.add_log)
        worker.status_signal.connect(
            self.update_browser_status
        )
        worker.browser_ready.connect(
            self.on_browser_ready
        )
        worker.room_info_signal.connect(
            self.update_room_info
        )
        worker.error_signal.connect(
            self.on_browser_error
        )
        worker.task_signal.connect(
            self.update_task_status
        )
        worker.finished.connect(
            self.on_browser_finished
        )

        worker.start()
        self.update_buttons()

    def on_browser_ready(self):
        self.browser_running = True
        self.add_log("浏览器已经启动")

        if self.closing:
            self.worker.stop_browser()

        self.update_buttons()

    def connect_room(self):
        if not self.browser_running:
            QMessageBox.warning(
                self, "提示", "请先启动 Edge"
            )
            return

        try:
            url = validate_live_url(
                self.url_input.text()
            )
        except ValueError as exc:
            QMessageBox.warning(
                self, "地址错误", str(exc)
            )
            return

        self.url_input.setText(url)
        self.worker.open_live_room(url)

        self.add_log("正在连接：" + url)
        self.save_current_config()

    def update_room_info(self, info):
        self.current_room_name = info.get("anchor", "") or ""
        self.anchor_label.setText(
            "主播：" + info.get("anchor", "未识别")
        )

        self.page_label.setText(
            "页面：" + info.get("title", "未识别")
        )

    def add_current_favorite(self):
        """收藏当前输入框的直播间链接，不要求 Edge 已启动。"""
        url = self.url_input.text().strip()
        try:
            url = validate_live_url(url)
        except ValueError as exc:
            QMessageBox.warning(self, "地址错误", str(exc))
            return

        name = self.current_room_name
        if name in ("", "未识别"):
            name = ""

        self.favorites_panel.set_current_room(url, name)
        self.favorites_panel.add_favorite()
        self.add_log("已提交收藏请求：" + url)

    def open_favorite_room(self, url):
        """收藏列表双击：填写网址，若浏览器运行则直接进入。"""
        self.url_input.setText(url)
        self.current_room_name = ""
        self.save_current_config()

        if self.browser_running and self.worker is not None:
            if self.task_status in ("running", "paused"):
                QMessageBox.information(
                    self, "发送任务进行中",
                    "请先停止当前发送任务，再切换直播间。"
                )
                return
            self.connect_room()
        else:
            self.add_log("已从收藏载入直播间，请先启动 Edge，再连接直播间")
            QMessageBox.information(
                self, "收藏已载入",
                "直播间地址已填入。请先点击“启动 Edge”，再点击“连接直播间”。"
            )

    def start_task(self):
        if not self.browser_running:
            QMessageBox.warning(
                self, "提示", "请先连接直播间"
            )
            return

        if not self.authorization_check.isChecked():
            QMessageBox.warning(
                self,
                "使用确认",
                "请先确认你有权在该直播间发送消息。"
            )
            return

        messages = [
            line.strip()
            for line in self.message_edit.toPlainText().splitlines()
            if line.strip()
        ]

        if not messages:
            QMessageBox.warning(
                self, "提示", "请先填写弹幕内容"
            )
            return

        if len(messages) > 100:
            QMessageBox.warning(
                self, "提示", "最多填写 100 条弹幕"
            )
            return

        self.save_current_config()

        mode = self.mode_combo.currentData()
        duration_seconds = (
            self.duration_spin.value() * self.duration_unit.currentData()
        )
        if mode == "duration":
            ending_info = (
                f"运行时长：{self.duration_spin.value()}"
                f"{self.duration_unit.currentText()}（暂停不计时）"
            )
        else:
            ending_info = f"发送上限：{self.limit_spin.value()} 条"

        reply = QMessageBox.question(
            self,
            "确认开始发送",
            f"即将在当前直播间提交弹幕。\n\n"
            f"弹幕内容：{len(messages)} 条\n"
            f"发送间隔：{self.interval_spin.value()} 秒\n"
            f"{ending_info}\n\n"
            "确认开始吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.worker.start_messages(
            messages,
            self.interval_spin.value(),
            self.limit_spin.value(),
            mode=mode,
            duration_seconds=duration_seconds,
        )

        self.task_status = "running"
        self.task_status_label.setText(
            "发送状态：准备启动"
        )

        self.update_buttons()

    def pause_task(self):
        if self.worker:
            self.worker.pause_messages()

    def resume_task(self):
        if self.worker:
            self.worker.resume_messages()

    def stop_task(self):
        if self.worker:
            self.worker.stop_messages()
            self.stop_task_button.setEnabled(False)

    def update_task_status(self, data):
        status = data.get("status", "stopped")

        self.task_status = status

        names = {
            "running": "发送中",
            "paused": "已暂停",
            "stopped": "已停止",
            "completed": "任务已达到结束条件",
        }

        self.task_status_label.setText(
            "发送状态：" + names.get(status, status)
        )

        attempted = data.get("attempted", 0)
        confirmed = data.get("confirmed", 0)

        self.task_count_label.setText(
            f"尝试提交：{attempted} 条 | "
            f"已执行提交：{confirmed} 条"
        )

        if data.get("message"):
            self.add_log(data["message"])

        self.update_buttons()

    def stop_browser(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop_browser()
            self.browser_running = False
            self.update_browser_status("关闭中")
            self.update_buttons()

    def on_browser_error(self, message):
        self.add_log("错误：" + message)

    def on_browser_finished(self):
        self.browser_running = False
        self.task_status = "stopped"

        self.update_browser_status("未启动")
        self.update_buttons()

        if self.closing:
            self.close()
        else:
            self.add_log("浏览器已停止")

    def closeEvent(self, event):
        self.save_current_config()

        if self.worker and self.worker.isRunning():
            event.ignore()

            if not self.closing:
                self.closing = True
                self.add_log("正在关闭浏览器...")
                self.worker.stop_browser()
                self.update_buttons()

            return

        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setFont(
        QFont("Microsoft YaHei", 10)
    )

    window = DouyinAssistant()
    window.show()

    sys.exit(app.exec())
import sys
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QMessageBox,
    QGroupBox,
    QGridLayout,
    QSpinBox,
    QCheckBox,
    QDockWidget,
    QComboBox,
)

from favorites_panel import FavoritesPanel

from browser_manager import (
    BrowserManager,
    validate_live_url,
)

from message_config import (
    load_config,
    save_config,
)

class DouyinAssistant(QMainWindow):

    def __init__(self):
        super().__init__()

        self.config = load_config()

        self.worker = None
        self.browser_running = False
        self.task_status = "stopped"
        self.closing = False
        self.current_room_name = ""

        self.init_ui()
        self.restore_config()
        self.update_buttons()

    def make_button(self, name, callback):
        button = QPushButton(name)
        button.clicked.connect(callback)
        return button

    def init_ui(self):
        self.setWindowTitle(
            "直播间弹幕助手 V0.4.7"
        )

        self.resize(1100, 900)
        self.setMinimumSize(850, 600)

        # 主界面添加滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)

        self.setCentralWidget(scroll)

        center = QWidget()
        scroll.setWidget(center)

        layout = QVBoxLayout(center)

        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(16)


        title = QLabel("直播间弹幕助手")
        title.setObjectName("mainTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Live Message Assistant | V0.4.7"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # 浏览器控制
        browser_group = QGroupBox("浏览器与直播间")
        browser_layout = QVBoxLayout(browser_group)

        self.browser_status = QLabel("● 未启动")

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "请输入抖音或虎牙直播间地址"
        )
        self.url_input.textChanged.connect(
            lambda _text: self.update_buttons()
        )

        browser_layout.addWidget(self.browser_status)
        browser_layout.addWidget(self.url_input)

        browser_buttons = QHBoxLayout()

        self.start_browser_button = self.make_button(
            "启动 Edge", self.start_browser
        )
        self.connect_button = self.make_button(
            "连接直播间", self.connect_room
        )
        self.stop_browser_button = self.make_button(
            "关闭 Edge", self.stop_browser
        )
        self.favorite_current_button = self.make_button(
            "收藏当前直播间", self.add_current_favorite
        )

        for button in (
            self.start_browser_button,
            self.connect_button,
            self.stop_browser_button,
            self.favorite_current_button,
        ):
            browser_buttons.addWidget(button)

        browser_layout.addLayout(browser_buttons)

        layout.addWidget(browser_group)

        # 当前直播间
        room_group = QGroupBox("当前直播间")
        room_layout = QHBoxLayout(room_group)

        self.anchor_label = QLabel("主播：未识别")
        self.page_label = QLabel("页面：未连接")

        self.page_label.setWordWrap(True)

        room_layout.addWidget(self.anchor_label)
        room_layout.addWidget(self.page_label, 1)

        layout.addWidget(room_group)

        # 弹幕管理
        message_group = QGroupBox("弹幕内容管理")
        message_layout = QVBoxLayout(message_group)

        tip = QLabel(
            "每行一条弹幕，按照顺序发送；"
            "到列表末尾后从第一条继续。"
        )
        tip.setObjectName("hintLabel")

        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText(
            "欢迎来到直播间！\n"
            "大家可以在评论区交流。\n"
            "感谢大家的支持！"
        )

        self.message_edit.setFixedHeight(190)

        self.message_edit.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        message_layout.setSpacing(12)

        message_layout.addWidget(tip)
        message_layout.addWidget(self.message_edit)

        self.message_count = QLabel("共 0 条弹幕")

        message_layout.addWidget(self.message_count)

        self.message_edit.textChanged.connect(
            self.update_message_count
        )

        layout.addWidget(message_group)

        # 发送设置
        settings_group = QGroupBox("定时发送设置")
        settings_layout = QGridLayout(settings_group)

        self.interval_spin = QSpinBox()

        # 允许 1～600 秒
        self.interval_spin.setRange(1, 600)

        # 每次点击箭头增加或减少 1 秒
        self.interval_spin.setSingleStep(1)

        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setValue(60)

        # 允许直接输入间隔
        self.interval_spin.setKeyboardTracking(False)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 20)
        self.limit_spin.setSuffix(" 条")

        settings_layout.addWidget(
            QLabel("发送间隔："), 0, 0
        )
        settings_layout.addWidget(
            self.interval_spin, 0, 1
        )

        settings_layout.addWidget(
            QLabel("本次最多发送："), 0, 2
        )
        settings_layout.addWidget(
            self.limit_spin, 0, 3
        )

        # V0.4.6: 可选择按条数或按时长结束任务
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("按条数结束", "count")
        self.mode_combo.addItem("按时长结束", "duration")

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 525600)
        self.duration_spin.setValue(5)
        self.duration_spin.setKeyboardTracking(False)

        self.duration_unit = QComboBox()
        self.duration_unit.addItem("分钟", 60)
        self.duration_unit.addItem("小时", 3600)
        self.duration_unit.addItem("天", 86400)

        settings_layout.addWidget(QLabel("任务结束方式："), 1, 0)
        settings_layout.addWidget(self.mode_combo, 1, 1)
        settings_layout.addWidget(QLabel("运行时长："), 1, 2)

        duration_row = QHBoxLayout()
        duration_row.addWidget(self.duration_spin)
        duration_row.addWidget(self.duration_unit)
        settings_layout.addLayout(duration_row, 1, 3)

        self.duration_hint = QLabel(
            "到时自动结束；暂停期间不计时，最长365天。"
            "检测到停播或直播状态持续无法确认时提前停止。"
        )
        self.duration_hint.setWordWrap(True)
        settings_layout.addWidget(self.duration_hint, 2, 0, 1, 4)

        self.mode_combo.currentIndexChanged.connect(
            self.update_mode_fields
        )
        self.duration_unit.currentIndexChanged.connect(
            self.update_duration_unit
        )
        self.update_mode_fields()

        layout.addWidget(settings_group)

        # 使用确认
        self.authorization_check = QCheckBox(
            "我确认已获准在当前直播间发送这些消息，"
            "并会遵守直播间和平台规则"
        )

        layout.addWidget(self.authorization_check)

        # 发送操作
        task_group = QGroupBox("弹幕发送控制")
        task_layout = QVBoxLayout(task_group)

        task_buttons = QHBoxLayout()

        self.start_task_button = self.make_button(
            "开始发送", self.start_task
        )
        self.pause_task_button = self.make_button(
            "暂停", self.pause_task
        )
        self.resume_task_button = self.make_button(
            "继续", self.resume_task
        )
        self.stop_task_button = self.make_button(
            "停止发送", self.stop_task
        )

        task_buttons.addWidget(self.start_task_button)
        task_buttons.addWidget(self.pause_task_button)
        task_buttons.addWidget(self.resume_task_button)
        task_buttons.addWidget(self.stop_task_button)

        task_layout.addLayout(task_buttons)

        self.task_status_label = QLabel(
            "发送状态：未启动"
        )

        self.task_count_label = QLabel(
            "尝试提交：0 条 | 已执行提交：0 条"
        )

        task_layout.addWidget(self.task_status_label)
        task_layout.addWidget(self.task_count_label)

        layout.addWidget(task_group)

        # 日志
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        self.log_output.setMinimumHeight(220)

        self.log_output.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )

        clear_button = self.make_button(
            "清空日志", self.log_output.clear
        )

        log_layout.addWidget(self.log_output)
        log_layout.addWidget(clear_button)

        layout.addWidget(log_group)

        # 收藏面板是 QMainWindow 的右侧停靠面板；
        # 不依赖浏览器进程已经启动。
        self.favorites_panel = FavoritesPanel(self)
        self.favorites_dock = QDockWidget("收藏直播间", self)
        self.favorites_dock.setObjectName("favoritesDock")
        self.favorites_dock.setWidget(self.favorites_panel)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self.favorites_dock
        )
        self.favorites_panel.room_selected.connect(
            self.open_favorite_room
        )

        self.apply_style()

        self.add_log("弹幕助手 V0.4.7 已启动（停播自动停止保护）")
        self.add_log("请先启动 Edge 并连接直播间")

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #F5F7FB;
            }

            QWidget {
                font-family: "Microsoft YaHei";
                font-size: 13px;
                color: #243247;
            }

            QLabel#mainTitle {
                font-size: 26px;
                font-weight: bold;
                color: #18283B;
            }

            QLabel#subtitle {
                font-size: 12px;
                color: #8491A5;
            }

            QLabel#hintLabel {
                color: #64748B;
                font-size: 12px;
            }

            QGroupBox {
                background: white;
                border: 1px solid #E0E5EE;
                border-radius: 9px;
                margin-top: 12px;
                padding: 13px;
                font-weight: bold;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 5px;
            }

            QLineEdit, QSpinBox {
                padding: 8px;
                border: 1px solid #D6DFEB;
                border-radius: 6px;
                background: white;
            }

            QTextEdit {
                border: 1px solid #D6DFEB;
                border-radius: 6px;
                padding: 8px;
                background: white;
            }

            QPushButton {
                padding: 10px 12px;
                border-radius: 6px;
                background: #E8EDF5;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #D7E0ED;
            }

            QPushButton:disabled {
                background: #EDF0F3;
                color: #9CA3AF;
            }

            QPushButton {
                min-height: 24px;
            }

            QTextEdit[readOnly="true"] {
                background: #111827;
                color: #D1FAE5;
                border: none;
                font-family: Consolas;
                font-size: 12px;
            }
        """)

    def update_duration_unit(self):
        old = self.duration_spin.value()
        unit_seconds = self.duration_unit.currentData()
        maximum = 31536000 // unit_seconds
        self.duration_spin.setMaximum(maximum)
        self.duration_spin.setValue(min(old, maximum))

    def update_mode_fields(self):
        duration_mode = self.mode_combo.currentData() == "duration"
        self.limit_spin.setEnabled(not duration_mode)
        self.duration_spin.setEnabled(duration_mode)
        self.duration_unit.setEnabled(duration_mode)

    def restore_config(self):
        config = self.config

        self.message_edit.setPlainText(
            "\n".join(config["messages"])
        )

        self.interval_spin.setValue(
            config["interval"]
        )

        self.limit_spin.setValue(
            config["limit"]
        )

        self.url_input.setText(
            config["room_url"]
        )

        mode = config.get("task_mode", "count")
        self.mode_combo.setCurrentIndex(1 if mode == "duration" else 0)

        unit_seconds = int(config.get("duration_unit_seconds", 60))
        unit_index = self.duration_unit.findData(unit_seconds)
        self.duration_unit.setCurrentIndex(
            unit_index if unit_index >= 0 else 0
        )
        self.update_duration_unit()
        self.duration_spin.setValue(
            int(config.get("duration_value", 5))
        )
        self.update_mode_fields()
        self.update_message_count()

    def save_current_config(self):
        messages = [
            line.strip()
            for line in self.message_edit.toPlainText().splitlines()
            if line.strip()
        ]

        config = {
            "messages": messages,
            "interval": self.interval_spin.value(),
            "limit": self.limit_spin.value(),
            "room_url": self.url_input.text().strip(),
            "task_mode": self.mode_combo.currentData(),
            "duration_value": self.duration_spin.value(),
            "duration_unit_seconds": self.duration_unit.currentData(),
        }

        try:
            save_config(config)
        except OSError as exc:
            self.add_log(f"配置保存失败：{exc}")

    def update_message_count(self):
        messages = [
            line for line in
            self.message_edit.toPlainText().splitlines()
            if line.strip()
        ]

        self.message_count.setText(
            f"共 {len(messages)} 条弹幕"
        )

    def add_log(self, message):
        timestamp = datetime.now().strftime(
            "%H:%M:%S"
        )

        self.log_output.append(
            f"[{timestamp}] {message}"
        )

    def update_browser_status(self, status):
        self.browser_status.setText(
            "● " + status
        )

    def update_buttons(self):
        active = (
            self.worker is not None
            and self.worker.isRunning()
        )

        idle = not active and not self.closing

        self.start_browser_button.setEnabled(idle)

        self.connect_button.setEnabled(
            self.browser_running
            and self.task_status not in ("running", "paused")
        )

        self.stop_browser_button.setEnabled(
            active and not self.closing
        )

        self.favorite_current_button.setEnabled(
            bool(self.url_input.text().strip()) and not self.closing
        )

        stopped = self.task_status in (
            "stopped", "completed"
        )

        self.start_task_button.setEnabled(
            self.browser_running and stopped
            and not self.closing
        )

        self.pause_task_button.setEnabled(
            self.task_status == "running"
        )

        self.resume_task_button.setEnabled(
            self.task_status == "paused"
        )

        self.stop_task_button.setEnabled(
            self.task_status in ("running", "paused")
        )

    def start_browser(self):
        if self.worker is not None and self.worker.isRunning():
            return

        self.browser_running = False
        self.update_browser_status("启动中")

        worker = BrowserManager(self)
        self.worker = worker

        worker.log_signal.connect(self.add_log)
        worker.status_signal.connect(
            self.update_browser_status
        )
        worker.browser_ready.connect(
            self.on_browser_ready
        )
        worker.room_info_signal.connect(
            self.update_room_info
        )
        worker.error_signal.connect(
            self.on_browser_error
        )
        worker.task_signal.connect(
            self.update_task_status
        )
        worker.finished.connect(
            self.on_browser_finished
        )

        worker.start()
        self.update_buttons()

    def on_browser_ready(self):
        self.browser_running = True
        self.add_log("浏览器已经启动")

        if self.closing:
            self.worker.stop_browser()

        self.update_buttons()

    def connect_room(self):
        if not self.browser_running:
            QMessageBox.warning(
                self, "提示", "请先启动 Edge"
            )
            return

        try:
            url = validate_live_url(
                self.url_input.text()
            )
        except ValueError as exc:
            QMessageBox.warning(
                self, "地址错误", str(exc)
            )
            return

        self.url_input.setText(url)
        self.worker.open_live_room(url)

        self.add_log("正在连接：" + url)
        self.save_current_config()

    def update_room_info(self, info):
        self.current_room_name = info.get("anchor", "") or ""
        self.anchor_label.setText(
            "主播：" + info.get("anchor", "未识别")
        )

        self.page_label.setText(
            "页面：" + info.get("title", "未识别")
        )

    def add_current_favorite(self):
        """收藏当前输入框的直播间链接，不要求 Edge 已启动。"""
        url = self.url_input.text().strip()
        try:
            url = validate_live_url(url)
        except ValueError as exc:
            QMessageBox.warning(self, "地址错误", str(exc))
            return

        name = self.current_room_name
        if name in ("", "未识别"):
            name = ""

        self.favorites_panel.set_current_room(url, name)
        self.favorites_panel.add_favorite()
        self.add_log("已提交收藏请求：" + url)

    def open_favorite_room(self, url):
        """收藏列表双击：填写网址，若浏览器运行则直接进入。"""
        self.url_input.setText(url)
        self.current_room_name = ""
        self.save_current_config()

        if self.browser_running and self.worker is not None:
            if self.task_status in ("running", "paused"):
                QMessageBox.information(
                    self, "发送任务进行中",
                    "请先停止当前发送任务，再切换直播间。"
                )
                return
            self.connect_room()
        else:
            self.add_log("已从收藏载入直播间，请先启动 Edge，再连接直播间")
            QMessageBox.information(
                self, "收藏已载入",
                "直播间地址已填入。请先点击“启动 Edge”，再点击“连接直播间”。"
            )

    def start_task(self):
        if not self.browser_running:
            QMessageBox.warning(
                self, "提示", "请先连接直播间"
            )
            return

        if not self.authorization_check.isChecked():
            QMessageBox.warning(
                self,
                "使用确认",
                "请先确认你有权在该直播间发送消息。"
            )
            return

        messages = [
            line.strip()
            for line in self.message_edit.toPlainText().splitlines()
            if line.strip()
        ]

        if not messages:
            QMessageBox.warning(
                self, "提示", "请先填写弹幕内容"
            )
            return

        if len(messages) > 100:
            QMessageBox.warning(
                self, "提示", "最多填写 100 条弹幕"
            )
            return

        self.save_current_config()

        mode = self.mode_combo.currentData()
        duration_seconds = (
            self.duration_spin.value() * self.duration_unit.currentData()
        )
        if mode == "duration":
            ending_info = (
                f"运行时长：{self.duration_spin.value()}"
                f"{self.duration_unit.currentText()}（暂停不计时）"
            )
        else:
            ending_info = f"发送上限：{self.limit_spin.value()} 条"

        reply = QMessageBox.question(
            self,
            "确认开始发送",
            f"即将在当前直播间提交弹幕。\n\n"
            f"弹幕内容：{len(messages)} 条\n"
            f"发送间隔：{self.interval_spin.value()} 秒\n"
            f"{ending_info}\n\n"
            "确认开始吗？",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self.worker.start_messages(
            messages,
            self.interval_spin.value(),
            self.limit_spin.value(),
            mode=mode,
            duration_seconds=duration_seconds,
        )

        self.task_status = "running"
        self.task_status_label.setText(
            "发送状态：准备启动"
        )

        self.update_buttons()

    def pause_task(self):
        if self.worker:
            self.worker.pause_messages()

    def resume_task(self):
        if self.worker:
            self.worker.resume_messages()

    def stop_task(self):
        if self.worker:
            self.worker.stop_messages()
            self.stop_task_button.setEnabled(False)

    def update_task_status(self, data):
        status = data.get("status", "stopped")

        self.task_status = status

        names = {
            "running": "发送中",
            "paused": "已暂停",
            "stopped": "已停止",
            "completed": "任务已达到结束条件",
        }

        self.task_status_label.setText(
            "发送状态：" + names.get(status, status)
        )

        attempted = data.get("attempted", 0)
        confirmed = data.get("confirmed", 0)

        self.task_count_label.setText(
            f"尝试提交：{attempted} 条 | "
            f"已执行提交：{confirmed} 条"
        )

        if data.get("message"):
            self.add_log(data["message"])

        self.update_buttons()

    def stop_browser(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop_browser()
            self.browser_running = False
            self.update_browser_status("关闭中")
            self.update_buttons()

    def on_browser_error(self, message):
        self.add_log("错误：" + message)

    def on_browser_finished(self):
        self.browser_running = False
        self.task_status = "stopped"

        self.update_browser_status("未启动")
        self.update_buttons()

        if self.closing:
            self.close()
        else:
            self.add_log("浏览器已停止")

    def closeEvent(self, event):
        self.save_current_config()

        if self.worker and self.worker.isRunning():
            event.ignore()

            if not self.closing:
                self.closing = True
                self.add_log("正在关闭浏览器...")
                self.worker.stop_browser()
                self.update_buttons()

            return

        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setFont(
        QFont("Microsoft YaHei", 10)
    )

    window = DouyinAssistant()
    window.show()

    sys.exit(app.exec())