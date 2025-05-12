import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ENSPIntegration:
    """eNSP集成模块，仅负责拓扑导入功能"""
    
    def __init__(self, topo_file_path: Optional[str] = None):
        """初始化拓扑导入
        
        Args:
            topo_file_path: 拓扑文件路径，可选
        """
        self.topo_file_path = topo_file_path
        
    def validate_topo_file(self, topo_file: str) -> bool:
        """验证拓扑文件是否有效
        
        Args:
            topo_file: 拓扑文件路径
            
        Returns:
            是否为有效的拓扑文件
        """
        if not topo_file or not os.path.exists(topo_file):
            logger.error(f"拓扑文件不存在: {topo_file}")
            return False
            
        # 检查文件扩展名
        if not topo_file.lower().endswith('.topo'):
            logger.error(f"不是有效的拓扑文件（.topo）: {topo_file}")
            return False
            
        # 简单检查文件内容，确保是XML格式
        try:
            with open(topo_file, 'r', encoding='utf-8') as f:
                content = f.read(1000)  # 只读取前1000个字符进行检查
                if '<?xml' not in content or '<topo>' not in content:
                    logger.error(f"拓扑文件格式不正确: {topo_file}")
                    return False
            return True
        except Exception as e:
            logger.error(f"读取拓扑文件时出错: {str(e)}")
            return False
    
    def get_import_command(self, topo_file: str) -> str:
        """获取导入拓扑的命令，用于手动操作指导
        
        Args:
            topo_file: 拓扑文件路径
            
        Returns:
            导入命令指导
        """
        if not self.validate_topo_file(topo_file):
            return ""
            
        # 返回导入指导
        topo_abs_path = os.path.abspath(topo_file)
        return f"在eNSP软件中选择'文件 > 导入拓扑'，然后选择文件: {topo_abs_path}"
    
    def print_import_guide(self, topo_file: str) -> None:
        """打印导入拓扑的指导
        
        Args:
            topo_file: 拓扑文件路径
        """
        if not self.validate_topo_file(topo_file):
            print("无效的拓扑文件，无法导入")
            return
            
        print("\n=== eNSP拓扑导入指南 ===")
        print("1. 打开eNSP软件")
        print("2. 创建新项目或打开现有项目")
        print("3. 选择菜单: 文件 > 导入拓扑")
        print(f"4. 浏览并选择拓扑文件: {os.path.abspath(topo_file)}")
        print("5. 点击'打开'完成导入\n")
        print("注意: 导入可能会替换当前项目中的设备和连接") 