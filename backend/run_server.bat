@echo off
set "PYTHON_EXE=c:\Users\Valen Mascarenhas\Desktop\hackathon\Solvathon\v(idk)\t1\university-portal\venv\Scripts\python.exe"
set "APP_DIR=c:\Users\Valen Mascarenhas\Desktop\hackathon\Solvathon\v(idk)\t1\university-portal\backend"
cd /d "%APP_DIR%"
"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
