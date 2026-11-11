
import sys
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
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
    QFrame,
    QScrollArea,
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

        self.resize(1180, 900)
        self.setMinimumSize(980, 760)

        page = QWidget()
        page.setObjectName("page")
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        self.setCentralWidget(scroll)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(2)

        title = QLabel("直播间弹幕助手")
        title.setObjectName("mainTitle")

        subtitle = QLabel("连接直播间后，按列表顺序发送已确认的弹幕")
        subtitle.setObjectName("subtitle")

        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()

        self.browser_status = QLabel("未启动")
        self.browser_status.setObjectName("statusPill")
        header.addWidget(self.browser_status, 0, Qt.AlignVCenter)
        layout.addLayout(header)

        browser_card = QWidget()
        browser_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        browser_outer = QVBoxLayout(browser_card)
        browser_outer.setContentsMargins(0, 0, 0, 0)
        browser_outer.setSpacing(8)
        browser_title = QLabel("直播间")
        browser_title.setObjectName("cardTitle")
        browser_outer.addWidget(browser_title)

        browser_group = QFrame()
        browser_group.setObjectName("cardBody")
        browser_group.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        browser_layout = QVBoxLayout(browser_group)
        browser_layout.setContentsMargins(14, 14, 14, 14)
        browser_layout.setSpacing(12)

        url_label = QLabel("直播间地址")
        url_label.setObjectName("fieldLabel")
        self.url_input = QLineEdit()
        self.url_input.setObjectName("roomUrl")
        self.url_input.setPlaceholderText(
            "https://live.douyin.com/房间号  或  https://www.huya.com/房间号"
        )
        self.url_input.setFixedHeight(36)
        self.url_input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.url_input.textChanged.connect(
            lambda _text: self.update_buttons()
        )
        browser_layout.addWidget(url_label)
        browser_layout.addWidget(self.url_input)

        browser_buttons = QHBoxLayout()
        browser_buttons.setSpacing(8)

        self.start_browser_button = self.make_button(
            "启动 Edge", self.start_browser
        )
        self.connect_button = self.make_button(
            "连接直播间", self.connect_room
        )
        self.favorite_current_button = self.make_button(
            "收藏当前直播间", self.add_current_favorite
        )
        self.stop_browser_button = self.make_button(
            "关闭 Edge", self.stop_browser
        )
        self.start_browser_button.setObjectName("primaryButton")
        self.connect_button.setObjectName("accentButton")
        self.stop_browser_button.setObjectName("dangerButton")

        browser_buttons.addWidget(self.start_browser_button)
        browser_buttons.addWidget(self.connect_button)
        browser_buttons.addWidget(self.favorite_current_button)
        browser_buttons.addStretch()
        browser_buttons.addWidget(self.stop_browser_button)
        for button in (
            self.start_browser_button,
            self.connect_button,
            self.favorite_current_button,
            self.stop_browser_button,
        ):
            button.setFixedHeight(34)
        browser_layout.addLayout(browser_buttons)

        room_line = QHBoxLayout()
        room_line.setSpacing(8)
        anchor_caption = QLabel("主播")
        page_caption = QLabel("页面")
        anchor_caption.setObjectName("fieldLabel")
        page_caption.setObjectName("fieldLabel")
        self.anchor_label = QLabel("未识别")
        self.page_label = QLabel("未连接")
        self.anchor_label.setObjectName("roomValue")
        self.page_label.setObjectName("roomValue")
        self.anchor_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        self.page_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        room_line.addWidget(anchor_caption)
        room_line.addWidget(self.anchor_label)
        room_line.addSpacing(16)
        room_line.addWidget(page_caption)
        room_line.addWidget(self.page_label, 1)
        browser_layout.addLayout(room_line)
        browser_outer.addWidget(browser_group)
        browser_card.setMinimumHeight(
            browser_outer.sizeHint().height()
        )
        layout.addWidget(browser_card)

        message_group = QGroupBox("弹幕")
        message_layout = QVBoxLayout(message_group)
        message_layout.setContentsMargins(8, 12, 8, 8)
        message_layout.setSpacing(8)

        tip = QLabel("每行一条，按顺序循环发送")
        tip.setObjectName("hintLabel")

        self.message_edit = QTextEdit()
        self.message_edit.setPlaceholderText(
            "欢迎来到直播间！\n"
            "大家可以在评论区交流。\n"
            "感谢大家的支持！"
        )
        self.message_edit.setFixedHeight(120)
        self.message_edit.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        self.message_count = QLabel("共 0 条弹幕")
        self.message_count.setObjectName("hintLabel")
        message_head = QHBoxLayout()
        message_head.addWidget(tip)
        message_head.addStretch()
        message_head.addWidget(self.message_count)
        message_layout.addLayout(message_head)
        message_layout.addWidget(self.message_edit)
        self.message_edit.textChanged.connect(
            self.update_message_count
        )
        layout.addWidget(message_group)

        settings_group = QGroupBox("发送设置")
        settings_layout = QGridLayout(settings_group)
        settings_layout.setContentsMargins(8, 12, 8, 8)
        settings_layout.setHorizontalSpacing(12)
        settings_layout.setVerticalSpacing(8)
        settings_layout.setColumnStretch(1, 1)
        settings_layout.setColumnStretch(3, 1)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 600)
        self.interval_spin.setSingleStep(1)
        self.interval_spin.setSuffix(" 秒")
        self.interval_spin.setValue(60)
        self.interval_spin.setKeyboardTracking(False)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 20)
        self.limit_spin.setSuffix(" 条")

        interval_label = QLabel("发送间隔")
        limit_label = QLabel("本次最多发送")
        mode_label = QLabel("结束方式")
        duration_label = QLabel("运行时长")
        for name in (
            interval_label, limit_label, mode_label, duration_label
        ):
            name.setObjectName("fieldLabel")

        settings_layout.addWidget(interval_label, 0, 0)
        settings_layout.addWidget(self.interval_spin, 0, 1)
        settings_layout.addWidget(limit_label, 0, 2)
        settings_layout.addWidget(self.limit_spin, 0, 3)

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

        settings_layout.addWidget(mode_label, 1, 0)
        settings_layout.addWidget(self.mode_combo, 1, 1)
        settings_layout.addWidget(duration_label, 1, 2)

        duration_row = QHBoxLayout()
        duration_row.setSpacing(8)
        duration_row.addWidget(self.duration_spin)
        duration_row.addWidget(self.duration_unit)
        settings_layout.addLayout(duration_row, 1, 3)

        self.duration_hint = QLabel(
            "按时长结束时，到点自动停止；暂停期间不计时，最长 365 天。"
        )
        self.duration_hint.setObjectName("hintLabel")
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

        task_group = QGroupBox("发送")
        task_layout = QVBoxLayout(task_group)
        task_layout.setContentsMargins(8, 12, 8, 8)
        task_layout.setSpacing(10)

        status_row = QHBoxLayout()
        self.task_status_label = QLabel("未启动")
        self.task_status_label.setObjectName("statusPill")
        self.task_count_label = QLabel("尝试提交 0 条  ·  已执行提交 0 条")
        self.task_count_label.setObjectName("hintLabel")
        status_row.addWidget(self.task_status_label)
        status_row.addSpacing(12)
        status_row.addWidget(self.task_count_label)
        status_row.addStretch()
        task_layout.addLayout(status_row)

        self.authorization_check = QCheckBox(
            "我确认已获准在当前直播间发送这些消息，并会遵守直播间和平台规则"
        )
        task_layout.addWidget(self.authorization_check)

        task_buttons = QHBoxLayout()
        task_buttons.setSpacing(8)
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
        self.start_task_button.setObjectName("primaryButton")
        self.stop_task_button.setObjectName("dangerButton")
        task_buttons.addWidget(self.start_task_button)
        task_buttons.addWidget(self.pause_task_button)
        task_buttons.addWidget(self.resume_task_button)
        task_buttons.addWidget(self.stop_task_button)
        task_buttons.addStretch()
        task_layout.addLayout(task_buttons)
        layout.addWidget(task_group)

        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(8, 12, 8, 8)
        log_layout.setSpacing(6)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(120)
        self.log_output.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        clear_button = self.make_button(
            "清空日志", self.log_output.clear
        )
        clear_button.setObjectName("quietButton")
        log_bar = QHBoxLayout()
        log_bar.addStretch()
        log_bar.addWidget(clear_button)
        log_layout.addLayout(log_bar)
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group, 1)

        self.favorites_panel = FavoritesPanel(self)
        self.favorites_dock = QDockWidget("收藏直播间", self)
        self.favorites_dock.setObjectName("favoritesDock")
        self.favorites_dock.setWidget(self.favorites_panel)
        self.favorites_dock.setMinimumWidth(300)
        self.favorites_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            self.favorites_dock
        )
        self.favorites_panel.room_selected.connect(
            self.open_favorite_room
        )

        self.apply_style()
        page.setMinimumHeight(layout.totalMinimumSize().height())
        self._paint_pill(self.browser_status, "未启动", "idle")
        self._paint_pill(self.task_status_label, "未启动", "idle")

        self.add_log("弹幕助手 V0.4.6 已启动")
        self.add_log("请先启动 Edge 并连接直播间")

    def _paint_pill(self, label, text, kind):
        colors = {
            "idle": ("#EEF2F7", "#64748B"),
            "busy": ("#FEF3C7", "#B45309"),
            "ok": ("#DCFCE7", "#166534"),
            "stop": ("#F1F5F9", "#475569"),
            "done": ("#DBEAFE", "#1D4ED8"),
        }
        background, foreground = colors.get(kind, colors["idle"])
        label.setText(text)
        label.setStyleSheet(
            "background: %s; color: %s; border-radius: 11px;"
            "padding: 4px 12px; font-weight: 600;"
            % (background, foreground)
        )

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#page {
                background: #F3F5F9;
            }

            QWidget {
                font-family: "Microsoft YaHei";
                font-size: 13px;
                color: #1F2A37;
            }

            QLabel#mainTitle {
                font-size: 22px;
                font-weight: 700;
                color: #142033;
            }

            QLabel#subtitle, QLabel#hintLabel, QLabel#fieldLabel {
                color: #6B778C;
                font-size: 12px;
                font-weight: 400;
            }

            QLabel#roomValue {
                font-weight: 600;
                color: #1F2A37;
            }

            QLabel#cardTitle {
                font-size: 14px;
                font-weight: 700;
                color: #142033;
                padding-left: 2px;
            }

            QFrame#cardBody {
                background: white;
                border: 1px solid #E4E9F2;
                border-radius: 12px;
            }

            QScrollArea#pageScroll, QScrollArea#pageScroll > QWidget > QWidget {
                background: #F3F5F9;
                border: none;
            }

            QGroupBox {
                background: white;
                border: 1px solid #E4E9F2;
                border-radius: 12px;
                margin-top: 18px;
                font-weight: 600;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #142033;
            }

            QGroupBox QLabel#fieldLabel,
            QGroupBox QLabel#hintLabel {
                font-weight: 400;
            }

            QLineEdit, QSpinBox, QComboBox {
                padding: 6px 8px;
                border: 1px solid #D5DEEA;
                border-radius: 8px;
                background: white;
            }

            QLineEdit#roomUrl {
                padding: 0 10px;
                min-height: 36px;
                max-height: 36px;
            }

            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #3B82F6;
            }

            QTextEdit {
                border: 1px solid #D5DEEA;
                border-radius: 8px;
                padding: 8px;
                background: #FBFCFE;
            }

            QPushButton {
                padding: 6px 14px;
                border-radius: 8px;
                border: 1px solid #E2E8F0;
                background: white;
                color: #1F2A37;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #F8FAFC;
                border-color: #CBD5E1;
            }

            QPushButton:disabled {
                background: #F8FAFC;
                color: #A8B3C4;
                border-color: #EEF2F6;
            }

            QPushButton#primaryButton {
                background: #1D4ED8;
                color: white;
                border: none;
            }

            QPushButton#primaryButton:hover {
                background: #1E40AF;
            }

            QPushButton#primaryButton:disabled {
                background: #F8FAFC;
                color: #A8B3C4;
                border: 1px solid #EEF2F6;
            }

            QPushButton#accentButton {
                background: #0F766E;
                color: white;
                border: none;
            }

            QPushButton#accentButton:hover {
                background: #115E59;
            }

            QPushButton#accentButton:disabled {
                background: #F8FAFC;
                color: #A8B3C4;
                border: 1px solid #EEF2F6;
            }

            QPushButton#dangerButton {
                background: white;
                color: #B91C1C;
                border: 1px solid #FECACA;
            }

            QPushButton#dangerButton:hover {
                background: #FEF2F2;
            }

            QPushButton#dangerButton:disabled {
                background: #F8FAFC;
                color: #A8B3C4;
                border: 1px solid #EEF2F6;
            }

            QPushButton#quietButton {
                background: transparent;
                border: none;
                color: #64748B;
                font-weight: 500;
            }

            QTextEdit[readOnly="true"] {
                background: #0F172A;
                color: #D1FAE5;
                border: none;
                border-radius: 8px;
                font-family: Consolas, "Microsoft YaHei";
                font-size: 12px;
            }

            QCheckBox {
                spacing: 8px;
                font-weight: 400;
                color: #334155;
            }

            QListWidget {
                border: 1px solid #E4E9F2;
                border-radius: 8px;
                background: white;
                padding: 4px;
                outline: none;
            }

            QListWidget::item {
                padding: 8px;
                border-radius: 6px;
            }

            QListWidget::item:selected {
                background: #E8F0FE;
                color: #1E3A8A;
            }

            QDockWidget {
                font-weight: 600;
                color: #142033;
            }

            QDockWidget::title {
                background: #F8FAFC;
                padding: 8px;
                text-align: left;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 4px;
            }

            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 4px;
                min-height: 24px;
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
        kinds = {
            "未启动": "idle",
            "启动中": "busy",
            "运行中": "ok",
            "关闭中": "busy",
        }
        self._paint_pill(
            self.browser_status,
            status,
            kinds.get(status, "idle"),
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
            info.get("anchor") or "未识别"
        )
        self.page_label.setText(
            info.get("title") or "未连接"
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

        task_kinds = {
            "running": "ok",
            "paused": "busy",
            "stopped": "stop",
            "completed": "done",
        }
        self._paint_pill(
            self.task_status_label,
            names.get(status, status),
            task_kinds.get(status, "idle"),
        )

        attempted = data.get("attempted", 0)
        confirmed = data.get("confirmed", 0)

        self.task_count_label.setText(
            f"尝试提交 {attempted} 条  ·  已执行提交 {confirmed} 条"
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
