"""
utils/validators.py - Валидация данных
Функции для проверки корректности входящих данных, URLs, файлов и команд
ПЛАН 1: Базовая валидация + заглушки для будущих планов
"""

import re
import os
import mimetypes
from typing import Dict, List, Optional, Tuple, Union, Any
from urllib.parse import urlparse
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)

class ValidationError(Exception):
    """Исключение для ошибок валидации"""
    pass

class BaseValidator:
    """Базовый класс для валидаторов"""
    
    @staticmethod
    def is_valid_telegram_id(user_id: Union[int, str]) -> bool:
        """Проверка корректности Telegram ID"""
        try:
            user_id = int(user_id)
            # Telegram ID всегда положительное число
            return user_id > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_username(username: str) -> bool:
        """Проверка корректности Telegram username"""
        if not username:
            return False
        
        # Убираем @ если есть
        username = username.lstrip('@')
        
        # Username может содержать только буквы, цифры и подчеркивания
        # Длина от 5 до 32 символов
        pattern = r'^[a-zA-Z0-9_]{5,32}$'
        return bool(re.match(pattern, username))
    
    @staticmethod
    def is_valid_group_id(group_id: Union[int, str]) -> bool:
        """Проверка корректности ID группы"""
        try:
            group_id = int(group_id)
            # ID группы в Telegram отрицательное число
            return group_id < 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_thread_id(thread_id: Union[int, str]) -> bool:
        """Проверка корректности ID треда (топика)"""
        try:
            thread_id = int(thread_id)
            # Thread ID всегда положительное число
            return thread_id > 0
        except (ValueError, TypeError):
            return False

