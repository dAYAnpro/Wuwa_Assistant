import time
import threading
import ctypes

# Windows Virtual-Key Codes mapping
VK_MAP = {
    "F1": 0x70,
    "F2": 0x71,
    "F3": 0x72,
    "F4": 0x73,
    "F5": 0x74,
    "F6": 0x75,
    "F7": 0x76,
    "F8": 0x77,
    "F9": 0x78,
    "F10": 0x79,
    "F11": 0x7A,
    "F12": 0x7B,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
    "NUMPAD0": 0x60,
    "NUMPAD1": 0x61,
    "NUMPAD2": 0x62,
    "NUMPAD3": 0x63,
    "NUMPAD4": 0x64,
    "NUMPAD5": 0x65,
    "NUMPAD6": 0x66,
    "NUMPAD7": 0x67,
    "NUMPAD8": 0x68,
    "NUMPAD9": 0x69,
}

class WindowsHotkeyListener:
    """
    Hardware-level global hotkey listener using Windows GetAsyncKeyState.
    Works independently of active window focus ('scope') and bypasses
    User Interface Privilege Isolation (UIPI) issues with elevated games.
    """
    def __init__(self, key_name="F8", callback=None):
        self.callback = callback
        self.user32 = ctypes.windll.user32
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        self.set_key(key_name)

    def set_key(self, key_name: str):
        normalized = key_name.upper().replace("<", "").replace(">", "").strip()
        with self.lock:
            self.key_name = normalized
            self.vk_code = VK_MAP.get(normalized, 0x77) # Default to F8 (0x77)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _listen_loop(self):
        was_down = False
        while self.running:
            with self.lock:
                current_vk = self.vk_code

            # GetAsyncKeyState: Most significant bit (0x8000) indicates key is physically held down
            is_down = bool(self.user32.GetAsyncKeyState(current_vk) & 0x8000)

            # Trigger only on initial key-down event (debounce)
            if is_down and not was_down:
                if self.callback:
                    try:
                        self.callback()
                    except Exception as e:
                        print(f"[!] Hotkey callback error: {e}")

            was_down = is_down
            # 50 Hz poll rate (20ms interval): uses < 0.05% CPU and provides instant response
            time.sleep(0.02)
