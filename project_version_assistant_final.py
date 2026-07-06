import os
import re
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QPoint, QEvent
from PySide6.QtGui import QFont, QColor, QCursor, QIcon, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QFileDialog, QMessageBox, QVBoxLayout, QHBoxLayout, QGridLayout,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QLineEdit, QAbstractItemView,
    QGraphicsDropShadowEffect, QScrollArea, QSizeGrip, QSystemTrayIcon,
    QMenu, QPlainTextEdit
)


APP_NAME = "Git-Tool"
APP_VERSION = "1.5"
# 优化操作弹出黑窗口问题
DEFAULT_BRANCH = "master"

CONFIG_DIR = Path(os.getenv("APPDATA") or Path.home()) / "ProjectVersionAssistant"
CONFIG_FILE = CONFIG_DIR / "config.json"


def resource_path(name):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def load_config():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    default_cfg = {
        "repo_path": "",
        "reminder_enabled": False,
        "reminder_time": "18:00",
        "last_remind_date": ""
    }

    if not CONFIG_FILE.exists():
        return default_cfg

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        default_cfg.update(data)
        return default_cfg
    except Exception:
        return default_cfg


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def short_time():
    return datetime.now().strftime("%H:%M:%S")


def safe_branch_name(text):
    text = text.strip()
    text = re.sub(r"[^A-Za-z0-9_\-\/\.]", "_", text)
    text = text.strip("._-/")
    return text or ("from_old_" + datetime.now().strftime("%Y%m%d_%H%M%S"))


class ShadowMixin:
    def apply_shadow(self, blur=28, x=0, y=12, alpha=42):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur)
        shadow.setOffset(x, y)
        shadow.setColor(QColor(30, 42, 65, alpha))
        self.setGraphicsEffect(shadow)


class RoundedCard(QFrame, ShadowMixin):
    def __init__(self, radius=6, padding=16, bg="qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F6F8F2, stop:1 #EEF4E8)", border="#8FA579", parent=None):
        super().__init__(parent)
        self.setObjectName("roundedCard")
        self.setStyleSheet(f"""
            QFrame#roundedCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {radius}px;
            }}
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(padding, padding, padding, padding)
        self.layout.setSpacing(12)


class WindowControlButton(QPushButton):
    def __init__(self, text, hover_bg="#E8EFE1", hover_fg="#273338", fg="#273338", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setFixedSize(46, 34)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 0px;
                color: {fg};
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {hover_bg};
                color: {hover_fg};
            }}
        """)


