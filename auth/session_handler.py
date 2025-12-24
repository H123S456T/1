#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
会话处理模块
负责用户会话的创建、验证、管理和清理
"""

import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import threading
from loguru import logger


@dataclass
class SessionData:
    """会话数据类"""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    custom_agents: Dict[str, Any]  # 自定义智能体
    discussion_data: Dict[str, Any]  # 当前讨论数据
    user_preferences: Dict[str, Any]  # 用户偏好


class SessionHandler:
    """
    会话处理器类
    管理用户会话的生命周期
    """
    
    def __init__(self, session_timeout: int = 3600, cleanup_interval: int = 300):
        """
        初始化会话处理器
        
        Args:
            session_timeout: 会话超时时间（秒）
            cleanup_interval: 清理间隔（秒）
        """
        self.session_timeout = session_timeout
        self.active_sessions: Dict[str, SessionData] = {}
        self.session_lock = threading.Lock()
        
        # 启动后台清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self.cleanup_interval = cleanup_interval
        self._stop_cleanup = False
        self.cleanup_thread.start()
        
        logger.info(f"会话处理器初始化完成，超时时间: {session_timeout}秒")

    def _generate_session_id(self) -> str:
        """
        生成唯一的会话ID
        
        Returns:
            str: 会话ID
        """
        return secrets.token_urlsafe(32)

    def create_session(self, user_id: str, user_preferences: Dict = None) -> str:
        """
        创建新会话
        
        Args:
            user_id: 用户ID
            user_preferences: 用户偏好设置
            
        Returns:
            str: 会话ID
        """
        session_id = self._generate_session_id()
        now = datetime.now()
        
        session_data = SessionData(
            session_id=session_id,
            user_id=user_id,
            created_at=now,
            last_activity=now,
            custom_agents={},
            discussion_data={},
            user_preferences=user_preferences or {}
        )
        
        with self.session_lock:
            self.active_sessions[session_id] = session_data
        
        logger.info(f"创建新会话: {session_id} for user: {user_id}")
        return session_id

    def validate_session(self, session_id: str) -> Tuple[bool, Optional[SessionData]]:
        """
        验证会话有效性
        
        Args:
            session_id: 会话ID
            
        Returns:
            Tuple[是否有效, 会话数据]
        """
        with self.session_lock:
            if session_id not in self.active_sessions:
                return False, None
            
            session_data = self.active_sessions[session_id]
            now = datetime.now()
            
            # 检查是否超时
            time_since_activity = (now - session_data.last_activity).total_seconds()
            if time_since_activity > self.session_timeout:
                logger.info(f"会话超时: {session_id}")
                del self.active_sessions[session_id]
                return False, None
            
            # 更新最后活动时间
            session_data.last_activity = now
            return True, session_data

    def update_session_activity(self, session_id: str) -> bool:
        """
        更新会话活动时间
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否更新成功
        """
        with self.session_lock:
            if session_id in self.active_sessions:
                self.active_sessions[session_id].last_activity = datetime.now()
                return True
            return False

    def get_session_data(self, session_id: str) -> Optional[SessionData]:
        """
        获取会话数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            Optional[SessionData]: 会话数据
        """
        with self.session_lock:
            return self.active_sessions.get(session_id)

    def add_custom_agent(self, session_id: str, agent_name: str, agent_config: Dict) -> bool:
        """
        添加自定义智能体到会话
        
        Args:
            session_id: 会话ID
            agent_name: 智能体名称
            agent_config: 智能体配置
            
        Returns:
            bool: 是否添加成功
        """
        is_valid, session_data = self.validate_session(session_id)
        if not is_valid:
            return False
        
        with self.session_lock:
            session_data.custom_agents[agent_name] = {
                'config': agent_config,
                'created_at': datetime.now().isoformat(),
                'usage_count': 0
            }
        
        logger.debug(f"会话 {session_id} 添加自定义智能体: {agent_name}")
        return True

    def get_custom_agents(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话的自定义智能体
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict[str, Any]: 自定义智能体字典
        """
        is_valid, session_data = self.validate_session(session_id)
        if not is_valid:
            return {}
        
        return session_data.custom_agents

    def remove_custom_agent(self, session_id: str, agent_name: str) -> bool:
        """
        移除自定义智能体
        
        Args:
            session_id: 会话ID
            agent_name: 智能体名称
            
        Returns:
            bool: 是否移除成功
        """
        is_valid, session_data = self.validate_session(session_id)
        if not is_valid:
            return False
        
        with self.session_lock:
            if agent_name in session_data.custom_agents:
                del session_data.custom_agents[agent_name]
                logger.debug(f"会话 {session_id} 移除自定义智能体: {agent_name}")
                return True
        return False

    def update_discussion_data(self, session_id: str, discussion_data: Dict) -> bool:
        """
        更新会话的讨论数据
        
        Args:
            session_id: 会话ID
            discussion_data: 讨论数据
            
        Returns:
            bool: 是否更新成功
        """
        is_valid, session_data = self.validate_session(session_id)
        if not is_valid:
            return False
        
        with self.session_lock:
            session_data.discussion_data.update(discussion_data)
        return True

    def get_discussion_data(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话的讨论数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict[str, Any]: 讨论数据
        """
        is_valid, session_data = self.validate_session(session_id)
        if not is_valid:
            return {}
        
        return session_data.discussion_data

    def clear_discussion_data(self, session_id: str) -> bool:
        """
        清空讨论数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否清空成功
        """
        is_valid, session_data = self.validate_session(session_id)
        if not is_valid:
            return False
        
        with self.session_lock:
            session_data.discussion_data = {}
        return True

    def destroy_session(self, session_id: str) -> bool:
        """
        销毁会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否销毁成功
        """
        with self.session_lock:
            if session_id in self.active_sessions:
                user_id = self.active_sessions[session_id].user_id
                del self.active_sessions[session_id]
                logger.info(f"销毁会话: {session_id} for user: {user_id}")
                return True
        return False

    def get_user_sessions(self, user_id: str) -> List[str]:
        """
        获取用户的所有活跃会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            List[str]: 会话ID列表
        """
        sessions = []
        with self.session_lock:
            for session_id, session_data in self.active_sessions.items():
                if session_data.user_id == user_id:
                    sessions.append(session_id)
        return sessions

    def get_session_stats(self) -> Dict[str, Any]:
        """
        获取会话统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        with self.session_lock:
            total_sessions = len(self.active_sessions)
            
            # 按用户分组统计
            user_session_count = {}
            for session_data in self.active_sessions.values():
                user_id = session_data.user_id
                user_session_count[user_id] = user_session_count.get(user_id, 0) + 1
            
            # 计算平均会话时长
            now = datetime.now()
            total_duration = 0
            for session_data in self.active_sessions.values():
                duration = (now - session_data.created_at).total_seconds()
                total_duration += duration
            
            avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
            
            return {
                'total_sessions': total_sessions,
                'unique_users': len(user_session_count),
                'average_duration_seconds': avg_duration,
                'sessions_per_user': user_session_count
            }

    def _cleanup_expired_sessions(self):
        """清理过期会话"""
        now = datetime.now()
        expired_sessions = []
        
        with self.session_lock:
            for session_id, session_data in self.active_sessions.items():
                time_since_activity = (now - session_data.last_activity).total_seconds()
                if time_since_activity > self.session_timeout:
                    expired_sessions.append(session_id)
            
            # 删除过期会话
            for session_id in expired_sessions:
                user_id = self.active_sessions[session_id].user_id
                del self.active_sessions[session_id]
                logger.info(f"清理过期会话: {session_id} for user: {user_id}")
        
        if expired_sessions:
            logger.info(f"清理了 {len(expired_sessions)} 个过期会话")

    def _cleanup_worker(self):
        """后台清理工作线程"""
        while not self._stop_cleanup:
            try:
                self._cleanup_expired_sessions()
                time.sleep(self.cleanup_interval)
            except Exception as e:
                logger.error(f"会话清理工作线程错误: {e}")
                time.sleep(60)  #