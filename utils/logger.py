# utils/logger.py
"""
完整的日志管理模块
基于loguru提供统一的日志记录功能
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from datetime import datetime

# 如果使用标准库的logging，可以这样导入：
# from logging import Logger
# 但由于我们使用loguru，可以省略类型注解或使用Any

def setup_logger(name: str = None) -> Any:  # 或者直接省略 -> Logger
    """设置日志系统"""
    if name is None:
        name = "clinical_system"
    
    # 确保日志目录存在
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 配置loguru
    logger.remove()  # 移除默认配置
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        level="INFO",
        colorize=True
    )
    
    # 添加文件输出
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )
    
    return logger

def get_logger(name: str = None) -> Any:
    """获取日志记录器"""
    if name is None:
        # 获取调用者的模块名
        import inspect
        frame = inspect.currentframe().f_back
        module = inspect.getmodule(frame)
        name = module.__name__ if module else "unknown"
    
    return logger.bind(name=name)

# 便捷的日志函数
def log_system_start():
    """记录系统启动日志"""
    logger.info("=" * 50)
    logger.info("临床MDT智能模拟助手启动")
    logger.info("=" * 50)

def log_system_stop():
    """记录系统停止日志"""
    logger.info("=" * 50)
    logger.info("临床MDT智能模拟助手停止")
    logger.info("=" * 50)

def log_user_action(username: str, action: str, details: str = ""):
    """记录用户操作日志"""
    logger.info(f"用户操作 | 用户: {username} | 动作: {action} | 详情: {details}")

def log_discussion_start(session_id: str, agents: list, medical_record_preview: str = ""):
    """记录讨论开始日志"""
    preview = medical_record_preview[:100] + "..." if len(medical_record_preview) > 100 else medical_record_preview
    logger.info(f"讨论开始 | 会话: {session_id} | 智能体: {agents} | 病历预览: {preview}")

def log_discussion_end(session_id: str, result: str, duration: float):
    """记录讨论结束日志"""
    logger.info(f"讨论结束 | 会话: {session_id} | 结果: {result} | 耗时: {duration:.2f}秒")