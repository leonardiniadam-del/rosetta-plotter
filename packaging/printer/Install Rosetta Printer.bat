@echo off
rem Adds the "Rosetta Plotter" printer, so any program can print straight into the Rosetta Plotter app.
rem Double-click this file. Windows asks for permission once, because adding a printer needs it.
setlocal
title Install the Rosetta Plotter printer

net session >nul 2>&1
if errorlevel 1 (
    echo Asking Windows for permission to add a printer...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    if errorlevel 1 (
        echo.
        echo Permission was not given, so the printer was not added.
        echo Run this again and choose Yes, or ask whoever looks after this computer.
        pause
    )
    exit /b
)

if not exist "%~dp0Install-RosettaPrinter.ps1" (
    echo.
    echo The file Install-RosettaPrinter.ps1 is missing. Keep it in the same folder as this file.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-RosettaPrinter.ps1"
if errorlevel 1 (
    echo.
    echo The printer was NOT installed. The reason is in the red text above.
) else (
    echo.
    echo The printer is installed.
)
pause
