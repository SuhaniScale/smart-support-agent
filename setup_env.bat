@echo off
setlocal
cd /d "%~dp0"

echo ================================
echo Creating Python virtual environment...
echo ================================
python -m venv .venv

if not exist ".venv\Scripts\activate.bat" (
    echo Failed to create .venv.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install google-genai

echo.
echo ================================
echo Virtual environment is ready.
echo ================================
echo.
echo Next, if needed, authenticate to Google Cloud:
echo   gcloud auth application-default login

echo To run the agent:
echo   python agents\meaning_extraction_agent.py

echo.
pause
