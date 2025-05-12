#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试与eNSP设备的SSH连接脚本
"""

import os
import sys
import time
import logging
import getpass
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

# 添加src目录到Python路径
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / "src"))

# 配置日志
logs_dir = current_dir / "logs"
logs_dir.mkdir(exist_ok=True)
log_file = logs_dir / "ensp_device_test.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(log_file), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_ssh_connection(ip, port=22, username="admin", password=None):
    """测试SSH连接到指定设备
    
    Args:
        ip: 设备IP地址
        port: SSH端口，默认22
        username: 用户名，默认admin
        password: 密码，如果不提供则会提示输入
        
    Returns:
        bool: 连接是否成功
    """
    try:
        import paramiko
        
        if password is None:
            password = getpass.getpass(f"请输入设备 {ip} 的密码: ")
        
        # 创建SSH客户端
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(f"正在连接到设备 {ip}:{port}...")
        start_time = time.time()
        
        # 尝试连接
        client.connect(
            hostname=ip,
            port=port,
            username=username,
            password=password,
            timeout=10
        )
        
        connect_time = time.time() - start_time
        print(f"[OK] 成功连接到设备! (耗时: {connect_time:.2f}秒)")
        
        # 执行简单命令测试
        print("正在执行测试命令...")
        stdin, stdout, stderr = client.exec_command("display version")
        output = stdout.read().decode("utf-8")
        
        # 打印命令输出的前几行
        lines = output.splitlines()
        if lines:
            print("\n命令输出 (部分):")
            for i, line in enumerate(lines[:10]):
                print(f"  {line}")
            if len(lines) > 10:
                print(f"  ... (还有 {len(lines) - 10} 行)")
        
        # 关闭连接
        client.close()
        print("\n[OK] 测试完成，SSH连接正常！")
        return True
        
    except ImportError:
        print("[ERROR] 错误: 缺少paramiko库，请使用以下命令安装:")
        print("   pip install paramiko")
        return False
    except Exception as e:
        print(f"[ERROR] 连接失败: {str(e)}")
        print("\n可能的解决方案:")
        print("1. 确保设备已启动并可访问")
        print("2. 验证IP地址、端口、用户名和密码是否正确")
        print("3. 确保设备已配置SSH服务并启用")
        print("4. 检查网络连接和防火墙设置")
        return False

def test_telnet_connection(ip, port=23, username="admin", password=None):
    """测试Telnet连接到指定设备
    
    Args:
        ip: 设备IP地址
        port: Telnet端口，默认23
        username: 用户名，默认admin
        password: 密码，如果不提供则会提示输入
        
    Returns:
        bool: 连接是否成功
    """
    try:
        from telnetlib import Telnet
        
        if password is None:
            password = getpass.getpass(f"请输入设备 {ip} 的密码: ")
        
        print(f"正在通过Telnet连接到设备 {ip}:{port}...")
        start_time = time.time()
        
        # 尝试连接
        tn = Telnet(ip, port, timeout=10)
        
        # 等待登录提示
        tn.read_until(b"Username:", timeout=5)
        tn.write(username.encode('ascii') + b"\n")
        
        tn.read_until(b"Password:", timeout=5)
        tn.write(password.encode('ascii') + b"\n")
        
        # 检查是否成功登录
        output = tn.read_until(b">", timeout=5).decode('ascii')
        
        connect_time = time.time() - start_time
        print(f"[OK] 成功连接到设备! (耗时: {connect_time:.2f}秒)")
        
        # 执行简单命令测试
        print("正在执行测试命令...")
        tn.write(b"display version\n")
        output = tn.read_until(b">", timeout=5).decode('ascii')
        
        # 打印命令输出的前几行
        lines = output.splitlines()
        if lines:
            print("\n命令输出 (部分):")
            for i, line in enumerate(lines[:10]):
                print(f"  {line}")
            if len(lines) > 10:
                print(f"  ... (还有 {len(lines) - 10} 行)")
        
        # 关闭连接
        tn.close()
        print("\n[OK] 测试完成，Telnet连接正常！")
        return True
        
    except ImportError:
        print("[ERROR] 错误: 缺少telnetlib库")
        return False
    except Exception as e:
        print(f"[ERROR] 连接失败: {str(e)}")
        print("\n可能的解决方案:")
        print("1. 确保设备已启动并可访问")
        print("2. 验证IP地址、端口、用户名和密码是否正确")
        print("3. 确保设备已配置Telnet服务并启用")
        print("4. 检查网络连接和防火墙设置")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("eNSP设备连接测试工具")
    print("=" * 60)
    print("\n此工具用于测试与eNSP设备的连接")
    
    try:
        # 解析命令行参数
        import argparse
        parser = argparse.ArgumentParser(description="测试与eNSP设备的连接")
        parser.add_argument("--ip", default="", help="设备IP地址")
        parser.add_argument("--port", type=int, default=22, help="SSH端口号")
        parser.add_argument("--username", default="admin", help="登录用户名")
        parser.add_argument("--password", default="", help="登录密码")
        parser.add_argument("--telnet", action="store_true", help="使用Telnet代替SSH")
        
        args = parser.parse_args()
        
        # 如果未提供IP，提示用户输入
        ip = args.ip
        if not ip:
            ip = input("请输入设备IP地址: ")
        
        # 测试连接
        if args.telnet:
            success = test_telnet_connection(ip, args.port, args.username, args.password or None)
        else:
            success = test_ssh_connection(ip, args.port, args.username, args.password or None)
        
        if not success:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n操作已取消")
        sys.exit(130)
    except Exception as e:
        print(f"发生错误: {str(e)}")
        logger.exception("执行过程中发生错误")
        sys.exit(1)
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 