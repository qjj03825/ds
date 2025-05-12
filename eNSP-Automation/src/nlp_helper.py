#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
NLP辅助模块：将自然语言描述转换为网络拓扑配置
支持多种模式：
1. 本地规则解析（无需API）
2. OpenAI API（需要密钥）
3. DeepSeek API（需要密钥）
4. 讯飞星火（需要密钥）
"""

import re
import json
import os
import logging
import requests
import time
import base64
import hmac
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NLPTopologyGenerator:
    """自然语言处理网络拓扑生成器"""
    
    def __init__(self):
        """初始化NLP拓扑生成器"""
        self.model_type = "local"  # 默认使用本地规则解析
        self.api_key = ""
        self.api_url = ""
        self.api_secret = ""  # 用于讯飞星火等需要密钥对的API
        self.api_app_id = ""  # 用于讯飞星火等需要应用ID的API
        self.config_file = Path.cwd() / "configs" / "nlp_config.json"
        
        # 加载配置
        self.load_config()
        
        # 本地解析的关键词和模式
        self.device_keywords = {
            "路由器": "AR2220",
            "交换机": "S5700",
            "核心交换机": "S5700",
            "汇聚交换机": "S5700",
            "接入交换机": "S5700",
            "防火墙": "USG6000"
        }
        
        self.connection_patterns = [
            # 连接模式1：设备A连接到设备B
            r"(\w+)[连接到|连接|链接到|链接|连通|通过](\w+)",
            # 连接模式2：设备A与设备B相连
            r"(\w+)[与|和|同](\w+)[相连|互联|相互连接]",
            # 连接模式3：设备A的端口X连接到设备B的端口Y
            r"(\w+)的?(接口|端口|interface|port)(\w+)[连接到|连接|链接到|链接](\w+)的?(接口|端口|interface|port)(\w+)"
        ]
        
        self.network_patterns = [
            # IP分配模式
            r"(\w+)(的)?(IP地址|地址)[为|是|设为|设置为|配置为]([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})",
            # VLAN模式
            r"(创建|配置|划分|设置)VLAN[^\d]*(\d+(?:\s*[,，、]\s*\d+)*)",
            # 网段模式
            r"网段[为|是]([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/\d{1,2})"
        ]
    
    def load_config(self):
        """加载NLP配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.model_type = config.get("model_type", "local")
                self.api_key = config.get("api_key", "")
                self.api_url = config.get("api_url", "")
                self.api_secret = config.get("api_secret", "")
                self.api_app_id = config.get("api_app_id", "")
                logger.info(f"已加载NLP配置，使用模型类型: {self.model_type}")
            except Exception as e:
                logger.error(f"加载NLP配置失败: {str(e)}")
        
    def save_config(self):
        """保存NLP配置"""
        try:
            config_dir = Path(self.config_file).parent
            config_dir.mkdir(exist_ok=True)
            
            config = {
                "model_type": self.model_type,
                "api_key": self.api_key,
                "api_url": self.api_url,
                "api_secret": self.api_secret,
                "api_app_id": self.api_app_id
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            logger.info("已保存NLP配置")
            return True
        except Exception as e:
            logger.error(f"保存NLP配置失败: {str(e)}")
            return False
    
    def parse_network_description(self, description: str, model_type: Optional[str] = None) -> Dict[str, Any]:
        """
        解析网络描述，生成拓扑数据
        
        Args:
            description: 自然语言网络描述
            model_type: 模型类型，可选 "local", "openai", "deepseek", "xunfei"
            
        Returns:
            拓扑数据字典，包含devices和connections
        """
        # 使用指定模型类型或默认模型类型
        model = model_type or self.model_type
        
        # 根据模型类型选择不同的解析方法
        if model == "local":
            return self._parse_local(description)
        elif model == "openai":
            return self._parse_with_openai(description)
        elif model == "deepseek":
            return self._parse_with_deepseek(description)
        elif model == "xunfei":
            return self._parse_with_xunfei(description)
        else:
            logger.warning(f"未知的模型类型: {model}，使用本地规则解析")
            return self._parse_local(description)
    
    def _parse_local(self, description: str) -> Dict[str, Any]:
        """使用本地规则解析网络描述"""
        # 基本拓扑数据结构
        topology_data = {
            "devices": [],
            "connections": []
        }
        
        # 提取设备信息
        device_matches = []
        for keyword, device_type in self.device_keywords.items():
            matches = re.finditer(f"(\\d+个|[一二三四五六七八九十]+个)?({keyword})(\\d+|[一二三四五六七八九十]+)?", description)
            for match in matches:
                count_prefix = match.group(1) or ""
                count_prefix = count_prefix.replace("个", "")
                device_name_suffix = match.group(3) or ""
                
                # 处理中文数字
                cn_nums = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, 
                          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
                
                count = 1
                if count_prefix in cn_nums:
                    count = cn_nums[count_prefix]
                elif count_prefix.isdigit():
                    count = int(count_prefix)
                
                # 生成设备
                for i in range(1, count + 1):
                    if device_name_suffix:
                        device_name = f"{keyword}{device_name_suffix}"
                    else:
                        device_name = f"{keyword}{i}"
                    
                    # 添加设备
                    topology_data["devices"].append({
                        "name": device_name,
                        "type": device_type,
                        "management_ip": f"192.168.1.{len(topology_data['devices']) + 1}",
                        "subnet_mask": "255.255.255.0"
                    })
        
        # 提取连接信息
        for pattern in self.connection_patterns:
            matches = re.finditer(pattern, description)
            for match in matches:
                groups = match.groups()
                if len(groups) >= 2:
                    from_device = groups[0]
                    to_device = groups[1]
                    
                    # 查找设备
                    from_device_index = next((i for i, d in enumerate(topology_data["devices"]) 
                                            if from_device in d["name"]), None)
                    to_device_index = next((i for i, d in enumerate(topology_data["devices"]) 
                                          if to_device in d["name"]), None)
                    
                    if from_device_index is not None and to_device_index is not None:
                        from_device_obj = topology_data["devices"][from_device_index]
                        to_device_obj = topology_data["devices"][to_device_index]
                        
                        # 确定端口
                        from_port = "GigabitEthernet0/0/1"
                        to_port = "GigabitEthernet0/0/1"
                        
                        # 添加连接
                        topology_data["connections"].append({
                            "from": f"{from_device_obj['name']}:{from_port}",
                            "to": f"{to_device_obj['name']}:{to_port}",
                            "bandwidth": "1G"
                        })
        
        # 如果没有识别到设备，添加默认设备
        if not topology_data["devices"]:
            # 添加默认的路由器和交换机
            topology_data["devices"] = [
                {
                    "name": "Router1",
                    "type": "AR2220",
                    "management_ip": "192.168.1.1",
                    "subnet_mask": "255.255.255.0"
                },
                {
                    "name": "Switch1",
                    "type": "S5700",
                    "management_ip": "192.168.1.2",
                    "subnet_mask": "255.255.255.0"
                }
            ]
            
            # 添加默认连接
            topology_data["connections"] = [
                {
                    "from": "Router1:GigabitEthernet0/0/0",
                    "to": "Switch1:GigabitEthernet0/0/1",
                    "bandwidth": "1G"
                }
            ]
        
        return topology_data
    
    def _parse_with_openai(self, description: str) -> Dict[str, Any]:
        """使用OpenAI API解析网络描述"""
        try:
            # 检查API密钥
            if not self.api_key:
                logger.error("OpenAI API密钥未设置")
                return self._parse_local(description)
            
            # 修改这行 - 优先使用用户设置的URL，如果没有则使用默认值
            api_url = self.api_url if self.api_url else "https://api.openai.com/v1/chat/completions"
            
            # 在执行前先记录信息
            logger.info(f"正在调用OpenAI API: {api_url}")
            
            # 构建提示词
            system_message = """您是一个专业的网络拓扑分析助手。请分析用户提供的网络拓扑描述，并输出一个结构化的JSON对象。
您必须严格按照以下JSON格式输出，不要添加任何额外字段或改变结构：

{
  "devices": [
    {
      "name": "设备名称",
      "type": "设备类型(AR2220/S5700/USG6000)",
      "management_ip": "管理IP地址",
      "subnet_mask": "子网掩码"
    }
  ],
  "connections": [
    {
      "from": "设备名:GigabitEthernet0/0/端口号",
      "to": "设备名:GigabitEthernet0/0/端口号",
      "bandwidth": "带宽(1G/10G等)"
    }
  ]
}

重要规则：
1. 请直接输出JSON，不要添加额外的包装字段
2. 不要输出markdown代码块，只输出原始JSON
3. 不要添加任何解释文字
4. 确保输出的JSON格式正确可解析
5. 设备类型应该是AR2220、S5700或USG6000中的一种
6. 你的输出将被直接解析为JSON，不要有任何额外文本"""
            
            # 准备API请求参数
            payload = {
                "model": "gpt-4o",  # 可以根据实际需求调整模型
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"分析以下网络拓扑描述并输出符合要求的JSON格式:\n\n{description}"}
                ],
                "temperature": 0.1,  # 低温度以获得更确定的输出
                "max_tokens": 2000
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 可选：添加代理设置（如果需要）
            proxies = None
            # proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}  # 取消注释并设置为您的代理
            
            # 添加重试机制
            max_retries = 3
            retry_delay = 2  # 初始延迟2秒
            
            for retry in range(max_retries):
                try:
                    # 发送API请求
                    logger.info(f"发送OpenAI API请求 (尝试 {retry+1}/{max_retries})")
                    
                    response = requests.post(
                        api_url,
                        headers=headers,
                        json=payload,
                        timeout=60,  # 增加超时时间
                        proxies=proxies
                    )
                    
                    # 详细记录API响应信息以便调试
                    logger.info(f"OpenAI API响应状态码: {response.status_code}")
                    if response.status_code != 200:
                        logger.error(f"OpenAI API响应错误: {response.text}")
                    
                    # 处理响应
                    if response.status_code == 200:
                        response_data = response.json()
                        
                        if "choices" in response_data:
                            logger.info(f"成功获取OpenAI响应")
                            content = response_data["choices"][0]["message"]["content"]
                            
                            # 从响应中提取JSON
                            try:
                                # 尝试直接解析JSON
                                json_data = json.loads(content)
                                
                                # 检查是否包含必要的字段
                                if "devices" in json_data and "connections" in json_data:
                                    logger.info("成功使用OpenAI API解析网络描述")
                                    return json_data
                                else:
                                    logger.warning("OpenAI API返回的JSON缺少必要字段")
                            except json.JSONDecodeError:
                                # 如果直接解析失败，尝试提取JSON部分
                                import re
                                json_match = re.search(r'({.*})', content.replace('\n', ''), re.DOTALL)
                                if json_match:
                                    try:
                                        json_data = json.loads(json_match.group(1))
                                        if "devices" in json_data and "connections" in json_data:
                                            logger.info("成功从OpenAI响应中提取JSON数据")
                                            return json_data
                                    except json.JSONDecodeError:
                                        logger.warning("无法从OpenAI响应中提取有效JSON")
                        break
                    
                    logger.warning(f"第{retry+1}次请求失败: 状态码 {response.status_code}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                except Exception as req_err:
                    logger.warning(f"第{retry+1}次请求异常: {str(req_err)}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
            
            # 如果所有重试都失败，则回退到本地解析
            logger.error("OpenAI API调用失败，回退到本地规则解析")
            return self._parse_local(description)
            
        except Exception as e:
            logger.error(f"OpenAI API调用失败: {str(e)}")
            return self._parse_local(description)
    
    def _parse_with_deepseek(self, description: str) -> Dict[str, Any]:
        """使用DeepSeek API解析网络描述"""
        try:
            # 检查API密钥
            if not self.api_key:
                logger.error("DeepSeek API密钥未设置")
                return self._parse_local(description)
            
            # 使用NVIDIA API端点
            api_url = self.api_url or "https://integrate.api.nvidia.com/v1/chat/completions"
            
            # 在执行前先记录信息
            logger.info(f"正在调用DeepSeek API (通过NVIDIA API): {api_url}")
            
            # 构建提示词
            system_message = """您是一个专业的网络拓扑分析助手。请分析用户提供的网络拓扑描述，并输出一个结构化的JSON对象。
您必须严格按照以下JSON格式输出，不要添加任何额外字段或改变结构：

{
  "devices": [
    {
      "name": "设备名称",
      "type": "设备类型(AR2220/S5700/USG6000)",
      "management_ip": "管理IP地址",
      "subnet_mask": "子网掩码"
    }
  ],
  "connections": [
    {
      "from": "设备名:GigabitEthernet0/0/端口号",
      "to": "设备名:GigabitEthernet0/0/端口号",
      "bandwidth": "带宽(1G/10G等)"
    }
  ]
}

重要规则：
1. 请直接输出JSON，不要添加额外的包装字段
2. 不要输出markdown代码块，只输出原始JSON
3. 不要添加任何解释文字
4. 确保输出的JSON格式正确可解析
5. 设备类型应该是AR2220、S5700或USG6000中的一种
6. 你的输出将被直接解析为JSON，不要有任何额外文本"""
            
            # 准备API请求参数 - 使用NVIDIA API格式
            payload = {
                "model": "deepseek-ai/deepseek-r1",  # 使用DeepSeek R1模型
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": f"分析以下网络拓扑描述并输出符合要求的JSON格式:\n\n{description}"}
                ],
                "temperature": 0.1,  # 低温度以获得更确定的输出
                "max_tokens": 2000
            }
            
            # 设置请求头 - 使用NVIDIA API认证方式
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 可选：添加代理设置（如果需要）
            proxies = None
            # proxies = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}  # 取消注释并设置为您的代理
            
            # 添加重试机制
            max_retries = 3
            retry_delay = 2  # 初始延迟2秒
            
            for retry in range(max_retries):
                try:
                    # 发送API请求
                    logger.info(f"发送DeepSeek API请求 (尝试 {retry+1}/{max_retries})")
                    
                    response = requests.post(
                        api_url,
                        headers=headers,
                        json=payload,
                        timeout=60,  # 增加超时时间
                        proxies=proxies
                    )
                    
                    # 详细记录API响应信息以便调试
                    logger.info(f"DeepSeek API响应状态码: {response.status_code}")
                    if response.status_code != 200:
                        logger.error(f"DeepSeek API响应错误: {response.text}")
                    
                    # 处理响应
                    if response.status_code == 200:
                        response_data = response.json()
                        
                        if "choices" in response_data and len(response_data["choices"]) > 0:
                            content = response_data["choices"][0]["message"]["content"]
                            logger.info(f"成功获取DeepSeek响应")
                            
                            # 从响应中提取JSON
                            try:
                                # 尝试直接解析JSON
                                json_data = json.loads(content)
                                
                                # 检查是否包含必要的字段
                                if "devices" in json_data and "connections" in json_data:
                                    logger.info("成功使用DeepSeek API解析网络描述")
                                    return json_data
                                else:
                                    logger.warning("DeepSeek API返回的JSON缺少必要字段")
                            except json.JSONDecodeError:
                                # 如果直接解析失败，尝试提取JSON部分
                                import re
                                json_match = re.search(r'({.*})', content.replace('\n', ''), re.DOTALL)
                                if json_match:
                                    try:
                                        json_data = json.loads(json_match.group(1))
                                        if "devices" in json_data and "connections" in json_data:
                                            logger.info("成功从DeepSeek响应中提取JSON数据")
                                            return json_data
                                    except json.JSONDecodeError:
                                        logger.warning("无法从DeepSeek响应中提取有效JSON")
                        break
                    
                    logger.warning(f"第{retry+1}次请求失败: 状态码 {response.status_code}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                except Exception as req_err:
                    logger.warning(f"第{retry+1}次请求异常: {str(req_err)}")
                    if retry < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2
            
            # 如果所有重试都失败，则回退到本地解析
            logger.error("DeepSeek API调用失败，回退到本地规则解析")
            return self._parse_local(description)
            
        except Exception as e:
            logger.error(f"DeepSeek API调用失败: {str(e)}")
            return self._parse_local(description)
    
    def _parse_with_xunfei(self, description: str) -> Dict[str, Any]:
        """使用讯飞星火API解析网络描述"""
        try:
            # 检查API密钥和应用ID
            if not self.api_key or not self.api_app_id or not self.api_secret:
                logger.error("讯飞星火API密钥、应用ID或密钥Secret未设置")
                return self._parse_local(description)
            
            # 创建URL，包含认证信息
            spark_url = self._create_spark_url()
            
            # 构建请求数据
            system_message = """您是一个专业的网络拓扑分析助手。请分析用户提供的网络拓扑描述，并输出一个结构化的JSON对象。
您必须严格按照以下JSON格式输出，不要添加任何额外字段或改变结构：

{
  "devices": [
    {
      "name": "设备名称",
      "type": "设备类型(AR2220/S5700/USG6000)",
      "management_ip": "管理IP地址",
      "subnet_mask": "子网掩码"
    }
  ],
  "connections": [
    {
      "from": "设备名:GigabitEthernet0/0/端口号",
      "to": "设备名:GigabitEthernet0/0/端口号",
      "bandwidth": "带宽(1G/10G等)"
    }
  ]
}

重要规则：
1. 请直接输出JSON，不要添加额外的包装字段
2. 不要输出markdown代码块，只输出原始JSON
3. 不要添加任何解释文字
4. 确保输出的JSON格式正确可解析
5. 设备类型应该是AR2220、S5700或USG6000中的一种
6. 你的输出将被直接解析为JSON，不要有任何额外文本"""
            
            # 星火API需要使用HTTP请求而非WebSocket
            spark_api_url = "https://spark-api.xf-yun.com/v2.1/chat"
            
            # 使用UUID生成消息ID
            message_id = str(uuid.uuid4())
            
            # 构建请求体数据
            request_data = {
                "header": {
                    "app_id": self.api_app_id,
                    "uid": "user_01"
                },
                "parameter": {
                    "chat": {
                        "domain": "general",
                        "temperature": 0.1,
                        "max_tokens": 2000
                    }
                },
                "payload": {
                    "message": {
                        "text": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": f"分析以下网络拓扑描述并输出符合要求的JSON格式:\n\n{description}"}
                        ]
                    }
                }
            }
            
            # 计算认证签名
            current_time = int(time.time())
            signature_origin = f"host: spark-api.xf-yun.com\ndate: {current_time}\nPOST /v2.1/chat HTTP/1.1"
            
            # 计算HMAC-SHA256签名
            signature_sha = hmac.new(
                self.api_secret.encode('utf-8'),
                signature_origin.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            
            # 将签名转为Base64
            signature_base64 = base64.b64encode(signature_sha).decode('utf-8')
            
            # 构建认证头
            authorization = f"api_key=\"{self.api_key}\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"{signature_base64}\""
            
            # 设置请求头
            headers = {
                "Content-Type": "application/json",
                "Authorization": authorization,
                "Host": "spark-api.xf-yun.com",
                "Date": str(current_time)
            }
            
            # 发送API请求
            response = requests.post(
                spark_api_url,
                headers=headers,
                json=request_data,
                timeout=30
            )
            
            # 处理响应
            if response.status_code == 200:
                response_data = response.json()
                
                # 提取返回的文本内容
                if "payload" in response_data and "choices" in response_data["payload"]:
                    content = response_data["payload"]["choices"]["text"][0]["content"]
                    
                    # 从响应中提取JSON
                    try:
                        # 尝试直接解析JSON
                        json_data = json.loads(content)
                        
                        # 检查是否包含必要的字段
                        if "devices" in json_data and "connections" in json_data:
                            logger.info("成功使用讯飞星火API解析网络描述")
                            return json_data
                        else:
                            logger.warning("讯飞星火API返回的JSON缺少必要字段")
                    except json.JSONDecodeError:
                        # 如果直接解析失败，尝试提取JSON部分
                        import re
                        json_match = re.search(r'({.*})', content.replace('\n', ''), re.DOTALL)
                        if json_match:
                            try:
                                json_data = json.loads(json_match.group(1))
                                if "devices" in json_data and "connections" in json_data:
                                    logger.info("成功从讯飞星火响应中提取JSON数据")
                                    return json_data
                            except json.JSONDecodeError:
                                logger.warning("无法从讯飞星火响应中提取有效JSON")
            
            logger.error(f"讯飞星火API调用失败 (状态码: {response.status_code}): {response.text}")
            return self._parse_local(description)
            
        except Exception as e:
            logger.error(f"讯飞星火API调用失败: {str(e)}")
            return self._parse_local(description)
    
    def _create_spark_url(self) -> str:
        """创建讯飞星火API的认证URL
        
        Returns:
            带有认证信息的URL
        """
        # 构建URL，包含认证信息
        # 由于实际实现比较复杂，这里只返回一个基本URL
        # 实际请求将使用HTTP而非WebSocket
        return "https://spark-api.xf-yun.com/v2.1/chat"

    def test_api_connection(self, model_type: Optional[str] = None) -> Dict[str, Any]:
        """
        测试API连接
        
        Args:
            model_type: 模型类型，可选 "openai", "deepseek", "xunfei"
            
        Returns:
            包含测试结果的字典 {"success": bool, "message": str}
        """
        # 使用指定模型类型或默认模型类型
        model = model_type or self.model_type
        
        # 如果是本地模型，不需要测试
        if model == "local":
            return {"success": True, "message": "本地规则解析不需要API连接"}
        
        # 检查API密钥是否设置
        if not self.api_key:
            return {"success": False, "message": f"{model} API密钥未设置"}
        
        # 准备简单的测试描述
        test_description = "测试网络，一台路由器连接一台交换机"
        
        try:
            if model == "openai":
                return self._test_openai_connection()
            elif model == "deepseek":
                return self._test_deepseek_connection()
            elif model == "xunfei":
                return self._test_xunfei_connection()
            else:
                return {"success": False, "message": f"未知的模型类型: {model}"}
        except Exception as e:
            logger.error(f"测试API连接失败: {str(e)}")
            return {"success": False, "message": f"测试API连接时发生错误: {str(e)}"}
    
    def _test_openai_connection(self) -> Dict[str, Any]:
        """测试OpenAI API连接"""
        # 检查API密钥
        if not self.api_key:
            return {"success": False, "message": "OpenAI API密钥未设置"}
        
        # 修改这行 - 优先使用用户设置的URL，如果没有则使用默认值
        api_url = self.api_url if self.api_url else "https://api.openai.com/v1/chat/completions"
        
        # 构建简单的测试请求
        payload = {
            "model": "gpt-3.5-turbo",  # 使用较小的模型进行测试
            "messages": [
                {"role": "user", "content": "返回一个简单的JSON: {\"test\": \"success\"}"}
            ],
            "max_tokens": 20
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # 发送API请求
            logger.info(f"测试OpenAI API连接: {api_url}")
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=10  # 缩短测试的超时时间
            )
            
            # 处理响应
            if response.status_code == 200:
                logger.info("OpenAI API连接测试成功")
                return {"success": True, "message": "OpenAI API连接成功"}
            else:
                error_message = f"OpenAI API连接失败 (状态码: {response.status_code}): {response.text}"
                logger.error(error_message)
                return {"success": False, "message": error_message}
                
        except Exception as e:
            error_message = f"OpenAI API连接出错: {str(e)}"
            logger.error(error_message)
            return {"success": False, "message": error_message}
    
    def _test_deepseek_connection(self) -> Dict[str, Any]:
        """测试DeepSeek API连接"""
        # 检查API密钥
        if not self.api_key:
            return {"success": False, "message": "DeepSeek API密钥未设置"}
        
        # 使用NVIDIA API端点
        api_url = self.api_url if self.api_url else "https://integrate.api.nvidia.com/v1/chat/completions"
        
        # 构建简单的测试请求
        payload = {
            "model": "deepseek-ai/deepseek-r1",
            "messages": [
                {"role": "user", "content": "返回一个简单的JSON: {\"test\": \"success\"}"}
            ],
            "max_tokens": 20
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # 发送API请求
            logger.info(f"测试DeepSeek API连接: {api_url}")
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=10  # 缩短测试的超时时间
            )
            
            # 处理响应
            if response.status_code == 200:
                logger.info("DeepSeek API连接测试成功")
                return {"success": True, "message": "DeepSeek API连接成功"}
            else:
                error_message = f"DeepSeek API连接失败 (状态码: {response.status_code}): {response.text}"
                logger.error(error_message)
                return {"success": False, "message": error_message}
                
        except Exception as e:
            error_message = f"DeepSeek API连接出错: {str(e)}"
            logger.error(error_message)
            return {"success": False, "message": error_message}
    
    def _test_xunfei_connection(self) -> Dict[str, Any]:
        """测试讯飞星火API连接"""
        # 检查API密钥和应用ID
        if not self.api_key or not self.api_app_id or not self.api_secret:
            return {"success": False, "message": "讯飞星火API密钥、应用ID或密钥Secret未设置"}
        
        # 创建URL，包含认证信息
        spark_api_url = "https://spark-api.xf-yun.com/v2.1/chat"
        
        # 使用UUID生成消息ID
        message_id = str(uuid.uuid4())
        
        # 构建请求体数据
        request_data = {
            "header": {
                "app_id": self.api_app_id,
                "uid": "user_01"
            },
            "parameter": {
                "chat": {
                    "domain": "general",
                    "temperature": 0.1,
                    "max_tokens": 20
                }
            },
            "payload": {
                "message": {
                    "text": [
                        {"role": "user", "content": "返回一个简单的JSON: {\"test\": \"success\"}"}
                    ]
                }
            }
        }
        
        # 计算认证签名
        current_time = int(time.time())
        signature_origin = f"host: spark-api.xf-yun.com\ndate: {current_time}\nPOST /v2.1/chat HTTP/1.1"
        
        # 计算HMAC-SHA256签名
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        # 将签名转为Base64
        signature_base64 = base64.b64encode(signature_sha).decode('utf-8')
        
        # 构建认证头
        authorization = f"api_key=\"{self.api_key}\", algorithm=\"hmac-sha256\", headers=\"host date request-line\", signature=\"{signature_base64}\""
        
        # 设置请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": authorization,
            "Host": "spark-api.xf-yun.com",
            "Date": str(current_time)
        }
        
        try:
            # 发送API请求
            logger.info("测试讯飞星火API连接")
            response = requests.post(
                spark_api_url,
                headers=headers,
                json=request_data,
                timeout=10
            )
            
            # 处理响应
            if response.status_code == 200:
                logger.info("讯飞星火API连接测试成功")
                return {"success": True, "message": "讯飞星火API连接成功"}
            else:
                error_message = f"讯飞星火API连接失败 (状态码: {response.status_code}): {response.text}"
                logger.error(error_message)
                return {"success": False, "message": error_message}
                
        except Exception as e:
            error_message = f"讯飞星火API连接出错: {str(e)}"
            logger.error(error_message)
            return {"success": False, "message": error_message}


# 测试函数
def main():
    """模块主函数，用于独立测试"""
    import sys
    
    if len(sys.argv) > 1:
        # 从命令行参数读取网络描述
        description = " ".join(sys.argv[1:])
    else:
        # 示例网络描述
        description = """设计一个简单的网络，包含一个路由器和两台交换机。
路由器连接到两台交换机，形成星型拓扑结构。"""
    
    # 创建NLP生成器
    generator = NLPTopologyGenerator()
    
    # 解析网络描述
    topology_data = generator.parse_network_description(description)
    
    # 输出解析结果
    logger.info(f"成功解析网络描述，生成了{len(topology_data['devices'])}个设备和{len(topology_data['connections'])}个连接")
    
    return topology_data


if __name__ == "__main__":
    main() 