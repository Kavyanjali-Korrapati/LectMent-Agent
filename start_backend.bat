@echo off
:: LectMent — Windows quick-start
:: Double-click this file OR run it from any terminal.
:: It always runs from the correct directory.

cd /d "%~dp0"
echo.
echo =========================================
echo  LectMent — Starting Backend
echo  API docs: http://localhost:8000/docs
echo =========================================
echo.

python start.py
pause
