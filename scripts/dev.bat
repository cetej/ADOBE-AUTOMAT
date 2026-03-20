@echo off
echo === NGM Localizer — DEV ===
echo.

REM Spusteni backendu
echo [1/2] Starting backend (port 8100)...
start "NGM-Backend" cmd /c "cd /d %~dp0\..\backend && python -m uvicorn main:app --reload --host 127.0.0.1 --port 8100"

timeout /t 2 /nobreak > nul

REM Spusteni frontendu
echo [2/2] Starting frontend (port 5173)...
start "NGM-Frontend" cmd /c "cd /d %~dp0\..\frontend && npm run dev"

echo.
echo Backend: http://localhost:8100
echo Frontend: http://localhost:5173
echo.
echo Zavirani oken ukonci servery.
