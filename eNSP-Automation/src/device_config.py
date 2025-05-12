#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
eNSP设备SSH配置自动化模块
用于与eNSP中的设备建立SSH连接并自动化配置
"""

import time
import logging
import os  # 新增导入os模块
from typing import List, Dict, Any, Optional
from pathlib import Path

# 设置日志
logger = logging.getLogger(__name__)

class DeviceConfigAutomation:
    """设备配置自动化工具，使用Netmiko连接设备"""
    
    def __init__(self):
        """初始化配置自动化工具"""
        self._check_dependencies()
        self.connections = {}
    
    def _check_dependencies(self):
        """检查依赖是否安装"""
        try:
            import netmiko
            logger.info("成功导入netmiko库")
        except ImportError:
            logger.error("无法导入netmiko库，请运行 pip install netmiko 安装")
            raise ImportError("请先安装netmiko库: pip install netmiko")
    
    def connect_device(self, device_ip: str, username: str = "admin", 
                      password: str = "huawei@123", port: int = 22, 
                      device_type: str = "huawei") -> bool:
        """连接设备
        
        Args:
            device_ip: 设备IP地址
            username: 用户名，默认admin
            password: 密码，默认huawei@123
            port: SSH端口，默认22
            device_type: 设备类型，默认huawei
            
        Returns:
            连接是否成功
        """
        try:
            # 创建日志文件
            log_file = 'ensp_device_session.log'
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"=== 设备连接开始：{device_ip} {time.ctime()} ===\n")
                log.write(f"Device settings: {device_type} {device_ip}:{port}\n\n")
            
            from netmiko import ConnectHandler
            import paramiko
            import socket
            
            # 首先检查设备是否可达
            logger.info(f"检查设备 {device_ip} 是否可达...")
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"[检查] 测试设备 {device_ip} 是否可达...\n")
            
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)  # 增加超时时间
                s.connect((device_ip, port))
                s.close()
                logger.info(f"设备 {device_ip} 可达")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[成功] 设备 {device_ip} 端口 {port} 可达\n")
            except (socket.timeout, ConnectionRefusedError) as e:
                logger.error(f"设备 {device_ip} 不可达或SSH端口未开放: {str(e)}")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 设备 {device_ip} 不可达: {str(e)}\n")
                return False
            
            # 设备连接参数
            device_params = {
                "device_type": device_type,
                "ip": device_ip,
                "username": username,
                "password": password,
                "port": port,
                "timeout": 15,  # 增加超时时间
                "auth_timeout": 15,  # 认证超时
                "banner_timeout": 15,  # banner超时
                "session_timeout": 60,  # 会话超时
                "global_delay_factor": 2,  # 全局延迟因子
                "fast_cli": False,  # 关闭快速CLI以提高兼容性
            }
            
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"[连接] 尝试连接设备 {device_ip}...\n")
            
            # 创建 SSH 客户端（类似用户提供的示例代码）
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接设备
            logger.info(f"正在连接设备 {device_ip}...")
            try:
                # 先尝试直接使用paramiko连接
                ssh.connect(hostname=device_ip, 
                           username=username, 
                           password=password, 
                           port=port, 
                           timeout=15,
                           allow_agent=False,
                           look_for_keys=False)
                
                # 获取shell
                shell = ssh.invoke_shell()
                time.sleep(1)  # 等待shell准备好
                
                # 测试shell是否正常
                shell.send('\n')
                time.sleep(0.5)
                output = shell.recv(65535).decode('utf-8', 'ignore')
                
                # 记录连接成功
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[成功] 已成功连接到设备 {device_ip} (paramiko方式)\n")
                    log.write(f"[输出] 初始输出: {output}\n")
                
                # 关闭paramiko连接，使用netmiko进行后续操作
                ssh.close()
                
                # 使用netmiko进行实际操作
                connection = ConnectHandler(**device_params)
                self.connections[device_ip] = connection
                
                # 获取设备基本信息
                try:
                    output = connection.send_command("display version", 
                                                   read_timeout=10)
                    
                    version_info = output.splitlines()[0] if output else '未知'
                    logger.info(f"设备信息: {version_info}")
                    
                    with open(log_file, 'a', encoding='utf-8') as log:
                        log.write(f"[信息] 设备版本: {version_info}\n")
                        log.write(f"[输出] {output}\n\n")
                        
                except Exception as e:
                    logger.warning(f"获取设备信息失败: {str(e)}")
                    with open(log_file, 'a', encoding='utf-8') as log:
                        log.write(f"[警告] 获取设备信息失败: {str(e)}\n")
                
                logger.info(f"成功连接到设备 {device_ip}")
                return True
                
            except paramiko.AuthenticationException:
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 认证失败，请检查用户名和密码\n")
                logger.error(f"认证失败，请检查用户名和密码")
                return False
                
            except (paramiko.SSHException, socket.timeout) as e:
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] SSH连接错误: {str(e)}\n")
                logger.error(f"SSH连接错误: {str(e)}")
                
                # 如果paramiko连接失败，尝试直接使用netmiko
                try:
                    with open(log_file, 'a', encoding='utf-8') as log:
                        log.write(f"[重试] 使用netmiko尝试连接设备 {device_ip}...\n")
                    
                    connection = ConnectHandler(**device_params)
                    
                    if connection.is_alive():
                        self.connections[device_ip] = connection
                        logger.info(f"成功连接到设备 {device_ip} (netmiko方式)")
                        
                        with open(log_file, 'a', encoding='utf-8') as log:
                            log.write(f"[成功] 已成功连接到设备 {device_ip} (netmiko方式)\n")
                        
                        # 获取设备基本信息
                        try:
                            output = connection.send_command("display version")
                            version_info = output.splitlines()[0] if output else '未知'
                            logger.info(f"设备信息: {version_info}")
                            
                            with open(log_file, 'a', encoding='utf-8') as log:
                                log.write(f"[信息] 设备版本: {version_info}\n")
                        except Exception as e:
                            logger.warning(f"获取设备信息失败: {str(e)}")
                        
                        return True
                    else:
                        logger.error(f"连接到设备 {device_ip} 失败: 连接不活跃")
                        with open(log_file, 'a', encoding='utf-8') as log:
                            log.write(f"[错误] 连接不活跃\n")
                        return False
                        
                except Exception as retry_e:
                    logger.error(f"重试连接设备 {device_ip} 失败: {str(retry_e)}")
                    with open(log_file, 'a', encoding='utf-8') as log:
                        log.write(f"[错误] 重试连接失败: {str(retry_e)}\n")
                    return False
            
        except Exception as e:
            logger.error(f"连接设备 {device_ip} 失败: {str(e)}")
            # 提供更详细的错误信息
            log_file = 'ensp_device_session.log'
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"[错误] 连接失败: {str(e)}\n")
                
            if "Authentication failed" in str(e):
                logger.error(f"认证失败，请检查用户名和密码")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 认证失败，请检查用户名和密码\n")
            elif "timed out" in str(e):
                logger.error(f"连接超时，请检查设备IP和端口是否正确")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 连接超时，请检查设备IP和端口是否正确\n")
            elif "Connection refused" in str(e):
                logger.error(f"连接被拒绝，请检查设备SSH服务是否启用")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 连接被拒绝，请检查设备SSH服务是否启用\n")
                    
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"=== 设备连接失败：{device_ip} {time.ctime()} ===\n\n")
            return False
    
    def configure_device(self, device_ip: str, commands: List[str]) -> Optional[str]:
        """配置设备
        
        Args:
            device_ip: 设备IP地址
            commands: 配置命令列表
            
        Returns:
            配置输出或None（如果失败）
        """
        log_file = 'ensp_device_session.log'  # 使用相同的日志文件
        
        # 检查是否已连接，如果没有则尝试连接
        if device_ip not in self.connections:
            logger.error(f"设备 {device_ip} 未连接")
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"[错误] 设备 {device_ip} 未连接，无法配置\n")
            return None
        
        # 记录开始配置
        logger.info(f"正在配置设备 {device_ip}...")
        with open(log_file, 'a', encoding='utf-8') as log:
            log.write(f"=== 配置会话开始 {time.ctime()} ===\n")
            log.write(f"设备: {device_ip}\n")
        
        all_output = ""
        
        try:
            # 直接创建新的SSH会话，而不使用现有连接
            # 这样可以确保命令执行的可靠性，避免连接中断问题
            import paramiko
            
            # 获取原始连接信息
            old_connection = self.connections[device_ip]
            username = old_connection.username
            password = old_connection.password
            port = old_connection.port
            
            # 创建SSH客户端
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接设备
            logger.info(f"为执行命令创建新的SSH会话...")
            ssh.connect(hostname=device_ip, username=username, password=password, port=port)
            
            # 打开交互式shell
            shell = ssh.invoke_shell()
            time.sleep(1)  # 等待shell初始化
            output = shell.recv(65535).decode('utf-8', 'ignore')
            logger.info(f"SSH会话初始输出: {output.strip()}")
            
            # 发送命令函数
            def send_command(command, wait_time=1):
                logger.info(f"发送命令: '{command}'")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[命令] {command}\n")
                
                shell.send(command + '\n')
                time.sleep(wait_time)  # 等待命令执行
                
                # 等待并接收所有输出
                output = ""
                while shell.recv_ready():
                    part = shell.recv(65535).decode('utf-8', 'ignore')
                    output += part
                    time.sleep(0.1)
                
                logger.info(f"命令 '{command}' 输出:\n{output}")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[输出] {output}\n\n")
                return output
            
            # 执行命令
            if len(commands) > 0:
                for command in commands:
                    command_output = send_command(command)
                    all_output += command_output + "\n"
                    
                    # 如果是save命令，可能需要确认
                    if command.lower() == "save":
                        # 发送确认
                        time.sleep(1)
                        send_command("y", wait_time=2)
            
            # 完成配置后，验证接口配置
            for command in commands:
                if "interface " in command.lower():
                    interface_name = command.split("interface ")[1].strip()
                    verify_cmd = f"display current-configuration interface {interface_name}"
                    verification_output = send_command(verify_cmd, wait_time=2)
                    
                    logger.info(f"验证接口 {interface_name} 配置:\n{verification_output}")
                    with open(log_file, 'a', encoding='utf-8') as log:
                        log.write(f"[验证] 接口配置:\n{verification_output}\n\n")
                    break
            
            # 关闭SSH会话
            ssh.close()
            logger.info(f"SSH会话已关闭")
            
            logger.info(f"设备 {device_ip} 配置完成")
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"=== 配置会话结束 {time.ctime()} ===\n\n")
            
            return all_output
            
        except Exception as e:
            logger.error(f"配置设备 {device_ip} 失败: {str(e)}")
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"[错误] 配置失败: {str(e)}\n")
                log.write(f"=== 配置会话异常终止 {time.ctime()} ===\n\n")
            return None
    
    def execute_command(self, device_ip: str, command: str) -> Optional[str]:
        """执行单个命令并返回结果
        
        Args:
            device_ip: 设备IP地址
            command: 要执行的命令
            
        Returns:
            命令输出或None（如果失败）
        """
        if device_ip not in self.connections:
            logger.error(f"设备 {device_ip} 未连接")
            return None
        
        try:
            connection = self.connections[device_ip]
            logger.info(f"在设备 {device_ip} 上执行命令: {command}")
            output = connection.send_command(command)
            return output
            
        except Exception as e:
            logger.error(f"在设备 {device_ip} 上执行命令失败: {str(e)}")
            return None
    
    def configure_ssh_access(self, device_ip: str, username: str = "admin", 
                           password: str = "huawei@123") -> bool:
        """配置设备的SSH访问（通常在首次启动时需要）
        
        Args:
            device_ip: 设备IP地址
            username: SSH用户名
            password: SSH密码
            
        Returns:
            配置是否成功
        """
        # 这里需要假设已经通过Console或其他方式连接到设备
        try:
            from netmiko import ConnectHandler
            import time
            
            # 连接参数
            device_params = {
                "device_type": "huawei", 
                "ip": device_ip,
                "username": "admin",  # 默认用户名
                "password": "admin",  # 默认密码
                "port": 23,           # Telnet端口
                "timeout": 15,        # 增加超时时间
                "global_delay_factor": 2  # 全局延迟因子
            }
            
            # 尝试通过Telnet连接
            logger.info(f"尝试通过Telnet连接到设备 {device_ip}...")
            connection = ConnectHandler(**device_params)
            logger.info(f"成功通过Telnet连接到设备 {device_ip}")
            
            # 等待系统初始化完成
            time.sleep(2)
            
            # SSH配置命令
            # 根据设备类型检测是否需要进入系统视图
            output = connection.send_command("display current-configuration | include sysname")
            
            ssh_commands = []
            
            # 如果没有系统名称，则先设置系统名称
            if not output.strip():
                ssh_commands.append("system-view")
                ssh_commands.append(f"sysname Device_{device_ip.replace('.', '_')}")
            else:
                ssh_commands.append("system-view")
            
            # 配置SSH命令
            ssh_commands.extend([
                "stelnet server enable",
                f"ssh user {username} authentication-type password",
                f"ssh user {username} service-type stelnet",
                "aaa",
                f"local-user {username} password cipher {password}",
                f"local-user {username} service-type ssh",
                f"local-user {username} privilege level 15",
                "quit",
                "user-interface vty 0 4",
                "authentication-mode aaa",
                "protocol inbound ssh",
                "quit",
                "save force"
            ])
            
            # 执行配置前先显示进度
            logger.info(f"正在配置设备 {device_ip} 的SSH服务...")
            
            # 分批执行，增加可靠性
            # 先进入系统视图
            connection.send_command("system-view")
            time.sleep(1)
            
            # 逐条执行命令，增加稳定性
            for cmd in ssh_commands:
                try:
                    logger.info(f"执行命令: {cmd}")
                    output = connection.send_command(cmd, expect_string=r"[>\]]")
                    time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"执行命令 '{cmd}' 时出错: {str(e)}")
            
            # 退出系统视图
            connection.send_command("quit")
            
            # 断开连接
            connection.disconnect()
            
            logger.info(f"设备 {device_ip} SSH服务配置成功")
            logger.info(f"您现在可以通过SSH连接到设备 {device_ip}")
            return True
            
        except Exception as e:
            logger.error(f"配置设备 {device_ip} SSH服务失败: {str(e)}")
            # 提供更多错误信息
            if "timed out" in str(e):
                logger.error(f"连接超时，请确保设备已启动并且Telnet服务已启用")
            elif "Authentication failed" in str(e):
                logger.error(f"认证失败，请检查默认用户名和密码")
            return False
    
    def disconnect_all(self):
        """断开所有连接"""
        for ip, connection in self.connections.items():
            try:
                connection.disconnect()
                logger.info(f"已断开与设备 {ip} 的连接")
            except Exception as e:
                logger.error(f"断开与设备 {ip} 的连接时出错: {str(e)}")
        
        self.connections = {}
    
    def disconnect_device(self, device_ip: str) -> bool:
        """断开特定设备的连接
        
        Args:
            device_ip: 设备IP地址
            
        Returns:
            断开连接是否成功
        """
        if device_ip not in self.connections:
            logger.warning(f"设备 {device_ip} 未连接")
            return False
        
        try:
            self.connections[device_ip].disconnect()
            del self.connections[device_ip]
            logger.info(f"已断开与设备 {device_ip} 的连接")
            return True
        except Exception as e:
            logger.error(f"断开与设备 {device_ip} 的连接时出错: {str(e)}")
            return False
    
    def save_config(self, device_ip: str) -> bool:
        """保存设备配置
        
        Args:
            device_ip: 设备IP地址
            
        Returns:
            保存是否成功
        """
        if device_ip not in self.connections:
            logger.error(f"设备 {device_ip} 未连接")
            return False
        
        try:
            connection = self.connections[device_ip]
            output = connection.send_command_timing("save")
            
            # 处理可能的交互提示
            if "overwrite" in output.lower() or "y/n" in output.lower():
                output += connection.send_command_timing("y")
            
            logger.info(f"设备 {device_ip} 配置已保存")
            return True
            
        except Exception as e:
            logger.error(f"保存设备 {device_ip} 配置失败: {str(e)}")
            return False
    
    def configure_port(self, device_ip: str, port_name: str, vlan_id: int, 
                      port_type: str = "access") -> bool:
        """配置端口的VLAN设置
        
        Args:
            device_ip: 设备IP地址
            port_name: 端口名称，例如：GigabitEthernet0/0/1
            vlan_id: VLAN ID
            port_type: 端口类型，默认为"access"，可选"trunk"
            
        Returns:
            配置是否成功
        """
        log_file = 'ensp_device_session.log'
        
        try:
            # 记录开始配置
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"=== 端口配置开始: {device_ip} {port_name} {time.ctime()} ===\n")
                log.write(f"配置参数: 端口={port_name}, VLAN={vlan_id}, 类型={port_type}\n")
            
            # 检查参数有效性
            if not isinstance(vlan_id, int) or vlan_id < 1 or vlan_id > 4094:
                logger.error(f"无效的VLAN ID: {vlan_id}，VLAN ID必须在1-4094范围内")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 无效的VLAN ID: {vlan_id}\n")
                return False
                
            if not port_name:
                logger.error("未指定端口名称")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 未指定端口名称\n")
                return False
                
            if port_type.lower() not in ["access", "trunk"]:
                logger.error(f"不支持的端口类型: {port_type}，仅支持access或trunk")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 不支持的端口类型: {port_type}\n")
                return False
                
            # 检查连接状态
            if device_ip not in self.connections:
                logger.error(f"设备 {device_ip} 未连接")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[错误] 设备未连接\n")
                return False
            
            # 直接创建新的SSH会话
            import paramiko
            
            # 获取原始连接信息
            old_connection = self.connections[device_ip]
            username = old_connection.username
            password = old_connection.password
            port = old_connection.port
            
            # 创建SSH客户端
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接设备
            logger.info(f"为配置端口创建新的SSH会话...")
            ssh.connect(hostname=device_ip, username=username, password=password, port=port)
            
            # 打开交互式shell
            shell = ssh.invoke_shell()
            time.sleep(1)  # 等待shell初始化
            output = shell.recv(65535).decode('utf-8', 'ignore')
            logger.info(f"SSH会话初始输出: {output.strip()}")
            
            # 发送命令函数
            def send_command(command, wait_time=1):
                logger.info(f"发送命令: '{command}'")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[命令] {command}\n")
                
                shell.send(command + '\n')
                time.sleep(wait_time)  # 等待命令执行
                
                # 等待并接收所有输出
                output = ""
                while shell.recv_ready():
                    part = shell.recv(65535).decode('utf-8', 'ignore')
                    output += part
                    time.sleep(0.1)
                
                logger.info(f"命令 '{command}' 输出:\n{output}")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[输出] {output}\n\n")
                return output
            
            # 进入系统视图并配置VLAN
            send_command('system-view')
            send_command(f'vlan {vlan_id}')
            send_command('quit')  # 退出VLAN配置
            
            # 配置端口
            send_command(f'interface {port_name}')
            
            if port_type.lower() == "access":
                send_command('port link-type access')
                send_command(f'port default vlan {vlan_id}')
            else:  # trunk模式
                send_command('port link-type trunk')
                send_command(f'port trunk allow-pass vlan {vlan_id}')
            
            send_command('quit')  # 退出接口配置
            
            # 保存配置
            send_command('return')  # 返回用户视图
            send_command('save')
            time.sleep(1)  # 等待保存提示
            send_command('y')  # 确认保存
            
            # 验证配置
            logger.info(f"验证端口 {port_name} 配置...")
            send_command('system-view')
            verification_output = send_command(f'display current-configuration interface {port_name}', wait_time=2)
            
            # 验证输出中是否包含期望的配置
            port_type_str = "link-type access" if port_type.lower() == "access" else "link-type trunk"
            vlan_str = f"default vlan {vlan_id}" if port_type.lower() == "access" else f"allow-pass vlan {vlan_id}"
            
            configuration_success = True
            
            if port_type_str not in verification_output:
                logger.warning(f"验证失败: 未找到端口类型 {port_type_str}")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[警告] 验证失败: 未找到端口类型 {port_type_str}\n")
                configuration_success = False
                
            if vlan_str not in verification_output and str(vlan_id) not in verification_output:
                logger.warning(f"验证失败: 未找到VLAN配置 {vlan_str}")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[警告] 验证失败: 未找到VLAN配置 {vlan_str}\n")
                configuration_success = False
            
            # 关闭SSH会话
            ssh.close()
            logger.info(f"SSH会话已关闭")
            
            # 记录验证信息
            if configuration_success:
                logger.info(f"端口 {port_name} 配置验证成功")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(f"[验证] 端口配置验证成功\n")
            
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"=== 端口配置完成 {time.ctime()} ===\n\n")
            
            return True
                
        except Exception as e:
            logger.error(f"配置端口 {port_name} 失败: {str(e)}")
            with open(log_file, 'a', encoding='utf-8') as log:
                log.write(f"[错误] 配置端口失败: {str(e)}\n")
                log.write(f"=== 端口配置失败 {time.ctime()} ===\n\n")
            return False
    
    def configure_interface(self, device_ip, interface, ip_address, netmask, verify=True):
        """配置接口IP地址并验证配置
        
        Args:
            device_ip: 设备IP
            interface: 接口名称
            ip_address: 分配的IP地址
            netmask: 子网掩码
            verify: 是否验证配置结果
            
        Returns:
            配置是否成功
        """
        if device_ip not in self.connections:
            logger.error(f"设备 {device_ip} 未连接")
            return False
        
        # 构建配置命令
        commands = [
            f"interface {interface}",
            f"ip address {ip_address} {netmask}",
            "undo shutdown",  # 确保接口启用
            "description External_Network",
            "quit",
            # 添加ACL配置允许ICMP
            "acl 2000",
            "rule permit icmp",
            "quit",
            # 添加防火墙配置
            "firewall zone trust",
            f"add interface {interface}",
            "quit",
            # 关闭ICMP限速
            "undo ip icmp rate-limit",
            f"ip icmp source {interface}"
        ]
        
        success = True
        for cmd in commands:
            try:
                result = self.send_command(device_ip, cmd)
                logger.info(f"命令'{cmd}' 执行结果: {result}")
                if "Error" in result or "错误" in result:
                    logger.error(f"接口配置失败: {result}")
                    success = False
            except Exception as e:
                logger.error(f"执行命令'{cmd}'失败: {str(e)}")
                success = False
        
        # 验证配置是否生效
        if verify and success:
            time.sleep(1)  # 等待配置生效
            verify_cmd = f"display ip interface brief | include {interface}"
            result = self.send_command(device_ip, verify_cmd)
            if ip_address not in result:
                logger.error(f"接口IP配置未生效: {result}")
                success = False
            else:
                logger.info(f"接口 {interface} 配置IP {ip_address} 成功验证")
                
            # 测试接口连通性
            ping_cmd = f"ping -c 4 {ip_address}"
            result = self.send_command(device_ip, ping_cmd)
            if "100% packet loss" in result:
                logger.warning(f"接口连通性测试失败: {result}")
                # 尝试修复接口状态
                self.send_command(device_ip, f"interface {interface}")
                self.send_command(device_ip, "undo shutdown")
                self.send_command(device_ip, "quit")
        
        return success

    def send_command(self, device_ip, command, timeout=10, expect_prompt=None, wait_time=1):
        """发送命令到设备并等待响应
        
        Args:
            device_ip: 设备IP地址
            command: 要发送的命令
            timeout: 命令执行超时时间
            expect_prompt: 期望的命令提示符，用于确认命令执行完成
            wait_time: 命令执行后的等待时间
            
        Returns:
            命令输出结果
        """
        if device_ip not in self.connections:
            logger.error(f"设备 {device_ip} 未连接")
            return "错误: 设备未连接"
        
        try:
            connection = self.connections[device_ip]
            logger.info(f"发送命令: '{command}'")
            
            # 首先检查连接是否活跃
            if not connection.is_alive():
                logger.warning(f"连接不活跃，尝试重新建立连接")
                try:
                    connection.establish_connection()
                    if not connection.is_alive():
                        logger.error("重新连接失败")
                        return "错误: 连接中断且无法重连"
                except Exception as e:
                    logger.error(f"重新连接时出错: {str(e)}")
                    return f"错误: 连接中断: {str(e)}"
            
            # 使用不同的方法发送命令并处理复杂情况
            try:
                # 首先尝试使用send_command
                output = connection.send_command(
                    command,
                    strip_prompt=False,
                    strip_command=False,
                    read_timeout=timeout,
                    expect_string=expect_prompt
                )
                
                # 等待命令完成
                time.sleep(wait_time)
                
                # 检查是否有错误提示
                if "error" in output.lower() or "invalid" in output.lower():
                    logger.warning(f"命令可能有错误: {output}")
                
                return output
                
            except Exception as cmd_error:
                logger.warning(f"标准命令发送失败，尝试另一种方式: {str(cmd_error)}")
                
                # 使用send_command_timing尝试发送命令
                try:
                    output = connection.send_command_timing(
                        command,
                        strip_prompt=False,
                        strip_command=False,
                        read_timeout=timeout
                    )
                    time.sleep(wait_time)
                    return output
                except Exception as timing_error:
                    logger.error(f"命令执行失败: {str(timing_error)}")
                    return f"错误: 执行失败: {str(timing_error)}"
            
        except Exception as e:
            logger.error(f"发送命令时发生错误: {str(e)}")
            return f"错误: {str(e)}" 