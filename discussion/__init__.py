"""
讨论引擎模块
提供多智能体讨论的核心功能
"""

from .discussion_engine import ClinicalDiscussionEngine
from .user_interaction import UserIntervention

__all__ = [
    'ClinicalDiscussionEngine',
    'UserIntervention',
]