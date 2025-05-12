#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
from typing import Optional, Dict, Any, List
import logging
import time
import json
from pathlib import Path
from xml.dom import minidom
import xml.etree.ElementTree as ET

# 设置控制台编码，解决中文乱码问题
if sys.platform == 'win32':
    try:
        import subprocess
        # 设置控制台编码为UTF-8
        subprocess.run(['chcp', '65001'], shell=True, check=False)
        # 确保Python解释器使用UTF-8编码
        if hasattr(sys, 'setdefaultencoding'):
            sys.setdefaultencoding('utf-8')
        # 设置标准输出和标准错误的编码
        sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
        sys.stderr.reconfigure(encoding='utf-8') if hasattr(sys.stderr, 'reconfigure') else None
    except Exception as e:
        print(f"设置编码时出错: {e}")

# 添加src目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from topology_generator import TopologyGenerator
from device_config import DeviceConfigAutomation
from nlp_helper import NLPTopologyGenerator  # 导入NLP模块

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ensp_automation_gui.log')
    ]
)
logger = logging.getLogger(__name__)

class StdoutRedirector:
    """重定向标准输出到Tkinter文本控件"""
    
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""
        
    def write(self, string):
        self.buffer += string
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        
    def flush(self):
        self.text_widget.update_idletasks()

