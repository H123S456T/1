import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import queue
import re
from loguru import logger


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from interface.cli_interface import CLIInterface

class InterventionType(Enum):
    """用户介入类型枚举"""
    QUESTION_TO_AGENT = "question_to_agent"      # 向特定智能体提问
    BROADCAST_QUESTION = "broadcast_question"    # 向所有智能体提问
    ADD_INFORMATION = "add_information"          # 补充信息
    REQUEST_CLARIFICATION = "request_clarification" # 请求澄清
    DIRECT_COMMAND = "direct_command"            # 直接命令（如跳过、终止等）
    CHANGE_FOCUS = "change_focus"               # 改变讨论焦点


@dataclass
class UserIntervention:
    """用户介入数据结构"""
    intervention_id: str
    type: InterventionType
    timestamp: datetime
    user_id: str
    session_id: str
    content: Dict[str, Any]  # 介入内容，根据类型不同而不同
    status: str = "pending"  # pending, processing, completed, failed
    response: Optional[Dict[str, Any]] = None


class UserInteractionManager:
    """用户交互管理器"""
    
    def __init__(self, discussion_engine, interface: 'CLIInterface'):
        self.discussion_engine = discussion_engine
        self.interface = interface
        self.pending_interventions = queue.Queue()
        self.active_interventions: Dict[str, UserIntervention] = {}
        self.intervention_history: List[UserIntervention] = []
        
        # 启动干预处理线程
        self._processing_thread = threading.Thread(target=self._process_interventions, daemon=True)
        self._stop_processing = False
        self._processing_thread.start()
        
        logger.info("用户交互管理器初始化完成")

    def check_for_intervention(self, round_num: int, current_agent: str = None) -> bool:
        """
        检查是否有用户介入请求
        返回True表示有介入请求需要处理
        """
        try:
            # 非阻塞检查用户输入
            if self.interface.has_user_input(timeout=0.1):
                return True
            
            # 定期检查（每1轮）是否应该提示用户介入
            if round_num % 1 == 0:
                if self.interface.should_prompt_for_intervention():
                    return True
                    
        except Exception as e:
            logger.error(f"检查用户介入时出错: {e}")
        
        return False

    def get_intervention(self) -> Optional[UserIntervention]:
        """获取用户介入请求"""
        try:
            if not self.pending_interventions.empty():
                return self.pending_interventions.get_nowait()
        except queue.Empty:
            pass
        return None

    def handle_intervention(self, intervention: UserIntervention) -> Dict[str, Any]:
        """处理用户介入请求"""
        intervention.status = "processing"
        self.active_interventions[intervention.intervention_id] = intervention
        
        try:
            result = self._execute_intervention(intervention)
            intervention.status = "completed"
            intervention.response = result
            logger.info(f"成功处理用户介入: {intervention.type}")
        except Exception as e:
            intervention.status = "failed"
            intervention.response = {"error": str(e)}
            logger.error(f"处理用户介入失败: {e}")
        
        self.intervention_history.append(intervention)
        del self.active_interventions[intervention.intervention_id]
        
        return intervention.response

    def _execute_intervention(self, intervention: UserIntervention) -> Dict[str, Any]:
        """执行具体的介入操作"""
        handler_map = {
            InterventionType.QUESTION_TO_AGENT: self._handle_question_to_agent,
            InterventionType.BROADCAST_QUESTION: self._handle_broadcast_question,
            InterventionType.ADD_INFORMATION: self._handle_add_information,
            InterventionType.REQUEST_CLARIFICATION: self._handle_request_clarification,
            InterventionType.DIRECT_COMMAND: self._handle_direct_command,
            InterventionType.CHANGE_FOCUS: self._handle_change_focus,
        }
        
        handler = handler_map.get(intervention.type)
        if handler:
            return handler(intervention)
        else:
            raise ValueError(f"未知的介入类型: {intervention.type}")

    def _handle_question_to_agent(self, intervention: UserIntervention) -> Dict[str, Any]:
        """处理向特定智能体提问"""
        target_agent = intervention.content.get('target_agent')
        question = intervention.content.get('question')
        
        if not target_agent or not question:
            raise ValueError("缺少目标智能体或问题内容")
        
        # 获取目标智能体
        agent = self.discussion_engine.agents.get(target_agent)
        if not agent:
            raise ValueError(f"智能体 '{target_agent}' 不存在")
        
        # 构建提问消息
        message = f"用户提问: {question}\n\n请基于当前讨论上下文回答这个问题。"
        
        # 调用智能体回答
        response = agent.chat(message)
        
        return {
            "target_agent": target_agent,
            "question": question,
            "response": response,
            "timestamp": datetime.now().isoformat()
        }

    def _handle_broadcast_question(self, intervention: UserIntervention) -> Dict[str, Any]:
        """处理向所有智能体广播提问"""
        question = intervention.content.get('question')
        if not question:
            raise ValueError("缺少问题内容")
        
        responses = {}
        message = f"用户向所有专家提问: {question}\n\n请基于您的专业领域回答这个问题。"
        
        for agent_name, agent in self.discussion_engine.agents.items():
            try:
                response = agent.chat(message)
                responses[agent_name] = response
            except Exception as e:
                responses[agent_name] = f"回答时出错: {str(e)}"
                logger.error(f"智能体 {agent_name} 回答失败: {e}")
        
        return {
            "question": question,
            "responses": responses,
            "timestamp": datetime.now().isoformat()
        }

    def _handle_add_information(self, intervention: UserIntervention) -> Dict[str, Any]:
        """处理用户补充信息"""
        information = intervention.content.get('information')
        information_type = intervention.content.get('type', 'general')
        
        if not information:
            raise ValueError("缺少补充信息内容")
        
        # 更新讨论上下文
        self.discussion_engine.add_user_information(information, information_type)
        
        # 通知所有智能体有新信息
        notification = f"用户提供了新的{information_type}信息: {information}"
        for agent in self.discussion_engine.agents.values():
            agent.update_context(notification)
        
        return {
            "information_type": information_type,
            "information": information,
            "timestamp": datetime.now().isoformat(),
            "message": "信息已成功添加到讨论上下文"
        }

    def _handle_request_clarification(self, intervention: UserIntervention) -> Dict[str, Any]:
        """处理请求澄清"""
        clarification_request = intervention.content.get('clarification_request')
        target_agent = intervention.content.get('target_agent')
        
        if not clarification_request:
            raise ValueError("缺少澄清请求内容")
        
        if target_agent:
            # 向特定智能体请求澄清
            agent = self.discussion_engine.agents.get(target_agent)
            if not agent:
                raise ValueError(f"智能体 '{target_agent}' 不存在")
            
            message = f"用户请求澄清: {clarification_request}"
            response = agent.chat(message)
            
            return {
                "target_agent": target_agent,
                "clarification_request": clarification_request,
                "response": response,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # 向所有智能体请求澄清
            responses = {}
            message = f"用户请求澄清: {clarification_request}"
            
            for agent_name, agent in self.discussion_engine.agents.items():
                try:
                    response = agent.chat(message)
                    responses[agent_name] = response
                except Exception as e:
                    responses[agent_name] = f"澄清时出错: {str(e)}"
            
            return {
                "clarification_request": clarification_request,
                "responses": responses,
                "timestamp": datetime.now().isoformat()
            }

    def _handle_direct_command(self, intervention: UserIntervention) -> Dict[str, Any]:
        """处理直接命令"""
        command = intervention.content.get('command')
        parameters = intervention.content.get('parameters', {})
        
        command_handlers = {
            'skip_round': self._handle_skip_round,
            'terminate_discussion': self._handle_terminate_discussion,
            'change_rounds': self._handle_change_rounds,
            'pause_discussion': self._handle_pause_discussion,
            'resume_discussion': self._handle_resume_discussion,
        }
        
        handler = command_handlers.get(command)
        if handler:
            return handler(parameters)
        else:
            raise ValueError(f"未知命令: {command}")

    def _handle_skip_round(self, parameters: Dict) -> Dict[str, Any]:
        """处理跳过当前轮命令"""
        self.discussion_engine.skip_current_round = True
        return {"message": "已跳过当前轮讨论", "command": "skip_round"}

    def _handle_terminate_discussion(self, parameters: Dict) -> Dict[str, Any]:
        """处理终止讨论命令"""
        self.discussion_engine.terminate_discussion = True
        return {"message": "讨论已终止", "command": "terminate_discussion"}

    def _handle_change_rounds(self, parameters: Dict) -> Dict[str, Any]:
        """处理改变讨论轮数命令"""
        new_rounds = parameters.get('new_rounds')
        if new_rounds and new_rounds > 0:
            self.discussion_engine.discussion_rounds = new_rounds
            return {
                "message": f"讨论轮数已改为 {new_rounds}",
                "command": "change_rounds",
                "new_rounds": new_rounds
            }
        else:
            raise ValueError("无效的轮数")

    def _handle_pause_discussion(self, parameters: Dict) -> Dict[str, Any]:
        """处理暂停讨论命令"""
        self.discussion_engine.pause_discussion = True
        return {"message": "讨论已暂停", "command": "pause_discussion"}

    def _handle_resume_discussion(self, parameters: Dict) -> Dict[str, Any]:
        """处理恢复讨论命令"""
        self.discussion_engine.pause_discussion = False
        return {"message": "讨论已恢复", "command": "resume_discussion"}

    def _handle_change_focus(self, intervention: UserIntervention) -> Dict[str, Any]:
        """处理改变讨论焦点"""
        new_focus = intervention.content.get('new_focus')
        if not new_focus:
            raise ValueError("缺少新的讨论焦点")
        
        # 更新讨论焦点
        self.discussion_engine.discussion_focus = new_focus
        
        # 通知所有智能体焦点变化
        notification = f"讨论焦点已改为: {new_focus}"
        for agent in self.discussion_engine.agents.values():
            agent.update_focus(new_focus)
        
        return {
            "message": f"讨论焦点已改为: {new_focus}",
            "new_focus": new_focus,
            "timestamp": datetime.now().isoformat()
        }

    def submit_intervention(self, intervention_data: Dict[str, Any]) -> str:
        """提交用户介入请求"""
        intervention_id = f"intervention_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        intervention = UserIntervention(
            intervention_id=intervention_id,
            type=InterventionType(intervention_data['type']),
            timestamp=datetime.now(),
            user_id=intervention_data.get('user_id', 'unknown'),
            session_id=intervention_data.get('session_id', 'unknown'),
            content=intervention_data.get('content', {})
        )
        
        self.pending_interventions.put(intervention)
        logger.info(f"已提交用户介入请求: {intervention.type}")
        
        return intervention_id

    def get_intervention_status(self, intervention_id: str) -> Optional[UserIntervention]:
        """获取介入请求状态"""
        if intervention_id in self.active_interventions:
            return self.active_interventions[intervention_id]
        
        for intervention in self.intervention_history:
            if intervention.intervention_id == intervention_id:
                return intervention
        
        return None

    def _process_interventions(self):
        """处理介入请求的后台线程"""
        while not self._stop_processing:
            try:
                intervention = self.pending_interventions.get(timeout=1)
                if intervention:
                    self.handle_intervention(intervention)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"处理介入请求时出错: {e}")

    def stop_processing(self):
        """停止处理线程"""
        self._stop_processing = True
        if self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5)

    def get_intervention_history(self, session_id: str = None) -> List[UserIntervention]:
        """获取介入历史"""
        if session_id:
            return [i for i in self.intervention_history if i.session_id == session_id]
        return self.intervention_history

    def clear_pending_interventions(self):
        """清空待处理的介入请求"""
        while not self.pending_interventions.empty():
            try:
                self.pending_interventions.get_nowait()
            except queue.Empty:
                break


