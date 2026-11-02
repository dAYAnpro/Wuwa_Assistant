# Wuthering Waves Echo OCR Scanner & Desktop App

A fast, lightweight, and anti-cheat safe OCR scanner that extracts your Echo inventory into JSON with a modern dark-themed GUI and hardware-level global hotkey support.

---

### Why the "Scope / Focus" Problem Happened & How It's Solved

1. **The Cause:**
   * Wuthering Waves runs with **Windows Administrator Privileges** (because of its anti-cheat engine).
   * In Windows, **UIPI (User Interface Privilege Isolation)** explicitly blocks normal user programs from intercepting keystrokes or reading input when an elevated game window has focus. This is why standard scripts only register `F8` when their own window has focus.

2. **The Solution:**
   * **Kernel-Level Input Polling (`hotkey_manager.py`):** Uses Windows `GetAsyncKeyState` to read physical key states asynchronously from the kernel rather than relying on window hooks.
   * **Automatic Elevation (`--uac-admin` / `run_app.bat`):** Prompts for Administrator elevation so it can monitor hotkeys and capture stats without ever needing to Alt-Tab.

---

### Features

- 🖥️ **Modern Desktop GUI (`app.py`):**
  - Dark-mode gaming UI built with CustomTkinter.
  - Live visual feed showing each scanned Echo card with stats, cost badges, and color-coded Crit Value (CV).
  - Search & filter bar (instantly search by monster name, set, or stat).
  - Quick action buttons to open `echoes.json` or clear saved items.
- ⚡ **Instant Global Hotkey (Default: `F8`):**
  - Select an Echo in-game and press `F8`—stats are captured in under **0.5s**.
  - Dropdown in UI to change hotkey to `F9`, `F10`, `Insert`, `Home`, etc.
- 📌 **Always on Top Mode:**
  - Toggle switch keeps the scanner floating in a corner or on a second monitor while gaming.
- 🎯 **Level Filter & Deduplication:**
  - Automatically skips `+0` unleveled Echoes.
  - Rejects duplicates using MD5 stat fingerprinting.
- 🔊 **Audio Chimes:**
  - Success chime (`1200 Hz`) on new echo.
  - Skip tone on `+0` echo.
  - Double-beep on duplicate.
  - Toggle switch in GUI to mute if desired.

---

### How to Run

#### Option 1: 1-Click GUI App (Recommended)
Double-click [**`run_app.bat`**](file:///e:/programming/WorkSpace/Wuwa_Extract/run_app.bat).
*It will automatically request Administrator permission so the hotkey works while Wuthering Waves is focused.*

#### Option 2: Build a Standalone `.exe`
Double-click [**`build_exe.bat`**](file:///e:/programming/WorkSpace/Wuwa_Extract/build_exe.bat).
*It uses PyInstaller to compile everything into a portable Windows executable inside `dist\WuWaEchoScanner\`.*

#### Option 3: Terminal CLI
```powershell
python scanner.py
```

---

### Project Files

- [**`app.py`**](file:///e:/programming/WorkSpace/Wuwa_Extract/app.py): The modern CustomTkinter GUI desktop application.
- [**`run_app.bat`**](file:///e:/programming/WorkSpace/Wuwa_Extract/run_app.bat): 1-click launcher with automatic Administrator elevation.
- [**`build_exe.bat`**](file:///e:/programming/WorkSpace/Wuwa_Extract/build_exe.bat): Compiles the app into a standalone `.exe`.
- [**`hotkey_manager.py`**](file:///e:/programming/WorkSpace/Wuwa_Extract/hotkey_manager.py): Windows kernel-level hotkey listener (`GetAsyncKeyState`).
- [**`parser.py`**](file:///e:/programming/WorkSpace/Wuwa_Extract/parser.py): High-performance single-pass ONNX neural OCR engine.
- [**`storage.py`**](file:///e:/programming/WorkSpace/Wuwa_Extract/storage.py): Pure JSON file manager with fingerprint deduplication.
- [**`echoes.json`**](file:///e:/programming/WorkSpace/Wuwa_Extract/echoes.json): Your saved echoes database.
"# Wuwa_Assistant" 
