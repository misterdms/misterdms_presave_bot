"""
🛡️ Security System - Do Presave Reminder Bot v25 (Plan 1 Active Code)
"""
 
from config import config
from functools import wraps

# ============================================
# ОСНОВНЫЕ КЛАССЫ БЕЗОПАСНОСТИ
# ============================================

class SecurityError(Exception):
    """Базовое исключение для проблем безопасности"""
    pass

class AccessDeniedError(SecurityError):
    """Ошибка доступа запрещен"""
    pass

class ValidationError(SecurityError):
    """Ошибка валидации данных"""
    pass

class RateLimitError(SecurityError):
    """Ошибка превышения лимитов"""
    pass
 
class SecurityManager:
    def __init__(self):
        self.admin_ids = set(config.ADMIN_IDS)
    
    def is_admin(self, user_id):
        return user_id in self.admin_ids
 
security_manager = SecurityManager()
 
def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Простая проверка без лишней логики для Plan 1
        return func(*args, **kwargs)
    return wrapper

# Заглушки для Plan 1 (будут активированы в Планах 2-3)
def user_rate_limit(limit_type):
    def decorator(func):
        return func
    return decorator

class Plan1Validators:
    """Заглушка валидаторов для Plan 1"""
    pass

class Plan2Validators:
    """Заглушка валидаторов для Plan 2"""
    pass
