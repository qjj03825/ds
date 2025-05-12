#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
eNSP端口配置测试脚本
用于测试端口配置功能是否正常工作
"""

import time
import sys
import socket
from src.device_config import DeviceConfigAutomation

def test_port_config():
    # 设置控制台编码为UTF-8
    if sys.platform == 'win32':
        import subprocess
        subprocess.run(['chcp', '65001'], shell=True, check=False)
    
    print("=" * 50)
    print("eNSP端口配置测试")
    print("=" * 50)
    
    # 创建自动化对象
    automation = DeviceConfigAutomation()
    
    # 连接设备
    device_ip = "10.135.65.222"
    username = "admin"
    password = "huawei@123"
    
    # 首先检查设备端口是否可达
    print(f"\n[1] 检查设备 {device_ip} 是否可达...")
    
    # 尝试多次检查连接
    max_retries = 3
    for retry in range(1, max_retries + 1):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)  # 5秒超时
            s.connect((device_ip, 22))
            s.close()
            print(f"设备 {device_ip} 可达")
            break
        except (socket.timeout, ConnectionRefusedError) as e:
            print(f"尝试 {retry}/{max_retries}: 设备 {device_ip} 不可达: {str(e)}")
            if retry < max_retries:
                print(f"等待5秒后重试...")
                time.sleep(5)
            else:
                print(f"设备 {device_ip} 不可达，测试终止")
                return False
    
    print(f"\n[2] 正在连接到设备 {device_ip}...")
    
    # 尝试多次连接
    connected = False
    for retry in range(1, max_retries + 1):
        try:
            if automation.connect_device(device_ip, username, password):
                connected = True
                break
            else:
                print(f"尝试 {retry}/{max_retries}: 连接失败")
        except Exception as e:
            print(f"尝试 {retry}/{max_retries}: 连接出错: {str(e)}")
        
        if retry < max_retries:
            print(f"等待5秒后重试...")
            time.sleep(5)
    
    if not connected:
        print(f"连接设备 {device_ip} 失败，测试终止")
        return False
    
    print(f"成功连接到设备 {device_ip}")
    
    # 配置端口
    port_name = "GigabitEthernet0/0/4"
    vlan_id = 40
    port_type = "access"
    
    print(f"\n[3] 正在配置端口 {port_name}, VLAN {vlan_id}, 类型 {port_type}...")
    
    try:
        result = automation.configure_port(device_ip, port_name, vlan_id, port_type)
        
        if result:
            print(f"端口 {port_name} 配置成功")
            
            # 检查配置是否生效
            print(f"\n[4] 验证端口配置...")
            
            # 为了确认配置是否真正生效，使用execute_command获取接口配置
            verification_output = automation.execute_command(
                device_ip, 
                f"display current-configuration interface {port_name}"
            )
            
            if verification_output:
                print(f"验证输出:\n{verification_output}")
                
                # 检查关键配置项
                expected_configs = [
                    f"interface {port_name}",
                    "port link-type access",
                    f"port default vlan {vlan_id}"
                ]
                
                all_found = True
                for cfg in expected_configs:
                    if cfg not in verification_output:
                        print(f"警告: 未找到预期配置: {cfg}")
                        all_found = False
                
                if all_found:
                    print("验证成功: 所有预期配置项均已应用")
                else:
                    print("验证部分成功: 某些配置项可能未正确应用")
            else:
                print("无法获取验证输出")
        else:
            print(f"端口 {port_name} 配置失败")
    except Exception as e:
        print(f"配置端口时出错: {str(e)}")
    
    # 断开连接前暂停几秒，确保命令完成
    time.sleep(2)
    
    # 断开连接
    print(f"\n[5] 正在断开与设备 {device_ip} 的连接...")
    try:
        automation.disconnect_device(device_ip)
        print("连接已断开")
    except Exception as e:
        print(f"断开连接时出错: {str(e)}")
    
    print("\n测试完成")
    return True

if __name__ == "__main__":
    test_port_config() 