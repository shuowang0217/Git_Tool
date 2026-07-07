@echo off
chcp 65001 >nul

echo ========================================
echo Git-Tool v1.5.1 - 打包 exe
echo ========================================
echo.

echo 正在安装依赖...
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo 依赖安装失败，请检查 Python 和网络。
    pause
    exit /b
)

echo.
echo 正在打包 exe...

set ICON_ARG=
if exist app_icon.ico set ICON_ARG=--icon app_icon.ico

set DATA_ARG=
if exist app_icon.ico set DATA_ARG=--add-data "app_icon.ico;."

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "Git-Tool-v1.5.1" ^
  %ICON_ARG% ^
  %DATA_ARG% ^
  project_version_assistant_final.py

if errorlevel 1 (
    echo.
    echo 打包失败。
    pause
    exit /b
)

echo.
echo ========================================
echo 打包完成
echo exe 位置：dist\Git-Tool-v1.5.1.exe
echo ========================================
pause
