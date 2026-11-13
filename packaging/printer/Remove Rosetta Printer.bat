@echo off
rem Removes the "Rosetta Plotter" printer that "Install Rosetta Printer.bat" added.
setlocal
title Remove the Rosetta Plotter printer

net session >nul 2>&1
if errorlevel 1 (
    echo Asking Windows for permission to remove a printer...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    if errorlevel 1 (
        echo.
        echo Permission was not given, so nothing was removed.
        pause
    )
    exit /b
)

if not exist "%~dp0Remove-RosettaPrinter.ps1" (
    echo.
    echo The file Remove-RosettaPrinter.ps1 is missing. Keep it in the same folder as this file.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Remove-RosettaPrinter.ps1"
if errorlevel 1 (
    echo.
    echo The printer was NOT removed. The reason is in the red text above.
)
pause