class URLValidator:
    """Валидация URL и ссылок"""
    
    # Паттерны для различных музыкальных платформ
    MUSIC_PLATFORMS = {
        'spotify': [
            r'https?://open\.spotify\.com/',
            r'https?://spotify\.link/',
        ],
        'apple_music': [
            r'https?://music\.apple\.com/',
            r'https?://itunes\.apple\.com/',
        ],
        'youtube_music': [
            r'https?://music\.youtube\.com/',
            r'https?://youtu\.be/',
            r'https?://youtube\.com/watch',
        ],
        'deezer': [
            r'https?://deezer\.com/',
            r'https?://www\.deezer\.com/',
        ],
        'soundcloud': [
            r'https?://soundcloud\.com/',
            r'https?://on\.soundcloud\.com/',
        ],
        'bandcamp': [
            r'https?://.*\.bandcamp\.com/',
        ],
        'yandex_music': [
            r'https?://music\.yandex\.',
        ],
        'vk_music': [
            r'https?://vk\.com/music',
            r'https?://m\.vk\.com/music',
        ],
        'other': [
            r'https?://.*',  # Любая другая ссылка
        ]
    }
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Базовая проверка корректности URL"""
        if not url:
            return False
        
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def is_music_platform_url(url: str) -> Tuple[bool, Optional[str]]:
        """Проверка, является ли URL ссылкой на музыкальную платформу"""
        if not URLValidator.is_valid_url(url):
            return False, None
        
        for platform, patterns in URLValidator.MUSIC_PLATFORMS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return True, platform
        
        return False, None
    
    @staticmethod
    def extract_urls_from_text(text: str) -> List[str]:
        """Извлечение всех URL из текста"""
        if not text:
            return []
        
        # Паттерн для поиска URL
        url_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
        
        urls = re.findall(url_pattern, text, re.IGNORECASE)
        
        # Дополнительная проверка корректности найденных URL
        valid_urls = []
        for url in urls:
            if URLValidator.is_valid_url(url):
                valid_urls.append(url)
        
        return valid_urls
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        """Очистка и нормализация URL"""
        if not url:
            return ""
        
        # Убираем пробелы
        url = url.strip()
        
        # Добавляем https:// если нет протокола
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url

class TextValidator:
    """Валидация текстовых данных"""
    
    @staticmethod
    def is_valid_message_length(text: str, min_length: int = 1, max_length: int = 4096) -> bool:
        """Проверка длины сообщения Telegram"""
        if not text:
            return min_length == 0
        
        return min_length <= len(text) <= max_length
    
    @staticmethod
    def contains_forbidden_words(text: str, forbidden_words: List[str] = None) -> bool:
        """Проверка на запрещенные слова"""
        if not text or not forbidden_words:
            return False
        
        text_lower = text.lower()
        return any(word.lower() in text_lower for word in forbidden_words)
    
    @staticmethod
    def is_spam_like(text: str) -> bool:
        """Простая проверка на спам (много повторяющихся символов/слов)"""
        if not text:
            return False
        
        # Проверка на много повторяющихся символов
        repeated_chars = re.findall(r'(.)\1{4,}', text)  # 5+ одинаковых символов подряд
        if repeated_chars:
            return True
        
        # Проверка на много эмодзи подряд
        emoji_pattern = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]{10,}'
        if re.search(emoji_pattern, text):
            return True
        
        return False
    
    @staticmethod
    def extract_mentions(text: str) -> List[str]:
        """Извлечение всех упоминаний @username из текста"""
        if not text:
            return []
        
        mentions = re.findall(r'@(\w+)', text)
        return [mention for mention in mentions if BaseValidator.is_valid_username(mention)]

class CommandValidator:
    """Валидация команд бота"""
    
    # Команды доступные всем пользователям
    PUBLIC_COMMANDS = [
        '/start', '/help', '/mystat', '/last10links', '/last30links'
    ]
    
    # Команды только для администраторов
    ADMIN_COMMANDS = [
        '/menu', '/resetmenu', '/enablebot', '/disablebot',
        '/setmode_conservative', '/setmode_normal', '/setmode_burst', '/setmode_adminburst',
        '/currentmode', '/reloadmodes', '/clearlinks'
    ]
    
    # ПЛАН 2: Команды кармы (ЗАГЛУШКИ)
    KARMA_COMMANDS = [
        '/karma', '/leaderboard', '/topusers'
    ]
    
    # ПЛАН 3: ИИ команды (ЗАГЛУШКИ)
    AI_COMMANDS = [
        '/ai', '/ask', '/help_ai'
    ]
    
    # ПЛАН 4: Backup команды (ЗАГЛУШКИ)
    BACKUP_COMMANDS = [
        '/downloadsql', '/backupstatus', '/backuphelp', '/restore'
    ]
    
    @staticmethod
    def is_valid_command(command: str) -> bool:
        """Проверка корректности команды"""
        if not command:
            return False
        
        if not command.startswith('/'):
            return False
        
        # Команда может содержать только буквы, цифры и подчеркивания
        command_name = command[1:]  # Убираем /
        pattern = r'^[a-zA-Z0-9_]+$'
        
        return bool(re.match(pattern, command_name))
    
    @staticmethod
    def is_public_command(command: str) -> bool:
        """Проверка, является ли команда публичной"""
        return command.split()[0] in CommandValidator.PUBLIC_COMMANDS
    
    @staticmethod
    def is_admin_command(command: str) -> bool:
        """Проверка, является ли команда административной"""
        base_command = command.split()[0]
        return base_command in CommandValidator.ADMIN_COMMANDS
    
    @staticmethod
    def validate_karma_command(command_text: str) -> Tuple[bool, Dict]:
        """ЗАГЛУШКА: Валидация команды кармы"""
        # TODO: Реализовать в Плане 2
        logger.debug("🔄 validate_karma_command - в разработке (План 2)")
        return False, {"error": "Команды кармы в разработке"}
    
    @staticmethod
    def parse_command_args(command_text: str) -> Tuple[str, List[str]]:
        """Разбор команды на саму команду и аргументы"""
        parts = command_text.split()
        if not parts:
            return "", []
        
        command = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        return command, args

class ConfigValidator:
    """Валидация конфигурации и переменных окружения"""
    
    @staticmethod
    def validate_bot_token(token: str) -> bool:
        """Проверка корректности токена бота"""
        if not token:
            return False
        
        # Токен бота должен соответствовать формату: число:строка
        pattern = r'^\d+:[A-Za-z0-9_-]+$'
        return bool(re.match(pattern, token))
    
    @staticmethod
    def validate_webhook_secret(secret: str) -> bool:
        """Проверка корректности секрета webhook"""
        if not secret:
            return False
        
        # Секрет должен быть достаточно длинным и содержать разные символы
        return len(secret) >= 16 and any(c.isalpha() for c in secret) and any(c.isdigit() for c in secret)
    
    @staticmethod
    def validate_database_url(url: str) -> bool:
        """Проверка корректности URL базы данных"""
        if not url:
            return False
        
        # PostgreSQL URL должен начинаться с postgresql://
        return url.startswith('postgresql://') or url.startswith('postgres://')
    
    @staticmethod
    def validate_admin_ids(ids_string: str) -> Tuple[bool, List[int]]:
        """Валидация строки с ID администраторов"""
        if not ids_string:
            return False, []
        
        try:
            ids = [int(id_str.strip()) for id_str in ids_string.split(',') if id_str.strip()]
            
            # Проверяем каждый ID
            valid_ids = []
            for user_id in ids:
                if BaseValidator.is_valid_telegram_id(user_id):
                    valid_ids.append(user_id)
                else:
                    logger.warning(f"Некорректный admin ID: {user_id}")
            
            return len(valid_ids) > 0, valid_ids
            
        except ValueError:
            return False, []
    
    @staticmethod
    def validate_whitelist(whitelist_string: str) -> Tuple[bool, List[int]]:
        """Валидация whitelist топиков"""
        if not whitelist_string:
            return False, []
        
        try:
            thread_ids = [int(id_str.strip()) for id_str in whitelist_string.split(',') if id_str.strip()]
            
            # Проверяем каждый thread ID
            valid_ids = []
            for thread_id in thread_ids:
                if BaseValidator.is_valid_thread_id(thread_id):
                    valid_ids.append(thread_id)
                else:
                    logger.warning(f"Некорректный thread ID: {thread_id}")
            
            return len(valid_ids) > 0, valid_ids
            
        except ValueError:
            return False, []

# ============================================
# ПЛАН 3: ВАЛИДАЦИЯ ФАЙЛОВ И ФОРМ (ЗАГЛУШКИ)
# ============================================

class FileValidator:
    """ЗАГЛУШКА: Валидация загружаемых файлов"""
    
    # Разрешенные типы файлов для скриншотов
    ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    
    @staticmethod
    def validate_image_file(file_path: str) -> Tuple[bool, str]:
        """ЗАГЛУШКА: Валидация файла изображения"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 validate_image_file - в разработке (План 3)")
        return False, "Валидация файлов в разработке"
    
    @staticmethod
    def validate_backup_file(file_path: str) -> Tuple[bool, str]:
        """ЗАГЛУШКА: Валидация backup файла"""
        # TODO: Реализовать в Плане 4
        logger.debug("🔄 validate_backup_file - в разработке (План 4)")
        return False, "Валидация backup в разработке"

