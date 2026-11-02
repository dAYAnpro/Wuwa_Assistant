import sys
import os
import time
import argparse
import threading
import ctypes
from ctypes import wintypes
import winsound
import cv2
import numpy as np
import mss
from pynput import keyboard

from parser import EchoParser
from storage import EchoStorage

# Enable Windows DPI awareness so GetWindowRect matches mss physical pixel coordinates
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

def get_foreground_window_rect(sct):
    """
    Get the bounding box of the active foreground window, safely clamped
    to desktop screen bounds (fixes mss BitBlt crash on maximized windows).
    """
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

    # Clamp against virtual desktop bounds to fix Windows Aero -8px maximized borders
    all_mon = sct.monitors[0]
    left = max(all_mon["left"], rect.left)
    top = max(all_mon["top"], rect.top)
    right = min(all_mon["left"] + all_mon["width"], rect.right)
    bottom = min(all_mon["top"] + all_mon["height"], rect.bottom)

    clamped_w = right - left
    clamped_h = bottom - top

    if clamped_w <= 100 or clamped_h <= 100:
        return None

    return {
        "top": top,
        "left": left,
        "width": clamped_w,
        "height": clamped_h
    }

def capture_screen_panel(sct):
    """Capture the right-hand panel of the active window or primary monitor."""
    win_rect = get_foreground_window_rect(sct)
    if win_rect:
        try:
            sct_img = sct.grab(win_rect)
        except Exception:
            sct_img = sct.grab(sct.monitors[1])
    else:
        # Fallback to primary monitor
        sct_img = sct.grab(sct.monitors[1])

    # Convert BGRA to BGR
    img = np.array(sct_img)[:, :, :3]
    h, w, _ = img.shape
    
    # In Wuthering Waves (16:9), the Echo detail panel starts around 65% width
    # If Ultrawide (21:9 or wider), panel is pinned to right side (~35% of equivalent 16:9 width)
    aspect = w / max(1, h)
    if aspect > 1.85: # Ultrawide
        panel_w = int(h * (16 / 9) * 0.35)
        crop_x = max(0, w - panel_w)
    else:
        crop_x = int(w * 0.65)

    panel = img[:, crop_x:]
    return panel

class WuWaScannerApp:
    def __init__(self, hotkey="<f8>", json_file="echoes.json", min_level=1):
        self.hotkey = hotkey
        self.min_level = min_level
        self.parser = EchoParser()
        self.storage = EchoStorage(json_path=json_file)
        self.sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
        self.lock = threading.Lock()

    def scan_once(self, panel_img=None):
        # Thread-safe lock to prevent multiple simultaneous hotkey triggers
        if not self.lock.acquire(blocking=False):
            return

        try:
            if panel_img is None:
                panel_img = capture_screen_panel(self.sct)

            echo = self.parser.parse_panel(panel_img)
            if not echo or len(echo.get("main_stats", [])) == 0:
                print("[-] No Echo detected on screen. Make sure the Echo detail panel is visible!")
                try:
                    winsound.Beep(400, 180) # Error tone
                except Exception:
                    pass
                return

            # Skip Level 0 / Unleveled Echoes
            echo_lvl = echo.get("level", 0)
            if echo_lvl < self.min_level:
                print(f"\n[-] [SKIPPED +0 ECHO] {echo['name']} is Level +{echo_lvl}. (Only leveled echoes are saved)")
                try:
                    winsound.Beep(500, 150) # Neutral skip tone
                except Exception:
                    pass
                return

            # Save to storage
            is_new = self.storage.add_echo(echo, min_level=self.min_level)

            # Audio feedback
            try:
                if is_new:
                    winsound.Beep(1200, 120) # Success chime
                else:
                    winsound.Beep(700, 80)  # Duplicate warning
            except Exception:
                pass

            # Print terminal output
            print("\n" + "="*52)
            status_tag = "[NEW ECHO SAVED TO JSON]" if is_new else "[ALREADY SCANNED (DUPLICATE)]"
            print(f"{status_tag:^52}")
            print("="*52)
            print(f"Echo:        {echo['name']}")
            print(f"Cost:        COST {echo['cost']}  |  Level: +{echo['level']}")
            print(f"Sonata Set:  {echo['sonata']}")
            print("-" * 52)
            print("Main Stats:")
            for m in echo['main_stats']:
                print(f"  • {m['stat']:<26} {m['value']}")
            print("-" * 52)
            print(f"Sub-Stats ({len(echo['sub_stats'])}/5):")
            for s in echo['sub_stats']:
                print(f"  • {s['stat']:<26} {s['value']}")
            print("-" * 52)
            print(f"Substats CV: {echo['substats_cv']:<6} | Total CV: {echo['total_cv']:<6} | Total in JSON: {self.storage.count()}")
            print("="*52 + "\n")

        except Exception as e:
            print(f"[!] Scan error: {e}")
            try:
                winsound.Beep(350, 250)
            except Exception:
                pass
        finally:
            self.lock.release()

    def run(self):
        print("="*56)
        print("     WUTHERING WAVES ECHO SCANNER -> JSON     ")
        print("="*56)
        print(f"[*] Hotkey:       {self.hotkey.upper()}")
        print(f"[*] Min Level:    +{self.min_level} (Level +0 echoes are automatically skipped)")
        print(f"[*] Save File:    {self.storage.json_path}")
        print(f"[*] Stored Count: {self.storage.count()} leveled echoes")
        print("-" * 56)
        print("Instructions:")
        print(" 1. Open Wuthering Waves to your Echo backpack.")
        print(" 2. Click or hover on any Echo.")
        print(f" 3. Press {self.hotkey.upper()} to extract stats to JSON.")
        print(" 4. Press Ctrl+C in this terminal window to stop.")
        print("="*56)
        print("\n[+] Waiting for hotkey press...\n")

        with keyboard.GlobalHotKeys({self.hotkey: self.scan_once}) as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                print("\n[*] Scanner stopped by user. Goodbye!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wuthering Waves Echo OCR Scanner (JSON)")
    parser.add_argument("--hotkey", default="<f8>", help="Hotkey trigger (default: <f8>)")
    parser.add_argument("--file", help="Scan a static screenshot file directly")
    parser.add_argument("--json", default="echoes.json", help="JSON export filename")
    parser.add_argument("--min-level", type=int, default=1, help="Minimum echo level to save (default: 1, skips +0)")

    args = parser.parse_args()

    app = WuWaScannerApp(hotkey=args.hotkey, json_file=args.json, min_level=args.min_level)

    if args.file:
        print(f"[*] Processing single image: {args.file}")
        img = cv2.imread(args.file)
        if img is None:
            print(f"[!] Could not load image from {args.file}")
            sys.exit(1)
        h, w, _ = img.shape
        panel = img[:, int(w * 0.65):]
        app.scan_once(panel)
    else:
        app.run()
