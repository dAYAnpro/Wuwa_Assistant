import os
import sys
import time
import threading
import subprocess
import ctypes
from ctypes import wintypes
import winsound
import json

import cv2
import numpy as np
import mss
import customtkinter as ctk

from parser import EchoParser
from storage import EchoStorage
from hotkey_manager import WindowsHotkeyListener, VK_MAP

# Ensure Per-Monitor DPI awareness for proper coordinate translation
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

def is_admin() -> bool:
    """Check if the current process has Windows Administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def restart_as_admin():
    """Relaunch the current script with elevated Administrator privileges."""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(f'"{arg}"' for arg in sys.argv), None, 1
    )
    sys.exit(0)

def get_foreground_window_rect(sct):
    """Safely get clamped coordinates of active window."""
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    if w <= 100 or h <= 100:
        return None

    all_mon = sct.monitors[0]
    left = max(all_mon["left"], rect.left)
    top = max(all_mon["top"], rect.top)
    right = min(all_mon["left"] + all_mon["width"], rect.right)
    bottom = min(all_mon["top"] + all_mon["height"], rect.bottom)

    clamped_w = right - left
    clamped_h = bottom - top

    if clamped_w <= 100 or clamped_h <= 100:
        return None

    return {"top": top, "left": left, "width": clamped_w, "height": clamped_h}

def capture_screen_panel(sct):
    """Capture the right-hand panel of active game window or primary monitor."""
    win_rect = get_foreground_window_rect(sct)
    if win_rect:
        try:
            sct_img = sct.grab(win_rect)
        except Exception:
            sct_img = sct.grab(sct.monitors[1])
    else:
        sct_img = sct.grab(sct.monitors[1])

    img = np.array(sct_img)[:, :, :3]
    h, w, _ = img.shape

    aspect = w / max(1, h)
    if aspect > 1.85: # Ultrawide
        panel_w = int(h * (16 / 9) * 0.35)
        crop_x = max(0, w - panel_w)
    else:
        crop_x = int(w * 0.65)

    return img[:, crop_x:]

class EchoCard(ctk.CTkFrame):
    """Visual widget representing a single scanned Echo."""
    def __init__(self, master, echo_data, **kwargs):
        super().__init__(master, fg_color="#23242A", corner_radius=10, **kwargs)
        self.echo_data = echo_data
        self._build_ui()

    def _build_ui(self):
        # Header Row
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=14, pady=(12, 6))

        # Echo Name
        name_lbl = ctk.CTkLabel(
            header_frame,
            text=self.echo_data.get("name", "Unknown Echo"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#F3F4F6",
            anchor="w"
        )
        name_lbl.pack(side="left", fill="x", expand=True)

        # Cost Badge
        cost = self.echo_data.get("cost", 0)
        cost_colors = {4: ("#FEF08A", "#854D0E"), 3: ("#E9D5FF", "#6B21A8"), 1: ("#CFFAFE", "#155E75")}
        fg_col, txt_col = cost_colors.get(cost, ("#374151", "#9CA3AF"))
        cost_badge = ctk.CTkLabel(
            header_frame,
            text=f"COST {cost}",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=fg_col,
            text_color=txt_col,
            corner_radius=6,
            padx=8,
            pady=2
        )
        cost_badge.pack(side="right", padx=(6, 0))

        # Level Badge
        lvl = self.echo_data.get("level", 0)
        lvl_badge = ctk.CTkLabel(
            header_frame,
            text=f"+{lvl}",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#065F46",
            text_color="#6EE7B7",
            corner_radius=6,
            padx=8,
            pady=2
        )
        lvl_badge.pack(side="right", padx=(6, 0))

        # Sonata Row
        sonata_frame = ctk.CTkFrame(self, fg_color="transparent")
        sonata_frame.pack(fill="x", padx=14, pady=(0, 6))
        sonata_lbl = ctk.CTkLabel(
            sonata_frame,
            text=f"Set: {self.echo_data.get('sonata', 'Unknown')}",
            font=ctk.CTkFont(size=12),
            text_color="#9CA3AF",
            anchor="w"
        )
        sonata_lbl.pack(side="left")

        # Stats Separator
        sep = ctk.CTkFrame(self, height=1, fg_color="#374151")
        sep.pack(fill="x", padx=14, pady=4)

        # Main & Substats Body
        body_frame = ctk.CTkFrame(self, fg_color="transparent")
        body_frame.pack(fill="x", padx=14, pady=6)

        # Left Column: Main Stats
        main_col = ctk.CTkFrame(body_frame, fg_color="transparent")
        main_col.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            main_col, text="MAIN STATS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#60A5FA", anchor="w"
        ).pack(anchor="w")

        main_dict = self.echo_data.get("main_stats", {})
        for stat, val in main_dict.items():
            ctk.CTkLabel(
                main_col, text=f"• {stat}: {val}", font=ctk.CTkFont(size=12), text_color="#E5E7EB", anchor="w"
            ).pack(anchor="w")

        # Right Column: Sub-stats
        sub_col = ctk.CTkFrame(body_frame, fg_color="transparent")
        sub_col.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(
            sub_col, text="SUB-STATS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#34D399", anchor="w"
        ).pack(anchor="w")

        sub_dict = self.echo_data.get("sub_stats", {})
        for stat, val in sub_dict.items():
            ctk.CTkLabel(
                sub_col, text=f"• {stat}: {val}", font=ctk.CTkFont(size=12), text_color="#D1D5DB", anchor="w"
            ).pack(anchor="w")

        # Footer Row (CV & Timestamp)
        footer_frame = ctk.CTkFrame(self, fg_color="transparent")
        footer_frame.pack(fill="x", padx=14, pady=(4, 10))

        # CV Badge
        cv_val = self.echo_data.get("crit_value", {}).get("substats_cv", 0.0)
        total_cv = self.echo_data.get("crit_value", {}).get("total_cv", 0.0)

        if cv_val >= 35.0:
            cv_bg, cv_fg, cv_rank = "#78350F", "#FDE68A", "GOD ROLL"
        elif cv_val >= 25.0:
            cv_bg, cv_fg, cv_rank = "#581C87", "#E9D5FF", "GREAT"
        elif cv_val >= 15.0:
            cv_bg, cv_fg, cv_rank = "#1E3A8A", "#BFDBFE", "DECENT"
        else:
            cv_bg, cv_fg, cv_rank = "#374151", "#9CA3AF", "LOW"

        cv_pill = ctk.CTkLabel(
            footer_frame,
            text=f"CV: {cv_val} ({cv_rank})  |  Total CV: {total_cv}",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=cv_bg,
            text_color=cv_fg,
            corner_radius=6,
            padx=10,
            pady=3
        )
        cv_pill.pack(side="left")

        time_lbl = ctk.CTkLabel(
            footer_frame,
            text=self.echo_data.get("scanned_at", ""),
            font=ctk.CTkFont(size=11),
            text_color="#6B7280"
        )
        time_lbl.pack(side="right")


class WuWaScannerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Appearance & Geometry
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Wuthering Waves Echo Scanner")
        self.geometry("980x720")
        self.minsize(860, 600)

        # Core Components
        self.storage = EchoStorage("echoes.json")
        self.parser = EchoParser()
        self.sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
        self.is_scanning = False
        self.is_paused = False
        self.sound_enabled = True
        self.current_hotkey = "F8"
        self.min_level = 1

        # Hotkey listener using Windows kernel API
        self.hotkey_listener = WindowsHotkeyListener(
            key_name=self.current_hotkey, callback=self.on_hotkey_triggered
        )
        self.hotkey_listener.start()

        # Build Layout
        self._build_layout()
        self._load_echo_cards()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_layout(self):
        # 2-Column Grid: Left Sidebar (Controls) & Right Main (Echo Feed)
        self.grid_columnconfigure(0, weight=0, minsize=310)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT SIDEBAR ---
        sidebar = ctk.CTkFrame(self, fg_color="#18191E", corner_radius=0, width=310)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        sidebar.grid_propagate(False)

        # App Title
        title_box = ctk.CTkFrame(sidebar, fg_color="transparent")
        title_box.pack(fill="x", padx=18, pady=(20, 10))
        ctk.CTkLabel(
            title_box, text="🌊 WuWa Scanner", font=ctk.CTkFont(size=20, weight="bold"), text_color="#38BDF8"
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box, text="Autonomous Echo OCR Tool", font=ctk.CTkFont(size=12), text_color="#64748B"
        ).pack(anchor="w")

        # Admin Badge
        admin_frame = ctk.CTkFrame(sidebar, fg_color="#202229", corner_radius=8)
        admin_frame.pack(fill="x", padx=18, pady=8)

        if is_admin():
            ctk.CTkLabel(
                admin_frame,
                text="🛡️ Administrator Mode: ACTIVE",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#4ADE80",
                padx=10,
                pady=8
            ).pack(anchor="w")
        else:
            ctk.CTkLabel(
                admin_frame,
                text="⚠️ Standard Mode (Game scope may block)",
                font=ctk.CTkFont(size=11),
                text_color="#FBBF24",
                padx=10,
                pady=6
            ).pack(anchor="w", pady=(2, 0))
            ctk.CTkButton(
                admin_frame,
                text="⚡ Restart as Admin",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#D97706",
                hover_color="#B45309",
                height=26,
                command=restart_as_admin
            ).pack(fill="x", padx=10, pady=(2, 8))

        # Status Display Box
        self.status_box = ctk.CTkFrame(sidebar, fg_color="#1E293B", corner_radius=8)
        self.status_box.pack(fill="x", padx=18, pady=8)

        self.status_dot = ctk.CTkLabel(
            self.status_box,
            text="● LISTENING FOR " + self.current_hotkey,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38BDF8"
        )
        self.status_dot.pack(padx=12, pady=10)

        # Settings Section
        settings_label = ctk.CTkLabel(
            sidebar, text="SETTINGS", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748B"
        )
        settings_label.pack(anchor="w", padx=20, pady=(12, 4))

        # Hotkey Selector
        hk_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        hk_frame.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(hk_frame, text="Scan Hotkey:", font=ctk.CTkFont(size=13), text_color="#D1D5DB").pack(side="left")
        self.hk_combo = ctk.CTkComboBox(
            hk_frame,
            values=["F8", "F9", "F10", "F11", "F12", "INSERT", "HOME", "END"],
            width=110,
            command=self.on_hotkey_changed
        )
        self.hk_combo.set("F8")
        self.hk_combo.pack(side="right")

        # Min Level Filter
        lvl_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        lvl_frame.pack(fill="x", padx=18, pady=4)
        ctk.CTkLabel(lvl_frame, text="Min Level:", font=ctk.CTkFont(size=13), text_color="#D1D5DB").pack(side="left")
        self.lvl_combo = ctk.CTkComboBox(
            lvl_frame,
            values=["+1 (Skip +0)", "+5", "+10", "+15", "+20", "+25", "All (+0 included)"],
            width=130,
            command=self.on_min_level_changed
        )
        self.lvl_combo.set("+1 (Skip +0)")
        self.lvl_combo.pack(side="right")

        # Sound Feedback Switch
        self.sound_switch = ctk.CTkSwitch(
            sidebar,
            text="Audio Chimes",
            font=ctk.CTkFont(size=13),
            command=self.on_sound_toggled
        )
        self.sound_switch.select()
        self.sound_switch.pack(anchor="w", padx=20, pady=8)

        # Always On Top Switch
        self.ontop_switch = ctk.CTkSwitch(
            sidebar,
            text="Always on Top",
            font=ctk.CTkFont(size=13),
            command=self.on_ontop_toggled
        )
        self.ontop_switch.pack(anchor="w", padx=20, pady=4)

        # Action Buttons
        btn_sep = ctk.CTkFrame(sidebar, height=1, fg_color="#2D3039")
        btn_sep.pack(fill="x", padx=18, pady=12)

        self.scan_now_btn = ctk.CTkButton(
            sidebar,
            text="📸 Scan Active Game Now",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0284C7",
            hover_color="#0369A1",
            height=36,
            command=self.trigger_manual_scan
        )
        self.scan_now_btn.pack(fill="x", padx=18, pady=4)

        self.pause_btn = ctk.CTkButton(
            sidebar,
            text="⏸️ Pause Hotkey",
            font=ctk.CTkFont(size=13),
            fg_color="#334155",
            hover_color="#475569",
            height=34,
            command=self.toggle_pause
        )
        self.pause_btn.pack(fill="x", padx=18, pady=4)

        # File & Management Buttons
        ctk.CTkButton(
            sidebar,
            text="📂 Open echoes.json",
            font=ctk.CTkFont(size=12),
            fg_color="#1E293B",
            hover_color="#334155",
            height=32,
            command=self.open_json_file
        ).pack(fill="x", padx=18, pady=4)

        ctk.CTkButton(
            sidebar,
            text="📁 Open Folder",
            font=ctk.CTkFont(size=12),
            fg_color="#1E293B",
            hover_color="#334155",
            height=32,
            command=self.open_folder
        ).pack(fill="x", padx=18, pady=4)

        ctk.CTkButton(
            sidebar,
            text="🗑️ Clear Saved Echoes",
            font=ctk.CTkFont(size=12),
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            height=32,
            command=self.clear_all_echoes
        ).pack(fill="x", padx=18, pady=(4, 16))

        # --- RIGHT MAIN AREA ---
        main_frame = ctk.CTkFrame(self, fg_color="#0F1015", corner_radius=0)
        main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Top Bar
        top_bar = ctk.CTkFrame(main_frame, fg_color="#18191E", height=60, corner_radius=0)
        top_bar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            top_bar,
            placeholder_text="🔍 Filter by name, stat, sonata, cost...",
            width=320,
            height=36,
            fg_color="#202229",
            border_color="#374151"
        )
        self.search_entry.pack(side="left", padx=18, pady=12)
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_cards())

        # Counters Badge
        self.counter_lbl = ctk.CTkLabel(
            top_bar,
            text=f"Total: {self.storage.count()} Echoes",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#94A3B8"
        )
        self.counter_lbl.pack(side="right", padx=18)

        # Scrollable Feed
        self.feed = ctk.CTkScrollableFrame(
            main_frame,
            fg_color="transparent",
            label_text="Scanned Echoes Feed",
            label_font=ctk.CTkFont(size=13, weight="bold"),
            label_text_color="#94A3B8"
        )
        self.feed.grid(row=1, column=0, sticky="nsew", padx=16, pady=12)

    def _load_echo_cards(self):
        """Populate feed with stored echoes from JSON."""
        for widget in self.feed.winfo_children():
            widget.destroy()

        echoes = list(reversed(self.storage.echoes))
        for echo in echoes:
            card = EchoCard(self.feed, echo)
            card.pack(fill="x", pady=6)

        self.counter_lbl.configure(text=f"Total: {self.storage.count()} Echoes")

    def _filter_cards(self):
        """Filter echo feed in real-time as user types."""
        query = self.search_entry.get().strip().lower()
        for widget in self.feed.winfo_children():
            if isinstance(widget, EchoCard):
                data = widget.echo_data
                name = data.get("name", "").lower()
                sonata = data.get("sonata", "").lower()
                cost_str = f"cost {data.get('cost', '')}".lower()
                stats_str = " ".join([f"{k} {v}" for k, v in data.get("main_stats", {}).items()]).lower()
                sub_str = " ".join([f"{k} {v}" for k, v in data.get("sub_stats", {}).items()]).lower()

                full_text = f"{name} {sonata} {cost_str} {stats_str} {sub_str}"
                if query in full_text:
                    widget.pack(fill="x", pady=6)
                else:
                    widget.pack_forget()

    def on_hotkey_triggered(self):
        """Callback from background hardware listener."""
        if self.is_paused or self.is_scanning:
            return
        threading.Thread(target=self._execute_scan, daemon=True).start()

    def trigger_manual_scan(self):
        """Manual scan trigger from button."""
        if self.is_scanning:
            return
        threading.Thread(target=self._execute_scan, daemon=True).start()

    def _execute_scan(self):
        """Perform the screen capture, OCR, and storage update."""
        self.is_scanning = True
        self.after(0, lambda: self.status_dot.configure(text="⚡ SCANNING...", text_color="#FBBF24"))

        try:
            panel_img = capture_screen_panel(self.sct)
            echo = self.parser.parse_panel(panel_img)

            if not echo or len(echo.get("main_stats", [])) == 0:
                self.after(0, lambda: self.status_dot.configure(text="[-] Card Not Visible", text_color="#EF4444"))
                if self.sound_enabled:
                    try:
                        winsound.Beep(400, 180)
                    except Exception:
                        pass
                time.sleep(1.2)
                return

            # Add to storage
            success, reason = self.storage.add_echo(echo, min_level=self.min_level)

            if success:
                # New echo saved!
                if self.sound_enabled:
                    try:
                        winsound.Beep(1200, 120)
                    except Exception:
                        pass
                self.after(0, lambda: self._on_new_echo_saved(echo))
            elif reason == "duplicate":
                # Already saved
                if self.sound_enabled:
                    try:
                        winsound.Beep(700, 80)
                    except Exception:
                        pass
                self.after(0, lambda: self.status_dot.configure(text="⚠️ Duplicate (Skipped)", text_color="#F59E0B"))
            elif reason == "level_skipped":
                # Level +0 skipped
                if self.sound_enabled:
                    try:
                        winsound.Beep(500, 120)
                    except Exception:
                        pass
                self.after(0, lambda: self.status_dot.configure(text=f"[-] Level +{echo.get('level', 0)} Skipped", text_color="#9CA3AF"))

            time.sleep(1.0)

        except Exception as e:
            print(f"[!] Scan error: {e}")
            self.after(0, lambda: self.status_dot.configure(text="❌ Error Occurred", text_color="#EF4444"))
            time.sleep(1.0)
        finally:
            self.is_scanning = False
            self.after(0, self._restore_status)

    def _on_new_echo_saved(self, echo):
        """Add new echo card to top of feed."""
        new_record = self.storage.echoes[-1]
        card = EchoCard(self.feed, new_record)
        card.pack(fill="x", pady=6)
        # Re-sort to put newest on top
        self._load_echo_cards()
        self.status_dot.configure(text=f"✅ Saved {echo.get('name', 'Echo')}!", text_color="#4ADE80")

    def _restore_status(self):
        if self.is_paused:
            self.status_dot.configure(text="⏸️ SCANNER PAUSED", text_color="#F59E0B")
        else:
            self.status_dot.configure(text=f"● LISTENING FOR {self.current_hotkey}", text_color="#38BDF8")

    def on_hotkey_changed(self, choice):
        self.current_hotkey = choice
        self.hotkey_listener.set_key(choice)
        self._restore_status()

    def on_min_level_changed(self, choice):
        if "All" in choice:
            self.min_level = 0
        else:
            # Parse integer from "+5", "+10", etc.
            digits = "".join(c for c in choice.split()[0] if c.isdigit())
            self.min_level = int(digits) if digits else 1

    def on_sound_toggled(self):
        self.sound_enabled = self.sound_switch.get() == 1

    def on_ontop_toggled(self):
        self.attributes("-topmost", self.ontop_switch.get() == 1)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_btn.configure(text="▶️ Resume Hotkey", fg_color="#166534", hover_color="#15803D")
        else:
            self.pause_btn.configure(text="⏸️ Pause Hotkey", fg_color="#334155", hover_color="#475569")
        self._restore_status()

    def open_json_file(self):
        path = os.path.abspath("echoes.json")
        if os.path.exists(path):
            os.startfile(path)

    def open_folder(self):
        os.startfile(os.path.abspath("."))

    def clear_all_echoes(self):
        self.storage.clear_all()
        self._load_echo_cards()
        self.status_dot.configure(text="Echoes Cleared", text_color="#9CA3AF")
        self.after(1500, self._restore_status)

    def on_close(self):
        self.hotkey_listener.stop()
        self.destroy()

if __name__ == "__main__":
    app = WuWaScannerGUI()
    app.mainloop()
