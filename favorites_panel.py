"""收藏直播间面板。使用独立表，不删除旧版收藏数据。"""
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from paths import app_data_dir

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem,
    QLabel, QMessageBox,
)

DB_PATH = app_data_dir() / "assistant.db"


def parse_platform(url):
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()

    if parsed.scheme != "https" or not parsed.path.strip("/"):
        raise ValueError("请输入完整的 HTTPS 直播间链接")

    if host == "live.douyin.com":
        return "抖音"
    if host in ("huya.com", "www.huya.com"):
        return "虎牙"
    raise ValueError("目前只支持抖音、虎牙直播间链接")


class FavoriteStore:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS room_favorites_v044 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def connect(self):
        return sqlite3.connect(str(DB_PATH), timeout=10)

    def all(self):
        with self.connect() as conn:
            return conn.execute("""
                SELECT id, platform, name, url
                FROM room_favorites_v044 ORDER BY id DESC
            """).fetchall()

    def add(self, name, url):
        url = url.strip()
        platform = parse_platform(url)
        name = name.strip() or urlparse(url).path.strip("/")
        with self.connect() as conn:
            conn.execute("""
                INSERT INTO room_favorites_v044 (platform, name, url)
                VALUES (?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    platform = excluded.platform,
                    name = excluded.name
            """, (platform, name, url))

    def delete(self, favorite_id):
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM room_favorites_v044 WHERE id = ?",
                (favorite_id,)
            )


class FavoritesPanel(QWidget):
    room_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = FavoriteStore()
        self.setMinimumWidth(240)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("收藏名称"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：常看的主播")
        layout.addWidget(self.name_edit)

        layout.addWidget(QLabel("直播间链接"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://...")
        layout.addWidget(self.url_edit)

        actions = QHBoxLayout()
        self.add_button = QPushButton("添加")
        self.open_button = QPushButton("打开")
        self.delete_button = QPushButton("删除")
        for button in (self.add_button, self.open_button, self.delete_button):
            actions.addWidget(button)
        layout.addLayout(actions)

        layout.addWidget(QLabel("双击直播间即可打开"))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget, 1)

        self.add_button.clicked.connect(self.add_favorite)
        self.open_button.clicked.connect(self.open_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        self.list_widget.itemDoubleClicked.connect(self.open_item)
        self.refresh()

    def set_current_room(self, url, name=""):
        self.url_edit.setText(url)
        self.name_edit.setText(name)

    def refresh(self):
        self.list_widget.clear()
        try:
            records = self.store.all()
        except sqlite3.Error as exc:
            QMessageBox.warning(self, "数据库错误", str(exc))
            return

        for favorite_id, platform, name, url in records:
            item = QListWidgetItem(f"[{platform}] {name}\n{url}")
            item.setData(Qt.ItemDataRole.UserRole, (favorite_id, url))
            self.list_widget.addItem(item)

    def add_favorite(self):
        try:
            self.store.add(self.name_edit.text(), self.url_edit.text())
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "收藏失败", str(exc))
            return
        self.refresh()

    def selected_record(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def open_item(self, item):
        record = item.data(Qt.ItemDataRole.UserRole)
        if record:
            self.room_selected.emit(record[1])

    def open_selected(self):
        record = self.selected_record()
        if record:
            self.room_selected.emit(record[1])
        else:
            QMessageBox.information(self, "提示", "请选择一个收藏的直播间")

    def delete_selected(self):
        record = self.selected_record()
        if not record:
            return
        try:
            self.store.delete(record[0])
        except sqlite3.Error as exc:
            QMessageBox.warning(self, "删除失败", str(exc))
            return
        self.refresh()
