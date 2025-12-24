from typing import Dict, List, Optional, Any
from loguru import logger
from agents.base_agent import BaseAgent
from datetime import datetime

class SpecialtyAgent(BaseAgent):
    """专科智能体类 - 修复版本"""
    
    def __init__(self, args, specialty: str, agent_name: str = None, 
                 logger: list = None, custom_prompt: str = None):
        """
        初始化专科智能体 - 修复初始化顺序问题
        """
        self.specialty = specialty
        self.custom_prompt = custom_prompt
        self.agent_name = agent_name or f"{specialty}专家"
        
        # 先获取注册表配置
        self.agent_registry = self._get_default_registry()
        
        # 获取智能体配置
        agent_config = self.agent_registry.get_agent_config(self.specialty)
        
        if not agent_config:
            raise ValueError(f"专科智能体 '{self.specialty}' 在注册表中不存在")
        
        # 使用自定义提示词或注册表中的提示词
        prompt = self.custom_prompt or agent_config.get('prompt', '')
        
        # 构建完整的系统提示词
        full_prompt = self._build_specialty_prompt(prompt, self.specialty)
        
        # 正确处理logger参数
        if logger is None:
            from utils.logger import setup_logger
            self.logger = setup_logger(f"agent_{self.agent_name}")
        elif hasattr(logger, 'info'):  # 检查是否是真正的logger对象
            self.logger = logger
        else:
            # 如果传递的是列表，创建新的logger
            from utils.logger import setup_logger
            self.logger = setup_logger(f"agent_{self.agent_name}")

        # 最后调用父类初始化
        super().__init__(
            args=args,
            specialty=specialty,
            system_instruction=full_prompt,
            agent_name=self.agent_name,
            logger=logger
        )
            
        self.logger.info(f"初始化专科智能体: {specialty}")
    
    def _get_default_registry(self):
        """延迟获取默认注册表"""
        from agents.agent_registry import get_agent_registry
        return get_agent_registry()    
    
    def _build_specialty_prompt(self, base_prompt: str, specialty: str) -> str:
        """构建专科专用的提示词 - 保留原有设置"""
        current_date = datetime.now().strftime("%Y年%m月%d日")
        return f"""你是一位{specialty}的资深专家医生。{base_prompt}

请严格遵循以下指导原则：
1. 每次讨论都要基于之前所有讨论内容进行更加深入探讨
2. 特别关注之前各科专家提到的诊断、治疗与检查内容
3. 从{specialty}专业角度分析可能存在的风险和并发症
4. 必须提供详细的鉴别诊断分析，包括：
   - 支持某项诊断的临床证据和理由
   - 不支持某项诊断的排除依据和原因
   - 各种可能性按概率排序
5. 基于循证医学原则提出个体化建议
6. 考虑多学科协作的治疗方案整合

讨论要求：
- 每次发言都要引用和回应之前专家的观点
- 分析要基于最新的临床指南和证据
- 重点关注跨专科的协同治疗和风险管控
- 提供具体的检查建议和治疗时间节点

当前日期：{current_date}
请用专业、准确的语言进行深入分析。"""
      
    def analyze_clinical_case(self, medical_record: Dict, discussion_history: List[Dict] = None, specific_prompt: str = None) -> Dict[str, Any]:
        # 设置共享历史记录
        if discussion_history:
            self.set_shared_history(discussion_history)
        
        medical_text = self._extract_medical_text(medical_record)
        prompt_section = f"\n{specific_prompt}" if specific_prompt else ""
        
        # 构建包含历史上下文的提示
        history_context = self._format_discussion_history_for_prompt(discussion_history)
        
        message = f"""基于以下病例信息和讨论历史，请从{self.specialty}角度提供专业分析：

    【病历信息】
    {medical_text}

    【讨论历史】
    {history_context}

    【要求】
    请用500字以内简洁回答，可以包含：
    1. 涉及机制判断及理由
    2. 诊断和鉴别诊断建议及理由  
    3. 治疗建议及理由
    4. 检查建议及理由
    {prompt_section}
    请专注于{self.specialty}专业领域，根据上述要点进行总结回答，不用分点，提供精炼的专业汇总意见。"""
        
        try:
            # 使用chat方法保持历史记录连续性
            response = self.chat(message, temperature=0.3)  # 降低温度以获得更稳定的响应
            
            # 解析响应，确保简洁
            concise_response = self._make_response_concise(response)
            
            analysis_result = {
                "success": True,
                "specialty": self.specialty,
                "concise_analysis": concise_response,
                "word_count": len(concise_response),
                "timestamp": self._get_timestamp()
            }
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"临床病例分析错误: {e}")
            return {
                "success": False,
                "error": str(e),
                "specialty": self.specialty
            }
    def _format_discussion_history_for_prompt(self, discussion_history: List[Dict]) -> str:
        """格式化讨论历史用于提示词"""
        if not discussion_history:
            return "暂无讨论历史"
        
        formatted_history = []
        for i, round_data in enumerate(discussion_history[-6:], 1):  # 只取最近6轮
            round_num = round_data.get("round", i)
            formatted_history.append(f"第{round_num}轮讨论:")
            
            for contribution in round_data.get("contributions", []):
                agent = contribution.get("agent", "")
                analysis = contribution.get("contribution", {}).get("concise_analysis", "")
                if analysis:
                    short_analysis = analysis[:150] + "..." if len(analysis) > 150 else analysis
                    formatted_history.append(f"  {agent}: {short_analysis}")
        
        return "\n".join(formatted_history) if formatted_history else "暂无相关讨论历史"
    
    def _make_response_concise(self, response: str, max_words: int = 400) -> str:
        """确保响应简洁"""
        words = response.split()
        if len(words) <= max_words:
            return response
        
        # 如果超过字数限制，提取关键部分
        # 保留开头和结尾的重要信息
        important_parts = words[:50] + words[-50:]
        return ' '.join(important_parts) + "...[内容已精简]"
       
    def _extract_medical_text(self, medical_record: Dict) -> str:
        """提取病历文本 - 支持多种格式"""
        # 如果已经是字符串格式，直接返回
        if isinstance(medical_record, str):
            return medical_record
        
        # 如果是字典格式，提取关键信息
        if isinstance(medical_record, dict):
            # 优先使用自由文本字段
            if 'free_text' in medical_record:
                return medical_record['free_text']
            elif 'text' in medical_record:
                return medical_record['text']
            elif 'content' in medical_record:
                return medical_record['content']
            else:
                # 如果没有自由文本字段，将字典内容拼接成文本
                return self._dict_to_text(medical_record)
        
        # 其他格式转换为字符串
        return str(medical_record)
    
    def _dict_to_text(self, medical_dict: Dict) -> str:
        """将病历字典转换为文本 - 简洁格式"""
        text_parts = []
        
        # 按常见病历字段顺序组织
        common_fields = [
            ('chief_complaint', '主诉'),
            ('present_illness', '现病史'),
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
        
        return '\n'.join(text_parts)
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """解析分析响应"""
        return {
            "success": True,
            "specialty": self.specialty,
            "raw_response": response,
            "summary": self._extract_summary(response),
            "key_points": self._extract_key_points(response),
            "diagnosis_suggestions": self._extract_diagnosis_suggestions(response),
            "treatment_recommendations": self._extract_treatment_recommendations(response)
        }
    
    def _extract_summary(self, response: str) -> str:
        """提取摘要 - 改进版本"""
        # 尝试找到总结性语句
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        # 寻找包含总结关键词的句子
        summary_keywords = ['总结', '综上', '因此', '建议', '诊断']
        summary_lines = []
        
        for line in lines:
            if any(keyword in line for keyword in summary_keywords):
                summary_lines.append(line)
            elif len(line) > 30 and len(line) < 200:  # 适中长度的句子
                summary_lines.append(line)
        
        # 取前3个有意义的句子
        if summary_lines:
            return ' '.join(summary_lines[:3])
        else:
            # 如果没有明显总结，取前100个字符
            return response[:100] + '...' if len(response) > 100 else response
    
    def _extract_key_points(self, response: str) -> List[str]:
        """提取关键点 - 改进版本"""
        key_points = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            # 识别列表项
            if (line.startswith(('- ', '* ', '• ', '1.', '2.', '3.', '4.', '5.')) or
                line.startswith(('一、', '二、', '三、', '四、', '五、'))):
                key_points.append(line)
            # 识别重要陈述（包含关键词）
            elif (any(keyword in line for keyword in 
                     ['诊断', '治疗', '建议', '考虑', '可能', '需要']) and 
                  len(line) > 10 and len(line) < 150):
                key_points.append(line)
        
        return key_points[:8]  # 最多返回8个关键点
    
    def _extract_diagnosis_suggestions(self, response: str) -> List[str]:
        """提取诊断建议"""
        diagnosis_keywords = ['诊断', '考虑', '可能', '鉴别', '排除']
        suggestions = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if any(keyword in line for keyword in diagnosis_keywords):
                suggestions.append(line)
        
        return suggestions[:5]
    
    def _extract_treatment_recommendations(self, response: str) -> List[str]:
        """提取治疗建议"""
        treatment_keywords = ['治疗', '用药', '手术', '建议', '方案']
        recommendations = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if any(keyword in line for keyword in treatment_keywords):
                recommendations.append(line)
        
        return recommendations[:5]
    
    def _log_analysis(self, medical_record: Dict, question: str, result: Dict) -> None:
        """记录分析过程"""
        if self.logger is not None:
            log_entry = {
                "timestamp": self._get_timestamp(),
                "agent": self.agent_name,
                "specialty": self.specialty,
                "medical_record_preview": str(medical_record)[:100] + '...' if len(str(medical_record)) > 100 else str(medical_record),
                "question": question,
                "analysis_success": result.get("success", False),
                "summary": result.get("summary", "") 
            }
            self.logger.append(log_entry)
    
    def provide_differential_diagnosis(self, medical_record: Dict) -> Dict[str, Any]:
        """
        提供鉴别诊断 - 支持自由文本输入
        """
        medical_text = self._extract_medical_text(medical_record)
        
        message = f"""基于以下病例信息，请提供{self.specialty}相关的鉴别诊断：

病例信息:
{medical_text}

请按可能性从高到低列出鉴别诊断，并简要说明理由。"""
        
        try:
            response = self.chat_without_history(message)
            
            return {
                "success": True,
                "specialty": self.specialty,
                "differential_diagnosis": response,
                "formatted_ddx": self._format_ddx_response(response)
            }
            
        except Exception as e:
            logger.error(f"鉴别诊断错误: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _format_ddx_response(self, response: str) -> List[Dict]:
        """格式化鉴别诊断响应"""
        # 简单的解析逻辑，可根据需要增强
        diagnoses = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):  # 忽略注释行
                diagnoses.append({
                    "diagnosis": line[:100],  # 限制长度
                    "reasoning": "待进一步分析"
                })
        
        return diagnoses[:10]  # 最多返回10个诊断
    
    def suggest_treatment_plan(self, medical_record: Dict, diagnosis: str = None) -> Dict[str, Any]:
        """
        建议治疗方案 - 支持自由文本输入
        """
        medical_text = self._extract_medical_text(medical_record)
        
        message = f"""请基于以下病例信息建议治疗方案：
        
病例信息:
{medical_text}"""
        
        if diagnosis:
            message += f"\n\n初步诊断: {diagnosis}"
        
        message += f"""

请从{self.specialty}角度建议治疗方案，包括：
1. 药物治疗建议
2. 非药物治疗建议  
3. 随访计划
4. 注意事项"""
        
        try:
            response = self.chat_without_history(message)
            
            return {
                "success": True,
                "specialty": self.specialty,
                "treatment_plan": response,
                "structured_plan": self._parse_treatment_plan(response)
            }
            
        except Exception as e:
            logger.error(f"治疗方案建议错误: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _parse_treatment_plan(self, response: str) -> Dict[str, List]:
        """解析治疗方案"""
        # 简单的解析逻辑
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        return {
            "medications": [line for line in lines if any(word in line for word in ['用药', '药物', '治疗'])][:5],
            "procedures": [line for line in lines if any(word in line for word in ['手术', '操作', '治疗'])][:5],
            "follow_up": [line for line in lines if any(word in line for word in ['随访', '复查', '监测'])][:5],
            "notes": lines[:10]  # 返回前10行作为备注
        }

    def respond_to_user_question(self, question: str, context: Dict = None) -> Dict[str, Any]:
        """
        响应用户提问 - 增强版本
        """
        try:
            # 构建响应消息
            message = f"""用户向您提问：{question}

请基于您的专业知识提供专业、准确的回答。"""
            
            if context and context.get('discussion_context'):
                message += f"\n\n当前讨论背景：{context['discussion_context']}"
            
            if context and context.get('medical_record'):
                message += f"\n\n相关病例信息：{self._format_medical_record_for_analysis(context['medical_record'])}"
            
            # 使用chat_without_history确保响应独立
            response = self.chat_without_history(message)
            
            return {
                "success": True,
                "agent_name": self.agent_name,
                "question": question,
                "response": response,
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            self.logger.error(f"响应用户提问失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_name": self.agent_name
            }

    def respond_to_user_question(self, question: str, context: Dict = None, concise: bool = False) -> Dict[str, Any]:
        """
        响应用户提问 - 增强版本，支持简洁模式
        """
        try:
            # 构建响应消息
            if concise:
                # 简洁模式：限制回答长度
                message = f"""用户向您提问：{question}

    请基于您的专业知识和当前讨论背景，提供简洁、专业的回答（控制在200字以内）。

    要求：
    1. 直接回答问题核心
    2. 基于专业角度提供关键建议
    3. 避免冗长的解释
    4. 如需要更多信息请直接说明"""
            else:
                # 完整模式
                message = f"""用户向您提问：{question}

    请基于您的专业知识提供专业、准确的回答。"""
            
            if context and context.get('discussion_context'):
                message += f"\n\n当前讨论背景：{context['discussion_context']}"
            
            if context and context.get('medical_record'):
                message += f"\n\n相关病例信息：{self._format_medical_record_for_analysis(context['medical_record'])}"
            
            # 使用chat_without_history确保响应独立
            response = self.chat_without_history(message)
            
            # 如果启用简洁模式，控制回答长度
            if concise and len(response) > 200:
                response = response[:200] + "...[回答已精简]"
            
            return {
                "success": True,
                "agent_name": self.agent_name,
                "question": question,
                "response": response,
                "concise_mode": concise,
                "word_count": len(response),
                "timestamp": self._get_timestamp()
            }
            
        except Exception as e:
            self.logger.error(f"响应用户提问失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "agent_name": self.agent_name
            }

class SpecialtyAgentFactory:
    """专科智能体工厂类 - 优化版本"""
    
    @staticmethod
    def create_agent(args, specialty: str, prompt: str, agent_name: str = None, 
                    description: str = "", category: str = "", logger: list = None) -> SpecialtyAgent:
        """
        创建专科智能体
        
        Args:
            args: 命令行参数
            specialty: 专科名称
            prompt: 提示词
            agent_name: 智能体名称
            description: 描述
            category: 分类
            logger: 日志记录器
            
        Returns:
            专科智能体实例
        """
        return SpecialtyAgent(
            args=args,
            specialty=specialty,
            agent_name=agent_name,
            logger=logger,
            custom_prompt=prompt
        )
    
    @staticmethod
    def create_multiple_agents(args, agent_configs: List[Dict], logger: list = None) -> Dict[str, SpecialtyAgent]:
        """
        批量创建多个专科智能体
        
        Args:
            args: 命令行参数
            agent_configs: 智能体配置列表
            logger: 日志记录器
            
        Returns:
            智能体字典 {专科名: 智能体实例}
        """
        agents = {}
        for config in agent_configs:
            try:
                agent = SpecialtyAgentFactory.create_agent(
                    args=args,
                    specialty=config['specialty'],
                    prompt=config.get('prompt', ''),
                    agent_name=config.get('agent_name'),
                    logger=logger
                )
                agents[config['specialty']] = agent
                logger.info(f"成功创建专科智能体: {config['specialty']}")
            except Exception as e:
                logger.error(f"创建专科智能体失败 {config['specialty']}: {e}")
                continue
        
        return agents
    

class LogicAgent(BaseAgent):
    """逻辑检查智能体 - 负责检查讨论的逻辑一致性"""
    
    def __init__(self, args, specialty="逻辑检查", agent_name="LogicAgent", logger=None):
        system_prompt = """你是逻辑检查专家，负责分析医学讨论的逻辑一致性。
        检查内容包括：诊断推理的逻辑链条、证据支持、结论合理性等。"""
        
        super().__init__(args, specialty, system_prompt, agent_name, logger)
    
    def check_logic(self, reasoning_text: str) -> Dict[str, Any]:
        """检查推理逻辑"""
        message = f"""请分析以下医学推理的逻辑质量：
        
推理内容：
{reasoning_text}

请从以下维度评估：
1. 逻辑链条是否完整
2. 证据是否充分支持结论
3. 是否存在逻辑跳跃或矛盾
4. 推理的严谨性"""

        response = self.chat_without_history(message)
        
        return {
            "logic_score": self._extract_logic_score(response),
            "issues": self._identify_logic_issues(response),
            "suggestions": self._extract_suggestions(response),
            "full_analysis": response
        }
    
class DecisionMakersAgent(BaseAgent):
    """决策智能体 - 完整修复版本"""
        
    def __init__(self, args, specialty="决策专家", agent_name="DecisionMaker", logger=None):
        current_date = datetime.now().strftime("%Y年%m月%d日")
        
        system_prompt = f"""你是临床决策专家，负责整合各专科意见，形成统一的诊断、鉴别诊断和治疗方案。
    请基于各专科专家的分析，综合考虑患者的整体情况，提出最终建议。

    请确保你的建议包括：
    1. 综合诊断意见与鉴别诊断（按可能性排序）
    2. 推荐的治疗方案（分阶段说明）
    3. 必要的辅助检查建议
    4. 随访计划和预后评估
    5. 关键风险提示和注意事项

    特别要求：
    - 整合所有专科专家的意见，突出共识和分歧点
    - 基于多学科讨论制定个体化方案
    - 明确治疗优先级和时间节点
    - 强调患者安全和生活质量考量

    当前系统日期：{current_date}
    请提供专业、全面的最终决策，不要包含个人签名。"""

        super().__init__(args, specialty, system_prompt, agent_name, logger)
    
    def make_final_decision(self, agents: Dict, discussion_log: List, medical_context: Dict) -> Dict[str, Any]:
        """生成最终决策"""
        try:
            # 提取所有智能体的分析结果
            all_analyses = []
            for round_log in discussion_log:
                for contribution in round_log.get("contributions", []):
                    if "contribution" in contribution and contribution["contribution"].get("success"):
                        analysis = contribution["contribution"].get("concise_analysis", "")
                        all_analyses.append(f"{contribution['agent']}: {analysis}")
            
            # 构建更结构化的决策消息
            message = self._build_decision_message(medical_context, all_analyses)
            
            # 使用chat_without_history确保决策独立性
            response = self.chat_without_history(message)
            
            return self._parse_decision_response(response)
            
        except Exception as e:
            logger.error(f"最终决策生成失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _build_decision_message(self, medical_context: Dict, analyses: List[str]) -> str:
        """构建决策消息"""
        current_date = datetime.now().strftime("%Y年%m月%d日")
        medical_record = medical_context.get('medical_record', '')
            
        return f"""作为临床决策专家，请基于以下多专科讨论结果，形成最终临床决策：

【病历摘要】
{medical_record}

【讨论问题】  
{medical_context.get('question', '')}

【各专科意见汇总】
{chr(10).join(analyses)}

【决策要求】
请提供结构化的最终建议：
1. 综合诊断意见（按可能性排序，附支持证据）
2. 推荐的多学科治疗方案（分阶段、分专科）
3. 必要的辅助检查建议和优先级
4. 后续治疗计划和预后评估
5. 关键风险提示和跨专科注意事项

决策日期：{current_date}
请确保建议基于各专科专家的深度分析，并考虑患者的整体情况。不要包含个人签名。"""

    def _parse_decision_response(self, response: str) -> Dict[str, Any]:
        """解析决策响应"""
        return {
            "success": True,
            "final_decision": response,
            "timestamp": self._get_timestamp()
        }   