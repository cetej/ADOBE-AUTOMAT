@echo off
echo Nastavuji CEP Debug Mode pro Adobe...
echo.

for %%v in (9 10 11 12 13 14 15 16) do (
    reg add "HKCU\Software\Adobe\CSXS.%%v" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul 2>&1
    reg add "HKLM\Software\Adobe\CSXS.%%v" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul 2>&1
    echo CSXS.%%v - OK
)

echo.
echo Hotovo! Nyni zavri a znovu otevri Illustrator.
echo.
pause
