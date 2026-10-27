"""
ui_command_palette.py — Smart Command Palette overlay for JARVIS:
- Opened via Ctrl+K shortcut or UI trigger.
- Instant search, keyboard navigation (Up/Down/Enter/Escape), MRU history,
  and safe dispatch across system controls, views, profiles, actions, and plugins.
- Non-interrupting to active voice conversations.
"""
from __future__ import annotations

from typing import Optional, Callable

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QFrame, QPushButton
)

from theme import ThemeColors as C
from core.command_palette import CommandPaletteRegistry, CommandItem


def _qcol(h: str, a: int = 255) -> QColor:
    if not h:
        return QColor(0, 0, 0, a)
    s = str(h).strip()
    if s.startswith("rgba"):
        try:
            parts = s.replace("rgba(", "").replace(")", "").split(",")
            r, g, b = int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip())
            alpha = int(float(parts[3].strip()) * 255) if len(parts) > 3 else a
            return QColor(r, g, b, alpha)
        except Exception:
            return QColor(0, 0, 0, a)
    return QColor(s)


class CommandItemWidget(QWidget):
    """Custom styled item widget for each command palette entry."""

    def __init__(self, item: CommandItem, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setStyleSheet("background: transparent;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(8)

        # Category pill
        cat_color = {
            "RECENT":  C.BRASS_BRIGHT,
            "PROFILE": C.GREEN,
            "ACTION":  C.PRI,
            "PLUGIN":  "#00b4d8",
            "VIEW":    C.TEXT_MED,
            "SYSTEM":  C.BRASS,
        }.get(item.category, C.TEXT_DIM)

        cat_lbl = QLabel(f"[{item.category}]")
        cat_lbl.setFont(QFont("Courier New", 6, QFont.Weight.Bold))
        cat_lbl.setStyleSheet(f"color: {cat_color}; background: rgba(0, 0, 0, 0.4); padding: 2px 4px; border-radius: 2px;")
        lay.addWidget(cat_lbl)

        # Title and description
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(1)

        title_lbl = QLabel(item.title)
        title_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent; border: none;")
        info_col.addWidget(title_lbl)

        if item.description:
            desc_lbl = QLabel(item.description)
            desc_lbl.setFont(QFont("Courier New", 6))
            desc_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
            info_col.addWidget(desc_lbl)

        lay.addLayout(info_col, stretch=1)

        # Shortcut badge if any
        if item.shortcut:
            sc_lbl = QLabel(item.shortcut)
            sc_lbl.setFont(QFont("Courier New", 6, QFont.Weight.Bold))
            sc_lbl.setStyleSheet(f"color: {C.ACC}; background: {C.PANEL2}; border: 1px solid {C.BORDER}; padding: 2px 5px; border-radius: 3px;")
            lay.addWidget(sc_lbl)


class CommandPaletteOverlay(QWidget):
    """
    Smart Command Palette overlay opened with Ctrl+K.
    Keyboard navigation:
      Up/Down: move selection in results
      Enter: execute selected command
      Escape: close palette
    """

    _OW = 560
    _OH = 370

    def __init__(self, registry: CommandPaletteRegistry, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._OW, self._OH)
        self._registry = registry
        self._current_items: list[CommandItem] = []
        self._init_ui()

    def hideEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().hideEvent(e)

    def closeEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().closeEvent(e)

    def _init_ui(self):
        self.setStyleSheet(f"""
            QWidget#CommandPalette {{
                background: rgba(3, 14, 26, 0.98);
                border: 1.5px solid {C.PRI};
                border-radius: 6px;
            }}
        """)
        self.setObjectName("CommandPalette")

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(10, 10, 10, 8)
        main_lay.setSpacing(6)

        # Search Bar
        search_box = QWidget()
        search_box.setStyleSheet(f"""
            background: #000c14;
            border: 1px solid rgba(0, 229, 255, 0.4);
            border-radius: 4px;
        """)
        s_lay = QHBoxLayout(search_box)
        s_lay.setContentsMargins(8, 4, 8, 4)
        s_lay.setSpacing(6)

        icon_lbl = QLabel("◈")
        icon_lbl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        s_lay.addWidget(icon_lbl)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or search... (Esc to close)")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {C.WHITE};
                border: none;
                selection-background-color: {C.PRI_DIM};
            }}
        """)
        self._input.textChanged.connect(self._on_search_changed)
        s_lay.addWidget(self._input, stretch=1)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(18, 18)
        close_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED}; border: none;
            }}
            QPushButton:hover {{
                color: {C.RED};
            }}
        """)
        close_btn.clicked.connect(self.hide)
        s_lay.addWidget(close_btn)

        main_lay.addWidget(search_box)

        # Results List
        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keep focus in input
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                outline: none;
            }}
            QListWidget::item {{
                background: transparent;
                border-bottom: 1px solid rgba(212, 175, 55, 0.1);
                padding: 0px;
            }}
            QListWidget::item:selected {{
                background: rgba(0, 229, 255, 0.18);
                border-left: 2px solid {C.PRI};
            }}
            QListWidget::item:hover {{
                background: rgba(212, 175, 55, 0.12);
            }}
        """)
        self._list.itemDoubleClicked.connect(lambda _: self._execute_selected())
        main_lay.addWidget(self._list, stretch=1)

        # Footer Hint
        hint_row = QHBoxLayout()
        hint_lbl = QLabel("↑↓ Navigate  •  ↵ Execute  •  ESC Close  •  Ctrl+K Toggle")
        hint_lbl.setFont(QFont("Courier New", 7))
        hint_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hint_row.addWidget(hint_lbl)
        main_lay.addLayout(hint_row)

        self.installEventFilter(self)
        self._input.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.hide()
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._execute_selected()
                return True
            elif key == Qt.Key.Key_Down:
                cur = self._list.currentRow()
                nxt = min(self._list.count() - 1, cur + 1)
                self._list.setCurrentRow(nxt)
                return True
            elif key == Qt.Key.Key_Up:
                cur = self._list.currentRow()
                nxt = max(0, cur - 1)
                self._list.setCurrentRow(nxt)
                return True
        return super().eventFilter(obj, event)

    def show_palette(self):
        """Show palette, reset input, and focus."""
        self._input.clear()
        self._refresh_list("")
        self.show()
        self.raise_()
        self._input.setFocus()

    def _on_search_changed(self, text: str):
        self._refresh_list(text)

    def _refresh_list(self, query: str):
        self._list.clear()
        self._current_items = self._registry.filter_commands(query)

        for item in self._current_items:
            widget = CommandItemWidget(item)
            list_item = QListWidgetItem(self._list)
            list_item.setSizeHint(widget.sizeHint())
            self._list.addItem(list_item)
            self._list.setItemWidget(list_item, widget)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _execute_selected(self):
        cur_row = self._list.currentRow()
        if 0 <= cur_row < len(self._current_items):
            item = self._current_items[cur_row]
            self.hide()
            self._registry.execute(item.id)
