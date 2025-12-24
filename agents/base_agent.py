import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger
from openai import OpenAI
import time

class AgentHelper:
    """智能体助手基类 - 处理LLM API调用"""
    
    def __init__(self, args, agent_name: str, url: str = "http://127.0.0.1:7778"):
        # 从args中获取engine参数
        self.engine = getattr(args, 'model', 'vllm')
        self.agent_name = agent_name
        self.url = url
        self.api_key = os.getenv("API_KEY", "")
        self.default_temp = 0.3
        
        # 初始化客户端
        self.client = self._initialize_client()
    
    def _initialize_client(self) -> OpenAI:
        """根据引擎类型初始化客户端"""
        if self.engine == "openai":
            return OpenAI(api_key=self.api_key)
        
        elif self.engine == "deepseek":
            return OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1",
            )
        
        elif self.engine == "vllm":
            # 处理vllm后端
            base_url = self.url
            if base_url.endswith("/v1"):
                base_url = base_url[:-3]
            return OpenAI(
                api_key="EMPTY",  # vllm不需要真正的API key
                base_url=f"{base_url}/v1",
            )
        
        elif self.engine == "siliconflow":
            return OpenAI(
                api_key=self.api_key,
                base_url="https://api.siliconflow.cn/v1",
            )
        
        else:
            raise ValueError(f"不支持的引擎类型: {self.engine}")
    
    def invoke(self, llm_name: str, messages: List[Dict], temperature: float = None, timeout: int = 60) -> str: 
        """调用LLM API"""
        if temperature is None:
            temperature = self.default_temp
        
        max_retries = 3
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=llm_name,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=100000,
                    timeout=timeout
                )
                
                content = response.choices[0].message.content
                if content:
                    return content
                else:
                    raise ValueError("Empty response from model")
                    
            except Exception as e:
                self.logger.warning(f"API调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise Exception(f"API调用失败: {e}")
        
        raise Exception("无法获取模型响应")

class BaseAgent(AgentHelper):
    """基础智能体类 - 所有智能体的基类"""
    
    def __init__(self, args, specialty: str, system_instruction: str, 
                 agent_name: str, logger: list = None):
        """
        初始化基础智能体
        
        Args:
            args: 命令行参数
            specialty: 专业领域
            system_instruction: 系统指令
            agent_name: 智能体名称
            logger: 日志记录器
        """
        self.args = args
        self.specialty = specialty
        self.system_instruction = system_instruction
        self.agent_name = agent_name

        if logger is None:
            from utils.logger import setup_logger
            self.logger = setup_logger(f"agent_{agent_name}")
        else:
            self.logger = logger
        
        # 初始化助手
        super().__init__(
            args=args,
            agent_name=agent_name,
            url=getattr(args, 'url', "http://10.124.0.7:9001/v1")
        )
        
        # 初始化消息历史
        self.messages = [{"role": "system", "content": system_instruction}]
        self.history = {
            "with_history": self.messages.copy(),
            "without_history": []
        }
        
        # 答案和推理记录
        self.ans_list = []
        self.reason_list = []
        self.ans = ""
        self.reason = ""
        
        self.logger.info(f"初始化智能体: {agent_name} ({specialty})")
    
    def chat(self, message: str, temperature: float = None, timeout: int = 60) -> str:
        """有历史记录的对话"""
        if temperature is None:
            temperature = self.args.temp
        
        self.messages.append({"role": "user", "content": message})
        
        try:
            response = self.invoke(self.args.llm_name, self.messages, temperature, timeout)
            self.messages.append({"role": "assistant", "content": response})
            
            # 记录历史
            self.history['with_history'].extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": response}
            ])
            
            return response
            
        except Exception as e:
            self.logger.error(f"智能体 {self.agent_name} 对话失败: {e}")
            raise
    
    def chat_without_history(self, message: str, system_instruction: str = None, 
                            temperature: float = None, timeout: int = 60) -> str:
        """无历史记录的对话"""
        if temperature is None:
            temperature = self.args.temp
        
        system_content = system_instruction or self.system_instruction
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": message}
        ]
        
        try:
            response = self.invoke(self.args.llm_name, messages, temperature, timeout)
            
            # 记录历史
            self.history['without_history'].append({
                "messages": messages + [{"role": "assistant", "content": response}],
                "timestamp": self._get_timestamp()
            })
            
            return response
            
        except Exception as e:
            self.logger.error(f"智能体 {self.agent_name} 无历史对话失败: {e}")
            raise
    
    def add_log(self, step: str, input_data: str, info: str, answer: str) -> None:
        """添加日志记录"""
        log_entry = {
            "timestamp": self._get_timestamp(),
            "agent_name": self.agent_name,
            "step": step,
            "input": input_data,
            "info": info,
            "answer": answer
        }
        self.logger.append(log_entry)
    
    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        return datetime.now().isoformat()
    
    def save_conversation(self, filepath: str = None) -> None:
        """保存对话历史"""
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"logs/{self.agent_name}_{timestamp}.json"
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
        
        logger.info(f"对话历史已保存: {filepath}")
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取智能体信息"""
        return {
            "name": self.agent_name,
            "specialty": self.specialty,
            "system_instruction_preview": self.system_instruction[:100] + "..." 
                if len(self.system_instruction) > 100 else self.system_instruction,
            "message_count": len(self.messages) - 1,  # 减去系统消息
            "answer_count": len(self.ans_list)
        }
    def set_shared_history(self, shared_messages: List[Dict]) -> None:
        """设置共享历史记录"""
        # 保留系统消息，添加共享历史
        system_message = self.messages[0] if self.messages and self.messages[0]["role"] == "system" else None
        if system_message:
            self.messages = [system_message] + shared_messages.copy()
        else:
            self.messages = shared_messages.copy()
    
    def get_current_messages(self) -> List[Dict]:
        """获取当前消息历史（不包括系统消息）"""
        if self.messages and self.messages[0]["role"] == "system":
            return self.messages[1:]
        return self.messages.copy()
    
    def add_to_shared_history(self, role: str, content: str) -> None:
        """添加消息到共享历史"""
        self.messages.append({"role": role, "content": content})
        
    def _format_medical_record_for_analysis(self, medical_record: Dict) -> str:
        """格式化病历信息用于分析 - 通用方法"""
        if isinstance(medical_record, str):
            return medical_record
        
        if isinstance(medical_record, dict):
            # 优先使用自由文本字段
            if 'free_text' in medical_record:
                return medical_record['free_text']
            elif 'text' in medical_record:
                return medical_record['text']
            elif 'content' in medical_record:
                return medical_record['content']
            else:
                # 将字典内容拼接成文本
                return self._dict_to_text(medical_record)
        
        return str(medical_record)
    
    def _dict_to_text(self, medical_dict: Dict) -> str:
        """将病历字典转换为文本 - 简洁格式"""
        text_parts = []
        
        # 按常见病历字段顺序组织
        common_fields = [
            ('chief_complaint', '主诉'),
            ('present_illaint', '现病史'),
            ('past_history', '既往史'),
            ('physical_exam', '体格检查'),
            ('lab_results', '辅助检查'),
            ('vital_signs', '生命体征'),
            ('diagnosis', '初步诊断')
        ]
        
        for field_key, field_name in common_fields:
            if field_key in medical_dict and medical_dict[field_key]:
                text_parts.append(f"{field_name}: {medical_dict[field_key]}")
        
        # 添加其他字段
        for key, value in medical_dict.items():
            if key not in [f[0] for f in common_fields] and value:
                text_parts.append(f"{key}: {value}")
        
        return '\n'.join(text_parts) if text_parts else "无病历信息"

    def update_context(self, new_information: str, information_type: str = "general") -> None:
        """
        更新智能体上下文信息 - 通用实现
        
        Args:
            new_information: 新的信息内容
            information_type: 信息类型 (general, lab_result, imaging, etc.)
        """
        try:
            # 根据信息类型构建不同的更新消息
            type_descriptions = {
                "general": "补充信息",
                "lab_result": "实验室检查结果",
                "imaging": "影像学检查结果", 
                "vital_signs": "生命体征",
                "treatment_response": "治疗反应"
            }
            
            description = type_descriptions.get(information_type, "补充信息")
            update_message = f"""用户提供了新的{description}：{new_information}