class ENSPAutomationGUI:
    """eNSP自动化工具图形用户界面"""
    
    def __init__(self, master=None):
        """初始化GUI窗口"""
        self.root = master or tk.Tk()
        self.root.title("eNSP自动化工具")
        # 设置更大的窗口尺寸，并允许调整大小
        self.root.geometry("1100x800")  # 进一步增加高度到800px
        self.root.minsize(1100, 750)  # 设置更大的最小窗口大小
        self.root.resizable(True, True)  # 允许调整窗口大小
        
        # 设置窗口在屏幕中央
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # 初始化状态
        self.topology_data = {
            "devices": [],
            "connections": []
        }
        self.ssh_client = None
        self.connected = False
        
        # 创建笔记本控件
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 初始化成员变量
        self.generator = TopologyGenerator()
        self.device_config = DeviceConfigAutomation()
        self.nlp_generator = NLPTopologyGenerator()  # 初始化NLP生成器
        self.working_thread = None
        self.current_topology = None
        self.current_topo_file = None
        self.connected_devices = []  # 改为列表，与后续的append/remove操作匹配
        
        # 设置样式
        self.style = ttk.Style()
        self.style.configure("TLabel", font=("微软雅黑", 10))
        self.style.configure("TButton", font=("微软雅黑", 10))
        self.style.configure("TFrame", background="#f0f0f0")
        
        # 创建启动窗口
        self.show_splash_screen()
        
        # 创建主框架
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 故障排除指南按钮放在顶部，始终可见
        help_frame = ttk.Frame(self.main_frame)
        help_frame.pack(fill=tk.X, pady=(0, 10))
        
        help_button = tk.Button(
            help_frame, 
            text="故障排除指南", 
            command=self.show_troubleshooting,
            width=20,
            bg="#e74c3c",   # 红色背景
            fg="white",     # 白色文字
            font=("微软雅黑", 10, "bold")
        )
        help_button.pack(side=tk.RIGHT, padx=5)
        

        # 拓扑和配置页面
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 创建网络拓扑页面
        self.topology_tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.topology_tab, text="网络拓扑生成")
        
        # 项目名称
        ttk.Label(self.topology_tab, text="项目名称:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.project_name_var = tk.StringVar()
        self.project_name_var.set("MyNetwork")
        self.project_name_entry = ttk.Entry(self.topology_tab, textvariable=self.project_name_var, width=20)
        self.project_name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 示例选择
        ttk.Label(self.topology_tab, text="示例:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        
        self.examples = ["", "简单网络", "VLAN划分", "路由配置"]
        self.example_var = tk.StringVar()
        self.example_combo = ttk.Combobox(self.topology_tab, textvariable=self.example_var, values=self.examples, width=15)
        self.example_combo.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        self.example_combo.bind("<<ComboboxSelected>>", self.load_example)
        
        # 设备列表和相关按钮
        self.devices_frame = ttk.LabelFrame(self.topology_tab, text="设备", padding=5)
        self.devices_frame.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        self.topology_tab.grid_rowconfigure(1, weight=1)
        self.topology_tab.grid_columnconfigure(0, weight=1)
        
        # 设备列表
        self.devices_listbox = tk.Listbox(self.devices_frame, width=40, height=10)
        self.devices_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 设备列表滚动条
        devices_scrollbar = ttk.Scrollbar(self.devices_frame, orient=tk.VERTICAL, command=self.devices_listbox.yview)
        devices_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.devices_listbox.config(yscrollcommand=devices_scrollbar.set)
        
        # 设备按钮
        devices_button_frame = ttk.Frame(self.devices_frame)
        devices_button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        # 调整设备按钮布局为垂直排列
        device_btns_left = ttk.Frame(devices_button_frame)
        device_btns_left.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(device_btns_left, text="添加设备", command=self.add_device, width=10).pack(pady=2)
        ttk.Button(device_btns_left, text="删除设备", command=self.delete_device, width=10).pack(pady=2)
        ttk.Button(device_btns_left, text="编辑设备", command=self.edit_device, width=10).pack(pady=2)
        
        # 连接列表和相关按钮
        self.connections_frame = ttk.LabelFrame(self.topology_tab, text="连接", padding=5)
        self.connections_frame.grid(row=1, column=2, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)
        self.topology_tab.grid_columnconfigure(2, weight=1)
        
        # 连接列表
        self.connections_listbox = tk.Listbox(self.connections_frame, width=40, height=10)
        self.connections_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 连接列表滚动条
        connections_scrollbar = ttk.Scrollbar(self.connections_frame, orient=tk.VERTICAL, command=self.connections_listbox.yview)
        connections_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.connections_listbox.config(yscrollcommand=connections_scrollbar.set)
        
        # 连接按钮
        connections_button_frame = ttk.Frame(self.connections_frame)
        connections_button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        # 调整连接按钮布局为垂直排列
        conn_btns_left = ttk.Frame(connections_button_frame)
        conn_btns_left.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(conn_btns_left, text="添加连接", command=self.add_connection, width=10).pack(pady=2)
        ttk.Button(conn_btns_left, text="删除连接", command=self.delete_connection, width=10).pack(pady=2)
        ttk.Button(conn_btns_left, text="编辑连接", command=self.edit_connection, width=10).pack(pady=2)
        
        # 拓扑操作按钮
        topology_actions_frame = ttk.Frame(self.topology_tab)
        topology_actions_frame.grid(row=2, column=0, columnspan=4, sticky=tk.E, padx=5, pady=5)
        
        
        # 原有的底部按钮
        ttk.Button(topology_actions_frame, text="生成拓扑", command=self.generate_topology).pack(side=tk.LEFT, padx=5)
        ttk.Button(topology_actions_frame, text="保存拓扑", command=self.save_topology).pack(side=tk.LEFT, padx=5)
        ttk.Button(topology_actions_frame, text="加载拓扑", command=self.load_topology).pack(side=tk.LEFT, padx=5)
        
        # 创建NLP拓扑描述页面
        self.nlp_tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.nlp_tab, text="自然语言描述")
        
        # 自然语言描述部分
        # NLP项目名称
        ttk.Label(self.nlp_tab, text="项目名称:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        self.nlp_project_name_var = tk.StringVar()
        self.nlp_project_name_var.set("NLPNetwork")
        self.nlp_project_name_entry = ttk.Entry(self.nlp_tab, textvariable=self.nlp_project_name_var, width=20)
        self.nlp_project_name_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 选择模型
        ttk.Label(self.nlp_tab, text="模型:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        
        self.model_types = ["本地规则解析", "OpenAI", "DeepSeek", "讯飞星火"]
        self.model_type_var = tk.StringVar(value="本地规则解析")
        self.model_type_combo = ttk.Combobox(self.nlp_tab, textvariable=self.model_type_var, values=self.model_types, width=15)
        self.model_type_combo.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        self.model_type_combo.bind("<<ComboboxSelected>>", self.model_type_selected)
        
        # API设置按钮
        ttk.Button(self.nlp_tab, text="设置API", command=self.setup_api).grid(row=0, column=4, padx=5, pady=5)
        
        # 网络描述框架
        self.description_frame = ttk.LabelFrame(self.nlp_tab, text="网络描述", padding=5)
        self.description_frame.grid(row=1, column=0, columnspan=5, sticky=tk.NSEW, padx=5, pady=5)
        self.nlp_tab.grid_rowconfigure(1, weight=1)
        self.nlp_tab.grid_columnconfigure(0, weight=1)
        
        # 描述文本
        self.description_text = scrolledtext.ScrolledText(self.description_frame, wrap=tk.WORD, width=80, height=15)
        self.description_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 描述操作框架
        description_actions_frame = ttk.Frame(self.description_frame)
        description_actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 示例描述按钮
        ttk.Button(description_actions_frame, text="加载示例描述", command=self.load_example_description).pack(side=tk.LEFT, padx=5)
        
        # 添加说明标签
        ttk.Label(description_actions_frame, text="← 先描述您的网络，然后点击 →", foreground="gray").pack(side=tk.LEFT, padx=10)
        
        # 网络描述解析按钮 - 新添加
        self.parse_button = ttk.Button(
            description_actions_frame, 
            text="网络描述解析", 
            command=self.parse_network_description,
            style="Accent.TButton"  # 使用特殊样式让按钮更显眼
        )
        self.parse_button.pack(side=tk.RIGHT, padx=5)
        
        # 设置按钮样式
        self.style.configure("Accent.TButton", font=("微软雅黑", 10, "bold"))
        
        # 生成拓扑按钮 - 移到最右边
        ttk.Button(description_actions_frame, text="生成拓扑", command=self.generate_nlp_topology).pack(side=tk.RIGHT, padx=5)
        
        # 解析结果预览框架
        self.parsed_result_frame = ttk.LabelFrame(self.nlp_tab, text="解析结果预览", padding=5)
        self.parsed_result_frame.grid(row=2, column=0, columnspan=5, sticky=tk.NSEW, padx=5, pady=5)
        self.nlp_tab.grid_rowconfigure(2, weight=1)
        
        # 解析结果文本
        self.parsed_result_text = scrolledtext.ScrolledText(self.parsed_result_frame, wrap=tk.WORD, width=80, height=8)
        self.parsed_result_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.parsed_result_text.config(state=tk.DISABLED)  # 初始设为只读
        
        # 设备配置页面
        self.config_tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.config_tab, text="设备配置")
        
        # SSH连接配置框架
        self.ssh_frame = ttk.LabelFrame(self.config_tab, text="SSH连接", padding=5)
        self.ssh_frame.grid(row=0, column=0, columnspan=4, sticky=tk.NSEW, padx=5, pady=5)
        self.config_tab.grid_rowconfigure(0, weight=0)
        self.config_tab.grid_columnconfigure(0, weight=1)
        
        # SSH连接参数
        ttk.Label(self.ssh_frame, text="设备IP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.device_ip_var = tk.StringVar()
        self.device_ip_entry = ttk.Entry(self.ssh_frame, textvariable=self.device_ip_var, width=15)
        self.device_ip_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(self.ssh_frame, text="端口:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.port_var = tk.StringVar(value="22")
        self.port_entry = ttk.Entry(self.ssh_frame, textvariable=self.port_var, width=5)
        self.port_entry.grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(self.ssh_frame, text="设备类型:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.device_type_var = tk.StringVar(value="huawei")
        device_types = ["huawei", "huawei_telnet"]
        self.device_type_combo = ttk.Combobox(self.ssh_frame, textvariable=self.device_type_var, values=device_types, width=12)
        self.device_type_combo.grid(row=0, column=5, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(self.ssh_frame, text="用户名:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.username_var = tk.StringVar(value="admin")
        self.username_entry = ttk.Entry(self.ssh_frame, textvariable=self.username_var, width=15)
        self.username_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(self.ssh_frame, text="密码:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.password_var = tk.StringVar(value="huawei@123")
        self.password_entry = ttk.Entry(self.ssh_frame, textvariable=self.password_var, width=15, show="*")
        self.password_entry.grid(row=1, column=3, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # 连接状态标签
        self.conn_status_var = tk.StringVar(value="未连接")
        self.conn_status_label = ttk.Label(self.ssh_frame, textvariable=self.conn_status_var, foreground="red")
        self.conn_status_label.grid(row=1, column=5, sticky=tk.W, padx=5, pady=5)
        
        # 连接按钮
        self.connect_button = ttk.Button(self.ssh_frame, text="连接", command=self.connect_device)
        self.connect_button.grid(row=0, column=6, padx=5, pady=5)
        
        # 断开按钮
        self.disconnect_button = ttk.Button(self.ssh_frame, text="断开", command=self.disconnect_device)
        self.disconnect_button.grid(row=1, column=6, padx=5, pady=5)
        
        # SSH帮助按钮
        ttk.Button(self.ssh_frame, text="SSH配置帮助", command=self.show_ssh_guide).grid(row=0, column=7, rowspan=2, padx=5, pady=5)
        
        # 设备操作框架
        self.connected_devices_frame = ttk.LabelFrame(self.config_tab, text="已连接设备", padding=5)
        self.connected_devices_frame.grid(row=1, column=0, columnspan=1, sticky=tk.NSEW, padx=5, pady=5)
        self.config_tab.grid_rowconfigure(1, weight=1)
        self.config_tab.grid_columnconfigure(0, weight=1)  # 缩小已连接设备列的宽度
        
        # 已连接设备列表
        self.connected_devices_listbox = tk.Listbox(self.connected_devices_frame, width=15, height=5)
        self.connected_devices_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 已连接设备列表滚动条
        connected_devices_scrollbar = ttk.Scrollbar(self.connected_devices_frame, orient=tk.VERTICAL, command=self.connected_devices_listbox.yview)
        connected_devices_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.connected_devices_listbox.config(yscrollcommand=connected_devices_scrollbar.set)
        
        # 配置命令框架
        self.commands_frame = ttk.LabelFrame(self.config_tab, text="配置命令", padding=5)
        self.commands_frame.grid(row=1, column=1, columnspan=3, sticky=tk.NSEW, padx=5, pady=5)
        self.config_tab.grid_columnconfigure(1, weight=3)  # 增大配置命令区域的宽度
        
        # 命令文本区域
        self.commands_text = scrolledtext.ScrolledText(self.commands_frame, width=50, height=8, wrap=tk.WORD)
        self.commands_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 添加命令列表
        self.command_list_frame = ttk.LabelFrame(self.config_tab, text="命令列表", padding=5)
        self.command_list_frame.grid(row=2, column=0, columnspan=4, sticky=tk.NSEW, padx=5, pady=5)
        self.config_tab.grid_rowconfigure(2, weight=2)  # 增大命令列表的高度比例
        
        # 命令列表
        self.command_listbox = tk.Listbox(self.command_list_frame, width=60, height=12)
        self.command_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 命令列表滚动条
        command_scrollbar = ttk.Scrollbar(self.command_list_frame, orient=tk.VERTICAL, command=self.command_listbox.yview)
        command_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.command_listbox.config(yscrollcommand=command_scrollbar.set)
        
        # 命令列表操作按钮框架
        cmd_list_buttons_frame = ttk.Frame(self.command_list_frame)
        cmd_list_buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        # 创建两行按钮以更好地布局
        cmd_buttons_row1 = ttk.Frame(cmd_list_buttons_frame)
        cmd_buttons_row1.pack(side=tk.TOP, fill=tk.X, pady=2)
        
        cmd_buttons_row2 = ttk.Frame(cmd_list_buttons_frame)
        cmd_buttons_row2.pack(side=tk.TOP, fill=tk.X, pady=2)
        
        ttk.Button(cmd_buttons_row1, text="添加命令", command=self.add_command).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_buttons_row1, text="删除命令", command=self.delete_command).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_buttons_row1, text="执行命令", command=self.execute_commands).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_buttons_row1, text="清空列表", command=self.clear_command_list).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(cmd_buttons_row2, text="模板组", command=self.add_command_templates).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_buttons_row2, text="命令库", command=self.open_command_library).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_buttons_row2, text="配置端口", command=self.configure_port).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_buttons_row2, text="保存模板", command=self.save_command_template).pack(side=tk.LEFT, padx=5)
        
        # 命令按钮框架
        cmd_buttons_frame = ttk.Frame(self.commands_frame)
        cmd_buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        ttk.Button(cmd_buttons_frame, text="发送命令", command=self.send_commands).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_buttons_frame, text="保存配置", command=self.save_device_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(cmd_buttons_frame, text="命令模板", command=self.load_command_template).pack(side=tk.LEFT, padx=5)
        
        # 日志框架
        self.log_frame = ttk.LabelFrame(self.config_tab, text="日志", padding=5)
        self.log_frame.grid(row=3, column=0, columnspan=4, sticky=tk.NSEW, padx=5, pady=5)
        self.config_tab.grid_rowconfigure(3, weight=1)
        
        # 日志文本区域
        self.log_text = scrolledtext.ScrolledText(self.log_frame, width=50, height=6, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 重定向标准输出到日志文本区域
        sys.stdout = StdoutRedirector(self.log_text)
        
        # 导入拓扑页面
        self.import_tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(self.import_tab, text="eNSP导入")
        
        ttk.Label(self.import_tab, text="导入拓扑:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.import_topo_path_var = tk.StringVar()
        self.import_topo_path_entry = ttk.Entry(self.import_tab, textvariable=self.import_topo_path_var, width=50)
        self.import_topo_path_entry.grid(row=0, column=1, columnspan=2, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Button(self.import_tab, text="浏览...", command=self.browse_topo_file).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(self.import_tab, text="导入到eNSP", command=self.import_to_ensp).grid(row=0, column=4, padx=5, pady=5)
        
        # 添加SSH配置引导 - 由于删除了设备控制行，调整SSH配置引导的位置到row=1
        ttk.Label(self.import_tab, text="SSH配置引导:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Button(self.import_tab, text="显示SSH配置说明", command=self.show_ssh_guide).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 自动检测eNSP路径
        # self.detect_ensp_path()
        
        # 输出欢迎信息
        self.log("eNSP自动化工具已启动。\n请创建网络拓扑或加载现有拓扑文件。")
        self.log("NLP功能已启用，您可以使用自然语言描述来生成网络拓扑。")
    
    def show_splash_screen(self):
        """显示启动窗口，提供连接信息和使用提示"""
        splash = tk.Toplevel(self.root)
        splash.title("eNSP自动化工具 - 欢迎")
        splash.geometry("600x400")  # 减小初始高度
        splash.resizable(True, True)
        splash.transient(self.root)
        splash.grab_set()
        
        # 设置窗口在屏幕中央
        splash.update_idletasks()
        width = splash.winfo_width()
        height = splash.winfo_height()
        x = (splash.winfo_screenwidth() // 2) - (width // 2)
        y = (splash.winfo_screenheight() // 2) - (height // 2)
        splash.geometry('{}x{}+{}+{}'.format(width, height, x, y))
        
        # 创建可滚动的框架
        outer_frame = ttk.Frame(splash)
        outer_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建Canvas和Scrollbar
        canvas = tk.Canvas(outer_frame)
        scrollbar = ttk.Scrollbar(outer_frame, orient=tk.VERTICAL, command=canvas.yview)
        
        # 将Canvas和Scrollbar放置
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 配置Canvas
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        # 创建内部框架
        inner_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        
        # 标题
        title_frame = ttk.Frame(inner_frame)
        title_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(
            title_frame, 
            text="欢迎使用 eNSP自动化工具", 
            font=("微软雅黑", 16, "bold")
        ).pack()
        
        ttk.Label(
            title_frame, 
            text="用于自动化配置华为设备的图形界面工具",
            font=("微软雅黑", 10)
        ).pack(pady=5)
        
        # 内容区域
        content_frame = ttk.Frame(inner_frame)
        content_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 连接信息部分
        ttk.Label(
            content_frame, 
            text="SSH连接提示:", 
            font=("微软雅黑", 12, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))
        
        connection_text = """1. 默认连接参数: 
   - 用户名: admin
   - 密码: huawei@123
   - 端口: 22
   
2. 确保华为设备已正确配置SSH服务
   - 使用'自动连接'功能可自动配置SSH

3. 如果遇到连接问题:
   - 点击"故障排除指南"获取帮助
   - 使用测试工具 test_connection.py 检测连接"""
        
        ttk.Label(
            content_frame, 
            text=connection_text,
            justify=tk.LEFT,
            wraplength=560
        ).pack(anchor=tk.W, pady=5)
        
        # 使用提示部分
        ttk.Label(
            content_frame, 
            text="使用提示:", 
            font=("微软雅黑", 12, "bold")
        ).pack(anchor=tk.W, pady=(10, 5))
        
        tips_text = """1. 网络拓扑生成:
   - 添加设备和连接，生成拓扑文件导入eNSP

2. 设备配置:
   - 连接到设备后，可以使用命令列表进行批量配置
   - 常用配置操作已封装为预置功能，如端口配置

3. 配置验证:
   - 系统会自动验证配置结果
   - 验证结果会直观展示在界面上

4. 故障排除:
   - 如果命令执行失败，系统会自动尝试重新连接
   - 日志文件包含详细的操作记录"""
        
        ttk.Label(
            content_frame, 
            text=tips_text,
            justify=tk.LEFT,
            wraplength=560
        ).pack(anchor=tk.W, pady=5)
        
        # 按钮区域
        button_frame = ttk.Frame(inner_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 绑定鼠标滚轮事件
        def _on_mousewheel(event):
            try:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except (tk.TclError, Exception) as e:
                # Canvas可能已经被销毁，静默处理错误
                canvas.unbind_all("<MouseWheel>")
                pass
        
        # 将滚轮事件绑定到标识符以便后续解绑
        canvas.bind_all("<MouseWheel>", _on_mousewheel, add="+")
        
        # 设置窗口关闭时的清理函数
        def _on_close():
            # 在窗口关闭前解绑鼠标滚轮事件
            canvas.unbind_all("<MouseWheel>")
            splash.destroy()
        
        ttk.Button(
            button_frame, 
            text="开始使用", 
            command=_on_close,
            width=20
        ).pack(side=tk.RIGHT)
        
        # 设置滚动区域的大小
        inner_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 显示7秒后自动关闭（调用_on_close而不是直接destroy）
        splash.after(7000, _on_close)
    
    def log(self, message):
        """输出日志信息，优化显示格式"""
        timestamp = time.strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}"
        
        # 根据消息类型添加颜色标记
        tag = None
        if "错误" in message or "失败" in message:
            tag = "error"
        elif "成功" in message or "已完成" in message:
            tag = "success"
        elif "警告" in message:
            tag = "warning"
        elif "配置" in message:
            tag = "config"
        
        # 添加到日志窗口
        self.log_text.insert(tk.END, formatted_message + "\n")
        
        # 应用标签样式
        if tag:
            line_count = int(self.log_text.index(tk.END).split('.')[0]) - 1
            line_start = f"{line_count}.0"
            line_end = f"{line_count}.end"
            self.log_text.tag_add(tag, line_start, line_end)
        
        # 确保滚动到最新日志
        self.log_text.see(tk.END)
        self.log_text.update_idletasks()  # 强制更新UI
        
        # 配置标签颜色
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("config", foreground="blue")
    
    def browse_ensp_path(self):
        """浏览并选择eNSP安装路径"""
        path = filedialog.askdirectory(title="选择eNSP安装目录")
        if path:
            self.ensp_path_var.set(path)
            self.log(f"eNSP路径已设置为: {path}")
    
    def detect_ensp_path(self):
        """自动检测eNSP安装路径"""
        # 常见的eNSP安装路径
        common_paths = [
            "C:\\Program Files\\eNSP",
            "C:\\Program Files (x86)\\eNSP",
            "D:\\Program Files\\eNSP",
            "D:\\Program Files (x86)\\eNSP",
            os.path.expanduser("~\\eNSP")
        ]
        
        for path in common_paths:
            if os.path.exists(path) and os.path.isfile(os.path.join(path, "eNSP.exe")):
                self.ensp_path_var.set(path)
                self.log(f"已自动检测到eNSP路径: {path}")
                return
        
        self.log("未能自动检测到eNSP路径，请手动指定")
    
    def load_example(self, event):
        """加载示例拓扑"""
        example = self.example_var.get()
        
        if example == "简单网络":
            self.topology_data = {
                "devices": [
                    {
                        "name": "Core-SW",
                        "type": "S5700",
                        "management_ip": "192.168.1.1",
                        "subnet_mask": "255.255.255.0"
                    },
                    {
                        "name": "Router",
                        "type": "AR2220",
                        "management_ip": "192.168.1.2",
                        "subnet_mask": "255.255.255.0"
                    }
                ],
                "connections": [
                    {
                        "from": "Core-SW:GigabitEthernet0/0/1",
                        "to": "Router:GigabitEthernet0/0/0",
                        "bandwidth": "1G"
                    }
                ]
            }
        elif example == "VLAN划分":
            self.topology_data = {
                "devices": [
                    {
                        "name": "Core-SW",
                        "type": "S5700",
                        "management_ip": "192.168.1.1",
                        "subnet_mask": "255.255.255.0",
                        "vlans": ["10", "20", "30"]
                    },
                    {
                        "name": "Access-SW1",
                        "type": "S5700",
                        "management_ip": "192.168.1.2",
                        "subnet_mask": "255.255.255.0"
                    },
                    {
                        "name": "Access-SW2",
                        "type": "S5700",
                        "management_ip": "192.168.1.3",
                        "subnet_mask": "255.255.255.0"
                    }
                ],
                "connections": [
                    {
                        "from": "Core-SW:GigabitEthernet0/0/1",
                        "to": "Access-SW1:GigabitEthernet0/0/1",
                        "bandwidth": "1G"
                    },
                    {
                        "from": "Core-SW:GigabitEthernet0/0/2",
                        "to": "Access-SW2:GigabitEthernet0/0/1",
                        "bandwidth": "1G"
                    }
                ]
            }
        elif example == "路由配置":
            self.topology_data = {
                "devices": [
                    {
                        "name": "Router1",
                        "type": "AR2220",
                        "management_ip": "192.168.1.1",
                        "subnet_mask": "255.255.255.0"
                    },
                    {
                        "name": "Router2",
                        "type": "AR2220",
                        "management_ip": "192.168.2.1",
                        "subnet_mask": "255.255.255.0"
                    },
                    {
                        "name": "SW1",
                        "type": "S5700",
                        "management_ip": "192.168.1.2",
                        "subnet_mask": "255.255.255.0"
                    },
                    {
                        "name": "SW2",
                        "type": "S5700",
                        "management_ip": "192.168.2.2",
                        "subnet_mask": "255.255.255.0"
                    }
                ],
                "connections": [
                    {
                        "from": "Router1:GigabitEthernet0/0/0",
                        "to": "Router2:GigabitEthernet0/0/0",
                        "bandwidth": "1G"
                    },
                    {
                        "from": "Router1:GigabitEthernet0/0/1",
                        "to": "SW1:GigabitEthernet0/0/1",
                        "bandwidth": "1G"
                    },
                    {
                        "from": "Router2:GigabitEthernet0/0/1",
                        "to": "SW2:GigabitEthernet0/0/1",
                        "bandwidth": "1G"
                    }
                ]
            }
        else:
            # 清空数据
            self.topology_data = {
                "devices": [],
                "connections": []
            }
        
        # 更新列表框
        self.update_devices_listbox()
        self.update_connections_listbox()
        
        self.log(f"已加载示例: {example}")
    
    def update_devices_listbox(self):
        """更新设备列表框"""
        self.devices_listbox.delete(0, tk.END)
        for device in self.topology_data["devices"]:
            self.devices_listbox.insert(tk.END, f"{device['name']} ({device['type']})")
    
    def update_connections_listbox(self):
        """更新连接列表框"""
        self.connections_listbox.delete(0, tk.END)
        for connection in self.topology_data["connections"]:
            self.connections_listbox.insert(tk.END, f"{connection['from']} → {connection['to']}")
    
    def browse_topo_file(self):
        """浏览并选择拓扑文件"""
        path = filedialog.askopenfilename(
            title="选择拓扑文件",
            filetypes=[("拓扑文件", "*.topo"), ("所有文件", "*.*")]
        )
        if path:
            self.import_topo_path_var.set(path)
            self.current_topo_file = path
            self.log(f"已选择拓扑文件: {path}")
    
    def show_ssh_guide(self):
        """显示SSH配置引导"""
        guide = """
SSH配置引导

首次启动设备后，需要手动配置SSH服务以便Python脚本能够连接：

1. 在eNSP中右键点击设备，选择"Console"进入命令行
2. 执行以下命令配置SSH（以S5700为例）：

system-view
sysname Device_Name
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

3. 在本工具的"设备配置"标签页中，输入设备IP、用户名（admin）和密码（huawei@123），点击"连接"
4. 连接成功后即可发送配置命令
"""
        # 创建对话框显示SSH引导
        dialog = tk.Toplevel(self.root)
        dialog.title("SSH配置引导")
        dialog.geometry("600x400")
        dialog.resizable(True, True)
        
        text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert(tk.END, guide)
        text.config(state=tk.DISABLED)
        
        ttk.Button(dialog, text="关闭", command=dialog.destroy).pack(pady=10)

    def add_device(self):
        """添加设备"""
        # 创建设备对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("添加设备")
        dialog.geometry("400x350")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 设备属性
        ttk.Label(dialog, text="设备名称:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(dialog, text="设备类型:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        type_var = tk.StringVar(value="S5700")
        
        # 扩展设备类型列表
        device_categories = {
            "路由器": ["AR2220", "AR3260"],
            "交换机": ["S5700", "S5730", "CE6850", "S3700", "CE6800", "CE12800"], 
            "无线局域网": ["AC6005-8", "AC6605-26", "AD9430-28"],
            "防火墙": ["USG6000"],
            "PC": ["PC", "MCS", "Client", "Server", "STA", "Cellphone"],
            "云设备": ["Cloud", "FRSW", "HUB"]
        }
        
        # 创建复合下拉框
        device_type_frame = ttk.Frame(dialog)
        device_type_frame.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 设备类别下拉框
        category_var = tk.StringVar(value="交换机")
        categories = list(device_categories.keys())
        category_combo = ttk.Combobox(device_type_frame, textvariable=category_var, values=categories, width=10)
        category_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # 设备型号下拉框
        device_models = device_categories["交换机"]  # 默认显示交换机
        device_model_combo = ttk.Combobox(device_type_frame, textvariable=type_var, values=device_models, width=12)
        device_model_combo.pack(side=tk.LEFT)
        
        # 当类别改变时更新型号下拉框
        def update_models(*args):
            selected_category = category_var.get()
            device_model_combo['values'] = device_categories.get(selected_category, [])
            if device_categories.get(selected_category):
                type_var.set(device_categories[selected_category][0])
        
        category_var.trace('w', update_models)
        
        # 设备版本
        ttk.Label(dialog, text="设备版本:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        version_var = tk.StringVar(value="V200R019C00")
        ttk.Entry(dialog, textvariable=version_var, width=25).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 其他参数框架
        params_frame = ttk.LabelFrame(dialog, text="其他参数", padding=5)
        params_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W+tk.E, padx=10, pady=5)
        
        # 添加参数按钮
        params_list = []
        
        def add_param():
            row = len(params_list) + 1
            if row <= 5:  # 限制最多5个额外参数
                param_name_var = tk.StringVar()
                param_value_var = tk.StringVar()
                
                ttk.Label(params_frame, text="参数名:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
                ttk.Entry(params_frame, textvariable=param_name_var, width=10).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
                ttk.Label(params_frame, text="值:").grid(row=row, column=2, sticky=tk.W, padx=5, pady=2)
                ttk.Entry(params_frame, textvariable=param_value_var, width=10).grid(row=row, column=3, sticky=tk.W, padx=5, pady=2)
                
                params_list.append((param_name_var, param_value_var))
        
        ttk.Button(params_frame, text="添加参数", command=add_param).grid(row=0, column=0, columnspan=4, padx=5, pady=5)
        
        # 确定/取消按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        def on_ok():
            # 验证必填字段
            name = name_var.get().strip()
            device_type = type_var.get().strip()
            
            if not name or not device_type:
                messagebox.showwarning("警告", "设备名称和类型为必填项", parent=dialog)
                return
            
            # 创建设备对象
            device = {
                "name": name,
                "type": device_type,
                "version": version_var.get().strip()
            }
            
            # 添加其他参数
            for param_name_var, param_value_var in params_list:
                param_name = param_name_var.get().strip()
                param_value = param_value_var.get().strip()
                if param_name and param_value:
                    device[param_name] = param_value
            
            # 添加到拓扑数据中
            self.topology_data["devices"].append(device)
            
            # 更新设备列表
            self.update_devices_listbox()
            
            self.log(f"已添加设备: {name} ({device_type})")
            dialog.destroy()
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def edit_device(self):
        """编辑设备"""
        # 获取选中的设备索引
        selection = self.devices_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要编辑的设备")
            return
        
        # 获取设备数据
        device_index = selection[0]
        device = self.topology_data["devices"][device_index]
        
        # 创建编辑对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"编辑设备 - {device['name']}")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 设备属性
        ttk.Label(dialog, text="设备名称:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        name_var = tk.StringVar(value=device["name"])
        ttk.Entry(dialog, textvariable=name_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(dialog, text="设备类型:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        type_var = tk.StringVar(value=device["type"])
        
        # 扩展设备类型列表
        device_categories = {
            "路由器": ["AR2220", "AR3260"],
            "交换机": ["S5700", "S5730", "CE6850", "S3700", "CE6800", "CE12800"], 
            "无线局域网": ["AC6005-8", "AC6605-26", "AD9430-28"],
            "防火墙": ["USG6000"],
            "PC": ["PC", "MCS", "Client", "Server", "STA", "Cellphone"],
            "云设备": ["Cloud", "FRSW", "HUB"]
        }
        
        # 查找当前设备类型所在类别
        current_category = "交换机"  # 默认类别
        for category, models in device_categories.items():
            if device["type"] in models:
                current_category = category
                break
        
        # 创建复合下拉框
        device_type_frame = ttk.Frame(dialog)
        device_type_frame.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 设备类别下拉框
        category_var = tk.StringVar(value=current_category)
        categories = list(device_categories.keys())
        category_combo = ttk.Combobox(device_type_frame, textvariable=category_var, values=categories, width=10)
        category_combo.pack(side=tk.LEFT, padx=(0, 5))
        
        # 设备型号下拉框
        device_models = device_categories[current_category]
        device_model_combo = ttk.Combobox(device_type_frame, textvariable=type_var, values=device_models, width=12)
        device_model_combo.pack(side=tk.LEFT)
        
        # 当类别改变时更新型号下拉框
        def update_models(*args):
            selected_category = category_var.get()
            device_model_combo['values'] = device_categories.get(selected_category, [])
            if device_categories.get(selected_category) and type_var.get() not in device_categories.get(selected_category):
                type_var.set(device_categories[selected_category][0])
        
        category_var.trace('w', update_models)
        
        # 设备版本
        ttk.Label(dialog, text="设备版本:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        version_var = tk.StringVar(value=device.get("version", "V200R019C00"))
        ttk.Entry(dialog, textvariable=version_var, width=25).grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 确定/取消按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        def on_ok():
            # 验证必填字段
            name = name_var.get().strip()
            device_type = type_var.get().strip()
            
            if not name or not device_type:
                messagebox.showwarning("警告", "设备名称和类型为必填项", parent=dialog)
                return
            
            # 更新设备对象
            device["name"] = name
            device["type"] = device_type
            device["version"] = version_var.get().strip()
            
            # 清除旧的管理IP、子网掩码和VLAN信息
            if "management_ip" in device:
                del device["management_ip"]
            if "subnet_mask" in device:
                del device["subnet_mask"]
            if "vlans" in device:
                del device["vlans"]
            
            # 更新设备列表
            self.update_devices_listbox()
            
            self.log(f"已更新设备: {name} ({device_type})")
            dialog.destroy()
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def delete_device(self):
        """删除设备"""
        # 获取选中的设备索引
        selection = self.devices_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要删除的设备")
            return
        
        # 获取设备数据
        device_index = selection[0]
        device = self.topology_data["devices"][device_index]
        
        # 确认删除
        if not messagebox.askyesno("确认", f"确定要删除设备 {device['name']} 吗？\n注意：这也会删除与此设备相关的所有连接"):
            return
        
        # 删除与此设备相关的所有连接
        device_name = device["name"]
        connections_to_remove = []
        
        for connection in self.topology_data["connections"]:
            from_device = connection["from"].split(":")[0]
            to_device = connection["to"].split(":")[0]
            
            if from_device == device_name or to_device == device_name:
                connections_to_remove.append(connection)
        
        for connection in connections_to_remove:
            self.topology_data["connections"].remove(connection)
        
        # 删除设备
        self.topology_data["devices"].pop(device_index)
        
        # 更新设备和连接列表
        self.update_devices_listbox()
        self.update_connections_listbox()
        
        self.log(f"已删除设备: {device_name} 和相关连接")

    def add_connection(self):
        """添加连接"""
        # 检查是否有设备
        if not self.topology_data["devices"]:
            messagebox.showinfo("提示", "请先添加设备")
            return
        
        # 创建连接对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("添加连接")
        dialog.geometry("450x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 准备设备列表和接口数据
        devices = [(device["name"], device["type"]) for device in self.topology_data["devices"]]
        interface_templates = {
            "S5700": ["GigabitEthernet0/0/1", "GigabitEthernet0/0/2", "GigabitEthernet0/0/3", "GigabitEthernet0/0/4"],
            "S5730": ["GigabitEthernet0/0/1", "GigabitEthernet0/0/2", "GigabitEthernet0/0/3", "GigabitEthernet0/0/4"],
            "CE6850": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2", "GigabitEthernet1/0/3", "GigabitEthernet1/0/4"],
            "AR2220": ["GigabitEthernet0/0/0", "GigabitEthernet0/0/1"],
            "USG6000": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2", "GigabitEthernet1/0/3", "GigabitEthernet1/0/4"]
        }
        
        # 来源设备
        ttk.Label(dialog, text="来源设备:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        from_device_var = tk.StringVar()
        from_device_combo = ttk.Combobox(dialog, textvariable=from_device_var, width=25)
        from_device_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        from_device_combo['values'] = [device[0] for device in devices]
        
        # 来源端口
        ttk.Label(dialog, text="来源端口:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        from_port_var = tk.StringVar()
        from_port_combo = ttk.Combobox(dialog, textvariable=from_port_var, width=25)
        from_port_combo.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 目标设备
        ttk.Label(dialog, text="目标设备:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        to_device_var = tk.StringVar()
        to_device_combo = ttk.Combobox(dialog, textvariable=to_device_var, width=25)
        to_device_combo.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        to_device_combo['values'] = [device[0] for device in devices]
        
        # 目标端口
        ttk.Label(dialog, text="目标端口:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        to_port_var = tk.StringVar()
        to_port_combo = ttk.Combobox(dialog, textvariable=to_port_var, width=25)
        to_port_combo.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 带宽
        ttk.Label(dialog, text="带宽:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        bandwidth_var = tk.StringVar(value="1G")
        bandwidth_combo = ttk.Combobox(dialog, textvariable=bandwidth_var, width=25)
        bandwidth_combo.grid(row=4, column=1, sticky=tk.W, padx=10, pady=5)
        bandwidth_combo['values'] = ["100M", "1G", "10G"]
        
        # 更新端口列表
        def update_from_ports(*args):
            device_name = from_device_var.get()
            if not device_name:
                return
            
            # 查找设备类型
            device_type = None
            for d_name, d_type in devices:
                if d_name == device_name:
                    device_type = d_type
                    break
            
            if device_type and device_type in interface_templates:
                from_port_combo['values'] = interface_templates[device_type]
            else:
                from_port_combo['values'] = []
        
        def update_to_ports(*args):
            device_name = to_device_var.get()
            if not device_name:
                return
            
            # 查找设备类型
            device_type = None
            for d_name, d_type in devices:
                if d_name == device_name:
                    device_type = d_type
                    break
            
            if device_type and device_type in interface_templates:
                to_port_combo['values'] = interface_templates[device_type]
            else:
                to_port_combo['values'] = []
        
        # 绑定变更事件
        from_device_var.trace('w', update_from_ports)
        to_device_var.trace('w', update_to_ports)
        
        # 确定/取消按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        def on_ok():
            # 验证必填字段
            from_device = from_device_var.get().strip()
            from_port = from_port_var.get().strip()
            to_device = to_device_var.get().strip()
            to_port = to_port_var.get().strip()
            
            if not all([from_device, from_port, to_device, to_port]):
                messagebox.showwarning("警告", "来源设备、端口和目标设备、端口为必填项", parent=dialog)
                return
            
            # 检查是否连接到自己
            if from_device == to_device:
                messagebox.showwarning("警告", "不能创建设备到自身的连接", parent=dialog)
                return
            
            # 创建连接对象
            connection = {
                "from": f"{from_device}:{from_port}",
                "to": f"{to_device}:{to_port}",
                "bandwidth": bandwidth_var.get().strip()
            }
            
            # 检查连接是否已存在
            for existing_conn in self.topology_data["connections"]:
                if (existing_conn["from"] == connection["from"] and existing_conn["to"] == connection["to"]) or \
                   (existing_conn["to"] == connection["from"] and existing_conn["from"] == connection["to"]):
                    messagebox.showwarning("警告", "相同的设备连接已存在", parent=dialog)
                    return
            
            # 添加到拓扑数据中
            self.topology_data["connections"].append(connection)
            
            # 更新连接列表
            self.update_connections_listbox()
            
            self.log(f"已添加连接: {connection['from']} → {connection['to']}")
            dialog.destroy()
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def edit_connection(self):
        """编辑连接"""
        # 获取选中的连接索引
        selection = self.connections_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要编辑的连接")
            return
        
        # 获取连接数据
        connection_index = selection[0]
        connection = self.topology_data["connections"][connection_index]
        
        # 解析连接数据
        from_parts = connection["from"].split(":")
        to_parts = connection["to"].split(":")
        
        # 创建编辑对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("编辑连接")
        dialog.geometry("450x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 准备设备列表和接口数据
        devices = [(device["name"], device["type"]) for device in self.topology_data["devices"]]
        interface_templates = {
            "S5700": ["GigabitEthernet0/0/1", "GigabitEthernet0/0/2", "GigabitEthernet0/0/3", "GigabitEthernet0/0/4"],
            "S5730": ["GigabitEthernet0/0/1", "GigabitEthernet0/0/2", "GigabitEthernet0/0/3", "GigabitEthernet0/0/4"],
            "CE6850": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2", "GigabitEthernet1/0/3", "GigabitEthernet1/0/4"],
            "AR2220": ["GigabitEthernet0/0/0", "GigabitEthernet0/0/1"],
            "USG6000": ["GigabitEthernet1/0/1", "GigabitEthernet1/0/2", "GigabitEthernet1/0/3", "GigabitEthernet1/0/4"]
        }
        
        # 来源设备
        ttk.Label(dialog, text="来源设备:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        from_device_var = tk.StringVar(value=from_parts[0])
        from_device_combo = ttk.Combobox(dialog, textvariable=from_device_var, width=25)
        from_device_combo.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        from_device_combo['values'] = [device[0] for device in devices]
        
        # 来源端口
        ttk.Label(dialog, text="来源端口:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        from_port_var = tk.StringVar(value=from_parts[1])
        from_port_combo = ttk.Combobox(dialog, textvariable=from_port_var, width=25)
        from_port_combo.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 目标设备
        ttk.Label(dialog, text="目标设备:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        to_device_var = tk.StringVar(value=to_parts[0])
        to_device_combo = ttk.Combobox(dialog, textvariable=to_device_var, width=25)
        to_device_combo.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        to_device_combo['values'] = [device[0] for device in devices]
        
        # 目标端口
        ttk.Label(dialog, text="目标端口:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        to_port_var = tk.StringVar(value=to_parts[1])
        to_port_combo = ttk.Combobox(dialog, textvariable=to_port_var, width=25)
        to_port_combo.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 带宽
        ttk.Label(dialog, text="带宽:").grid(row=4, column=0, sticky=tk.W, padx=10, pady=5)
        bandwidth_var = tk.StringVar(value=connection.get("bandwidth", "1G"))
        bandwidth_combo = ttk.Combobox(dialog, textvariable=bandwidth_var, width=25)
        bandwidth_combo.grid(row=4, column=1, sticky=tk.W, padx=10, pady=5)
        bandwidth_combo['values'] = ["100M", "1G", "10G"]
        
        # 更新端口列表（设置初始值）
        for device in self.topology_data["devices"]:
            if device["name"] == from_parts[0]:
                from_device_type = device["type"]
                if from_device_type in interface_templates:
                    from_port_combo['values'] = interface_templates[from_device_type]
            
            if device["name"] == to_parts[0]:
                to_device_type = device["type"]
                if to_device_type in interface_templates:
                    to_port_combo['values'] = interface_templates[to_device_type]
        
        # 更新端口列表（动态更新）
        def update_from_ports(*args):
            device_name = from_device_var.get()
            if not device_name:
                return
            
            # 查找设备类型
            for device in self.topology_data["devices"]:
                if device["name"] == device_name:
                    device_type = device["type"]
                    if device_type in interface_templates:
                        from_port_combo['values'] = interface_templates[device_type]
                    break
        
        def update_to_ports(*args):
            device_name = to_device_var.get()
            if not device_name:
                return
            
            # 查找设备类型
            for device in self.topology_data["devices"]:
                if device["name"] == device_name:
                    device_type = device["type"]
                    if device_type in interface_templates:
                        to_port_combo['values'] = interface_templates[device_type]
                    break
        
        # 绑定变更事件
        from_device_var.trace('w', update_from_ports)
        to_device_var.trace('w', update_to_ports)
        
        # 确定/取消按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=10)
        
        def on_ok():
            # 验证必填字段
            from_device = from_device_var.get().strip()
            from_port = from_port_var.get().strip()
            to_device = to_device_var.get().strip()
            to_port = to_port_var.get().strip()
            
            if not all([from_device, from_port, to_device, to_port]):
                messagebox.showwarning("警告", "来源设备、端口和目标设备、端口为必填项", parent=dialog)
                return
            
            # 检查是否连接到自己
            if from_device == to_device:
                messagebox.showwarning("警告", "不能创建设备到自身的连接", parent=dialog)
                return
            
            # 创建新连接对象
            new_connection = {
                "from": f"{from_device}:{from_port}",
                "to": f"{to_device}:{to_port}",
                "bandwidth": bandwidth_var.get().strip()
            }
            
            # 检查是否与其他连接冲突
            for i, existing_conn in enumerate(self.topology_data["connections"]):
                if i != connection_index and (
                   (existing_conn["from"] == new_connection["from"] and existing_conn["to"] == new_connection["to"]) or
                   (existing_conn["to"] == new_connection["from"] and existing_conn["from"] == new_connection["to"])):
                    messagebox.showwarning("警告", "相同的设备连接已存在", parent=dialog)
                    return
            
            # 更新连接对象
            self.topology_data["connections"][connection_index] = new_connection
            
            # 更新连接列表
            self.update_connections_listbox()
            
            self.log(f"已更新连接: {new_connection['from']} → {new_connection['to']}")
            dialog.destroy()
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def delete_connection(self):
        """删除连接"""
        # 获取选中的连接索引
        selection = self.connections_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要删除的连接")
            return
        
        # 获取连接数据
        connection_index = selection[0]
        connection = self.topology_data["connections"][connection_index]
        
        # 确认删除
        if not messagebox.askyesno("确认", f"确定要删除连接 {connection['from']} → {connection['to']} 吗？"):
            return
        
        # 删除连接
        self.topology_data["connections"].pop(connection_index)
        
        # 更新连接列表
        self.update_connections_listbox()
        
        self.log(f"已删除连接: {connection['from']} → {connection['to']}")

    def generate_topology(self):
        """生成拓扑文件"""
        # 检查是否有设备和连接
        if not self.topology_data["devices"]:
            messagebox.showinfo("提示", "请先添加设备")
            return
        
        if not self.topology_data["connections"]:
            if not messagebox.askyesno("确认", "当前拓扑没有任何连接，确定要继续生成吗？"):
                return
        
        # 获取项目名称
        project_name = self.project_name_var.get().strip()
        if not project_name:
            messagebox.showinfo("提示", "请输入项目名称")
            return
        
        # 创建输出目录
        config_dir = Path.cwd() / "configs"
        config_dir.mkdir(exist_ok=True)
        
        # 生成拓扑
        try:
            self.log(f"开始生成拓扑: {project_name}")
            self.log(f"设备数量: {len(self.topology_data['devices'])}")
            self.log(f"连接数量: {len(self.topology_data['connections'])}")
            
            # 打印设备和连接信息用于调试
            for device in self.topology_data["devices"]:
                self.log(f"设备: {device['name']} ({device['type']})")
            
            for conn in self.topology_data["connections"]:
                self.log(f"连接: {conn['from']} → {conn['to']}")
            
            # 生成拓扑数据
            topology = self.generator.generate(self.topology_data)
            self.log(f"拓扑数据生成成功: {len(topology['devices'])}个设备，{len(topology['connections'])}个连接")
            
            # 保存JSON格式拓扑
            json_file = config_dir / f"{project_name}.json"
            self.generator.save_topology(topology, json_file)
            self.log(f"拓扑JSON文件已保存到: {json_file}")
            
            # 保存eNSP拓扑文件
            topo_file = config_dir / f"{project_name}.topo"
            self.log(f"正在生成topo文件: {topo_file}")
            
            result = self.generator.generate_topo_file(topology, topo_file)
            if result:
                self.log(f"eNSP拓扑文件已生成: {topo_file}")
                
                # 检查文件是否为空
                file_size = os.path.getsize(topo_file)
                if file_size == 0:
                    self.log(f"警告: 生成的文件大小为0字节")
                    messagebox.showwarning("警告", "生成的拓扑文件大小为0字节，可能无法在eNSP中正确加载。请检查日志获取详细信息。")
                else:
                    self.log(f"文件大小: {file_size} 字节")
                
                # 保存当前拓扑数据
                self.current_topology = topology
                self.current_topo_file = topo_file
                
                # 更新导入路径
                self.import_topo_path_var.set(str(topo_file))
                
                # 显示成功消息
                messagebox.showinfo("成功", f"拓扑已成功生成！\n\n文件位置：\n{topo_file}\n\n请转到'eNSP控制'标签页导入拓扑文件。")
                
                # 切换到eNSP控制页面
                self.notebook.select(2)  # 索引从0开始，eNSP控制是第3个标签
            else:
                self.log(f"错误: 拓扑文件生成失败")
                messagebox.showerror("错误", "生成拓扑文件失败，请检查日志获取详细信息。")
        
        except Exception as e:
            self.log(f"生成拓扑时出错: {str(e)}")
            
            # 更详细的错误跟踪
            import traceback
            error_trace = traceback.format_exc()
            self.log(f"错误详情: {error_trace}")
            
            # 显示错误对话框
            messagebox.showerror("错误", f"生成拓扑时出错: {str(e)}\n\n请查看日志获取详细信息。")
    
    def save_topology(self):
        """保存当前拓扑数据到文件"""
        # 获取保存路径
        file_path = filedialog.asksaveasfilename(
            title="保存拓扑数据",
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # 保存拓扑数据
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.topology_data, f, ensure_ascii=False, indent=2)
            
            self.log(f"拓扑数据已保存到: {file_path}")
            messagebox.showinfo("成功", f"拓扑数据已保存！\n\n文件位置：\n{file_path}")
            
        except Exception as e:
            self.log(f"保存拓扑数据时出错: {str(e)}")
            messagebox.showerror("错误", f"保存拓扑数据时出错: {str(e)}")
    
    def load_topology(self):
        """从文件加载拓扑数据"""
        # 获取文件路径
        file_path = filedialog.askopenfilename(
            title="加载拓扑数据",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # 加载拓扑数据
            with open(file_path, 'r', encoding='utf-8') as f:
                topology_data = json.load(f)
            
            # 验证数据格式
            if not isinstance(topology_data, dict) or "devices" not in topology_data or "connections" not in topology_data:
                raise ValueError("拓扑数据格式不正确")
            
            # 更新拓扑数据
            self.topology_data = topology_data
            
            # 更新列表框
            self.update_devices_listbox()
            self.update_connections_listbox()
            
            # 从文件名中提取项目名称
            project_name = Path(file_path).stem
            self.project_name_var.set(project_name)
            
            self.log(f"已加载拓扑数据: {file_path}")
            messagebox.showinfo("成功", f"拓扑数据已加载！\n\n文件位置：\n{file_path}")
            
        except Exception as e:
            self.log(f"加载拓扑数据时出错: {str(e)}")
            messagebox.showerror("错误", f"加载拓扑数据时出错: {str(e)}")
    
    def import_to_ensp(self):
        """将拓扑文件导入到eNSP"""
        # 获取拓扑文件路径
        topo_file = self.import_topo_path_var.get().strip()
        if not topo_file:
            messagebox.showinfo("提示", "请选择要导入的拓扑文件")
            return
        
        # 检查文件是否存在
        if not os.path.exists(topo_file):
            messagebox.showerror("错误", f"拓扑文件不存在: {topo_file}")
            return
        
        # 提示用户手动打开eNSP并导入拓扑文件 - 增加启动设备的提示
        guide = f"""
请按照以下步骤手动导入拓扑文件到eNSP:

1. 打开eNSP应用程序
2. 在eNSP窗口中点击 "文件" -> "打开"
3. 浏览到以下位置并选择拓扑文件:
   {topo_file}
4. 点击 "确定" 加载拓扑

要启动设备，请在eNSP中:
1. 选择所有设备（按Ctrl+A或右键菜单"全选"）
2. 右键单击选择"启动"
3. 等待所有设备完成启动
"""
        messagebox.showinfo("eNSP导入指南", guide)
        self.log(f"已生成导入拓扑文件指南，请手动打开eNSP并导入文件: {topo_file}")
    
    def start_all_devices(self):
        """此功能已移除"""
        pass
    
    def stop_all_devices(self):
        """此功能已移除"""
        pass

    def connect_device(self):
        """连接到网络设备（优化版无弹窗）"""
        # 直接从主界面输入框获取连接信息
        ip = self.device_ip_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            self.log("端口必须是有效的数字")
            return
        
        device_type = self.device_type_var.get().strip()
        
        # 验证必填字段
        if not (ip and username and password):
            self.log("所有连接字段都必须填写")
            return
        
        # 禁用连接按钮，防止重复点击
        self.connect_button.config(state=tk.DISABLED)
        # 更新连接状态标签
        self.conn_status_var.set("连接中...")
        self.conn_status_label.config(foreground="orange")
        
        # 使用线程避免UI阻塞
        def connect_thread():
            import socket
            import time
            
            try:
                # 首先测试端口是否开放
                self.log(f"正在检查设备 {ip} 端口 {port} 是否可达...")
                
                # 检查是否可以连接到端口
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(3)
                    s.connect((ip, port))
                    s.close()
                    self.log(f"设备 {ip} 可达")
                except (socket.timeout, ConnectionRefusedError) as e:
                    self.log(f"设备 {ip} 不可达或端口 {port} 未开放: {str(e)}")
                    self.connect_button.config(state=tk.NORMAL)
                    self.conn_status_var.set("未连接")
                    self.conn_status_label.config(foreground="red")
                    return
                
                # 尝试进行连接
                self.log(f"正在连接到设备 {ip}...")
                
                # 连接前检查是否已存在连接
                if ip in self.connected_devices:
                    self.log(f"已经连接到设备 {ip}，先断开现有连接...")
                    try:
                        self.device_config.disconnect_device(ip)
                        if ip in self.connected_devices:
                            self.connected_devices.remove(ip)
                        self.update_connected_devices_listbox()
                    except Exception as e:
                        self.log(f"断开现有连接失败: {str(e)}")
                
                # 连接设备
                result = self.device_config.connect_device(
                    device_ip=ip,
                    username=username,
                    password=password,
                    port=port,
                    device_type=device_type
                )
                
                # 更新连接状态
                if result:
                    self.log(f"成功连接到设备 {ip}")
                    # 更新状态标签为连接成功
                    self.conn_status_var.set("已连接")
                    self.conn_status_label.config(foreground="green")
                    
                    # 添加到已连接设备列表
                    if ip not in self.connected_devices:
                        self.connected_devices.append(ip)
                        self.update_connected_devices_listbox()
                    
                    # 启动连接监控线程
                    monitor_thread = threading.Thread(
                        target=self.monitor_connection,
                        args=(ip, username, password, port, device_type),
                        daemon=True
                    )
                    monitor_thread.start()
                else:
                    self.log(f"连接到设备 {ip} 失败，请检查凭据和设备状态")
                    # 更新状态标签为连接失败
                    self.conn_status_var.set("连接失败")
                    self.conn_status_label.config(foreground="red")
                
                # 重新启用连接按钮
                self.connect_button.config(state=tk.NORMAL)
            
            except Exception as e:
                self.log(f"连接过程中出现错误: {str(e)}")
                self.connect_button.config(state=tk.NORMAL)
                self.conn_status_var.set("连接错误")
                self.conn_status_label.config(foreground="red")
        
        # 启动连接线程
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()

    def monitor_connection(self, ip, username, password, port, device_type):
        """监控连接状态，如果断开则尝试重连"""
        stop_flag = False
        while not stop_flag and ip in self.connected_devices:
            try:
                # 检查连接是否仍然有效
                if ip in self.device_config.connections:
                    connection = self.device_config.connections[ip]
                    if not connection.is_alive():
                        self.log(f"设备 {ip} 连接已断开，尝试重新连接...")
                        
                        # 尝试重新连接
                        try:
                            # 先断开可能存在的连接
                            self.device_config.disconnect_device(ip)
                            if ip in self.connected_devices:
                                self.connected_devices.remove(ip)
                            time.sleep(1)
                            
                            # 重新连接
                            result = self.device_config.connect_device(
                                device_ip=ip,
                                username=username,
                                password=password,
                                port=port,
                                device_type=device_type
                            )
                            
                            if result:
                                self.log(f"已重新连接到设备 {ip}")
                                if ip not in self.connected_devices:
                                    self.connected_devices.append(ip)
                                self.update_connected_devices_listbox()
                            else:
                                self.log(f"重新连接失败，请手动重试")
                        except Exception as e:
                            self.log(f"重新连接时出错: {str(e)}")
                
                # 30秒检查一次
                for _ in range(30):
                    if ip not in self.connected_devices:
                        stop_flag = True
                        break
                    time.sleep(1)
            except Exception as e:
                self.log(f"监控连接时出错: {str(e)}")
                time.sleep(5)
    
    def disconnect_device(self):
        """断开与设备的连接"""
        # 获取选中的设备
        selection = self.connected_devices_listbox.curselection()
        if not selection:
            self.log("请先选择一个已连接的设备")
            return
        
        # 获取设备IP
        device_ip = self.connected_devices_listbox.get(selection[0])
        
        # 断开连接
        self.log(f"正在断开与设备 {device_ip} 的连接...")
        
        # 禁用断开按钮
        self.disconnect_button.config(state=tk.DISABLED)
        
        # 断开连接
        if self.device_config.disconnect_device(device_ip):
            self.log(f"已断开与设备 {device_ip} 的连接")
            
            # 从已连接设备列表移除
            if device_ip in self.connected_devices:
                self.connected_devices.remove(device_ip)
                self.update_connected_devices_listbox()
            
            # 更新连接状态标签
            self.conn_status_var.set("未连接")
            self.conn_status_label.config(foreground="red")
        else:
            self.log(f"断开与设备 {device_ip} 的连接失败")
        
        # 启用断开按钮
        self.disconnect_button.config(state=tk.NORMAL)
    
    def _disconnect_device_by_ip(self, device_ip):
        """通过IP断开与设备的连接（内部方法）"""
        try:
            # 断开设备连接
            if self.device_config.disconnect_device(device_ip):
                self.log(f"已断开与设备 {device_ip} 的连接")
                
                # 从已连接设备列表中移除
                if device_ip in self.connected_devices:
                    self.connected_devices.remove(device_ip)
                
                # 更新界面
                self.update_connected_devices_listbox()
                return True
            else:
                self.log(f"断开与设备 {device_ip} 的连接失败")
                return False
        except Exception as e:
            self.log(f"断开连接时出错: {str(e)}")
            return False
            
    def update_connected_devices_listbox(self):
        """更新已连接设备列表框"""
        # 清空列表框
        self.connected_devices_listbox.delete(0, tk.END)
        
        # 添加已连接设备
        for device_ip in self.connected_devices:
            self.connected_devices_listbox.insert(tk.END, device_ip)
    
    def send_commands(self):
        """发送配置命令到设备"""
        # 获取选中的设备
        selection = self.connected_devices_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要配置的设备")
            return
        
        # 获取设备IP
        device_ip = self.connected_devices_listbox.get(selection[0])
        
        # 获取命令
        commands_text = self.commands_text.get("1.0", tk.END).strip()
        if not commands_text:
            messagebox.showinfo("提示", "请输入要执行的命令")
            return
        
        # 解析命令
        commands = [cmd.strip() for cmd in commands_text.split("\n") if cmd.strip()]
        
        # 发送命令
        try:
            self.log(f"正在向设备 {device_ip} 发送配置命令...")
            
            # 执行命令
            output = self.device_config.configure_device(device_ip, commands)
            
            if output:
                self.log(f"命令执行成功，输出:\n{output}\n")
                messagebox.showinfo("成功", f"配置命令已成功发送到设备 {device_ip}")
            else:
                self.log(f"执行命令失败")
                messagebox.showerror("错误", f"向设备 {device_ip} 发送命令失败")
        
        except Exception as e:
            self.log(f"发送命令时出错: {str(e)}")
            messagebox.showerror("错误", f"发送命令时出错: {str(e)}")
    
    def save_device_config(self):
        """保存设备配置"""
        # 获取选中的设备
        selection = self.connected_devices_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要保存配置的设备")
            return
        
        # 获取设备IP
        device_ip = self.connected_devices_listbox.get(selection[0])
        
        # 保存配置
        try:
            self.log(f"正在保存设备 {device_ip} 的配置...")
            
            # 执行保存
            saved = self.device_config.save_config(device_ip)
            
            if saved:
                self.log(f"设备 {device_ip} 配置已保存")
                messagebox.showinfo("成功", f"设备 {device_ip} 的配置已成功保存")
            else:
                self.log(f"保存设备 {device_ip} 配置失败")
                messagebox.showerror("错误", f"保存设备 {device_ip} 的配置失败")
        
        except Exception as e:
            self.log(f"保存配置时出错: {str(e)}")
            messagebox.showerror("错误", f"保存配置时出错: {str(e)}")
    
    def load_command_template(self):
        """加载命令模板"""
        # 创建命令模板选择对话框
        templates = {
            "基本VLAN配置": """system-view
vlan batch 10 20 30
interface GigabitEthernet0/0/1
port link-type trunk
port trunk allow-pass vlan 10 20 30
quit
interface Vlanif10
ip address 192.168.10.1 255.255.255.0
quit""",
            "OSPF路由配置": """system-view
ospf 1
area 0
network 192.168.1.0 0.0.0.255
quit
quit""",
            "ACL配置": """system-view
acl 3000
rule 5 permit ip source 192.168.1.0 0.0.0.255
rule 10 deny ip
quit""",
            "SSH服务配置": """system-view
stelnet server enable
ssh user admin authentication-type password
ssh user admin service-type stelnet
user-interface vty 0 4
authentication-mode aaa
protocol inbound ssh
quit"""
        }
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("加载命令模板")
        dialog.geometry("400x300")
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 模板列表
        ttk.Label(dialog, text="选择模板:").pack(anchor=tk.W, padx=10, pady=5)
        
        template_listbox = tk.Listbox(dialog, width=40, height=10)
        template_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        for template_name in templates.keys():
            template_listbox.insert(tk.END, template_name)
        
        # 预览区域
        ttk.Label(dialog, text="预览:").pack(anchor=tk.W, padx=10, pady=5)
        
        preview_text = scrolledtext.ScrolledText(dialog, width=40, height=10, wrap=tk.WORD)
        preview_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 选择事件处理
        def on_template_select(event):
            selection = template_listbox.curselection()
            if selection:
                template_name = template_listbox.get(selection[0])
                template_content = templates[template_name]
                preview_text.delete("1.0", tk.END)
                preview_text.insert(tk.END, template_content)
        
        template_listbox.bind("<<ListboxSelect>>", on_template_select)
        
        # 按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        def on_ok():
            # 获取选中的模板
            selection = template_listbox.curselection()
            if selection:
                template_name = template_listbox.get(selection[0])
                template_content = templates[template_name]
                
                # 将模板内容插入到命令文本框
                self.commands_text.delete("1.0", tk.END)
                self.commands_text.insert(tk.END, template_content)
                
                dialog.destroy()
            else:
                messagebox.showinfo("提示", "请选择一个模板", parent=dialog)
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.RIGHT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=10)
    
    def configure_port(self):
        """配置端口VLAN"""
        # 获取选中的设备
        selection = self.connected_devices_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个已连接的设备")
            return
        
        # 获取设备IP
        device_ip = self.connected_devices_listbox.get(selection[0])
        
        # 创建配置对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("配置端口VLAN")
        dialog.geometry("500x450")  # 增加高度以显示验证结果
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 配置参数
        ttk.Label(dialog, text=f"设备: {device_ip}", font=("微软雅黑", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=10, pady=10)
        
        ttk.Label(dialog, text="端口名称:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        port_var = tk.StringVar(value="GigabitEthernet0/0/1")
        port_entry = ttk.Entry(dialog, textvariable=port_var, width=25)
        port_entry.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(dialog, text="VLAN ID:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=5)
        vlan_var = tk.StringVar(value="10")
        vlan_entry = ttk.Entry(dialog, textvariable=vlan_var, width=10)
        vlan_entry.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(dialog, text="端口类型:").grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)
        port_type_var = tk.StringVar(value="access")
        port_types = ["access", "trunk"]
        port_type_combo = ttk.Combobox(dialog, textvariable=port_type_var, values=port_types, width=10)
        port_type_combo.grid(row=3, column=1, sticky=tk.W, padx=10, pady=5)
        
        # 预览区域
        ttk.Label(dialog, text="配置预览:").grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)
        
        preview_text = scrolledtext.ScrolledText(dialog, width=50, height=8, wrap=tk.WORD)
        preview_text.grid(row=5, column=0, columnspan=2, padx=10, pady=5, sticky=tk.NSEW)
        
        # 验证结果区域
        ttk.Label(dialog, text="验证结果:").grid(row=6, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)
        
        verification_text = scrolledtext.ScrolledText(dialog, width=50, height=8, wrap=tk.WORD)
        verification_text.grid(row=7, column=0, columnspan=2, padx=10, pady=5, sticky=tk.NSEW)
        verification_text.insert(tk.END, "配置完成后将显示验证结果...\n")
        verification_text.config(state=tk.DISABLED)
        
        # 更新预览
        def update_preview(*args):
            port = port_var.get().strip()
            vlan = vlan_var.get().strip()
            port_type = port_type_var.get().strip()
            
            if not (port and vlan):
                return
            
            preview = f"system-view\nvlan {vlan}\ninterface {port}\n"
            
            if port_type == "access":
                preview += f"port link-type access\nport default vlan {vlan}"
            else:
                preview += f"port link-type trunk\nport trunk allow-pass vlan {vlan}"
            
            preview_text.delete("1.0", tk.END)
            preview_text.insert(tk.END, preview)
        
        # 绑定更新事件
        port_var.trace("w", update_preview)
        vlan_var.trace("w", update_preview)
        port_type_var.trace("w", update_preview)
        
        # 初始预览
        update_preview()

        # 让对话框的行和列可以跟随调整大小
        dialog.grid_rowconfigure(5, weight=1)
        dialog.grid_rowconfigure(7, weight=1)
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_columnconfigure(1, weight=1)
        
        # 按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.grid(row=8, column=0, columnspan=2, pady=10)
        
        def on_apply():
            # 获取参数
            port = port_var.get().strip()
            vlan = vlan_var.get().strip()
            port_type = port_type_var.get().strip()
            
            if not port:
                messagebox.showwarning("警告", "请输入端口名称", parent=dialog)
                return
            
            if not vlan:
                messagebox.showwarning("警告", "请输入VLAN ID", parent=dialog)
                return
            
            try:
                vlan_id = int(vlan)
                if vlan_id < 1 or vlan_id > 4094:
                    messagebox.showwarning("警告", "VLAN ID必须在1-4094范围内", parent=dialog)
                    return
            except ValueError:
                messagebox.showwarning("警告", "VLAN ID必须是数字", parent=dialog)
                return
            
            # 显示进度
            status_label = ttk.Label(dialog, text="正在配置...", foreground="blue")
            status_label.grid(row=9, column=0, columnspan=2, pady=5)
            dialog.update()
            
            # 清空验证结果区域并准备显示新结果
            verification_text.config(state=tk.NORMAL)
            verification_text.delete("1.0", tk.END)
            verification_text.insert(tk.END, "配置中，请稍候...\n")
            dialog.update()
            
            # 配置端口
            try:
                self.log(f"正在配置设备 {device_ip} 的端口 {port}，VLAN {vlan}，类型 {port_type}...")
                
                # 调用配置方法
                result = self.device_config.configure_port(
                    device_ip=device_ip,
                    port_name=port,
                    vlan_id=vlan_id,
                    port_type=port_type
                )
                
                # 获取验证结果
                try:
                    # 连接设备
                    connection = self.device_config.connections[device_ip]
                    
                    # 获取配置验证
                    verification_output = connection.send_command(f"display current-configuration interface {port}")
                    
                    # 显示验证结果
                    verification_text.delete("1.0", tk.END)
                    verification_text.insert(tk.END, f"端口配置验证结果:\n{verification_output}\n")
                    
                    # 高亮关键信息
                    if port_type == "access":
                        verify_terms = ["link-type access", f"default vlan {vlan}"]
                    else:
                        verify_terms = ["link-type trunk", f"allow-pass vlan {vlan}"]
                    
                    for term in verify_terms:
                        start_pos = "1.0"
                        while True:
                            pos = verification_text.search(term, start_pos, tk.END)
                            if not pos:
                                break
                            line = pos.split('.')[0]
                            col = pos.split('.')[1]
                            end_pos = f"{line}.{int(col) + len(term)}"
                            verification_text.tag_add("highlight", pos, end_pos)
                            start_pos = end_pos
                    
                    verification_text.tag_configure("highlight", foreground="green", font=("微软雅黑", 10, "bold"))
                    
                except Exception as e:
                    self.log(f"获取验证结果失败: {str(e)}")
                    verification_text.insert(tk.END, f"获取验证结果失败，但配置可能已成功: {str(e)}\n")
                
                if result:
                    self.log(f"端口 {port} 配置成功")
                    status_label.config(text="配置成功！", foreground="green")
                    messagebox.showinfo("成功", f"端口 {port} 已成功配置为 {port_type} 模式，VLAN {vlan}", parent=dialog)
                else:
                    self.log(f"端口 {port} 配置失败")
                    status_label.config(text="配置失败！", foreground="red")
                    verification_text.insert(tk.END, "\n配置失败，请检查日志获取更多信息。\n")
                    messagebox.showerror("错误", f"端口 {port} 配置失败，请检查日志", parent=dialog)
            
            except Exception as e:
                self.log(f"配置端口时出错: {str(e)}")
                status_label.config(text="配置错误！", foreground="red")
                verification_text.insert(tk.END, f"\n配置过程出错: {str(e)}\n")
                messagebox.showerror("错误", f"配置端口时出错: {str(e)}", parent=dialog)
            
            verification_text.config(state=tk.NORMAL)
        
        ttk.Button(buttons_frame, text="应用配置", command=on_apply).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="关闭", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def save_command_template(self):
        """保存命令模板"""
        # 获取当前命令
        commands = self.commands_text.get("1.0", tk.END).strip()
        if not commands:
            messagebox.showinfo("提示", "请先输入要保存的命令")
            return
        
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("保存命令模板")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 模板名称
        ttk.Label(dialog, text="模板名称:").pack(anchor=tk.W, padx=10, pady=5)
        
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=30).pack(fill=tk.X, padx=10, pady=5)
        
        # 按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        def on_ok():
            # 获取模板名称
            template_name = name_var.get().strip()
            if not template_name:
                messagebox.showinfo("提示", "请输入模板名称", parent=dialog)
                return
            
            # 保存模板
            try:
                # 创建模板目录
                templates_dir = Path("templates")
                templates_dir.mkdir(exist_ok=True)
                
                # 保存模板文件
                template_file = templates_dir / f"{template_name}.txt"
                with open(template_file, "w", encoding="utf-8") as f:
                    f.write(commands)
                
                self.log(f"命令模板已保存: {template_name}")
                messagebox.showinfo("成功", f"命令模板 '{template_name}' 已保存", parent=dialog)
                dialog.destroy()
            
            except Exception as e:
                self.log(f"保存命令模板时出错: {str(e)}")
                messagebox.showerror("错误", f"保存命令模板时出错: {str(e)}", parent=dialog)
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.RIGHT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=10)
    
    def model_type_selected(self, event):
        """当选择不同的模型类型时触发"""
        model_type = self.model_type_var.get()
        self.log(f"选择模型类型: {model_type}")
        
        # 如果选择的非本地模型，自动打开API设置对话框
        if model_type != "本地规则解析" and not self.nlp_generator.api_key:
            api_model_map = {
                "本地规则解析": "local",
                "OpenAI": "openai",
                "DeepSeek": "deepseek",
                "讯飞星火": "xunfei"
            }
            model_code = api_model_map.get(model_type, "local")
            
            # 设置默认API端点URL
            if model_code == "openai" and not self.nlp_generator.api_url:
                self.nlp_generator.api_url = "https://api.openai.com/v1/chat/completions"
            elif model_code == "deepseek" and not self.nlp_generator.api_url:
                self.nlp_generator.api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
            
            # 如果用户确认，则打开API设置对话框
            if messagebox.askyesno("提示", f"您选择了{model_type}，但未设置API密钥。要现在设置吗？"):
                self.setup_api()
    
    def setup_api(self):
        """设置API"""
        model_type = self.model_type_var.get()
        api_model_map = {
            "本地规则解析": "local",
            "OpenAI": "openai",
            "DeepSeek": "deepseek",
            "讯飞星火": "xunfei"
        }
        
        model_code = api_model_map.get(model_type, "local")
        
        # 如果是本地规则解析，不需要设置API
        if model_code == "local":
            messagebox.showinfo("提示", "本地规则解析模式不需要API密钥")
            return
        
        # 创建API设置对话框
        dialog = tk.Toplevel(self.root)
        dialog.title(f"{model_type} API设置")
        dialog.geometry("600x350")  # 增加窗口大小以适应测试连接按钮
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 根据不同的模型类型显示不同的输入字段
        row = 0
        
        # API密钥 (所有模型都需要)
        ttk.Label(dialog, text="API密钥:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=10)
        api_key_var = tk.StringVar(value=self.nlp_generator.api_key)
        api_key_entry = ttk.Entry(dialog, textvariable=api_key_var, width=50)
        api_key_entry.grid(row=row, column=1, sticky=tk.W, padx=10, pady=10)
        row += 1
        
        # API端点URL（所有模型可选）
        ttk.Label(dialog, text="API端点URL:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=10)
        api_url_var = tk.StringVar(value=self.nlp_generator.api_url)
        api_url_entry = ttk.Entry(dialog, textvariable=api_url_var, width=50)
        api_url_entry.grid(row=row, column=1, sticky=tk.W, padx=10, pady=10)
        row += 1
        
        # 讯飞星火需要额外的字段
        api_secret_var = tk.StringVar(value=self.nlp_generator.api_secret)
        api_app_id_var = tk.StringVar(value=self.nlp_generator.api_app_id)
        
        if model_code == "xunfei":
            # API密钥Secret
            ttk.Label(dialog, text="API密钥Secret:").grid(row=row, column=0, sticky=tk.W, padx=10, pady=10)
            api_secret_entry = ttk.Entry(dialog, textvariable=api_secret_var, width=50)
            api_secret_entry.grid(row=row, column=1, sticky=tk.W, padx=10, pady=10)
            row += 1
            
            # 应用ID
            ttk.Label(dialog, text="应用ID(AppId):").grid(row=row, column=0, sticky=tk.W, padx=10, pady=10)
            api_app_id_entry = ttk.Entry(dialog, textvariable=api_app_id_var, width=50)
            api_app_id_entry.grid(row=row, column=1, sticky=tk.W, padx=10, pady=10)
            row += 1
        
        # 提示信息
        help_text = ""
        if model_code == "openai":
            help_text = "OpenAI API密钥格式通常为 'sk-...'，可从OpenAI官网获取"
            if not api_url_var.get():
                api_url_var.set("https://api.openai.com/v1/chat/completions")
        elif model_code == "deepseek":
            help_text = "DeepSeek API密钥可从NVIDIA API Gateway获取，格式为'nvapi-...'，从英伟达获取"
            if not api_url_var.get():
                api_url_var.set("https://integrate.api.nvidia.com/v1/chat/completions")
        elif model_code == "xunfei":
            help_text = "讯飞星火API需要APPID、API密钥和API Secret，可从讯飞开放平台获取"
        
        if help_text:
            help_label = ttk.Label(dialog, text=help_text, foreground="gray")
            help_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)
            row += 1
        
        # 状态信息标签
        status_var = tk.StringVar(value="")
        status_label = ttk.Label(dialog, textvariable=status_var, foreground="black")
        status_label.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=5)
        row += 1
        
        # 测试连接和确定/取消按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.grid(row=row, column=0, columnspan=2, pady=10)
        
        # 使用类方法进行测试连接
        
        def test_connection():
            # 临时应用API设置进行测试
            temp_api_key = api_key_var.get().strip()
            temp_api_url = api_url_var.get().strip()
            temp_api_secret = api_secret_var.get().strip() if model_code == "xunfei" else ""
            temp_api_app_id = api_app_id_var.get().strip() if model_code == "xunfei" else ""
            
            if not temp_api_key:
                status_var.set("错误: API密钥不能为空")
                status_label.config(foreground="red")
                return
            
            # 更新状态
            status_var.set("正在测试API连接...")
            status_label.config(foreground="blue")
            dialog.update_idletasks()
            
            # 备份当前设置
            backup_api_key = self.nlp_generator.api_key
            backup_api_url = self.nlp_generator.api_url
            backup_api_secret = self.nlp_generator.api_secret
            backup_api_app_id = self.nlp_generator.api_app_id
            
            # 临时应用新设置
            self.nlp_generator.api_key = temp_api_key
            self.nlp_generator.api_url = temp_api_url
            self.nlp_generator.api_secret = temp_api_secret
            self.nlp_generator.api_app_id = temp_api_app_id
            
            # 创建一个新线程运行测试连接函数，使用类的方法
            test_thread = threading.Thread(
                target=lambda: self._run_test_connection(model_code, status_var, status_label)
            )
            test_thread.daemon = True
            test_thread.start()
            
            # 在测试完成后恢复原始设置（放在主线程，以避免竞态条件）
            def restore_settings():
                self.nlp_generator.api_key = backup_api_key
                self.nlp_generator.api_url = backup_api_url
                self.nlp_generator.api_secret = backup_api_secret
                self.nlp_generator.api_app_id = backup_api_app_id
            
            # 30秒后恢复原始设置，无论测试成功与否
            self.root.after(30000, restore_settings)
        
        def on_ok():
            # 设置API信息
            self.nlp_generator.api_key = api_key_var.get().strip()
            self.nlp_generator.api_url = api_url_var.get().strip()
            self.nlp_generator.model_type = model_code
            
            # 设置讯飞星火特有的字段
            if model_code == "xunfei":
                self.nlp_generator.api_secret = api_secret_var.get().strip()
                self.nlp_generator.api_app_id = api_app_id_var.get().strip()
            
            # 保存配置
            saved = self.nlp_generator.save_config()
            
            if saved:
                messagebox.showinfo("成功", f"{model_type} API设置已保存", parent=dialog)
                dialog.destroy()
            else:
                messagebox.showerror("错误", "保存API设置失败", parent=dialog)
        
        ttk.Button(buttons_frame, text="测试连接", command=test_connection).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def load_example_description(self):
        """加载示例网络描述"""
        examples = {
            "简单网络": """设计一个简单的网络，包含一台路由器和两台交换机。
路由器连接到两台交换机，交换机1的IP地址是192.168.1.10，交换机2的IP地址是192.168.2.10。
""",
            "VLAN网络": """设计一个包含三层交换的网络，具有以下要求：
1. 一台核心交换机
2. 两台接入交换机
3. 划分VLAN 10、20和30
4. 核心交换机连接到两台接入交换机
""",
            "总部分支网络": """设计一个总部和分支机构的网络：
总部有一台路由器和两台交换机，分支有一台路由器和一台交换机。
总部路由器通过广域网连接到分支路由器。
总部网段是192.168.1.0/24，分支网段是192.168.2.0/24。
"""
        }
        
        # 创建示例选择对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("选择示例描述")
        dialog.geometry("300x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 示例列表
        ttk.Label(dialog, text="选择示例:").pack(padx=10, pady=5, anchor=tk.W)
        
        listbox = tk.Listbox(dialog, height=5, width=30)
        listbox.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        for example_name in examples:
            listbox.insert(tk.END, example_name)
        
        # 确定/取消按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.pack(pady=10)
        
        def on_ok():
            # 获取选中的示例
            selection = listbox.curselection()
            if not selection:
                messagebox.showinfo("提示", "请选择一个示例", parent=dialog)
                return
            
            example_name = listbox.get(selection[0])
            example_content = examples[example_name]
            
            # 在描述文本框中添加示例内容
            self.description_text.delete("1.0", tk.END)
            self.description_text.insert("1.0", example_content)
            
            dialog.destroy()
        
        ttk.Button(buttons_frame, text="确定", command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=10)
    
    def generate_nlp_topology(self):
        """从自然语言描述生成拓扑"""
        # 获取项目名称
        project_name = self.nlp_project_name_var.get().strip()
        if not project_name:
            messagebox.showinfo("提示", "请输入项目名称")
            return
        
        # 检查是否已经解析过
        if hasattr(self, 'parsed_topology_data') and self.parsed_topology_data:
            # 使用已解析的拓扑数据
            topology_data = self.parsed_topology_data
            self.log(f"使用已解析的拓扑数据: {len(topology_data.get('devices', []))}个设备, {len(topology_data.get('connections', []))}个连接")
        else:
            # 获取描述文本
            description = self.description_text.get("1.0", tk.END).strip()
            if not description:
                messagebox.showinfo("提示", "请输入网络描述")
                return
            
            # 获取模型类型
            model_type_map = {
                "本地规则解析": "local",
                "OpenAI": "openai",
                "DeepSeek": "deepseek",
                "讯飞星火": "xunfei"
            }
            model_type = model_type_map.get(self.model_type_var.get(), "local")
            
            # 检查API设置（对于非本地模型）
            if model_type != "local" and not self.nlp_generator.api_key:
                if not messagebox.askyesno("警告", f"未设置{self.model_type_var.get()} API密钥，将使用本地规则解析。是否继续？"):
                    return
                model_type = "local"
            
            # 显示处理中对话框
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("处理中")
            progress_dialog.geometry("300x100")
            progress_dialog.resizable(False, False)
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()
            
            ttk.Label(progress_dialog, text="正在处理自然语言描述...").pack(padx=20, pady=10)
            progress = ttk.Progressbar(progress_dialog, mode="indeterminate")
            progress.pack(padx=20, pady=10, fill=tk.X)
            progress.start()
            
            try:
                # 解析网络描述
                self.log(f"正在使用{self.model_type_var.get()}解析网络描述...")
                topology_data = self.nlp_generator.parse_network_description(description, model_type)
                progress_dialog.destroy()
            except Exception as e:
                progress_dialog.destroy()
                self.log(f"处理自然语言描述时出错: {str(e)}")
                messagebox.showerror("错误", f"处理自然语言描述时出错: {str(e)}")
                return
        
        # 更新拓扑数据
        self.topology_data = topology_data
        
        # 设置项目名称
        self.project_name_var.set(project_name)
        
        # 更新UI
        self.update_devices_listbox()
        self.update_connections_listbox()
        
        # 切换到拓扑标签
        self.notebook.select(0)
        
        self.log(f"从自然语言描述生成的拓扑已加载: {len(topology_data.get('devices', []))}个设备, {len(topology_data.get('connections', []))}个连接")
        messagebox.showinfo("成功", 
            f"已从自然语言描述生成拓扑！\n\n设备数量: {len(topology_data.get('devices', []))}\n连接数量: {len(topology_data.get('connections', []))}\n\n请检查和编辑生成的拓扑，然后点击'生成拓扑'按钮生成最终文件。")
        
        # 清除已解析的拓扑数据，避免下次误用
        if hasattr(self, 'parsed_topology_data'):
            self.parsed_topology_data = None
    
    def parse_network_description(self):
        """
        解析网络描述
        
        该功能将用户的自然语言网络描述发送到AI模型进行处理，
        并将结果显示在解析结果预览区域，供用户确认后再生成拓扑。
        这样将流程分为两步：1) 解析描述 2) 生成拓扑，
        使用户能够在生成拓扑前查看和确认AI的解析结果。
        """
        # 获取描述文本
        description = self.description_text.get("1.0", tk.END).strip()
        if not description:
            messagebox.showinfo("提示", "请输入网络描述")
            return
        
        # 获取项目名称
        project_name = self.nlp_project_name_var.get().strip()
        if not project_name:
            messagebox.showinfo("提示", "请输入项目名称")
            return
        
        # 获取模型类型映射
        model_type_map = {
            "本地规则解析": "local",
            "OpenAI": "openai",
            "DeepSeek": "deepseek",
            "讯飞星火": "xunfei"
        }
        model_type = model_type_map.get(self.model_type_var.get(), "local")
        
        # 检查API设置（对于非本地模型）
        if model_type != "local" and not self.nlp_generator.api_key:
            if not messagebox.askyesno("警告", f"未设置{self.model_type_var.get()} API密钥，将使用本地规则解析。是否继续？"):
                return
            model_type = "local"
        
        # 启用文本区域以便流式更新
        self.parsed_result_text.config(state=tk.NORMAL)
        self.parsed_result_text.delete("1.0", tk.END)
        self.parsed_result_text.insert(tk.END, "【正在解析网络描述...】\n\n")
        self.parsed_result_text.insert(tk.END, f"• 使用{self.model_type_var.get()}解析用户输入...\n")
        self.parsed_result_text.see(tk.END)
        self.parsed_result_text.update_idletasks()
        
        # 在线程中处理以避免UI冻结
        def parse_thread():
            try:
                # 更新状态信息
                self.root.after(0, lambda: self._update_parsing_status("• 分析网络需求..."))
                time.sleep(0.5)  # 模拟处理延时
                self.root.after(0, lambda: self._update_parsing_status("• 识别设备类型和拓扑结构..."))
                time.sleep(0.5)  # 模拟处理延时
                self.root.after(0, lambda: self._update_parsing_status("• 生成设备配置..."))
                time.sleep(0.5)  # 模拟处理延时
                
                # 解析网络描述 - 这里调用我们优化的AI解析功能
                self.log(f"正在使用{self.model_type_var.get()}解析网络描述...")
                parsed_data = self.nlp_generator.parse_network_description(description, model_type)
                
                # 更新状态信息
                self.root.after(0, lambda: self._update_parsing_status("• 完成网络拓扑解析"))
                time.sleep(0.5)  # 模拟处理延时
                self.root.after(0, lambda: self._update_parsing_status("• 生成网络部署建议..."))
                time.sleep(0.5)  # 模拟处理延时
                
                # 更新解析结果文本区域
                self.root.after(0, lambda: self._update_parsed_result(parsed_data))
                
                # 显示解析成功消息
                self.log(f"网络描述解析成功: {len(parsed_data.get('devices', []))}个设备, {len(parsed_data.get('connections', []))}个连接")
            
            except Exception as e:
                self.log(f"解析网络描述时出错: {str(e)}")
                self.root.after(0, lambda: self._update_parsing_status(f"解析出错: {str(e)}", is_error=True))
        
        # 启动解析线程
        thread = threading.Thread(target=parse_thread)
        thread.daemon = True
        thread.start()
    
    def _update_parsed_result(self, data):
        """
        更新解析结果文本区域
        
        Args:
            data: 解析得到的拓扑数据字典
            
        功能:
            1. 将解析结果以格式化JSON形式显示在预览区域
            2. 保存解析结果供后续生成拓扑使用
            3. 允许用户在生成拓扑前查看和确认网络结构
        """
        # 启用文本区域以便更新
        self.parsed_result_text.config(state=tk.NORMAL)
        
        # 清空现有内容
        self.parsed_result_text.delete("1.0", tk.END)
        
        # 添加人类可读的网络拓扑描述
        self.parsed_result_text.insert(tk.END, "【网络拓扑描述】\n\n")
        
        # 添加AI方案评估和建议
        self.parsed_result_text.insert(tk.END, "AI方案评估：\n")
        
        # 生成拓扑概述
        device_count = len(data.get("devices", []))
        connection_count = len(data.get("connections", []))
        device_types = {}
        for device in data.get("devices", []):
            device_type = device.get("type", "未知")
            if device_type in device_types:
                device_types[device_type] += 1
            else:
                device_types[device_type] = 1
        
        # 方案概述
        overview = f"该网络由{device_count}台设备组成，包含{connection_count}个连接。"
        if device_types:
            device_summary = "，".join([f"{count}台{type_}" for type_, count in device_types.items()])
            overview += f"设备组成：{device_summary}。"
        
        self.parsed_result_text.insert(tk.END, overview + "\n\n")
        
        # 添加网络架构评估
        if device_count > 0:
            # 判断网络类型和复杂度
            if device_count <= 3:
                arch_type = "小型网络"
                if "USG6000" in str(device_types):
                    arch_type = "小型安全网络"
            elif device_count <= 10:
                arch_type = "中型网络"
                if "CE6850" in str(device_types) or "CE6800" in str(device_types):
                    arch_type = "中型园区网络"
            else:
                arch_type = "大型网络"
                if "CE12800" in str(device_types):
                    arch_type = "大型企业网络"
            
            architecture = f"网络架构：这是一个{arch_type}方案。"
            
            # 网络架构特点
            has_router = any(d.get("type", "").startswith(("AR", "USG")) for d in data.get("devices", []))
            has_core_switch = any(d.get("type", "").startswith("CE") for d in data.get("devices", []))
            has_access_switch = any(d.get("type", "").startswith("S5") for d in data.get("devices", []))
            
            if has_router and has_core_switch and has_access_switch:
                architecture += "采用了三层网络架构（核心层、汇聚层、接入层），适合企业网络部署。"
            elif has_router and has_access_switch:
                architecture += "采用了两层网络架构（核心层、接入层），适合中小型网络部署。"
            elif has_router:
                architecture += "以路由器为中心的网络架构，适合小型办公环境。"
            else:
                architecture += "基于交换的扁平化网络结构，适合简单场景。"
                
            self.parsed_result_text.insert(tk.END, architecture + "\n\n")
            
            # 添加网络建议
            recommendations = "建议与优化：\n"
            
            # 针对不同类型网络的建议
            if has_router and not any("OSPF" in str(data) for _ in range(1)):
                recommendations += "1. 考虑配置OSPF动态路由协议，提高路由灵活性。\n"
            
            if has_core_switch and not any("VLAN" in str(data) for _ in range(1)):
                recommendations += "2. 建议划分VLAN以隔离广播域并提高安全性。\n"
                
            if device_count > 3 and not any("备份" in str(data) for _ in range(1)):
                recommendations += "3. 建议配置设备配置备份策略。\n"
                
            if not any("安全" in str(data) for _ in range(1)) and has_router:
                recommendations += "4. 考虑添加基本ACL访问控制策略增强安全性。\n"
                
            if len(recommendations.split("\n")) <= 2:  # 只有标题行
                recommendations += "• 当前网络拓扑结构合理，无特别优化建议。\n"
                
            self.parsed_result_text.insert(tk.END, recommendations + "\n")
            
            # 添加推荐配置命令
            self.parsed_result_text.insert(tk.END, "推荐配置命令：\n")
            
            # 为不同设备生成配置命令
            for i, device in enumerate(data.get("devices", []), 1):
                device_name = device.get("name", f"Device{i}")
                device_type = device.get("type", "")
                
                self.parsed_result_text.insert(tk.END, f"【{device_name}配置】\n")
                commands = []
                
                # 基本配置命令
                commands.append("system-view")
                commands.append(f"sysname {device_name}")
                
                # 根据设备类型添加特定配置
                if device_type.startswith(("AR", "USG")):  # 路由器配置
                    # 接口配置
                    interfaces = []
                    for conn in data.get("connections", []):
                        if device_name in conn.get("from", ""):
                            interface = conn.get("from", "").split(":")[1]
                            if interface not in interfaces:
                                interfaces.append(interface)
                        if device_name in conn.get("to", ""):
                            interface = conn.get("to", "").split(":")[1]
                            if interface not in interfaces:
                                interfaces.append(interface)
                    
                    # 生成接口配置
                    for idx, iface in enumerate(interfaces):
                        commands.append(f"interface {iface}")
                        commands.append(f"ip address 192.168.{i}.{idx+1} 255.255.255.0")
                        commands.append("undo shutdown")
                        commands.append("quit")
                    
                    # 如果有路由器，添加OSPF配置
                    if has_router and len(data.get("devices", [])) > 1:
                        commands.append("ospf 1")
                        commands.append("area 0")
                        for idx in range(len(interfaces)):
                            commands.append(f"network 192.168.{i}.0 0.0.0.255")
                        commands.append("quit")
                    
                    # 添加ACL配置
                    commands.append("acl 3000")
                    commands.append("rule 5 permit ip source 192.168.0.0 0.0.255.255")
                    commands.append("rule 10 deny ip")
                    commands.append("quit")
                
                elif device_type.startswith(("S5", "CE")):  # 交换机配置
                    # VLAN配置
                    if has_core_switch:
                        commands.append("vlan batch 10 20 30")
                        
                        # 接口配置
                        interfaces = []
                        for conn in data.get("connections", []):
                            if device_name in conn.get("from", ""):
                                interface = conn.get("from", "").split(":")[1]
                                if interface not in interfaces:
                                    interfaces.append(interface)
                            if device_name in conn.get("to", ""):
                                interface = conn.get("to", "").split(":")[1]
                                if interface not in interfaces:
                                    interfaces.append(interface)
                        
                        # 生成接口配置
                        for idx, iface in enumerate(interfaces):
                            commands.append(f"interface {iface}")
                            if idx == 0 and has_router:  # 连接路由器的端口设为trunk
                                commands.append("port link-type trunk")
                                commands.append("port trunk allow-pass vlan all")
                            else:  # 其他端口设为access
                                commands.append("port link-type access")
                                commands.append(f"port default vlan {10 + (idx % 3) * 10}")
                            commands.append("quit")
                        
                        # 如果是核心交换机，添加STP配置
                        if device_type.startswith("CE"):
                            commands.append("stp mode rstp")
                            commands.append("stp enable")
                            # 如果是第一台核心交换机，设为根桥
                            if i == 1 or device_name.lower().startswith(("core", "核心")):
                                commands.append("stp root primary")
                
                # 添加SSH配置
                commands.append("stelnet server enable")
                commands.append("ssh user admin authentication-type password")
                commands.append("ssh user admin service-type stelnet")
                commands.append("aaa")
                commands.append("local-user admin password cipher huawei@123")
                commands.append("local-user admin service-type ssh")
                commands.append("local-user admin privilege level 15")
                commands.append("quit")
                commands.append("user-interface vty 0 4")
                commands.append("authentication-mode aaa")
                commands.append("protocol inbound ssh")
                commands.append("quit")
                
                # 保存配置
                commands.append("return")
                commands.append("save")
                commands.append("y")
                
                # 显示命令
                for cmd in commands:
                    self.parsed_result_text.insert(tk.END, f"{cmd}\n")
                self.parsed_result_text.insert(tk.END, "\n")
        
        # 设备描述
        self.parsed_result_text.insert(tk.END, "设备列表：\n")
        if "devices" in data and data["devices"]:
            for i, device in enumerate(data["devices"], 1):
                device_info = f"{i}. {device['name']} ({device['type']})"
                
                # 添加IP信息(如果有)
                ip_info = ""
                for iface in device.get("interfaces", []):
                    if iface.get("ip"):
                        ip_info = f" - IP: {iface.get('ip')}/{iface.get('mask', '24')}"
                        break
                
                self.parsed_result_text.insert(tk.END, f"{device_info}{ip_info}\n")
        else:
            self.parsed_result_text.insert(tk.END, "  未检测到设备\n")
        
        # 连接描述
        self.parsed_result_text.insert(tk.END, "\n连接关系：\n")
        if "connections" in data and data["connections"]:
            for i, conn in enumerate(data["connections"], 1):
                from_parts = conn["from"].split(":")
                to_parts = conn["to"].split(":")
                bandwidth = conn.get("bandwidth", "未指定")
                
                conn_info = f"{i}. {from_parts[0]}的{from_parts[1]}接口 → {to_parts[0]}的{to_parts[1]}接口"
                if bandwidth:
                    conn_info += f" (带宽: {bandwidth})"
                
                self.parsed_result_text.insert(tk.END, f"{conn_info}\n")
        else:
            self.parsed_result_text.insert(tk.END, "  未检测到连接关系\n")
        
        # 添加分隔线
        self.parsed_result_text.insert(tk.END, "\n" + "-" * 50 + "\n\n")
        
        # 添加原始JSON数据
        self.parsed_result_text.insert(tk.END, "【原始JSON数据】\n\n")
        formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
        self.parsed_result_text.insert(tk.END, formatted_json)
        
        # 再次设为只读
        self.parsed_result_text.config(state=tk.DISABLED)
        
        # 保存解析结果，以便后续生成拓扑使用
        self.parsed_topology_data = data
    
    def _update_parsing_status(self, message, is_error=False):
        """更新解析状态信息"""
        # 在预览区添加状态信息
        self.parsed_result_text.config(state=tk.NORMAL)
        if is_error:
            self.parsed_result_text.insert(tk.END, f"错误: {message}\n")
            self.parsed_result_text.config(state=tk.DISABLED)
            messagebox.showerror("错误", message)
        else:
            self.parsed_result_text.insert(tk.END, f"{message}\n")
            self.parsed_result_text.see(tk.END)
            self.parsed_result_text.update_idletasks()

    def show_troubleshooting(self):
        """显示故障排除指南"""
        # 创建帮助窗口
        help_window = tk.Toplevel(self.root)
        help_window.title("eNSP自动化工具 - 故障排除指南")
        help_window.geometry("800x600")
        help_window.resizable(True, True)
        
        # 创建笔记本组件
        help_notebook = ttk.Notebook(help_window)
        help_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # TOPO文件问题
        topo_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(topo_frame, text="TOPO文件问题")
        
        topo_text = scrolledtext.ScrolledText(topo_frame, wrap=tk.WORD)
        topo_text.pack(fill=tk.BOTH, expand=True)
        
        topo_guide = """
TOPO文件问题排查

如果TOPO文件导入eNSP后无设备显示或报错，请尝试以下步骤：

1. 文件格式问题
   - 确保生成的.topo文件是XML格式
   - 检查文件是否可以用文本编辑器打开查看

2. 设备未显示
   - 检查生成的TOPO文件中是否包含<device>元素
   - 确保设备有正确的位置属性，否则可能在视图外

3. eNSP版本兼容
   - 不同版本的eNSP可能有不同的TOPO文件格式要求
   - 尝试更新到最新版本的eNSP

4. 手动修复步骤
   a. 打开eNSP，创建一个包含相同设备的拓扑
   b. 保存该拓扑，查看其XML结构
   c. 比较自动生成的文件与eNSP创建的文件的区别

5. 替代方案
   - 如果TOPO文件导入失败，可以使用GUI界面中的设备列表
   - 手动在eNSP中创建相同设备，并按图示连接
"""
        topo_text.insert(tk.END, topo_guide)
        topo_text.config(state=tk.DISABLED)
        
        # 设备连接问题
        connection_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(connection_frame, text="设备连接问题")
        
        connection_text = scrolledtext.ScrolledText(connection_frame, wrap=tk.WORD)
        connection_text.pack(fill=tk.BOTH, expand=True)
        
        connection_guide = """
设备连接问题排查

如果无法连接到eNSP中的设备，请检查以下事项：

1. 设备启动状态
   - 确保设备在eNSP中已完全启动(绿色图标)
   - 启动完成后等待约30秒让系统服务完全启动

2. SSH服务配置
   - 默认情况下，eNSP中的设备没有开启SSH服务
   - 需要通过Console连接到设备，手动配置SSH：
     
     system-view
     stelnet server enable
     ssh user admin authentication-type password
     ssh user admin service-type stelnet
     aaa
     local-user admin password cipher Admin@123
     local-user admin service-type ssh
     local-user admin privilege level 15
     quit
     user-interface vty 0 4
     authentication-mode aaa
     protocol inbound ssh
     quit
     save

3. IP地址检查
   - 确认设备的IP地址配置正确
   - 可通过Console登录后使用"display ip interface brief"查看
   - 确保PC与设备网络可互通

4. 防火墙和安全软件
   - 检查本机防火墙是否阻止了SSH连接
   - 暂时关闭防病毒软件的网络防护功能
   
5. eNSP网络隔离
   - eNSP默认将虚拟网络与实际网络隔离
   - 检查eNSP的"工具 -> 选项 -> 高级"中的网络设置

6. 诊断命令
   - 在PC上使用ping测试网络连通性: ping 192.168.1.x
   - 使用telnet测试SSH端口: telnet 192.168.1.x 22
"""
        connection_text.insert(tk.END, connection_guide)
        connection_text.config(state=tk.DISABLED)
        
        # 网络拓扑问题
        topology_frame = ttk.Frame(help_notebook, padding=10)
        help_notebook.add(topology_frame, text="网络拓扑问题")
        
        topology_text = scrolledtext.ScrolledText(topology_frame, wrap=tk.WORD)
        topology_text.pack(fill=tk.BOTH, expand=True)
        
        topology_guide = """
网络拓扑问题排查

创建和管理网络拓扑时的常见问题及解决方案：

1. 设备类型兼容性
   - 确保选择的设备类型在eNSP中可用
   - 常用设备类型: AR2220, S5700, USG6000
   
2. 连接限制
   - 注意设备接口的连接限制和兼容性
   - 确保连接的两端接口类型兼容(如以太网到以太网)
   
3. 复杂拓扑生成
   - 对于复杂拓扑，先创建简单版本测试
   - 逐步添加设备和连接，确保每步都能正常工作
   
4. NLP生成的拓扑问题
   - 自动生成的拓扑可能需要手动调整
   - 检查NLP解析的设备和连接是否符合实际需求
   - 本地规则解析模式可能对复杂描述支持有限
   
5. 自定义设备配置
   - 生成的设备配置可能需要根据具体需求修改
   - 可以在设备连接后发送自定义配置命令
   
6. 常见设备错误
   - "端口冲突": 检查是否有多个连接使用同一接口
   - "设备类型不支持": 尝试使用eNSP支持的设备型号
   - "连接不兼容": 检查连接两端的接口类型是否匹配
"""
        topology_text.insert(tk.END, topology_guide)
        topology_text.config(state=tk.DISABLED)
        
        # 关闭按钮
        ttk.Button(help_window, text="关闭", command=help_window.destroy).pack(pady=10)

    def add_command(self):
        """添加命令到命令列表"""
        # 创建添加命令对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("添加命令")
        dialog.geometry("500x400")
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 命令类别
        ttk.Label(dialog, text="选择命令类别:").pack(anchor=tk.W, padx=10, pady=5)
        
        # 命令分类
        categories = [
            "基本命令", "VLAN配置", "接口配置", "路由配置", "DHCP配置", 
            "ACL配置", "SSH配置", "OSPF配置", "STP配置", "自定义命令"
        ]
        
        category_var = tk.StringVar(value=categories[0])
        category_combo = ttk.Combobox(dialog, textvariable=category_var, values=categories, width=20)
        category_combo.pack(fill=tk.X, padx=10, pady=5)
        
        # 命令选择框架
        command_select_frame = ttk.LabelFrame(dialog, text="选择命令", padding=5)
        command_select_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 命令选择列表
        command_select_listbox = tk.Listbox(command_select_frame, width=50, height=10)
        command_select_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 命令选择滚动条
        select_scrollbar = ttk.Scrollbar(command_select_frame, orient=tk.VERTICAL, command=command_select_listbox.yview)
        select_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        command_select_listbox.config(yscrollcommand=select_scrollbar.set)
        
        # 命令预览
        ttk.Label(dialog, text="命令预览:").pack(anchor=tk.W, padx=10, pady=5)
        preview_var = tk.StringVar()
        preview_entry = ttk.Entry(dialog, textvariable=preview_var, width=50)
        preview_entry.pack(fill=tk.X, padx=10, pady=5)
        
        # 更新命令列表的函数
        def update_commands(*args):
            command_select_listbox.delete(0, tk.END)
            category = category_var.get()
            
            # 根据类别填充命令
            commands = {
                "基本命令": [
                    "system-view", "quit", "return", "save", "undo", "sysname 设备名称"
                ],
                "VLAN配置": [
                    "vlan 10", "vlan batch 10 20 30", "name VLAN名称"
                ],
                "接口配置": [
                    "interface GigabitEthernet0/0/1", 
                    "port link-type access", 
                    "port default vlan 10",
                    "port link-type trunk",
                    "port trunk allow-pass vlan 10",
                    "port trunk allow-pass vlan all",
                    "ip address 192.168.1.1 255.255.255.0",
                    "shutdown",
                    "undo shutdown"
                ],
                "路由配置": [
                    "ip route-static 192.168.1.0 255.255.255.0 192.168.2.1",
                    "ip route-static 0.0.0.0 0.0.0.0 192.168.1.1"
                ],
                "DHCP配置": [
                    "dhcp enable",
                    "ip pool 池名称",
                    "network 192.168.1.0 mask 255.255.255.0",
                    "gateway-list 192.168.1.1",
                    "dns-list 8.8.8.8"
                ],
                "ACL配置": [
                    "acl 2000",
                    "rule 5 permit source 192.168.1.0 0.0.0.255",
                    "rule 10 deny"
                ],
                "SSH配置": [
                    "stelnet server enable",
                    "ssh user admin authentication-type password",
                    "ssh user admin service-type stelnet",
                    "aaa",
                    "local-user admin password cipher huawei@123",
                    "local-user admin service-type ssh",
                    "local-user admin privilege level 15",
                    "user-interface vty 0 4",
                    "authentication-mode aaa",
                    "protocol inbound ssh"
                ],
                "OSPF配置": [
                    "ospf 1",
                    "area 0",
                    "network 192.168.1.0 0.0.0.255"
                ],
                "STP配置": [
                    "stp enable",
                    "stp mode rstp",
                    "stp root primary"
                ],
                "自定义命令": []
            }
            
            # 添加命令到列表
            if category in commands:
                for cmd in commands[category]:
                    command_select_listbox.insert(tk.END, cmd)
        
        # 绑定类别变化事件
        category_combo.bind("<<ComboboxSelected>>", update_commands)
        
        # 选择命令时更新预览
        def on_command_select(event):
            selection = command_select_listbox.curselection()
            if selection:
                selected_command = command_select_listbox.get(selection[0])
                preview_var.set(selected_command)
        
        command_select_listbox.bind("<<ListboxSelect>>", on_command_select)
        
        # 自定义命令输入
        custom_frame = ttk.LabelFrame(dialog, text="自定义命令", padding=5)
        custom_frame.pack(fill=tk.X, padx=10, pady=5)
        
        custom_var = tk.StringVar()
        custom_entry = ttk.Entry(custom_frame, textvariable=custom_var, width=50)
        custom_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        def apply_custom():
            custom_cmd = custom_var.get().strip()
            if custom_cmd:
                preview_var.set(custom_cmd)
        
        ttk.Button(custom_frame, text="应用", command=apply_custom).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 功能按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        def on_add():
            command = preview_var.get().strip()
            if command:
                self.command_listbox.insert(tk.END, command)
                preview_var.set("")
        
        def on_ok():
            command = preview_var.get().strip()
            if command:
                self.command_listbox.insert(tk.END, command)
            dialog.destroy()
        
        ttk.Button(buttons_frame, text="添加并继续", command=on_add).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="完成", command=on_ok).pack(side=tk.RIGHT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=10)
        
        # 初始化命令列表
        update_commands()
    
    def delete_command(self):
        """从命令列表中删除命令"""
        selection = self.command_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要删除的命令")
            return
        
        # 删除选中的命令
        self.command_listbox.delete(selection[0])
    
    def execute_commands(self):
        """执行命令列表中的命令"""
        # 获取选中的设备
        selection = self.connected_devices_listbox.curselection()
        if not selection:
            messagebox.showinfo("提示", "请先选择要配置的设备")
            return
        
        # 获取设备IP
        device_ip = self.connected_devices_listbox.get(selection[0])
        
        # 获取命令列表
        commands = []
        for i in range(self.command_listbox.size()):
            command = self.command_listbox.get(i)
            commands.append(command)
        
        if not commands:
            messagebox.showinfo("提示", "命令列表为空，请先添加命令")
            return
        
        # 确认执行
        if not messagebox.askyesno("确认", f"确定要在设备 {device_ip} 上执行这些命令吗?\n\n" + "\n".join(commands)):
            return
        
        # 执行命令
        try:
            self.log(f"正在向设备 {device_ip} 发送命令...")
            
            # 执行命令
            output = self.device_config.configure_device(device_ip, commands)
            
            if output:
                self.log(f"命令执行成功，输出:\n{output}\n")
                messagebox.showinfo("成功", f"命令已成功发送到设备 {device_ip}")
            else:
                self.log(f"执行命令失败")
                messagebox.showerror("错误", f"向设备 {device_ip} 发送命令失败")
        
        except Exception as e:
            self.log(f"发送命令时出错: {str(e)}")
            messagebox.showerror("错误", f"发送命令时出错: {str(e)}")
    
    def clear_command_list(self):
        """清空命令列表"""
        if messagebox.askyesno("确认", "确定要清空命令列表吗?"):
            self.command_listbox.delete(0, tk.END)
    
    def open_command_library(self):
        """打开命令库"""
        dialog = tk.Toplevel(self.root)
        dialog.title("命令库")
        dialog.geometry("800x600")
        dialog.resizable(True, True)
        
        # 创建笔记本控件
        notebook = ttk.Notebook(dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 从文件中加载命令库
        command_library = {
            "基本命令": [],
            "VLAN配置": [],
            "接口配置": [],
            "路由配置": [],
            "DHCP配置": [],
            "ACL配置": [],
            "SSH配置": [],
            "OSPF配置": [],
            "STP配置": []
        }
        
        # 解析命令文件内容
        try:
            with open("command_library.txt", "r", encoding="utf-8") as f:
                content = f.read()
                sections = content.split("###")
                
                current_section = "基本命令"
                for line in content.splitlines():
                    if line.startswith("###"):
                        # 新节点开始
                        current_section = line.strip("#").strip()
                        if current_section not in command_library:
                            command_library[current_section] = []
                    elif line.strip() and not line.startswith("#"):
                        # 添加命令到当前节点
                        if current_section in command_library:
                            command_library[current_section].append(line.strip())
        except FileNotFoundError:
            # 从我们提供的文件中提取命令
            # 尝试加载您提供的命令文件
            try:
                with open("c:\\Users\\Lenovo\\Desktop\\命令.txt", "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    # 简单解析命令模块
                    current_section = "基本命令"
                    for line in content.splitlines():
                        if "、" in line and "命令" in line:
                            # 可能是新章节
                            section_match = line.split("、")
                            if len(section_match) > 1:
                                section_name = section_match[1].split("（")[0].strip()
                                if "命令" in section_name:
                                    current_section = section_name
                                    if current_section not in command_library:
                                        command_library[current_section] = []
                        
                        # 查找示例命令（以 [ 开头的行）
                        elif line.strip().startswith("[") and "]" in line:
                            cmd_parts = line.split("]")
                            if len(cmd_parts) > 1:
                                cmd = cmd_parts[1].strip()
                                if cmd and not cmd.startswith("//") and not cmd.startswith("#"):
                                    command_library[current_section].append(cmd)
                
                # 保存解析后的命令库文件
                with open("command_library.txt", "w", encoding="utf-8") as f:
                    for section, commands in command_library.items():
                        f.write(f"### {section}\n")
                        for cmd in commands:
                            f.write(f"{cmd}\n")
                        f.write("\n")
            
            except Exception as e:
                self.log(f"加载命令库失败: {str(e)}")
        
        # 创建命令库选项卡
        for category, commands in command_library.items():
            if not commands:
                continue
                
            # 创建分类选项卡
            tab = ttk.Frame(notebook, padding=5)
            notebook.add(tab, text=category)
            
            # 命令列表
            cmd_listbox = tk.Listbox(tab, width=80, height=20)
            cmd_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # 滚动条
            scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=cmd_listbox.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            cmd_listbox.config(yscrollcommand=scrollbar.set)
            
            # 添加命令到列表
            for cmd in commands:
                cmd_listbox.insert(tk.END, cmd)
            
            # 添加使用按钮
            def create_use_command(cmd_list):
                def use_command():
                    selection = cmd_list.curselection()
                    if selection:
                        selected_cmd = cmd_list.get(selection[0])
                        self.command_listbox.insert(tk.END, selected_cmd)
                        messagebox.showinfo("提示", f"已添加命令: {selected_cmd}", parent=dialog)
                return use_command
            
            button_frame = ttk.Frame(tab)
            button_frame.pack(fill=tk.X, pady=10)
            
            ttk.Button(button_frame, text="添加到命令列表", 
                    command=create_use_command(cmd_listbox)).pack(side=tk.LEFT, padx=10)
            
            # 添加双击事件
            cmd_listbox.bind("<Double-1>", lambda e, lb=cmd_listbox: self.add_command_from_library(lb))
        
        # 添加搜索功能
        search_frame = ttk.LabelFrame(dialog, text="搜索命令", padding=5)
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=5)
        
        # 搜索结果列表
        result_frame = ttk.LabelFrame(dialog, text="搜索结果", padding=5)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        result_listbox = tk.Listbox(result_frame, width=80, height=10)
        result_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        result_scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=result_listbox.yview)
        result_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        result_listbox.config(yscrollcommand=result_scrollbar.set)
        
        # 搜索函数
        def search_commands():
            search_text = search_var.get().strip().lower()
            if not search_text:
                return
                
            result_listbox.delete(0, tk.END)
            
            for category, commands in command_library.items():
                for cmd in commands:
                    if search_text in cmd.lower():
                        result_listbox.insert(tk.END, f"{category}: {cmd}")
        
        ttk.Button(search_frame, text="搜索", command=search_commands).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # 添加从搜索结果添加命令的功能
        def add_from_search():
            selection = result_listbox.curselection()
            if selection:
                result = result_listbox.get(selection[0])
                cmd = result.split(": ", 1)[1] if ": " in result else result
                self.command_listbox.insert(tk.END, cmd)
                messagebox.showinfo("提示", f"已添加命令: {cmd}", parent=dialog)
        
        ttk.Button(result_frame, text="添加到命令列表", 
                command=add_from_search).pack(side=tk.LEFT, padx=10, pady=5)
        
        # 添加双击事件
        result_listbox.bind("<Double-1>", lambda e: add_from_search())
        
        # 底部按钮
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(button_frame, text="关闭", 
                command=dialog.destroy).pack(side=tk.RIGHT, padx=10)
    
    def add_command_from_library(self, listbox):
        """从命令库中添加命令到命令列表"""
        selection = listbox.curselection()
        if selection:
            selected_cmd = listbox.get(selection[0])
            self.command_listbox.insert(tk.END, selected_cmd)

    def add_command_templates(self):
        """添加预设命令模板组"""
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("常用命令模板组")
        dialog.geometry("550x400")
        dialog.resizable(True, True)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 创建模板列表
        templates_frame = ttk.LabelFrame(dialog, text="选择模板", padding=5)
        templates_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 定义常用命令模板组
        command_templates = {
            "VLAN配置模板": [
                "system-view",
                "vlan 30",
                "quit",
                "interface GigabitEthernet0/0/3",
                "port link-type access",
                "port default vlan 30",
                "quit",
                "return"
            ],
            "SSH配置模板": [
                "system-view",
                "stelnet server enable",
                "ssh user admin authentication-type password",
                "ssh user admin service-type stelnet",
                "aaa",
                "local-user admin password cipher huawei@123",
                "local-user admin service-type ssh",
                "local-user admin privilege level 15",
                "quit",
                "user-interface vty 0 4",
                "authentication-mode aaa",
                "protocol inbound ssh",
                "quit",
                "return"
            ],
            "OSPF配置模板": [
                "system-view",
                "ospf 1",
                "area 0",
                "network 192.168.1.0 0.0.0.255",
                "quit",
                "quit",
                "return"
            ],
            "ACL基础配置模板": [
                "system-view",
                "acl 3000",
                "rule 5 permit ip source 192.168.1.0 0.0.0.255",
                "rule 10 deny ip",
                "quit",
                "return"
            ],
            "接口IP配置模板": [
                "system-view",
                "interface GigabitEthernet0/0/1",
                "ip address 192.168.1.1 255.255.255.0",
                "undo shutdown",
                "quit",
                "return"
            ],
            "DHCP服务器配置模板": [
                "system-view",
                "dhcp enable",
                "ip pool HUAWEI",
                "network 192.168.1.0 mask 255.255.255.0",
                "gateway-list 192.168.1.1",
                "dns-list 8.8.8.8",
                "quit",
                "interface GigabitEthernet0/0/1",
                "dhcp select global",
                "quit",
                "return"
            ],
            "DHCP接口模式配置模板": [
                "system-view",
                "dhcp enable",
                "interface GigabitEthernet0/0/1",
                "ip address 192.168.1.1 255.255.255.0",
                "dhcp select interface",
                "dhcp server excluded-ip-address 192.168.1.1 192.168.1.10",
                "dhcp server dns-list 8.8.8.8",
                "quit",
                "return"
            ],
            "静态路由配置模板": [
                "system-view",
                "ip route-static 192.168.2.0 255.255.255.0 192.168.1.2",
                "ip route-static 0.0.0.0 0.0.0.0 192.168.1.254",
                "quit",
                "return"
            ]
        }
        
        # 添加模板列表
        listbox = tk.Listbox(templates_frame, width=40, height=15)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(templates_frame, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)
        
        # 填充模板列表
        for template_name in command_templates.keys():
            listbox.insert(tk.END, template_name)
        
        # 预览区域
        preview_frame = ttk.LabelFrame(dialog, text="命令预览", padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        preview_text = scrolledtext.ScrolledText(preview_frame, width=50, height=10, wrap=tk.WORD)
        preview_text.pack(fill=tk.BOTH, expand=True)
        
        # 显示选中模板的命令
        def show_template(event):
            selection = listbox.curselection()
            if selection:
                template_name = listbox.get(selection[0])
                preview_text.delete("1.0", tk.END)
                for cmd in command_templates[template_name]:
                    preview_text.insert(tk.END, cmd + "\n")
        
        listbox.bind("<<ListboxSelect>>", show_template)
        
        # 功能按钮
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)
        
        def add_template():
            selection = listbox.curselection()
            if not selection:
                messagebox.showinfo("提示", "请选择一个命令模板", parent=dialog)
                return
            
            template_name = listbox.get(selection[0])
            cmds = command_templates[template_name]
            
            # 添加所有命令到列表
            for cmd in cmds:
                self.command_listbox.insert(tk.END, cmd)
            
            messagebox.showinfo("成功", f"已添加 {template_name} 的所有命令", parent=dialog)
            dialog.destroy()
        
        ttk.Button(buttons_frame, text="添加到命令列表", command=add_template).pack(side=tk.LEFT, padx=10)
        ttk.Button(buttons_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=10)
        
        # 添加模板编辑功能
        def edit_template():
            selection = listbox.curselection()
            if not selection:
                messagebox.showinfo("提示", "请选择一个命令模板", parent=dialog)
                return
                
            template_name = listbox.get(selection[0])
            
            # 创建编辑对话框
            edit_dialog = tk.Toplevel(dialog)
            edit_dialog.title(f"编辑模板 - {template_name}")
            edit_dialog.geometry("500x400")
            edit_dialog.resizable(True, True)
            edit_dialog.transient(dialog)
            edit_dialog.grab_set()
            
            # 命令编辑区
            ttk.Label(edit_dialog, text="编辑命令:").pack(anchor=tk.W, padx=10, pady=5)
            
            edit_text = scrolledtext.ScrolledText(edit_dialog, width=50, height=15, wrap=tk.WORD)
            edit_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            # 填充当前命令
            for cmd in command_templates[template_name]:
                edit_text.insert(tk.END, cmd + "\n")
            
            # 按钮
            edit_buttons_frame = ttk.Frame(edit_dialog)
            edit_buttons_frame.pack(fill=tk.X, padx=10, pady=10)
            
            def save_edits():
                # 获取编辑后的命令
                new_commands = []
                for line in edit_text.get("1.0", tk.END).splitlines():
                    if line.strip():
                        new_commands.append(line.strip())
                
                # 更新模板
                command_templates[template_name] = new_commands
                
                # 更新预览
                if listbox.curselection():
                    preview_text.delete("1.0", tk.END)
                    for cmd in new_commands:
                        preview_text.insert(tk.END, cmd + "\n")
                
                messagebox.showinfo("成功", f"模板 {template_name} 已更新", parent=edit_dialog)
                edit_dialog.destroy()
            
            ttk.Button(edit_buttons_frame, text="保存更改", command=save_edits).pack(side=tk.RIGHT, padx=10)
            ttk.Button(edit_buttons_frame, text="取消", command=edit_dialog.destroy).pack(side=tk.RIGHT, padx=10)
        
        ttk.Button(buttons_frame, text="编辑模板", command=edit_template).pack(side=tk.LEFT, padx=10)

    def _run_test_connection(self, model_code, status_var, status_label):
        """测试API连接的辅助函数（运行在线程中）"""
        try:
            # 测试连接
            result = self.nlp_generator.test_api_connection(model_code)
            
            # 在主线程中更新UI
            if result["success"]:
                self.root.after(0, lambda: status_var.set(f"成功: {result['message']}"))
                self.root.after(0, lambda: status_label.config(foreground="green"))
            else:
                self.root.after(0, lambda: status_var.set(f"失败: {result['message']}"))
                self.root.after(0, lambda: status_label.config(foreground="red"))
        except Exception as e:
            self.root.after(0, lambda: status_var.set(f"错误: {str(e)}"))
            self.root.after(0, lambda: status_label.config(foreground="red"))

# 主函数
def main():
    """主程序入口"""
    try:
        # 创建GUI对象
        app = ENSPAutomationGUI()
        # 显示欢迎窗口
        # app.show_splash_screen()  # 移除此行以避免重复显示欢迎窗口
        # 开始主循环
        app.root.mainloop()
    except Exception as e:
        print(f"程序运行出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()