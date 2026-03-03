@echo off
setlocal

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python -m venv .venv
    ) else (
        echo Python not found. Install Python 3.10+ and retry.
        exit /b 1
    )
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e .[dev]

echo Environment ready. Activate with: .venv\Scripts\activate.bat
