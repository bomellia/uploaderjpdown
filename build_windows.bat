@echo off
setlocal
py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed --onefile --name uploaderjp-backup --collect-all playwright app.py
if errorlevel 1 exit /b 1
echo Built: dist\uploaderjp-backup.exe
