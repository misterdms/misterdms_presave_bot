"""
🔍 Data Validators - Do Presave Reminder Bot v25+
Система валидации данных, backup файлов, AI запросов и защиты от инъекций

ПРИНЦИПЫ БЕЗОПАСНОСТИ:
- Валидация всех пользовательских данных
- Защита от SQL-инъекций и code injection
- Проверка backup файлов перед restore
- Валидация AI запросов и ответов
- Санитизация входных данных
"""

import re
import os
import json
import zipfile
import hashlib
import mimetypes
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timezone
from urllib.parse import urlparse
from dataclasses import dataclass
from enum import Enum

from config import config
from utils.logger import get_logger

logger = get_logger(__name__)

class ValidationResult:
    """Результат валидации"""
    
    def __init__(self, is_valid: bool, message: str = "", data: Any = None, errors: List[str] = None):
        self.is_valid = is_valid
        self.message = message
        self.data = data
        self.errors = errors or []
    
    def __bool__(self):
        return self.is_valid
    
    def __str__(self):
        return f"ValidationResult(valid={self.is_valid}, message='{self.message}')"

class FileType(Enum):
    """Типы файлов для валидации"""
    IMAGE = "image"
    DOCUMENT = "document"
    BACKUP = "backup"
    AUDIO = "audio"
    VIDEO = "video"
    UNKNOWN = "unknown"

# ============================================
# БАЗОВЫЕ ВАЛИДАТОРЫ
# ============================================

