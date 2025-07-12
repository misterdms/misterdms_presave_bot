"""
🛡️ Security System - Do Presave Reminder Bot v25+
Система безопасности и проверки прав доступа для всех планов
"""

import re
import hashlib
import hmac
import time
from functools import wraps
from typing import List, Optional, Dict, Any, Union, Callable
from urllib.parse import urlparse
import telebot
from telebot.types import Message, CallbackQuery, User as TelegramUser

from config import config
from utils.logger import get_logger, telegram_logger

logger = get_logger(__name__)

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
    """Основной менеджер безопасности"""
    
    def __init__(self):
        self.admin_ids = set(config.ADMIN_IDS)
        self.whitelist_threads = set(config.WHITELIST_THREADS)
        self.rate_limit_storage = {}  # Простое хранилище лимитов в памяти
        
        # Настройки лимитов
        self.rate_limits = {
            'admin_commands': {'max_calls': 100, 'window_seconds': 3600},    # 100 команд в час для админов
            'user_commands': {'max_calls': 20, 'window_seconds': 3600},     # 20 команд в час для пользователей
            'karma_changes': {'max_calls': 10, 'window_seconds': 300},      # 10 изменений кармы в 5 минут
            'ai_requests': {'max_calls': 50, 'window_seconds': 3600},       # 50 ИИ запросов в час
            'form_submissions': {'max_calls': 5, 'window_seconds': 300},    # 5 форм в 5 минут
            'backup_operations': {'max_calls': 3, 'window_seconds': 3600}   # 3 backup в час
        }
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка является ли пользователь админом"""
        return user_id in self.admin_ids
    
    def is_whitelisted_thread(self, thread_id: Optional[int]) -> bool:
        """Проверка находится ли топик в whitelist"""
        if thread_id is None:
            return False
        return thread_id in self.whitelist_threads
    
    def validate_telegram_user(self, user: TelegramUser) -> bool:
        """Валидация пользователя Telegram"""
        if not user:
            return False
            
        # Проверяем базовые поля
        if not user.id or user.id <= 0:
            return False
            
        # Проверяем что пользователь не бот (кроме нашего бота)
        if user.is_bot and user.id != int(config.BOT_TOKEN.split(':')[0]):
            logger.warning(f"🤖 Попытка доступа от бота: {user.id}")
            return False
            
        return True
    
    def check_rate_limit(self, user_id: int, operation_type: str) -> bool:
        """Проверка rate limit для пользователя"""
        if operation_type not in self.rate_limits:
            return True  # Нет ограничений для неизвестных операций
            
        limit_config = self.rate_limits[operation_type]
        key = f"{user_id}:{operation_type}"
        current_time = time.time()
        
        # Получаем историю вызовов
        if key not in self.rate_limit_storage:
            self.rate_limit_storage[key] = []
            
        calls = self.rate_limit_storage[key]
        
        # Очищаем старые записи
        window_start = current_time - limit_config['window_seconds']
        calls[:] = [call_time for call_time in calls if call_time > window_start]
        
        # Проверяем лимит
        if len(calls) >= limit_config['max_calls']:
            logger.warning(
                f"⚠️ Rate limit превышен: пользователь {user_id}, операция {operation_type}",
                user_id=user_id,
                operation_type=operation_type,
                calls_count=len(calls),
                limit=limit_config['max_calls']
            )
            return False
            
        # Добавляем текущий вызов
        calls.append(current_time)
        return True
    
    def sanitize_input(self, text: str, max_length: int = 1000, 
                      allow_html: bool = False, allow_sql: bool = False) -> str:
        """Очистка пользовательского ввода"""
        if not isinstance(text, str):
            raise ValidationError("Ввод должен быть строкой")
            
        # Ограничиваем длину
        if len(text) > max_length:
            text = text[:max_length]
            
        # Удаляем опасные символы если не разрешен HTML
        if not allow_html:
            # Экранируем HTML
            text = text.replace('&', '&amp;')
            text = text.replace('<', '&lt;')
            text = text.replace('>', '&gt;')
            text = text.replace('"', '&quot;')
            text = text.replace("'", '&#x27;')
            
        # Проверяем на SQL инъекции если не разрешен SQL
        if not allow_sql:
            sql_keywords = [
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
                'UNION', 'EXEC', 'EXECUTE', '--', ';', 'xp_', 'sp_'
            ]
            
            text_upper = text.upper()
            for keyword in sql_keywords:
                if keyword in text_upper:
                    logger.warning(
                        f"🚨 Попытка SQL инъекции: {keyword} в тексте",
                        text=text[:100],
                        detected_keyword=keyword
                    )
                    # Заменяем на безопасный текст
                    text = text.replace(keyword.lower(), '[FILTERED]')
                    text = text.replace(keyword.upper(), '[FILTERED]')
                    
        return text.strip()
    
    def validate_url(self, url: str, allowed_domains: Optional[List[str]] = None) -> bool:
        """Валидация URL"""
        try:
            parsed = urlparse(url)
            
            # Проверяем схему
            if parsed.scheme not in ['http', 'https']:
                return False
                
            # Проверяем домен
            if not parsed.netloc:
                return False
                
            # Проверяем разрешенные домены
            if allowed_domains:
                domain = parsed.netloc.lower()
                if not any(allowed_domain in domain for allowed_domain in allowed_domains):
                    return False
                    
            return True
            
        except Exception:
            return False
    
    def validate_username(self, username: str) -> bool:
        """Валидация username Telegram"""
        if not username:
            return False
            
        # Убираем @ если есть
        username = username.lstrip('@')
        
        # Проверяем формат (буквы, цифры, подчеркивания, 5-32 символа)
        pattern = r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$'
        return bool(re.match(pattern, username))
    
    def verify_webhook_signature(self, body: bytes, signature: str) -> bool:
        """Проверка подписи webhook от Telegram"""
        try:
            secret_key = config.WEBHOOK_SECRET.encode()
            expected_signature = hmac.new(secret_key, body, hashlib.sha256).hexdigest()
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки webhook подписи: {e}")
            return False

# Глобальный экземпляр менеджера безопасности
security_manager = SecurityManager()

# ============================================
# ДЕКОРАТОРЫ ДЛЯ ПРОВЕРКИ ПРАВ
# ============================================

def admin_required(func: Callable) -> Callable:
    """Декоратор для проверки прав админа"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Ищем объект с user_id среди аргументов
        user_id = None
        
        # Проверяем аргументы
        for arg in args:
            if isinstance(arg, (Message, CallbackQuery)):
                user_id = arg.from_user.id
                break
            elif hasattr(arg, 'user_id'):
                user_id = arg.user_id
                break
            elif hasattr(arg, 'from_user') and hasattr(arg.from_user, 'id'):
                user_id = arg.from_user.id
                break
                
        # Проверяем kwargs
        if user_id is None:
            user_id = kwargs.get('user_id') or kwargs.get('admin_id')
            
        if user_id is None:
            logger.error("❌ Не удалось определить user_id для проверки прав админа")
            raise AccessDeniedError("Не удалось определить пользователя")
            
        if not security_manager.is_admin(user_id):
            telegram_logger.user_action(
                user_id, 
                f"попытка доступа к админской функции {func.__name__}",
                function=func.__name__,
                access_denied=True
            )
            raise AccessDeniedError("Доступ запрещен: требуются права админа")
            
        # Проверяем rate limit для админов
        if not security_manager.check_rate_limit(user_id, 'admin_commands'):
            raise RateLimitError("Превышен лимит команд админа")
            
        telegram_logger.admin_action(
            user_id,
            f"вызов функции {func.__name__}",
            function=func.__name__
        )
        
        return func(*args, **kwargs)
    
    return wrapper

