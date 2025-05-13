# eNSP-Automation

eNSP-Automation是一个用于自动化配置华为eNSP网络拓扑的Python工具。它允许用户通过自然语言描述或GUI界面快速创建和配置网络拓扑。

## 功能特点

- 自然语言处理：通过描述来创建网络拓扑
- 图形用户界面：直观的拖放式拓扑设计
- 多种NLP模式支持：
  - 本地规则解析（无需API）
  - OpenAI API（需要密钥）
  - DeepSeek API（需要密钥）
  - 讯飞星火（需要密钥）
- 设备自动配置：根据拓扑生成设备配置脚本
- eNSP集成：eNSP拓扑导入

## 系统要求

- Windows 10/11 (64位)
- Python 3.8+
- 华为eNSP软件 (V100R003C00 或更高版本)
- VirtualBox 6.1+ (eNSP依赖)

## 安装步骤

1. 克隆或下载本项目
2. 安装所需依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 确保已安装华为eNSP软件
4. 如果使用API功能，请在`configs/nlp_config.json`中配置相应的API密钥

## 使用方法

### GUI界面

运行以下命令启动图形界面：
```bash
python src/main.py
```

### 命令行使用

通过命令行处理网络描述：
```bash
python src/nlp_helper.py "设计一个简单的网络，包含一个路由器和两台交换机"
```

### 拓扑测试

测试eNSP连接：
```bash
python test_connection.py
```

## 项目架构

- `src/`：源代码目录
  - `main.py`：主程序入口
  - `gui.py`：图形用户界面
  - `nlp_helper.py`：自然语言处理模块
  - `topology_generator.py`：拓扑生成模块
  - `device_config.py`：设备配置生成模块
  - `ensp_integration.py`：eNSP拓扑导入模块
- `configs/`：配置文件目录
- `logs/`：日志文件目录
- `examples/`：示例拓扑和配置

## 常见问题

1. **API调用失败**：
   - 检查API密钥是否正确配置
   - 确认网络连接正常
   - 检查API服务是否可用

2. **拓扑生成问题**：
   - 尝试使用更具体的网络描述
   - 使用内置示例作为参考

## 许可证

MIT

## 维护者：覃家爵 17758548250

请联系项目维护者获取更多帮助和支持。 2025.5.4