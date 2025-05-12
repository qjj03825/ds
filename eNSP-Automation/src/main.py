#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
eNSP自动化工具命令行入口
支持通过命令行方式创建和管理网络拓扑
"""

import os
import sys
import json
import logging
import argparse
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from nlp_helper import NLPTopologyGenerator  # 更改为新的NLP处理模块
from topology_generator import TopologyGenerator

# 配置日志
log_file = 'ensp_automation.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

class ENSPAutomation:
    """eNSP自动化工具主类，提供命令行方式的拓扑自动化功能"""
    
    def __init__(self, api_key: Optional[str] = None):
        """初始化eNSP自动化工具
        
        Args:
            api_key: API密钥（可选，仅当使用外部NLP服务时需要）
        """
        self.nlp = NLPTopologyGenerator()
        # 如果提供了API密钥，则配置NLP
        if api_key:
            self.nlp.api_key = api_key
        
        self.generator = TopologyGenerator()
        
        # 创建输出目录
        config_dir = Path(__file__).parent.parent / "configs"
        config_dir.mkdir(exist_ok=True)
        logger.info(f"配置目录: {config_dir}")
    
    def create_from_description(self, description: str, project_name: str) -> bool:
        """从自然语言描述创建网络拓扑
        
        Args:
            description: 网络拓扑自然语言描述
            project_name: 项目名称
            
        Returns:
            bool: 是否成功创建拓扑
        """
        try:
            # 解析描述为拓扑结构
            logger.info("正在解析网络拓扑描述...")
            parsed_data = self.nlp.parse_network_description(description)
            
            # 生成拓扑配置
            logger.info("正在生成拓扑配置...")
            topology = self.generator.generate(parsed_data)
            
            # 保存拓扑配置到文件
            config_dir = Path(__file__).parent.parent / "configs"
            output_file = config_dir / f"{project_name}.json"
            topo_file = config_dir / f"{project_name}.topo"
            
            self.generator.save_topology(topology, output_file)
            logger.info(f"拓扑配置已保存至: {output_file}")
            
            # 生成topo文件
            success = self.generator.generate_topo_file(topology, topo_file)
            if success:
                logger.info(f"拓扑文件已生成: {topo_file}")
            else:
                logger.error("生成拓扑文件失败")
                return False
            
            logger.info(f"拓扑创建完成，拓扑文件位置: {topo_file}")
            return True
        
        except Exception as e:
            logger.error(f"创建拓扑失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def main():
    """主函数：解析命令行参数并执行相应操作"""
    parser = argparse.ArgumentParser(
        description="eNSP自动化工具 - 网络拓扑自动生成与配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从描述文件创建拓扑
  python main.py create my_network --description-file campus_network.txt
  
  # 从命令行描述创建拓扑
  python main.py create simple_net --description "一个包含路由器和两台交换机的简单网络"
"""
    )
    parser.add_argument("--api-key", help="NLP服务API密钥")
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 创建项目子命令
    create_parser = subparsers.add_parser("create", help="从描述创建网络拓扑")
    create_parser.add_argument("project_name", help="项目名称")
    create_parser.add_argument("--description", help="网络拓扑描述")
    create_parser.add_argument("--description-file", help="网络拓扑描述文件路径")
    create_parser.add_argument("--model", default="local", 
                              choices=["local", "openai", "deepseek", "xunfei"],
                              help="使用的NLP模型类型 (默认: local)")
    
    args = parser.parse_args()
    
    # 如果没有指定子命令，显示帮助
    if not args.command:
        parser.print_help()
        return 0
    
    # 初始化自动化工具
    try:
        automation = ENSPAutomation(args.api_key)
        
        if args.command == "create":
            # 获取网络拓扑描述
            description = args.description
            if not description and args.description_file:
                try:
                    # 尝试从文件获取描述
                    description_file = Path(args.description_file)
                    if not description_file.exists():
                        # 尝试从examples目录获取
                        examples_dir = Path(__file__).parent.parent / "examples"
                        description_file = examples_dir / args.description_file
                    
                    with open(description_file, "r", encoding="utf-8") as f:
                        description = f.read()
                        print(f"已从文件读取描述: {description_file}")
                except Exception as e:
                    print(f"错误: 无法读取描述文件 {args.description_file}: {e}")
                    return 1
            
            if not description:
                print("错误: 未提供网络拓扑描述，请通过--description参数或--description-file参数提供")
                return 1
            
            # 创建项目
            print(f"正在从描述创建网络拓扑: {args.project_name}")
            if not automation.create_from_description(description, args.project_name):
                print("创建项目失败")
                return 1
            print(f"成功创建项目: {args.project_name}")
    
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"发生错误: {e}")
        logger.exception("执行命令时发生错误")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 