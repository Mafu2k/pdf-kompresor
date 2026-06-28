@echo off
REM ====================================================================
REM  Buduje samodzielny "PDF Kompresor.exe" (wbudowany Python + PyMuPDF).
REM  Wymaga zainstalowanego Pythona 3.9+ 64-bit.
REM ====================================================================
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Tworze srodowisko budowania...
python -m venv .build-venv || goto :err
".build-venv\Scripts\python.exe" -m pip install --upgrade pip >nul

echo [2/3] Instaluje zaleznosci (pymupdf, pyinstaller)...
".build-venv\Scripts\python.exe" -m pip install pymupdf pyinstaller || goto :err

echo [3/3] Buduje .exe (to potrwa 1-3 min)...
".build-venv\Scripts\pyinstaller.exe" --onefile --windowed ^
  --name "PDF Kompresor" --icon icon.ico --add-data "icon.ico;." ^
  --collect-all pymupdf --noconfirm pdf_kompresor.py || goto :err

echo.
echo GOTOWE:  dist\PDF Kompresor.exe
pause
exit /b 0

:err
echo.
echo BLAD budowania. Sprawdz, czy Python jest zainstalowany (python --version).
pause
exit /b 1
