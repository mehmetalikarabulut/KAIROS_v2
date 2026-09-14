@echo off
rem Run this on first use or after the project's requirements change.
call "%~dp0START_KAIROS.bat" --update
exit /b %errorlevel%
