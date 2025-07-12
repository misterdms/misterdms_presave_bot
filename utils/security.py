"""
Система безопасности Do Presave Reminder Bot v25+
Проверка прав администраторов, защита от инъекций, валидация данных
"""

import re
import html
import functools
from typing import List, Optional, Callable, Any, Union
import telebot
from telebot.types import Message, CallbackQuery

from utils.logger import get_logger

logger = get_logger(__name__)

class SecurityManager:
    """Менеджер безопасности для проверки прав и валидации"""
    
    def __init__(self, admin_ids: List[int], whitelist_threads: List[int]):
        """Инициализация менеджера безопасности"""
        self.admin_ids = set(admin_ids)
        self.whitelist_threads = set(whitelist_threads)
        
        # Паттерны для валидации
        self.username_pattern = re.compile(r'^@?[a-zA-Z0-9_]{5,32}$')
        self.url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        
        logger.info(f"Менеджер безопасности инициализирован: {len(self.admin_ids)} админов, "
                   f"{len(self.whitelist_threads)} разрешенных топиков")
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка является ли пользователь администратором"""
        return user_id in self.admin_ids
    
    def is_thread_allowed(self, thread_id: int) -> bool:
        """Проверка разрешен ли топик для работы бота"""
        return thread_id in self.whitelist_threads
    
    def validate_admin_message(self, message: Message) -> bool:
        """Комплексная проверка сообщения от админа"""
        if not message or not message.from_user:
            return False
            
        user_id = message.from_user.id
        
        # Проверка прав админа
        if not self.is_admin(user_id):
            logger.warning(f"Попытка доступа не-админа: {user_id}")
            return False
        
        # Проверка что сообщение в личке или разрешенном топике
        if message.chat.type == 'private':
            return True  # В личке админы могут все
        
        # В группе проверяем топик
        thread_id = getattr(message, 'message_thread_id', None)
        if thread_id and not self.is_thread_allowed(thread_id):
            logger.warning(f"Админ {user_id} пытается работать в неразрешенном топике {thread_id}")
            return False
        
        return True
    
    def validate_admin_callback(self, callback: CallbackQuery) -> bool:
        """Проверка callback от админа"""
        if not callback or not callback.from_user:
            return False
            
        user_id = callback.from_user.id
        
        # Проверка прав админа
        if not self.is_admin(user_id):
            logger.warning(f"Попытка callback не-админа: {user_id}")
            return False
        
        return True
    
    def sanitize_input(self, text: str, max_length: int = 1000) -> str:
        """Очистка пользовательского ввода от опасных символов"""
        if not text:
            return ""
        
        # Ограничение длины
        text = text[:max_length]
        
        # HTML escape для предотвращения XSS
        text = html.escape(text)
        
        # Удаление потенциально опасных символов
        # Оставляем только безопасные символы
        safe_pattern = re.compile(r'[^\w\s\-@#.,!?()+=:;/\'"«»\u0400-\u04FF]', re.UNICODE)
        text = safe_pattern.sub('', text)
        
        return text.strip()
    
    def validate_username(self, username: str) -> bool:
        """Валидация username Telegram"""
        if not username:
            return False
            
        # Убираем @ если есть
        username = username.lstrip('@')
        
        return bool(self.username_pattern.match(username))
    
    def extract_username(self, text: str) -> Optional[str]:
        """Извлечение username из текста"""
        if not text:
            return None
        
        # Ищем @username в тексте
        username_match = re.search(r'@([a-zA-Z0-9_]{5,32})', text)
        if username_match:
            return username_match.group(1)
        
        return None
    
    def detect_urls(self, text: str) -> List[str]:
        """Обнаружение URL в тексте"""
        if not text:
            return []
        
        urls = self.url_pattern.findall(text)
        return urls
    
    def validate_karma_amount(self, amount_str: str) -> Optional[int]:
        """Валидация количества кармы для команды /karma"""
        if not amount_str:
            return None
        
        # ПЛАН 2: Валидация кармы (ЗАГЛУШКА)
        # try:
        #     amount = int(amount_str)
        #     
        #     # Проверка разумных лимитов
        #     if amount < -1000 or amount > 1000:
        #         return None
        #         
        #     return amount
        # except ValueError:
        #     return None
        
        # Пока возвращаем None (функция не активна)
        return None
    
    def validate_ratio_format(self, ratio_str: str) -> Optional[tuple]:
        """Валидация формата соотношения для команды /ratiostat"""
        if not ratio_str:
            return None
        
        # ПЛАН 2: Валидация соотношения (ЗАГЛУШКА)
        # # Поддерживаем форматы: 15:12, 15-12
        # ratio_pattern = re.compile(r'^(\d+)[:_-](\d+)$')
        # match = ratio_pattern.match(ratio_str.strip())
        # 
        # if match:
        #     requests = int(match.group(1))
        #     karma = int(match.group(2))
        #     
        #     # Проверка разумных лимитов
        #     if requests > 10000 or karma > 100500:
        #         return None
        #         
        #     return (requests, karma)
        
        # Пока возвращаем None (функция не активна)
        return None
    
    def is_potential_spam(self, message: Message) -> bool:
        """Проверка сообщения на спам"""
        if not message or not message.text:
            return False
        
        text = message.text
        
        # Проверки на спам
        spam_indicators = [
            len(text) > 2000,  # Слишком длинное сообщение
            text.count('http') > 5,  # Много ссылок
            len(set(text.lower().split())) < len(text.split()) * 0.3,  # Много повторений
            re.search(r'(.)\1{10,}', text),  # Много одинаковых символов подряд
        ]
        
        spam_score = sum(spam_indicators)
        
        if spam_score >= 2:
            logger.warning(f"Обнаружен потенциальный спам от {message.from_user.id}: score={spam_score}")
            return True
        
        return False
    
    def rate_limit_check(self, user_id: int, action: str) -> bool:
        """Проверка лимитов частоты действий"""
        # ПЛАН 1: Простая заглушка, потом расширим
        # В будущем здесь будет полноценная система rate limiting
        
        # Админы не ограничены
        if self.is_admin(user_id):
            return True
        
        # Пока разрешаем всем (в продакшене добавим Redis/memory cache)
        return True

    def log_security_event(self, event_type: str, user_id: int, details: str = None):
        """Логирование событий безопасности"""
        logger.warning(f"Событие безопасности: {event_type} от пользователя {user_id}"
                      + (f" | {details}" if details else ""),
                      event_type=event_type, user_id=user_id, details=details)

def validate_admin(user_id: int, admin_ids: list) -> bool:
    """
    Простая функция валидации прав администратора
    
    Args:
        user_id: ID пользователя  
        admin_ids: Список ID администраторов
        
    Returns:
        bool: True если пользователь админ
    """
    return user_id in admin_ids

# Декораторы для проверки прав доступа

def admin_required(func: Callable) -> Callable:
    """Декоратор для проверки прав администратора"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Ищем message или callback в аргументах
        message_or_callback = None
        
        for arg in args:
            if isinstance(arg, (Message, CallbackQuery)):
                message_or_callback = arg
                break
        
        if not message_or_callback:
            logger.error("admin_required: не найден Message или CallbackQuery в аргументах")
            return
        
        user_id = message_or_callback.from_user.id
        
        # Получаем список админов из окружения
        import os
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        try:
            admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]
        except ValueError:
            logger.error("admin_required: неверный формат ADMIN_IDS")
            return
        
        if user_id not in admin_ids:
            logger.warning(f"Попытка доступа не-админа к функции {func.__name__}: {user_id}")
            
            # Отправляем сообщение об ошибке если есть bot в аргументах
            bot = None
            for arg in args:
                if hasattr(arg, 'send_message'):  # Это скорее всего bot
                    bot = arg
                    break
            
            if bot and isinstance(message_or_callback, Message):
                bot.send_message(
                    message_or_callback.chat.id,
                    "❌ Доступ запрещен! Команда доступна только администраторам."
                )
            elif bot and isinstance(message_or_callback, CallbackQuery):
                bot.answer_callback_query(
                    message_or_callback.id,
                    "❌ Доступ запрещен! Только для администраторов.",
                    show_alert=True
                )
            
            return
        
        # Логируем действие админа
        logger.info(f"Админ {user_id} выполняет {func.__name__}")
        
        return func(*args, **kwargs)
    
    return wrapper


