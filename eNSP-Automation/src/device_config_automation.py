#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
设备配置自动化模块
用于SSH连接网络设备并执行命令
"""

import time
import logging

try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import NetMikoTimeoutException, NetMikoAuthenticationException
except ImportError:
    # 如果没有netmiko，我们提供一个兼容性警告
    ConnectHandler = None
    class NetMikoTimeoutException(Exception): pass
    class NetMikoAuthenticationException(Exception): pass
    logging.getLogger(__name__).warning("无法导入netmiko模块，SSH功能将不可用。请使用pip install netmiko安装")

logger = logging.getLogger(__name__)

class DeviceConfigAutomation:
    """网络设备SSH连接和配置自动化类"""
    
    def __init__(self):
        """初始化设备配置自动化对象"""
        if ConnectHandler is None:
            logger.warning("未安装netmiko模块，SSH功能不可用")
        self.connection = None
        self.device_info = None
    
    def connect(self, ip, username, password, device_type='huawei', port=22, timeout=60):
        """
        连接到网络设备
        
        Args:
            ip (str): 设备IP地址
            username (str): 登录用户名
            password (str): 登录密码
            device_type (str): 设备类型，默认为'huawei'
            port (int): SSH端口，默认为22
            timeout (int): 连接超时时间，默认为60秒
            
        Returns:
            bool: 连接成功返回True，否则返回False
        """
        if ConnectHandler is None:
            logger.error("未安装netmiko模块，无法使用SSH功能")
            return False
            
        self.device_info = {
            'device_type': device_type,
            'host': ip,
            'username': username,
            'password': password,
            'port': port,
            'timeout': timeout,
        }
        
        try:
            logger.info(f"正在连接设备 {ip}...")
            self.connection = ConnectHandler(**self.device_info)
            logger.info(f"成功连接到设备 {ip}")
            return True
        except NetMikoTimeoutException:
            logger.error(f"连接超时: {ip}")
            return False
        except NetMikoAuthenticationException:
            logger.error(f"认证失败: {ip}")
            return False
        except Exception as e:
            logger.error(f"连接失败: {ip}, 错误: {str(e)}")
            return False
    
    def disconnect(self):
        """断开与设备的连接"""
        if self.connection:
            self.connection.disconnect()
            logger.info("已断开设备连接")
            self.connection = None
    
    def execute_command(self, command):
        """
        执行单个命令
        
        Args:
            command (str): 要执行的命令
            
        Returns:
            str: 命令执行结果
        """
        if not self.connection:
            logger.error("未连接到设备")
            return ""
        
        try:
            output = self.connection.send_command(command)
            return output
        except Exception as e:
            logger.error(f"执行命令失败: {command}, 错误: {str(e)}")
            return f"命令执行错误: {str(e)}"
    
    def execute_commands(self, commands):
        """
        执行多个命令
        
        Args:
            commands (list): 命令列表
            
        Returns:
            str: 所有命令执行结果
        """
        if not self.connection:
            logger.error("未连接到设备")
            return ""
        
        results = []
        for cmd in commands:
            logger.info(f"执行命令: {cmd}")
            output = self.execute_command(cmd)
            results.append(f"命令: {cmd}\n{output}\n")
        
        return "\n".join(results)
    
    def configure(self, config_commands):
        """
        进入配置模式并执行配置命令
        
        Args:
            config_commands (list): 配置命令列表
            
        Returns:
            str: 配置命令执行结果
        """
        if not self.connection:
            logger.error("未连接到设备")
            return ""
        
        try:
            logger.info("进入配置模式...")
            output = self.connection.send_config_set(config_commands)
            logger.info("配置命令已执行")
            return output
        except Exception as e:
            logger.error(f"配置失败, 错误: {str(e)}")
            return f"配置错误: {str(e)}"
    
    @staticmethod
    def wait_for_device(ip, max_attempts=30, wait_time=10):
        """
        等待设备变为可访问状态
        
        Args:
            ip (str): 设备IP地址
            max_attempts (int): 最大尝试次数
            wait_time (int): 每次尝试间隔时间(秒)
            
        Returns:
            bool: 设备可访问返回True，否则返回False
        """
        import socket
        
        logger.info(f"等待设备 {ip} 变为可访问...")
        
        for attempt in range(max_attempts):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, 22))
            sock.close()
            
            if result == 0:
                logger.info(f"设备 {ip} 已可访问")
                return True
            
            logger.info(f"等待设备 {ip}，尝试 {attempt+1}/{max_attempts}")
            time.sleep(wait_time)
        
        logger.error(f"设备 {ip} 在 {max_attempts} 次尝试后仍不可访问")
        return False 