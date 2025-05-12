@echo off
chcp 65001 >nul
title eNSP 连接测试工具
color 0A
cls

echo ================================================
echo      eNSP连接测试工具
echo ================================================
echo.

:: 切换到脚本所在目录
cd /d %~dp0

echo 请选择要测试的连接类型:
echo.
echo 1. 测试eNSP软件连接 (软件控制)
echo 2. 测试设备SSH连接 (设备配置)
echo.
set /p choice="输入选项 (1 或 2): "

if "%choice%"=="1" (
  echo.
  echo 正在测试与eNSP软件的连接...
  echo 将尝试连接到eNSP并创建测试项目
  echo.
  python test_connection.py %*
) else if "%choice%"=="2" (
  echo.
  echo 正在测试与eNSP设备的SSH连接...
  echo.
  python test_device_connection.py %*
) else (
  echo.
  echo 无效的选项，请重新运行并选择 1 或 2
  echo.
  goto end
)

if %ERRORLEVEL% NEQ 0 (
  color 0C
  echo.
  echo 连接测试失败! 可能的原因:
  echo  - Python未安装或未添加到PATH
  echo  - 缺少必要的Python依赖库
  echo  - eNSP未安装或未正确运行
  echo  - 设备未启动或网络不可达
  echo.
  echo 请尝试运行以下命令安装依赖:
  echo pip install -r requirements.txt
  echo.
  echo 确保以管理员权限运行eNSP软件
  echo.
)

:end
pause 