class FunctionTile(QPushButton):
    def __init__(self, code, text, accent, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(64)
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #F6F8F2, stop:1 #EEF4E8);
                border: 1px solid #8FA579;
                border-radius: 6px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #EEF4E8, stop:1 #DDE8D5);
                border: 1px solid #618764;
            }}
            QPushButton:pressed {{
                background: #DDE8D5;
            }}
        """)

        box = QHBoxLayout(self)
        box.setContentsMargins(12, 8, 14, 8)
        box.setSpacing(12)

        code_label = QLabel(code)
        code_label.setAlignment(Qt.AlignCenter)
        code_label.setFixedSize(38, 34)
        code_label.setStyleSheet(f"""
            QLabel {{
                background: #EEF4E8;
                border: 1px solid #7C9870;
                border-radius: 4px;
                color: #2B5748;
                font-size: 12px;
                font-weight: 900;
            }}
        """)

        text_label = QLabel(text)
        text_label.setStyleSheet("""
            QLabel {
                color: #273338;
                font-size: 14px;
                font-weight: 800;
                background: transparent;
            }
        """)
        text_label.setWordWrap(True)

        box.addWidget(code_label)
        box.addWidget(text_label, 1)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.cfg = load_config()
        self.repo_path = self.cfg.get("repo_path", "")
        self.selected_commit = None
        self.log_commits = []
        self.drag_pos = None
        self.is_collapsed = False
        self.collapsed_edge = None
        self.expanded_geometry = None
        self.auto_hide_margin = 14
        self.auto_hide_delay_ms = 800

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(500, 520)
        self.resize(720, 800)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self.auto_hide_timer = QTimer(self)
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self.collapse_to_screen_edge)

        self.build_ui()
        self.setup_tray_icon()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_reminder)
        self.timer.start(20_000)

        self.update_project_label()
        self.add_status("应用启动成功")
        if self.repo_path:
            self.add_status("已载入上次项目")
            self.refresh_history(silent=True)
            self.refresh_status(silent=True)
        else:
            self.add_status("未选择项目")

        self.auto_hide_timer.start(1500)

    # =========================
    # UI
    # =========================
    def build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        root.setStyleSheet("""
            QWidget#root {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #273338, stop:1 #2B5748);
                border-radius: 0px;
            }
            QLabel {
                color: #273338;
                font-family: "Helvetica Neue", "Arial", sans-serif;
                background: transparent;
            }
            QTableWidget {
                background: #F6F8F2;
                border: 1px solid #8FA579;
                border-radius: 6px;
                color: #273338;
                font-size: 13px;
                selection-background-color: #CFE2D3;
                selection-color: #273338;
                gridline-color: transparent;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #DDE8D5;
            }
            QHeaderView::section {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EEF4E8, stop:1 #DDE8D5);
                color: #2B5748;
                border: none;
                border-bottom: 1px solid #8FA579;
                font-size: 12px;
                font-weight: 700;
                padding: 9px;
            }
            QListWidget {
                background: #F6F8F2;
                border: 1px solid #8FA579;
                border-radius: 6px;
                color: #273338;
                font-size: 13px;
                outline: none;
            }
            QListWidget::item {
                padding: 9px;
                border-bottom: 1px solid #DDE8D5;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 8px 0 8px 0;
            }
            QScrollBar::handle:vertical {
                background: #618764;
                border-radius: 4px;
                min-height: 36px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 14, 14, 14)

        panel = QFrame()
        panel.setObjectName("mainPanel")
        panel.setStyleSheet("""
            QFrame#mainPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #9CB080, stop:1 #B9C9A8);
                border: none;
                border-radius: 0px;
            }
        """)

        outer.addWidget(panel)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        # title bar
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(52)
        self.title_bar.setObjectName("titleBar")
        self.title_bar.setStyleSheet("""
            QWidget#titleBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #273338, stop:1 #2B5748);
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom: 1px solid #2B5748;
            }
        """)
        tb = QHBoxLayout(self.title_bar)
        tb.setContentsMargins(16, 0, 0, 0)
        tb.setSpacing(8)

        min_btn = WindowControlButton("-", "#2B5748", "white", "#F6F8F2")
        self.max_btn = WindowControlButton("□", "#2B5748", "white", "#F6F8F2")
        close_btn = WindowControlButton("×", "#618764", "white", "#F6F8F2")
        min_btn.setToolTip("最小化")
        self.max_btn.setToolTip("最大化")
        close_btn.setToolTip("关闭")
        min_btn.clicked.connect(self.showMinimized)
        self.max_btn.clicked.connect(self.toggle_max_restore)
        close_btn.clicked.connect(self.close)

        logo = QLabel("GT")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(32, 32)
        logo.setStyleSheet("""
            QLabel {
                background: #F6F8F2;
                color: #273338;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 900;
            }
        """)

        title = QLabel(APP_NAME)
        title.setStyleSheet("font-size:18px;font-weight:900;color:#F6F8F2;")
        self.top_status_dot = QLabel()
        self.top_status_dot.setFixedSize(8, 8)
        self.top_status_dot.setStyleSheet("""
            QLabel {
                background: #9CB080;
                border-radius: 4px;
            }
        """)
        self.top_status_label = QLabel("就绪")
        self.top_status_label.setStyleSheet("""
            QLabel {
                color: #DDE8D5;
                font-size: 12px;
                font-weight: 800;
                background: transparent;
            }
        """)
        tb.addWidget(logo)
        tb.addWidget(title)
        tb.addSpacing(8)
        tb.addWidget(self.top_status_dot)
        tb.addWidget(self.top_status_label)
        tb.addStretch(2)

        tb.addSpacing(4)
        tb.addWidget(min_btn)
        tb.addWidget(self.max_btn)
        tb.addWidget(close_btn)

        panel_layout.addWidget(self.title_bar)

        scroll_area = QScrollArea()
        scroll_area.setObjectName("contentScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.viewport().setStyleSheet("background: #AFC19A;")

        content = QWidget()
        content.setObjectName("content")
        content.setStyleSheet("""
            QWidget#content {
                background: #AFC19A;
            }
        """)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 18, 20, 14)
        content_layout.setSpacing(12)
        scroll_area.setWidget(content)
        panel_layout.addWidget(scroll_area, 1)

        # project card
        project_card = RoundedCard(radius=6, padding=12)
        project_row = QHBoxLayout()
        project_row.setSpacing(10)

        folder = QLabel("01")
        folder.setFixedSize(42, 42)
        folder.setAlignment(Qt.AlignCenter)
        folder.setStyleSheet("""
            QLabel {
                background: #EEF4E8;
                border: 1px solid #8FA579;
                border-radius: 4px;
                color: #2B5748;
                font-size: 13px;
                font-weight: 900;
            }
        """)
        project_row.addWidget(folder)

        self.project_label = QLabel("当前项目：未选择")
        self.project_label.setStyleSheet("font-size:14px;font-weight:800;color:#273338;background: transparent;")
        project_row.addWidget(self.project_label, 1)

        self.project_hint = QLabel("点击选择项目  ›")
        self.project_hint.setStyleSheet("font-size:12px;color:#2B5748;font-weight:700;background: transparent;")
        project_row.addWidget(self.project_hint)

        project_card.layout.addLayout(project_row)
        project_card.mousePressEvent = lambda event: self.choose_project()
        content_layout.addWidget(project_card)

        # main CTA
        cta_card = RoundedCard(radius=6, padding=12)
        self.one_click_btn = QPushButton("一键保存并上传")
        self.one_click_btn.setCursor(Qt.PointingHandCursor)
        self.one_click_btn.setFixedHeight(58)
        self.one_click_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2B5748, stop:1 #356B57);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 18px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #273338, stop:1 #2B5748);
            }
            QPushButton:pressed {
                background: #273338;
            }
        """)
        self.one_click_btn.clicked.connect(self.one_click_save_upload)
        cta_card.layout.addWidget(self.one_click_btn)
        content_layout.addWidget(cta_card)

        # feature tiles
        self.function_grid = QGridLayout()
        self.function_grid.setHorizontalSpacing(10)
        self.function_grid.setVerticalSpacing(10)

        specs = [
            ("01", "选择项目", "#2B5748", self.choose_project),
            ("02", "初始化项目", "#2B5748", self.init_project),
            ("03", "查看修改", "#2B5748", self.show_changes),
            ("04", "保存版本", "#2B5748", self.save_version),
            ("05", "上传云端", "#2B5748", self.push_cloud),
            ("06", "获取最新版本", "#2B5748", self.pull_latest),
            ("07", "查看历史版本", "#2B5748", self.show_history),
            ("08", "切换分支/旧版本修改", "#2B5748", self.continue_from_old_version),
            ("09", "分支合并", "#2B5748", self.merge_branch),
            ("10", "定时提醒上传代码", "#2B5748", self.set_reminder),
        ]

        self.function_tiles = []
        for i, (icon, text, color, handler) in enumerate(specs):
            btn = FunctionTile(icon, text, color)
            btn.clicked.connect(handler)
            self.function_tiles.append(btn)

        content_layout.addLayout(self.function_grid)
        self.reflow_function_grid()

        # bottom
        bottom_row = QVBoxLayout()
        bottom_row.setSpacing(12)

        history_card = RoundedCard(radius=6, padding=16)
        h_top = QHBoxLayout()
        h_title = QLabel("历史版本")
        h_title.setStyleSheet("font-size:16px;font-weight:900;color:#273338;background: transparent;")
        h_top.addWidget(h_title)
        h_top.addStretch(1)

        refresh_hist = QPushButton("刷新")
        refresh_hist.setCursor(Qt.PointingHandCursor)
        refresh_hist.setFixedSize(72, 30)
        refresh_hist.setStyleSheet("""
            QPushButton {
                background: #EEF4E8;
                color: #2B5748;
                border: 1px solid #8FA579;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #DDE8D5;
                border: 1px solid #618764;
            }
        """)
        refresh_hist.clicked.connect(self.show_history)
        h_top.addWidget(refresh_hist)
        history_card.layout.addLayout(h_top)

        self.history_summary = QLabel("当前分支：-   远程状态：-   工作区状态：-")
        self.history_summary.setStyleSheet("font-size:12px;color:#273338;font-weight:800;line-height:1.45;background: transparent;")
        history_card.layout.addWidget(self.history_summary)

        history_body = QHBoxLayout()
        history_body.setSpacing(10)

        branch_panel = QVBoxLayout()
        branch_title = QLabel("分支列表")
        branch_title.setStyleSheet("font-size:12px;color:#2B5748;font-weight:900;background: transparent;")
        branch_panel.addWidget(branch_title)

        self.history_branch_list = QListWidget()
        self.history_branch_list.setMaximumWidth(170)
        self.history_branch_list.setMinimumHeight(160)
        self.history_branch_list.setStyleSheet("""
            QListWidget {
                background: #F6F8F2;
                border: 1px solid #8FA579;
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
                font-weight: 800;
                color: #273338;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #DDE8D5;
                color: #2B5748;
            }
        """)
        self.history_branch_list.itemSelectionChanged.connect(self.on_history_branch_selection_changed)
        branch_panel.addWidget(self.history_branch_list)
        history_body.addLayout(branch_panel)

        version_panel = QVBoxLayout()
        version_title = QLabel("历史版本")
        version_title.setStyleSheet("font-size:12px;color:#2B5748;font-weight:900;background: transparent;")
        version_panel.addWidget(version_title)

        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["版本号", "时间", "状态", "说明"])
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setShowGrid(False)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.history_table.itemSelectionChanged.connect(self.on_history_selection_changed)
        self.history_table.setMinimumHeight(160)
        version_panel.addWidget(self.history_table)
        history_body.addLayout(version_panel, 1)
        history_card.layout.addLayout(history_body)

        self.history_detail = QLabel("选中版本详情：-")
        self.history_detail.setWordWrap(True)
        self.history_detail.setStyleSheet("""
            QLabel {
                background: #EEF4E8;
                color: #273338;
                border: 1px solid #8FA579;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                font-weight: 700;
                line-height: 1.45;
            }
        """)
        history_card.layout.addWidget(self.history_detail)

        hist_actions = QHBoxLayout()
        hist_actions.setSpacing(8)
        self.history_switch_btn = QPushButton("切换分支")
        self.history_old_btn = QPushButton("从此版本修改")
        self.history_merge_btn = QPushButton("分支合并")
        for btn in (self.history_switch_btn, self.history_old_btn, self.history_merge_btn):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton {
                    background: #EEF4E8;
                    color: #2B5748;
                    border: 1px solid #8FA579;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 900;
                    padding: 0 12px;
                }
                QPushButton:hover {
                    background: #DDE8D5;
                    border: 1px solid #618764;
                }
            """)
            hist_actions.addWidget(btn)
        hist_actions.addStretch(1)
        self.history_switch_btn.clicked.connect(self.continue_from_old_version)
        self.history_old_btn.clicked.connect(self.continue_from_old_version)
        self.history_merge_btn.clicked.connect(self.merge_branch)
        history_card.layout.addLayout(hist_actions)
        bottom_row.addWidget(history_card)

        self.status_list = None

        content_layout.addLayout(bottom_row, 1)

        # footer
        footer = QHBoxLayout()
        footer.setContentsMargins(8, 3, 8, 0)
        left = QLabel(f"{APP_NAME} v{APP_VERSION}")
        left.setStyleSheet("font-size:13px;color:#2B5748;font-weight:700;")
        self.ready_label = QLabel("就绪")
        self.ready_label.setStyleSheet("font-size:13px;color:#2B5748;font-weight:800;")
        footer.addWidget(left)
        footer.addStretch(1)
        footer.addWidget(self.ready_label)
        content_layout.addLayout(footer)

        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(18, 18)
        self.size_grip.raise_()

    def toggle_max_restore(self):
        self.auto_hide_timer.stop()
        if self.is_collapsed:
            self.restore_from_screen_edge()
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("□")
            self.max_btn.setToolTip("最大化")
        else:
            self.showMaximized()
            self.max_btn.setText("❐")
            self.max_btn.setToolTip("还原")

    def setup_tray_icon(self):
        icon_path = resource_path("app_icon.ico")
        icon = QIcon(str(icon_path)) if icon_path.exists() else self.windowIcon()
        self.setWindowIcon(icon)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip(APP_NAME)

        tray_menu = QMenu(self)
        show_action = QAction("显示窗口", self)
        quit_action = QAction("退出", self)
        show_action.triggered.connect(self.show_from_tray)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def hide_to_tray(self):
        self.auto_hide_timer.stop()
        self.hide()
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                APP_NAME,
                "已最小化到托盘，点击托盘图标可恢复窗口。",
                QSystemTrayIcon.Information,
                1600
            )

    def show_from_tray(self):
        self.auto_hide_timer.stop()
        if self.is_collapsed:
            self.restore_from_screen_edge()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.Trigger,
            QSystemTrayIcon.DoubleClick,
            QSystemTrayIcon.MiddleClick,
        ):
            self.show_from_tray()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self.hide_to_tray)
        super().changeEvent(event)

    def enterEvent(self, event):
        self.auto_hide_timer.stop()
        if self.is_collapsed:
            self.restore_from_screen_edge()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.should_auto_hide():
            self.auto_hide_timer.start(self.auto_hide_delay_ms)
        super().leaveEvent(event)

    def should_auto_hide(self):
        return (
            self.isVisible()
            and not self.isMinimized()
            and not self.isMaximized()
            and self.drag_pos is None
            and QApplication.activeModalWidget() is None
            and not self.frameGeometry().contains(QCursor.pos())
        )

    def collapse_to_screen_edge(self):
        if not self.should_auto_hide() or self.is_collapsed:
            return

        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        area = screen.availableGeometry()
        normal = self.geometry()
        self.expanded_geometry = normal

        center = normal.center()
        distances = {
            "left": abs(center.x() - area.left()),
            "right": abs(area.right() - center.x()),
            "top": abs(center.y() - area.top()),
            "bottom": abs(area.bottom() - center.y()),
        }
        self.collapsed_edge = min(distances, key=distances.get)

        x = normal.x()
        y = normal.y()
        if self.collapsed_edge == "left":
            x = area.left() - normal.width() + self.auto_hide_margin
            y = self.clamp(normal.y(), area.top(), area.bottom() - normal.height() + 1)
        elif self.collapsed_edge == "right":
            x = area.right() - self.auto_hide_margin + 1
            y = self.clamp(normal.y(), area.top(), area.bottom() - normal.height() + 1)
        elif self.collapsed_edge == "top":
            x = self.clamp(normal.x(), area.left(), area.right() - normal.width() + 1)
            y = area.top() - normal.height() + self.auto_hide_margin
        else:
            x = self.clamp(normal.x(), area.left(), area.right() - normal.width() + 1)
            y = area.bottom() - self.auto_hide_margin + 1

        self.is_collapsed = True
        self.move(x, y)

    def restore_from_screen_edge(self):
        if not self.expanded_geometry:
            self.is_collapsed = False
            return

        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            target = self.expanded_geometry
            x = self.clamp(target.x(), area.left(), area.right() - target.width() + 1)
            y = self.clamp(target.y(), area.top(), area.bottom() - target.height() + 1)
            target.moveTo(x, y)
            self.setGeometry(target)
        else:
            self.setGeometry(self.expanded_geometry)

        self.is_collapsed = False
        self.collapsed_edge = None

    def clamp(self, value, low, high):
        if high < low:
            return low
        return max(low, min(value, high))

    def mousePressEvent(self, event):
        self.auto_hide_timer.stop()
        if self.is_collapsed:
            self.restore_from_screen_edge()
        if event.button() == Qt.LeftButton and event.position().y() < 60:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() & Qt.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_pos = None

    def reflow_function_grid(self):
        if not hasattr(self, "function_grid") or not hasattr(self, "function_tiles"):
            return

        columns = 1 if self.width() < 660 else 2
        for tile in self.function_tiles:
            self.function_grid.removeWidget(tile)

        for i, tile in enumerate(self.function_tiles):
            self.function_grid.addWidget(tile, i // columns, i % columns)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow_function_grid()
        if hasattr(self, "size_grip"):
            self.size_grip.move(self.width() - 28, self.height() - 28)

    # =========================
    # 状态与提示
    # =========================
    def set_operation_state(self, text="就绪", state="ready"):
        colors = {
            "ready": "#9CB080",
            "busy": "#E8EFE1",
            "error": "#D96A55",
        }
        color = colors.get(state, colors["ready"])
        if hasattr(self, "top_status_dot"):
            self.top_status_dot.setStyleSheet(f"""
                QLabel {{
                    background: {color};
                    border-radius: 4px;
                }}
            """)
        if hasattr(self, "top_status_label"):
            self.top_status_label.setText(text)
        if hasattr(self, "ready_label"):
            self.ready_label.setText(text)
        QApplication.processEvents()

    def add_status(self, text):
        if self.status_list is not None:
            item = QListWidgetItem(f"{short_time()}   {text}")
            self.status_list.insertItem(0, item)
        self.set_operation_state("就绪", "ready")

    def clear_status(self):
        if self.status_list is None:
            return
        self.status_list.clear()
        self.add_status("状态已清空")

    def update_project_label(self):
        if not self.repo_path:
            self.project_label.setText("当前项目：未选择")
            self.project_hint.setText("点击选择项目  ›")
            self.project_label.setToolTip("")
            return

        name = Path(self.repo_path).name or self.repo_path
        self.project_label.setText(f"当前项目：{name}")
        self.project_label.setToolTip(self.repo_path)
        self.project_hint.setText("点击切换项目  ›")

    def ask_repo(self):
        if self.repo_path:
            return self.repo_path

        ret = QMessageBox.question(
            self,
            "选择项目",
            "还没有选择项目，是否现在选择？",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.choose_project()

        return self.repo_path if self.repo_path else None

    def show_info(self, title, text):
        QMessageBox.information(self, title, text)

    def show_error(self, title, text):
        QMessageBox.critical(self, title, text)

    # =========================
    # Git 基础封装
    # =========================
    def run_git(self, args, repo_path=None, timeout=120):
        repo_path = repo_path or self.repo_path

        if not repo_path:
            return False, "未选择项目。"

        try:
            self.set_operation_state("处理中", "busy")
            env = os.environ.copy()
            startupinfo = None
            creationflags = 0
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                creationflags = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(
                ["git"] + args,
                cwd=repo_path,
                text=True,
                encoding="utf-8",
                errors="ignore",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                timeout=timeout,
                env=env,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            ok = result.returncode == 0
            self.set_operation_state("就绪" if ok else "失败", "ready" if ok else "error")
            return ok, out if out else err
        except subprocess.TimeoutExpired:
            self.set_operation_state("超时", "error")
            return False, "Git 命令执行超时。请检查网络、账号登录状态或仓库地址。"
        except FileNotFoundError:
            self.set_operation_state("失败", "error")
            return False, "没有找到 Git。请先安装 Git，并确认 git 命令已经加入系统环境变量。"
        except Exception as e:
            self.set_operation_state("失败", "error")
            return False, str(e)

    def is_git_repo(self):
        if not self.repo_path:
            return False

        ok, out = self.run_git(["rev-parse", "--is-inside-work-tree"], timeout=10)
        return ok and out.strip().lower() == "true"

    def is_selected_folder_empty(self):
        if not self.repo_path:
            return False

        try:
            return not any(Path(self.repo_path).iterdir())
        except Exception:
            return False

    def has_commits(self):
        ok, _ = self.run_git(["rev-parse", "--verify", "HEAD"], timeout=10)
        return ok

    def current_branch(self):
        ok, out = self.run_git(["branch", "--show-current"], timeout=10)
        if ok and out.strip():
            return out.strip()

        return DEFAULT_BRANCH

    def has_remote_origin(self):
        ok, out = self.run_git(["remote", "get-url", "origin"], timeout=10)
        return ok and bool(out.strip())

    def has_upstream(self):
        ok, out = self.run_git(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            timeout=10
        )
        return ok and bool(out.strip())

    def remote_status_text(self):
        if not self.has_remote_origin():
            return "未绑定远程仓库"

        if not self.has_upstream():
            return "已绑定远程，未绑定上游分支"

        ok, out = self.run_git(["rev-list", "--left-right", "--count", "@{u}...HEAD"], timeout=20)
        if not ok:
            return "远程状态未知"

        parts = out.split()
        if len(parts) != 2:
            return "远程状态未知"

        behind, ahead = parts
        if behind == "0" and ahead == "0":
            return "本地与远程已同步"
        if behind == "0":
            return f"本地领先 {ahead} 个版本，未上传"
        if ahead == "0":
            return f"本地落后 {behind} 个版本"
        return f"本地领先 {ahead} 个版本，落后 {behind} 个版本"

    def worktree_status_text(self):
        changes, _ = self.get_changes_raw()
        if not changes or not changes.strip():
            return "无未保存改动"

        count = len([line for line in changes.splitlines() if line.strip()])
        return f"{count} 个未保存改动"

    def list_local_branches(self):
        branches = []
        seen = set()

        ok, out = self.run_git(["branch", "--format", "%(refname:short)"], timeout=20)
        if not ok:
            return branches

        for line in out.splitlines():
            name = line.strip()
            if not name or name in seen:
                continue

            seen.add(name)
            branches.append(name)

        return branches

    def list_remote_branches(self):
        branches = []
        seen = set()

        ok, out = self.run_git(["branch", "-r", "--format", "%(refname:short)"], timeout=20)
        if not ok:
            return branches

        for line in out.splitlines():
            name = line.strip()
            if not name or name.endswith("/HEAD") or name in seen:
                continue

            seen.add(name)
            branches.append(name)

        return branches

    def restore_commit_to_worktree(self, commit_id):
        ok, out = self.run_git(["restore", "--source", commit_id, "--staged", "--worktree", "."], timeout=120)
        if ok:
            return True, out

        return self.run_git(["checkout", commit_id, "--", "."], timeout=120)

    def list_merge_branches(self):
        branches = []
        seen = set()

        commands = [
            ["branch", "--format", "%(refname:short)"],
            ["branch", "-r", "--format", "%(refname:short)"],
        ]

        for args in commands:
            ok, out = self.run_git(args, timeout=20)
            if not ok:
                continue

            for line in out.splitlines():
                name = line.strip()
                if not name or name.endswith("/HEAD"):
                    continue
                if name in seen:
                    continue

                seen.add(name)
                branches.append(name)

        return branches

    def get_changes_raw(self, include_untracked=True):
        ok, out = self.run_git(["status", "--porcelain"], timeout=20)
        if not ok:
            return None, out
        if not include_untracked:
            lines = [line for line in out.splitlines() if not line.startswith("??")]
            return "\n".join(lines), ""
        return out, ""

    def discard_pending_changes(self):
        ok, out = self.run_git(["reset", "--hard"], timeout=60)
        if not ok:
            return False, out

        ok, out = self.run_git(["clean", "-fd"], timeout=60)
        if not ok:
            return False, out

        return True, ""

    def confirm_save_pending_changes(self, action_text, allow_discard=False):
        changes, err = self.get_changes_raw(include_untracked=False)
        if changes is None:
            self.show_error("失败", err)
            return False

        if not changes.strip():
            return True

        if allow_discard:
            box = QMessageBox(self)
            box.setWindowTitle("当前有未保存改动")
            box.setText(f"当前项目有未保存改动。\n\n要如何继续{action_text}？")
            box.setInformativeText("选择“丢弃改动并继续”会清理当前工作区的未保存内容。")
            save_btn = box.addButton("先保存再继续", QMessageBox.AcceptRole)
            discard_btn = box.addButton("丢弃改动并继续", QMessageBox.DestructiveRole)
            cancel_btn = box.addButton("取消", QMessageBox.RejectRole)
            box.setDefaultButton(save_btn)
            box.exec()

            clicked = box.clickedButton()
            if clicked == save_btn:
                return self.save_version_auto()
            if clicked == discard_btn:
                ok, out = self.discard_pending_changes()
                if not ok:
                    self.show_error("丢弃改动失败", out)
                    return False

                self.add_status("已丢弃当前未保存改动")
                return True
            if clicked == cancel_btn:
                return False

            return False

        choice = QMessageBox.question(
            self,
            "当前有未保存改动",
            f"当前项目有未保存改动。\n\n是否先自动保存当前版本，再{action_text}？",
            QMessageBox.Yes | QMessageBox.No
        )

        if choice != QMessageBox.Yes:
            return False

        return self.save_version_auto()

    def has_unpushed_commits(self):
        if not self.has_commits():
            return False

        if self.has_upstream():
            ok, out = self.run_git(["rev-list", "--count", "@{u}..HEAD"], timeout=20)
            if ok:
                try:
                    return int(out.strip()) > 0
                except Exception:
                    return False

        # 没有 upstream 但有远程仓库时，认为可能存在未上传版本
        if self.has_remote_origin():
            return True

        return False

    def ensure_remote_if_needed(self):
        if self.has_remote_origin():
            return True

        text, ok = QInputDialog.getText(
            self,
            "设置远程仓库",
            "当前项目还没有绑定云端仓库。\n\n请输入 GitHub / Gitee 仓库地址：\n例如：https://github.com/用户名/仓库名.git",
            QLineEdit.Normal,
            ""
        )

        if not ok or not text.strip():
            return False

        ok2, out = self.run_git(["remote", "add", "origin", text.strip()], timeout=20)
        if ok2:
            self.add_status("已绑定远程仓库 origin")
            return True

        self.show_error("绑定远程仓库失败", out)
        return False

    def init_git_repo(self):
        if self.is_git_repo():
            self.add_status("当前项目已经是 Git 项目")
            return True

        ok, out = self.run_git(["init"], timeout=30)
        if not ok:
            self.show_error("初始化失败", out)
            return False

        # 统一主分支名称，失败不影响基本使用。
        # 注意：公司 Gitblit 服务器默认 HEAD 通常指向 master。
        # 如果这里强制改成 main，上传后 Gitblit 首页可能仍默认看 master，导致需要手动点击 main 才能查看历史版本。
        self.run_git(["branch", "-M", DEFAULT_BRANCH], timeout=10)
        self.add_status(f"Git 初始化完成，当前主分支：{DEFAULT_BRANCH}")
        return True

    # =========================
    # 功能 1：选择项目
    # =========================
    def choose_project(self):
        path = QFileDialog.getExistingDirectory(self, "选择项目文件夹", self.repo_path or str(Path.home()))
        if not path:
            return

        self.repo_path = path
        self.cfg["repo_path"] = path
        save_config(self.cfg)

        self.update_project_label()
        self.add_status("已选择项目：" + Path(path).name)
        self.refresh_history(silent=True)
        self.refresh_status(silent=True)

    # =========================
    # 功能 2：初始化项目
    # =========================
    def init_project(self):
        if not self.ask_repo():
            return False

        if not self.init_git_repo():
            return False

        choice = QMessageBox.question(
            self,
            "远程仓库",
            "是否现在绑定云端仓库地址？",
            QMessageBox.Yes | QMessageBox.No
        )

        if choice == QMessageBox.Yes:
            self.ensure_remote_if_needed()

        self.refresh_history(silent=True)
        return True

    # =========================
    # 功能 3：查看修改
    # =========================
    def refresh_status(self, silent=False):
        if not self.repo_path:
            return False

        if not self.is_git_repo():
            if not silent:
                self.show_info("提示", "当前文件夹还不是 Git 项目，请先初始化项目。")
            return False

        changes, err = self.get_changes_raw()
        if changes is None:
            if not silent:
                self.show_error("查看修改失败", err)
            return False

        if not changes.strip():
            if not silent:
                self.show_info("查看修改", "当前没有未保存的文件改动。")
            self.add_status("当前没有未保存的文件改动")
            return True

        parsed = self.parse_changes(changes)
        self.add_status(f"检测到 {len(parsed)} 个文件改动")

        if not silent:
            text = "\n".join([f"{desc}: {file}" for desc, file in parsed[:40]])
            if len(parsed) > 40:
                text += f"\n\n还有 {len(parsed)-40} 个文件未显示。"
            self.show_info("查看修改", text)

        return True

    def show_changes(self):
        return self.refresh_status(silent=False)

    def parse_changes(self, raw):
        result = []
        for line in raw.splitlines():
            if not line.strip():
                continue

            status = line[:2]
            file = line[3:] if len(line) > 3 else line

            if status == "??":
                desc = "新增"
            elif "M" in status:
                desc = "修改"
            elif "D" in status:
                desc = "删除"
            elif "R" in status:
                desc = "重命名"
            elif "A" in status:
                desc = "新增"
            else:
                desc = "变更"

            result.append((desc, file))
        return result

    # =========================
    # 功能 4：保存版本
    # =========================
    def save_version(self):
        if not self.ask_repo():
            return False

        if not self.is_git_repo():
            self.show_info("提示", "当前项目还没有初始化 Git。")
            return False

        changes, err = self.get_changes_raw()
        if changes is None:
            self.show_error("保存失败", err)
            return False

        if not changes.strip():
            self.show_info("保存版本", "没有新的文件改动，不需要保存版本。")
            self.add_status("没有新的文件改动，不需要保存版本")
            return True

        msg = self.ask_commit_message("保存版本")
        if not msg:
            return False

        return self.commit_with_message(msg, show_success=True)

    def ask_commit_message(self, title="保存版本"):
        """弹出版本说明输入框。

        普通“保存版本”和“一键保存并上传”都走这里，避免一键保存时只能使用固定默认说明。
        返回去掉首尾空格后的说明；用户取消或输入为空时返回 None。
        """
        default_msg = "save: " + now_text()
        msg, ok = QInputDialog.getText(
            self,
            title,
            "请输入本次版本说明：",
            QLineEdit.Normal,
            default_msg
        )

        if not ok or not msg.strip():
            return None

        return msg.strip()

    def commit_with_message(self, message, show_success=False):
        ok, out = self.run_git(["add", "-A"], timeout=60)
        if not ok:
            self.show_error("保存失败：git add", out)
            return False

        ok, out = self.run_git(["commit", "-m", message], timeout=60)
        if not ok:
            self.show_error("保存版本失败", out)
            return False

        self.add_status("版本保存成功")
        self.refresh_history(silent=True)

        if show_success:
            self.show_info("完成", "版本保存成功。")

        return True

    def save_version_auto(self):
        if not self.ask_repo() or not self.is_git_repo():
            return False

        changes, err = self.get_changes_raw()
        if changes is None:
            self.show_error("保存失败", err)
            return False

        if not changes.strip():
            self.add_status("没有新的文件改动，跳过保存版本")
            return True

        msg = self.ask_commit_message("一键保存并上传")
        if not msg:
            self.add_status("用户取消输入版本说明，已停止一键保存并上传")
            return False

        return self.commit_with_message(msg, show_success=False)

    # =========================
    # 功能 5：上传云端
    # =========================
    def push_cloud(self):
        if not self.ask_repo():
            return False

        if not self.is_git_repo():
            self.show_info("提示", "当前项目还没有初始化 Git。")
            return False

        if not self.has_commits():
            self.show_info("上传云端", "当前还没有保存过版本，请先保存版本。")
            return False

        if not self.ensure_remote_if_needed():
            return False

        ok, out = self.run_git(["push"], timeout=180)
        if ok:
            self.add_status("上传云端成功")
            self.show_info("完成", "上传云端成功。")
            return True

        branch = self.current_branch()
        ok2, out2 = self.run_git(["push", "-u", "origin", branch], timeout=180)
        if ok2:
            self.add_status("首次上传成功，并已绑定当前分支")
            self.show_info("完成", "首次上传成功，并已绑定当前分支。")
            return True

        self.show_error(
            "上传失败",
            out + "\n\n常见原因：\n"
            "1. GitHub / Gitee 没有登录\n"
            "2. 云端有新版本，需要先获取最新版本\n"
            "3. 远程仓库地址错误\n"
            "4. 当前分支没有权限上传"
        )
        return False

    # =========================
    # 功能 6：获取最新版本
    # =========================
    def clone_remote_repo_into_current_folder(self):
        if not self.repo_path:
            return False

        if not self.is_selected_folder_empty():
            self.show_info("提示", "当前文件夹不是 Git 项目，也不是空文件夹。\n\n如果要从云端下载项目，请选择一个空文件夹。")
            return False

        text, ok = QInputDialog.getText(
            self,
            "下载云端项目",
            "当前选择的是空文件夹。\n\n请输入 GitHub / Gitee 仓库地址：\n例如：https://github.com/用户名/仓库名.git",
            QLineEdit.Normal,
            ""
        )

        if not ok or not text.strip():
            return False

        self.set_operation_state("下载中", "busy")
        self.add_status("开始从云端下载项目")

        ok2, out = self.run_git(["clone", text.strip(), "."], repo_path=self.repo_path, timeout=300)
        if not ok2:
            self.set_operation_state("下载失败", "error")
            self.show_error("下载云端项目失败", out)
            return False

        self.set_operation_state("完成", "ready")
        self.add_status("云端项目下载完成")
        self.refresh_history(silent=True)
        self.refresh_status(silent=True)
        self.show_info("完成", "云端项目已下载到当前空文件夹。")
        return True

    def pull_latest(self):
        if not self.ask_repo():
            return False

        if not self.is_git_repo() and self.is_selected_folder_empty():
            return self.clone_remote_repo_into_current_folder()

        if not self.is_git_repo():
            self.show_info("提示", "当前项目还没有初始化 Git。")
            return False

        if not self.has_remote_origin():
            self.show_info("提示", "当前项目还没有绑定远程仓库。")
            return False

        if self.has_upstream():
            ok, out = self.run_git(["pull", "--rebase", "--autostash"], timeout=180)
        else:
            branch = self.current_branch()
            ok, out = self.run_git(["pull", "origin", branch, "--rebase", "--autostash"], timeout=180)

        if ok:
            self.add_status("获取最新版本成功")
            self.refresh_history(silent=True)
            self.show_info("完成", "获取最新版本成功。")
            return True

        self.show_error(
            "获取最新失败",
            out + "\n\n可能存在文件冲突，需要手动处理。"
        )
        return False

    # =========================
    # 功能 7：查看历史版本
    # =========================
    def show_history(self):
        self.refresh_history(silent=False)

    def refresh_history(self, silent=True):
        self.history_table.setRowCount(0)
        self.history_branch_list.clear()
        self.history_summary.setText("当前分支：-   远程状态：-   工作区状态：-")
        self.history_detail.setText("选中版本详情：-")
        self.log_commits = []
        self.selected_commit = None

        if not self.repo_path or not self.is_git_repo() or not self.has_commits():
            if not silent:
                self.show_info("历史版本", "暂无历史版本。")
            return False

        current_branch = self.current_branch()
        self.history_summary.setText(
            f"当前分支：{current_branch}   远程状态：{self.remote_status_text()}   工作区状态：{self.worktree_status_text()}"
        )

        local_branches = self.list_local_branches()
        remote_branches = self.list_remote_branches()

        self.history_branch_list.blockSignals(True)

        local_title = QListWidgetItem("本地分支")
        local_title.setForeground(QColor("#2B5748"))
        local_title.setFlags(local_title.flags() & ~Qt.ItemIsSelectable)
        self.history_branch_list.addItem(local_title)

        selected_row = None
        for branch in local_branches:
            label = f"> {branch}" if branch == current_branch else f"  {branch}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, branch)
            if branch == current_branch:
                item.setForeground(QColor("#2B5748"))
            self.history_branch_list.addItem(item)
            if branch == current_branch:
                selected_row = self.history_branch_list.count() - 1

        if remote_branches:
            remote_title = QListWidgetItem("远程分支")
            remote_title.setForeground(QColor("#2B5748"))
            remote_title.setFlags(remote_title.flags() & ~Qt.ItemIsSelectable)
            self.history_branch_list.addItem(remote_title)

            for branch in remote_branches:
                item = QListWidgetItem(f"  {branch}")
                item.setData(Qt.UserRole, branch)
                item.setForeground(QColor("#618764"))
                self.history_branch_list.addItem(item)

        self.history_branch_list.blockSignals(False)

        if selected_row is None and self.history_branch_list.count() > 1:
            selected_row = 1

        if selected_row is not None:
            self.history_branch_list.setCurrentRow(selected_row)
        else:
            self.populate_history_versions(current_branch)

        self.add_status("历史版本已刷新")

        if not silent:
            self.show_info("历史版本", "历史版本已刷新。\n左侧选择分支，右侧查看该分支的历史版本。")

        return True

    def populate_history_versions(self, branch_name):
        self.history_table.setRowCount(0)
        self.log_commits = []
        self.selected_commit = None
        self.history_detail.setText("选中版本详情：-")

        current_branch = self.current_branch()
        self.history_summary.setText(
            f"当前分支：{current_branch}   正在查看：{branch_name}   远程状态：{self.remote_status_text()}   工作区状态：{self.worktree_status_text()}"
        )

        ok_tip, tip = self.run_git(["rev-parse", "--short", branch_name], timeout=20)
        branch_tip = tip.strip() if ok_tip else ""

        ok, out = self.run_git(
            ["log", branch_name, "--date=short", "--pretty=format:%h|%ad|%an|%D|%s", "-60"],
            timeout=30
        )

        if not ok:
            self.show_error("查看历史版本失败", out)
            return False

        for line in out.splitlines():
            parts = line.split("|", 4)
            if len(parts) != 5:
                continue

            commit_id, date, author, refs, msg = parts
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            refs_display = refs.replace("HEAD -> ", "").replace("tag: ", "")
            is_current_version = commit_id == branch_tip and branch_name == current_branch
            is_branch_tip = commit_id == branch_tip
            status = "历史版本"
            if commit_id == branch_tip and branch_name == current_branch:
                status = "当前版本"
            elif commit_id == branch_tip:
                status = "分支最新"
            elif "origin/" in refs:
                status = "已上传"
            elif "tag: " in refs:
                status = "标签"

            values = [commit_id, date, status, msg]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col == 0:
                    item.setForeground(QColor("#2B5748"))
                elif col == 2:
                    if value == "当前版本":
                        item.setForeground(QColor("#2B5748"))
                    elif value in ("分支最新", "已上传"):
                        item.setForeground(QColor("#618764"))
                    elif value == "标签":
                        item.setForeground(QColor("#9CB080"))
                    else:
                        item.setForeground(QColor("#2B5748"))
                elif col == 3:
                    item.setForeground(QColor("#618764"))
                if is_current_version:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setBackground(QColor("#DDEFE6"))
                    item.setForeground(QColor("#1F3F35"))
                    if col == 2:
                        item.setBackground(QColor("#2B5748"))
                        item.setForeground(QColor("#FFFFFF"))
                elif is_branch_tip:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setBackground(QColor("#EEF4E8"))
                self.history_table.setItem(row, col, item)

            self.log_commits.append({
                "id": commit_id,
                "date": date,
                "author": author,
                "refs": refs_display,
                "msg": msg,
                "branch": branch_name,
                "status": status
            })

        return True

    def on_history_branch_selection_changed(self):
        items = self.history_branch_list.selectedItems()
        if not items:
            return

        branch_name = items[0].data(Qt.UserRole)
        if not branch_name:
            return

        self.populate_history_versions(branch_name)

    def on_history_selection_changed(self):
        rows = self.history_table.selectionModel().selectedRows()
        if not rows:
            self.selected_commit = None
            return

        row = rows[0].row()
        if 0 <= row < len(self.log_commits):
            info = self.log_commits[row]
            self.selected_commit = info["id"]
            detail = (
                "选中版本详情：\n"
                f"版本号：{info['id']}\n"
                f"时间：{info['date']}\n"
                f"作者：{info['author']}\n"
                f"所属分支：{info['branch']}\n"
                f"状态：{info['status']}\n"
                f"说明：{info['msg']}"
            )
            self.history_detail.setText(detail)
            self.add_status("已选择历史版本：" + self.selected_commit)

    # =========================
    # 功能 8：切换分支 / 从旧版本继续修改
    # =========================
    def continue_from_old_version(self):
        if not self.ask_repo():
            return False

        if not self.is_git_repo():
            self.show_info("提示", "当前项目还没有初始化 Git。")
            return False

        if not self.has_commits():
            self.show_info("提示", "当前项目暂无历史版本。")
            return False

        actions = ["切换到已有分支", "从历史版本修改"]
        action, ok = QInputDialog.getItem(
            self,
            "切换分支 / 旧版本修改",
            "请选择要执行的操作：",
            actions,
            0,
            False
        )

        if not ok or not action:
            return False

        if action == "切换到已有分支":
            branches = self.list_local_branches()
            current = self.current_branch()

            if not branches:
                self.show_info("切换分支", "当前没有本地分支可切换。")
                return False

            branch_name, ok = QInputDialog.getItem(
                self,
                "切换分支",
                f"当前分支：{current}\n\n请选择分支：",
                branches,
                0,
                False
            )

            if not ok or not branch_name:
                return False

            if not self.confirm_save_pending_changes(f"切换到分支 {branch_name}", allow_discard=True):
                return False

            ok, out = self.run_git(["switch", branch_name], timeout=60)
            if not ok:
                ok, out = self.run_git(["checkout", branch_name], timeout=60)

            if not ok:
                self.show_error("切换分支失败", out)
                return False

            self.add_status(f"已切换到分支最新版本：{branch_name}")
            self.refresh_history(silent=True)
            self.refresh_status(silent=True)
            self.show_info("完成", f"已切换到分支最新版本：\n{branch_name}")
            return True

        if not self.selected_commit:
            self.refresh_history(silent=True)
            self.show_info("提示", "请先在历史版本表格中选择一个版本。")
            return False

        modes = ["在当前分支直接修改（不新建分支）", "创建新分支后修改"]
        mode, ok = QInputDialog.getItem(
            self,
            "从旧版本继续修改",
            f"已选择历史版本：{self.selected_commit}\n\n请选择修改方式：",
            modes,
            0,
            False
        )

        if not ok or not mode:
            return False

        if not self.confirm_save_pending_changes("从旧版本继续修改"):
            return False

        if mode == "在当前分支直接修改（不新建分支）":
            ok, out = self.run_git(["branch", "--show-current"], timeout=10)
            current = out.strip() if ok else ""
            if not current:
                self.show_info("提示", "当前不在普通分支上，不能直接在当前分支修改。")
                return False

            choice = QMessageBox.question(
                self,
                "确认恢复旧版本",
                f"将把当前分支：\n{current}\n\n的工作区内容恢复为历史版本：\n{self.selected_commit}\n\n不会创建新分支，也不会移动分支指针。\n后续点击“保存版本”会在当前分支产生新提交。\n\n是否继续？",
                QMessageBox.Yes | QMessageBox.No
            )

            if choice != QMessageBox.Yes:
                return False

            ok, out = self.restore_commit_to_worktree(self.selected_commit)
            if not ok:
                self.show_error("恢复旧版本失败", out)
                return False

            self.add_status(f"已在当前分支恢复旧版本内容：{self.selected_commit}")
            self.refresh_history(silent=True)
            self.refresh_status(silent=True)
            self.show_info("完成", f"当前分支的工作区内容已恢复为旧版本 {self.selected_commit}。\n\n可以继续修改，确认后点击“保存版本”。")
            return True

        default_name = "from_old_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name, ok = QInputDialog.getText(
            self,
            "从旧版本继续修改",
            "请输入新的修改线名称：",
            QLineEdit.Normal,
            default_name
        )

        if not ok or not branch_name.strip():
            return False

        branch_name = safe_branch_name(branch_name)

        ok, out = self.run_git(["switch", "-c", branch_name, self.selected_commit], timeout=60)
        if not ok:
            ok, out = self.run_git(["checkout", "-b", branch_name, self.selected_commit], timeout=60)

        if not ok:
            self.show_error("创建新修改线失败", out)
            return False

        self.add_status(f"已从旧版本 {self.selected_commit} 创建新分支：{branch_name}")
        self.refresh_history(silent=True)
        self.refresh_status(silent=True)
        self.show_info("完成", f"已切换到旧版本的新修改线：\n{branch_name}\n\n现在可以在这个旧版本基础上继续修改。")
        return True

    # =========================
    # 功能 9：分支合并
    # =========================
    def merge_branch(self):
        if not self.ask_repo():
            return False

        if not self.is_git_repo():
            self.show_info("提示", "当前项目还没有初始化 Git。")
            return False

        if not self.has_commits():
            self.show_info("提示", "当前项目暂无历史版本，不能合并分支。")
            return False

        ok, out = self.run_git(["branch", "--show-current"], timeout=10)
        current = out.strip() if ok else ""
        if not current:
            self.show_info("提示", "当前不在普通分支上，暂时不能合并。")
            return False

        changes, err = self.get_changes_raw()
        if changes is None:
            self.show_error("分支合并失败", err)
            return False

        if changes.strip():
            choice = QMessageBox.question(
                self,
                "当前有未保存改动",
                "当前项目有未保存改动。\n\n是否先自动保存当前版本，再合并分支？",
                QMessageBox.Yes | QMessageBox.No
            )

            if choice != QMessageBox.Yes:
                return False

            if not self.save_version_auto():
                return False

        source_branches = self.list_merge_branches()
        target_branches = self.list_local_branches()
        if not source_branches or not target_branches:
            self.show_info("分支合并", "当前没有可合并的分支。")
            return False

        source_branch, ok = QInputDialog.getItem(
            self,
            "选择来源分支",
            "第 1 步：请选择来源分支 B\n\n这个分支的改动会被合并出去：",
            source_branches,
            0,
            False
        )

        if not ok or not source_branch:
            return False

        default_target_index = target_branches.index(current) if current in target_branches else 0
        target_branch, ok = QInputDialog.getItem(
            self,
            "选择目标分支",
            "第 2 步：请选择目标分支 A\n\n来源分支 B 会被合并到这个分支：",
            target_branches,
            default_target_index,
            False
        )

        if not ok or not target_branch:
            return False

        if source_branch == target_branch:
            self.show_info("分支合并", "来源分支和目标分支不能是同一个分支。")
            return False

        choice = QMessageBox.question(
            self,
            "确认合并",
            f"将把来源分支 B：\n{source_branch}\n\n合并到目标分支 A：\n{target_branch}\n\n当前分支：{current}\n确认后会先切换到目标分支 A，再执行合并。\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )

        if choice != QMessageBox.Yes:
            return False

        if current != target_branch:
            self.add_status(f"切换到目标分支：{target_branch}")
            ok, out = self.run_git(["switch", target_branch], timeout=60)
            if not ok:
                ok, out = self.run_git(["checkout", target_branch], timeout=60)

            if not ok:
                self.show_error("切换目标分支失败", out)
                return False

        self.add_status(f"开始合并分支：{source_branch} -> {target_branch}")
        ok, out = self.run_git(["merge", "--no-edit", source_branch], timeout=180)

        if not ok:
            self.set_operation_state("合并冲突", "error")
            self.refresh_status(silent=True)
            self.show_error(
                "分支合并失败",
                out + "\n\n如果提示存在冲突，需要手动处理冲突文件，处理完成后再保存版本。"
            )
            return False

        self.set_operation_state("完成", "ready")
        self.add_status(f"分支合并完成：{source_branch} -> {target_branch}")
        self.refresh_history(silent=True)
        self.refresh_status(silent=True)
        self.show_info("完成", f"已将来源分支 {source_branch} 合并到目标分支 {target_branch}。")
        return True

    # =========================
    # 功能 10：定时提醒上传代码
    # =========================
    def set_reminder(self):
        current = self.cfg.get("reminder_time", "18:00")
        text, ok = QInputDialog.getText(
            self,
            "定时提醒上传代码",
            "请输入每天提醒时间，例如 18:00\n\n留空并确定 = 关闭提醒",
            QLineEdit.Normal,
            current
        )

        if not ok:
            return

        text = text.strip()

        if not text:
            self.cfg["reminder_enabled"] = False
            save_config(self.cfg)
            self.add_status("已关闭定时提醒")
            self.show_info("完成", "已关闭定时提醒。")
            return

        if not re.match(r"^\d{2}:\d{2}$", text):
            self.show_error("格式错误", "时间格式应为 HH:MM，例如 18:00。")
            return

        hh, mm = map(int, text.split(":"))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            self.show_error("格式错误", "时间范围不正确。")
            return

        self.cfg["reminder_enabled"] = True
        self.cfg["reminder_time"] = text
        save_config(self.cfg)

        self.add_status(f"已开启定时提醒：每天 {text}")
        self.show_info("完成", f"已开启定时提醒：每天 {text}")

    def need_reminder(self):
        if not self.repo_path or not self.is_git_repo():
            return False

        changes, _ = self.get_changes_raw()
        if changes and changes.strip():
            return True

        return self.has_unpushed_commits()

    def check_reminder(self):
        self.cfg = load_config()

        if not self.cfg.get("reminder_enabled", False):
            return

        remind_time = self.cfg.get("reminder_time", "18:00")
        today = datetime.now().strftime("%Y-%m-%d")

        if datetime.now().strftime("%H:%M") != remind_time:
            return

        if self.cfg.get("last_remind_date") == today:
            return

        self.cfg["last_remind_date"] = today
        save_config(self.cfg)

        if self.need_reminder():
            self.add_status("提醒：当前项目有改动或未上传版本")
            QMessageBox.information(
                self,
                "代码上传提醒",
                "当前项目有改动或未上传版本。\n\n建议点击“一键保存并上传”。"
            )

    # =========================
    # 一键保存并上传
    # =========================
    def one_click_save_upload(self):
        if not self.ask_repo():
            return False

        if not self.is_git_repo():
            choice = QMessageBox.question(
                self,
                "初始化项目",
                "当前项目还不是 Git 项目。\n\n是否自动初始化？",
                QMessageBox.Yes | QMessageBox.No
            )

            if choice != QMessageBox.Yes:
                return False

            if not self.init_git_repo():
                return False

            self.set_operation_state("处理中", "busy")
        self.add_status("开始一键保存并上传")

        if not self.save_version_auto():
            self.set_operation_state("失败", "error")
            return False

        if not self.has_commits():
            self.set_operation_state("就绪", "ready")
            self.show_info("提示", "当前没有可上传的版本。\n请先修改代码后再保存上传。")
            return False

        if not self.ensure_remote_if_needed():
            self.set_operation_state("就绪", "ready")
            return False

        # 有 upstream 时先拉取，避免推送失败；首次上传时直接 push -u
        if self.has_upstream():
            ok, out = self.run_git(["pull", "--rebase", "--autostash"], timeout=180)
            if not ok:
                self.set_operation_state("失败", "error")
                self.show_error(
                    "获取云端最新版本失败",
                    out + "\n\n可能存在冲突，需要手动处理后再上传。"
                )
                return False

            self.add_status("已获取云端最新版本")

        ok, out = self.run_git(["push"], timeout=180)
        if not ok:
            branch = self.current_branch()
            ok, out = self.run_git(["push", "-u", "origin", branch], timeout=180)

        if not ok:
            self.set_operation_state("失败", "error")
            self.show_error(
                "上传失败",
                out + "\n\n常见原因：\n"
                "1. GitHub / Gitee 没有登录\n"
                "2. 远程仓库地址错误\n"
                "3. 云端有新版本或冲突\n"
                "4. 当前账号没有权限"
            )
            return False

        self.refresh_history(silent=True)
        self.set_operation_state("完成", "ready")
        self.add_status("一键保存并上传完成")
        self.show_info("完成", "代码已保存并上传到云端。")
        return True


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    icon_path = resource_path("app_icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