def whitelist_required(func: Callable) -> Callable:
    """Декоратор для проверки разрешенного топика"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Ищем message в аргументах
        message = None
        
        for arg in args:
            if isinstance(arg, Message):
                message = arg
                break
        
        if not message:
            logger.error("whitelist_required: не найден Message в аргументах")
            return
        
        # Проверяем топик
        thread_id = getattr(message, 'message_thread_id', None)
        
        if thread_id:
            # Получаем whitelist из окружения
            import os
            whitelist_str = os.getenv('WHITELIST', '')
            try:
                whitelist_threads = [int(x.strip()) for x in whitelist_str.split(',') if x.strip()]
            except ValueError:
                logger.error("whitelist_required: неверный формат WHITELIST")
                return
            
            if thread_id not in whitelist_threads:
                logger.info(f"Сообщение в неразрешенном топике {thread_id} проигнорировано")
                return
        
        return func(*args, **kwargs)
    
    return wrapper


def rate_limited(action: str, max_per_hour: int = 60):
    """Декоратор для ограничения частоты действий"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Ищем message или callback в аргументах
            message_or_callback = None
            
            for arg in args:
                if isinstance(arg, (Message, CallbackQuery)):
                    message_or_callback = arg
                    break
            
            if not message_or_callback:
                return func(*args, **kwargs)
            
            user_id = message_or_callback.from_user.id
            
            # ПЛАН 1: Простая заглушка rate limiting
            # В будущем здесь будет полноценная проверка с учетом режимов лимитов
            
            # Пока просто выполняем функцию
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Утилиты для работы с пользователями