class UserInputParser:
    """用户输入解析器"""
    
    @staticmethod
    def parse_intervention_command(user_input: str) -> Dict[str, Any]:
        """解析用户输入的介入命令"""
        user_input = user_input.strip()
        
        # 直接命令解析
        direct_commands = {
            '跳过': ('skip_round', {}),
            '终止': ('terminate_discussion', {}),
            '暂停': ('pause_discussion', {}),
            '继续': ('resume_discussion', {}),
        }
        
        for cmd, (command, params) in direct_commands.items():
            if cmd in user_input:
                return {
                    'type': InterventionType.DIRECT_COMMAND.value,
                    'content': {'command': command, 'parameters': params}
                }
        
        # 提问模式解析
        question_patterns = [
            (r'问(.+?)：(.+)', 'specific'),  # 问智能体：问题
            (r'向(.+?)提问：(.+)', 'specific'),  # 向智能体提问：问题
            (r'(.+?)：(.+)', 'specific'),  # 智能体：问题
            (r'大家(.+)', 'broadcast'),  # 大家问题
            (r'全体(.+)', 'broadcast'),  # 全体问题
        ]
        
        for pattern, q_type in question_patterns:
            match = re.match(pattern, user_input)
            if match:
                if q_type == 'specific':
                    agent_name = match.group(1).strip()
                    question = match.group(2).strip()
                    return {
                        'type': InterventionType.QUESTION_TO_AGENT.value,
                        'content': {'target_agent': agent_name, 'question': question}
                    }
                else:  # broadcast
                    question = match.group(1).strip()
                    return {
                        'type': InterventionType.BROADCAST_QUESTION.value,
                        'content': {'question': question}
                    }
        
        # 补充信息模式
        info_patterns = [
            (r'补充信息：(.+)', 'general'),
            (r'新增信息：(.+)', 'general'),
            (r'检查结果：(.+)', 'test_result'),
            (r'化验结果：(.+)', 'lab_result'),
            (r'影像学：(.+)', 'imaging'),
        ]
        
        for pattern, info_type in info_patterns:
            match = re.match(pattern, user_input)
            if match:
                information = match.group(1).strip()
                return {
                    'type': InterventionType.ADD_INFORMATION.value,
                    'content': {'information': information, 'type': info_type}
                }
        
        # 默认作为广播问题处理
        return {
            'type': InterventionType.BROADCAST_QUESTION.value,
            'content': {'question': user_input}
        }