import os
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from jinja2 import Environment, FileSystemLoader
import logging
from pathlib import Path
import re
import uuid
import subprocess

# 设置日志
logger = logging.getLogger(__name__)

class TopologyGenerator:
    """eNSP网络拓扑生成引擎"""
    
    DEVICE_TEMPLATES = {
        # 交换机设备
        "CE6850": {
            "base_config": "ce6850_base.cfg",
            "interfaces": ["GE1/0/1-48", "XGE1/0/49-52"],
            "version": "V200R019C00",
            "model": "CE6850-V200R019C00"
        },
        "CE6800": {
            "base_config": "ce6800_base.cfg",
            "interfaces": ["GE1/0/1-48", "XGE1/0/49-52"],
            "version": "V200R019C00",
            "model": "CE6800-V200R019C00"
        },
        "CE12800": {
            "base_config": "ce12800_base.cfg",
            "interfaces": ["GE1/0/1-48", "XGE1/0/49-56"],
            "version": "V200R019C00",
            "model": "CE12800-V200R019C00"
        },
        "S5730": {
            "base_config": "s5730_base.cfg",
            "interfaces": ["GE0/0/1-24", "XGE0/0/25-28"],
            "version": "V200R019C00",
            "model": "S5730-V200R019C00"
        },
        "S5700": {
            "base_config": "s5700_base.cfg",
            "interfaces": ["GE0/0/1-24"],
            "version": "V200R019C00",
            "model": "S5700-V200R019C00"
        },
        "S3700": {
            "base_config": "s3700_base.cfg",
            "interfaces": ["GE0/0/1-24"],
            "version": "V200R019C00",
            "model": "S3700-V200R019C00"
        },
        # 路由器设备
        "AR2220": {
            "base_config": "ar2220_base.cfg",
            "interfaces": ["GE0/0/0-1"],
            "version": "V200R009C00",
            "model": "AR2220-V200R009C00"
        },
        "AR3260": {
            "base_config": "ar3260_base.cfg",
            "interfaces": ["GE0/0/0-5"],
            "version": "V200R009C00",
            "model": "AR3260-V200R009C00"
        },
        # 安全设备
        "USG6000": {
            "base_config": "usg6000_base.cfg",
            "interfaces": ["GE1/0/1-8"],
            "version": "V200R011C10",
            "model": "USG6000-V200R011C10"
        },
        # 无线设备
        "AC6005-8": {
            "base_config": "ac6005_base.cfg",
            "interfaces": ["GE0/0/1-8"],
            "version": "V200R019C00",
            "model": "AC6005-8-V200R019C00"
        },
        "AC6605-26": {
            "base_config": "ac6605_base.cfg",
            "interfaces": ["GE0/0/1-24", "XGE0/0/25-26"],
            "version": "V200R019C00",
            "model": "AC6605-26-V200R019C00"
        },
        "AD9430-28": {
            "base_config": "ad9430_base.cfg",
            "interfaces": ["GE0/0/1-24", "XGE0/0/25-28"],
            "version": "V200R019C00",
            "model": "AD9430-28-V200R019C00"
        },
        # PC及终端设备
        "PC": {
            "base_config": "pc_base.cfg",
            "interfaces": ["Ethernet0/0/0"],
            "version": "PC",
            "model": "PC"
        },
        "MCS": {
            "base_config": "mcs_base.cfg",
            "interfaces": ["Ethernet0/0/0"],
            "version": "MCS",
            "model": "MCS"
        },
        "Client": {
            "base_config": "client_base.cfg",
            "interfaces": ["Ethernet0/0/0"],
            "version": "Client",
            "model": "Client"
        },
        "Server": {
            "base_config": "server_base.cfg",
            "interfaces": ["Ethernet0/0/0-1"],
            "version": "Server",
            "model": "Server"
        },
        "STA": {
            "base_config": "sta_base.cfg",
            "interfaces": ["WLAN-Radio0/0/0"],
            "version": "STA",
            "model": "STA"
        },
        "Cellphone": {
            "base_config": "cellphone_base.cfg",
            "interfaces": ["WLAN-Radio0/0/0"],
            "version": "Cellphone",
            "model": "Cellphone"
        },
        # 云设备
        "Cloud": {
            "base_config": "cloud_base.cfg",
            "interfaces": ["Ethernet0/0/0-3"],
            "version": "Cloud",
            "model": "Cloud"
        },
        "FRSW": {
            "base_config": "frsw_base.cfg",
            "interfaces": ["Serial0/0/0-3"],
            "version": "FRSW",
            "model": "FRSW"
        },
        "HUB": {
            "base_config": "hub_base.cfg",
            "interfaces": ["Ethernet0/0/0-7"],
            "version": "HUB",
            "model": "HUB"
        }
    }

    def __init__(self, templates_dir: str = "../templates"):
        """初始化拓扑生成引擎
        
        Args:
            templates_dir: 模板目录路径
        """
        self.templates_dir = templates_dir
        self.jinja_env = Environment(
            loader=FileSystemLoader(templates_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def generate(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """根据解析的数据生成拓扑
        
        Args:
            parsed_data: 解析的数据
            
        Returns:
            生成的拓扑
        """
        # 设备实例
        devices = []
        for device_data in parsed_data["devices"]:
            template = self._get_template(device_data["type"])
            devices.append({
                "name": device_data["name"],
                "type": device_data["type"],
                "version": template.get("version", "V200R019C00"),
                "model": template.get("model", f"{device_data['type']}-V200R019C00"),
                "config": self._generate_device_config(template, device_data),
                "interfaces": self._init_interfaces(template)
            })
        
        # 连接关系建立
        connections = []
        for conn in parsed_data["connections"]:
            src_dev, src_port = self._parse_connection_point(conn["from"])
            dst_dev, dst_port = self._parse_connection_point(conn["to"])
            connections.append({
                "source": f"{src_dev}:{src_port}",
                "target": f"{dst_dev}:{dst_port}",
                "bandwidth": conn.get("bandwidth", "1G")
            })
        
        # 使用字符串表示当前时间，避免JSON序列化问题
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        topology = {
            "version": "1.0",
            "devices": devices,
            "connections": connections,
            "generated_at": current_time
        }
        
        # 验证拓扑
        valid, issues = self.validate_topology(topology)
        if not valid:
            logger.warning("拓扑验证失败，存在以下问题:")
            for issue in issues:
                logger.warning(f" - {issue}")
            # 尝试修复配置
            self._fix_topology_issues(topology, issues)
            # 再次验证
            valid, issues = self.validate_topology(topology)
            if not valid:
                logger.warning("拓扑修复后仍有问题:")
                for issue in issues:
                    logger.warning(f" - {issue}")
        
        return topology
    
    def generate_topo_file(self, topology: Dict[str, Any], output_file: str) -> str:
        """生成eNSP格式XML文件
        
        Args:
            topology: 拓扑配置
            output_file: 输出文件路径(.topo)
            
        Returns:
            生成的文件路径
        """
        try:
            logger.info(f"开始生成topo文件: {output_file}")
            logger.info(f"拓扑包含设备数量: {len(topology['devices'])}")
            logger.info(f"拓扑包含连接数量: {len(topology['connections'])}")
            
            # 创建XML根节点 - 按照老师提供的结构
            topo = ET.Element('topo', version='1.3.00.100')
            
            # 创建设备节点
            devices = ET.SubElement(topo, 'devices')
            
            # 设备ID映射，用于后续连接
            device_id_map = {}
            
            # 初始位置配置
            start_x, start_y = 170, 170
            x_spacing, y_spacing = 150, 100
            
            # 添加设备
            for i, device in enumerate(topology["devices"]):
                # 计算位置
                row = i // 3  # 每行3个设备
                col = i % 3
                x = start_x + col * x_spacing
                y = start_y + row * y_spacing
                
                # 生成唯一ID - 使用UUID格式，与老师代码一致
                device_id = str(uuid.uuid4()).upper()
                device_id_map[device["name"]] = device_id
                
                # 确定设备模型
                device_type = device["type"]
                
                # 根据设备类型设置model
                if any(sw in device_type for sw in ["S5700", "S5730", "S3700"]):
                    model = "S5700"
                elif any(ce in device_type for ce in ["CE6850", "CE6800", "CE12800"]):
                    model = "CE6800"
                # 路由器设备
                elif any(ar in device_type for ar in ["AR2220", "AR3260"]):
                    model = "AR2220"
                # 防火墙设备
                elif "USG" in device_type:
                    model = "USG6000V"
                # 无线设备
                elif any(ac in device_type for ac in ["AC6005", "AC6605"]):
                    model = "AC6005"
                elif "AD9430" in device_type:
                    model = "AD9430"
                # PC设备
                elif device_type in ["PC", "Client", "Server", "MCS"]:
                    model = "PC" 
                elif device_type in ["STA", "Cellphone"]:
                    model = "STA"
                # 云设备
                elif device_type == "Cloud":
                    model = "Cloud"
                elif device_type == "FRSW":
                    model = "FRSW"
                elif device_type == "HUB":
                    model = "HUB"
                else:
                    model = "S5700"  # 默认
                
                # 添加设备元素 - 使用与老师代码完全相同的结构
                dev = ET.SubElement(devices, 'dev', {
                    'id': device_id,
                    'name': device["name"],
                    'model': model,
                    'cx': f"{x}.000000",
                    'cy': f"{y}.000000"
                })
                
                # 添加插槽和接口 - 与老师代码相同
                slot = ET.SubElement(dev, 'slot', {'number': 'slot17', 'isMainBoard': '1'})
                
                # 根据设备类型添加不同接口
                # 交换机设备
                if any(sw in device_type for sw in ["S5700", "S5730", "S3700"]):
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'GE', 'count': '24'})
                elif any(ce in device_type for ce in ["CE6850", "CE6800", "CE12800"]):
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'GE', 'count': '48'})
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'XGE', 'count': '4'})
                # 路由器设备
                elif any(ar in device_type for ar in ["AR2220", "AR3260"]):
                    # AR设备的接口 - 修改为与成功拓扑一致的接口格式
                    # 分拆为两个接口声明，而不是一个count=2的声明
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'GE', 'count': '1'})
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'GE', 'count': '1'})
                # 防火墙设备
                elif "USG" in device_type:
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'GE', 'count': '8'})
                # 无线设备
                elif any(ac in device_type for ac in ["AC6005", "AC6605"]):
                    # 无线AC接口
                    ac_count = "8" if "AC6005" in device_type else "24"
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'GE', 'count': ac_count})
                    
                    if "AC6605" in device_type:
                        # AC6605还有XGE接口
                        ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'XGE', 'count': '2'})
                elif "AD9430" in device_type:
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'GE', 'count': '24'})
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'XGE', 'count': '4'})
                # PC设备
                elif device_type in ["PC", "Client", "MCS"]:
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'Ethernet', 'count': '1'})
                elif device_type == "Server":
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'Ethernet', 'count': '2'})
                elif device_type in ["STA", "Cellphone"]:
                    ET.SubElement(slot, 'interface', {'sztype': 'WLAN', 'interfacename': 'WLAN-Radio', 'count': '1'})
                # 云设备
                elif device_type == "Cloud":
                    cloud_interface = ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'Ethernet', 'count': '4'})
                    
                    # 添加Cloud设备接口映射 - 对接物理网卡
                    # 获取系统可用网卡信息
                    available_adapters = []
                    try:
                        # 在Windows系统下查询物理网卡信息
                        if os.name == 'nt':
                            try:
                                # 尝试使用PowerShell获取网卡信息
                                result = subprocess.run(
                                    ['powershell', '-Command', 
                                    'Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Select-Object -Property Name,InterfaceDescription,MacAddress,Status | Format-List'],
                                    capture_output=True, text=True, check=False
                                )
                                
                                if result.returncode == 0:
                                    output = result.stdout
                                    # 解析结果，提取网卡信息
                                    adapters = re.findall(r'Name\s+:\s+(.*?)[\r\n]+.*?InterfaceDescription\s+:\s+(.*?)[\r\n]+.*?MacAddress\s+:\s+(.*?)[\r\n]+', 
                                                        output, re.DOTALL)
                                    
                                    for name, desc, mac in adapters:
                                        available_adapters.append({
                                            'name': name.strip(), 
                                            'description': desc.strip(),
                                            'mac': mac.strip()
                                        })
                                
                                logger.info(f"找到{len(available_adapters)}个可用网络适配器")
                            except Exception as e:
                                logger.error(f"获取网络适配器信息失败: {str(e)}")
                    
                    except Exception as e:
                        logger.warning(f"无法获取网络适配器信息: {str(e)}")
                    
                    # 添加接口映射，如果找到可用适配器则使用，否则使用默认值
                    adapter_uid = "\\Device\\NPF_{8D6783D1-0E30-4C3F-9C5E-5A84041B0E0E}"  # 默认值，与可通拓扑一致
                    
                    # 如果找到可用适配器，使用第一个
                    if available_adapters:
                        try:
                            # 尝试获取设备标识符
                            # 在Windows系统上运行wmic命令获取网卡标识符
                            result = subprocess.run(
                                ['powershell', '-Command', 
                                "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | ForEach-Object { $_ | Get-NetAdapterAdvancedProperty -RegistryKeyword 'NetCfgInstanceId' | Select-Object -ExpandProperty RegistryValue }"],
                                capture_output=True, text=True, check=False
                            )
                            
                            if result.returncode == 0 and result.stdout.strip():
                                device_id = result.stdout.strip().split('\n')[0].strip()
                                adapter_uid = f"\\Device\\NPF_{{{device_id}}}"
                                logger.info(f"使用网络适配器标识符: {adapter_uid}")
                            else:
                                logger.warning(f"无法获取网络适配器标识符，使用默认值: {adapter_uid}")
                        except Exception as e:
                            logger.warning(f"获取网络适配器标识符失败: {str(e)}")
                    
                    # 添加接口映射子元素
                    interface_map = ET.SubElement(slot, 'interfaceMap', {
                        'sztype': 'Ethernet',
                        'interfacename': 'Ethernet',
                        'displayNo': '1',
                        'remoteDisplayNo': '2',
                        'adapterUid': adapter_uid,
                        'isOpen': '1',
                        'udpPort': '0',
                        'peerIPAdd': '0.0.0.0',
                        'peerIP': '0',
                        'peerPort': '0'
                    })
                    
                    # 添加第二个接口映射（用于对接虚拟设备）
                    interface_map2 = ET.SubElement(slot, 'interfaceMap', {
                        'sztype': 'Ethernet',
                        'interfacename': 'Ethernet',
                        'displayNo': '2',
                        'remoteDisplayNo': '1',
                        'adapterUid': '',
                        'isOpen': '0',
                        'udpPort': '0',
                        'peerIPAdd': '0.0.0.0',
                        'peerIP': '0',
                        'peerPort': '0'
                    })
                
                elif device_type == "FRSW":
                    ET.SubElement(slot, 'interface', {'sztype': 'Serial', 'interfacename': 'Serial', 'count': '4'})
                
                elif device_type == "HUB":
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'Ethernet', 'count': '8'})
                
                else:
                    # 默认接口配置
                    ET.SubElement(slot, 'interface', {'sztype': 'Ethernet', 'interfacename': 'Ethernet', 'count': '1'})
                
                logger.info(f"添加设备: {device['name']} (ID: {device_id})")
            
            # 添加连接线 - 与老师代码相同
            lines = ET.SubElement(topo, 'lines')
            
            # 处理连接
            for conn in topology["connections"]:
                source = conn["source"].split(":")
                target = conn["target"].split(":")
                
                src_dev_name = source[0]
                src_port = source[1]
                dst_dev_name = target[0]
                dst_port = target[1]
                
                # 获取设备ID
                if src_dev_name not in device_id_map:
                    logger.warning(f"未找到源设备: {src_dev_name}")
                    continue
                if dst_dev_name not in device_id_map:
                    logger.warning(f"未找到目标设备: {dst_dev_name}")
                    continue
                
                src_dev_id = device_id_map[src_dev_name]
                dst_dev_id = device_id_map[dst_dev_name]
                
                # 创建线条 - 与老师代码完全相同
                line = ET.SubElement(lines, 'line', {
                    'srcDeviceID': src_dev_id,
                    'destDeviceID': dst_dev_id
                })
                
                # 简化接口索引提取
                src_index = self._get_interface_index(src_port)
                dst_index = self._get_interface_index(dst_port)
                
                # 创建接口对 - 完全匹配可通拓扑文件的参数
                ET.SubElement(line, 'interfacePair', {
                    'lineName': 'Copper',
                    'srcIndex': str(src_index),
                    'srcBoundRectIsMoved': '1',
                    'srcBoundRect_X': '251.898056',
                    'srcBoundRect_Y': '238.959305',
                    'srcOffset_X': '0.000000',
                    'srcOffset_Y': '0.000000',
                    'tarIndex': str(dst_index),
                    'tarBoundRectIsMoved': '1',
                    'tarBoundRect_X': '339.101959',
                    'tarBoundRect_Y': '249.040695',
                    'tarOffset_X': '0.000000',
                    'tarOffset_Y': '0.000000',
                    'srcIfindex': '0',
                    'tarIfindex': '0',
                    'speedlimit': '100.0'
                })
                
                logger.info(f"添加连接: {src_dev_name}:{src_port}({src_index}) -> {dst_dev_name}:{dst_port}({dst_index})")
            
            # 添加空节点 - 与老师代码完全相同
            ET.SubElement(topo, 'shapes')
            ET.SubElement(topo, 'txttips')
            
            # 格式化XML - 使用老师提供的prettify函数
            def prettify(elem):
                """格式化XML输出"""
                rough_string = ET.tostring(elem, 'utf-8')
                reparsed = minidom.parseString(rough_string)
                return reparsed.toprettyxml(indent="  ")
                
            # 保存到文件 - 使用老师的方式
            try:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(prettify(topo))
                
                # 确认文件是否成功写入
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    logger.info(f"topo文件已生成 {output_file} (大小: {file_size} 字节)")
                    
                    if file_size == 0:
                        logger.error("生成的文件大小为0字节")
                        return None
                    
                    # 预览文件内容前100个字符
                    try:
                        with open(output_file, "r", encoding="utf-8") as preview:
                            content_preview = preview.read(100)
                            logger.info(f"文件内容预览: {content_preview}...")
                    except Exception as read_error:
                        logger.warning(f"无法预览文件内容: {str(read_error)}")
                    
                    return output_file
                else:
                    logger.error(f"文件未成功创建 {output_file}")
                    return None
            except Exception as file_error:
                logger.error(f"写入文件时出错: {str(file_error)}")
                # 使用二进制模式作为备份方案
                try:
                    xml_str = prettify(topo)
                    with open(output_file, "wb") as f:
                        f.write(xml_str.encode('utf-8'))
                    logger.info(f"使用二进制模式成功写入文件 {output_file}")
                    return output_file
                except Exception as binary_error:
                    logger.error(f"二进制写入也失败: {str(binary_error)}")
                    return None
                
        except Exception as e:
            logger.error(f"生成topo文件时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def _get_interface_index(self, interface_name: str) -> int:
        """从接口名获取索引
        
        Args:
            interface_name: 接口名称，如GE0/0/1
            
        Returns:
            接口索引
        """
        # 从接口名提取索引
        if not interface_name:
            return 0
            
        # 提取数字部分作为索引
        # 对于如GE0/0/1这样的接口名，取最后的数字作为索引
        import re
        match = re.search(r'(\d+)$', interface_name)
        if match:
            return int(match.group(1))
        return 0
    
    def _get_template(self, device_type: str) -> Dict[str, Any]:
        """获取设备模板
        
        Args:
            device_type: 设备类型
            
        Returns:
            设备模板信息
            
        Raises:
            ValueError: 设备类型不支持时抛出
        """
        template = self.DEVICE_TEMPLATES.get(device_type)
        if not template:
            # 如果没有精确匹配，尝试模糊匹配
            for key, value in self.DEVICE_TEMPLATES.items():
                if key in device_type:
                    return value
            raise ValueError(f"不支持的设备类型: {device_type}")
        return template
    
    def _generate_device_config(self, template: Dict[str, Any], device_data: Dict[str, Any]) -> str:
        """生成设备配置
        
        Args:
            template: 设备模板
            device_data: 设备数据
            
        Returns:
            生成的设备配置
        """
        try:
            # 修复模板路径
            templates_dir = Path(__file__).parent.parent / "templates"
            if not templates_dir.exists():
                templates_dir.mkdir(exist_ok=True)
                logger.warning(f"创建模板目录: {templates_dir}")
            
            # 创建模板环境
            env = Environment(
                loader=FileSystemLoader([templates_dir, self.templates_dir], encoding='utf-8'),
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            # 检查模板文件是否存在
            template_file = template.get("base_config", "")
            template_path = templates_dir / template_file
            
            if not template_path.exists():
                # 如果模板文件不存在，使用硬编码的配置
                logger.warning(f"模板文件不存在: {template_path}，使用默认配置")
                
                # 根据设备类型选择不同的硬编码配置
                device_type = device_data["type"]
                
                # 交换机设备
                if any(sw in device_type for sw in ["S5700", "S5730", "S3700", "CE6850", "CE6800", "CE12800"]):
                    # 交换机配置
                    config = f"""#
# {device_data["name"]} 配置
#
sysname {device_data["name"]}
#
# VLAN基础配置
vlan batch 1
"""
                    # 添加VLAN配置
                    if device_data.get("vlans"):
                        vlan_list = " ".join(device_data["vlans"])
                        config += f"""vlan batch {vlan_list}
"""
                        for vlan in device_data["vlans"]:
                            config += f"""vlan {vlan}
 description VLAN-{vlan}
"""
                    
                    config += """#
# 系统服务配置
undo telnet server enable
stelnet server enable
#
"""
                    # 管理接口配置
                    if device_data.get("management_ip"):
                        config += f"""# 管理接口配置
interface Vlanif1
 description Management_Interface
 ip address {device_data["management_ip"]} {device_data.get("subnet_mask", "255.255.255.0")}
quit
#
"""
                    
                    # 接口基础配置
                    config += """# 接口基础配置
interface GigabitEthernet0/0/1
 port link-type access
 port default vlan 1
 undo shutdown
quit
#
# 安全访问配置
acl 2000
 rule 5 permit source 192.168.0.0 0.0.255.255
 rule 10 permit icmp
quit
#
# ICMP响应配置
undo ip icmp rate-limit
"""

                    if device_data.get("management_ip"):
                        config += "ip icmp source Vlanif1\n"
                    
                    config += """#
# 日志配置
info-center enable
info-center source default channel 0 log level warning
#
save
return
"""
                    return config
                
                # 路由器设备
                elif any(ar in device_type for ar in ["AR2220", "AR3260"]):
                    # 路由器配置
                    config = f"""#
sysname {device_data["name"]}
#
undo info-center enable
#
"""
                    # 确保启用接口并配置IP地址
                    if device_data.get("management_ip"):
                        config += f"""interface GigabitEthernet0/0/0
 ip address {device_data["management_ip"]} {device_data.get("subnet_mask", "255.255.255.0")}
 undo shutdown
#
"""
                    # 添加GE0/0/1接口配置，确保所有接口都启用
                    config += f"""interface GigabitEthernet0/0/1
 undo shutdown
#
"""
                    # 添加基本的路由配置，确保网络连通性
                    if device_data.get("management_ip"):
                        ip_parts = device_data["management_ip"].split('.')
                        gateway = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.1"
                        config += f"""ip route-static 0.0.0.0 0.0.0.0 {gateway}
#
"""
                    config += "return"
                    return config
                
                # 防火墙设备
                elif "USG" in device_type:
                    # 防火墙配置
                    config = f"""#
# {device_data["name"]} 配置
#
sysname {device_data["name"]}
#
# 系统基本配置
info-center timestamp debugging date-time
info-center timestamp log date-time
info-center timestamp trap date-time
info-center terminal logging level informational
#
# 安全区域配置
firewall zone trust
firewall zone untrust
#
"""
                    if device_data.get("management_ip"):
                        config += f"""# 管理接口配置
interface GigabitEthernet1/0/1
 description Management_Interface
 ip address {device_data["management_ip"]} {device_data.get("subnet_mask", "255.255.255.0")}
 firewall zone trust
 undo shutdown
#
interface GigabitEthernet1/0/2
 description External_Interface 
 undo shutdown
 firewall zone untrust
#
"""
                    
                    # 添加ICMP通信规则
                    config += """# 安全策略配置 - 允许ICMP
security-policy
 rule name allow-icmp
  action permit
  source-zone trust
  destination-zone untrust
  service ICMP
 rule name allow-icmp-inbound
  action permit
  source-zone untrust
  destination-zone trust
  service ICMP
quit
#
# ICMP配置
policy interzone trust untrust
 policy 10 permit icmp
quit
policy interzone untrust trust
 policy 10 permit icmp
quit
#
# 启用PING响应
ip icmp-reply
ip unreachable
#
save
y
return
"""
                    return config
                
                # 无线设备
                elif any(ac in device_type for ac in ["AC6005", "AC6605"]):
                    # AC配置
                    config = f"""#
sysname {device_data["name"]}
#
vlan batch 1
#
undo info-center enable
#
"""
                    if device_data.get("management_ip"):
                        config += f"""interface Vlanif1
 ip address {device_data["management_ip"]} {device_data.get("subnet_mask", "255.255.255.0")}
#
"""
                    config += "return"
                    return config
                
                elif "AD9430" in device_type:
                    # AP配置
                    config = f"""#
sysname {device_data["name"]}
#
undo info-center enable
#
"""
                    config += "return"
                    return config
                
                # PC及终端设备
                elif device_type in ["PC", "Client", "Server", "MCS", "STA", "Cellphone"]:
                    # PC配置
                    config = f"hostname {device_data['name']}"
                    if device_data.get("management_ip"):
                        config += f"\nip {device_data['management_ip']} {device_data.get('subnet_mask', '255.255.255.0')}"
                    return config
                
                # 云设备
                elif device_type in ["Cloud", "FRSW", "HUB"]:
                    # 云设备配置
                    return f"hostname {device_data['name']}"
                
                else:
                    # 默认配置
                    return f"sysname {device_data['name']}\nreturn"
            
            # 正常使用模板渲染
            jinja_template = env.get_template(template_file)
            return jinja_template.render(device=device_data)
            
        except Exception as e:
            logger.error(f"生成设备配置失败: {str(e)}")
            # 模板渲染失败时，使用基础配置
            return f"sysname {device_data['name']}\nreturn"
    
    def _init_interfaces(self, template: Dict[str, Any]) -> List[Dict[str, Any]]:
        """初始化接口列表
        
        Args:
            template: 设备模板
            
        Returns:
            接口列表
        """
        interfaces = []
        for iface_range in template["interfaces"]:
            if "-" in iface_range:
                base, range_str = iface_range.split("-")
                prefix = base.rstrip("0123456789")
                start_idx = int(base[len(prefix):])
                end_idx = int(range_str)
                
                for i in range(start_idx, end_idx + 1):
                    interfaces.append({
                        "name": f"{prefix}{i}",
                        "connected": False,
                        "remote_device": None,
                        "remote_interface": None
                    })
            else:
                interfaces.append({
                    "name": iface_range,
                    "connected": False,
                    "remote_device": None,
                    "remote_interface": None
                })
        
        return interfaces
    
    def _parse_connection_point(self, connection_str: str) -> Tuple[str, str]:
        """解析连接点字符串
        
        Args:
            connection_str: 连接点字符串，格式为'设备:接口'
            
        Returns:
            设备名和接口名的元组
        """
        parts = connection_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"连接点格式错误: {connection_str}")
        return parts[0], parts[1]
    
    def save_topology(self, topology: Dict[str, Any], output_file: str) -> None:
        """保存拓扑到JSON文件
        
        Args:
            topology: 拓扑数据
            output_file: 输出文件路径
        """
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(topology, f, ensure_ascii=False, indent=4)
        logger.info(f"拓扑已保存到：{output_file}")
    
    def save_topo_file(self, topology: Dict[str, Any], output_file: str) -> None:
        """保存拓扑为eNSP的.topo文件
        
        Args:
            topology: 拓扑数据
            output_file: 输出文件路径（应以.topo结尾）
        """
        xml_content = self.generate_topo_file(topology, output_file)
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        logger.info(f"eNSP拓扑文件已保存到：{output_file}")
    
    def validate_topology(self, topology: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证拓扑配置的有效性
        
        Args:
            topology: 拓扑配置
            
        Returns:
            验证结果和问题列表
        """
        issues = []
        valid = True
        
        # 检查设备配置
        for device in topology["devices"]:
            # 检查设备名称
            if not device.get("name"):
                issues.append(f"设备缺少名称")
                valid = False
            
            # 检查设备类型
            if not device.get("type"):
                issues.append(f"设备 {device.get('name', 'Unknown')} 缺少类型")
                valid = False
            
            # 检查设备配置
            if not device.get("config"):
                issues.append(f"设备 {device.get('name', 'Unknown')} 缺少配置")
                valid = False
            
            # 检查接口配置
            config = device.get("config", "")
            if "interface" in config:
                # 对于路由器设备，检查接口是否启用
                if "AR" in device.get("type", "") and "undo shutdown" not in config:
                    issues.append(f"设备 {device.get('name', 'Unknown')} 的接口未启用")
                    valid = False
                
                # 对于交换机设备，检查VLAN配置
                if "S5700" in device.get("type", "") and "vlan batch" not in config:
                    issues.append(f"设备 {device.get('name', 'Unknown')} 的VLAN配置可能有问题")
                    valid = False
        
        # 检查连接配置
        device_names = [device["name"] for device in topology["devices"]]
        for connection in topology["connections"]:
            src = connection.get("source", "").split(":")[0]
            dst = connection.get("target", "").split(":")[0]
            
            # 检查连接的设备是否存在
            if src not in device_names:
                issues.append(f"连接中的源设备 {src} 不存在")
                valid = False
            
            if dst not in device_names:
                issues.append(f"连接中的目标设备 {dst} 不存在")
                valid = False
        
        # 检查IP地址冲突
        ip_addresses = {}
        for device in topology["devices"]:
            config = device.get("config", "")
            for line in config.split("\n"):
                if "ip address" in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        ip = parts[parts.index("address") + 1]
                        if ip in ip_addresses:
                            issues.append(f"IP地址冲突: {ip} 在设备 {device['name']} 和 {ip_addresses[ip]} 上都配置了")
                            valid = False
                        else:
                            ip_addresses[ip] = device["name"]
        
        return valid, issues

    def _fix_topology_issues(self, topology: Dict[str, Any], issues: List[str]) -> None:
        """尝试修复拓扑中的问题
        
        Args:
            topology: 拓扑配置
            issues: 问题列表
        """
        # 修复接口未启用问题
        for device in topology["devices"]:
            if "AR" in device.get("type", "") and "undo shutdown" not in device.get("config", ""):
                logger.info(f"修复设备 {device['name']} 的接口状态")
                # 在config中添加undo shutdown
                config_lines = device["config"].split("\n")
                new_config = []
                for line in config_lines:
                    new_config.append(line)
                    if "interface" in line and "GigabitEthernet" in line:
                        new_config.append(" undo shutdown")
                device["config"] = "\n".join(new_config)
            
        # 修复IP地址冲突
        ip_addresses = {}
        conflicting_devices = set()
        
        # 找出所有冲突的IP和设备
        for device in topology["devices"]:
            config = device.get("config", "")
            new_config_lines = []
            changed = False
            
            for line in config.split("\n"):
                if "ip address" in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        ip_index = parts.index("address") + 1
                        ip = parts[ip_index]
                        
                        if ip in ip_addresses:
                            # 冲突了，生成新IP
                            conflicting_devices.add(device["name"])
                            old_ip = ip
                            ip_parts = ip.split('.')
                            new_last_octet = str((int(ip_parts[3]) + 10) % 254)
                            if new_last_octet == "0":
                                new_last_octet = "1"
                            new_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{new_last_octet}"
                            
                            # 检查新IP是否也冲突
                            while new_ip in ip_addresses.values():
                                new_last_octet = str((int(new_last_octet) + 1) % 254)
                                if new_last_octet == "0":
                                    new_last_octet = "1"
                                new_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.{new_last_octet}"
                            
                            logger.info(f"修复IP冲突: 设备 {device['name']} 的IP从 {old_ip} 改为 {new_ip}")
                            parts[ip_index] = new_ip
                            line = " ".join(parts)
                            changed = True
                        
                        ip_addresses[ip] = device["name"]
                
                new_config_lines.append(line)
            
            if changed:
                device["config"] = "\n".join(new_config_lines)
