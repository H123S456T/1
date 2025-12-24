from typing import Dict, List, Optional, Any
from loguru import logger
from agents.base_agent import BaseAgent
from agents.agent_registry import get_agent_registry

class CustomAgent(BaseAgent):
    """
    自定义智能体类
    支持用户自定义提示词和行为的临时智能体
    """
    
    def __init__(self, args, agent_name: str, custom_prompt: str, 
                 description: str = "", category: str = "自定义",
                 logger: list = None, session_id: str = None):
        """
        初始化自定义智能体
        
        Args:
            args: 命令行参数
            agent_name: 智能体名称
            custom_prompt: 自定义提示词
            description: 描述信息
            category: 分类
            logger: 日志记录器
            session_id: 会话ID（用于注册）
        """
        self.agent_name = agent_name
        self.custom_prompt = custom_prompt
        self.description = description
        self.category = category
        self.session_id = session_id
        self.agent_registry = get_agent_registry()
        
        # 构建完整的系统提示词
        full_prompt = self._build_custom_prompt(custom_prompt)
        
        super().__init__(
            args=args,
            specialty=agent_name,  # 使用智能体名称作为专科
            system_instruction=full_prompt,
            agent_name=agent_name,
            logger=logger
        )
        
        # 注册到智能体注册表
        if session_id:
            self._register_agent()
        
        logger.info(f"Initialized custom agent: {agent_name}")
    
    def _build_custom_prompt(self, base_prompt: str) -> str:
        """构建自定义提示词"""
        custom_prompt = f"""你是一位专业的医学智能体。{base_prompt}

请遵循以下原则：
1. 基于提供的医学知识进行分析
2. 保持专业和准确的表达
3. 考虑临床实际情况
4. 提供有建设性的建议

请用清晰、专业的语言进行回答。"""
        
        return custom_prompt
    
    def _register_agent(self) -> bool:
        """将自定义智能体注册到注册表"""
        try:
            success = self.agent_registry.create_custom_agent(
                session_id=self.session_id,
                agent_name=self.agent_name,
                prompt=self.custom_prompt,
                description=self.description,
                category=self.category
            )
            
            if success:
                logger.info(f"Custom agent {self.agent_name} registered successfully")
            else:
                logger.warning(f"Failed to register custom agent {self.agent_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error registering custom agent: {e}")
            return False
    
    def analyze_case(self, medical_record: Dict, specific_question: str = None) -> Dict[str, Any]:
        """
        分析病例（自定义智能体的主要方法）
        
        Args:
            medical_record: 病历信息
            specific_question: 具体问题
            
        Returns:
            分析结果
        """
        message = self._build_custom_analysis_message(medical_record, specific_question)
        
        try:
            response = self.chat_without_history(message)
            
            return {
                "success": True,
                "agent_type": "custom",
                "agent_name": self.agent_name,
                "response": response,
                "structured_analysis": self._structure_custom_response(response),
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"Error in custom agent analysis: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_name": self.agent_name
            }
    
    def _build_custom_analysis_message(self, medical_record: Dict, question: str = None) -> str:
        """构建自定义分析消息"""
        message = f"""请根据您的专业领域分析以下病例：

【病例信息】
{self._format_medical_record_for_custom_analysis(medical_record)}"""
        
        if question:
            message += f"\n\n【需要回答的问题】\n{question}"
        
        message += f"\n\n请基于您的专业知识提供分析。"
        
        return message
    
    def _format_medical_record_for_custom_analysis(self, medical_record: Dict) -> str:
        """格式化病历信息用于自定义分析"""
        formatted = []
        
        if medical_record.get('chief_complaint'):
            formatted.append(f"主诉: {medical_record['chief_complaint']}")
        if medical_record.get('present_illness'):
            formatted.append(f"现病史: {medical_record['present_illness']}")
        if medical_record.get('past_history'):
            formatted.append(f"既往史: {medical_record['past_history']}")
        if medical_record.get('physical_exam'):
            formatted.append(f"体格检查: {medical_record['physical_exam']}")
        if medical_record.get('lab_results'):
            formatted.append(f"辅助检查: {medical_record['lab_results']}")
        
        return '\n'.join(formatted)
    
    def _structure_custom_response(self, response: str) -> Dict[str, Any]:
        """结构化自定义响应"""
        # 简单的结构化处理，可以根据需要增强
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        # 提取关键部分
        diagnosis_section = []
        treatment_section = []
        reasoning_section = []
        other_section = []
        
        current_section = other_section
        for line in lines:
            if any(keyword in line.lower() for keyword in ['诊断', '考虑', '可能']):
                current_section = diagnosis_section
            elif any(keyword in line.lower() for keyword in ['治疗', '用药', '手术']):
                current_section = treatment_section
            elif any(keyword in line.lower() for keyword in ['因为', '由于', '理由']):
                current_section = reasoning_section
            elif line.startswith(('#', '##', '###')):  # Markdown标题
                current_section = other_section
            
            current_section.append(line)
        
        return {
            "diagnosis": '\n'.join(diagnosis_section) if diagnosis_section else "未明确",
            "treatment_suggestions": '\n'.join(treatment_section) if treatment_section else "未提供",
            "reasoning": '\n'.join(reasoning_section) if reasoning_section else response[:500],  # 截取部分作为推理
            "full_response": response
        }
    
    def respond_to_user_question(self, user_question: str, context: Dict = None) -> Dict[str, Any]:
        """
        响应用户提问（用于用户介入时的交互）
        
        Args:
            user_question: 用户问题
            context: 上下文信息
            
        Returns:
            响应结果
        """
        message = self._build_user_response_message(user_question, context)
        
        try:
            response = self.chat_without_history(message)
            
            return {
                "success": True,
                "agent_name": self.agent_name,
                "question": user_question,
                "response": response,
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"Error responding to user question: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_name": self.agent_name
            }
    
    def _build_user_response_message(self, question: str, context: Dict = None) -> str:
        """构建用户响应消息"""
        message = f"""用户向您提问：{question}

请基于您的专业知识提供专业、准确的回答。"""
        
        if context and context.get('discussion_context'):
            message += f"\n\n当前讨论背景：{context['discussion_context']}"
        
        if context and context.get('medical_record'):
            message += f"\n\n相关病例信息：{self._format_medical_record_for_custom_analysis(context['medical_record'])}"
        
        return message
    
    def provide_specialized_insight(self, topic: str, medical_context: Dict) -> Dict[str, Any]:
        """
        提供专业见解（针对特定主题）
        
        Args:
            topic: 主题
            medical_context: 医学上下文
            
        Returns:
            专业见解
        """
        message = f"""请就以下主题提供专业见解：
主题：{topic}

相关医学背景：
{self._format_medical_context(medical_context)}

请提供深入、专业的分析。"""
        
        try:
            response = self.chat_without_history(message)
            
            return {
                "success": True,
                "topic": topic,
                "insight": response,
                "agent_name": self.agent_name,
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"Error providing specialized insight: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_medical_context(self, context: Dict) -> str:
        """格式化医学上下文"""
        formatted = []
        for key, value in context.items():
            if value:
                formatted.append(f"{key}: {value}")
        return '\n'.join(formatted) if formatted else "无额外上下文"
    
    def evaluate_other_opinion(self, other_opinion: str, medical_record: Dict) -> Dict[str, Any]:
        """
        评估其他智能体的意见
        
        Args:
            other_opinion: 其他智能体的意见
            medical_record: 病历信息
            
        Returns:
            评估结果
        """
        message = f"""请评估以下医学意见：
其他智能体的意见：{other_opinion}

相关病例信息：
{self._format_medical_record_for_custom_analysis(medical_record)}

请从专业角度评估该意见的合理性、优点和局限性。"""
        
        try:
            response = self.chat_without_history(message)
            
            return {
                "success": True,
                "evaluated_opinion": other_opinion,
                "evaluation": response,
                "agent_name": self.agent_name,
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"Error evaluating other opinion: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取智能体信息"""
        return {
            "name": self.agent_name,
            "type": "custom",
            "description": self.description,
            "category": self.category,
            "session_id": self.session_id,
            "prompt_preview": self.custom_prompt[:100] + "..." if len(self.custom_prompt) > 100 else self.custom_prompt
        }


class CustomAgentFactory:
    """自定义智能体工厂类"""
    
    @staticmethod
    def create_agent(args, agent_config: Dict, session_id: str = None, logger: list = None) -> CustomAgent:
        """
        创建自定义智能体
        
        Args:
            args: 命令行参数
            agent_config: 智能体配置字典
            session_id: 会话ID
            logger: 日志记录器
            
        Returns:
            自定义智能体实例
        """
        required_fields = ['name', 'prompt']
        for field in required_fields:
            if field not in agent_config:
                raise ValueError(f"Missing required field: {field}")
        
        return CustomAgent(
            args=args,
            agent_name=agent_config['name'],
            custom_prompt=agent_config['prompt'],
            description=agent_config.get('description', ''),
            category=agent_config.get('category', '自定义'),
            logger=logger,
            session_id=session_id
        )
    
    @staticmethod
    def create_from_user_input(args, session_id: str, logger: list = None) -> CustomAgent:
        """
        从用户输入创建自定义智能体
        
        Args:
            args: 命令行参数
            session_id: 会话ID
            logger: 日志记录器
            
        Returns:
            自定义智能体实例
        """
        print("\n=== 创建自定义智能体 ===")
        
        # 获取用户输入
        agent_name = input("请输入智能体名称: ").strip()
        if not agent_name:
            raise ValueError("智能体名称不能为空")
        
        print("请输入智能体的专业提示词（输入完成后按Ctrl+D或输入END结束）:")
        prompt_lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == 'END':
                    break
                prompt_lines.append(line)
            except EOFError:
                break
        
        custom_prompt = '\n'.join(prompt_lines)
        if not custom_prompt:
            raise ValueError("提示词不能为空")
        
        description = input("请输入智能体描述（可选）: ").strip()
        category = input("请输入分类（可选，默认为'自定义'）: ").strip() or "自定义"
        
        agent_config = {
            'name': agent_name,
            'prompt': custom_prompt,
            'description': description,
            'category': category
        }
        
        return CustomAgentFactory.create_agent(args, agent_config, session_id, logger)
    
    @staticmethod
    def create_temporary_agent(args, agent_name: str, prompt: str, logger: list = None) -> CustomAgent:
        """
        创建临时智能体（不注册到注册表）
        
        Args:
            args: 命令行参数
            agent_name: 智能体名称
            prompt: 提示词
            logger: 日志记录器
            
        Returns:
            临时自定义智能体
        """
        return CustomAgent(
            args=args,
            agent_name=agent_name,
            custom_prompt=prompt,
            description="临时智能体",
            category="临时",
            logger=logger,
            session_id=None  # 不注册
        )


class CustomAgentManager:
    """自定义智能体管理器"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.agent_registry = get_agent_registry()
        self.active_custom_agents: Dict[str, CustomAgent] = {}
    
    def create_custom_agent(self, args, agent_config: Dict, logger: list = None) -> CustomAgent:
        """创建并管理自定义智能体"""
        agent = CustomAgentFactory.create_agent(args, agent_config, self.session_id, logger)
        self.active_custom_agents[agent_config['name']] = agent
        return agent
    
    def get_custom_agent(self, agent_name: str) -> Optional[CustomAgent]:
        """获取自定义智能体"""
        return self.active_custom_agents.get(agent_name)
    
    def list_custom_agents(self) -> List[Dict[str, Any]]:
        """列出所有自定义智能体"""
        return [agent.get_agent_info() for agent in self.active_custom_agents.values()]
    
    def remove_custom_agent(self, agent_name: str) -> bool:
        """移除自定义智能体"""
        if agent_name in self.active_custom_agents:
            # 从注册表删除
            self.agent_registry.delete_custom_agent(self.session_id, agent_name)
            # 从活动列表删除
            del self.active_custom_agents[agent_name]
            logger.info(f"Removed custom agent: {agent_name}")
            return True
        return False
    
    def cleanup(self):
        """清理所有自定义智能体"""
        agent_names = list(self.active_custom_agents.keys())
        for agent_name in agent_names:
            self.remove_custom_agent(agent_name)
        logger.info(f"Cleaned up all custom agents for session {self.session_id}")