def user_rate_limit(operation_type: str = 'user_commands'):
    """Декоратор для проверки rate limit пользователя"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Ищем user_id
            user_id = None
            
            for arg in args:
                if isinstance(arg, (Message, CallbackQuery)):
                    user_id = arg.from_user.id
                    break
                elif hasattr(arg, 'user_id'):
                    user_id = arg.user_id
                    break
                    
            if user_id is None:
                user_id = kwargs.get('user_id')
                
            if user_id and not security_manager.check_rate_limit(user_id, operation_type):
                raise RateLimitError(f"Превышен лимит операций типа {operation_type}")
                
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

def whitelisted_thread_required(func: Callable) -> Callable:
    """Декоратор для проверки что команда выполняется в разрешенном топике"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Ищем thread_id среди аргументов
        thread_id = None
        
        for arg in args:
            if isinstance(arg, Message):
                thread_id = getattr(arg, 'message_thread_id', None)
                break
            elif hasattr(arg, 'thread_id'):
                thread_id = arg.thread_id
                break
                
        if thread_id is None:
            thread_id = kwargs.get('thread_id')
            
        # Если thread_id не определен, считаем что это ЛС
        if thread_id is None:
            return func(*args, **kwargs)
            
        if not security_manager.is_whitelisted_thread(thread_id):
            logger.warning(
                f"⚠️ Попытка выполнения команды в неразрешенном топике: {thread_id}",
                thread_id=thread_id,
                function=func.__name__
            )
            raise AccessDeniedError("Команда недоступна в этом топике")
            
        return func(*args, **kwargs)
    
    return wrapper

