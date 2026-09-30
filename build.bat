@echo off

set "SCRIPT_NAME=frontend.py"
set "APP_NAME=songs_manager"

pyinstaller --onefile --windowed --collect-all customtkinter --name "%APP_NAME%" --distpath . --workpath ./build_temp --specpath ./build_temp %SCRIPT_NAME%

rmdir /s /q build_temp
del "%APP_NAME%.spec" 2>nul
