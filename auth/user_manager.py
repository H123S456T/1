#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户管理模块
负责用户认证、注册、数据持久化等功能
"""

import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging
from loguru import logger
import jwt

from dataclasses import dataclass, field

"""
统一的用户管理模块
"""

@dataclass
class User:
    """统一的用户数据类"""
    user_id: str
    username: str
    password: str
    email: str = ""
    full_name: str = ""
    department: str = ""
    role: str = "user"
    created_at: str = ""
    last_login: str = ""
    login_count: int = 0
    is_active: bool = True
    preferences: Dict = field(default_factory=lambda: {
        "default_rounds": 3,
        "auto_save": True,
        "export_format": "docx",
        "language": "zh-CN"
    })
    custom_agents: List[Dict] = field(default_factory=list)
    discussion_history: List[Dict] = field(default_factory=list)
    
    # 添加一个简单的初始化后处理
    def __post_init__(self):
        """初始化后处理"""
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """将User对象转换为字典"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'password': self.password,
            'email': self.email,
            'full_name': self.full_name,
            'department': self.department,
            'role': self.role,
            'created_at': self.created_at,
            'last_login': self.last_login,
            'login_count': self.login_count,
            'is_active': self.is_active,
            'preferences': self.preferences,
            'custom_agents': self.custom_agents,
            'discussion_history': self.discussion_history
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'User':
        """从字典创建User对象"""
        return cls(**data)
    
class UnifiedUserManager:
    """统一的用户管理器"""
    
    def __init__(self, data_dir: str = "data/users"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.users_file = self.data_dir / "users.json"
        self.sessions_file = self.data_dir / "sessions.json"
        
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Dict] = {}
        
        self._load_data()

         # 初始化数据管理器功能
        self._initialize_data_manager()   

    def _initialize_data_manager(self):
        """初始化数据管理功能"""
        # 直接整合UserDataManager的功能到此类中
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Dict] = {}
        self._load_data()        

    def create_user(self, username: str, password: str, **kwargs) -> Tuple[bool, str]:
        """创建新用户 - 修复版本"""
        try:
            # 检查用户名是否已存在
            if self.user_exists(username):
                return False, "用户名已存在"
            
            # 直接在此处处理用户创建，不依赖data_manager
            user_id = self._create_user_record(username, password, kwargs)
            
            if user_id:
                logger.info(f"用户创建成功: {username}")
                return True, user_id
            else:
                return False, "创建用户失败"
                
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            return False, str(e)

    def _create_user_record(self, username: str, password: str, user_data: dict) -> Optional[str]:
        """创建用户记录 - 整合UserDataManager的功能"""
        try:
            # 生成用户ID
            next_number = len(self.users) + 1
            user_id = f"user_{next_number:06d}"
            
            # 哈希密码
            password = password
            
            # 创建用户对象
            user_data.update({
                'user_id': user_id,
                'username': username,
                'password': password,
                'created_at': datetime.now().isoformat(),
                'last_login': None,
                'login_count': 0,
                'is_active': True
            })
            
            user = User(**user_data)
            self.users[user_id] = user
            self._save_data()
            
            return user_id
            
        except Exception as e:
            logger.error(f"创建用户记录失败: {e}")
            return None

    def _load_data(self):
        """加载用户和会话数据"""
        try:
            # 加载用户数据
            if self.users_file.exists():
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    users_data = json.load(f)
                    for user_id, user_data in users_data.items():
                        self.users[user_id] = User(**user_data)
            
            # 加载会话数据
            if self.sessions_file.exists():
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    self.sessions = json.load(f)
                    
            logger.info(f"Loaded {len(self.users)} users and {len(self.sessions)} sessions")
            
        except Exception as e:
            logger.error(f"Error loading user data: {e}")
            self.users = {}
            self.sessions = {}

    def _verify_password(self, input_password: str, stored_password: str) -> bool:
        """
        验证密码是否正确
        
        Args:
            input_password: 用户输入的密码
            stored_password: 存储的密码
            
        Returns:
            bool: 密码是否正确
        """
        # 简单的密码验证（实际项目中应该使用哈希加密）
        return input_password == stored_password
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """用户认证"""
        try:
            user = next((u for u in self.users.values() if u.username == username), None)
            if not user or not user.is_active:
                return None
            
            if self._verify_password(password, user.password):
                # 更新登录信息
                user.last_login = datetime.now().isoformat()
                user.login_count += 1
                self._save_data()
                
                return user
            return None
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    def user_exists(self, username: str) -> bool:
        """
        检查用户名是否已存在
        
        Args:
            username: 要检查的用户名
            
        Returns:
            bool: 用户名是否存在
        """
        return any(user.username == username for user in self.users.values())   
   
    
    def _save_data(self):
        """保存用户和会话数据"""
        try:
            # 保存用户数据
            users_data = {user_id: self._user_to_dict(user) for user_id, user in self.users.items()}
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)
            
            # 保存会话数据
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            raise
    
    def _user_to_dict(self, user: User) -> Dict:
        """将UserProfile对象转换为字典"""
        return {
            'user_id': user.user_id,
            'username': user.username,
            'password': user.password,
            'email': user.email,
            'full_name': user.full_name,
            'department': user.department,
            'role': user.role,
            'created_at': user.created_at,
            'last_login': user.last_login,
            'login_count': user.login_count,
            'is_active': user.is_active,
            'preferences': user.preferences,
            'custom_agents': user.custom_agents
        }


# 单例模式实例
_user_manager_instance = None

def get_user_manager(data_dir: str = "data/users") -> UnifiedUserManager:
    """
    获取用户管理器单例实例
    
    Args:
        data_dir: 数据目录路径
        
    Returns:
        UnifiedUserManager: 用户管理器实例
    """
    global _user_manager_instance
    if _user_manager_instance is None:
        _user_manager_instance = UnifiedUserManager(data_dir)
    return _user_manager_instance

__all__ = [
    'UnifiedUserManager',
    'User',  
    'get_user_manager'
]