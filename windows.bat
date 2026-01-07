@echo off
SETLOCAL EnableDelayedExpansion
TITLE Gemini Metadata - Windows Installer
CLS

echo ========================================================
echo      GEMINI METADATA - WINDOWS NATIVE INSTALLER
echo      (Auto-Config, ExifTool Fetcher, & Shortcut)
echo ========================================================
echo.

:: 1. CEK PYTHON
echo [1/6] Memeriksa Python...
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python tidak terdeteksi!
    echo Harap install Python 3.10+ dan centang "Add to PATH".
    PAUSE
    EXIT /B
)
echo     OK.

:: 2. SETUP EXIFTOOL (AUTO DOWNLOAD)
echo [2/6] Memeriksa ExifTool...
IF NOT EXIST "tools" MKDIR "tools"
IF NOT EXIST "tools\exiftool.exe" (
    echo     Download ExifTool...
    powershell -Command "Invoke-WebRequest -Uri 'https://exiftool.org/exiftool-13.10.zip' -OutFile 'exiftool.zip'; Expand-Archive -Path 'exiftool.zip' -DestinationPath 'tools_temp' -Force; Move-Item -Path 'tools_temp\exiftool(-k).exe' -Destination 'tools\exiftool.exe' -Force; Remove-Item 'exiftool.zip'; Remove-Item 'tools_temp' -Recurse -Force"
)
echo     OK.

:: 3. SETUP VENV
echo [3/6] Menyiapkan Virtual Environment...
IF EXIST "venv" RMDIR /S /Q "venv"
python -m venv venv
echo     OK.

:: 4. INSTALL REQUIREMENTS
echo [4/6] Menginstall Library...
CALL venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo     OK.

:: 5. GENERATE CONFIG
echo [5/6] Membuat Config...
SET "CURRENT_DIR=%CD%"
SET "ESCAPED_DIR=%CURRENT_DIR:\=\\%"
(
echo {
echo     "temp_folder": "%ESCAPED_DIR%\\tmp_processing",
echo     "output_folder": "%ESCAPED_DIR%\\output"
echo }
) > user_settings.json
echo     OK.

:: 6. SHORTCUT
echo [6/6] Membuat Shortcut Desktop...
(
echo @echo off
echo CD /D "%%~dp0"
echo SET PYTHONWARNINGS=ignore
echo SET GRPC_ENABLE_FORK_SUPPORT=0
echo CALL venv\Scripts\activate
echo streamlit run app.py --server.headless true
) > run.bat

SET "VBS_SCRIPT=%TEMP%\CreateShortcut.vbs"
(
echo Set oWS = WScript.CreateObject^("WScript.Shell"^)
echo sLink = oWS.ExpandEnvironmentStrings^("%%USERPROFILE%%\Desktop\Gemini Metadata.lnk"^)
echo Set oLink = oWS.CreateShortcut^(sLink^)
echo oLink.TargetPath = "%CURRENT_DIR%\run.bat"
echo oLink.WorkingDirectory = "%CURRENT_DIR%"
echo oLink.IconLocation = "shell32.dll, 238"
echo oLink.Save
) > "%VBS_SCRIPT%"
cscript //nologo "%VBS_SCRIPT%"
DEL "%VBS_SCRIPT%"

echo.
echo ========================================================
echo      SELESAI! Cek Shortcut di Desktop Anda.
echo ========================================================
PAUSE