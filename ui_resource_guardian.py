"""
ui_resource_guardian.py — Smart Resource Guardian UI components:
- ResourceSparkline: Compact 60-sample sparkline widget for the HUD telemetry column.
- ResourceDiagnosticsOverlay: Floating diagnostics, leak analysis, and profile manager.
"""
from __future__ import annotations

import math
import time
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QScrollArea
)

from theme import ThemeColors as C
from core.resource_guardian import (
    ResourceGuardian,
    PROFILE_LOW_RAM,
    PROFILE_BALANCED,
    PROFILE_FULL_EXPERIENCE,
    PROFILE_DISPLAY_NAMES,
)
from memory.config_manager import save_resource_profile


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


class ResourceSparkline(QWidget):
    """
    Compact 60-sample telemetry sparkline widget integrated into the HUD sidebar.
    Displays Process RAM (RSS in MB) trend over time with hover highlights.
    Clicking it opens the ResourceDiagnosticsOverlay.
    """

    def __init__(self, parent=None, on_click=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self.setMinimumWidth(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False
        self._on_click = on_click
        self._guardian = ResourceGuardian.get_instance()

    def enterEvent(self, _):
        self._hovered = True
        self.update()

    def leaveEvent(self, _):
        self._hovered = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and callable(self._on_click):
            self._on_click()
        super().mousePressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()

        # Background panel
        p.setBrush(QBrush(_qcol(C.PANEL2)))
        border_col = C.ACC if self._hovered else C.BORDER
        p.setPen(QPen(_qcol(border_col), 1.2 if self._hovered else 1.0))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        # Header label
        f_lbl = QFont("Courier New", 7, QFont.Weight.Bold)
        p.setFont(f_lbl)
        p.setPen(QPen(_qcol(C.PRI_DIM)))
        p.drawText(QRectF(6, 4, W - 12, 12), Qt.AlignmentFlag.AlignLeft, "APP RAM")

        history = self._guardian.get_history()
        cur_val = history[-1].process_rss_mb if history else self._guardian._read_rss_mb()
        cur_text = f"{cur_val:.0f}M"
        p.setPen(QPen(_qcol(C.PRI)))
        p.drawText(QRectF(6, 4, W - 12, 12), Qt.AlignmentFlag.AlignRight, cur_text)

        # Plot area
        chart_x = 6.0
        chart_y = 18.0
        chart_w = float(W - 12)
        chart_h = float(H - 22)

        if len(history) < 2:
            p.setPen(QPen(_qcol(C.TEXT_DIM)))
            p.setFont(QFont("Courier New", 6))
            p.drawText(QRectF(chart_x, chart_y, chart_w, chart_h),
                       Qt.AlignmentFlag.AlignCenter, "SAMPLING...")
            return

        values = [s.process_rss_mb for s in history]
        min_v = min(values)
        max_v = max(values)
        span = max(10.0, max_v - min_v)

        n = len(values)
        dx = chart_w / max(1, n - 1)

        path = QPainterPath()
        points: list[QPointF] = []

        for i, val in enumerate(values):
            norm = (val - min_v) / span
            px = chart_x + i * dx
            py = (chart_y + chart_h) - (norm * (chart_h - 2)) - 1
            pt = QPointF(px, py)
            points.append(pt)
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)

        # Area fill
        fill_path = QPainterPath(path)
        fill_path.lineTo(chart_x + (n - 1) * dx, chart_y + chart_h)
        fill_path.lineTo(chart_x, chart_y + chart_h)
        fill_path.closeSubpath()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(_qcol(C.PRI_GHO)))
        p.drawPath(fill_path)

        # Trace stroke
        trace_col = C.ACC if self._hovered else C.PRI
        p.setPen(QPen(_qcol(trace_col), 1.3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


class ResourceDiagnosticsOverlay(QWidget):
    """
    Floating resource guardian diagnostics overlay.
    Subclasses QWidget (acts like _HudOverlay) and repaints HUD background when closed.
    """

    _OW = 580
    _OH = 530

    def __init__(self, parent=None, on_profile_changed=None):
        super().__init__(parent)
        self.setFixedSize(self._OW, self._OH)
        self._on_profile_changed = on_profile_changed
        self._guardian = ResourceGuardian.get_instance()
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

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
            e.accept()
        else:
            super().keyPressEvent(e)

    def _init_ui(self):
        self.setStyleSheet(f"""
            QWidget {{
                background: rgba(3, 14, 26, 0.98);
                color: {C.TEXT};
                font-family: 'Courier New';
            }}
        """)

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(14, 12, 14, 12)
        main_lay.setSpacing(8)

        # ── Header ───────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        title_lbl = QLabel("◈ RESOURCE GUARDIAN & DIAGNOSTICS")
        title_lbl.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {C.BRASS_BRIGHT}; background: transparent; border: none;")
        hdr_row.addWidget(title_lbl)

        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2}; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.RED}; color: white; border-color: {C.RED};
            }}
        """)
        close_btn.clicked.connect(self.hide)
        hdr_row.addWidget(close_btn)
        main_lay.addLayout(hdr_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        main_lay.addWidget(sep)

        # ── Profile Selector ──────────────────────────────────────────────────
        prof_box = QWidget()
        prof_box.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        pb_lay = QVBoxLayout(prof_box)
        pb_lay.setContentsMargins(8, 6, 8, 6)
        pb_lay.setSpacing(4)

        pb_hdr = QLabel("RESOURCE PROFILE")
        pb_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        pb_hdr.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; border: none;")
        pb_lay.addWidget(pb_hdr)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        self._prof_btns: dict[str, QPushButton] = {}

        for pid, label in [
            (PROFILE_LOW_RAM, "LOW RAM"),
            (PROFILE_BALANCED, "BALANCED"),
            (PROFILE_FULL_EXPERIENCE, "FULL EXPERIENCE"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, p=pid: self._select_profile(p))
            btn_row.addWidget(b)
            self._prof_btns[pid] = b

        pb_lay.addLayout(btn_row)

        self._prof_desc_lbl = QLabel()
        self._prof_desc_lbl.setFont(QFont("Courier New", 7))
        self._prof_desc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        self._prof_desc_lbl.setWordWrap(True)
        pb_lay.addWidget(self._prof_desc_lbl)

        main_lay.addWidget(prof_box)

        # ── Scrollable Diagnostics Content ────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: transparent; border: none;")
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        c_lay = QVBoxLayout(content)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(8)

        # 1. Live Metrics Grid
        grid_w = QWidget()
        grid_w.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        glay = QGridLayout(grid_w)
        glay.setContentsMargins(8, 6, 8, 6)
        glay.setSpacing(6)

        self._lbl_proc_ram = QLabel()
        self._lbl_sys_ram = QLabel()
        self._lbl_cpu = QLabel()
        self._lbl_state = QLabel()

        for col_idx, (title, lbl) in enumerate([
            ("JARVIS PROCESS RAM", self._lbl_proc_ram),
            ("SYSTEM RAM (OS)", self._lbl_sys_ram),
            ("CPU UTILISATION", self._lbl_cpu),
            ("RUNTIME STATE", self._lbl_state),
        ]):
            box = QWidget()
            box.setStyleSheet("background: rgba(3, 14, 24, 0.6); border: 1px solid rgba(212, 175, 55, 0.2); border-radius: 3px;")
            b_lay = QVBoxLayout(box)
            b_lay.setContentsMargins(6, 4, 6, 4)
            b_lay.setSpacing(2)

            th = QLabel(title)
            th.setFont(QFont("Courier New", 6, QFont.Weight.Bold))
            th.setStyleSheet(f"color: {C.PRI_DIM}; border: none; background: transparent;")
            b_lay.addWidget(th)

            lbl.setFont(QFont("Courier New", 7))
            lbl.setStyleSheet(f"color: {C.WHITE}; border: none; background: transparent;")
            lbl.setWordWrap(True)
            b_lay.addWidget(lbl)

            glay.addWidget(box, col_idx // 2, col_idx % 2)

        c_lay.addWidget(grid_w)

        # 2. Leak Diagnostics & Recommendation
        leak_box = QWidget()
        leak_box.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        lb_lay = QVBoxLayout(leak_box)
        lb_lay.setContentsMargins(8, 6, 8, 6)
        lb_lay.setSpacing(3)

        self._leak_status_lbl = QLabel("◈ MEMORY HEALTH: ANALYZING...")
        self._leak_status_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._leak_status_lbl.setStyleSheet(f"color: {C.GREEN}; border: none; background: transparent;")
        lb_lay.addWidget(self._leak_status_lbl)

        self._leak_rec_lbl = QLabel()
        self._leak_rec_lbl.setFont(QFont("Courier New", 7))
        self._leak_rec_lbl.setStyleSheet(f"color: {C.TEXT_MED}; border: none; background: transparent;")
        self._leak_rec_lbl.setWordWrap(True)
        lb_lay.addWidget(self._leak_rec_lbl)
        c_lay.addWidget(leak_box)

        # 3. Startup & Module Breakdown
        start_box = QWidget()
        start_box.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        sb_lay = QVBoxLayout(start_box)
        sb_lay.setContentsMargins(8, 6, 8, 6)
        sb_lay.setSpacing(3)

        sb_hdr = QLabel("STARTUP BREAKDOWN & OPTIONAL MODULES")
        sb_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        sb_hdr.setStyleSheet(f"color: {C.PRI_DIM}; border: none; background: transparent;")
        sb_lay.addWidget(sb_hdr)

        self._startup_lbl = QLabel()
        self._startup_lbl.setFont(QFont("Courier New", 7))
        self._startup_lbl.setStyleSheet(f"color: {C.TEXT}; border: none; background: transparent;")
        self._startup_lbl.setWordWrap(True)
        sb_lay.addWidget(self._startup_lbl)
        c_lay.addWidget(start_box)

        # 4. Background Workers
        work_box = QWidget()
        work_box.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        wb_lay = QVBoxLayout(work_box)
        wb_lay.setContentsMargins(8, 6, 8, 6)
        wb_lay.setSpacing(3)

        wb_hdr = QLabel("ACTIVE BACKGROUND WORKERS")
        wb_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        wb_hdr.setStyleSheet(f"color: {C.PRI_DIM}; border: none; background: transparent;")
        wb_lay.addWidget(wb_hdr)

        self._workers_lbl = QLabel()
        self._workers_lbl.setFont(QFont("Courier New", 7))
        self._workers_lbl.setStyleSheet(f"color: {C.TEXT}; border: none; background: transparent;")
        self._workers_lbl.setWordWrap(True)
        wb_lay.addWidget(self._workers_lbl)
        c_lay.addWidget(work_box)

        scroll.setWidget(content)
        main_lay.addWidget(scroll, stretch=1)

        self.refresh()

    def _select_profile(self, profile: str):
        clean = self._guardian.set_profile(profile)
        save_resource_profile(clean)
        if callable(self._on_profile_changed):
            try:
                self._on_profile_changed(clean)
            except Exception:
                pass
        self.refresh()

    def refresh(self):
        """Update all telemetry and diagnostic fields."""
        cur_prof = self._guardian.get_profile()

        # Update profile buttons
        desc_map = {
            PROFILE_LOW_RAM: "LOW RAM: Nonessential particles paused, telemetry slowed to 5s, optional AI models deferred.",
            PROFILE_BALANCED: "BALANCED: Full visualizer ribbons, responsive voice interaction, 2s telemetry interval.",
            PROFILE_FULL_EXPERIENCE: "FULL EXPERIENCE: Maximum particle count, unconstrained visualizer fidelity, 1.5s telemetry.",
        }
        self._prof_desc_lbl.setText(desc_map.get(cur_prof, ""))

        for pid, btn in self._prof_btns.items():
            if pid == cur_prof:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(212, 175, 55, 0.35), stop:1 rgba(0, 229, 255, 0.25));
                        color: #ffffff; border: 1.5px solid {C.BRASS_BRIGHT}; border-radius: 3px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(4, 18, 30, 0.70); color: {C.TEXT_MED};
                        border: 1px solid rgba(212, 175, 55, 0.22); border-radius: 3px;
                    }}
                    QPushButton:hover {{
                        background: rgba(212, 175, 55, 0.15); color: {C.BRASS_BRIGHT};
                    }}
                """)

        # Analyze memory
        diag = self._guardian.analyze_memory()
        history = self._guardian.get_history()
        latest = history[-1] if history else None

        # Metrics
        p_rss = diag["current_rss_mb"]
        p_base = diag["baseline_rss_mb"]
        p_peak = diag["peak_rss_mb"]
        p_delta = diag["delta_from_baseline_mb"]
        sign = "+" if p_delta >= 0 else ""
        self._lbl_proc_ram.setText(f"RSS: {p_rss:.1f} MB (Delta: {sign}{p_delta:.1f} MB)\nPeak: {p_peak:.1f} MB | Boot: {p_base:.1f} MB")

        if latest:
            self._lbl_sys_ram.setText(f"{latest.system_ram_percent:.0f}% Used\n{latest.system_ram_available_gb:.1f} GB Free of {latest.system_ram_total_gb:.1f} GB")
            self._lbl_cpu.setText(f"JARVIS App: {latest.process_cpu_percent:.1f}%\nTotal System: {latest.system_cpu_percent:.1f}%")
            self._lbl_state.setText(f"Status: {latest.state}\nSamples: {len(history)} / 60")
        else:
            self._lbl_sys_ram.setText("Measuring...")
            self._lbl_cpu.setText("Measuring...")
            self._lbl_state.setText("IDLE")

        # Health status
        st = diag["growth_status"]
        if st == "SUSTAINED_GROWTH":
            col = C.RED
            lbl = "⚠️ SUSTAINED GROWTH DETECTED"
        elif st == "MODERATE_ELEVATION":
            col = C.ACC
            lbl = "⚡ MODERATE MEMORY FLUCTUATION"
        else:
            col = C.GREEN
            lbl = "✓ MEMORY STABLE & HEALTHY"

        self._leak_status_lbl.setText(f"◈ {lbl} ({diag['growth_rate_mb_min']:+.2f} MB/min)")
        self._leak_status_lbl.setStyleSheet(f"color: {col}; border: none; background: transparent;")
        self._leak_rec_lbl.setText(diag["recommendation"])

        # Startup summary
        st_sum = self._guardian.startup_tracker.get_summary()
        stages_str = " | ".join(f"{s['name']}: {s['duration_s']}s" for s in st_sum["stages"]) if st_sum["stages"] else "Initialized"
        mods_str = ", ".join(f"{m} ({st})" for m, st in st_sum["optional_modules"].items())
        self._startup_lbl.setText(f"Stages: {stages_str}\nOptional Modules: {mods_str}")

        # Workers
        workers = self._guardian.get_workers_status()
        if workers:
            w_lines = [f"• {w['name']}: {'ALIVE' if w['is_alive'] else 'STOPPED'} ({w['description']})" for w in workers]
            self._workers_lbl.setText("\n".join(w_lines))
        else:
            self._workers_lbl.setText("• Main Qt Thread\n• Telemetry Poller (sys_metrics)\n• Asyncio Core Runner")
