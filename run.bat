@echo off
title Smart Classroom Attention Detector
color 0A
echo.
echo  ================================================
echo    Smart Classroom Attention Detector
echo  ================================================
echo.
echo  [*] Starting server... please wait
echo  [*] DeepFace loads in ~15 seconds on first run
echo.
echo  Open your browser and go to:
echo      http://127.0.0.1:5000
echo.
echo  Login credentials:
echo      Username : teacher
echo      Password : admin123
echo.
echo  Press Ctrl+C in this window to stop the server.
echo  ================================================
echo.

cd /d "%~dp0"
python app.py

echo.
echo  [!] Server stopped.
pause
