@echo off
setlocal EnableExtensions DisableDelayedExpansion
if /I "%~1"=="--help" goto help
pushd "%~dp0"
if errorlevel 1 goto folder_error

rem Optional override: full path to conda.bat or conda.exe.
if defined KAIROS_CONDA if exist "%KAIROS_CONDA%" goto conda_found
set "KAIROS_CONDA="
for /f "delims=" %%C in ('where conda.bat 2^>nul') do if not defined KAIROS_CONDA set "KAIROS_CONDA=%%C"
if defined KAIROS_CONDA goto conda_found
if defined CONDA_EXE if exist "%CONDA_EXE%" set "KAIROS_CONDA=%CONDA_EXE%"
if defined KAIROS_CONDA goto conda_found
for %%C in ("%USERPROFILE%\miniconda3\condabin\conda.bat" "%USERPROFILE%\anaconda3\condabin\conda.bat" "%USERPROFILE%\miniforge3\condabin\conda.bat" "%LOCALAPPDATA%\miniconda3\condabin\conda.bat" "%LOCALAPPDATA%\anaconda3\condabin\conda.bat" "%ProgramData%\miniconda3\condabin\conda.bat" "%ProgramData%\anaconda3\condabin\conda.bat") do if not defined KAIROS_CONDA if exist "%%~C" set "KAIROS_CONDA=%%~C"
if defined KAIROS_CONDA goto conda_found
echo Conda was not found. Open Anaconda Prompt or Miniconda Prompt,
echo change to this project folder, and run this script again.
echo For a custom install, set KAIROS_CONDA to the full path of conda.bat.
goto failed

:conda_found
if not exist "app.py" goto folder_error
if not exist "requirements.txt" goto folder_error
echo Using the kairos Conda environment.
call "%KAIROS_CONDA%" run --no-capture-output -n kairos python --version
if errorlevel 1 (
    echo Cannot run Python in the kairos environment.
    echo In Anaconda Prompt, run: conda install -n kairos python=3.12 pip
    goto failed
)
if /I "%~1"=="--update" goto update
goto launch

:update
echo Installing or updating packages allowed by requirements.txt...
call "%KAIROS_CONDA%" run --no-capture-output -n kairos python -m pip install --upgrade pip
if errorlevel 1 goto failed
call "%KAIROS_CONDA%" run --no-capture-output -n kairos python -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto failed
call "%KAIROS_CONDA%" run --no-capture-output -n kairos python -m pip check
if errorlevel 1 goto failed

:launch
echo Starting KAIROS from %CD%
echo Keep this window open. Press Ctrl+C to stop the app.
echo If the browser does not open, visit http://localhost:8501
call "%KAIROS_CONDA%" run --no-capture-output -n kairos python -m streamlit run app.py --server.port 8501 --server.address localhost
if errorlevel 1 (
    echo Startup failed. For missing packages, run UPDATE_AND_START_KAIROS.bat.
    echo If port 8501 is occupied, stop the previous KAIROS window first.
    goto failed
)
popd
exit /b 0

:folder_error
echo Keep this script in the KAIROS folder alongside app.py and requirements.txt.
:failed
echo.
echo The operation failed. Read the error above.
pause
popd
exit /b 1

:help
echo START_KAIROS.bat: start the local project using Conda environment kairos.
echo UPDATE_AND_START_KAIROS.bat: install/update required packages, then start.
echo Run the update script on first use and after project dependency changes.
exit /b 0
