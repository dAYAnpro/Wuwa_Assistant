@echo off
title Building WuWa Echo Scanner Standalone Executable
cd /d "%~dp0"

echo ====================================================
echo   Building WuWa Echo Scanner (.exe) via PyInstaller
echo ====================================================
echo.

"C:\Users\dAYAn\miniconda3\Scripts\pyinstaller.exe" ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "WuWaEchoScanner" ^
    --collect-data "customtkinter" ^
    --collect-data "rapidocr_onnxruntime" ^
    --hidden-import "rapidocr_onnxruntime.ch_ppocr_v3_det.text_detect" ^
    --hidden-import "rapidocr_onnxruntime.ch_ppocr_v3_rec.text_recognize" ^
    --hidden-import "rapidocr_onnxruntime.ch_ppocr_v2_cls.text_cls" ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL._tkinter_finder" ^
    --uac-admin ^
    app.py

echo.
echo ====================================================
echo   Build Complete!
echo   Output located in: dist\WuWaEchoScanner\
echo ====================================================
pause
