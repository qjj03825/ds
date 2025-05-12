# eNSP 设备连接故障排除指南

## 常见连接问题

如果您在使用 eNSP 自动化工具连接设备时遇到问题，请按照以下步骤进行故障排除：

### 1. 确认设备可达

首先确保设备网络可达：

```
ping <设备IP地址>
```

如果无法 ping 通，请检查：
- 设备是否已启动
- 网络连接是否正常
- IP 地址是否正确
- 防火墙设置是否阻止了通信

### 2. 验证 SSH 服务

检查设备的 SSH 服务是否正常运行：

```
telnet <设备IP地址> 22
```

如果无法连接到端口 22，则可能是设备上的 SSH 服务未启用。

### 3. 检查认证信息

默认认证信息：
- 用户名: `admin`
- 密码: `huawei@123`

如果使用默认凭据无法登录，您可能需要在设备上配置或更新 SSH 凭据。

### 4. 配置设备 SSH 服务

如果设备是新设置的，您可能需要手动配置 SSH 服务：

1. 在 eNSP 中右击设备，选择"Console"进入命令行
2. 执行以下命令：

```
system-view
stelnet server enable
ssh user admin authentication-type password
ssh user admin service-type stelnet
aaa
local-user admin password cipher huawei@123
local-user admin service-type ssh
local-user admin privilege level 15
quit
user-interface vty 0 4
authentication-mode aaa
protocol inbound ssh
quit
save force
s5700设备ssh模板：
vlan 10
[sw1-vlan10]q
[sw1]int g0/0/1	
[sw1-GigabitEthernet0/0/1]port link-type access 
[sw1-GigabitEthernet0/0/1]port default vlan 10
[sw1-GigabitEthernet0/0/1]q
[sw1]int Vlanif 10
[sw1-Vlanif10]ip add 10.135.65.222 16
[sw1-Vlanif10]q
[sw1]aaa
[sw1-aaa]local-user admin password cipher huawei@123
[sw1-aaa]local-user admin privilege level 15
[sw1-aaa]local-user admin service-type ssh
[sw1-aaa]q
[sw1]user-interface vtY 0 4
[sw1-ui-vty0-4]authentication-mode aaa	
[sw1-ui-vty0-4]protocol inbound ssh
[sw1-ui-vty0-4]q
[sw1]stelnet server enable 
Info: Succeeded in starting the Stelnet server.	
[sw1]ssh user admin authentication-type all
Info: Succeeded in adding a new SSH user.
[sw1]ssh user admin service-type all	
[sw1]ssh client first-time enable 	
[sw1]sftp server enable 
Info: Succeeded in starting the SFTP server.
```

### 5. 检查日志文件

连接失败时，请查看这些日志文件以获取详细错误信息：
- `ensp_device_session.log`
- `ensp_automation_gui.log`
- `ensp_automation.log`

## 测试连接

如果仍然有问题，您可以使用以下脚本测试连接，以确定具体原因：

```python
# test_connect.py
import paramiko
import time

def test_connect(host, username, password, port=22):
    print(f"正在尝试连接到 {host}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(hostname=host, 
                   username=username, 
                   password=password, 
                   port=port,
                   timeout=10,
                   allow_agent=False,
                   look_for_keys=False)
        print("连接成功!")
        shell = ssh.invoke_shell()
        shell.send("display version\n")
        time.sleep(1)
        output = shell.recv(65535).decode()
        print(f"设备输出:\n{output}")
        ssh.close()
        return True
    except Exception as e:
        print(f"连接失败: {str(e)}")
        return False

# 使用您的设备IP地址，并尝试不同的认证信息
test_connect("10.135.65.222", "admin", "huawei@123")
```

## 常见错误信息和解决方案

| 错误信息 | 可能原因 | 解决方案 |
|---------|---------|---------|
| Authentication failed | 用户名或密码错误 | 检查凭据，尝试使用huawei@123作为默认密码 |
| Connection timed out | 设备不可达或端口未开放 | 检查网络连接和防火墙设置 |
| Connection refused | SSH服务未启用 | 在设备上配置SSH服务 |
| Host key verification failed | SSH主机密钥问题 | 在连接设置中添加AutoAddPolicy(已在代码中实现) |

如有其他问题，请参考华为eNSP文档或联系支持团队。 