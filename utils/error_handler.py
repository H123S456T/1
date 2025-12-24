"""
统一的错误处理模块
"""

from typing import Optional, Callable, Any
from loguru import logger

class ClinicalError(Exception):
    """临床系统基础异常类"""
    
    def __init__(self, message: str, code: str = "CLINICAL_ERROR", 
                 details: Optional[Dict] = None, original_error: Optional[Exception] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        self.original_error = original_error
        super().__init__(self.message)

class AuthenticationError(ClinicalError):
    """认证错误"""
    def __init__(self, message: str = "认证失败", details: Optional[Dict] = None):
        super().__init__(message, "AUTH_ERROR", details)

class AuthorizationError(ClinicalError):
    """授权错误"""
    def __init__(self, message: str = "权限不足", details: Optional[Dict] = None):
        super().__init__(message, "AUTHZ_ERROR", details)

class ResourceNotFoundError(ClinicalError):
    """资源未找到错误"""
    def __init__(self, resource_type: str, resource_id: str, details: Optional[Dict] = None):
        message = f"{resource_type} {resource_id} 未找到"
        super().__init__(message, "RESOURCE_NOT_FOUND", details)

class ValidationError(ClinicalError):
    """数据验证错误"""
    def __init__(self, field: str, message: str, details: Optional[Dict] = None):
        super().__init__(f"字段 {field} 验证失败: {message}", "VALIDATION_ERROR", details)

def error_handler(func: Callable) -> Callable:
    """统一的错误处理装饰器"""
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except ClinicalError:
            raise  # 已知错误直接抛出
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise ClinicalError(
                "系统内部错误", 
                "INTERNAL_ERROR", 
                {"function": func.__name__},
                e
            )
    return wrapper

def handle_api_errors(response_func: Callable) -> Callable:
    """API错误处理装饰器"""
    def wrapper(*args, **kwargs) -> Dict[str, Any]:
        try:
            return response_func(*args, **kwargs)
        except ClinicalError as e:
            return {
                "success": False,
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "details": e.details
                }
            }
        except Exception as e:
            logger.error(f"API error: {e}")
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "内部服务器错误"
                }
            }
    return wrapper