class FormValidator:
    """ЗАГЛУШКА: Валидация данных форм"""
    
    @staticmethod
    def validate_presave_request(form_data: Dict) -> Tuple[bool, List[str]]:
        """ЗАГЛУШКА: Валидация заявки на пресейв"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 validate_presave_request - в разработке (План 3)")
        return False, ["Валидация форм в разработке"]
    
    @staticmethod
    def validate_approval_claim(form_data: Dict) -> Tuple[bool, List[str]]:
        """ЗАГЛУШКА: Валидация заявки об одобрении"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 validate_approval_claim - в разработке (План 3)")
        return False, ["Валидация заявок в разработке"]

# ============================================
# ПЛАН 3: ВАЛИДАЦИЯ ИИ ЗАПРОСОВ (ЗАГЛУШКИ)
# ============================================

class AIValidator:
    """ЗАГЛУШКА: Валидация запросов к ИИ"""
    
    @staticmethod
    def validate_ai_prompt(prompt: str) -> Tuple[bool, str]:
        """ЗАГЛУШКА: Валидация промпта для ИИ"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 validate_ai_prompt - в разработке (План 3)")
        return False, "Валидация ИИ в разработке"
    
    @staticmethod
    def is_safe_content(text: str) -> bool:
        """ЗАГЛУШКА: Проверка безопасности контента для ИИ"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 is_safe_content - в разработке (План 3)")
        return True

# ============================================
# UTILITIES ДЛЯ РАБОТЫ С ВАЛИДАТОРАМИ
# ============================================

def validate_all_required_env_vars() -> Tuple[bool, List[str]]:
    """Валидация всех обязательных переменных окружения"""
    errors = []
    
    # Проверка BOT_TOKEN
    bot_token = os.getenv('BOT_TOKEN')
    if not ConfigValidator.validate_bot_token(bot_token):
        errors.append("BOT_TOKEN некорректен или отсутствует")
    
    # Проверка GROUP_ID
    group_id = os.getenv('GROUP_ID')
    if not BaseValidator.is_valid_group_id(group_id):
        errors.append("GROUP_ID некорректен или отсутствует")
    
    # Проверка ADMIN_IDS
    admin_ids = os.getenv('ADMIN_IDS')
    valid, _ = ConfigValidator.validate_admin_ids(admin_ids)
    if not valid:
        errors.append("ADMIN_IDS некорректны или отсутствуют")
    
    # Проверка DATABASE_URL
    db_url = os.getenv('DATABASE_URL')
    if not ConfigValidator.validate_database_url(db_url):
        errors.append("DATABASE_URL некорректен или отсутствует")
    
    # Проверка WHITELIST
    whitelist = os.getenv('WHITELIST')
    valid, _ = ConfigValidator.validate_whitelist(whitelist)
    if not valid:
        errors.append("WHITELIST некорректен или отсутствует")
    
    return len(errors) == 0, errors

def create_validation_report() -> Dict[str, Any]:
    """Создание отчета о валидации конфигурации"""
    report = {
        "timestamp": datetime.utcnow(),
        "valid": True,
        "errors": [],
        "warnings": [],
        "config_status": {}
    }
    
    try:
        # Валидация основных переменных
        valid, errors = validate_all_required_env_vars()
        report["valid"] = valid
        report["errors"] = errors
        
        # Детальная информация по каждой переменной
        bot_token = os.getenv('BOT_TOKEN')
        report["config_status"]["bot_token"] = ConfigValidator.validate_bot_token(bot_token)
        
        group_id = os.getenv('GROUP_ID')
        report["config_status"]["group_id"] = BaseValidator.is_valid_group_id(group_id)
        
        # Опциональные переменные
        webhook_secret = os.getenv('WEBHOOK_SECRET')
        if webhook_secret:
            report["config_status"]["webhook_secret"] = ConfigValidator.validate_webhook_secret(webhook_secret)
        else:
            report["warnings"].append("WEBHOOK_SECRET не установлен")
        
        logger.info(f"✅ Отчет валидации создан: {'✅ OK' if valid else '❌ ERRORS'}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания отчета валидации: {e}")
        report["valid"] = False
        report["errors"].append(f"Ошибка валидации: {e}")
    
    return report