def get_user_id_from_message(message: Message) -> Optional[int]:
    """Безопасное получение ID пользователя из сообщения"""
    if not message or not message.from_user:
        return None
    return message.from_user.id

def get_username_from_message(message: Message) -> Optional[str]:
    """Безопасное получение username из сообщения"""
    if not message or not message.from_user:
        return None
    return message.from_user.username

def format_user_mention(user_id: int, username: str = None, first_name: str = None) -> str:
    """Форматирование упоминания пользователя"""
    if username:
        return f"@{username}"
    elif first_name:
        return f"<a href='tg://user?id={user_id}'>{html.escape(first_name)}</a>"
    else:
        return f"<a href='tg://user?id={user_id}'>Пользователь {user_id}</a>"

def extract_command_args(message: Message) -> List[str]:
    """Извлечение аргументов команды из сообщения"""
    if not message or not message.text:
        return []
    
    # Разделяем по пробелам, первый элемент - команда
    parts = message.text.strip().split()
    
    if len(parts) <= 1:
        return []
    
    # Возвращаем аргументы без команды
    return parts[1:]

def is_private_chat(message: Message) -> bool:
    """Проверка что сообщение в личном чате"""
    return message and message.chat.type == 'private'

def is_group_chat(message: Message) -> bool:
    """Проверка что сообщение в группе"""
    return message and message.chat.type in ['group', 'supergroup']


# ПЛАН 3: Дополнительные проверки для ИИ и форм (ЗАГЛУШКИ)

# def validate_ai_prompt(prompt: str) -> bool:
#     """Валидация промпта для ИИ"""
#     if not prompt or len(prompt.strip()) < 3:
#         return False
#     
#     # Проверка на потенциально вредные промпты
#     harmful_patterns = [
#         r'jailbreak',
#         r'ignore.{0,20}previous.{0,20}instructions',
#         r'act.{0,20}as.{0,20}dan',
#     ]
#     
#     for pattern in harmful_patterns:
#         if re.search(pattern, prompt.lower()):
#             return False
#     
#     return True

# def validate_screenshot_upload(file_info) -> bool:
#     """Валидация загружаемого скриншота"""
#     if not file_info:
#         return False
#     
#     # Проверка размера файла
#     max_size = int(os.getenv('SCREENSHOT_MAX_SIZE_MB', '10')) * 1024 * 1024
#     if file_info.file_size > max_size:
#         return False
#     
#     # Проверка типа файла (по расширению)
#     allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp']
#     file_path = file_info.file_path.lower()
#     
#     if not any(file_path.endswith(ext) for ext in allowed_extensions):
#         return False
#     
#     return True


if __name__ == "__main__":
    """Тестирование системы безопасности"""
    
    # Создание тестового менеджера
    security = SecurityManager(
        admin_ids=[12345, 67890],
        whitelist_threads=[2, 3]
    )
    
    # Тестирование функций
    print("Тестирование SecurityManager:")
    print(f"Админ 12345: {security.is_admin(12345)}")
    print(f"Не-админ 99999: {security.is_admin(99999)}")
    print(f"Топик 2 разрешен: {security.is_thread_allowed(2)}")
    print(f"Топик 999 разрешен: {security.is_thread_allowed(999)}")
    
    # Тестирование валидации
    print(f"Username 'testuser': {security.validate_username('testuser')}")
    print(f"Username '@invalid-user!': {security.validate_username('@invalid-user!')}")
    
    # Тестирование обнаружения URL
    test_text = "Привет! Вот ссылка: https://example.com и еще одна http://test.org"
    urls = security.detect_urls(test_text)
    print(f"Найденные URL: {urls}")
    
    # Тестирование очистки ввода
    dirty_input = "<script>alert('xss')</script>Привет мир!"
    clean_input = security.sanitize_input(dirty_input)
    print(f"Очищенный ввод: {clean_input}")
    
    print("✅ Тестирование безопасности завершено")
