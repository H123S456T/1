"""
配置管理模块
负责系统配置的加载、验证和管理
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from loguru import logger

# 添加 SystemConfig 类定义
@dataclass
class SystemConfig:
    session_timeout: int = 3600
    max_concurrent_discussions: int = 10
    backup_interval: int = 3600
    auto_save: bool = True
    max_log_size: str = "10MB"
    max_backup_files: int = 5

@dataclass
class ModelConfig:
    """模型配置类"""
    engine: str = "vllm"
    api_base: str = "http://10.124.0.7:9001/v1"
    model_name: str = "Qwen3-next"
    temperature: float = 0.3
    max_tokens: int = 100000
    timeout: int = 60
    max_retries: int = 3,
    available_models: List[Dict] = field(default_factory=list)  # 可用模型列表


@dataclass
class DiscussionConfig:
    """讨论配置类"""
    default_rounds: int = 3
    max_rounds: int = 5
    enable_user_intervention: bool = True
    auto_save: bool = True
    export_formats: list = field(default_factory=lambda: ["json", "docx", "pdf"])


@dataclass
class UserConfig:
    """用户配置类"""
    session_timeout: int = 3600  # 1小时
    max_custom_agents: int = 5
    data_retention_days: int = 30
    enable_auto_logout: bool = True


@dataclass
class UIPreferences:
    """界面偏好配置"""
    language: str = "zh-CN"
    theme: str = "default"
    show_timestamps: bool = True
    auto_scroll: bool = True
    max_display_lines: int = 100


@dataclass
class ClinicalConfig:
    """
    临床多智能体系统配置主类
    """
    
    # 子系统配置
    model: ModelConfig = field(default_factory=ModelConfig)
    discussion: DiscussionConfig = field(default_factory=DiscussionConfig)
    user: UserConfig = field(default_factory=UserConfig)
    ui: UIPreferences = field(default_factory=UIPreferences)
    system: SystemConfig = field(default_factory=SystemConfig)

    # 路径配置
    data_dir: str = "data"
    log_dir: str = "logs"
    export_dir: str = "exports"
    temp_dir: str = "temp"
    
    # 系统配置
    debug: bool = False
    log_level: str = "INFO"
    
    def __post_init__(self):
        """初始化后处理，创建必要的目录"""
        self._create_directories()
        self._load_external_model_config()  # 加载外部配置
        self._validate_config()
    
    def _load_external_model_config(self):
        """从外部文件加载模型配置 - 新增方法"""
        model_config_paths = [
            "model_config.json",
            "config/model_config.json", 
            "data/model_config.json"
        ]
        
        for config_path in model_config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        external_config = json.load(f)
                    
                    # 更新模型配置
                    if 'model_config' in external_config:
                        model_config_data = external_config['model_config']
                        self.model = ModelConfig(**model_config_data)
                    
                    # 加载可用模型列表
                    if 'available_models' in external_config:
                        self.model.available_models = external_config['available_models']
                    
                    logger.info(f"已从外部文件加载模型配置: {config_path}")
                    break
                    
                except Exception as e:
                    logger.warning(f"加载外部模型配置失败 {config_path}: {e}")
        else:
            logger.info("未找到根目录、data或config目录下的外部模型配置文件，将使用默认配置")

    def get_available_models(self) -> List[Dict[str, str]]:
        """获取可用模型列表"""
        if not self.model.available_models:
            # 提供默认的模型选项
            return [
                {
                    "name": "vllm-local",
                    "engine": "vllm", 
                    "api_base": "http://127.0.0.1:8000/v1",
                    "model_name": "Qwen3-next",
                    "description": "本地VLLM服务"
                }
            ]
        return self.model.available_models
        
    def update_model_config(self, engine: str, api_base: str, model_name: str, **kwargs):
        """更新模型配置"""
        self.model.engine = engine
        self.model.api_base = api_base
        self.model.model_name = model_name
        
        # 更新其他参数
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                setattr(self.model, key, value)
        
        logger.info(f"模型配置已更新: {engine} - {model_name}")

    def _create_directories(self):
        """创建必要的目录结构"""
        directories = [
            self.data_dir,
            self.log_dir,
            self.export_dir,
            self.temp_dir,
            os.path.join(self.data_dir, "users"),
            os.path.join(self.data_dir, "discussions"),
            os.path.join(self.data_dir, "sessions")
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def _validate_config(self):       
        if self.discussion.default_rounds > self.discussion.max_rounds:
            raise ValueError("默认讨论轮数不能超过最大轮数")
        
        if self.user.max_custom_agents <= 0:
            raise ValueError("最大自定义智能体数必须大于0")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'model': asdict(self.model),
            'discussion': asdict(self.discussion),
            'user': asdict(self.user),
            'ui': asdict(self.ui),
            'system': asdict(self.system),
            'data_dir': self.data_dir,
            'log_dir': self.log_dir,
            'export_dir': self.export_dir,
            'temp_dir': self.temp_dir,
            'debug': self.debug,
            'log_level': self.log_level
        }
    
    def save_to_file(self, filepath: str = None):
        """保存配置到文件"""
        if filepath is None:
            filepath = os.path.join(self.data_dir, "config.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.info(f"配置已保存到: {filepath}")
    
    @classmethod
    def load_from_file(cls, filepath: str = None) -> 'ClinicalConfig':
        """从文件加载配置"""
        if filepath is None:
            filepath = os.path.join("data", "config.json")
        
        if not os.path.exists(filepath):
            logger.warning(f"配置文件不存在: {filepath}，使用默认配置")
            return cls()
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            return cls.from_dict(config_dict)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，使用默认配置")
            return cls()
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ClinicalConfig':
        """从字典创建配置对象"""
        # 创建主配置对象
        config = cls()
        
        # 更新模型配置
        if 'model' in config_dict:
            model_config = config_dict['model']
            config.model = ModelConfig(**config_dict['model'])
        
        # 更新讨论配置
        if 'discussion' in config_dict:
            discussion_config = config_dict['discussion']
            config.discussion = DiscussionConfig(**config_dict['discussion'])
        
        # 更新用户配置
        if 'user' in config_dict:
            user_config = config_dict['user']
            config.user = UserConfig(**config_dict['user'])
        
        # 更新UI配置
        if 'ui' in config_dict:
            ui_config = config_dict['ui']
            config.ui = UIPreferences(**config_dict['ui'])
        
        # 更新系统配置
        if 'system' in config_dict:
            system_config = config_dict['system']
            config.debug = system_config.get('debug', config.debug)
            config.log_level = system_config.get('log_level', config.log_level)
            config.data_dir = system_config.get('data_dir', config.data_dir)
            config.log_dir = system_config.get('log_dir', config.log_dir)
            config.export_dir = system_config.get('export_dir', config.export_dir)
            config.temp_dir = system_config.get('temp_dir', config.temp_dir)
        
        return config


# 全局配置实例
_config_instance: Optional[ClinicalConfig] = None

def get_config() -> ClinicalConfig:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ClinicalConfig.load_from_file()
    return _config_instance

def update_config(new_config: ClinicalConfig):
    """更新全局配置"""
    global _config_instance
    _config_instance = new_config
    _config_instance.save_to_file()

def reload_config(filepath: str = None) -> ClinicalConfig:
    """重新加载配置 - 修复版本"""
    global _config_instance
    _config_instance = ClinicalConfig.load_from_file(filepath)
    return _config_instance

def create_default_config(filepath: str = "config.json") -> ClinicalConfig:
    """创建默认配置"""
    config = ClinicalConfig()
    config.save_to_file(filepath)
    return config