def validate_input(**validation_rules):
    """Декоратор для валидации входных параметров"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Валидируем kwargs согласно правилам
            for param_name, rules in validation_rules.items():
                if param_name in kwargs:
                    value = kwargs[param_name]
                    
                    # Проверяем тип
                    if 'type' in rules and not isinstance(value, rules['type']):
                        raise ValidationError(f"Параметр {param_name} должен быть типа {rules['type'].__name__}")
                    
                    # Проверяем длину для строк
                    if isinstance(value, str):
                        max_length = rules.get('max_length', 1000)
                        if len(value) > max_length:
                            raise ValidationError(f"Параметр {param_name} превышает максимальную длину {max_length}")
                        
                        # Очищаем ввод
                        allow_html = rules.get('allow_html', False)
                        allow_sql = rules.get('allow_sql', False)
                        kwargs[param_name] = security_manager.sanitize_input(
                            value, max_length, allow_html, allow_sql
                        )
                    
                    # Проверяем числовые диапазоны
                    if isinstance(value, (int, float)):
                        if 'min_value' in rules and value < rules['min_value']:
                            raise ValidationError(f"Параметр {param_name} меньше минимального значения {rules['min_value']}")
                        if 'max_value' in rules and value > rules['max_value']:
                            raise ValidationError(f"Параметр {param_name} больше максимального значения {rules['max_value']}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# ============================================
# СПЕЦИАЛИЗИРОВАННЫЕ ВАЛИДАТОРЫ ПО ПЛАНАМ
# ============================================

class Plan1Validators:
    """Валидаторы для Плана 1 - базовый функционал"""
    
    @staticmethod
    def validate_limit_mode(mode: str) -> bool:
        """Валидация режима лимитов"""
        valid_modes = ['CONSERVATIVE', 'NORMAL', 'BURST', 'ADMIN_BURST']
        return mode.upper() in valid_modes
    
    @staticmethod
    def validate_reminder_text(text: str) -> str:
        """Валидация текста напоминания"""
        if len(text) > 500:
            raise ValidationError("Текст напоминания слишком длинный (макс. 500 символов)")
        
        return security_manager.sanitize_input(text, max_length=500, allow_html=True)

class Plan2Validators:
    """Валидаторы для Плана 2 - система кармы"""
    
    @staticmethod
    def validate_karma_change(change: int) -> bool:
        """Валидация изменения кармы"""
        # Карма не может быть изменена более чем на ±50 за раз
        if abs(change) > 50:
            raise ValidationError("Слишком большое изменение кармы (макс. ±50)")
        return True
    
    @staticmethod
    def validate_karma_amount(karma: int) -> bool:
        """Валидация общего количества кармы"""
        if karma < 0:
            raise ValidationError("Карма не может быть отрицательной")
        if karma > config.MAX_KARMA:
            raise ValidationError(f"Карма не может превышать {config.MAX_KARMA}")
        return True
    
    @staticmethod
    def validate_ratio_format(ratio_string: str) -> tuple[int, int]:
        """Валидация формата соотношения просьбы:карма"""
        # Поддерживаем форматы: "15:12", "15-12", "15/12"
        pattern = r'^(\d+)[:\-/](\d+)$'
        match = re.match(pattern, ratio_string.strip())
        
        if not match:
            raise ValidationError("Неверный формат соотношения. Используйте: 15:12")
        
        requests_count = int(match.group(1))
        karma_count = int(match.group(2))
        
        if requests_count > 1000:
            raise ValidationError("Количество просьб не может превышать 1000")
        if karma_count > config.MAX_KARMA:
            raise ValidationError(f"Карма не может превышать {config.MAX_KARMA}")
            
        return requests_count, karma_count

class Plan3Validators:
    """Валидаторы для Плана 3 - ИИ и интерактивные формы"""
    
    @staticmethod
    def validate_ai_prompt(prompt: str) -> str:
        """Валидация запроса к ИИ"""
        if len(prompt) > 2000:
            raise ValidationError("Запрос к ИИ слишком длинный (макс. 2000 символов)")
        
        # Проверяем на запрещенные фразы
        forbidden_phrases = [
            'ignore previous instructions',
            'forget everything',
            'system prompt',
            'jailbreak',
            'act as if'
        ]
        
        prompt_lower = prompt.lower()
        for phrase in forbidden_phrases:
            if phrase in prompt_lower:
                raise ValidationError(f"Запрос содержит запрещенную фразу: {phrase}")
        
        return security_manager.sanitize_input(prompt, max_length=2000)
    
    @staticmethod
    def validate_file_upload(file_size: int, file_type: str) -> bool:
        """Валидация загружаемых файлов"""
        # Максимальный размер 10MB
        max_size = 10 * 1024 * 1024
        if file_size > max_size:
            raise ValidationError("Файл слишком большой (макс. 10MB)")
        
        # Разрешенные типы файлов для скриншотов
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if file_type not in allowed_types:
            raise ValidationError("Неподдерживаемый тип файла. Разрешены: JPEG, PNG, WebP")
        
        return True
    
    @staticmethod
    def validate_presave_links(links: List[str]) -> List[str]:
        """Валидация ссылок для пресейвов"""
        if len(links) > 10:
            raise ValidationError("Слишком много ссылок (макс. 10)")
        
        validated_links = []
        
        # Разрешенные домены для пресейвов
        allowed_domains = [
            'spotify.com', 'music.apple.com', 'music.youtube.com',
            'soundcloud.com', 'bandcamp.com', 'deezer.com',
            'tidal.com', 'music.amazon.com', 'linktr.ee',
            'fanlink.to', 'smarturl.it', 'ffm.to'
        ]
        
        for link in links:
            if not security_manager.validate_url(link, allowed_domains):
                raise ValidationError(f"Неразрешенная ссылка: {link}")
            validated_links.append(link)
        
        return validated_links

class Plan4Validators:
    """Валидаторы для Плана 4 - backup система"""
    
    @staticmethod
    def validate_backup_filename(filename: str) -> bool:
        """Валидация имени backup файла"""
        # Должен начинаться с presave_bot_backup_ и заканчиваться на .zip
        pattern = r'^presave_bot_backup_\d{8}_\d{6}\.zip$'
        return bool(re.match(pattern, filename))
    
    @staticmethod
    def validate_backup_age(created_date: str) -> int:
        """Валидация возраста backup и возврат дней"""
        try:
            from datetime import datetime
            created = datetime.strptime(created_date, '%Y-%m-%d')
            age_days = (datetime.now() - created).days
            
            if age_days < 0:
                raise ValidationError("Дата создания backup не может быть в будущем")
            if age_days > 365:
                raise ValidationError("Backup слишком старый (более года)")
                
            return age_days
        except ValueError:
            raise ValidationError("Неверный формат даты. Используйте: YYYY-MM-DD")

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def check_admin_rights(user_id: int) -> bool:
    """Простая проверка прав админа"""
    return security_manager.is_admin(user_id)

def check_whitelist_thread(thread_id: Optional[int]) -> bool:
    """Простая проверка whitelist топика"""
    return security_manager.is_whitelisted_thread(thread_id)

def sanitize_user_input(text: str, max_length: int = 1000) -> str:
    """Простая очистка пользовательского ввода"""
    return security_manager.sanitize_input(text, max_length)

def validate_telegram_username(username: str) -> bool:
    """Простая валидация username"""
    return security_manager.validate_username(username)

def extract_user_id_from_message(message: Message) -> int:
    """Извлечение user_id из сообщения"""
    return message.from_user.id

def extract_thread_id_from_message(message: Message) -> Optional[int]:
    """Извлечение thread_id из сообщения"""
    return getattr(message, 'message_thread_id', None)

def log_security_event(event_type: str, user_id: int, details: Dict[str, Any]):
    """Логирование событий безопасности"""
    telegram_logger.user_action(
        user_id,
        f"security_event: {event_type}",
        event_type=event_type,
        **details
    )

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = [
    # Основные классы
    'SecurityManager', 'SecurityError', 'AccessDeniedError', 'ValidationError', 'RateLimitError',
    
    # Глобальный экземпляр
    'security_manager',
    
    # Декораторы
    'admin_required', 'user_rate_limit', 'whitelisted_thread_required', 'validate_input',
    
    # Валидаторы по планам
    'Plan1Validators', 'Plan2Validators', 'Plan3Validators', 'Plan4Validators',
    
    # Вспомогательные функции
    'check_admin_rights', 'check_whitelist_thread', 'sanitize_user_input', 
    'validate_telegram_username', 'extract_user_id_from_message', 
    'extract_thread_id_from_message', 'log_security_event'
]

if __name__ == "__main__":
    # Тестирование системы безопасности
    
    print("🧪 Тестирование системы безопасности...")
    
    # Тест валидации
    try:
        text = security_manager.sanitize_input("<script>alert('xss')</script>Hello World!")
        print(f"✅ Очистка XSS: {text}")
    except Exception as e:
        print(f"❌ Ошибка очистки: {e}")
    
    # Тест валидации URL
    valid_url = security_manager.validate_url("https://spotify.com/track/123")
    invalid_url = security_manager.validate_url("ftp://evil.com/malware")
    print(f"✅ Валидация URL: spotify.com = {valid_url}, evil.com = {invalid_url}")
    
    # Тест валидации username
    valid_username = security_manager.validate_username("@test_user_123")
    invalid_username = security_manager.validate_username("@123invalid")
    print(f"✅ Валидация username: test_user_123 = {valid_username}, 123invalid = {invalid_username}")
    
    # Тест проверки админских прав
    admin_check = security_manager.is_admin(471560832)  # Первый админ из конфига
    print(f"✅ Проверка админа: {admin_check}")
    
    # Тест валидаторов планов
    try:
        Plan2Validators.validate_karma_change(5)
        requests, karma = Plan2Validators.validate_ratio_format("15:12")
        print(f"✅ Валидация кармы: изменение +5, соотношение {requests}:{karma}")
    except Exception as e:
        print(f"❌ Ошибка валидации кармы: {e}")
    
    print("✅ Тестирование безопасности завершено!")
