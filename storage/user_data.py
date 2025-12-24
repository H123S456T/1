import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger
import jwt
from dataclasses import dataclass, asdict
from auth import User

class UserDataManager:
    """用户数据管理类"""
    
    def __init__(self, data_dir: str = "data/users", secret_key: str = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # JWT密钥
        self.secret_key = secret_key or os.getenv('JWT_SECRET', 'clinical-multi-agent-secret-key')
        
        # 用户数据文件路径
        self.users_file = self.data_dir / "users.json"
        self.sessions_file = self.data_dir / "sessions.json"
        
        # 内存中的用户数据和会话
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Dict] = {}
        
        self._load_data()
    
    def _load_data(self):
        """加载用户数据和会话数据"""
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
            
            logger.info(f"已加载 {len(self.users)} 个用户和 {len(self.sessions)} 个会话")
            
        except Exception as e:
            logger.error(f"加载用户数据失败: {e}")
            # 如果文件损坏，创建空数据
            self.users = {}
            self.sessions = {}
    
    def _save_data(self):
        """保存用户数据和会话数据到文件"""
        try:
            # 保存用户数据
            users_data = {user_id: asdict(user) for user_id, user in self.users.items()}
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(users_data, f, ensure_ascii=False, indent=2)
            
            # 保存会话数据
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
            
            logger.debug("用户数据已保存")
            
        except Exception as e:
            logger.error(f"保存用户数据失败: {e}")
            raise
    