class BaseValidator:
    """Базовый класс для валидаторов"""
    
    @staticmethod
    def sanitize_string(text: str, max_length: int = 1000, allow_html: bool = False) -> str:
        """
        Санитизация строки
        
        Args:
            text: Исходная строка
            max_length: Максимальная длина
            allow_html: Разрешить HTML теги
            
        Returns:
            str: Санитизированная строка
        """
        if not isinstance(text, str):
            return ""
        
        # Обрезка по длине
        text = text[:max_length]
        
        # Удаление HTML тегов если не разрешены
        if not allow_html:
            text = re.sub(r'<[^>]+>', '', text)
        
        # Удаление опасных символов
        text = re.sub(r'[<>"\'\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
        
        # Нормализация пробелов
        text = ' '.join(text.split())
        
        return text.strip()
    
    @staticmethod
    def is_valid_integer(value: Any, min_value: int = None, max_value: int = None) -> ValidationResult:
        """Валидация целого числа"""
        try:
            int_value = int(value)
            
            if min_value is not None and int_value < min_value:
                return ValidationResult(False, f"Значение {int_value} меньше минимального {min_value}")
            
            if max_value is not None and int_value > max_value:
                return ValidationResult(False, f"Значение {int_value} больше максимального {max_value}")
            
            return ValidationResult(True, "Валидное целое число", int_value)
            
        except (ValueError, TypeError):
            return ValidationResult(False, f"'{value}' не является целым числом")
    
    @staticmethod
    def is_valid_float(value: Any, min_value: float = None, max_value: float = None) -> ValidationResult:
        """Валидация числа с плавающей точкой"""
        try:
            float_value = float(value)
            
            if min_value is not None and float_value < min_value:
                return ValidationResult(False, f"Значение {float_value} меньше минимального {min_value}")
            
            if max_value is not None and float_value > max_value:
                return ValidationResult(False, f"Значение {float_value} больше максимального {max_value}")
            
            return ValidationResult(True, "Валидное число", float_value)
            
        except (ValueError, TypeError):
            return ValidationResult(False, f"'{value}' не является числом")

# ============================================
# ВАЛИДАТОРЫ TELEGRAM ДАННЫХ
# ============================================

class TelegramValidator:
    """Валидация данных Telegram"""
    
    @staticmethod
    def validate_user_id(user_id: Any) -> ValidationResult:
        """Валидация ID пользователя Telegram"""
        result = BaseValidator.is_valid_integer(user_id, min_value=1, max_value=999999999999)
        
        if not result.is_valid:
            return ValidationResult(False, f"Некорректный user_id: {result.message}")
        
        return ValidationResult(True, "Валидный user_id", result.data)
    
    @staticmethod
    def validate_chat_id(chat_id: Any) -> ValidationResult:
        """Валидация ID чата/группы"""
        result = BaseValidator.is_valid_integer(chat_id, min_value=-999999999999, max_value=999999999999)
        
        if not result.is_valid:
            return ValidationResult(False, f"Некорректный chat_id: {result.message}")
        
        return ValidationResult(True, "Валидный chat_id", result.data)
    
    @staticmethod
    def validate_message_id(message_id: Any) -> ValidationResult:
        """Валидация ID сообщения"""
        result = BaseValidator.is_valid_integer(message_id, min_value=1)
        
        if not result.is_valid:
            return ValidationResult(False, f"Некорректный message_id: {result.message}")
        
        return ValidationResult(True, "Валидный message_id", result.data)
    
    @staticmethod
    def validate_username(username: str) -> ValidationResult:
        """Валидация username Telegram"""
        if not isinstance(username, str):
            return ValidationResult(False, "Username должен быть строкой")
        
        # Удаление @
        username = username.lstrip('@')
        
        # Проверка формата
        if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
            return ValidationResult(False, "Username должен содержать 5-32 символа (буквы, цифры, _)")
        
        return ValidationResult(True, "Валидный username", username)
    
    @staticmethod
    def validate_callback_data(data: str) -> ValidationResult:
        """Валидация callback_data для inline кнопок"""
        if not isinstance(data, str):
            return ValidationResult(False, "Callback data должна быть строкой")
        
        if len(data) > 64:
            return ValidationResult(False, "Callback data не может быть длиннее 64 символов")
        
        # Проверка на допустимые символы
        if not re.match(r'^[a-zA-Z0-9_\-:.]+$', data):
            return ValidationResult(False, "Callback data содержит недопустимые символы")
        
        return ValidationResult(True, "Валидная callback data", data)

# ============================================
# ВАЛИДАТОРЫ ССЫЛОК И URL
# ============================================

class URLValidator:
    """Валидация URL и ссылок"""
    
    # Поддерживаемые музыкальные платформы
    SUPPORTED_PLATFORMS = {
        'spotify.com': 'Spotify',
        'music.apple.com': 'Apple Music',
        'music.youtube.com': 'YouTube Music',
        'youtu.be': 'YouTube',
        'youtube.com': 'YouTube',
        'soundcloud.com': 'SoundCloud',
        'bandcamp.com': 'Bandcamp',
        'deezer.com': 'Deezer',
        'tidal.com': 'Tidal',
        'music.amazon.com': 'Amazon Music',
        'linktr.ee': 'Linktree',
        'fanlink.to': 'FanLink',
        'smarturl.it': 'SmartURL',
        'feature.fm': 'Feature.fm'
    }
    
    @staticmethod
    def validate_url(url: str) -> ValidationResult:
        """Базовая валидация URL"""
        if not isinstance(url, str):
            return ValidationResult(False, "URL должен быть строкой")
        
        url = url.strip()
        
        if not url:
            return ValidationResult(False, "URL не может быть пустым")
        
        # Добавление протокола если отсутствует
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            parsed = urlparse(url)
            
            if not parsed.netloc:
                return ValidationResult(False, "Некорректный формат URL")
            
            # Проверка на подозрительные символы
            if re.search(r'[<>"\'\x00-\x1F\x7F-\x9F]', url):
                return ValidationResult(False, "URL содержит недопустимые символы")
            
            return ValidationResult(True, "Валидный URL", url)
            
        except Exception as e:
            return ValidationResult(False, f"Ошибка парсинга URL: {e}")
    
    @staticmethod
    def validate_music_link(url: str) -> ValidationResult:
        """Валидация ссылки на музыкальную платформу"""
        url_result = URLValidator.validate_url(url)
        
        if not url_result.is_valid:
            return url_result
        
        url = url_result.data
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Удаление www.
        domain = re.sub(r'^www\.', '', domain)
        
        # Проверка поддерживаемых платформ
        platform = None
        for supported_domain, platform_name in URLValidator.SUPPORTED_PLATFORMS.items():
            if domain == supported_domain or domain.endswith('.' + supported_domain):
                platform = platform_name
                break
        
        if not platform:
            return ValidationResult(
                False, 
                f"Неподдерживаемая платформа: {domain}",
                errors=[f"Поддерживаются: {', '.join(URLValidator.SUPPORTED_PLATFORMS.values())}"]
            )
        
        # Дополнительные проверки для конкретных платформ
        validation_errors = []
        
        # Spotify - проверка формата
        if platform == 'Spotify':
            if not re.search(r'(track|album|playlist|artist)/[a-zA-Z0-9]+', url):
                validation_errors.append("Spotify ссылка должна содержать track, album, playlist или artist")
        
        # YouTube - проверка формата
        elif platform in ['YouTube', 'YouTube Music']:
            if not re.search(r'(watch\?v=|embed/|youtu\.be/)[a-zA-Z0-9_-]+', url):
                validation_errors.append("YouTube ссылка должна содержать video ID")
        
        if validation_errors:
            return ValidationResult(False, "Некорректный формат ссылки", errors=validation_errors)
        
        return ValidationResult(True, f"Валидная ссылка {platform}", {
            'url': url,
            'platform': platform,
            'domain': domain
        })
    
    @staticmethod
    def extract_links_from_text(text: str) -> List[str]:
        """Извлечение всех ссылок из текста"""
        if not isinstance(text, str):
            return []
        
        # Паттерн для поиска URL
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        
        links = re.findall(url_pattern, text)
        
        # Также ищем ссылки без протокола
        domain_pattern = r'(?:www\.)?(?:' + '|'.join(re.escape(domain) for domain in URLValidator.SUPPORTED_PLATFORMS.keys()) + r')[^\s]*'
        domain_links = re.findall(domain_pattern, text)
        
        # Добавляем протокол к ссылкам без него
        for link in domain_links:
            if link not in links and not link.startswith(('http://', 'https://')):
                links.append('https://' + link)
        
        return list(set(links))  # Удаление дубликатов

# ============================================
# ВАЛИДАТОРЫ ФАЙЛОВ
# ============================================

class FileValidator:
    """Валидация файлов"""
    
    # Разрешенные типы файлов
    ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    ALLOWED_DOCUMENT_TYPES = {'application/pdf', 'text/plain', 'application/zip'}
    ALLOWED_AUDIO_TYPES = {'audio/mpeg', 'audio/wav', 'audio/ogg'}
    
    # Максимальные размеры файлов (в байтах)
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB
    MAX_BACKUP_SIZE = 100 * 1024 * 1024  # 100MB
    
    @staticmethod
    def get_file_type(mime_type: str) -> FileType:
        """Определение типа файла по MIME-type"""
        if mime_type.startswith('image/'):
            return FileType.IMAGE
        elif mime_type.startswith('audio/'):
            return FileType.AUDIO
        elif mime_type.startswith('video/'):
            return FileType.VIDEO
        elif mime_type in FileValidator.ALLOWED_DOCUMENT_TYPES:
            return FileType.DOCUMENT
        elif mime_type == 'application/zip':
            return FileType.BACKUP
        else:
            return FileType.UNKNOWN
    
    @staticmethod
    def validate_file_size(file_size: int, file_type: FileType) -> ValidationResult:
        """Валидация размера файла"""
        max_sizes = {
            FileType.IMAGE: FileValidator.MAX_IMAGE_SIZE,
            FileType.DOCUMENT: FileValidator.MAX_DOCUMENT_SIZE,
            FileType.BACKUP: FileValidator.MAX_BACKUP_SIZE,
            FileType.AUDIO: FileValidator.MAX_DOCUMENT_SIZE,
            FileType.VIDEO: FileValidator.MAX_DOCUMENT_SIZE
        }
        
        max_size = max_sizes.get(file_type, FileValidator.MAX_DOCUMENT_SIZE)
        
        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            file_size_mb = file_size / (1024 * 1024)
            return ValidationResult(
                False, 
                f"Файл слишком большой: {file_size_mb:.1f}MB (максимум {max_size_mb:.0f}MB)"
            )
        
        return ValidationResult(True, "Размер файла в норме")
    
    @staticmethod
    def validate_file_name(filename: str) -> ValidationResult:
        """Валидация имени файла"""
        if not isinstance(filename, str):
            return ValidationResult(False, "Имя файла должно быть строкой")
        
        filename = filename.strip()
        
        if not filename:
            return ValidationResult(False, "Имя файла не может быть пустым")
        
        # Проверка на недопустимые символы
        if re.search(r'[<>:"/\\|?*\x00-\x1f]', filename):
            return ValidationResult(False, "Имя файла содержит недопустимые символы")
        
        # Проверка длины
        if len(filename) > 255:
            return ValidationResult(False, "Имя файла слишком длинное (максимум 255 символов)")
        
        return ValidationResult(True, "Валидное имя файла", filename)
    
    @staticmethod
    def validate_image_file(file_path: str = None, file_data: bytes = None, filename: str = None) -> ValidationResult:
        """Валидация изображения"""
        try:
            # Проверка имени файла
            if filename:
                name_result = FileValidator.validate_file_name(filename)
                if not name_result.is_valid:
                    return name_result
            
            # Проверка размера
            if file_data:
                size_result = FileValidator.validate_file_size(len(file_data), FileType.IMAGE)
                if not size_result.is_valid:
                    return size_result
            
            # Проверка MIME-типа
            if filename:
                mime_type, _ = mimetypes.guess_type(filename)
                if mime_type not in FileValidator.ALLOWED_IMAGE_TYPES:
                    return ValidationResult(
                        False, 
                        f"Неподдерживаемый тип изображения: {mime_type}",
                        errors=[f"Поддерживаются: {', '.join(FileValidator.ALLOWED_IMAGE_TYPES)}"]
                    )
            
            return ValidationResult(True, "Валидное изображение")
            
        except Exception as e:
            return ValidationResult(False, f"Ошибка валидации изображения: {e}")

# ============================================
# ВАЛИДАТОРЫ BACKUP ФАЙЛОВ
# ============================================

class BackupValidator:
    """Валидация backup файлов"""
    
    REQUIRED_BACKUP_FILES = {
        'metadata.json',
        'tables_data.json',
        'restore_script.sql',
        'README_RESTORE.txt'
    }
    
    @staticmethod
    def validate_backup_file(file_path: str = None, file_data: bytes = None) -> ValidationResult:
        """Валидация backup ZIP архива"""
        try:
            if file_path and os.path.exists(file_path):
                # Валидация файла по пути
                return BackupValidator._validate_backup_from_path(file_path)
            elif file_data:
                # Валидация данных файла
                return BackupValidator._validate_backup_from_data(file_data)
            else:
                return ValidationResult(False, "Не предоставлен файл для валидации")
                
        except Exception as e:
            logger.error(f"❌ Ошибка валидации backup: {e}")
            return ValidationResult(False, f"Ошибка валидации backup: {e}")
    
    @staticmethod
    def _validate_backup_from_path(file_path: str) -> ValidationResult:
        """Валидация backup файла по пути"""
        if not zipfile.is_zipfile(file_path):
            return ValidationResult(False, "Файл не является ZIP архивом")
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                return BackupValidator._validate_zip_contents(zip_file)
        except zipfile.BadZipFile:
            return ValidationResult(False, "Поврежденный ZIP архив")
    
    @staticmethod
    def _validate_backup_from_data(file_data: bytes) -> ValidationResult:
        """Валидация backup данных"""
        try:
            import io
            
            with zipfile.ZipFile(io.BytesIO(file_data), 'r') as zip_file:
                return BackupValidator._validate_zip_contents(zip_file)
        except zipfile.BadZipFile:
            return ValidationResult(False, "Поврежденный ZIP архив")
    
    @staticmethod
    def _validate_zip_contents(zip_file: zipfile.ZipFile) -> ValidationResult:
        """Валидация содержимого ZIP архива"""
        file_list = set(zip_file.namelist())
        
        # Проверка обязательных файлов
        missing_files = BackupValidator.REQUIRED_BACKUP_FILES - file_list
        if missing_files:
            return ValidationResult(
                False, 
                "Отсутствуют обязательные файлы backup",
                errors=[f"Отсутствуют: {', '.join(missing_files)}"]
            )
        
        try:
            # Проверка metadata.json
            metadata_content = zip_file.read('metadata.json')
            metadata = json.loads(metadata_content)
            
            required_metadata = {'backup_date', 'database_age_days', 'tables'}
            missing_metadata = required_metadata - set(metadata.keys())
            if missing_metadata:
                return ValidationResult(
                    False,
                    "Некорректный metadata.json",
                    errors=[f"Отсутствуют поля: {', '.join(missing_metadata)}"]
                )
            
            # Проверка tables_data.json
            tables_content = zip_file.read('tables_data.json')
            tables_data = json.loads(tables_content)
            
            if not isinstance(tables_data, dict):
                return ValidationResult(False, "tables_data.json должен содержать объект")
            
            return ValidationResult(True, "Валидный backup файл", {
                'metadata': metadata,
                'tables_count': len(tables_data),
                'backup_date': metadata.get('backup_date')
            })
            
        except json.JSONDecodeError as e:
            return ValidationResult(False, f"Ошибка JSON в backup: {e}")
        except KeyError as e:
            return ValidationResult(False, f"Отсутствует файл в backup: {e}")

# ============================================
# ВАЛИДАТОРЫ AI ЗАПРОСОВ
# ============================================

class AIValidator:
    """Валидация AI запросов и ответов"""
    
    # Максимальные длины для AI
    MAX_PROMPT_LENGTH = 4000
    MAX_RESPONSE_LENGTH = 8000
    
    # Запрещенные темы
    FORBIDDEN_TOPICS = {
        'nsfw', 'adult', 'porn', 'violence', 'drugs', 'weapons',
        'hate', 'racism', 'extremism', 'terrorism', 'illegal'
    }
    
    @staticmethod
    def validate_ai_prompt(prompt: str) -> ValidationResult:
        """Валидация prompt для AI"""
        if not isinstance(prompt, str):
            return ValidationResult(False, "Prompt должен быть строкой")
        
        prompt = prompt.strip()
        
        if not prompt:
            return ValidationResult(False, "Prompt не может быть пустым")
        
        if len(prompt) > AIValidator.MAX_PROMPT_LENGTH:
            return ValidationResult(
                False, 
                f"Prompt слишком длинный: {len(prompt)} символов (максимум {AIValidator.MAX_PROMPT_LENGTH})"
            )
        
        # Проверка на запрещенные темы
        prompt_lower = prompt.lower()
        for forbidden_topic in AIValidator.FORBIDDEN_TOPICS:
            if forbidden_topic in prompt_lower:
                return ValidationResult(
                    False, 
                    f"Prompt содержит запрещенную тему: {forbidden_topic}"
                )
        
        # Санитизация
        sanitized_prompt = BaseValidator.sanitize_string(prompt, AIValidator.MAX_PROMPT_LENGTH)
        
        return ValidationResult(True, "Валидный AI prompt", sanitized_prompt)
    
    @staticmethod
    def validate_ai_response(response: str) -> ValidationResult:
        """Валидация ответа от AI"""
        if not isinstance(response, str):
            return ValidationResult(False, "AI ответ должен быть строкой")
        
        response = response.strip()
        
        if not response:
            return ValidationResult(False, "AI ответ не может быть пустым")
        
        if len(response) > AIValidator.MAX_RESPONSE_LENGTH:
            return ValidationResult(
                False,
                f"AI ответ слишком длинный: {len(response)} символов (максимум {AIValidator.MAX_RESPONSE_LENGTH})"
            )
        
        # Санитизация (разрешаем HTML для форматирования)
        sanitized_response = BaseValidator.sanitize_string(response, AIValidator.MAX_RESPONSE_LENGTH, allow_html=True)
        
        return ValidationResult(True, "Валидный AI ответ", sanitized_response)

# ============================================
# ВАЛИДАТОРЫ КАРМЫ
# ============================================

class KarmaValidator:
    """Валидация операций с кармой"""
    
    @staticmethod
    def validate_karma_change(amount: Any) -> ValidationResult:
        """Валидация изменения кармы"""
        result = BaseValidator.is_valid_integer(amount, min_value=-1000, max_value=1000)
        
        if not result.is_valid:
            return ValidationResult(False, f"Некорректное значение кармы: {result.message}")
        
        if result.data == 0:
            return ValidationResult(False, "Изменение кармы не может быть равно нулю")
        
        return ValidationResult(True, "Валидное изменение кармы", result.data)
    
    @staticmethod
    def validate_karma_reason(reason: str) -> ValidationResult:
        """Валидация причины изменения кармы"""
        if not isinstance(reason, str):
            return ValidationResult(False, "Причина должна быть строкой")
        
        reason = reason.strip()
        
        if len(reason) < 3:
            return ValidationResult(False, "Причина слишком короткая (минимум 3 символа)")
        
        if len(reason) > 200:
            return ValidationResult(False, "Причина слишком длинная (максимум 200 символов)")
        
        # Санитизация
        sanitized_reason = BaseValidator.sanitize_string(reason, 200)
        
        return ValidationResult(True, "Валидная причина", sanitized_reason)

# ============================================
# ГЛАВНЫЙ ВАЛИДАТОР
# ============================================

class DataValidator:
    """Главный класс валидации данных"""
    
    def __init__(self):
        self.telegram = TelegramValidator()
        self.url = URLValidator()
        self.file = FileValidator()
        self.backup = BackupValidator()
        self.ai = AIValidator()
        self.karma = KarmaValidator()
        self.base = BaseValidator()
    
    def validate_message_data(self, data: Dict[str, Any]) -> ValidationResult:
        """Валидация данных сообщения"""
        errors = []
        
        # Валидация обязательных полей
        required_fields = ['user_id', 'chat_id', 'message_id']
        for field in required_fields:
            if field not in data:
                errors.append(f"Отсутствует поле: {field}")
        
        if errors:
            return ValidationResult(False, "Некорректные данные сообщения", errors=errors)
        
        # Валидация каждого поля
        user_id_result = self.telegram.validate_user_id(data['user_id'])
        if not user_id_result.is_valid:
            errors.append(f"user_id: {user_id_result.message}")
        
        chat_id_result = self.telegram.validate_chat_id(data['chat_id'])
        if not chat_id_result.is_valid:
            errors.append(f"chat_id: {chat_id_result.message}")
        
        message_id_result = self.telegram.validate_message_id(data['message_id'])
        if not message_id_result.is_valid:
            errors.append(f"message_id: {message_id_result.message}")
        
        if errors:
            return ValidationResult(False, "Ошибки валидации данных сообщения", errors=errors)
        
        return ValidationResult(True, "Валидные данные сообщения", {
            'user_id': user_id_result.data,
            'chat_id': chat_id_result.data,
            'message_id': message_id_result.data
        })

# ============================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ
# ============================================

# Глобальный экземпляр валидатора
_data_validator: Optional[DataValidator] = None

def get_data_validator() -> DataValidator:
    """Получение глобального экземпляра валидатора"""
    global _data_validator
    
    if _data_validator is None:
        _data_validator = DataValidator()
    
    return _data_validator

# Удобные функции для быстрой валидации
def validate_user_id(user_id: Any) -> ValidationResult:
    """Быстрая валидация user_id"""
    return TelegramValidator.validate_user_id(user_id)

def validate_url(url: str) -> ValidationResult:
    """Быстрая валидация URL"""
    return URLValidator.validate_url(url)

def validate_music_link(url: str) -> ValidationResult:
    """Быстрая валидация музыкальной ссылки"""
    return URLValidator.validate_music_link(url)

def sanitize_string(text: str, max_length: int = 1000) -> str:
    """Быстрая санитизация строки"""
    return BaseValidator.sanitize_string(text, max_length)

def extract_links(text: str) -> List[str]:
    """Быстрое извлечение ссылок из текста"""
    return URLValidator.extract_links_from_text(text)

# ============================================
# ДЕКОРАТОРЫ ДЛЯ ВАЛИДАЦИИ
# ============================================

def validate_input(**validators):
    """
    Декоратор для валидации входных параметров функции
    
    Args:
        **validators: Словарь валидаторов для параметров
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Валидация аргументов
            for param_name, validator in validators.items():
                if param_name in kwargs:
                    value = kwargs[param_name]
                    result = validator(value)
                    
                    if not result.is_valid:
                        logger.warning(f"Валидация {param_name} в {func.__name__}: {result.message}")
                        raise ValueError(f"Ошибка валидации {param_name}: {result.message}")
                    
                    # Заменяем значение на валидированное
                    kwargs[param_name] = result.data if result.data is not None else value
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

# ============================================
# ТЕСТИРОВАНИЕ
# ============================================

if __name__ == "__main__":
    """Тестирование системы валидации"""
    
    print("🧪 Тестирование DataValidator...")
    
    validator = DataValidator()
    
    # Тест валидации Telegram данных
    print("\n📱 Тест Telegram данных:")
    test_cases = [
        (123456789, True),  # Валидный user_id
        (-1001234567890, True),  # Валидный chat_id группы
        ("invalid", False),  # Невалидный ID
        (0, False)  # Недопустимый ID
    ]
    
    for test_value, expected in test_cases:
        result = validator.telegram.validate_user_id(test_value)
        status = "✅" if result.is_valid == expected else "❌"
        print(f"  {test_value}: {status} {result.message}")
    
    # Тест валидации URL
    print("\n🔗 Тест URL:")
    url_tests = [
        ("https://spotify.com/track/abc123", True),
        ("youtube.com/watch?v=abc123", True),
        ("invalid-url", False),
        ("javascript:alert(1)", False)
    ]
    
    for url, expected in url_tests:
        result = validator.url.validate_music_link(url)
        status = "✅" if result.is_valid == expected else "❌"
        print(f"  {url}: {status}")
    
    # Тест санитизации
    print("\n🧹 Тест санитизации:")
    dirty_text = "<script>alert('xss')</script>Нормальный текст"
    clean_text = sanitize_string(dirty_text)
    print(f"  Исходный: {dirty_text}")
    print(f"  Очищенный: {clean_text}")
    
    print("\n✅ Тестирование завершено")