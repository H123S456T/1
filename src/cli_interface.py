#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import getpass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import uuid

# 导入自定义模块
from auth.user_manager import UnifiedUserManager
from auth.session_handler import SessionHandler
from agents.agent_registry import AgentRegistry
from discussion.discussion_engine import ClinicalDiscussionEngine
from storage.discussion_storage import DiscussionStorage
from storage.user_data import UserDataManager
from utils.config import ClinicalConfig
from utils.logger import setup_logger
from auth import User 

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class ClinicalCLI:
    """临床多智能体讨论系统命令行界面"""
    
    def __init__(self, config_path: str = "config.json"):
        # 初始化配置
        self.config = ClinicalConfig(config_path)
        self.cli_interface = CLIInterface(self)

        # 初始化日志
        self.logger = setup_logger("clinical_cli")
        
        # 初始化核心组件
        try:
            self.user_manager = UnifiedUserManager()
            self.session_handler = SessionHandler()
            self.agent_registry = AgentRegistry()
            self.discussion_storage = DiscussionStorage()
            self.user_data_manager = UserDataManager()
        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            # 提供更详细的错误信息
            if "api_base" in str(e):
                self.logger.error("请检查配置文件中模型API设置是否正确")
            raise
        
        # 当前会话状态
        self.current_session = None
        self.current_user = None
        self.current_discussion = None
        
        # 讨论配置
        self.discussion_config = {
            "rounds": self.config.discussion.default_rounds,
            "user_participation": False,  # 默认不参与讨论
            "auto_save": True,
            "export_format": "json"
        }

    def get_model_args(self):
        """获取模型参数 - 修复这个方法"""
        # 创建一个简单的参数对象
        class Args:
            def __init__(self, config):
                self.model = config.model.engine
                self.llm_name = config.model.model_name
                self.url = config.model.api_base  # 使用配置中的API地址
                self.temp = config.model.temperature
                self.discussion_rounds = getattr(config.discussion, 'default_rounds', 3)
        
        return Args(self.config)
    
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self, title: str):
        """打印标题"""
        self.clear_screen()
        print("=" * 60)
        print(f"临床MDT智能模拟助手 - {title}")
        print("=" * 60)
        print()
    
    def wait_for_enter(self, message: str = "按回车键继续..."):
        """等待用户按回车"""
        input(f"\n{message}")
   
    def authenticate_user(self) -> bool:
        """用户认证流程"""
        while True:
            self.print_header("用户认证")
            print("1. 用户登录")
            print("2. 用户注册")
            print("3. 退出系统")
            print()
            
            choice = self.cli_interface.get_user_input("请选择操作: ", required=False)
            
            if choice == "1":
                return self.user_login()
            elif choice == "2":
                self.user_register()
            elif choice == "3" or choice.lower() == "exit":
                print("感谢使用临床多智能体讨论系统！")
                sys.exit(0)
            else:
                print("无效选择，请重新输入。")
                self.wait_for_enter()
    
    def user_login(self) -> bool:
        """用户登录"""
        self.print_header("用户登录")
        
        username = self.cli_interface.get_user_input("用户名: ")
        password = self.cli_interface.get_user_input("密码: ", password=False) 
        
        try:
            user_info = self.user_manager.authenticate(username, password)
            if user_info:
                # user_info 是 User 对象，不是字典
                self.current_user = {
                    'user_id': user_info.user_id,
                    'username': user_info.username,
                    'full_name': getattr(user_info, 'full_name', ''),
                    'department': getattr(user_info, 'department', ''),
                    'role': getattr(user_info, 'role', 'user')
                }
                
                self.current_session = self.session_handler.create_session(user_info.user_id)
                                
                print(f"\n登录成功！欢迎回来，{user_info.username}！")
                self.logger.info(f"用户 {username} 登录成功")
                self.wait_for_enter()
                return True
            else:
                print("\n登录失败：用户名或密码错误。")
                self.wait_for_enter()
                return False
                
        except Exception as e:
            print(f"\n登录失败：{e}")
            self.wait_for_enter()
            return False

    def user_register(self):
        """用户注册"""
        self.print_header("用户注册")
        
        username = self.cli_interface.get_user_input("请输入用户名: ")
        
        # 检查用户名是否已存在
        if self.user_manager.user_exists(username):
            print("该用户名已存在，请选择其他用户名。")
            self.wait_for_enter()
            return
        
        password = self.cli_interface.get_user_input("请输入密码: ", password=False)
        confirm_password = self.cli_interface.get_user_input("请确认密码: ", password=False)
        
        if password != confirm_password:
            print("密码不一致，请重新输入。")
            self.wait_for_enter()
            return
        
        # 可选信息
        full_name = self.cli_interface.get_user_input("请输入真实姓名（可选）: ", required=False)
        department = self.cli_interface.get_user_input("请输入所在科室（可选）: ", required=False)
        
        try:
            # 直接使用UnifiedUserManager创建用户
            success, result = self.user_manager.create_user(
                username=username,
                password=password,
                full_name=full_name,
                department=department
            )
            
            if success:
                print(f"\n注册成功！欢迎使用临床多智能体讨论系统，{username}！")
                self.logger.info(f"新用户注册: {username}")
            else:
                print(f"\n注册失败：{result}")
            
            self.wait_for_enter()
            
        except Exception as e:
            print(f"\n注册失败：{e}")
            self.wait_for_enter() 

    def show_main_menu(self):
        """显示主菜单"""
        while True:
            self.print_header("主菜单")
            print(f"当前用户: {self.current_user['username']}")
            if self.current_session:
                print(f"会话ID: {self.current_session[:8]}...")
            print()
            
            print("1. 开始新的讨论")
            print("2. 查看历史讨论")
            print("3. 管理智能体")
            print("4. 系统设置")
            print("5. 用户信息")
            print("6. 退出系统")
            print()
            
            choice = self.cli_interface.get_user_input("请选择操作: ", required=False)
            
            if choice == "1":
                self.start_new_discussion()
            elif choice == "2":
                self.view_discussion_history()
            elif choice == "3":
                self.manage_agents()
            elif choice == "4":
                self.system_settings()
            elif choice == "5":
                self.user_information()
            elif choice == "5":
                self.user_information()
            elif choice == "6":
                if self.cli_interface.confirm_action("确定要退出系统吗？"):
                    print("感谢使用临床多智能体讨论系统！")
                    break
            else:
                print("无效选择，请重新输入。")
                self.wait_for_enter()

    def start_new_discussion(self):
        """开始新的讨论"""
        self.print_header("开始新的讨论")
        
        # 步骤1: 选择智能体
        available_agents = self.agent_registry.get_available_agents(self.current_session)
        agent_names = list(available_agents.keys())
        
        if not agent_names:
            print("当前没有可用的智能体，请先添加智能体。")
            self.wait_for_enter()
            return
        
        print("步骤1: 选择参与讨论的智能体")
        print("提示：可以输入多个编号，用空格或逗号分隔，如：1 3 5 或 1,3,5")
        
        selected_agents = self.cli_interface.select_from_list(
            agent_names, 
            "请选择要参与讨论的智能体（可多选）:", 
            allow_multiple=True
        )
        
        if not selected_agents:
            print("未选择任何智能体，取消讨论。")
            self.wait_for_enter()
            return
        
        print(f"已选择 {len(selected_agents)} 个智能体: {', '.join(selected_agents)}")       

        # 步骤2: 输入病历信息
        self.print_header("输入病历信息")
        print("步骤2: 输入病历信息")
        print("请输入患者的病历信息，包括主诉、现病史、既往史、体格检查、辅助检查等。")
        print("（输入完成后请双击回车结束输入）")
        print()
        
        medical_record = self.cli_interface.get_multiline_input("病历信息:")
        
        if not medical_record.strip():
            print("病历信息不能为空。")
            self.wait_for_enter()
            return
        
        # 步骤3: 输入讨论问题
        self.print_header("输入讨论问题")
        print("步骤3: 输入讨论问题")
        question = self.cli_interface.get_user_input("请输入需要讨论的临床问题: ")
        
        if not question.strip():
            print("讨论问题不能为空。")
            self.wait_for_enter()
            return
        
        # 步骤4: 配置讨论参数
        self.configure_discussion_settings()
        
        # 步骤5: 确认并开始讨论
        self.print_header("确认讨论信息")
        print("请确认以下讨论信息:")
        print(f"参与智能体: {', '.join(selected_agents)}")
        print(f"讨论问题: {question}")
        print(f"讨论轮数: {self.discussion_config['rounds']}")
        print(f"用户参与: {'是' if self.discussion_config['user_participation'] else '否'}")
        print()
        
        if not self.cli_interface.confirm_action("确认开始讨论吗？"):
            print("讨论已取消。")
            self.wait_for_enter()
            return
        
        # 开始讨论
        try:
            self.run_discussion(selected_agents, medical_record, question)
        except Exception as e:
            print(f"讨论过程中出现错误: {e}")
            self.logger.error(f"讨论错误: {e}")
            self.wait_for_enter()

    def configure_discussion_settings(self):
        """配置讨论设置"""
        self.print_header("讨论设置")
        
        print("当前设置:")
        print(f"1. 讨论轮数: {self.discussion_config['rounds']}")
        print(f"2. 用户参与讨论: {'是' if self.discussion_config['user_participation'] else '否'}")
        print(f"3. 自动保存: {'是' if self.discussion_config['auto_save'] else '否'}")
        print(f"4. 导出格式: {self.discussion_config['export_format']}")
        print()
        
        change_settings = self.cli_interface.confirm_action("是否修改讨论设置？")
        
        if change_settings:
            # 修改讨论轮数
            try:
                rounds_input = self.cli_interface.get_user_input(
                    f"讨论轮数 (当前: {self.discussion_config['rounds']}, 范围: 1-5): ", 
                    required=False
                )
                if rounds_input:
                    new_rounds = int(rounds_input)
                    if 1 <= new_rounds <= 5:
                        self.discussion_config['rounds'] = new_rounds
                        print(f"讨论轮数已设置为: {new_rounds}")
            except ValueError:
                print("讨论轮数必须在1-5之间，将使用默认值。")
            
            # 用户参与设置 - 明确提示
            print("\n用户参与设置:")
            print("如果选择'是'，讨论过程中会提示您介入；")
            print("如果选择'否'，系统将自动完成整个讨论过程。")
            participation = self.cli_interface.confirm_action("是否允许用户参与讨论？")
            self.discussion_config['user_participation'] = participation
            print(f"用户参与已设置为: {'是' if participation else '否'}")
            
            # 自动保存
            auto_save = self.cli_interface.confirm_action("是否自动保存讨论记录？")
            self.discussion_config['auto_save'] = auto_save
            
            # 导出格式
            formats = ["json", "docx", "txt"]
            print("可选导出格式: " + ", ".join(formats))
            export_format = self.cli_interface.get_user_input(f"导出格式 ({self.discussion_config['export_format']}): ", required=False)
            if export_format and export_format.lower() in formats:
                self.discussion_config['export_format'] = export_format.lower()

    def show_discussion_result(self, discussion_result: Dict):
        """显示讨论结果 - 修复未定义字段问题"""
        print("\n" + "=" * 80)
        print("临床多智能体讨论汇总报告")
        print("=" * 80)

        # === 修复：安全地获取字段，提供默认值 ===
        # 检查结果状态
        status = discussion_result.get("status", "completed")
        if status == "interrupted":
            print("讨论被用户中断")
            metadata = discussion_result.get("metadata", {})
            rounds_completed = metadata.get("rounds_completed", 0)
            print(f"已完成轮次: {rounds_completed}")
            return
        elif status == "error":
            error_msg = discussion_result.get("error", "未知错误")
            print(f"讨论过程中出现错误: {error_msg}")
            return

        # === 修复：安全获取metadata ===
        metadata = discussion_result.get('metadata', {})
        print(f"讨论ID: {metadata.get('discussion_id', '未知')}")
        print(f"参与智能体: {', '.join(metadata.get('agents_used', []))}")
        print(f"讨论轮数: {metadata.get('rounds', 0)}")
        print(f"生成时间: {metadata.get('timestamp', '未知')}")
        print("-" * 80)

        # === 修复：安全获取clinical_summary ===
        clinical_summary = discussion_result.get('clinical_summary', {})
        if clinical_summary:
            print("\n临床总结:")
            print("-" * 40)
            
            # 主要诊断 - 支持多种可能的字段名
            primary_diagnosis = clinical_summary.get('primary_diagnosis', 
                                                   clinical_summary.get('diagnosis',
                                                   clinical_summary.get('final_decision', '未知')))
            print(f"主要诊断: {primary_diagnosis}")
            
            # 治疗方案 - 支持多种数据结构
            treatment_plan = clinical_summary.get('treatment_plan', {})
            if treatment_plan:
                print("\n治疗方案:")
                if isinstance(treatment_plan, dict):
                    for category, plans in treatment_plan.items():
                        if plans:
                            print(f"  {category}:")
                            if isinstance(plans, list):
                                for plan in plans:
                                    print(f"    • {plan}")
                            else:
                                print(f"    • {plans}")
                elif isinstance(treatment_plan, list):
                    for plan in treatment_plan:
                        print(f"  • {plan}")
                elif isinstance(treatment_plan, str):
                    print(f"  {treatment_plan}")
        
        # === 修复：安全获取质量评估 ===
        quality_assessment = discussion_result.get('evaluation_metrics', {})
        if quality_assessment:
            print("\n质量评估:")
            for metric, score in quality_assessment.items():
                if isinstance(score, (int, float)):
                    print(f"  {metric}: {score}/100")
        
        # === 修复：安全获取讨论统计 ===
        discussion_process = discussion_result.get('discussion_process', {})
        discussion_log = discussion_process.get('discussion_log', [])
        if discussion_log:
            total_contributions = 0
            for round_data in discussion_log:
                contributions = round_data.get('contributions', [])
                total_contributions += len(contributions)
            
            print(f"\n讨论统计: 共{len(discussion_log)}轮，{total_contributions}次发言")
        
        print("\n" + "=" * 80)

    def run_discussion(self, agent_names: List[str], medical_record: str, question: str):
        """运行讨论 - 修复导出方法调用"""
        self.print_header("讨论进行中")
        
        print("正在初始化讨论环境...")
        
        # 创建讨论引擎
        discussion_engine = ClinicalDiscussionEngine(
            args=self.get_model_args(),
            user_session={
                'session_id': self.current_session,
                'user_id': self.current_user['user_id'] 
            },
            interface=self.cli_interface
        )

        if hasattr(discussion_engine, 'set_discussion_config'):
            discussion_engine.set_discussion_config(self.discussion_config)        
        discussion_engine.discussion_config = self.discussion_config
        discussion_engine.max_rounds = self.discussion_config['rounds']

        discussion_engine.initialize_discussion(medical_record, question, agent_names)    
        
        print("讨论开始...")
        print(f"病历信息: {medical_record}")
        print(f"讨论问题: {question}")
        print(f"参与智能体: {', '.join(agent_names)}")
        print(f"计划讨论轮数: {self.discussion_config['rounds']}")
        print("-" * 60)
        
        # 执行讨论
        self.logger.info(f"开始讨论，参与智能体: {agent_names}")
        discussion_result = discussion_engine.start_discussion()
        
        # 调试：打印结果结构
        self.logger.info(f"讨论结果类型: {type(discussion_result)}")
        if isinstance(discussion_result, dict):
            self.logger.info(f"讨论结果键: {list(discussion_result.keys())}")
        
        # 保存讨论结果
        if self.discussion_config['auto_save'] and isinstance(discussion_result, dict):
            try:
                # 构建完整的数据结构
                save_data = {
                    "agents": agent_names,
                    "rounds": self.discussion_config['rounds'],
                    "medical_record": medical_record,
                    "question": question,
                    "log": discussion_result.get("discussion_process", {}).get("discussion_log", []),
                    "summary": discussion_result.get("clinical_summary", {}),
                    "interventions": discussion_result.get("discussion_process", {}).get("user_interventions", []),
                    "metrics": discussion_result.get("evaluation_metrics", {}),
                    "metadata": discussion_result.get("metadata", {
                        "discussion_id": str(uuid.uuid4())[:8],
                        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                        "agents_used": agent_names,
                        "rounds": self.discussion_config['rounds']
                    }),
                    "medical_context": discussion_result.get("medical_context", {
                        "medical_record": medical_record,
                        "question": question
                    }),
                    "discussion_process": discussion_result.get("discussion_process", {
                        "discussion_log": discussion_result.get("discussion_process", {}).get("discussion_log", []),
                        "user_interventions": discussion_result.get("discussion_process", {}).get("user_interventions", [])
                    })
                }
                
                discussion_id = self.discussion_storage.save_discussion(
                    self.current_user['user_id'],
                    save_data
                )
                discussion_result['discussion_id'] = discussion_id
                self.logger.info(f"讨论记录已保存，ID: {discussion_id}")
                
            except Exception as e:
                self.logger.error(f"保存讨论记录失败: {e}")
                discussion_result['save_error'] = str(e)
        
        # 显示讨论结果
        self.show_discussion_result(discussion_result)
        
        # === 修复：调用正确的导出方法 ===
        self.handle_discussion_export(discussion_result)
        
        self.current_discussion = discussion_result
        self.wait_for_enter("讨论结束，按回车键返回主菜单...")

    def handle_discussion_export(self, discussion_result: Dict):
        """处理讨论导出 - 新增方法，替代export_discussion_result"""
        if not self.cli_interface.confirm_action("是否导出讨论结果？"):
            return
        
        # 使用现有的导出逻辑
        export_formats = [
            {"name": "JSON格式", "value": "json"},
            {"name": "Word文档", "value": "docx"}, 
            {"name": "HTML标准版", "value": "html"},
            {"name": "HTML简洁版", "value": "simple_html"},
            {"name": "文本文件", "value": "txt"}
        ]
        
        format_names = [fmt["name"] for fmt in export_formats]
        selected_formats = self.cli_interface.select_from_list(
            format_names,
            "请选择导出格式（可多选）:",
            allow_multiple=True
        )
        
        if not selected_formats:
            print("取消导出。")
            return
        
        # 获取导出路径
        default_filename = f"clinical_discussion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        export_base_path = self.cli_interface.get_user_input(
            f"导出路径（默认: ./exports/{default_filename}）: ",
            required=False
        )
        
        if not export_base_path:
            export_base_path = f"./exports/{default_filename}"
        
        # 确保导出目录存在
        os.makedirs(os.path.dirname(export_base_path), exist_ok=True)
        
        success_exports = []
        failed_exports = []
        
        try:
            for format_name in selected_formats:
                format_value = next(fmt["value"] for fmt in export_formats if fmt["name"] == format_name)
                
                try:
                    export_file = self.discussion_storage.export_discussion(
                        discussion_result,
                        format_value,
                        export_base_path + f".{format_value}"
                    )
                    
                    success_exports.append((format_name, export_file))
                    print(f"✅ 成功导出为 {format_name}: {export_file}")
                    
                except Exception as e:
                    failed_exports.append((format_name, str(e)))
                    print(f"❌ 导出 {format_name} 失败: {e}")
            
            # 显示导出结果汇总
            print("\n" + "="*50)
            print("导出结果汇总:")
            print("="*50)
            
            if success_exports:
                print("✅ 成功导出的格式:")
                for format_name, filepath in success_exports:
                    print(f"  - {format_name}: {filepath}")
            
            if failed_exports:
                print("❌ 导出失败的格式:")
                for format_name, error in failed_exports:
                    print(f"  - {format_name}: {error}")
            
            self.wait_for_enter()
            
        except Exception as e:
            print(f"❌ 导出过程中发生未知错误: {e}")
            self.wait_for_enter()
  
    def prompt_for_intervention_with_timeout(self, prompt: str, timeout: int = 5) -> Optional[str]:
        """
        带超时的用户介入提示
        """
        import threading
        from queue import Queue
        
        # 先显示提示信息
        print(f"\n{prompt}", end='', flush=True)
        
        result_queue = Queue()
        
        def input_with_timeout():
            try:
                user_input = input()  # 直接获取输入
                result_queue.put(user_input)
            except:
                result_queue.put(None)
        
        # 创建输入线程
        input_thread = threading.Thread(target=input_with_timeout)
        input_thread.daemon = True
        input_thread.start()
        
        # 等待输入或超时
        input_thread.join(timeout)
        
        if not result_queue.empty():
            return result_queue.get()
        else:
            print(f"\n⏰ {timeout}秒超时，继续自动讨论...")
            return None

    def get_structured_intervention_prompt(self) -> Dict[str, Any]:
        """获取结构化的介入提示选项"""        
        print(("  - 1 向特定智能体提问 (q); 2. 向所有智能体提问 (a); 3. 补充病例信息 (i); 4. 跳过当前轮次 (s); 5. 终止讨论 (x); 6. 继续自动讨论 (回车) "))
        
        # 直接显示提示，不等待
        print("请选择介入方式: ", end='', flush=True)
        
        try:
            choice = input().strip().lower()
        except:
            choice = ""
        
        intervention_map = {
            '1': 'question_to_agent',
            'q': 'question_to_agent',
            '2': 'broadcast_question', 
            'a': 'broadcast_question',
            '3': 'add_information',
            'i': 'add_information',
            '4': 'skip_round',
            's': 'skip_round',
            '5': 'interrupt',
            'x': 'interrupt'
        }
        
        intervention_type = intervention_map.get(choice)
        if intervention_type:
            return self._get_intervention_details(intervention_type)
        
        return None

    def _get_intervention_details(self, intervention_type: str) -> Dict[str, Any]:
        """获取介入详细信息 - 立即提示输入"""
        try:
            if intervention_type == 'question_to_agent':
                print("请选择目标智能体: ", end='', flush=True)
                # 显示可用智能体列表
                available_agents = list(self.agents.keys())
                for i, agent in enumerate(available_agents, 1):
                    print(f"{i}. {agent}")
                print("请输入智能体编号或名称: ", end='', flush=True)
                
                agent_input = input().strip()
                # 尝试解析为编号或名称
                if agent_input.isdigit() and 1 <= int(agent_input) <= len(available_agents):
                    target_agent = available_agents[int(agent_input) - 1]
                else:
                    target_agent = agent_input
                
                print("请输入问题: ", end='', flush=True)
                question = input().strip()
                
                return {
                    'type': 'question_to_agent',
                    'target_agent': target_agent,
                    'question': question
                }
            
            elif intervention_type == 'broadcast_question':
                print("请输入要向所有智能体提问的问题: ", end='', flush=True)
                question = input().strip()
                
                return {
                    'type': 'broadcast_question', 
                    'question': question
                }
            
            elif intervention_type == 'add_information':
                print("请输入要补充的病例信息: ", end='', flush=True)
                information = input().strip()
                
                return {
                    'type': 'add_information',
                    'information': information
                }
            
            elif intervention_type == 'skip_round':
                return {'type': 'skip_round'}
            
            elif intervention_type == 'interrupt':
                return {'type': 'interrupt'}
            
        except Exception as e:
            self.logger.error(f"获取介入详情失败: {e}")
        
        return None

    def view_discussion_history(self):
        """查看历史讨论"""
        self.print_header("历史讨论记录")
        
        try:
            discussions = self.discussion_storage.get_user_discussions(self.current_user['user_id'])
            
            if not discussions:
                print("暂无讨论记录。")
                self.wait_for_enter()
                return
            
            # 格式化讨论列表显示
            discussion_list = []
            for disc in discussions:
                discussion_list.append({
                    'id': disc['metadata']['discussion_id'],
                    'date': disc['metadata']['timestamp'],
                    'question': disc['medical_context']['question'][:50] + '...' if len(disc['medical_context']['question']) > 50 else disc['medical_context']['question'],
                    'agents': ', '.join(disc['metadata']['agents_used'][:3]) + ('...' if len(disc['metadata']['agents_used']) > 3 else '')
                })
            
            while True:
                # 显示讨论列表
                print("历史讨论记录:")
                print("-" * 80)
                print(f"{'序号':<4} {'日期':<12} {'问题':<30} {'参与智能体':<30}")
                print("-" * 80)
                
                for i, disc in enumerate(discussion_list, 1):
                    print(f"{i:<4} {disc['date']:<12} {disc['question']:<30} {disc['agents']:<30}")
                
                print("-" * 80)
                print("\n操作选项:")
                print("1. 查看详细记录")
                print("2. 导出讨论记录")
                print("3. 删除讨论记录")
                print("4. 返回主菜单")
                print()
                
                choice = self.cli_interface.get_user_input("请选择操作: ", required=False)
                
                if choice == "1":
                    self.view_discussion_details(discussions)
                elif choice == "2":
                    self.export_discussion_batch(discussions)
                elif choice == "3":
                    self.delete_discussions(discussions)
                elif choice == "4":
                    break
                else:
                    print("无效选择，请重新输入。")
                    self.wait_for_enter()
                    
        except Exception as e:
            print(f"获取历史记录失败: {e}")
            self.wait_for_enter()
    
    def view_discussion_details(self, discussions: List[Dict]):
        """查看讨论详情"""
        discussion_ids = [disc['discussion_id'] for disc in discussions]
        selected_id = self.cli_interface.select_from_list(
            discussion_ids,
            "请选择要查看的讨论记录:",
            allow_multiple=False
        )
        
        if selected_id:
            discussion_id = selected_id[0]
            discussion = next(disc for disc in discussions if disc['discussion_id'] == discussion_id)
            
            self.show_discussion_result(discussion)
            self.wait_for_enter()
    
    def export_discussion_batch(self, discussions: List[Dict]):
        """批量导出讨论记录"""
        discussion_ids = [disc['discussion_id'] for disc in discussions]
        selected_ids = self.cli_interface.select_from_list(
            discussion_ids,
            "请选择要导出的讨论记录（可多选）:",
            allow_multiple=True
        )
        
        if not selected_ids:
            return
        
        selected_discussions = [disc for disc in discussions if disc['discussion_id'] in selected_ids]
        
        export_formats = ["json", "docx", "html", "simple_html", "txt"]
        format_choice = self.cli_interface.select_from_list(
            export_formats,
            "请选择导出格式:",
            allow_multiple=False
        )
        
        if format_choice:
            export_format = format_choice[0]
            export_path = self.cli_interface.get_user_input("导出路径: ", required=False) or "./exports/batch_export"
            
            try:
                export_files = self.discussion_storage.export_discussions_batch(
                    selected_discussions,
                    export_format,
                    export_path
                )
                
                print(f"成功导出 {len(export_files)} 个文件。")
                for file in export_files:
                    print(f"  - {file}")
                
                self.wait_for_enter()
                
            except Exception as e:
                print(f"批量导出失败: {e}")
                self.wait_for_enter()
    
    def delete_discussions(self, discussions: List[Dict]):
        """删除讨论记录"""
        discussion_ids = [disc['discussion_id'] for disc in discussions]
        selected_ids = self.cli_interface.select_from_list(
            discussion_ids,
            "请选择要删除的讨论记录（可多选）:",
            allow_multiple=True
        )
        
        if not selected_ids:
            return
        
        if self.cli_interface.confirm_action(f"确定要删除选中的 {len(selected_ids)} 条讨论记录吗？此操作不可恢复。"):
            try:
                deleted_count = self.user_data_manager.delete_discussions(
                    self.current_user['user_id'],
                    selected_ids
                )
                
                print(f"成功删除 {deleted_count} 条讨论记录。")
                self.wait_for_enter()
                
            except Exception as e:
                print(f"删除失败: {e}")
                self.wait_for_enter()

    def manage_agents(self):
        """管理智能体 - 增强版本"""
        self.print_header("智能体管理")
        
        while True:
            available_agents = self.agent_registry.get_available_agents(self.current_session)
            builtin_agents = self.agent_registry.get_builtin_agents()
            custom_agents = self.agent_registry.get_custom_agents(self.current_session)
            
            print("当前可用智能体:")
            print("-" * 60)
            
            # 显示内置智能体（按分类分组）
            print("📚 内置智能体:")
            categorized_agents = self.agent_registry.get_agents_by_category(self.current_session)
            for category, agents in categorized_agents.items():
                if any(agent.get('is_builtin', False) for agent in agents):
                    print(f"  📂 {category}:")
                    for agent in agents:
                        if agent.get('is_builtin', False):
                            print(f"    • {agent['name']} - {agent['description']}")
            
            # 显示自定义智能体
            print("\n🎯 自定义智能体:")
            if custom_agents:
                for agent_name, agent_info in custom_agents.items():
                    print(f"    • {agent_name} - {agent_info.get('description', '自定义智能体')}")
            else:
                print("    暂无自定义智能体")
            
            print("-" * 60)
            print("\n🛠️ 操作选项:")
            print("1. 添加自定义智能体")
            print("2. 编辑自定义智能体") 
            print("3. 删除自定义智能体")
            print("4. 搜索智能体")
            print("5. 查看智能体详情")
            print("6. 返回主菜单")
            print()
            
            choice = self.cli_interface.get_user_input("请选择操作: ", required=False)
            
            if choice == "1":
                self.add_custom_agent()
            elif choice == "2":
                self.edit_custom_agent(custom_agents)
            elif choice == "3":
                self.delete_custom_agent(custom_agents)
            elif choice == "4":
                self.search_agents(available_agents)
            elif choice == "5":
                self.view_agent_details(available_agents)
            elif choice == "6":
                break
            else:
                print("无效选择，请重新输入。")
                self.wait_for_enter()

    def add_custom_agent(self):
        """添加自定义智能体 - 增强版本"""
        self.print_header("添加自定义智能体")
        
        print("🎯 创建新的自定义智能体")
        print("=" * 50)
        
        agent_name = self.cli_interface.get_user_input("智能体名称: ")
        
        # 检查名称是否已存在
        available_agents = self.agent_registry.get_available_agents(self.current_session)
        if agent_name in available_agents:
            print("❌ 该名称已存在，请使用其他名称。")
            self.wait_for_enter()
            return
        
        print("\n📝📝 请输入智能体的专业描述:")
        description = self.cli_interface.get_user_input("智能体描述: ")
        print("\n请输入智能体的专业提示词:")
        print("（这将决定智能体的专业领域和行为方式）")
        print("提示：可以描述智能体的专业背景、分析风格、回答特点等")
        agent_prompt = self.cli_interface.get_multiline_input("智能体提示词:")
        
        if not agent_prompt.strip():
            print("❌ 提示词不能为空。")
            self.wait_for_enter()
            return
        
        # 选择分类
        categories = ["内科", "外科", "医技科", "药学", "辅助科室", "自定义"]
        print("\n📂 请选择分类:")
        for i, category in enumerate(categories, 1):
            print(f"  {i}. {category}")
        
        category_choice = self.cli_interface.get_user_input(f"选择分类 (1-{len(categories)}): ", required=False)
        try:
            category_index = int(category_choice) - 1
            category = categories[category_index] if 0 <= category_index < len(categories) else "自定义"
        except:
            category = "自定义"
        
        try:
            success = self.agent_registry.create_custom_agent(
                self.current_session,
                agent_name,
                agent_prompt,
                description=description,
                category=category
            )
            
            if success:
                print(f"✅ 成功添加自定义智能体: {agent_name}")
                print(f"📂 分类: {category}")
                print(f"📝 描述: {description}")
                self.logger.info(f"用户 {self.current_user['username']} 添加自定义智能体: {agent_name}")
            else:
                print("❌ 添加智能体失败")
                
            self.wait_for_enter()
            
        except Exception as e:
            print(f"❌ 添加智能体失败: {e}")
            self.wait_for_enter()

    def search_agents(self, available_agents: Dict):
        """搜索智能体"""
        self.print_header("搜索智能体")
        
        query = self.cli_interface.get_user_input("请输入搜索关键词: ", required=False)
        if not query:
            return
        
        results = self.agent_registry.search_agents(query, self.current_session)
        
        if results:
            print(f"🔍 找到 {len(results)} 个相关智能体:")
            print("-" * 60)
            for i, result in enumerate(results, 1):
                type_icon = "📚" if result.get('is_builtin') else "🎯"
                print(f"{i}. {type_icon} {result['name']}")
                print(f"   分类: {result.get('category', '未知')}")
                print(f"   描述: {result.get('description', '')}")
                print()
        else:
            print("❌ 未找到相关智能体")
        
        self.wait_for_enter()

    def delete_custom_agent(self, custom_agents: Dict):
        """删除自定义智能体"""
        if not custom_agents:
            print("当前没有自定义智能体可删除。")
            self.wait_for_enter()
            return
        
        agent_names = list(custom_agents.keys())
        selected_agents = self.cli_interface.select_from_list(
            agent_names,
            "请选择要删除的自定义智能体（可多选）:",
            allow_multiple=True
        )
        
        if not selected_agents:
            return
        
        if self.cli_interface.confirm_action(f"确定要删除选中的 {len(selected_agents)} 个自定义智能体吗？"):
            try:
                for agent_name in selected_agents:
                    self.agent_registry.delete_custom_agent(
                        self.current_session,
                        agent_name
                    )
                    print(f"已删除智能体: {agent_name}")
                
                self.logger.info(f"用户 {self.current_user['username']} 删除自定义智能体: {selected_agents}")
                self.wait_for_enter()
                
            except Exception as e:
                print(f"删除智能体失败: {e}")
                self.wait_for_enter()
    
    def view_agent_details(self, available_agents: Dict):
        """查看智能体详情"""
        agent_names = list(available_agents.keys())
        selected_agent = self.cli_interface.select_from_list(
            agent_names,
            "请选择要查看的智能体:",
            allow_multiple=False
        )
        
        if not selected_agent:
            return
        
        agent_name = selected_agent[0]
        agent_info = available_agents[agent_name]
        
        self.print_header(f"智能体详情 - {agent_name}")
        print(f"类型: {'内置' if agent_name in self.agent_registry.get_builtin_agents() else '自定义'}")
        print(f"专业领域: {agent_info.get('specialty', '未指定')}")
        print("\n提示词:")
        print("-" * 60)
        print(agent_info.get('prompt', '无提示词信息'))
        print("-" * 60)
        
        self.wait_for_enter()
    
    def system_settings(self):
        """系统设置"""
        self.print_header("系统设置")
        
        print("当前系统设置:")
        print(f"1. 默认讨论轮数: {self.config.DEFAULT_ROUNDS}")
        print(f"2. 最大自定义智能体数: {self.config.MAX_CUSTOM_AGENTS}")
        print(f"3. 会话超时时间: {self.config.SESSION_TIMEOUT} 秒")
        print(f"4. 默认导出格式: {self.config.DEFAULT_EXPORT_FORMAT}")
        print()
        
        if self.current_user.get('role') == 'admin':
            print("管理员选项:")
            print("5. 修改系统设置")
            print("6. 查看系统日志")
            print("7. 管理所有用户")
            print()
        
        print("8. 返回主菜单")
        print()
        
        choice = self.cli_interface.get_user_input("请选择操作: ", required=False)
        
        if choice == "1" and self.current_user.get('role') == 'admin':
            self.change_default_rounds()
        elif choice == "2" and self.current_user.get('role') == 'admin':
            self.change_max_custom_agents()
        elif choice == "3" and self.current_user.get('role') == 'admin':
            self.change_session_timeout()
        elif choice == "4" and self.current_user.get('role') == 'admin':
            self.change_default_export_format()

        elif choice == "5" and self.current_user.get('role') == 'admin':
            print("当前系统设置:")
            print(f"1. 模型引擎: {self.config.model.engine}")
            print(f"2. API端点: {self.config.model.api_base}")
            print(f"3. 模型名称: {self.config.model.model_name}")
            print(f"4. 温度参数: {self.config.model.temperature}")
            print("\n模型配置管理:")
            print("5. 重新加载模型配置")
            print("6. 测试模型连接")
            print("7. 编辑模型配置文件")
            
            choice = self.cli_interface.get_user_input("请选择操作: ", required=False)
            
            if choice == "5" and self.current_user.get('role') == 'admin':
                self.reload_model_config()
            elif choice == "6":
                self.test_model_connection()
            elif choice == "7" and self.current_user.get('role') == 'admin':
                self.edit_model_config()

        elif choice == "6" and self.current_user.get('role') == 'admin':
            self.view_system_logs()
        elif choice == "7" and self.current_user.get('role') == 'admin':
            self.manage_all_users()
        elif choice == "8":
            # 返回主菜单
            pass
        else:
            print("无权限或无效选择。")
            self.wait_for_enter()
    
    def change_default_rounds(self):
        """修改默认讨论轮数"""
        new_rounds = self.get_user_input(f"新的默认讨论轮数 ({self.config.DEFAULT_ROUNDS}): ")
        try:
            new_rounds = int(new_rounds)
            if 1 <= new_rounds <= 10:
                self.config.DEFAULT_ROUNDS = new_rounds
                self.config.save()
                print("默认讨论轮数已更新。")
            else:
                print("讨论轮数必须在1-10之间。")
        except ValueError:
            print("请输入有效的数字。")
        self.wait_for_enter()

    def reload_model_config(self):
        """重新加载模型配置"""
        try:
            self.config = ClinicalConfig.reload_config()
            print("✅ 模型配置已重新加载")
        except Exception as e:
            print(f"❌ 重新加载配置失败: {e}")

    def test_model_connection(self):
        """测试模型连接"""
        print("测试模型连接...")
        # 实现测试逻辑
        pass

    def edit_model_config(self):
        """编辑模型配置文件"""
        config_file = "model_config.json"
        if not os.path.exists(config_file):
            # 创建默认配置文件
            self.create_default_model_config()
        
        print(f"编辑配置文件: {config_file}")
        # 可以调用系统编辑器或提供编辑界面
        pass    

    def change_max_custom_agents(self):
        """修改最大自定义智能体数"""
        new_max = self.get_user_input(f"新的最大自定义智能体数 ({self.config.MAX_CUSTOM_AGENTS}): ")
        try:
            new_max = int(new_max)
            if new_max >= 1:
                self.config.MAX_CUSTOM_AGENTS = new_max
                self.config.save()
                print("最大自定义智能体数已更新。")
            else:
                print("数值必须大于0。")
        except ValueError:
            print("请输入有效的数字。")
        self.wait_for_enter()
    
    def change_session_timeout(self):
        """修改会话超时时间"""
        new_timeout = self.get_user_input(f"新的会话超时时间（秒） ({self.config.SESSION_TIMEOUT}): ")
        try:
            new_timeout = int(new_timeout)
            if new_timeout >= 60:  # 至少1分钟
                self.config.SESSION_TIMEOUT = new_timeout
                self.config.save()
                print("会话超时时间已更新。")
            else:
                print("超时时间必须至少60秒。")
        except ValueError:
            print("请输入有效的数字。")
        self.wait_for_enter()
    
    def change_llm_api(self):
        """修改LLM API地址"""
        new_api = self.get_user_input(f"新的LLM API地址 ({self.config.LLM_API_BASE}): ")
        if new_api:
            self.config.LLM_API_BASE = new_api
            self.config.save()
            print("LLM API地址已更新。")
        self.wait_for_enter()
    
    def change_default_export_format(self):
        """修改默认导出格式"""
        formats = ["json", "docx", "txt", "pdf"]
        print("可选格式: " + ", ".join(formats))
        new_format = self.get_user_input(f"新的默认导出格式 ({self.config.DEFAULT_EXPORT_FORMAT}): ")
        if new_format and new_format.lower() in formats:
            self.config.DEFAULT_EXPORT_FORMAT = new_format.lower()
            self.config.save()
            print("默认导出格式已更新。")
        self.wait_for_enter()
    
    def view_system_logs(self):
        """查看系统日志"""
        self.print_header("系统日志")
        
        log_files = self.get_log_files()
        if not log_files:
            print("暂无日志文件。")
            self.wait_for_enter()
            return
        
        selected_file = self.cli_interface.select_from_list(
            log_files,
            "请选择要查看的日志文件:",
            allow_multiple=False
        )
        
        if selected_file:
            try:
                with open(selected_file[0], 'r', encoding='utf-8') as f:
                    content = f.read()
                
                print(f"日志文件: {selected_file[0]}")
                print("-" * 80)
                print(content)
                print("-" * 80)
                
                self.wait_for_enter()
                
            except Exception as e:
                print(f"读取日志文件失败: {e}")
                self.wait_for_enter()
    
    def get_log_files(self):
        """获取日志文件列表"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            return []
        
        log_files = []
        for file in os.listdir(log_dir):
            if file.endswith(".log"):
                log_files.append(os.path.join(log_dir, file))
        
        return sorted(log_files, reverse=True)  # 最新的在前
    
    def manage_all_users(self):
        """管理所有用户"""
        self.print_header("用户管理")
        
        try:
            all_users = self.user_manager.get_all_users()
            
            print("所有用户列表:")
            print("-" * 80)
            print(f"{'用户名':<15} {'真实姓名':<15} {'科室':<15} {'角色':<10} {'最后登录':<20}")
            print("-" * 80)
            
            for user in all_users:
                print(f"{user['username']:<15} {user.get('full_name', ''):<15} "
                      f"{user.get('department', ''):<15} {user.get('role', 'user'):<10} "
                      f"{user.get('last_login', '从未登录'):<20}")
            
            print("-" * 80)
            print("\n操作选项:")
            print("1. 查看用户详情")
            print("2. 修改用户角色")
            print("3. 重置用户密码")
            print("4. 删除用户")
            print("5. 返回系统设置")
            print()
            
            choice = self.cli_interface.get_user_input("请选择操作: ", required=False)
            
            if choice == "1":
                self.view_user_details(all_users)
            elif choice == "2":
                self.change_user_role(all_users)
            elif choice == "3":
                self.reset_user_password(all_users)
            elif choice == "4":
                self.delete_user(all_users)
            elif choice == "5":
                return
            else:
                print("无效选择，请重新输入。")
                self.wait_for_enter()
                
        except Exception as e:
            print(f"获取用户列表失败: {e}")
            self.wait_for_enter()
    
    def view_user_details(self, users: List[Dict]):
        """查看用户详情"""
        usernames = [user['username'] for user in users]
        selected_user = self.cli_interface.select_from_list(
            usernames,
            "请选择要查看的用户:",
            allow_multiple=False
        )
        
        if not selected_user:
            return
        
        username = selected_user[0]
        user_info = next(user for user in users if user['username'] == username)
        
        self.print_header(f"用户详情 - {username}")
        print(f"用户名: {user_info['username']}")
        print(f"真实姓名: {user_info.get('full_name', '未设置')}")
        print(f"科室: {user_info.get('department', '未设置')}")
        print(f"角色: {user_info.get('role', 'user')}")
        print(f"创建时间: {user_info.get('created_at', '未知')}")
        print(f"最后登录: {user_info.get('last_login', '从未登录')}")
        print(f"讨论记录数: {user_info.get('discussion_count', 0)}")
        
        self.wait_for_enter()
    
    def change_user_role(self, users: List[Dict]):
        """修改用户角色"""
        usernames = [user['username'] for user in users]
        selected_user = self.cli_interface.select_from_list(
            usernames,
            "请选择要修改角色的用户:",
            allow_multiple=False
        )
        
        if not selected_user:
            return
        
        username = selected_user[0]
        current_role = next(user['role'] for user in users if user['username'] == username)
        
        roles = ["user", "admin"]
        new_role = self.cli_interface.select_from_list(
            roles,
            f"请选择新角色 (当前: {current_role}):",
            allow_multiple=False
        )
        
        if new_role and new_role[0] != current_role:
            try:
                self.user_manager.change_user_role(username, new_role[0])
                print(f"用户 {username} 的角色已从 {current_role} 改为 {new_role[0]}。")
                self.logger.info(f"管理员 {self.current_user['username']} 修改用户 {username} 角色为 {new_role[0]}")
            except Exception as e:
                print(f"修改角色失败: {e}")
        
        self.wait_for_enter()
    
    def reset_user_password(self, users: List[Dict]):
        """重置用户密码"""
        usernames = [user['username'] for user in users]
        selected_user = self.cli_interface.select_from_list(
            usernames,
            "请选择要重置密码的用户:",
            allow_multiple=False
        )
        
        if not selected_user:
            return
        
        username = selected_user[0]
        
        if self.cli_interface.confirm_action(f"确定要重置用户 {username} 的密码吗？"):
            new_password = self.get_user_input("请输入新密码: ", password=True)
            confirm_password = self.get_user_input("请确认新密码: ", password=True)
            
            if new_password != confirm_password:
                print("密码不一致，重置取消。")
                self.wait_for_enter()
                return
            
            try:
                self.user_manager.reset_user_password(username, new_password)
                print(f"用户 {username} 的密码已重置。")
                self.logger.info(f"管理员 {self.current_user['username']} 重置用户 {username} 的密码")
            except Exception as e:
                print(f"重置密码失败: {e}")
            
            self.wait_for_enter()
    
    def delete_user(self, users: List[Dict]):
        """删除用户"""
        usernames = [user['username'] for user in users if user['username'] != self.current_user['username']]
        
        if not usernames:
            print("没有其他用户可删除。")
            self.wait_for_enter()
            return
        
        selected_user = self.cli_interface.select_from_list(
            usernames,
            "请选择要删除的用户:",
            allow_multiple=False
        )
        
        if not selected_user:
            return
        
        username = selected_user[0]
        
        if self.cli_interface.confirm_action(f"确定要删除用户 {username} 吗？此操作不可恢复。"):
            try:
                self.user_manager.delete_user(username)
                print(f"用户 {username} 已删除。")
                self.logger.info(f"管理员 {self.current_user['username']} 删除用户 {username}")
            except Exception as e:
                print(f"删除用户失败: {e}")
            
            self.wait_for_enter()
    
    def user_information(self):
        """用户信息"""
        self.print_header("用户信息")
        
        print(f"用户名: {self.current_user['username']}")
        print(f"真实姓名: {self.current_user.get('full_name', '未设置')}")
        print(f"科室: {self.current_user.get('department', '未设置')}")
        print(f"角色: {self.current_user.get('role', 'user')}")
        print(f"注册时间: {self.current_user.get('created_at', '未知')}")
        print(f"最后登录: {self.current_user.get('last_login', '未知')}")
        
        # 获取用户的讨论统计
        try:
            discussion_count = self.user_data_manager.get_user_discussion_count(self.current_user['user_id'])
            print(f"讨论记录数: {discussion_count}")
        except:
            print("讨论记录数: 无法获取")
        
        print("\n操作选项:")
        print("1. 修改个人信息")
        print("2. 修改密码")
        print("3. 返回主菜单")
        print()
        
        choice = self.cli_interface.get_user_input("请选择操作: ", required=False)
        
        if choice == "1":
            self.update_profile()
        elif choice == "2":
            self.change_password()
        elif choice == "3":
            return
        else:
            print("无效选择，请重新输入。")
            self.wait_for_enter()
    
    def update_profile(self):
        """修改个人信息"""
        self.print_header("修改个人信息")
        
        current_full_name = self.current_user.get('full_name', '')
        current_department = self.current_user.get('department', '')
        
        new_full_name = self.get_user_input(f"真实姓名 ({current_full_name}): ", required=False)
        new_department = self.get_user_input(f"科室 ({current_department}): ", required=False)
        
        if not new_full_name and not new_department:
            print("未修改任何信息。")
            self.wait_for_enter()
            return
        
        try:
            updates = {}
            if new_full_name:
                updates['full_name'] = new_full_name
            if new_department:
                updates['department'] = new_department
            
            self.user_manager.update_user_profile(self.current_user['user_id'], updates)
            
            # 更新当前会话中的用户信息
            if new_full_name:
                self.current_user['full_name'] = new_full_name
            if new_department:
                self.current_user['department'] = new_department
            
            print("个人信息已更新。")
            self.logger.info(f"用户 {self.current_user['username']} 更新个人信息")
            
        except Exception as e:
            print(f"更新个人信息失败: {e}")
        
        self.wait_for_enter()
    
    def change_password(self):
        """修改密码"""
        self.print_header("修改密码")
        
        current_password = self.get_user_input("当前密码: ", password=True)
        
        # 验证当前密码
        if not self.user_manager.verify_password(self.current_user['user_id'], current_password):
            print("当前密码不正确。")
            self.wait_for_enter()
            return
        
        new_password = self.get_user_input("新密码: ", password=True)
        confirm_password = self.get_user_input("确认新密码: ", password=True)
        
        if new_password != confirm_password:
            print("新密码不一致，修改取消。")
            self.wait_for_enter()
            return
        
        try:
            self.user_manager.change_user_password(self.current_user['user_id'], new_password)
            print("密码已修改。")
            self.logger.info(f"用户 {self.current_user['username']} 修改密码")
        except Exception as e:
            print(f"修改密码失败: {e}")
        
        self.wait_for_enter()
    
    def run(self):
        """运行CLI主循环"""
        try:
            # 显示欢迎信息
            self.clear_screen()
            print("=" * 60)
            print("      欢迎使用临床多智能体讨论系统")
            print("=" * 60)
            print()
            self.wait_for_enter("按回车键开始...")
            
            # 用户认证
            if not self.authenticate_user():
                return
            
            # 主菜单循环
            self.show_main_menu()
            
        except KeyboardInterrupt:
            print("\n\n感谢使用临床多智能体讨论系统！")
        except Exception as e:
            print(f"系统错误: {e}")
            self.logger.error(f"系统错误: {e}")
            self.wait_for_enter()

class CLIInterface:
    """CLI接口适配器 - 统一输入处理"""
    
    def __init__(self, cli_instance):
        self.cli = cli_instance
   
    def get_user_input(self, prompt: str = "", required: bool = True, password: bool = False) -> str:
        """获取用户输入"""
        while True:
            try:
                if password:
                    user_input = getpass.getpass(prompt)
                else:
                    user_input = input(prompt).strip()
                
                if required and not user_input:
                    print("请输入:")
                    continue
                    
                return user_input
            except KeyboardInterrupt:
                print("\n\n操作已取消。")
                sys.exit(0)
            except Exception as e:
                print(f"输入错误: {e}")
                continue

    def get_multiline_input(self, prompt: str) -> str:
        """获取多行输入"""
        print(prompt)
        print("（输入空行结束输入）")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "":
                    break
                lines.append(line)
            except EOFError:
                break
            except KeyboardInterrupt:
                return ""
        return "\n".join(lines)
    
    def confirm_action(self, prompt: str) -> bool:
        """确认操作"""
        response = self.get_user_input(f"{prompt} (y/n): ", required=False)
        return response and response.lower() in ['y', 'yes', '是', '确认']
    
    def select_from_list(self, items: List, prompt: str, allow_multiple: bool = False) -> List:
        """从列表中选择项目"""
        if not items:
            print("暂无选项可用。")
            return []
        
        print(f"\n{prompt}")
        print("-" * 40)
        
        for i, item in enumerate(items, 1):
            if isinstance(item, dict):
                display_text = item.get('name', str(item))
            else:
                display_text = str(item)
            print(f"{i}. {display_text}", end=" ")
            if i % 6 == 0:
                print()    
            
        print()        
        
        if allow_multiple:
            print(f"{len(items) + 1}. 全选")
            print(f"{len(items) + 2}. 取消选择")
            print("\n提示：可以输入多个编号，用空格、逗号或中文逗号分隔")
        else:
            print(f"{len(items) + 1}. 返回上级")
        
        print("-" * 40)
        
        while True:
            try:
                choice = self.get_user_input("请选择编号: ", required=False)
                
                if not choice:
                    return []
                
                if allow_multiple:
                    if choice.lower() == 'all' or choice == str(len(items) + 1):
                        return items
                    if choice.lower() in ['cancel', '取消'] or choice == str(len(items) + 2):
                        return []
                    
                    # 支持多种分隔符
                    import re
                    choice = re.sub(r'[，\s]+', ',', choice)
                    choice = choice.strip(',')
                    
                    if ',' in choice:
                        indices = []
                        for part in choice.split(','):
                            part = part.strip()
                            if part.isdigit():
                                indices.append(int(part))
                            elif '-' in part:
                                range_parts = part.split('-')
                                if len(range_parts) == 2 and range_parts[0].isdigit() and range_parts[1].isdigit():
                                    start, end = int(range_parts[0]), int(range_parts[1])
                                    indices.extend(range(start, end + 1))
                    else:
                        indices = [int(choice)] if choice.isdigit() else []
                    
                    valid_indices = [i for i in indices if 1 <= i <= len(items)]
                    if valid_indices:
                        selected_items = []
                        for i in valid_indices:
                            if i <= len(items):
                                selected_items.append(items[i-1])
                        return selected_items
                    else:
                        print("无效的选择，请重新输入。")
                
                else:
                    index = int(choice)
                    if 1 <= index <= len(items):
                        return [items[index-1]]
                    elif index == len(items) + 1:
                        return []
                    else:
                        print("无效的选择，请重新输入。")
                        
            except ValueError:
                print("请输入有效的数字。")
            except KeyboardInterrupt:
                return []
    
    def has_user_input(self, timeout: float = 0) -> bool:
        """检查是否有用户输入 - 简化实现"""
        # 在实际应用中可以实现真正的非阻塞检查
        return False
    
    def should_prompt_for_intervention(self) -> bool:
        """是否应该提示用户介入"""
        return False

    
def main():
    """主函数"""
    try:
        cli = ClinicalCLI()
        cli.run()
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()