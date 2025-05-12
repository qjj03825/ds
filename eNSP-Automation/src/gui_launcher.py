#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
eNSP-Automation GUI启动器
用于启动图形用户界面
"""

import os
import sys
import logging
import traceback
from pathlib import Path

# 解决中文编码问题
if sys.platform == 'win32':
    import locale
    # 设置默认编码为UTF-8
    if sys.stdout.encoding != 'utf-8':
        # 可能的话，设置控制台输出编码为UTF-8
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except AttributeError:
            pass  # Python 3.6及更早版本不支持reconfigure

# 配置日志
logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, 'ensp_automation_gui.log')

# 使用utf-8编码写入日志文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """检查必要的依赖项是否已安装"""
    dependencies = {
        "tkinter": "GUI界面核心库，Python标准库组件",
        "PyQt5": "图形界面库，用于部分高级界面组件",
        "PIL": "图像处理库，用于GUI图标显示",
        "win32com": "Windows COM组件，用于eNSP集成",
        "pythoncom": "COM组件库，用于与eNSP通信"
    }
    
    missing = []
    warnings = []
    
    for module, description in dependencies.items():
        try:
            if module == "PIL":
                from PIL import Image, ImageTk
                logger.info(f"[OK] 成功导入 {module}")
            elif module == "win32com":
                import win32com.client
                logger.info(f"[OK] 成功导入 {module}")
            else:
                __import__(module)
                logger.info(f"[OK] 成功导入 {module}")
        except ImportError:
            if module in ["tkinter", "win32com", "pythoncom"]:
                missing.append((module, description))
            else:
                warnings.append((module, description))
    
    # 如果缺少必要依赖，退出程序
    if missing:
        logger.error("缺少必要的依赖项:")
        for module, description in missing:
            logger.error(f"  - {module}: {description}")
        logger.error("请安装缺失的依赖后再次运行程序")
        return False
    
    # 显示警告但继续运行
    if warnings:
        logger.warning("某些可选依赖项未安装:")
        for module, description in warnings:
            logger.warning(f"  - {module}: {description}")
        logger.warning("可以通过运行以下命令安装所有依赖:")
        logger.warning("pip install -r requirements.txt")
        logger.warning("程序将继续运行，但某些功能可能不可用")
    
    return True

def main():
    """主函数：检查环境并启动GUI"""
    try:
        logger.info("=" * 60)
        logger.info("eNSP Automation 工具 - 启动图形界面")
        logger.info("=" * 60)
        
        # 检查依赖项
        if not check_dependencies():
            print("\n请安装缺失的依赖后再次运行程序")
            input("\n按Enter键退出...")
            return 1
        
        # 检查必要目录
        base_dir = Path(__file__).parent.parent
        logs_dir = base_dir / "logs"
        configs_dir = base_dir / "configs"
        
        if not logs_dir.exists():
            logs_dir.mkdir(exist_ok=True)
            logger.info(f"创建日志目录: {logs_dir}")
        
        if not configs_dir.exists():
            configs_dir.mkdir(exist_ok=True)
            logger.info(f"创建配置目录: {configs_dir}")
        
        # 检查NLP配置文件
        nlp_config_file = configs_dir / "nlp_config.json"
        if not nlp_config_file.exists():
            import json
            default_config = {
                "model_type": "local",
                "api_key": "",
                "api_url": "",
                "api_secret": "",
                "api_app_id": ""
            }
            with open(nlp_config_file, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            logger.info(f"创建默认NLP配置文件: {nlp_config_file}")
        
        # 启动GUI
        logger.info("正在启动eNSP Automation工具图形界面...")
        from gui import main as gui_main
        gui_main()
        
        return 0
        
    except Exception as e:
        logger.error(f"启动失败: {str(e)}")
        logger.error("详细错误信息:")
        logger.error(traceback.format_exc())
        print(f"\n启动失败: {str(e)}")
        input("\n按Enter键退出...")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 