请基于这个新信息重新评估您之前的分析。"""
            
            # 添加到消息历史
            self.messages.append({
                "role": "user", 
                "content": update_message
            })
            
            self.logger.info(f"智能体 {self.agent_name} 上下文已更新: {description}")
            
        except Exception as e:
            self.logger.error(f"更新智能体上下文失败: {e}")
            raise

    def update_focus(self, new_focus: str) -> None:
        """
        更新讨论焦点
        
        Args:
            new_focus: 新的讨论焦点
        """
        try:
            focus_message = f"""讨论焦点已更新为：{new_focus}

请基于这个新的讨论焦点调整您的分析方向。"""
            
            self.messages.append({
                "role": "system", 
                "content": focus_message
            })
            
            self.logger.info(f"智能体 {self.agent_name} 讨论焦点已更新")
            
        except Exception as e:
            self.logger.error(f"更新讨论焦点失败: {e}")
            raise







# 工具函数
def parse_content(content: str, tag: str = "Answer") -> str:
    """从内容中解析答案标签"""
    import re
    
    # 多种格式匹配
    patterns = [
        rf"<{tag}>Answer:\s*([A-E])</{tag}>",
        rf"<{tag}>Answer:\s*([A-E])",
        rf"<{tag}>Option:\s*([A-E])</{tag}>",
        rf"Answer:\s*([A-E])",
        rf"Option:\s*([A-E])",
        rf"<{tag}>([A-E])</{tag}>"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    # 如果没有找到格式化的答案，尝试查找字母
    for option in ["A", "B", "C", "D", "E"]:
        if option in content:
            return option
    
    raise ValueError(f"无法从内容中解析答案标签 <{tag}>")

def check_answer_same(ans_list: List[str]) -> bool:
    """检查答案列表是否一致"""
    return len(set(ans_list)) == 1

def find_answer(text: str, options: List[str] = ["A", "B", "C", "D", "E"]) -> str:
    """从文本中查找答案"""
    for option in options:
        if option in text:
            return option
    return ""