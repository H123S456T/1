#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger
from threading import Thread, Event
import queue
import uuid 

from agents.agent_registry import AgentRegistry
from agents.specialty_agents import SpecialtyAgent, LogicAgent, DecisionMakersAgent
from utils.config import ClinicalConfig
from utils.logger import setup_logger

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from interface.cli_interface import CLIInterface

class ClinicalDiscussionEngine:
    """
    临床多智能体讨论引擎
    负责协调多个医学专科智能体进行病例讨论
    """
    def __init__(self, args, user_session, interface: 'CLIInterface' = None):
        self.args = args
        self.session = user_session
        self.interface = interface
        self.config = ClinicalConfig()

        if self.interface is None:
            self.interface = self._create_default_interface()
        
        # 讨论状态
        self.is_running = False
        self.current_round = 0
        self.max_rounds = getattr(args, 'discussion_rounds', 3)
        self.skip_remaining_agents = False  

        self.discussion_config = {
            "rounds": getattr(args, 'discussion_rounds', 3),
            "user_participation": False,  # 默认不参与讨论
            "auto_save": True,
            "export_format": "json"
        }        
        # 数据存储
        self.discussion_log = []
        self.user_interventions = []
        self.medical_context = {}
        
        # 智能体管理
        self.agent_registry = AgentRegistry()
        self.agents = {}
        self.logic_agent = None
        self.decision_agent = None
        
        # 用户交互
        self.user_input_queue = queue.Queue()
        self.user_intervention_event = Event()
        
        # 初始化日志
        self.logger = setup_logger("discussion_engine")

    def _create_default_interface(self):
        """创建默认的接口适配器"""
        class DefaultInterface:
            def get_user_input(self, prompt="", timeout=None):
                return None
            def has_user_input(self, timeout=0):
                return False
            def should_prompt_for_intervention(self):
                return False
   
    def initialize_discussion(self, medical_record: str, discussion_question: str, 
                            selected_agent_names: List[str]) -> bool:
        """
        初始化讨论环境
        """
        try:
            self.medical_context = {
                "medical_record": medical_record,
                "question": discussion_question,
                "selected_agents": selected_agent_names,
                "start_time": datetime.now().isoformat(),
                "user_id": self.session.get('user_id', 'unknown')
            }
            
            # 初始化智能体
            self._initialize_agents(selected_agent_names)            

            # 确保正确初始化逻辑检查和决策者智能体
            try:
                self.logic_agent = LogicAgent(
                    args=self.args,
                    specialty="逻辑检查智能体",
                    agent_name="LogicAgent",
                    logger=self.logger
                )
                
                self.decision_agent = DecisionMakersAgent(
                    args=self.args,
                    specialty="决策专家智能体", 
                    agent_name="DecisionMaker",
                    logger=self.logger
                )
                self.logger.info("逻辑检查和决策智能体初始化成功")
            except Exception as e:
                self.logger.error(f"逻辑检查和决策智能体初始化失败: {e}")
            
            # 添加共享历史记录管理
            self.shared_discussion_history = []
            
            self.logger.info(f"讨论引擎初始化成功，选择了 {len(selected_agent_names)} 个智能体")
            return True
            
        except Exception as e:
            self.logger.error(f"讨论引擎初始化失败: {e}")
            return False
 
    def _generate_final_summary(self) -> Dict[str, Any]:
        """生成最终讨论汇总 - 增强版本，包含广播问题"""
        self.logger.info("生成最终讨论汇总")
        
        try:
            # 检查decision_agent是否已初始化
            if self.decision_agent is None:
                self.logger.warning("决策智能体未初始化")
                return self._generate_backup_summary()
            
            # 提取所有讨论内容，包括广播问题
            all_discussion_content = []
            for round_data in self.discussion_log:
                round_type = round_data.get("type", "normal")
                
                if round_type == "broadcast_question":
                    question = round_data.get("question", "")
                    all_discussion_content.append(f"广播提问: {question}")
                    
                    for contribution in round_data.get("contributions", []):
                        agent = contribution.get("agent", "")
                        response = contribution.get("response", "")
                        all_discussion_content.append(f"{agent}: {response}")
                else:
                    for contribution in round_data.get("contributions", []):
                        agent = contribution.get("agent", "")
                        analysis = contribution.get("contribution", {}).get("concise_analysis", "")
                        if analysis:
                            all_discussion_content.append(f"{agent}: {analysis}")
            
            # 决策者智能体生成汇总
            final_decision = self.decision_agent.make_final_decision(
                agents=self.agents,
                discussion_log=self.discussion_log,
                medical_context=self.medical_context
            )
            
            # 确保final_decision是字典类型
            if isinstance(final_decision, str):
                final_decision = {"summary": final_decision}

            # 生成临床质量评估
            quality_assessment = self._assess_discussion_quality()
            
            summary = {
                "medical_context": self.medical_context,
                "discussion_summary": final_decision,
                "quality_assessment": quality_assessment,
                "discussion_log": self.discussion_log,
                "user_interventions": self.user_interventions,
                "metadata": {
                    "total_rounds": len([r for r in self.discussion_log if r.get("type") == "normal"]),
                    "broadcast_rounds": len([r for r in self.discussion_log if r.get("type") == "broadcast_question"]),
                    "intervention_rounds": len([r for r in self.discussion_log if r.get("type") == "intervention"]),
                    "total_agents": len(self.agents),
                    "duration": self._calculate_duration(),
                    "generated_at": datetime.now().isoformat()
                }
            }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"生成最终汇总失败: {e}")
            return self._generate_backup_summary()

    def _generate_backup_summary(self) -> Dict[str, Any]:
        """备用汇总方法，当决策智能体不可用时使用"""
        self.logger.info("使用备用汇总方法")
        
        # 简单汇总所有智能体的发言
        all_contributions = []
        for round_log in self.discussion_log:
            for contribution in round_log.get("contributions", []):
                if "contribution" in contribution:
                    all_contributions.append({
                        "agent": contribution["agent"],
                        "analysis": contribution["contribution"].get("concise_analysis", ""),
                        "timestamp": contribution["timestamp"]
                    })
        
        # 生成简单总结
        summary_text = "多专科讨论汇总：\n"
        for contrib in all_contributions:
            summary_text += f"{contrib['agent']}: {contrib['analysis']}\n"
        
        return {
            "status": "completed_with_backup",
            "summary": summary_text,
            "contributions": all_contributions,
            "total_rounds": self.current_round,
            "total_contributions": len(all_contributions)
        }
   
    def _initialize_agents(self, agent_names: List[str]):
        """初始化选择的智能体 - 使用动态创建"""
        self.agents = {}
        # 只初始化选择的智能体，而不是所有可用智能体
        available_agents = self.agent_registry.get_available_agents(
            self.session.get('session_id')
        )
        
        for agent_name in agent_names:
            if agent_name in available_agents:
                # 动态创建专科智能体
                agent = self.agent_registry.create_specialty_agent(
                    args=self.args,
                    specialty=agent_name,
                    agent_name=agent_name,
                    logger=self.logger 
                )
                self.agents[agent_name] = agent
                self.logger.debug(f"智能体 {agent_name} 初始化成功")
            else:
                self.logger.warning(f"智能体 {agent_name} 不存在，跳过初始化")
        
        self.logger.info(f"成功初始化 {len(agent_names)} 个智能体（共选择 {len(agent_names)} 个）")
    
    def add_agent_dynamically(self, specialty: str):
        """动态添加专科智能体"""
        try:
            agent = self.agent_registry.create_specialty_agent(
                args=self.args,
                specialty=specialty,
                logger=self.discussion_log
            )
            self.agents[specialty] = agent
            self.logger.info(f"动态添加专科智能体: {specialty}")
            return True
        except Exception as e:
            self.logger.error(f"动态添加智能体失败 {specialty}: {e}")
            return False

    def start_discussion(self) -> Dict[str, Any]:
        """开始讨论 - 确保返回完整的数据结构"""
        self.is_running = True
        self.current_round = 0
        
        self.logger.info("开始多智能体临床讨论")
        
        try:
            # 执行多轮讨论
            for round_num in range(1, self.max_rounds + 1):
                self.current_round = round_num
                
                if not self.is_running:
                    break
                
                self.logger.info(f"开始第 {round_num} 轮讨论")
                
                # 执行单轮讨论
                round_result = self._execute_discussion_round(round_num)
                self.discussion_log.append(round_result)
                
                # 检查用户是否要介入
                if self._check_user_intervention():
                    self._handle_user_intervention()
                
                # 轮次间延迟
                time.sleep(1)
            
            # 生成最终汇总
            if self.is_running:
                final_summary = self._generate_final_summary()
                self.medical_context["end_time"] = datetime.now().isoformat()
                self.medical_context["status"] = "completed"
                
                # === 修复：构建完整的讨论结果数据 ===
                complete_result = {
                    "metadata": {
                        "discussion_id": str(uuid.uuid4())[:8],
                        "user_id": self.medical_context.get("user_id", "unknown"),
                        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                        "created_at": datetime.now().isoformat(),
                        "agents_used": self.medical_context.get("selected_agents", []),
                        "rounds": self.current_round,
                        "medical_record_length": len(self.medical_context.get("medical_record", "")),
                        "question_length": len(self.medical_context.get("question", "")),
                        "rounds_completed": self.current_round
                    },
                    "medical_context": {
                        "medical_record": self.medical_context.get("medical_record", ""),
                        "question": self.medical_context.get("question", ""),
                        "user_additional_info": self.medical_context.get("user_additional_info", "")
                    },
                    "discussion_process": {
                        "discussion_log": self.discussion_log,
                        "user_interventions": self.user_interventions,
                        "logic_reports": self._collect_logic_reports()
                    },
                    "clinical_summary": final_summary.get("discussion_summary", 
                                                         final_summary.get("summary", {})),
                    "evaluation_metrics": final_summary.get("quality_assessment", {})
                }
                
                return complete_result
            else:
                return self._create_interrupted_result()
                
        except Exception as e:
            self.logger.error(f"讨论过程中发生错误: {e}")
            return self._create_error_result(str(e))
        finally:
            self.is_running = False

    def _collect_logic_reports(self) -> List[Dict]:
        """收集逻辑检查报告"""
        logic_reports = []
        for round_log in self.discussion_log:
            for contribution in round_log.get("contributions", []):
                if "logic_report" in contribution:
                    logic_reports.append({
                        "agent": contribution["agent"],
                        "round": round_log["round"],
                        "report": contribution["logic_report"]
                    })
        return logic_reports

    def _create_interrupted_result(self) -> Dict[str, Any]:
        """创建被中断的讨论结果"""
        return {
            "metadata": {
                "discussion_id": str(uuid.uuid4())[:8],
                "status": "interrupted",
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "rounds_completed": self.current_round
            },
            "error": "讨论被用户中断"
        }

    def _create_error_result(self, error_msg: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            "metadata": {
                "discussion_id": str(uuid.uuid4())[:8],
                "status": "error",
                "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
            },
            "error": error_msg
        }
    
    def _check_user_intervention(self) -> bool:
        """检查用户介入 - 根据配置决定是否启用"""
        # 如果配置为无需人工介入，直接返回False
        if hasattr(self, 'discussion_config') and not self.discussion_config.get('user_participation', False):
            return False
        
        try:
            return self.interface.has_user_input(timeout=0.1)
        except Exception as e:
            self.logger.error(f"检查用户介入失败: {e}")
            return False

    def _check_user_intervention_after_contribution(self) -> bool:
        """检查用户是否要在发言后介入 - 立即显示选项"""
        # 如果配置为无需人工介入，直接返回False
        if hasattr(self, 'discussion_config') and not self.discussion_config.get('user_participation', False):
            return False
        
        try:
            # 立即显示介入选项，不等待回车
            print("💡" * 4 + " 是否介入讨论？")
            print("选项: 1-向智能体提问, 2-向所有提问, 3-补充信息, 4-跳过轮次, 5-终止讨论, 回车键-继续", end='', flush=True)
            
            # 带超时的输入
            user_input = input()
            
            if user_input and user_input.strip() in ['1', '2', '3', '4', '5']:
                return True
            return False
                    
        except Exception as e:
            self.logger.error(f"检查用户介入失败: {e}")
            return False
        
    def _get_user_intervention(self) -> Optional[Dict]:
        """获取用户介入请求 - 修复属性引用错误"""
        try:
            # 修复：使用正确的interface属性
            if hasattr(self, 'interface') and hasattr(self.interface, 'get_structured_intervention_prompt'):
                intervention = self.interface.get_structured_intervention_prompt()
                return intervention
                        
        except Exception as e:
            self.logger.error(f"获取用户介入失败: {e}")
            # 返回简化版本作为后备
            return self._get_simple_intervention_prompt()

    def _execute_discussion_round(self, round_num: int) -> Dict[str, Any]:
        """
        执行单轮讨论 - 使用阻塞式用户介入
        """
        round_log = {
            "round": round_num,
            "timestamp": datetime.now().isoformat(),
            "contributions": [],
            "logic_reports": []
        }
        
        # 重置跳过标志
        self.skip_remaining_agents = False
        
        # 获取当前讨论历史
        current_history = self._get_current_discussion_context()

        # 各智能体依次发言
        for agent_name, agent in self.agents.items():
            # 检查是否要跳过剩余发言
            if self.skip_remaining_agents:
                self.logger.info(f"跳过剩余发言: {agent_name}")
                break
                
            try:
                # 设置共享历史记录
                agent.set_shared_history(current_history)
                
                analysis_prompt = f"""作为{agent_name}专家，请基于之前所有讨论内容进行深度分析..."""
                
                # 智能体分析病例
                contribution = agent.analyze_clinical_case(
                    {"free_text": self.medical_context["medical_record"]},
                    discussion_history=current_history,
                    specific_prompt=analysis_prompt
                )
                
                # 记录贡献
                round_log["contributions"].append({
                    "agent": agent_name,
                    "contribution": contribution,
                    "timestamp": datetime.now().isoformat()
                })
                
                # 将本次发言添加到共享历史
                self._add_to_shared_history(
                    agent_name, 
                    contribution.get("concise_analysis", "无分析结果")
                )
                
                print(f"第{round_num}轮 - {agent_name} 发言:")
                print(f"  分析: {contribution.get('concise_analysis', '')}")
                print(f"  字数: {contribution.get('word_count', 0)}")
                print("-" * 50)
                
                # === 简化的阻塞式用户介入检查 ===
                if hasattr(self, 'discussion_config') and self.discussion_config.get('user_participation', False):
                    user_intervention = self._get_blocking_user_intervention(agent_name)
                    if user_intervention:
                        if self._handle_user_intervention(user_intervention):
                            # 如果用户选择中断或跳过，立即返回
                            if user_intervention.get('type') in ['interrupt', 'skip_round']:
                                return round_log
                        # 继续处理其他介入类型
                    
            except Exception as e:
                self.logger.error(f"智能体 {agent_name} 发言失败: {e}")
                round_log["contributions"].append({
                    "agent": agent_name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        return round_log

    def _get_blocking_user_intervention(self, current_agent: str = None) -> Optional[Dict]:
        """
        阻塞式获取用户介入选择
        直接等待用户输入，不设置超时
        """
        if not hasattr(self, 'discussion_config') or not self.discussion_config.get('user_participation', False):
            return None
        
        try:
            print("💡" * 4 + " 是否介入讨论？")
            print("选项: 1-向智能体提问, 2-向所有提问, 3-补充信息, 4-跳过轮次, 5-终止讨论, 回车键-继续 \n", end='', flush=True)
            
            while True:
                choice = input("请选择操作编号 (1-5) 或直接按回车继续: ").strip()
                
                if choice == "":
                    # 用户按回车，继续讨论
                    print("讨论继续...")
                    return None
                elif choice in ['1', '2', '3', '4', '5']:
                    return self._get_intervention_details(choice, current_agent)
                else:
                    print("无效输入，请选择 1-5 或直接按回车")
                    
        except Exception as e:
            self.logger.error(f"获取用户介入失败: {e}")
            return None
 
    def _get_intervention_details(self, choice: str, current_agent: str = None) -> Dict[str, Any]:
        """
        根据用户选择获取介入详情 - 阻塞式输入
        """
        intervention_map = {
            '1': 'question_to_agent',
            '2': 'broadcast_question',
            '3': 'add_information', 
            '4': 'skip_round',
            '5': 'interrupt'
        }
        
        intervention_type = intervention_map.get(choice)
        if not intervention_type:
            return None
        
        try:
            if intervention_type == 'question_to_agent':
                # 显示可用智能体
                print("\n可用智能体:")
                agents = list(self.agents.keys())
                for i, agent in enumerate(agents, 1):
                    print(f"{i}. {agent}")
                
                agent_choice = input("请选择智能体编号或名称: ").strip()
                
                # 解析智能体选择
                target_agent = None
                if agent_choice.isdigit() and 1 <= int(agent_choice) <= len(agents):
                    target_agent = agents[int(agent_choice) - 1]
                elif agent_choice in agents:
                    target_agent = agent_choice
                else:
                    # 默认使用当前智能体
                    target_agent = current_agent or agents[0] if agents else None
                
                if not target_agent:
                    print("无效的智能体选择")
                    return None
                    
                question = input("请输入您的问题: ").strip()
                if not question:
                    print("问题不能为空")
                    return None
                    
                return {
                    'type': intervention_type,
                    'target_agent': target_agent,
                    'question': question
                }
                
            elif intervention_type == 'broadcast_question':
                question = input("请输入要向所有智能体提问的问题: ").strip()
                if not question:
                    print("问题不能为空")
                    return None
                    
                return {
                    'type': intervention_type,
                    'question': question
                }
                
            elif intervention_type == 'add_information':
                information = input("请输入要补充的病例信息: ").strip()
                if not information:
                    print("信息不能为空")
                    return None
                    
                return {
                    'type': intervention_type,
                    'information': information
                }
                
            elif intervention_type == 'skip_round':
                return {'type': intervention_type}
                
            elif intervention_type == 'interrupt':
                return {'type': intervention_type}
                
        except Exception as e:
            self.logger.error(f"获取介入详情失败: {e}")
        
        return None

    def _handle_user_intervention(self, intervention_data: Dict) -> bool:
        """
        处理用户介入 - 简化版本
        返回: True表示需要中断当前流程，False表示继续
        """
        if not intervention_data:
            return False
            
        intervention_type = intervention_data.get('type')
        self.logger.info(f"处理用户介入: {intervention_type}")
        
        try:
            if intervention_type == 'question_to_agent':
                target_agent = intervention_data.get('target_agent')
                question = intervention_data.get('question')
                
                if target_agent and question and target_agent in self.agents:
                    response = self.agents[target_agent].respond_to_user_question(
                        question, 
                        context={
                            'discussion_context': self._get_current_discussion_context(),
                            'medical_record': self.medical_context.get("medical_record", "")
                        },
                        concise=True
                    )
                    
                    if response.get('success'):
                        print(f"\n=== {target_agent} 的回答 ===")
                        print(response.get('response', ''))
                        print("=" * 50)
                    else:
                        print(f"❌ {target_agent} 回答失败")
                        
                else:
                    print("❌ 无效的目标智能体或问题")
                    
            elif intervention_type == 'broadcast_question':
                question = intervention_data.get('question')
                if question:
                    print(f"\n=== 向所有智能体提问: {question} ===")
                    print("=" * 60)
                    
                    # 创建广播轮次记录
                    broadcast_round = {
                        "round": f"broadcast_{len(self.discussion_log) + 1}",
                        "timestamp": datetime.now().isoformat(),
                        "type": "broadcast_question",
                        "question": question,
                        "contributions": []
                    }
                    
                    # 每个智能体依次回应
                    for agent_name, agent in self.agents.items():
                        print(f"\n--- {agent_name} 正在回应 ---")
                        
                        response = agent.respond_to_user_question(
                            question,
                            context={
                                'discussion_context': self._get_current_discussion_context(),
                                'medical_record': self.medical_context.get("medical_record", "")
                            },
                            concise=True
                        )
                        
                        if response.get('success'):
                            response_text = response.get('response', '')
                            print(f"{agent_name}: {response_text}")
                            
                            # 记录到广播轮次
                            broadcast_round["contributions"].append({
                                "agent": agent_name,
                                "response": response_text,
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            # 添加到共享历史，让后续智能体能看到前面的回应
                            self._add_to_shared_history(
                                agent_name, 
                                f"对广播问题的回应: {response_text[:200]}..."
                            )
                        else:
                            print(f"{agent_name}: 回答失败")
                            broadcast_round["contributions"].append({
                                "agent": agent_name,
                                "error": response.get('error', '未知错误'),
                                "timestamp": datetime.now().isoformat()
                            })
                    
                    # 将广播轮次添加到讨论日志
                    self.discussion_log.append(broadcast_round)
                    print("\n" + "=" * 60)
                    print("所有智能体回应完成")
                    
            elif intervention_type == 'add_information':
                information = intervention_data.get('information')
                if information:
                    self._update_medical_context(information)
                    # 修复：确保所有智能体都有update_context方法
                    for agent in self.agents.values():
                        if hasattr(agent, 'update_context'):
                            agent.update_context(information)
                        else:
                            # 后备方案：通过聊天方式更新上下文
                            update_message = f"用户补充了新的信息：{information}"
                            agent.chat(update_message)
                    print("✅ 信息已补充到讨论中")
                    
            elif intervention_type == 'skip_round':
                self.skip_remaining_agents = True
                print("⏭️ 跳过本轮剩余发言")
                return True  # 需要中断
                
            elif intervention_type == 'interrupt':
                self.is_running = False
                print("讨论已终止!")
                return True  # 需要中断
                
            # 记录用户介入
            intervention_record = {
                "type": intervention_type,
                "timestamp": datetime.now().isoformat(),
                "data": intervention_data
            }
            self.user_interventions.append(intervention_record)


            
        except Exception as e:
            self.logger.error(f"处理用户介入失败: {e}")
        
        return False

    def _record_intervention_response(self, intervention_type: str, agent_name: str, response: Dict):
        """记录介入响应到讨论日志"""
        # 查找最近的轮次，如果没有则创建新的介入轮次
        if not self.discussion_log or self.discussion_log[-1].get("type") != "intervention":
            intervention_round = {
                "round": f"intervention_{len(self.discussion_log) + 1}",
                "timestamp": datetime.now().isoformat(),
                "type": "intervention",
                "contributions": []
            }
            self.discussion_log.append(intervention_round)
        else:
            intervention_round = self.discussion_log[-1]
        
        # 添加响应记录
        intervention_round["contributions"].append({
            "intervention_type": intervention_type,
            "agent": agent_name,
            "response": response.get('response', ''),
            "timestamp": datetime.now().isoformat()
        })

    def _get_current_discussion_context(self) -> List[Dict]:
        """获取当前讨论的上下文 - 增强版本，包含广播问题"""
        context_messages = []
        
        # 添加最近几轮讨论的摘要作为系统消息
        recent_rounds = self.discussion_log[-3:]  # 最近3轮
        context_text = []
        
        for round_data in recent_rounds:
            round_type = round_data.get("type", "normal")
            
            if round_type == "normal":
                round_num = round_data.get("round", 0)
                context_text.append(f"第{round_num + 1}轮讨论:")
            elif round_type == "broadcast_question":
                context_text.append("广播提问轮次:")
            elif round_type == "intervention":
                context_text.append("用户介入轮次:")
            
            for contribution in round_data.get("contributions", []):
                agent = contribution.get("agent", "")
                
                if round_type == "broadcast_question":
                    response = contribution.get("response", "")
                    if response:
                        short_response = response[:150] + "..." if len(response) > 150 else response
                        context_text.append(f"  {agent}: {short_response}")
                else:
                    analysis = contribution.get("contribution", {}).get("concise_analysis", "")
                    if analysis:
                        short_analysis = analysis[:150] + "..." if len(analysis) > 150 else analysis
                        context_text.append(f"  {agent}: {short_analysis}")
        
        # 将摘要转换为消息格式
        if context_text:
            context_messages.append({
                "role": "system", 
                "content": "之前的讨论摘要:\n" + "\n".join(context_text)
            })
        
        return context_messages if context_messages else [
            {"role": "system", "content": "这是第一轮讨论，暂无历史记录"}
        ]

    def _add_to_shared_history(self, agent_name: str, content: str) -> None:
        """添加发言到共享历史"""
        # 这里可以维护一个全局的共享历史记录
        self.shared_discussion_history.extend([
            {"role": "user", "content": f"请{agent_name}专家发言"},
            {"role": "assistant", "content": f"{agent_name}: {content}"}
        ])
    
    def _user_input_listener(self):
        """监听用户输入"""
        while self.is_running:
            try:
                # 非阻塞获取用户输入
                user_input = self.interface.get_user_input()
                if user_input:
                    self.user_input_queue.put(user_input)
                    self.user_intervention_event.set()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"用户输入监听错误: {e}")
                break
 
    def _process_single_intervention(self, user_input: Dict[str, Any]):
        """处理单个用户介入请求"""
        intervention_type = user_input.get('type', 'broadcast')
        
        intervention_record = {
            "type": intervention_type,
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input
        }
        
        try:
            if intervention_type == 'question_to_agent':
                # 用户向特定智能体提问
                target_agent = user_input.get('target_agent')
                question = user_input.get('question')
                
                if target_agent in self.agents:
                    response = self.agents[target_agent].respond_to_user_question(question)
                    intervention_record["response"] = response
                    intervention_record["target_agent"] = target_agent
                else:
                    intervention_record["error"] = f"智能体 {target_agent} 不存在"
                    
            elif intervention_type == 'broadcast_question':
                # 用户向所有智能体广播问题
                question = user_input.get('question')
                responses = {}
                
                for agent_name, agent in self.agents.items():
                    responses[agent_name] = agent.respond_to_user_question(question)
                
                intervention_record["responses"] = responses
                
            elif intervention_type == 'add_information':
                # 用户补充信息
                new_info = user_input.get('information')
                self._update_medical_context(new_info)
                intervention_record["information_added"] = new_info
                
            elif intervention_type == 'interrupt':
                # 用户中断讨论
                self.is_running = False
                intervention_record["action"] = "discussion_interrupted"
                
            self.user_interventions.append(intervention_record)
            self.logger.info(f"处理用户介入: {intervention_type}")
            
        except Exception as e:
            intervention_record["error"] = str(e)
            self.user_interventions.append(intervention_record)
            self.logger.error(f"处理用户介入失败: {e}")
    
    def _update_medical_context(self, new_information: str):
        """更新医疗上下文信息"""
        if "additional_info" not in self.medical_context:
            self.medical_context["additional_info"] = []
        
        self.medical_context["additional_info"].append({
            "info": new_information,
            "timestamp": datetime.now().isoformat()
        })
        
        # 通知所有智能体更新上下文
        for agent in self.agents.values():
            agent.update_context(new_information)
  
    def _assess_discussion_quality(self) -> Dict[str, Any]:
        """评估讨论质量"""
        try:
            # 分析讨论深度和广度
            total_contributions = sum(len(round["contributions"]) for round in self.discussion_log)
            unique_perspectives = len(set(
                cont["agent"] for round in self.discussion_log 
                for cont in round["contributions"] 
                if "agent" in cont
            ))
            
            # 评估逻辑一致性
            logic_issues = sum(
                1 for round in self.discussion_log 
                for report in round.get("logic_reports", [])
                if report.get("logic_report", {}).get("has_issues", False)
            )
            
            quality_scores = {
                "diagnosis_completeness": self._score_diagnosis_completeness(),
                "treatment_rationality": self._score_treatment_rationality(),
                "integration_quality": self._score_integration_quality(),
                "discussion_depth": min(10, total_contributions // len(self.agents)),
                "perspective_diversity": min(10, unique_perspectives * 2),
                "logic_consistency": max(0, 10 - logic_issues)
            }
            
            quality_scores["overall_score"] = sum(quality_scores.values()) / len(quality_scores)
            
            return quality_scores
            
        except Exception as e:
            self.logger.error(f"质量评估失败: {e}")
            return {"overall_score": 0, "error": str(e)}
    
    def _score_diagnosis_completeness(self) -> int:
        """评估诊断全面性"""
        # 基于讨论中提到的诊断数量和差异性评分
        diagnoses_mentioned = set()
        for round in self.discussion_log:
            for cont in round["contributions"]:
                if "diagnosis" in cont.get("contribution", {}):
                    diagnoses_mentioned.add(cont["contribution"]["diagnosis"])
        
        return min(10, len(diagnoses_mentioned))
    
    def _score_treatment_rationality(self) -> int:
        """评估治疗方案合理性"""
        # 基于治疗建议的逻辑一致性和证据支持评分
        return 8  # 简化实现，实际应基于逻辑检查结果
    
    def _score_integration_quality(self) -> int:
        """评估意见整合质量"""
        # 基于各科室意见的整合程度评分
        return 7  # 简化实现
    
    def _calculate_duration(self) -> str:
        """计算讨论持续时间"""
        start_time = datetime.fromisoformat(self.medical_context["start_time"])
        end_time = datetime.fromisoformat(self.medical_context.get("end_time", datetime.now().isoformat()))
        duration = end_time - start_time
        return str(duration)
    
    def stop_discussion(self):
        """停止讨论"""
        self.is_running = False
        self.logger.info("讨论已停止")
    
    def get_discussion_status(self) -> Dict[str, Any]:
        """获取当前讨论状态"""
        return {
            "is_running": self.is_running,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "active_agents": list(self.agents.keys()),
            "total_interventions": len(self.user_interventions)
        }
    
    def respond_to_user_question(self, question: str, target_agent: str = None) -> Dict[str, Any]:
        """
        响应特定智能体或所有智能体的用户提问
        
        Args:
            question: 用户问题
            target_agent: 目标智能体名称，None表示广播给所有智能体
            
        Returns:
            响应结果字典
        """
        try:
            if target_agent and target_agent in self.agents:
                # 向特定智能体提问
                response = self.agents[target_agent].respond_to_user_question(
                    question, 
                    context=self.medical_context
                )
                return {
                    "success": True,
                    "target_agent": target_agent,
                    "response": response
                }
            else:
                # 向所有智能体广播
                responses = {}
                for agent_name, agent in self.agents.items():
                    responses[agent_name] = agent.respond_to_user_question(
                        question, 
                        context=self.medical_context
                    )
                
                return {
                    "success": True,
                    "responses": responses,
                    "type": "broadcast"
                }
                
        except Exception as e:
            self.logger.error(f"用户提问响应失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }