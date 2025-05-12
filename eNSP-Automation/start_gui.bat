@echo off
chcp 65001 >nul
title eNSP Automation 工具 v3.0
color 0A
cls

echo ================================================
echo      eNSP Automation 工具启动程序
echo      版本: 3.0
echo ================================================
echo.
echo 功能特点:
echo  - 图形化网络拓扑创建与设计
echo  - 自然语言描述网络生成（多种AI模型支持）
echo  - 设备自动配置与管理
echo  - eNSP集成与自动化
echo.
echo 支持的设备:
echo  - 交换机: S5700/S5730/CE6850/CE12800
echo  - 路由器: AR2220/AR3260
echo  - 防火墙: USG6000
echo.
echo 正在检查环境并启动程序...
echo.

:: 切换到脚本所在目录
cd /d %~dp0

:: 检查必要目录
if not exist logs mkdir logs
if not exist configs mkdir configs
if not exist configs\nlp_config.json (
  echo 创建默认NLP配置文件...
  echo {"model_type": "local", "api_key": "", "api_url": "", "api_secret": "", "api_app_id": ""} > configs\nlp_config.json
)

:: 启动程序
python src\gui_launcher.py
if %ERRORLEVEL% NEQ 0 (
  color 0C
  echo.
  echo 启动失败! 可能的原因:
  echo  - Python未安装或未添加到PATH
  echo  - 缺少必要的Python依赖库
  echo.
  echo 请尝试运行以下命令安装依赖:
  echo pip install -r requirements.txt
  echo.
  echo 按任意键退出...
  pause > nul
  exit /b 1
) 