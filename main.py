# Do Presave Reminder Bot by Mister DMS v24.06
# Продвинутый бот для музыкального сообщества с поддержкой скриншотов

# ================================
# 1. ИМПОРТЫ И НАСТРОЙКИ
# ================================

# Стандартные библиотеки Python (без дополнительных зависимостей)
import os
import logging
import sqlite3
import threading
import time
import json
import re
import urllib.parse
import urllib.request
import urllib.error
import html
import functools
import base64  # Для кодирования скриншотов в БД
import traceback  # Для детального логирования ошибок
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
from contextlib import contextmanager
from queue import Queue
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver

# Основные зависимости (из requirements.txt)
import telebot  # pyTelegramBotAPI==4.22.1
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv  # python-dotenv==1.0.0

# ================================
# 2. КОНФИГУРАЦИЯ И ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# ================================

# Загрузка .env файла
load_dotenv()

# Валидация обязательных переменных
REQUIRED_VARS = ["BOT_TOKEN", "GROUP_ID", "THREAD_ID", "ADMIN_IDS"]

# Основные настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", "-1002811959953"))
THREAD_ID = int(os.getenv("THREAD_ID", "3"))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Режимы лимитов (из Environment_Variables.md)
CONSERVATIVE_MAX_HOUR = int(os.getenv("CONSERVATIVE_MAX_HOUR", "60"))
CONSERVATIVE_COOLDOWN = int(os.getenv("CONSERVATIVE_COOLDOWN", "60"))
NORMAL_MAX_HOUR = int(os.getenv("NORMAL_MAX_HOUR", "180"))
NORMAL_COOLDOWN = int(os.getenv("NORMAL_COOLDOWN", "20"))
BURST_MAX_HOUR = int(os.getenv("BURST_MAX_HOUR", "600"))
BURST_COOLDOWN = int(os.getenv("BURST_COOLDOWN", "6"))
ADMIN_BURST_MAX_HOUR = int(os.getenv("ADMIN_BURST_MAX_HOUR", "1200"))
ADMIN_BURST_COOLDOWN = int(os.getenv("ADMIN_BURST_COOLDOWN", "3"))

# Дополнительные настройки
RESPONSE_DELAY = int(os.getenv("RESPONSE_DELAY", "3"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your_secret")
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))

# Четкая терминология из гайда
REMINDER_TEXT = os.getenv("REMINDER_TEXT", "🎧 Напоминаем: не забудь сделать пресейв артистов выше! ♥️")

# Настройки для работы со скриншотами
MAX_SCREENSHOT_SIZE = 10 * 1024 * 1024  # 10MB максимум для скриншота
SCREENSHOT_TTL_DAYS = 7  # Скриншоты хранятся 7 дней
ALLOWED_PHOTO_FORMATS = ['jpg', 'jpeg', 'png', 'webp']  # Telegram поддерживает

# Настройка продвинутого логирования для Render.com
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "structured")  # structured или simple
ENABLE_PERFORMANCE_LOGS = os.getenv("ENABLE_PERFORMANCE_LOGS", "true").lower() == "true"
CORRELATION_ID_HEADER = "X-Request-ID"

# Конфигурация логирования с учетом Render.com
def setup_logging():
    """Настройка логирования оптимизированная для Render.com"""
    
    if LOG_FORMAT == "structured":
        # JSON логирование для легкого парсинга в Render.com
        
        class StructuredFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                    "process_id": os.getpid(),
                    "thread_id": threading.current_thread().ident
                }
                
                # Добавление контекста если есть
                if hasattr(record, 'user_id'):
                    log_entry['user_id'] = record.user_id
                if hasattr(record, 'correlation_id'):
                    log_entry['correlation_id'] = record.correlation_id
                if hasattr(record, 'performance_ms'):
                    log_entry['performance_ms'] = record.performance_ms
                if hasattr(record, 'client_ip'):
                    log_entry['client_ip'] = record.client_ip
                
                # Обработка исключений
                if record.exc_info:
                    log_entry['exception'] = self.formatException(record.exc_info)
                
                return json.dumps(log_entry, ensure_ascii=False)
        
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        
    else:
        # Простое логирование с эмодзи
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL),
            format=format_string,
            handlers=[logging.StreamHandler()]
        )
        return
    
    # Настройка root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    
    # Отключение излишне подробных логов библиотек
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

setup_logging()
logger = logging.getLogger(__name__)

# ================================
# 3. ИНИЦИАЛИЗАЦИЯ БОТА И БАЗЫ ДАННЫХ
# ================================

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN)
# Исправление DeprecationWarning для SQLite datetime в Python 3.12+
import sqlite3
from datetime import datetime

def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.fromisoformat(s.decode())

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("datetime", convert_datetime)

# ================================
# 4. КОНСТАНТЫ И КОНФИГУРАЦИЯ ЛИМИТОВ
# ================================

class LimitMode(Enum):
    CONSERVATIVE = "conservative"
    NORMAL = "normal" 
    BURST = "burst"
    ADMIN_BURST = "admin_burst"

class UserRank(Enum):
    NEWBIE = "🥉 Новенький"
    RELIABLE = "🥈 Надежный пресейвер"
    MEGA = "🥇 Мега-человечище"
    AMBASSADOR = "💎 Амбассадорище"

class UserState(Enum):
    IDLE = "idle"
    # ПРОСЬБА О ПРЕСЕЙВЕ (публикация объявления)
    ASKING_PRESAVE_LINKS = "asking_presave_links" 
    ASKING_PRESAVE_COMMENT = "asking_presave_comment"
    # ЗАЯВКА О СОВЕРШЕННОМ ПРЕСЕЙВЕ (аппрув скриншотов)
    CLAIMING_PRESAVE_SCREENSHOTS = "claiming_presave_screenshots"
    CLAIMING_PRESAVE_COMMENT = "claiming_presave_comment"
    # АДМИНСКИЕ СОСТОЯНИЯ
    EDITING_REMINDER = "editing_reminder"
    WAITING_USERNAME_FOR_ANALYTICS = "waiting_username_for_analytics"

# Настройки лимитов по режимам из Environment_Variables.md
LIMIT_MODES = {
    LimitMode.CONSERVATIVE: {"max_hour": CONSERVATIVE_MAX_HOUR, "cooldown": CONSERVATIVE_COOLDOWN},
    LimitMode.NORMAL: {"max_hour": NORMAL_MAX_HOUR, "cooldown": NORMAL_COOLDOWN},
    LimitMode.BURST: {"max_hour": BURST_MAX_HOUR, "cooldown": BURST_COOLDOWN},
    LimitMode.ADMIN_BURST: {"max_hour": ADMIN_BURST_MAX_HOUR, "cooldown": ADMIN_BURST_COOLDOWN}
}

# Telegram API лимиты (официальные)
TELEGRAM_LIMITS = {
    "individual_chat": 1,  # сообщений в секунду
    "group_chat": 20,      # сообщений в минуту  
    "bulk_overall": 30,    # сообщений в секунду общий лимит
    "webhook_requests": 100 # запросов в секунду от Telegram
}

# Скрытые лимиты методов (из статьи на Хабре)
METHOD_LIMITS = {
    "send_message": {"count": 60, "period": 15},        # за 15 секунд
    "send_animation": {"count": 10, "period": 300},     # за 5 минут (!)
    "send_photo": {"count": 60, "period": 15},          # за 15 секунд
    "send_video": {"count": 35, "period": 60},          # за 60 секунд
    "send_audio": {"count": 40, "period": 60},          # за 60 секунд
    "edit_message_text": {"count": 140, "period": 40}, # без кнопок
    "edit_message_reply_markup": {"count": 100, "period": 30}
}

RANK_THRESHOLDS = {1: UserRank.NEWBIE, 6: UserRank.RELIABLE, 16: UserRank.MEGA, 31: UserRank.AMBASSADOR}
TELEGRAM_DOMAINS = ["t.me", "telegram.me", "telegram.org", "telegram.dog"]

# Структуры данных для состояний
@dataclass
class UserSession:
    state: UserState
    data: dict
    timestamp: datetime
    
    def is_expired(self) -> bool:
        return (datetime.now() - self.timestamp) > timedelta(hours=1)

@dataclass  
class PresaveRequestSession:
    """Сессия для ПРОСЬБЫ О ПРЕСЕЙВЕ (публикация объявления)"""
    links: List[str]
    comment: str
    user_id: int
    timestamp: datetime

@dataclass  
class PresaveClaimSession:
    """Сессия для ЗАЯВКИ О СОВЕРШЕННОМ ПРЕСЕЙВЕ (аппрув скриншотов)"""
    screenshots: List[str]  # file_id из Telegram
    comment: str
    user_id: int
    timestamp: datetime

# Глобальные переменные для системы очередей и лимитов
message_queue = Queue(maxsize=1000)
method_limits_tracker = defaultdict(list)
user_sessions: Dict[int, UserSession] = {}
presave_request_sessions: Dict[int, PresaveRequestSession] = {}
presave_claim_sessions: Dict[int, PresaveClaimSession] = {}
bot_status = {"enabled": True, "start_time": datetime.now()}

# ================================
# 5. УТИЛИТЫ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ================================

def is_external_link(url: str) -> bool:
    """Проверка является ли ссылка внешней (не Telegram) - blacklist подход"""
    return not any(domain in url.lower() for domain in TELEGRAM_DOMAINS)

def format_user_stats(user_data: dict) -> str:
    """Форматирование статистики пользователя с прогресс-барами и эмодзи"""
    requests_count = user_data.get('requests_count', 0)
    approvals_count = user_data.get('approvals_count', 0)
    links_count = user_data.get('links_count', 0)
    rank = user_data.get('rank', UserRank.NEWBIE)
    
    # Определение прогресса до следующего звания
    next_threshold = None
    for threshold, threshold_rank in RANK_THRESHOLDS.items():
        if approvals_count < threshold:
            next_threshold = threshold
            break
    
    progress_text = ""
    if next_threshold:
        progress_bar = format_progress_bar(approvals_count, next_threshold, 10)
        next_rank = RANK_THRESHOLDS[next_threshold]
        progress_text = f"\n🎯 Прогресс до {next_rank.value}: {progress_bar}"
    
    return f"""
👤 **Моя статистика:**

🔗 Всего ссылок: {links_count}
🎵 Просьб о пресейвах: {requests_count}
✅ Подтвержденных заявок: {approvals_count}
🏆 Звание: {rank.value}
📅 Последняя активность: сегодня
{'🌟 **Доверенный пресейвер** - автоматические аппрувы' if is_trusted_user(approvals_count) else ''}
{progress_text}

💪 {'Отличная работа! Продолжайте в том же духе!' if approvals_count >= 16 else 'Продолжайте делать пресейвы для роста!'}
"""

def get_user_rank(approval_count: int) -> UserRank:
    """Определение звания пользователя по количеству аппрувов"""
    for threshold in sorted(RANK_THRESHOLDS.keys(), reverse=True):
        if approval_count >= threshold:
            return RANK_THRESHOLDS[threshold]
    return UserRank.NEWBIE

def is_trusted_user(approval_count: int) -> bool:
    """Проверка является ли пользователь доверенным (>= 6 аппрувов)"""
    return approval_count >= 6

def validate_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in ADMIN_IDS

# Функции для работы со скриншотами
def encode_screenshot_for_db(file_content: bytes) -> str:
    """Кодирование скриншота в base64 для хранения в SQLite"""
    return base64.b64encode(file_content).decode('utf-8')

def decode_screenshot_from_db(encoded_content: str) -> bytes:
    """Декодирование скриншота из base64"""
    return base64.b64decode(encoded_content.encode('utf-8'))

def validate_screenshot_size(file_size: int) -> bool:
    """Проверка размера скриншота"""
    return file_size <= MAX_SCREENSHOT_SIZE

def cleanup_expired_screenshots():
    """Очистка просроченных скриншотов (старше 7 дней)"""
    cutoff_date = datetime.now() - timedelta(days=SCREENSHOT_TTL_DAYS)
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            # Конвертируем datetime в строку для SQLite
            cutoff_date_str = cutoff_date.isoformat()
            cursor.execute('DELETE FROM screenshot_files WHERE expires_at < ?', (cutoff_date_str,))
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                log_user_action(0, "SUCCESS", f"Cleaned up {deleted_count} expired screenshots")
    except Exception as e:
        log_user_action(0, "ERROR", f"Failed to cleanup screenshots: {str(e)}")

def get_file_extension_from_telegram(file_path: str) -> str:
    """Определение расширения файла из Telegram file_path"""
    return file_path.split('.')[-1].lower() if '.' in file_path else 'jpg'

# ПРОДВИНУТАЯ СИСТЕМА ЛОГИРОВАНИЯ для Render.com
def log_user_action(user_id: int, action: str, details: str = "", correlation_id: str = None, client_ip: str = None):
    """
    Продвинутое логирование действий пользователей оптимизированное для Render.com
    
    Категории эмодзи:
    🎯 - Команды и действия пользователей
    📨 - HTTP запросы и webhook
    💬 - Отправка сообщений
    🔄 - Процессы и операции
    ✅ - Успешные операции
    ❌ - Ошибки
    🚨 - Критические предупреждения
    💓 - Keep alive и health checks
    🔐 - Безопасность и аутентификация
    📊 - Статистика и аналитика
    🎵 - Просьбы о пресейвах (объявления)
    📸 - Заявки на аппрув (скриншоты)
    """
    
    # Определение эмодзи по категории действия
    emoji_map = {
        'COMMAND': '🎯',
        'HTTP_REQUEST': '📨', 
        'SEND_MESSAGE': '💬',
        'PROCESS': '🔄',
        'SUCCESS': '✅',
        'ERROR': '❌',
        'WARNING': '🚨',
        'KEEP_ALIVE': '💓',
        'SECURITY': '🔐',
        'STATS': '📊',
        'MUSIC': '🎵',
        'SCREENSHOT': '📸',
        'DATABASE': '💾',
        'CALLBACK': '📲',
        'WEBHOOK': '🔗',
        'RATE_LIMIT': '⏱️',
        'REQUEST_PRESAVE': '🎵',
        'CLAIM_PRESAVE': '📸',
        'ADMIN_APPROVE': '✅',
        'ADMIN_REJECT': '❌',
        'SCREENSHOT_UPLOAD': '📤',
        'LINK_DETECTED': '🔗'
    }
    
    # Автоматическое определение категории
    action_upper = action.upper()
    emoji = '🔍'  # default
    for category, category_emoji in emoji_map.items():
        if category in action_upper:
            emoji = category_emoji
            break
    
    # Форматирование сообщения
    if LOG_FORMAT == "structured":
        # Структурированное логирование
        extra = {
            'user_id': user_id,
            'action': action,
            'details': details,
            'correlation_id': correlation_id,
            'client_ip': client_ip
        }
        logger.info(f"{emoji} {action}", extra=extra)
    else:
        # Простое логирование с эмодзи
        message_parts = [f"{emoji} {action}"]
        if user_id:
            message_parts.append(f"User: {user_id}")
        if details:
            message_parts.append(f"Details: {details}")
        if correlation_id:
            message_parts.append(f"ReqID: {correlation_id}")
        if client_ip:
            message_parts.append(f"IP: {client_ip}")
        
        logger.info(" | ".join(message_parts))

def performance_logger(operation_name: str):
    """Декоратор для логирования производительности операций"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not ENABLE_PERFORMANCE_LOGS:
                return func(*args, **kwargs)
            
            start_time = time.time()
            correlation_id = getattr(wrapper, '_correlation_id', None)
            
            try:
                result = func(*args, **kwargs)
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                if LOG_FORMAT == "structured":
                    extra = {
                        'operation': operation_name,
                        'performance_ms': duration_ms,
                        'correlation_id': correlation_id,
                        'status': 'success'
                    }
                    logger.info(f"⚡ Operation completed: {operation_name}", extra=extra)
                else:
                    logger.info(f"⚡ {operation_name}: {duration_ms}ms")
                
                return result
            except Exception as e:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                if LOG_FORMAT == "structured":
                    extra = {
                        'operation': operation_name,
                        'performance_ms': duration_ms,
                        'correlation_id': correlation_id,
                        'status': 'error',
                        'error': str(e)
                    }
                    logger.error(f"❌ Operation failed: {operation_name}", extra=extra)
                else:
                    logger.error(f"❌ {operation_name}: {duration_ms}ms - ERROR: {str(e)}")
                
                raise
        return wrapper
    return decorator

@contextmanager
def request_context(correlation_id: str = None, user_id: int = None, client_ip: str = None):
    """Контекстный менеджер для трейсинга запросов"""
    if not correlation_id:
        correlation_id = f"req_{int(time.time() * 1000)}_{os.getpid()}"
    
    # Сохранение контекста в thread-local storage
    context = {
        'correlation_id': correlation_id,
        'user_id': user_id,
        'client_ip': client_ip,
        'start_time': time.time()
    }
    
    old_context = getattr(threading.current_thread(), '_request_context', None)
    threading.current_thread()._request_context = context
    
    try:
        if LOG_FORMAT == "structured":
            extra = {
                'correlation_id': correlation_id,
                'user_id': user_id,
                'client_ip': client_ip
            }
            logger.info("🔄 Request started", extra=extra)
        else:
            logger.info(f"🔄 Request started: {correlation_id}")
        
        yield context
    
    finally:
        duration_ms = round((time.time() - context['start_time']) * 1000, 2)
        
        if LOG_FORMAT == "structured":
            extra = {
                'correlation_id': correlation_id,
                'user_id': user_id,
                'client_ip': client_ip,
                'total_duration_ms': duration_ms
            }
            logger.info("✅ Request completed", extra=extra)
        else:
            logger.info(f"✅ Request completed: {correlation_id} in {duration_ms}ms")
        
        threading.current_thread()._request_context = old_context

def get_current_context():
    """Получение текущего контекста запроса"""
    return getattr(threading.current_thread(), '_request_context', {})

def centralized_error_logger(error: Exception, context: str = "", user_id: int = None, correlation_id: str = None):
    """Централизованное логирование ошибок с контекстом"""
    
    error_type = type(error).__name__
    error_message = str(error)
    
    # Определение критичности ошибки
    critical_errors = ['ConnectionError', 'TimeoutError', 'DatabaseError', 'MemoryError']
    is_critical = any(critical_type in error_type for critical_type in critical_errors)
    
    emoji = '🚨' if is_critical else '❌'
    level = logging.CRITICAL if is_critical else logging.ERROR
    
    if LOG_FORMAT == "structured":
        extra = {
            'error_type': error_type,
            'error_message': error_message,
            'context': context,
            'user_id': user_id,
            'correlation_id': correlation_id,
            'is_critical': is_critical,
            'stack_trace': traceback.format_exc() if hasattr(traceback, 'format_exc') else None
        }
        logger.log(level, f"{emoji} {error_type}: {error_message}", extra=extra)
    else:
        message_parts = [f"{emoji} {error_type}: {error_message}"]
        if context:
            message_parts.append(f"Context: {context}")
        if user_id:
            message_parts.append(f"User: {user_id}")
        if correlation_id:
            message_parts.append(f"ReqID: {correlation_id}")
        
        logger.log(level, " | ".join(message_parts))

def sanitize_for_logs(data: any) -> str:
    """Очистка чувствительных данных для логирования"""
    if isinstance(data, str):
        # Маскировка токенов и секретов
        data = re.sub(r'(token["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]{10,})', r'\1***MASKED***', data, flags=re.IGNORECASE)
        data = re.sub(r'(secret["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]{10,})', r'\1***MASKED***', data, flags=re.IGNORECASE)
        data = re.sub(r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']{6,})', r'\1***MASKED***', data, flags=re.IGNORECASE)
    
    return str(data)

# Функции для работы с лимитами API
def check_method_limit(method_name: str) -> bool:
    """Проверка не превышен ли лимит для конкретного метода API"""
    if method_name not in METHOD_LIMITS:
        return True
    
    current_time = time.time()
    method_data = METHOD_LIMITS[method_name]
    
    # Очистка старых записей
    method_limits_tracker[method_name] = [
        timestamp for timestamp in method_limits_tracker[method_name]
        if current_time - timestamp < method_data["period"]
    ]
    
    # Проверка лимита
    return len(method_limits_tracker[method_name]) < method_data["count"]

def get_method_cooldown(method_name: str) -> float:
    """Получение времени ожидания для метода при превышении лимита"""
    if method_name in METHOD_LIMITS:
        return METHOD_LIMITS[method_name]["period"] / METHOD_LIMITS[method_name]["count"]
    return 1.0

def get_current_limit_mode() -> LimitMode:
    """Получение текущего режима лимитов из БД"""
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', ('limit_mode',))
            result = cursor.fetchone()
            if result:
                return LimitMode(result[0])
    except:
        pass
    return LimitMode.NORMAL

def update_limit_mode(mode: LimitMode, admin_id: int):
    """Обновление режима лимитов админом"""
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', ('limit_mode', mode.value, datetime.now()))
        
        log_user_action(admin_id, "SUCCESS", f"Limit mode changed to {mode.value}")
    except Exception as e:
        log_user_action(admin_id, "ERROR", f"Failed to update limit mode: {str(e)}")

def format_progress_bar(current: int, target: int, length: int = 10) -> str:
    """Создание прогресс-бара для мотивации пользователей"""
    filled = int(length * current / target) if target > 0 else 0
    filled = min(filled, length)  # Ограничиваем максимумом
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {current}/{target}"

def extract_links_from_text(text: str) -> List[str]:
    """Извлечение всех ссылок из текста сообщения"""
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)

def safe_html_escape(text: str) -> str:
    """Безопасное экранирование HTML для защиты от XSS"""
    return html.escape(text, quote=True)

def parse_url_safely(url: str) -> Optional[urllib.parse.ParseResult]:
    """Безопасный парсинг URL с валидацией"""
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed if parsed.scheme in ['http', 'https'] else None
    except Exception:
        return None

def make_keep_alive_request(url: str) -> bool:
    """Выполнение keep-alive запроса с таймаутом"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'PresaveBot-KeepAlive/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, Exception):
        return False

@contextmanager
def database_transaction():
    """Контекстный менеджер для безопасных транзакций БД"""
    conn = sqlite3.connect('bot.db')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# Метрики и мониторинг для Render.com
class MetricsCollector:
    """Сбор метрик для мониторинга производительности"""
    
    def __init__(self):
        self.metrics = defaultdict(int)
        self.timings = defaultdict(list)
        self.lock = threading.Lock()
    
    def increment(self, metric_name: str, value: int = 1):
        """Увеличение счетчика метрики"""
        with self.lock:
            self.metrics[metric_name] += value
    
    def timing(self, metric_name: str, duration_ms: float):
        """Запись времени выполнения"""
        with self.lock:
            self.timings[metric_name].append(duration_ms)
            # Хранить только последние 100 измерений
            if len(self.timings[metric_name]) > 100:
                self.timings[metric_name] = self.timings[metric_name][-100:]
    
    def get_summary(self) -> dict:
        """Получение сводки метрик"""
        with self.lock:
            summary = {
                'counters': dict(self.metrics),
                'timings': {}
            }
            
            for metric, times in self.timings.items():
                if times:
                    summary['timings'][metric] = {
                        'count': len(times),
                        'avg_ms': round(sum(times) / len(times), 2),
                        'min_ms': round(min(times), 2),
                        'max_ms': round(max(times), 2)
                    }
            
            return summary

# Глобальный экземпляр для сбора метрик
metrics = MetricsCollector()

# Rate limiting для защиты от спама
class RateLimiter:
    """Простая система rate limiting"""
    
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = threading.Lock()
    
    def is_allowed(self, client_ip: str, max_requests: int = 10, window_seconds: int = 60) -> bool:
        """Проверка лимита запросов для IP"""
        with self.lock:
            current_time = time.time()
            
            # Очистка старых запросов
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if current_time - req_time < window_seconds
            ]
            
            # Проверка лимита
            if len(self.requests[client_ip]) >= max_requests:
                return False
            
            # Добавление нового запроса
            self.requests[client_ip].append(current_time)
            return True

rate_limiter = RateLimiter()

# Система безопасности webhook
class WebhookSecurity:
    """Проверка безопасности webhook запросов"""
    
    @staticmethod
    def verify_telegram_request(headers: dict, content_length: int, client_ip: str = None) -> bool:
        """Базовая проверка безопасности запроса от Telegram"""
        
        # Разрешаем health check запросы
        if content_length == 0:
            return True
            
        # Проверка secret token если установлен (это основная защита)
        if WEBHOOK_SECRET and WEBHOOK_SECRET != "your_secret":
            secret_header = headers.get('X-Telegram-Bot-Api-Secret-Token')
            if secret_header != WEBHOOK_SECRET:
                return False
        
        # Проверка размера запроса
        if content_length > 10 * 1024 * 1024:  # 10MB лимит
            return False
        
        # Если secret token правильный - пропускаем
        return True

security = WebhookSecurity()

def get_user_role(user_id: int) -> str:
    """Определение роли пользователя"""
    return 'admin' if user_id in ADMIN_IDS else 'user'

def safe_string(text: str, max_length: int = 100) -> str:
    """Безопасная обработка строк с Unicode"""
    if not text:
        return "Unknown"
    
    try:
        # Удаляем null bytes и управляющие символы
        cleaned = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        
        # Ограничиваем длину
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length-3] + "..."
        
        return cleaned
    except (UnicodeError, TypeError):
        return "Unknown"

def safe_username(user) -> str:
    """Безопасное получение username"""
    try:
        if hasattr(user, 'username') and user.username:
            return safe_string(user.username, 50)
        elif hasattr(user, 'first_name') and user.first_name:
            return safe_string(user.first_name, 50)
        else:
            return f"User_{user.id if hasattr(user, 'id') else 'Unknown'}"
    except Exception:
        return "Unknown"

def clean_url(url: str) -> str:
    """Очистка URL от протокола для правильного формирования webhook"""
    if not url:
        return url
    
    # Убираем протокол если есть
    if url.startswith('https://'):
        return url[8:]
    elif url.startswith('http://'):
        return url[7:]
    
    return url

def determine_chat_context(message) -> str:
    """
    Определяет контекст чата для адаптивного поведения команд
    
    Returns:
        - "private_chat": Личные сообщения
        - "correct_thread": Правильный топик в целевой группе  
        - "wrong_thread": Неправильный топик в целевой группе
        - "wrong_group": Другая группа
        - "unsupported": Неподдерживаемый тип чата
    """
    chat_type = message.chat.type
    chat_id = message.chat.id
    current_thread = getattr(message, 'message_thread_id', None)
    
    # Логируем для отладки
    log_user_action(
        user_id=message.from_user.id,
        action="PROCESS_CONTEXT_CHECK",
        details=f"ChatType: {chat_type}, ChatID: {chat_id}, Thread: {current_thread}, ExpectedGroup: {GROUP_ID}, ExpectedThread: {THREAD_ID}"
    )
    
    # Личные сообщения
    if chat_type == 'private':
        return "private_chat"
    
    # Проверка группы
    if chat_id == GROUP_ID:
        # Правильная группа, проверяем топик
        if current_thread == THREAD_ID:
            return "correct_thread"
        else:
            return "wrong_thread"
    else:
        # Неправильная группа
        return "wrong_group"

def get_context_adaptive_response(context: str, base_message: str) -> str:
    """
    Адаптирует ответ бота в зависимости от контекста
    """
    if context == "private_chat":
        return base_message + "\n\n💡 В личных сообщениях доступны интерактивные формы через меню."
    elif context == "correct_thread":
        return base_message + f"\n\n🎯 Работаем в правильном топике:  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}"
    else:
        return base_message

# ================================
# 6. ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ (продолжение)
# ================================

def cleanup_expired_sessions():
    """Автоматическая очистка просроченных сессий"""
    current_time = datetime.now()
    expired_users = []
    
    # Основные сессии
    for user_id, session in user_sessions.items():
        if session.is_expired():
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del user_sessions[user_id]
        log_user_action(user_id, "SESSION_EXPIRED", "Auto cleanup")
    
    # Очистка сессий просьб о пресейвах
    expired_request_users = []
    for user_id, session in presave_request_sessions.items():
        # Конвертируем datetime для сравнения если timestamp строка
        session_time = session.timestamp
        if isinstance(session_time, str):
            session_time = datetime.fromisoformat(session_time)
        if (current_time - session_time) > timedelta(hours=1):
            expired_request_users.append(user_id)
    
    for user_id in expired_request_users:
        del presave_request_sessions[user_id]
        log_user_action(user_id, "REQUEST_SESSION_EXPIRED", "Auto cleanup")
    
    # Очистка сессий заявок на аппрув
    expired_claim_users = []
    for user_id, session in presave_claim_sessions.items():
        if (current_time - session.timestamp) > timedelta(hours=1):
            expired_claim_users.append(user_id)
    
    for user_id in expired_claim_users:
        del presave_claim_sessions[user_id]
        log_user_action(user_id, "CLAIM_SESSION_EXPIRED", "Auto cleanup")

# ================================
# 7. ДЕКОРАТОРЫ ДЛЯ БЕЗОПАСНОСТИ И ЛИМИТОВ
# ================================

def admin_required(func):
    """Декоратор проверки админских прав с логированием"""
    @functools.wraps(func)
    def wrapper(message):
        user_id = message.from_user.id
        correlation_id = get_current_context().get('correlation_id')
        
        if user_id not in ADMIN_IDS:
            log_user_action(
                user_id=user_id,
                action="SECURITY_ACCESS_DENIED", 
                details=f"Attempted admin function: {func.__name__}",
                correlation_id=correlation_id
            )
            metrics.increment('security.access_denied')
            bot.reply_to(message, "❌ Вы не имеете прав на это действие")
            return
        
        log_user_action(
            user_id=user_id,
            action="SECURITY_ADMIN_ACCESS", 
            details=f"Admin function: {func.__name__}",
            correlation_id=correlation_id
        )
        metrics.increment('security.admin_access')
        return func(message)
    return wrapper

def rate_limit(method_name: str = "send_message"):
    """
    Декоратор ограничения частоты запросов с учетом скрытых лимитов
    Использует данные из METHOD_LIMITS для каждого типа запроса
    """
    def decorator(func):
        @functools.wraps(func)
        @performance_logger(f"rate_limit_{method_name}")
        def wrapper(*args, **kwargs):
            correlation_id = get_current_context().get('correlation_id')
            
            # Проверка лимитов для конкретного метода
            if not check_method_limit(method_name):
                cooldown_time = get_method_cooldown(method_name)
                
                log_user_action(
                    user_id=0,
                    action="RATE_LIMIT_HIT",
                    details=f"Method: {method_name}, Cooldown: {cooldown_time}s",
                    correlation_id=correlation_id
                )
                metrics.increment(f'rate_limit.hit.{method_name}')
                
                time.sleep(cooldown_time)
            
            # Добавляем запись в трекер
            method_limits_tracker[method_name].append(time.time())
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# === УСТАРЕВШИЕ ДЕКОРАТОРЫ ===
# Теперь используем только topic_restricted для унификации
# Все проверки топиков теперь через topic_restricted декоратор
# TODO: стереть, если всё работает корректно
# def group_only(func):
#     """Декоратор для функций, работающих только в группе"""
#     @functools.wraps(func)
#     def wrapper(message):
#         correlation_id = get_current_context().get('correlation_id')
#         
#         if message.chat.id != GROUP_ID:
#             if message.chat.type == 'private':
#                 log_user_action(
#                     user_id=message.from_user.id,
#                     action="WARNING_WRONG_CHAT",
#                     details=f"Private chat, expected group {GROUP_ID}",
#                     correlation_id=correlation_id
#                 )
#                 bot.reply_to(message, "Эта команда работает только в группе")
#             return
#         
#         return func(message)
#     return wrapper
#
# def thread_only(func):
#     """Декоратор для функций, работающих только в определенном топике"""
#     @functools.wraps(func)
#     def wrapper(message):
#         correlation_id = get_current_context().get('correlation_id')
#         
#         if message.chat.id == GROUP_ID and message.message_thread_id != THREAD_ID:
#             log_user_action(
#                 user_id=message.from_user.id,
#                 action="WARNING_WRONG_THREAD",
#                 details=f"Thread {message.message_thread_id}, expected {THREAD_ID}",
#                 correlation_id=correlation_id
#             )
#             bot.reply_to(message, f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}")
#             return
#         return func(message)
#     return wrapper

def safe_api_call(method_name: str = "send_message"):
    """
    Декоратор для безопасных вызовов API с обработкой ошибок 429
    Автоматический retry с exponential backoff
    """
    def decorator(func):
        @functools.wraps(func)
        @performance_logger(f"api_call_{method_name}")
        def wrapper(*args, **kwargs):
            correlation_id = get_current_context().get('correlation_id')
            max_retries = 3
            
            for attempt in range(max_retries):
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    
                    # Логирование успешного вызова
                    duration_ms = round((time.time() - start_time) * 1000, 2)
                    log_user_action(
                        user_id=0,
                        action="SUCCESS_API_CALL",
                        details=f"Method: {method_name}, Duration: {duration_ms}ms",
                        correlation_id=correlation_id
                    )
                    metrics.increment(f'api.success.{method_name}')
                    metrics.timing(f'api.duration.{method_name}', duration_ms)
                    
                    return result
                    
                except Exception as e:
                    error_str = str(e).lower()
                    duration_ms = round((time.time() - start_time) * 1000, 2)
                    
                    if any(keyword in error_str for keyword in ['429', 'rate limit', 'too many requests']):
                        wait_time = (2 ** attempt) * get_method_cooldown(method_name)
                        
                        log_user_action(
                            user_id=0,
                            action="ERROR_API_RATE_LIMIT",
                            details=f"Method: {method_name}, Attempt: {attempt+1}, Wait: {wait_time}s",
                            correlation_id=correlation_id
                        )
                        metrics.increment(f'api.rate_limit.{method_name}')
                        
                        if attempt < max_retries - 1:
                            time.sleep(wait_time)
                            continue
                    
                    # Логирование других ошибок
                    centralized_error_logger(
                        error=e,
                        context=f"API call {method_name} attempt {attempt+1}",
                        correlation_id=correlation_id
                    )
                    metrics.increment(f'api.error.{method_name}')
                    
                    if attempt == max_retries - 1:
                        raise Exception(f"Max retries exceeded for {method_name}: {str(e)}")
                    
            return None
        return wrapper
    return decorator

def log_performance(operation_name: str = None):
    """Декоратор для автоматического логирования производительности"""
    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            correlation_id = get_current_context().get('correlation_id')
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                log_user_action(
                    user_id=0,
                    action="PROCESS_PERFORMANCE",
                    details=f"Operation: {operation_name}, Duration: {duration_ms}ms",
                    correlation_id=correlation_id
                )
                metrics.timing(f'performance.{operation_name}', duration_ms)
                
                return result
                
            except Exception as e:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                centralized_error_logger(
                    error=e,
                    context=f"Performance tracking for {operation_name}",
                    correlation_id=correlation_id
                )
                metrics.increment(f'performance.error.{operation_name}')
                
                raise
        return wrapper
    return decorator

def topic_restricted(func):
    """Декоратор для ограничения работы только в определенном топике и ЛС"""
    @functools.wraps(func)
    def wrapper(message):
        user_id = message.from_user.id
        correlation_id = get_current_context().get('correlation_id')
        
        # В ЛС работаем всегда
        if message.chat.type == 'private':
            log_user_action(
                user_id=user_id,
                action="SUCCESS_PRIVATE_CHAT",
                details="Private chat allowed",
                correlation_id=correlation_id
            )
            return func(message)
        
        # Детальное логирование для отладки
        log_user_action(
            user_id=user_id,
            action="PROCESS_GROUP_MESSAGE",
            details=f"Chat: {message.chat.id}, Thread: {message.message_thread_id}, Expected Group: {GROUP_ID}, Expected Thread: {THREAD_ID}",
            correlation_id=correlation_id
        )
        
        # В группах проверяем ID группы
        if message.chat.id != GROUP_ID:
            log_user_action(
                user_id=user_id,
                action="WARNING_WRONG_GROUP",
                details=f"Chat {message.chat.id}, expected {GROUP_ID}",
                correlation_id=correlation_id
            )
            return
        
        # Проверяем топик (с обработкой None)
        current_thread = getattr(message, 'message_thread_id', None)
        if current_thread != THREAD_ID:
            log_user_action(
                user_id=user_id,
                action="WARNING_WRONG_THREAD",
                details=f"Thread {current_thread}, expected {THREAD_ID}",
                correlation_id=correlation_id
            )
            
            try:
                # Отправляем ответ в тот же топик где пришло сообщение
                bot.reply_to(message, 
                    f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
                    message_thread_id=current_thread)
            except Exception as e:
                log_user_action(
                    user_id=user_id,
                    action="ERROR",
                    details=f"Failed to send wrong thread message: {str(e)}",
                    correlation_id=correlation_id
                )
            return
        
        # Успешная проверка
        log_user_action(
            user_id=user_id,
            action="SUCCESS_CORRECT_THREAD",
            details=f"Correct thread {THREAD_ID}",
            correlation_id=correlation_id
        )
        
        return func(message)
    return wrapper

def request_logging(func):
    """Декоратор для логирования входящих запросов"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Извлечение информации о запросе
        user_id = None
        if args and hasattr(args[0], 'from_user'):
            user_id = args[0].from_user.id
        
        # Создание контекста запроса
        correlation_id = f"req_{int(time.time() * 1000)}_{threading.current_thread().ident}"
        
        with request_context(correlation_id=correlation_id, user_id=user_id):
            log_user_action(
                user_id=user_id,
                action="COMMAND_REQUEST",
                details=f"Function: {func.__name__}",
                correlation_id=correlation_id
            )
            
            try:
                result = func(*args, **kwargs)
                metrics.increment(f'command.success.{func.__name__}')
                return result
            except Exception as e:
                centralized_error_logger(
                    error=e,
                    context=f"Command handler {func.__name__}",
                    user_id=user_id,
                    correlation_id=correlation_id
                )
                metrics.increment(f'command.error.{func.__name__}')
                raise
    return wrapper

# ================================
# 8. РАБОТА С БАЗОЙ ДАННЫХ
# ================================

class DatabaseManager:
    def __init__(self, db_path: str):
        """Инициализация подключения к SQLite"""
        self.db_path = db_path
    
    def create_tables(self):
        """Создание всех необходимых таблиц с поддержкой скриншотов"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_activity TEXT DEFAULT (datetime('now'))
                )
            ''')
            
            # Таблица ПРОСЬБ О ПРЕСЕЙВАХ (объявления)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS presave_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    links TEXT,  -- JSON массив ссылок
                    comment TEXT,
                    message_id INTEGER,  -- ID поста в топике
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица ЗАЯВОК НА АППРУВ (скриншоты совершенных пресейвов)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS approval_claims (
                    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    screenshots TEXT,  -- JSON массив file_id
                    comment TEXT,
                    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
                    admin_id INTEGER,  -- кто обработал
                    created_at TEXT DEFAULT (datetime('now')),
                    processed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица скриншотов с TTL
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS screenshot_files (
                    file_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    file_content TEXT,  -- base64 encoded
                    file_size INTEGER,
                    file_extension TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    expires_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица ссылок пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_links (
                    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    link_url TEXT,
                    message_id INTEGER,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица настроек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT (datetime('now'))
                )
            ''')
            
            # Индексы для производительности
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_presave_requests_user_id ON presave_requests(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_approval_claims_status ON approval_claims(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_approval_claims_user_id ON approval_claims(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_screenshot_files_expires ON screenshot_files(expires_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_links_user_id ON user_links(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_links_created ON user_links(created_at)')
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        """Добавление нового пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name))
                
                if cursor.rowcount > 0:
                    log_user_action(user_id, "DATABASE", "New user added")
        except Exception as e:
            log_user_action(user_id, "ERROR", f"Failed to add user: {str(e)}")
    
    def update_user_activity(self, user_id: int):
        """Обновление времени последней активности"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET last_activity = ? WHERE user_id = ?
                ''', (datetime.now().isoformat(), user_id))
        except Exception as e:
            log_user_action(user_id, "ERROR", f"Failed to update activity: {str(e)}")
    
    # Методы с четкой терминологией
    def add_presave_request(self, user_id: int, links: List[str], comment: str, message_id: int) -> int:
        """Добавление ПРОСЬБЫ О ПРЕСЕЙВЕ (объявление)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO presave_requests (user_id, links, comment, message_id)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, json.dumps(links), comment, message_id))
                
                log_user_action(user_id, "REQUEST_PRESAVE", 
                              f"Links: {len(links)}, Comment: {comment[:50]}...")
                return cursor.lastrowid
        except Exception as e:
            log_user_action(user_id, "ERROR", f"Failed to add presave request: {str(e)}")
            return 0
    
    def add_approval_claim(self, user_id: int, screenshots: List[str], comment: str) -> int:
        """Добавление ЗАЯВКИ НА АППРУВ (скриншоты совершенного пресейва)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO approval_claims (user_id, screenshots, comment)
                    VALUES (?, ?, ?)
                ''', (user_id, json.dumps(screenshots), comment))
                
                log_user_action(user_id, "CLAIM_PRESAVE", 
                              f"Screenshots: {len(screenshots)}, Comment: {comment[:50]}...")
                return cursor.lastrowid
        except Exception as e:
            log_user_action(user_id, "ERROR", f"Failed to add approval claim: {str(e)}")
            return 0
    
    def approve_claim(self, claim_id: int, admin_id: int, approved: bool):
        """Подтверждение/отклонение заявки админом"""
        status = "approved" if approved else "rejected"
        action = "ADMIN_APPROVE" if approved else "ADMIN_REJECT"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE approval_claims 
                    SET status = ?, admin_id = ?, processed_at = ?
                    WHERE claim_id = ?
                ''', (status, admin_id, datetime.now().isoformat(), claim_id))
                
                log_user_action(admin_id, action, f"Claim ID: {claim_id}")
        except Exception as e:
            log_user_action(admin_id, "ERROR", f"Failed to approve claim: {str(e)}")
    
    def get_pending_claims(self) -> List[dict]:
        """Получение заявок ожидающих рассмотрения"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT claim_id, user_id, screenshots, comment, created_at
                    FROM approval_claims 
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                ''')
                
                claims = []
                for row in cursor.fetchall():
                    claims.append({
                        'claim_id': row[0],
                        'user_id': row[1], 
                        'screenshots': json.loads(row[2]),
                        'comment': row[3],
                        'created_at': row[4]
                    })
                return claims
        except Exception as e:
            log_user_action(0, "ERROR", f"Failed to get pending claims: {str(e)}")
            return []
    
    # Методы для работы со скриншотами
    def save_screenshot(self, file_id: str, user_id: int, file_content: bytes, 
                       file_extension: str) -> bool:
        """Сохранение скриншота в БД с TTL"""
        try:
            encoded_content = encode_screenshot_for_db(file_content)
            expires_at = (datetime.now() + timedelta(days=SCREENSHOT_TTL_DAYS)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO screenshot_files 
                    (file_id, user_id, file_content, file_size, file_extension, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (file_id, user_id, encoded_content, len(file_content), 
                      file_extension, expires_at))
            
            log_user_action(user_id, "SCREENSHOT_UPLOAD", 
                          f"Size: {len(file_content)} bytes, Ext: {file_extension}")
            return True
        except Exception as e:
            log_user_action(user_id, "ERROR", f"Screenshot save failed: {str(e)}")
            return False
    
    def get_screenshot(self, file_id: str) -> Optional[bytes]:
        """Получение скриншота из БД"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_content FROM screenshot_files 
                    WHERE file_id = ? AND expires_at > ?
                ''', (file_id, datetime.now().isoformat()))
                
                result = cursor.fetchone()
                if result:
                    return decode_screenshot_from_db(result[0])
                return None
        except Exception as e:
            log_user_action(0, "ERROR", f"Failed to get screenshot: {str(e)}")
            return None
    
    def cleanup_expired_screenshots(self):
        """Очистка просроченных скриншотов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM screenshot_files WHERE expires_at < ?
                ''', (datetime.now(),))
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    log_user_action(0, "SUCCESS", f"Cleaned up {deleted_count} expired screenshots")
        except Exception as e:
            log_user_action(0, "ERROR", f"Failed to cleanup screenshots: {str(e)}")
    
    def add_user_link(self, user_id: int, link_url: str, message_id: int):
        """Добавление ссылки пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO user_links (user_id, link_url, message_id)
                    VALUES (?, ?, ?)
                ''', (user_id, link_url, message_id))
                
                # Обновляем активность пользователя
                self.update_user_activity(user_id)
                
                log_user_action(user_id, "LINK_DETECTED", f"URL: {link_url[:50]}...")
        except Exception as e:
            log_user_action(user_id, "ERROR", f"Failed to add user link: {str(e)}")
    
    def get_user_stats(self, user_id: int) -> dict:
        """Получение статистики пользователя"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Количество просьб о пресейвах
                cursor.execute('SELECT COUNT(*) FROM presave_requests WHERE user_id = ?', (user_id,))
                requests_count = cursor.fetchone()[0]
                
                # Количество подтвержденных заявок
                cursor.execute('SELECT COUNT(*) FROM approval_claims WHERE user_id = ? AND status = "approved"', (user_id,))
                approvals_count = cursor.fetchone()[0]
                
                # Общее количество ссылок
                cursor.execute('SELECT COUNT(*) FROM user_links WHERE user_id = ?', (user_id,))
                links_count = cursor.fetchone()[0]
                
                return {
                    'requests_count': requests_count,
                    'approvals_count': approvals_count,
                    'links_count': links_count,
                    'rank': get_user_rank(approvals_count),
                    'is_trusted': is_trusted_user(approvals_count)
                }
        except Exception as e:
            log_user_action(user_id, "ERROR", f"Failed to get user stats: {str(e)}")
            return {'requests_count': 0, 'approvals_count': 0, 'links_count': 0, 
                   'rank': UserRank.NEWBIE, 'is_trusted': False}
    
    def get_user_info(self, user_id: int) -> dict:
        """Получение информации о пользователе"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT username, first_name, last_name, created_at, last_activity
                    FROM users WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'username': result[0],
                        'first_name': result[1],
                        'last_name': result[2],
                        'created_at': result[3],
                        'last_activity': result[4]
                    }
        except Exception as e:
            log_user_action(user_id, "ERROR", f"Failed to get user info: {str(e)}")
        
        return {'username': 'Unknown', 'first_name': None, 'last_name': None}
    
    def get_leaderboard(self, limit: int = 10, board_type: str = "approvals") -> List[dict]:
        """Получение таблицы лидеров"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if board_type == "approvals":
                    cursor.execute('''
                        SELECT u.user_id, u.username, COUNT(ac.claim_id) as count
                        FROM users u
                        LEFT JOIN approval_claims ac ON u.user_id = ac.user_id AND ac.status = 'approved'
                        GROUP BY u.user_id, u.username
                        HAVING count > 0
                        ORDER BY count DESC
                        LIMIT ?
                    ''', (limit,))
                elif board_type == "requests":
                    cursor.execute('''
                        SELECT u.user_id, u.username, COUNT(pr.request_id) as count
                        FROM users u
                        LEFT JOIN presave_requests pr ON u.user_id = pr.user_id
                        GROUP BY u.user_id, u.username
                        HAVING count > 0
                        ORDER BY count DESC
                        LIMIT ?
                    ''', (limit,))
                else:  # ratio
                    cursor.execute('''
                        SELECT u.user_id, u.username, 
                               COUNT(DISTINCT pr.request_id) as requests,
                               COUNT(DISTINCT CASE WHEN ac.status = 'approved' THEN ac.claim_id END) as approvals,
                               CASE 
                                 WHEN COUNT(DISTINCT pr.request_id) > 0 
                                 THEN ROUND(CAST(COUNT(DISTINCT CASE WHEN ac.status = 'approved' THEN ac.claim_id END) AS FLOAT) / COUNT(DISTINCT pr.request_id), 2)
                                 ELSE 0.0
                               END as ratio
                        FROM users u
                        LEFT JOIN presave_requests pr ON u.user_id = pr.user_id
                        LEFT JOIN approval_claims ac ON u.user_id = ac.user_id
                        GROUP BY u.user_id, u.username
                        HAVING requests > 0 OR approvals > 0
                        ORDER BY ratio DESC, approvals DESC
                        LIMIT ?
                    ''', (limit,))
                
                results = []
                for row in cursor.fetchall():
                    if board_type == "ratio":
                        results.append({
                            'user_id': row[0],
                            'username': row[1],
                            'requests': row[2],
                            'approvals': row[3],
                            'ratio': row[4]
                        })
                    else:
                        results.append({
                            'user_id': row[0],
                            'username': row[1],
                            'count': row[2]
                        })
                
                return results
        except Exception as e:
            log_user_action(0, "ERROR", f"Failed to get leaderboard: {str(e)}")
            return []
    
    def get_recent_presave_requests(self, limit: int = 10) -> List[dict]:
        """Получение последних просьб о пресейвах"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT pr.request_id, pr.user_id, pr.message_id, pr.created_at, u.username
                    FROM presave_requests pr
                    JOIN users u ON pr.user_id = u.user_id
                    ORDER BY pr.created_at DESC
                    LIMIT ?
                ''', (limit,))
                
                requests = []
                for row in cursor.fetchall():
                    requests.append({
                        'request_id': row[0],
                        'user_id': row[1],
                        'message_id': row[2],
                        'created_at': row[3],
                        'username': row[4]
                    })
                
                return requests
        except Exception as e:
            log_user_action(0, "ERROR", f"Failed to get recent requests: {str(e)}")
            return []
    
    def get_recent_links(self, limit: int = 10) -> List[dict]:
        """Получение последних ссылок"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ul.link_url, ul.message_id, ul.created_at, u.username
                    FROM user_links ul
                    JOIN users u ON ul.user_id = u.user_id
                    ORDER BY ul.created_at DESC
                    LIMIT ?
                ''', (limit,))
                
                links = []
                for row in cursor.fetchall():
                    links.append({
                        'link_url': row[0],
                        'message_id': row[1],
                        'created_at': row[2],
                        'username': row[3]
                    })
                
                return links
        except Exception as e:
            log_user_action(0, "ERROR", f"Failed to get recent links: {str(e)}")
            return []
    
    def get_active_screenshots_count(self) -> int:
        """Получение количества активных скриншотов"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM screenshot_files WHERE expires_at > ?', (datetime.now().isoformat(),))
                return cursor.fetchone()[0]
        except Exception:
            return 0
    
    def is_bot_active(self) -> bool:
        """Проверка активности бота"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', ('bot_active',))
                result = cursor.fetchone()
                return result[0] == 'true' if result else True
        except Exception:
            return True
    
    def set_bot_active(self, active: bool):
        """Установка активности бота"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', ('bot_active', 'true' if active else 'false', datetime.now().isoformat()))
        except Exception as e:
            logger.error(f"❌ Failed to set bot active: {str(e)}")
            centralized_error_logger(error=e, context="set_bot_active")
    
    def update_setting(self, key: str, value: str):
        """Обновление настройки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', (key, value, datetime.now().isoformat()))
        except Exception as e:
            logger.error(f"❌ Failed to update setting {key}: {str(e)}")
            centralized_error_logger(error=e, context=f"update_setting({key})")
    
    def get_setting(self, key: str, default: str = None) -> str:
        """Получение настройки"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else default
        except Exception:
            return default

# Инициализация менеджера БД
db_manager = DatabaseManager('bot.db')

# ================================
# 9. ОБРАБОТЧИКИ КОМАНД (ПОЛЬЗОВАТЕЛЬСКИЕ)
# ================================

@bot.message_handler(commands=['start'])
@request_logging  
def start_command(message):
    """Приветствие адаптивное для разных контекстов"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Логируем контекст
    log_user_action(
        user_id=user_id,
        action="COMMAND_START",
        details=f"Context: {context}"
    )
    
    # Обработка по контексту
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    """Приветствие и базовая информация о боте"""
    user_id = message.from_user.id
    
    # Добавляем пользователя в БД
    db_manager.add_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    welcome_text = """
🤖 **Do Presave Reminder Bot by Mister DMS v24** - Bug Fixes

Добро пожаловать в продвинутую систему взаимной поддержки артистов!

🎵 **Что я умею:**
• Помогаю с просьбами о пресейвах
• Обрабатываю заявки о совершенных пресейвах  
• Веду статистику и рейтинги
• Мотивирую к взаимной поддержке

📱 **Начать:** /menu - главное меню
❓ **Помощь:** /help - подробная справка

🏆 **Система званий:**
🥉 Новенький (1-5 аппрувов)
🥈 Надежный пресейвер (6-15 аппрувов) - доверенный
🥇 Мега-человечище (16-30 аппрувов) - доверенный  
💎 Амбассадорище (31+ аппрувов) - доверенный
"""
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    log_user_action(user_id, "COMMAND", "Start command executed")

@bot.message_handler(commands=['help'])
@request_logging
def help_command(message):
    """Справка по использованию бота"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    is_admin = validate_admin(user_id)
    
    help_text = """
❓ **Справка по боту**

🎵 **Основные функции:**
• Автоматические напоминания о пресейвах при публикации ссылок
• Интерактивная подача объявлений о просьбе пресейва
• Система заявок на аппрув совершенных пресейвов
• Статистика и рейтинги участников

📱 **Команды:**
/menu - главное меню
/mystat - ваша статистика
/presavestats - общий рейтинг
/recent - последние 10 ссылок
/help - эта справка

🎯 **Как работает:**
1. Отправляете ссылку на музыку → бот напоминает о пресейвах
2. Подаете объявление через /menu → Действия → Попросить о пресейве
3. Делаете пресейвы других участников 
4. Заявляете об этом через /menu → Действия → Заявить о совершенном пресейве
5. Админ проверяет скриншоты и подтверждает
6. Получаете аппрув и растете в рейтинге!

🏆 **Звания даются за подтвержденные пресейвы других артистов**
"""
    
    if is_admin:
        help_text += """

👑 **Админские функции:**
/menu - расширенное админское меню
• Проверка заявок на аппрувы
• Настройки режимов лимитов
• Управление активностью бота
• Расширенная аналитика
• Диагностика системы
"""
    
    bot.reply_to(message, help_text, parse_mode='Markdown')
    log_user_action(user_id, "COMMAND", "Help command executed")

@bot.message_handler(commands=['mystat'])
@request_logging  
def my_stats_command(message):
    """Личная статистика пользователя с прогресс-барами"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    # Обновляем активность
    db_manager.update_user_activity(user_id)
    
    # Получаем статистику
    user_stats = db_manager.get_user_stats(user_id)
    stats_text = format_user_stats(user_stats)
    
    bot.reply_to(message, stats_text, parse_mode='Markdown')
    log_user_action(user_id, "STATS", "Personal stats requested")

@bot.message_handler(commands=['presavestats', 'linkstats'])
@request_logging
def presave_stats_command(message):
    """Общий рейтинг и статистика сообщества"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    # Получаем топы по разным категориям
    top_approvals = db_manager.get_leaderboard(5, "approvals")
    top_requests = db_manager.get_leaderboard(5, "requests") 
    top_ratio = db_manager.get_leaderboard(5, "ratio")
    
    stats_text = "🏆 **Рейтинги сообщества**\n\n"
    
    # Топ по аппрувам
    stats_text += "✅ **Топ по подтвержденным пресейвам:**\n"
    for i, user in enumerate(top_approvals, 1):
        username = user['username'] or 'Unknown'
        rank = get_user_rank(user['count'])
        stats_text += f"{i}. @{username} - {user['count']} {rank.value}\n"
    
    stats_text += "\n🎵 **Топ по просьбам о пресейвах:**\n"
    for i, user in enumerate(top_requests, 1):
        username = user['username'] or 'Unknown'  
        stats_text += f"{i}. @{username} - {user['count']}\n"
        
    stats_text += "\n⚖️ **Лучшие по взаимности (аппрув/просьба):**\n"
    for i, user in enumerate(top_ratio, 1):
        username = user['username'] or 'Unknown'
        ratio = user['ratio']
        stats_text += f"{i}. @{username} - {ratio} ({user['approvals']}/{user['requests']})\n"
    
    bot.reply_to(message, stats_text, parse_mode='Markdown')
    log_user_action(user_id, "STATS", "Community stats requested")

@bot.message_handler(commands=['userstat'])
@request_logging
def user_stats_command(message):
    """Статистика другого пользователя по @username"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    # Парсим username из команды
    command_parts = message.text.split()
    if len(command_parts) < 2:
        bot.reply_to(message, "❌ Укажите username: /userstat @username")
        return
    
    target_username = command_parts[1].replace('@', '')
    
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE username = ?', (target_username,))
            result = cursor.fetchone()
            
            if not result:
                bot.reply_to(message, f"❌ Пользователь @{target_username} не найден")
                return
            
            target_user_id = result[0]
            target_stats = db_manager.get_user_stats(target_user_id)
            
            stats_text = f"👤 **Статистика @{target_username}:**\n\n"
            stats_text += f"🎵 Просьб о пресейвах: {target_stats['requests_count']}\n"
            stats_text += f"✅ Подтвержденных заявок: {target_stats['approvals_count']}\n"
            stats_text += f"🔗 Всего ссылок: {target_stats['links_count']}\n"
            stats_text += f"🏆 Звание: {target_stats['rank'].value}\n"
            
            if target_stats['is_trusted']:
                stats_text += "\n🌟 **Доверенный пресейвер** - автоматические аппрувы"
            
            # Соотношение взаимности
            if target_stats['requests_count'] > 0:
                ratio = round(target_stats['approvals_count'] / target_stats['requests_count'], 2)
                stats_text += f"\n⚖️ Взаимность: {ratio} (аппрув/просьба)"
            
            bot.reply_to(message, stats_text, parse_mode='Markdown')
            log_user_action(user_id, "STATS", f"User stats requested for @{target_username}")
            
    except Exception as e:
        bot.reply_to(message, "❌ Ошибка получения статистики")
        log_user_action(user_id, "ERROR", f"Failed to get user stats: {str(e)}")

@bot.message_handler(commands=['topusers'])
@request_logging
def top_users_command(message):
    """Топ-5 самых активных пользователей"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    top_users = db_manager.get_leaderboard(5, "approvals")
    
    if not top_users:
        bot.reply_to(message, "📊 Пока нет данных для рейтинга")
        return
    
    top_text = "🏆 **Топ-5 активных пресейверов:**\n\n"
    
    for i, user in enumerate(top_users, 1):
        username = user['username'] or 'Unknown'
        count = user['count']
        rank = get_user_rank(count)
        
        if i == 1:
            emoji = "🥇"
        elif i == 2:
            emoji = "🥈"
        elif i == 3:
            emoji = "🥉"
        else:
            emoji = f"{i}."
            
        top_text += f"{emoji} @{username} - {count} аппрувов {rank.value}\n"
    
    bot.reply_to(message, top_text, parse_mode='Markdown')
    log_user_action(user_id, "STATS", "Top users requested")

@bot.message_handler(commands=['recent'])
@request_logging
def recent_links_command(message):
    """10 последних ссылок с авторами"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    recent_links = db_manager.get_recent_links(10)
    
    if not recent_links:
        bot.reply_to(message, "📎 Пока нет ссылок в сообществе")
        return
    
    recent_text = "📎 **Последние 10 ссылок:**\n\n"
    
    for i, link_data in enumerate(recent_links, 1):
        username = link_data['username'] or 'Unknown'
        link_url = link_data['link_url']
        message_id = link_data['message_id']
        
        # Создаем ссылку на сообщение
        message_link = f"https://t.me/c/{abs(GROUP_ID)}/{message_id}"
        
        recent_text += f"{i}. @{username} - [перейти к посту]({message_link})\n"
    
    bot.reply_to(message, recent_text, parse_mode='Markdown', disable_web_page_preview=True)
    log_user_action(user_id, "STATS", "Recent links requested")

@bot.message_handler(commands=['alllinks'])
@request_logging
def all_links_command(message):
    """Все ссылки в файле .txt"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    all_links = db_manager.get_recent_links(50)  # Последние 50
    
    if not all_links:
        bot.reply_to(message, "📎 Нет ссылок для экспорта")
        return
    
    # Формируем содержимое файла
    file_content = "# Все ссылки сообщества\n"
    file_content += f"# Экспорт от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for i, link_data in enumerate(all_links, 1):
        username = link_data['username'] or 'Unknown'
        link_url = link_data['link_url']
        created_at = link_data['created_at']
        
        file_content += f"{i}. @{username} | {created_at} | {link_url}\n"
    
    # Отправляем как документ
    file_bytes = file_content.encode('utf-8')
    
    bot.send_document(
        message.chat.id,
        ('community_links.txt', file_bytes),
        caption=f"📎 **Экспорт ссылок сообщества**\n\nВсего: {len(all_links)} ссылок",
        parse_mode='Markdown'
    )
    
    log_user_action(user_id, "STATS", f"All links exported: {len(all_links)} items")

@bot.message_handler(commands=['askpresave'])
@request_logging
def ask_presave_command(message):
    """ПРОСЬБА О ПРЕСЕЙВЕ - публикация объявления"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    if context == "private_chat":
        start_presave_request_flow(message)
    else:
        bot.reply_to(message, "Используйте /menu → ⚙️ Действия → Попросить о пресейве")
        
    log_user_action(user_id, "COMMAND", "Ask presave command")

@bot.message_handler(commands=['claimpresave'])
@request_logging  
def claim_presave_command(message):
    """ЗАЯВКА О СОВЕРШЕННОМ ПРЕСЕЙВЕ - подача скриншотов на аппрув"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Проверка контекста
    if context == "wrong_group":
        bot.reply_to(message, "❌ Бот не работает в этой группе")
        return
    elif context == "wrong_thread":
        current_thread = getattr(message, 'message_thread_id', None)
        bot.reply_to(message, 
            f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
            message_thread_id=current_thread)
        return
    
    if context == "private_chat":
        start_presave_claim_flow(message)
    else:
        bot.reply_to(message, "Используйте /menu → ⚙️ Действия → Заявить о совершенном пресейве")
        
    log_user_action(user_id, "COMMAND", "Claim presave command")

# ================================
# 10. ОБРАБОТЧИКИ КОМАНД (АДМИНСКИЕ)
# ================================

@bot.message_handler(commands=['menu'])
@topic_restricted
@request_logging
def menu_command(message):
    """Главное меню - работает только в правильном топике и ЛС"""
    user_id = message.from_user.id
    
    # Команда уже прошла проверку топика через декоратор topic_restricted
    
    # Декоратор topic_restricted уже обработал все проверки
    log_user_action(
        user_id=user_id,
        action="COMMAND_MENU",
        details=f"Chat: {message.chat.id}, Thread: {getattr(message, 'message_thread_id', None)}"
    )
    
    if validate_admin(user_id):
        # АДМИНСКОЕ МЕНЮ из структуры гайда
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"))
        keyboard.add(InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard"))
        keyboard.add(InlineKeyboardButton("⚙️ Действия", callback_data="admin_actions"))
        keyboard.add(InlineKeyboardButton("📊 Расширенная аналитика", callback_data="admin_analytics"))
        keyboard.add(InlineKeyboardButton("🔧 Диагностика", callback_data="diagnostics"))
        keyboard.add(InlineKeyboardButton("❓ Помощь", callback_data="help"))
        
        bot.send_message(message.chat.id, "👑 **Админское меню**", 
                        reply_markup=keyboard, parse_mode='Markdown')
    else:
        # ПОЛЬЗОВАТЕЛЬСКОЕ МЕНЮ из структуры гайда  
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"))
        keyboard.add(InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard"))
        keyboard.add(InlineKeyboardButton("⚙️ Действия", callback_data="user_actions"))
        keyboard.add(InlineKeyboardButton("📊 Аналитика", callback_data="user_analytics"))
        keyboard.add(InlineKeyboardButton("❓ Помощь", callback_data="help"))
        
        bot.send_message(message.chat.id, "📱 **Главное меню**", 
                        reply_markup=keyboard, parse_mode='Markdown')
    
    log_user_action(user_id, "COMMAND", "Menu opened")

@bot.message_handler(commands=['setmode_conservative', 'setmode_normal', 'setmode_burst', 'setmode_adminburst'])
@admin_required
@request_logging
def set_limit_mode_command(message):
    """Переключение режимов лимитов"""
    user_id = message.from_user.id
    command = message.text.split('_')[1]  # conservative, normal, burst, adminburst
    
    mode_map = {
        'conservative': LimitMode.CONSERVATIVE,
        'normal': LimitMode.NORMAL,
        'burst': LimitMode.BURST,
        'adminburst': LimitMode.ADMIN_BURST
    }
    
    new_mode = mode_map.get(command)
    if new_mode:
        update_limit_mode(new_mode, user_id)
        mode_settings = LIMIT_MODES[new_mode]
        
        bot.reply_to(message, 
                    f"✅ **Режим изменен на {new_mode.value}**\n\n"
                    f"Лимит: {mode_settings['max_hour']}/час\n"
                    f"Задержка: {mode_settings['cooldown']}с")
    else:
        bot.reply_to(message, "❌ Неизвестный режим")

@bot.message_handler(commands=['enablebot', 'disablebot'])
@admin_required
@request_logging
def toggle_bot_command(message):
    """Включение/выключение бота"""
    user_id = message.from_user.id
    enable = 'enable' in message.text
    
    db_manager.set_bot_active(enable)
    bot_status["enabled"] = enable
    
    status_text = "✅ Бот активирован" if enable else "⏸️ Бот деактивирован"
    bot.reply_to(message, status_text)
    
    log_user_action(user_id, "SUCCESS", f"Bot {'enabled' if enable else 'disabled'}")

@bot.message_handler(commands=['clearlinks', 'clearapprovals', 'clearasks'])
@admin_required
@request_logging
def clear_data_command(message):
    """Очистка различных данных"""
    user_id = message.from_user.id
    command = message.text[6:]  # убираем /clear
    
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            
            if command == 'links':
                cursor.execute('DELETE FROM user_links')
                cleared = cursor.rowcount
                bot.reply_to(message, f"✅ Очищено {cleared} ссылок")
                
            elif command == 'approvals':
                cursor.execute('DELETE FROM approval_claims WHERE status = "pending"')
                cleared = cursor.rowcount
                bot.reply_to(message, f"✅ Очищено {cleared} заявок на аппрув")
                
            elif command == 'asks':
                cursor.execute('DELETE FROM presave_requests')
                cleared = cursor.rowcount
                bot.reply_to(message, f"✅ Очищено {cleared} просьб о пресейвах")
            
            log_user_action(user_id, "SUCCESS", f"Cleared {command}: {cleared} items")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка очистки: {str(e)}")
        log_user_action(user_id, "ERROR", f"Failed to clear {command}: {str(e)}")

@bot.message_handler(commands=['checkapprovals'])
@admin_required
@request_logging
def check_approvals_command(message):
    """Проверка заявок на аппрув с интерактивными кнопками"""
    user_id = message.from_user.id
    
    pending_claims = db_manager.get_pending_claims()
    
    if not pending_claims:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню Действия", 
                                        callback_data="admin_actions"))
        bot.send_message(message.chat.id, "✅ Заявок на рассмотрение нет", 
                        reply_markup=keyboard)
        return
    
    # Показываем первую заявку для рассмотрения
    show_claim_for_approval(message.chat.id, pending_claims[0], 0, len(pending_claims))
    log_user_action(user_id, "ADMIN_APPROVE", f"Checking {len(pending_claims)} pending claims")

@bot.message_handler(commands=['threadcheck'])
@topic_restricted
@request_logging
def thread_check_command(message):
    """Тестовая команда для проверки топика"""
    user_id = message.from_user.id
    
    if not validate_admin(user_id):
        bot.reply_to(message, "❌ Команда только для админов")
        return
    
    current_thread = getattr(message, 'message_thread_id', None)
    chat_type = message.chat.type
    
    check_text = f"""
🔧 **Проверка топика:**

📊 **Текущий чат:** {message.chat.id}
🎯 **Ожидаемый чат:** {GROUP_ID}
📍 **Текущий топик:** {current_thread}
🎯 **Ожидаемый топик:** {THREAD_ID}
💬 **Тип чата:** {chat_type}

✅ **Статус:** {'Правильный топик!' if current_thread == THREAD_ID and message.chat.id == GROUP_ID else 'Неправильный топик!'}

🌐 **Правильная ссылка:**  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}
"""
    
    bot.reply_to(message, check_text, parse_mode='Markdown')
    log_user_action(user_id, "COMMAND", f"Thread check: {current_thread} vs {THREAD_ID}")

@bot.message_handler(commands=['keepalive', 'checksystem', 'botstatus'])
@admin_required
@request_logging
def diagnostic_commands(message):
    """Диагностические команды"""
    user_id = message.from_user.id
    command = message.text[1:]  # убираем /
    
    if command == 'keepalive':
        render_url = os.getenv('RENDER_EXTERNAL_URL', 'localhost')
        url = f"https://{render_url}/keepalive"
        
        start_time = time.time()
        success = make_keep_alive_request(url)
        duration = round((time.time() - start_time) * 1000, 2)
        
        status = "✅ OK" if success else "❌ FAILED"
        bot.reply_to(message, f"💓 **Keep Alive Test**\n\n{status}\nДлительность: {duration}ms")
        
    elif command == 'checksystem':
        # Проверка всех компонентов
        checks = {}
        
        # БД
        try:
            with database_transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM users')
                user_count = cursor.fetchone()[0]
            checks['database'] = f"✅ OK ({user_count} пользователей)"
        except Exception as e:
            checks['database'] = f"❌ ERROR: {str(e)}"
        
        # Telegram API
        try:
            bot_info = bot.get_me()
            checks['telegram_api'] = f"✅ OK (@{bot_info.username})"
        except Exception as e:
            checks['telegram_api'] = f"❌ ERROR: {str(e)}"
        
        # Скриншоты
        try:
            screenshots_count = db_manager.get_active_screenshots_count()
            checks['screenshots'] = f"✅ OK ({screenshots_count} активных)"
        except Exception as e:
            checks['screenshots'] = f"❌ ERROR: {str(e)}"
        
        system_text = "🔧 **Проверка системы:**\n\n"
        for component, status in checks.items():
            system_text += f"**{component}:** {status}\n"
        
        bot.reply_to(message, system_text, parse_mode='Markdown')
        
    elif command == 'botstatus':
        uptime = datetime.now() - bot_status["start_time"]
        current_mode = get_current_limit_mode()
        active = db_manager.is_bot_active()
        
        status_text = f"""
🤖 **Статус бота:**

📊 Активность: {'✅ Активен' if active else '⏸️ Деактивирован'}
⏱️ Uptime: {str(uptime).split('.')[0]}
🎛️ Режим лимитов: {current_mode.value}
📸 Активных скриншотов: {db_manager.get_active_screenshots_count()}
💾 Сессий пользователей: {len(user_sessions)}

🔗 Webhook: настроен
💓 Keep alive: активен
"""
        
        bot.reply_to(message, status_text, parse_mode='Markdown')
    
    log_user_action(user_id, "COMMAND", f"Diagnostic: {command}")

# ================================
# 11. ОБРАБОТЧИКИ CALLBACK КНОПОК
# ================================

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Центральный обработчик всех callback кнопок"""
    user_id = call.from_user.id
    user_role = get_user_role(user_id)
    
    # Проверяем топик для callback'ов из группы
    if call.message.chat.type != 'private':
        if call.message.chat.id != GROUP_ID:
            bot.answer_callback_query(call.id, "❌ Бот не работает в этой группе")
            return
        
        current_thread = getattr(call.message, 'message_thread_id', None)
        if current_thread != THREAD_ID:
            bot.answer_callback_query(call.id, f"❌ Перейдите в правильный топик: https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}")
            return
    
    # Создаем корреляционный ID для callback'а
    correlation_id = f"callback_{int(time.time() * 1000)}_{call.from_user.id}"
 
    # Устанавливаем контекст запроса вручную
    old_context = getattr(threading.current_thread(), '_request_context', None)
    threading.current_thread()._request_context = {
        'correlation_id': correlation_id,
        'user_id': call.from_user.id,
        'client_ip': None,
        'start_time': time.time()
    }
    
    try:
        # Логируем начало обработки callback'а
        log_user_action(
            user_id=user_id,
            action="CALLBACK_RECEIVED",
            details=f"Data: {call.data}, Role: {user_role}",
            correlation_id=correlation_id
        )
    
        # Обработка основных callback'ов
        if call.data == "my_stats":
            handle_my_stats_callback(call)
        elif call.data == "leaderboard":
            handle_leaderboard_callback(call)
        elif call.data.startswith("leaderboard_"):
            handle_leaderboard_type_callback(call)
        elif call.data == "user_actions":
            handle_user_actions_callback(call)
        elif call.data == "admin_actions" and user_role == 'admin':
            handle_admin_actions_callback(call)
        elif call.data == "admin_analytics" and user_role == 'admin':
            handle_admin_analytics_callback(call)
        elif call.data == "diagnostics" and user_role == 'admin':
            handle_diagnostics_callback(call)
        elif call.data == "help":
            handle_help_callback(call)
        
        # Настройки бота (админы)
        elif call.data == "bot_settings" and user_role == 'admin':
            handle_bot_settings_callback(call)
        elif call.data == "rate_modes_menu" and user_role == 'admin':
            handle_rate_modes_menu_callback(call)
        elif call.data.startswith("activate_bot") and user_role == 'admin':
            handle_activate_bot_callback(call)
        elif call.data.startswith("deactivate_bot") and user_role == 'admin':
            handle_deactivate_bot_callback(call)
        elif call.data.startswith("change_reminder") and user_role == 'admin':
            handle_change_reminder_callback(call)
        elif call.data.startswith("clear_data_menu") and user_role == 'admin':
            handle_clear_data_menu_callback(call)
        elif call.data == "test_keepalive" and user_role == 'admin':
            handle_test_keepalive_callback(call)
        elif call.data == "test_system" and user_role == 'admin':
            handle_test_system_callback(call)
        elif call.data == "bot_status_info" and user_role == 'admin':
            handle_bot_status_info_callback(call)
        elif call.data == "performance_metrics" and user_role == 'admin':
            handle_performance_metrics_callback(call)
        elif call.data.startswith("clear_") and user_role == 'admin':
            handle_clear_specific_data_callback(call)
        elif call.data == "check_approvals" and user_role == 'admin':
            handle_check_approvals_callback(call)
        elif call.data.startswith("recent_links_") and user_role == 'admin':
            handle_recent_links_callback(call)
        
        # Пользовательские функции  
        elif call.data == "user_analytics":
            handle_user_analytics_callback(call)
        elif call.data.startswith("recent_links_") and user_role == 'user':
            handle_recent_links_callback(call)
        # Интерактивные просьбы о пресейвах
        elif call.data == "start_presave_request":
            handle_start_presave_request_callback(call)
        elif call.data.startswith("cancel_request_"):
            handle_cancel_request_callback(call)
        elif call.data.startswith("publish_request_"):
            handle_publish_request_callback(call)
        
        # Интерактивные заявки на аппрув
        elif call.data == "start_presave_claim":
            handle_start_presave_claim_callback(call)
        elif call.data.startswith("cancel_claim_"):
            handle_cancel_claim_callback(call)
        elif call.data.startswith("submit_claim_"):
            handle_submit_claim_callback(call)
        elif call.data == "add_screenshot":
            handle_add_screenshot_callback(call)
        
        # Админские функции аппрува
        elif call.data.startswith("approve_claim_") and user_role == 'admin':
            handle_approve_claim_callback(call)
        elif call.data.startswith("reject_claim_") and user_role == 'admin':
            handle_reject_claim_callback(call)
        elif call.data.startswith("next_claim_") and user_role == 'admin':
            handle_next_claim_callback(call)
        
        # Настройки бота (админы)
        elif call.data == "bot_settings" and user_role == 'admin':
            handle_bot_settings_callback(call)
        elif call.data.startswith("setmode_") and user_role == 'admin':
            handle_setmode_callback(call)
        
        # Навигация назад
        elif call.data.startswith("back_"):
            handle_back_navigation(call)
        
        # Контентные функции
        elif call.data == "recent":
            handle_recent_callback(call)
        elif call.data == "alllinks":
            handle_alllinks_callback(call)
        
        # Дополнительные callback'ы
        elif call.data == "proceed_to_comment":
            handle_proceed_to_comment_callback(call)
        elif call.data == "admin_user_links" and user_role == 'admin':
            handle_admin_user_links_callback(call)
        elif call.data == "admin_user_approvals" and user_role == 'admin':
            handle_admin_user_approvals_callback(call)
        elif call.data == "admin_user_comparison" and user_role == 'admin':
            handle_admin_user_comparison_callback(call)
        elif call.data == "user_links_search":
            handle_user_links_search_callback(call)
        elif call.data == "user_approvals_search":
            handle_user_approvals_search_callback(call)
        elif call.data == "user_comparison_search":
            handle_user_comparison_search_callback(call)
        
        else:
            # Неизвестный callback
            log_user_action(user_id, "CALLBACK_UNKNOWN", f"Unknown: {call.data}")
            bot.answer_callback_query(call.id, "❌ Неизвестная команда")
            return
        
        bot.answer_callback_query(call.id)
        metrics.increment('callback.success')
        
    except Exception as e:
        centralized_error_logger(
            error=e,
            context=f"Callback handler: {call.data}",
            user_id=user_id,
            correlation_id=correlation_id
        )
        metrics.increment('callback.error')
        
        try:
            bot.answer_callback_query(call.id, "❌ Системная ошибка")
        except:
            pass
    finally:
        # Восстанавливаем предыдущий контекст
        threading.current_thread()._request_context = old_context

def handle_my_stats_callback(call):
    """Обработка показа личной статистики"""
    user_id = call.from_user.id
    
    # Обновляем активность
    db_manager.update_user_activity(user_id)
    
    # Получаем статистику
    user_stats = db_manager.get_user_stats(user_id)
    stats_text = format_user_stats(user_stats)
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        stats_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_leaderboard_callback(call):
    """Меню лидерборда с подменю"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("По просьбам о пресейве", callback_data="leaderboard_requests"))
    keyboard.add(InlineKeyboardButton("По аппрувам", callback_data="leaderboard_approvals")) 
    keyboard.add(InlineKeyboardButton("По соотношению Просьба-Аппрув", callback_data="leaderboard_ratio"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        "🏆 **Лидерборд** - выберите категорию", 
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_leaderboard_type_callback(call):
    """Показ конкретного типа лидерборда"""
    board_type = call.data.split('_')[1]  # requests, approvals, ratio
    
    leaderboard = db_manager.get_leaderboard(10, board_type)
    
    if not leaderboard:
        text = "📊 Пока нет данных для этого рейтинга"
    else:
        if board_type == "requests":
            text = "🎵 **Топ по просьбам о пресейвах:**\n\n"
            for i, user in enumerate(leaderboard, 1):
                username = user['username'] or 'Unknown'
                text += f"{i}. @{username} - {user['count']}\n"
        elif board_type == "approvals":
            text = "✅ **Топ по подтвержденным пресейвам:**\n\n"
            for i, user in enumerate(leaderboard, 1):
                username = user['username'] or 'Unknown'
                rank = get_user_rank(user['count'])
                text += f"{i}. @{username} - {user['count']} {rank.value}\n"
        else:  # ratio
            text = "⚖️ **Лучшие по взаимности:**\n\n"
            for i, user in enumerate(leaderboard, 1):
                username = user['username'] or 'Unknown'
                text += f"{i}. @{username} - {user['ratio']} ({user['approvals']}/{user['requests']})\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к рейтингам", callback_data="leaderboard"))
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_user_actions_callback(call):
    """Пользовательское меню действий"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🎵 Попросить о пресейве", callback_data="start_presave_request"))
    keyboard.add(InlineKeyboardButton("📸 Заявить о совершенном пресейве", callback_data="start_presave_claim"))
    keyboard.add(InlineKeyboardButton("📎 Последние 30 ссылок", callback_data="recent_links_30"))
    keyboard.add(InlineKeyboardButton("📎 Последние 10 ссылок", callback_data="recent_links_10"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        "⚙️ **Действия**", 
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_admin_actions_callback(call):
    """Админское меню действий"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🎵 Попросить о пресейве", callback_data="start_presave_request"))
    keyboard.add(InlineKeyboardButton("📸 Заявить о совершенном пресейве", callback_data="start_presave_claim"))
    keyboard.add(InlineKeyboardButton("✅ Проверить заявки на аппрувы", callback_data="check_approvals"))
    keyboard.add(InlineKeyboardButton("📎 Последние 30 ссылок", callback_data="recent_links_30"))
    keyboard.add(InlineKeyboardButton("📎 Последние 10 ссылок", callback_data="recent_links_10"))
    keyboard.add(InlineKeyboardButton("🎛️ Настройки бота", callback_data="bot_settings"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        "⚙️ **Админские действия**", 
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_start_presave_request_callback(call):
    """Начало интерактивной просьбы о пресейве"""
    user_id = call.from_user.id
    
    # Создаем сессию пользователя
    user_sessions[user_id] = UserSession(
        state=UserState.ASKING_PRESAVE_LINKS,
        data={'type': 'presave_request'},
        timestamp=datetime.now()
    )
    
    presave_request_sessions[user_id] = PresaveRequestSession(
        links=[],
        comment="",
        user_id=user_id,
        timestamp=datetime.now()
    )
    
    request_text = """
🎵 **Подача объявления с просьбой о пресейве**

📝 **Шаг 1:** Отправьте ссылки на ваш релиз

Поддерживаемые платформы:
• Spotify, Apple Music, Yandex Music
• YouTube Music, Deezer
• Bandlink, Taplink и другие конструкторы
• Популярные социальные сети

**Формат:** Одна ссылка на строку

Пример:
```
https://open.spotify.com/track/...
https://music.apple.com/album/...
https://bandlink.to/...
```
"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_request_{user_id}"))
    
    bot.edit_message_text(
        request_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    log_user_action(user_id, "REQUEST_PRESAVE", "Started interactive request flow")

def handle_start_presave_claim_callback(call):
    """Начало интерактивной заявки на аппрув"""
    user_id = call.from_user.id
    
    # Создаем сессию пользователя
    user_sessions[user_id] = UserSession(
        state=UserState.CLAIMING_PRESAVE_SCREENSHOTS,
        data={'type': 'presave_claim'},
        timestamp=datetime.now()
    )
    
    presave_claim_sessions[user_id] = PresaveClaimSession(
        screenshots=[],
        comment="",
        user_id=user_id,
        timestamp=datetime.now()
    )
    
    claim_text = """
📸 **Заявка на аппрув совершенного пресейва**

📷 **Шаг 1:** Отправьте скриншоты

Что нужно прислать:
• Скриншот страницы пресейва
• Скриншот подтверждения 
• Любые другие доказательства

**Требования:**
• Формат: JPG, PNG, WebP
• Максимум 10MB на файл
• Можно отправить несколько фото

После загрузки всех скриншотов нажмите "Перейти к комментарию"
"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_claim_{user_id}"))
    
    bot.edit_message_text(
        claim_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    log_user_action(user_id, "CLAIM_PRESAVE", "Started interactive claim flow")

def handle_back_navigation(call):
    """Обработка кнопок назад"""
    destination = call.data.split('_')[1]  # main, leaderboard, etc.
    
    if destination == "main":
        # Возврат в главное меню
        user_id = call.from_user.id
        
        if validate_admin(user_id):
            # АДМИНСКОЕ МЕНЮ
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"))
            keyboard.add(InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard"))
            keyboard.add(InlineKeyboardButton("⚙️ Действия", callback_data="admin_actions"))
            keyboard.add(InlineKeyboardButton("📊 Расширенная аналитика", callback_data="admin_analytics"))
            keyboard.add(InlineKeyboardButton("🔧 Диагностика", callback_data="diagnostics"))
            keyboard.add(InlineKeyboardButton("❓ Помощь", callback_data="help"))
            
            bot.edit_message_text("👑 **Админское меню**", 
                                call.message.chat.id, call.message.message_id,
                                reply_markup=keyboard, parse_mode='Markdown')
        else:
            # ПОЛЬЗОВАТЕЛЬСКОЕ МЕНЮ
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"))
            keyboard.add(InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard"))
            keyboard.add(InlineKeyboardButton("⚙️ Действия", callback_data="user_actions"))
            keyboard.add(InlineKeyboardButton("📊 Аналитика", callback_data="user_analytics"))
            keyboard.add(InlineKeyboardButton("❓ Помощь", callback_data="help"))
            
            bot.edit_message_text("📱 **Главное меню**", 
                                call.message.chat.id, call.message.message_id,
                                reply_markup=keyboard, parse_mode='Markdown')

def handle_recent_callback(call):
    """Показ последних ссылок через callback"""
    recent_links = db_manager.get_recent_links(10)
    
    if not recent_links:
        text = "📎 Пока нет ссылок в сообществе"
    else:
        text = "📎 **Последние 10 ссылок:**\n\n"
        for i, link_data in enumerate(recent_links, 1):
            username = link_data['username'] or 'Unknown'
            message_id = link_data['message_id']
            message_link = f"https://t.me/c/{abs(GROUP_ID)}/{message_id}"
            text += f"{i}. @{username} - [перейти к посту]({message_link})\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

def handle_alllinks_callback(call):
    """Экспорт всех ссылок через callback"""
    user_id = call.from_user.id
    
    all_links = db_manager.get_recent_links(50)  # Последние 50
    
    if not all_links:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
        
        bot.edit_message_text(
            "📎 **Экспорт ссылок**\n\nНет ссылок для экспорта",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return
    
    # Формируем содержимое файла
    file_content = "# Все ссылки сообщества\n"
    file_content += f"# Экспорт от {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for i, link_data in enumerate(all_links, 1):
        username = link_data['username'] or 'Unknown'
        link_url = link_data['link_url']
        created_at = link_data['created_at']
        
        file_content += f"{i}. @{username} | {created_at} | {link_url}\n"
    
    # Отправляем как документ
    file_bytes = file_content.encode('utf-8')
    
    # Удаляем старое сообщение
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    # Отправляем файл с кнопкой назад
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.send_document(
        call.message.chat.id,
        ('community_links.txt', file_bytes),
        caption=f"📎 **Экспорт ссылок сообщества**\n\nВсего: {len(all_links)} ссылок",
        parse_mode='Markdown',
        reply_markup=keyboard
    )
    
    log_user_action(user_id, "STATS", f"All links exported: {len(all_links)} items")

# Функции интерактивных форм
def start_presave_request_flow(message):
    """Запуск интерактивной формы просьбы о пресейве в ЛС"""
    user_id = message.from_user.id
    
    user_sessions[user_id] = UserSession(
        state=UserState.ASKING_PRESAVE_LINKS,
        data={'type': 'presave_request'},
        timestamp=datetime.now()
    )
    
    presave_request_sessions[user_id] = PresaveRequestSession(
        links=[],
        comment="",
        user_id=user_id,
        timestamp=datetime.now()
    )
    
    bot.reply_to(message, """
🎵 **Подача объявления с просьбой о пресейве**

📝 Отправьте ссылки на ваш релиз (одна ссылка на строку):
""")

def start_presave_claim_flow(message):
    """Запуск интерактивной формы заявки на аппрув в ЛС"""
    user_id = message.from_user.id
    
    user_sessions[user_id] = UserSession(
        state=UserState.CLAIMING_PRESAVE_SCREENSHOTS,
        data={'type': 'presave_claim'},
        timestamp=datetime.now()
    )
    
    presave_claim_sessions[user_id] = PresaveClaimSession(
        screenshots=[],
        comment="",
        user_id=user_id,
        timestamp=datetime.now()
    )
    
    bot.reply_to(message, """
📸 **Заявка на аппрув совершенного пресейва**

📷 Отправьте скриншоты доказательства пресейва:
""")

def show_claim_for_approval(chat_id: int, claim: dict, current_index: int, total_count: int):
    """Показ заявки админу для рассмотрения"""
    claim_id = claim['claim_id']
    user_id = claim['user_id']
    screenshots = claim['screenshots']
    comment = claim['comment']
    created_at = claim['created_at']
    
    # Получаем информацию о пользователе
    user_info = db_manager.get_user_info(user_id)
    username = user_info.get('username', 'Unknown')
    user_stats = db_manager.get_user_stats(user_id)
    
    header_text = f"""
📸 **Заявка на аппрув #{claim_id}** ({current_index + 1}/{total_count})

👤 **Пользователь:** @{username} (ID: {user_id})
🏆 **Звание:** {user_stats.get('rank', UserRank.NEWBIE).value}
✅ **Аппрувов:** {user_stats.get('approvals_count', 0)}
📅 **Дата заявки:** {created_at}

💬 **Комментарий:**
{comment}

🖼️ **Скриншотов:** {len(screenshots)}
"""
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"approve_claim_{claim_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_claim_{claim_id}")
    )
    
    if current_index < total_count - 1:
        keyboard.add(InlineKeyboardButton("⏭️ Следующая заявка", callback_data=f"next_claim_{current_index + 1}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню Действия", callback_data="admin_actions"))
    
    # Отправляем заголовок
    bot.send_message(chat_id, header_text, reply_markup=keyboard, parse_mode='Markdown')
    
    # Отправляем скриншоты
    for screenshot_id in screenshots:
        try:
            bot.send_photo(chat_id, screenshot_id, caption=f"Скриншот заявки #{claim_id}")
        except Exception as e:
            log_user_action(0, "ERROR", f"Failed to send screenshot {screenshot_id}: {str(e)}")

# ================================
# 12. ОБРАБОТЧИКИ СООБЩЕНИЙ
# ================================

@bot.message_handler(content_types=['photo'])
@topic_restricted
@request_logging
def handle_photo_messages(message):
    """Обработка скриншотов для заявок на аппрув"""
    user_id = message.from_user.id
    
    # Проверяем состояние пользователя
    if user_id not in user_sessions:
        bot.reply_to(message, "❌ Сначала начните процесс подачи заявки через /menu")
        return
    
    session = user_sessions[user_id]
    if session.state != UserState.CLAIMING_PRESAVE_SCREENSHOTS:
        bot.reply_to(message, "❌ Сейчас не ожидаются скриншоты")
        return
    
    try:
        # Получаем информацию о файле
        file_info = bot.get_file(message.photo[-1].file_id)  # Берем самое высокое качество
        
        # Проверяем размер
        if not validate_screenshot_size(file_info.file_size):
            bot.reply_to(message, f"❌ Скриншот слишком большой (лимит: {MAX_SCREENSHOT_SIZE//1024//1024}MB)")
            return
        
        # Скачиваем файл
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Определяем расширение
        file_extension = get_file_extension_from_telegram(file_info.file_path)
        
        # Сохраняем в БД
        if db_manager.save_screenshot(message.photo[-1].file_id, user_id, 
                                    downloaded_file, file_extension):
            
            # Добавляем в сессию
            if user_id not in presave_claim_sessions:
                presave_claim_sessions[user_id] = PresaveClaimSession(
                    screenshots=[], comment="", user_id=user_id, timestamp=datetime.now()
                )
            
            presave_claim_sessions[user_id].screenshots.append(message.photo[-1].file_id)
            
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(InlineKeyboardButton("➕ Добавить еще скриншот", callback_data="add_screenshot"))
            keyboard.add(InlineKeyboardButton("✅ Перейти к комментарию", callback_data="proceed_to_comment"))
            keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_claim_{user_id}"))
            
            bot.reply_to(message, 
                        f"✅ Скриншот добавлен! (Всего: {len(presave_claim_sessions[user_id].screenshots)})",
                        reply_markup=keyboard)
            
            log_user_action(user_id, "SCREENSHOT_UPLOAD", 
                          f"Total screenshots: {len(presave_claim_sessions[user_id].screenshots)}")
        else:
            bot.reply_to(message, "❌ Ошибка сохранения скриншота. Попробуйте еще раз")
            
    except Exception as e:
        log_user_action(user_id, "ERROR", f"Screenshot processing error: {str(e)}")
        bot.reply_to(message, "❌ Ошибка обработки скриншота")

@bot.message_handler(content_types=['text'])
@request_logging
def handle_text_messages(message):
    """
    Основной обработчик текстовых сообщений в группе
    Работает ТОЛЬКО в правильном топике целевой группы
    Четкое разделение обнаружения ссылок и ответа с напоминанием
    """
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Эта функция работает ТОЛЬКО в правильном топике
    if context != "correct_thread":
        return  # Молча игнорируем сообщения в других местах
    
    # Добавляем пользователя в БД
    db_manager.add_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Извлекаем все внешние ссылки
    text = message.text or ""
    links = extract_links_from_text(text)
    external_links = [link for link in links if is_external_link(link)]
    
    if external_links:
        # Сохраняем ссылки в БД
        for link in external_links:
            db_manager.add_user_link(user_id, link, message.message_id)
        
        # Получаем последние 10 просьб о пресейвах для показа
        recent_requests = db_manager.get_recent_presave_requests(10)
        
        # Формируем ответ с напоминанием
        response_text = REMINDER_TEXT + "\n\n"
        response_text += "🎵 **Последние просьбы о пресейвах:**\n"
        
        for i, request in enumerate(recent_requests, 1):
            username = request.get('username', 'Неизвестно')
            message_link = f"https://t.me/c/{abs(GROUP_ID)}/{request['message_id']}"
            response_text += f"{i}. @{username} - [перейти к посту]({message_link})\n"
        
        if not recent_requests:
            response_text += "Пока нет активных просьб о пресейвах"
        
        bot.reply_to(message, response_text, parse_mode='Markdown', 
                    message_thread_id=THREAD_ID)
        
        log_user_action(user_id, "LINK_DETECTED", 
                       f"External links: {len(external_links)}")

@bot.message_handler(content_types=['text'], func=lambda m: m.chat.type == 'private')
@request_logging
def handle_private_messages(message):
    """
    Обработчик личных сообщений с поддержкой состояний
    """
    user_id = message.from_user.id
    
    # Проверяем состояние пользователя
    if user_id in user_sessions:
        session = user_sessions[user_id]
        
        if session.state == UserState.ASKING_PRESAVE_LINKS:
            # Обработка ввода ссылок для просьбы о пресейве
            handle_presave_request_links_input(message)
        elif session.state == UserState.ASKING_PRESAVE_COMMENT:
            # Обработка комментария для просьбы о пресейве
            handle_presave_request_comment_input(message)
        elif session.state == UserState.CLAIMING_PRESAVE_COMMENT:
            # Обработка комментария для заявки на аппрув
            handle_presave_claim_comment_input(message)
        elif session.state == UserState.EDITING_REMINDER:
            # Админское редактирование напоминания
            handle_reminder_edit_input(message)
        elif session.state == UserState.WAITING_USERNAME_FOR_ANALYTICS:
            # Админская аналитика по username
            handle_username_analytics_input(message)
        else:
            bot.reply_to(message, "❌ Неожиданное состояние. Используйте /menu")
    else:
        # Нет активной сессии - показываем справку
        bot.reply_to(message, """
🤖 **Do Presave Reminder Bot by Mister DMS v24** - Bug Fixes

Для работы с ботом используйте:
📱 /menu - главное меню
❓ /help - справка

В личных сообщениях доступны только интерактивные формы через меню.
""")

# Обработчики состояний для интерактивных форм

def handle_presave_request_links_input(message):
    """Обработка ввода ссылок для просьбы о пресейве"""
    user_id = message.from_user.id
    links_text = message.text.strip()
    
    # Парсим ссылки (по одной на строку)
    links = [link.strip() for link in links_text.split('\n') if link.strip()]
    external_links = [link for link in links if is_external_link(link)]
    
    if not external_links:
        bot.reply_to(message, "❌ Не найдено подходящих ссылок. Отправьте ссылки на музыку (по одной на строку)")
        return
    
    # Сохраняем в сессию
    if user_id not in presave_request_sessions:
        presave_request_sessions[user_id] = PresaveRequestSession(
            links=[], comment="", user_id=user_id, timestamp=datetime.now()
        )
    
    presave_request_sessions[user_id].links = external_links
    
    # Переводим в состояние ввода комментария
    user_sessions[user_id].state = UserState.ASKING_PRESAVE_COMMENT
    
    bot.reply_to(message, f"""
✅ **Ссылки приняты:** {len(external_links)}

📝 **Теперь отправьте комментарий** к вашему объявлению о просьбе пресейва.

Расскажите о своём релизе, для которого нужна поддержка сообщества.
""")

def handle_presave_request_comment_input(message):
    """Обработка комментария для просьбы о пресейве"""
    user_id = message.from_user.id
    comment = message.text.strip()
    
    if user_id not in presave_request_sessions:
        bot.reply_to(message, "❌ Ошибка: нет сохраненных ссылок")
        return
    
    presave_request_sessions[user_id].comment = comment
    
    # Показываем финальное подтверждение для просьбы о пресейве
    show_request_confirmation(message.chat.id, user_id)

def handle_presave_claim_comment_input(message):
    """Обработка комментария для заявки на аппрув"""
    user_id = message.from_user.id
    comment = message.text.strip()
    
    if user_id not in presave_claim_sessions:
        bot.reply_to(message, "❌ Ошибка: нет сохраненных скриншотов")
        return
    
    presave_claim_sessions[user_id].comment = comment
    
    # Показываем финальное подтверждение
    show_claim_confirmation(message.chat.id, user_id)

def show_request_confirmation(chat_id: int, user_id: int):
    """Показ финального подтверждения просьбы о пресейве"""
    if user_id not in presave_request_sessions:
        return
    
    session = presave_request_sessions[user_id]
    
    confirmation_text = f"""
🎵 **Объявление о просьбе пресейва готово к публикации**

🔗 **Ссылок:** {len(session.links)}
💬 **Комментарий:** {session.comment}

Опубликовать в топике "Поддержка пресейвом"?
"""
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("✅ Опубликовать", callback_data=f"publish_request_{user_id}"))
    keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_request_{user_id}"))
    
    bot.send_message(chat_id, confirmation_text, reply_markup=keyboard, parse_mode='Markdown')

def show_claim_confirmation(chat_id: int, user_id: int):
    """Показ финального подтверждения заявки на аппрув"""
    if user_id not in presave_claim_sessions:
        return
    
    session = presave_claim_sessions[user_id]
    
    confirmation_text = f"""
📸 **Заявка на аппрув готова к отправке**

🖼️ **Скриншотов:** {len(session.screenshots)}
💬 **Комментарий:** {session.comment}

Отправить заявку админам на рассмотрение?
"""
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("✅ Отправить заявку", callback_data=f"submit_claim_{user_id}"))
    keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_claim_{user_id}"))
    
    bot.send_message(chat_id, confirmation_text, reply_markup=keyboard, parse_mode='Markdown')

def handle_reminder_edit_input(message):
    """Обработка ввода нового текста напоминания (админы)"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Нет прав доступа")
        return
    
    new_reminder = message.text.strip()
    
    try:
        # Обновляем напоминание в настройках
        db_manager.update_setting('reminder_text', new_reminder)
        
        # Обновляем глобальную переменную
        global REMINDER_TEXT
        REMINDER_TEXT = new_reminder
        
        # Очищаем состояние
        if user_id in user_sessions:
            del user_sessions[user_id]
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Вернуться в настройки бота", callback_data="bot_settings"))
        
        bot.reply_to(message, "✅ **Успешно** - Текст напоминания обновлен", 
                    reply_markup=keyboard, parse_mode='Markdown')
        
        log_user_action(user_id, "SUCCESS", "Reminder text updated")
        
    except Exception as e:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Вернуться в настройки бота", callback_data="bot_settings"))
        
        bot.reply_to(message, "❌ **Ошибка** - Не удалось обновить напоминание", 
                    reply_markup=keyboard, parse_mode='Markdown')
        
        log_user_action(user_id, "ERROR", f"Failed to update reminder: {str(e)}")

def handle_username_analytics_input(message):
    """Обработка ввода username для аналитики (админы)"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        bot.reply_to(message, "❌ Нет прав доступа")
        return
    
    username = message.text.strip().replace('@', '')
    
    if not username:
        bot.reply_to(message, "❌ Укажите корректный username")
        return
    
    # Получаем тип аналитики из сессии
    session = user_sessions.get(user_id)
    if not session:
        bot.reply_to(message, "❌ Сессия истекла")
        return
    
    analytics_type = session.data.get('analytics_type', 'links')
    
    try:
        if analytics_type == 'links':
            result = get_user_links_analytics(username)
            response = format_links_analytics(username, result)
        elif analytics_type == 'approvals':
            result = get_user_approvals_analytics(username)
            response = format_approvals_analytics(username, result)
        elif analytics_type == 'comparison':
            result = get_user_comparison_analytics(username)
            response = format_comparison_analytics(username, result)
        else:
            response = "❌ Неизвестный тип аналитики"
        
        # Очищаем состояние
        del user_sessions[user_id]
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Вернуться в аналитику", callback_data="admin_analytics"))
        
        bot.reply_to(message, response, reply_markup=keyboard, parse_mode='Markdown')
        
        log_user_action(user_id, "SUCCESS", f"Analytics for @{username}, type: {analytics_type}")
        
    except Exception as e:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Вернуться в аналитику", callback_data="admin_analytics"))
        
        bot.reply_to(message, f"❌ **Ошибка аналитики для @{username}**", 
                    reply_markup=keyboard, parse_mode='Markdown')
        
        log_user_action(user_id, "ERROR", f"Analytics failed for @{username}: {str(e)}")

# Дополнительные функции аналитики (упрощенные версии)
def get_user_links_analytics(username: str) -> dict:
    """Получение аналитики ссылок пользователя"""
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            
            if not result:
                return {}
            
            user_id = result[0]
            
            # Общее количество ссылок
            cursor.execute('SELECT COUNT(*) FROM user_links WHERE user_id = ?', (user_id,))
            total_links = cursor.fetchone()[0]
            
            # Просьбы о пресейвах
            cursor.execute('SELECT COUNT(*) FROM presave_requests WHERE user_id = ?', (user_id,))
            presave_requests = cursor.fetchone()[0]
            
            # Последние ссылки
            cursor.execute('''
                SELECT ul.link_url, ul.message_id, ul.created_at
                FROM user_links ul
                WHERE ul.user_id = ?
                ORDER BY ul.created_at DESC
                LIMIT 5
            ''', (user_id,))
            
            recent_links = [{'message_id': row[1]} for row in cursor.fetchall()]
            
            return {
                'total_links': total_links,
                'presave_requests': presave_requests,
                'recent_links': recent_links,
                'last_activity': 'Недавно'
            }
    except Exception:
        return {}

def get_user_approvals_analytics(username: str) -> dict:
    """Получение аналитики аппрувов пользователя"""
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            
            if not result:
                return {}
            
            user_id = result[0]
            user_stats = db_manager.get_user_stats(user_id)
            
            # Подтвержденные заявки
            cursor.execute('SELECT COUNT(*) FROM approval_claims WHERE user_id = ? AND status = "approved"', (user_id,))
            approved_claims = cursor.fetchone()[0]
            
            # Отклоненные заявки
            cursor.execute('SELECT COUNT(*) FROM approval_claims WHERE user_id = ? AND status = "rejected"', (user_id,))
            rejected_claims = cursor.fetchone()[0]
            
            # Ожидающие заявки
            cursor.execute('SELECT COUNT(*) FROM approval_claims WHERE user_id = ? AND status = "pending"', (user_id,))
            pending_claims = cursor.fetchone()[0]
            
            return {
                'approved_claims': approved_claims,
                'rejected_claims': rejected_claims,
                'pending_claims': pending_claims,
                'rank': user_stats['rank'].value,
                'monthly_stats': {'Этот месяц': approved_claims}
            }
    except Exception:
        return {}

def get_user_comparison_analytics(username: str) -> dict:
    """Получение сравнительной аналитики пользователя"""
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE username = ?', (username,))
            result = cursor.fetchone()
            
            if not result:
                return {}
            
            user_id = result[0]
            user_stats = db_manager.get_user_stats(user_id)
            
            return {
                'presave_requests': user_stats['requests_count'],
                'approved_claims': user_stats['approvals_count']
            }
    except Exception:
        return {}

def format_links_analytics(username: str, data: dict) -> str:
    """Форматирование аналитики ссылок пользователя"""
    if not data:
        return f"📊 **Аналитика @{username}**\n\nДанных не найдено"
    
    return f"""
📊 **Аналитика ссылок @{username}**

🔗 **Всего ссылок:** {data.get('total_links', 0)}
🎵 **Просьб о пресейвах:** {data.get('presave_requests', 0)}
📅 **Последняя активность:** {data.get('last_activity', 'Неизвестно')}

**Последние 5 ссылок:**
{chr(10).join([f"• [Пост {link['message_id']}](https://t.me/c/{abs(GROUP_ID)}/{link['message_id']})" for link in data.get('recent_links', [])[:5]])}
"""

def format_approvals_analytics(username: str, data: dict) -> str:
    """Форматирование аналитики аппрувов пользователя"""
    if not data:
        return f"📊 **Аналитика @{username}**\n\nДанных не найдено"
    
    return f"""
📊 **Аналитика аппрувов @{username}**

✅ **Подтвержденных заявок:** {data.get('approved_claims', 0)}
❌ **Отклоненных заявок:** {data.get('rejected_claims', 0)}
⏳ **Ожидающих заявок:** {data.get('pending_claims', 0)}
🏆 **Звание:** {data.get('rank', 'Неизвестно')}

**Статистика по месяцам:**
{chr(10).join([f"• {month}: {count} аппрувов" for month, count in data.get('monthly_stats', {}).items()])}
"""

def format_comparison_analytics(username: str, data: dict) -> str:
    """Форматирование сравнительной аналитики пользователя"""
    if not data:
        return f"📊 **Аналитика @{username}**\n\nДанных не найдено"
    
    requests = data.get('presave_requests', 0)
    approvals = data.get('approved_claims', 0)
    ratio = round(approvals / requests, 2) if requests > 0 else 0
    
    return f"""
📊 **Сравнительная аналитика @{username}**

🎵 **Просил пресейвы:** {requests} раз
📸 **Сделал пресейвы:** {approvals} раз
⚖️ **Соотношение (аппрув/просьба):** {ratio}

**Оценка взаимности:**
{get_reciprocity_assessment(ratio)}

**Рекомендации:**
{get_reciprocity_recommendations(ratio, requests, approvals)}
"""

def get_reciprocity_assessment(ratio: float) -> str:
    """Оценка взаимности пользователя"""
    if ratio >= 1.0:
        return "🌟 **Отличная взаимность** - делает больше, чем просит"
    elif ratio >= 0.7:
        return "✅ **Хорошая взаимность** - активно поддерживает других"
    elif ratio >= 0.4:
        return "⚖️ **Средняя взаимность** - есть куда стремиться"
    elif ratio >= 0.1:
        return "⚠️ **Низкая взаимность** - редко поддерживает других"
    else:
        return "❌ **Отсутствие взаимности** - только просит, не поддерживает"

def get_reciprocity_recommendations(ratio: float, requests: int, approvals: int) -> str:
    """Рекомендации по улучшению взаимности"""
    if ratio >= 1.0:
        return "Продолжайте в том же духе! Вы - пример для сообщества."
    elif ratio >= 0.7:
        return "Отличная активность! Можете иногда просить больше поддержки."
    elif ratio >= 0.4:
        needed = max(1, int(requests * 0.7 - approvals))
        return f"Сделайте еще {needed} пресейвов для улучшения баланса."
    else:
        needed = max(1, int(requests * 0.5))
        return f"Рекомендуется сделать {needed} пресейвов перед новыми просьбами."

# Дополнительные callback handlers (продолжение секции 11)

def handle_cancel_request_callback(call):
    """Отмена просьбы о пресейве"""
    callback_user_id = int(call.data.split('_')[2])
    
    # Проверка безопасности
    if call.from_user.id != callback_user_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша заявка")
        return
    
    # Очистка сессий
    if callback_user_id in user_sessions:
        del user_sessions[callback_user_id]
    if callback_user_id in presave_request_sessions:
        del presave_request_sessions[callback_user_id]
    
    bot.edit_message_text(
        "❌ **Просьба о пресейве отменена**",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )
    
    log_user_action(callback_user_id, "REQUEST_PRESAVE", "Request cancelled")

def handle_publish_request_callback(call):
    """Публикация просьбы о пресейве в топике"""
    try:
        callback_user_id = int(call.data.split('_')[2])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "❌ Некорректные данные")
        return
    
    # Проверка безопасности
    if call.from_user.id != callback_user_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша заявка")
        return
    
    if callback_user_id not in presave_request_sessions:
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return
    
    session = presave_request_sessions[callback_user_id]
    
    try:
        # Формируем сообщение для публикации
        username = safe_username(call.from_user)
        
        post_text = f"🎵 **Просьба о пресейве от @{username}**\n\n"
        post_text += f"💬 {safe_string(session.comment, 500)}\n\n"
        post_text += "🔗 **Ссылки:**\n"
        
        for i, link in enumerate(session.links, 1):
            post_text += f"{i}. {link}\n"
        
        # Публикуем в топике
        published_message = bot.send_message(
            GROUP_ID,
            post_text,
            parse_mode='Markdown',
            message_thread_id=THREAD_ID,
            disable_web_page_preview=True
        )
        
        # Сохраняем в БД
        request_id = db_manager.add_presave_request(
            user_id=callback_user_id,
            links=session.links,
            comment=session.comment,
            message_id=published_message.message_id
        )
        
        # Очистка сессий
        if callback_user_id in user_sessions:
            del user_sessions[callback_user_id]
        if callback_user_id in presave_request_sessions:
            del presave_request_sessions[callback_user_id]
        
        bot.edit_message_text(
            f"✅ **Объявление опубликовано!**\n\n[Перейти к посту](https://t.me/c/{abs(GROUP_ID)}/{published_message.message_id})",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        
        log_user_action(callback_user_id, "REQUEST_PRESAVE", f"Published request #{request_id}")
        
    except Exception as e:
        bot.edit_message_text(
            "❌ **Ошибка публикации**\n\nПопробуйте еще раз",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        log_user_action(callback_user_id, "ERROR", f"Failed to publish request: {str(e)}")

def handle_cancel_claim_callback(call):
    """Отмена заявки на аппрув"""
    callback_user_id = int(call.data.split('_')[2])
    
    # Проверка безопасности
    if call.from_user.id != callback_user_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша заявка")
        return
    
    # Очистка сессий
    if callback_user_id in user_sessions:
        del user_sessions[callback_user_id]
    if callback_user_id in presave_claim_sessions:
        del presave_claim_sessions[callback_user_id]
    
    bot.edit_message_text(
        "❌ **Заявка на аппрув отменена**",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )
    
    log_user_action(callback_user_id, "CLAIM_PRESAVE", "Claim cancelled")

def handle_submit_claim_callback(call):
    """Подача заявки на аппрув"""
    try:
        callback_user_id = int(call.data.split('_')[2])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "❌ Некорректные данные")
        return
    
    # Проверка безопасности
    if call.from_user.id != callback_user_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша заявка")
        return
    
    if callback_user_id not in presave_claim_sessions:
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return
    
    session = presave_claim_sessions[callback_user_id]
    
    try:
        # Проверяем доверенность пользователя
        user_stats = db_manager.get_user_stats(callback_user_id)
        is_trusted = user_stats['is_trusted']
        
        if is_trusted:
            # Автоматический аппрув для доверенных пользователей
            claim_id = db_manager.add_approval_claim(
                user_id=callback_user_id,
                screenshots=session.screenshots,
                comment=session.comment
            )
            
            # Сразу подтверждаем
            db_manager.approve_claim(claim_id, 0, True)  # 0 = system auto-approval
            
            success_text = f"""
✅ **Заявка автоматически подтверждена!**

🌟 Как доверенный пресейвер ({user_stats['rank'].value}), ваши заявки подтверждаются автоматически.

📈 **Ваша статистика обновлена:**
• Аппрувов: {user_stats['approvals_count'] + 1}
"""
            
            log_user_action(callback_user_id, "CLAIM_PRESAVE", f"Auto-approved claim #{claim_id}")
        else:
            # Обычная заявка на рассмотрение
            claim_id = db_manager.add_approval_claim(
                user_id=callback_user_id,
                screenshots=session.screenshots,
                comment=session.comment
            )
            
            success_text = f"""
📨 **Заявка отправлена на рассмотрение!**

📸 Заявка #{claim_id} передана админам для проверки.

⏳ Ожидайте подтверждения. После 6 аппрувов вы станете доверенным пресейвером с автоматическим подтверждением.
"""
            
            log_user_action(callback_user_id, "CLAIM_PRESAVE", f"Submitted claim #{claim_id}")
        
        # Очистка сессий
        if callback_user_id in user_sessions:
            del user_sessions[callback_user_id]
        if callback_user_id in presave_claim_sessions:
            del presave_claim_sessions[callback_user_id]
        
        bot.edit_message_text(
            success_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        bot.edit_message_text(
            "❌ **Ошибка отправки заявки**\n\nПопробуйте еще раз",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        log_user_action(callback_user_id, "ERROR", f"Failed to submit claim: {str(e)}")

def handle_approve_claim_callback(call):
    """Подтверждение заявки админом"""
    claim_id = int(call.data.split('_')[2])
    admin_id = call.from_user.id
    
    try:
        # Подтверждаем заявку
        db_manager.approve_claim(claim_id, admin_id, True)
        
        bot.edit_message_text(
            f"✅ **Заявка #{claim_id} подтверждена**\n\nАппрув засчитан пользователю",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        
        log_user_action(admin_id, "ADMIN_APPROVE", f"Approved claim #{claim_id}")
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")
        log_user_action(admin_id, "ERROR", f"Failed to approve claim #{claim_id}: {str(e)}")

def handle_reject_claim_callback(call):
    """Отклонение заявки админом"""
    claim_id = int(call.data.split('_')[2])
    admin_id = call.from_user.id
    
    try:
        # Отклоняем заявку
        db_manager.approve_claim(claim_id, admin_id, False)
        
        bot.edit_message_text(
            f"❌ **Заявка #{claim_id} отклонена**\n\nАппрув не засчитан",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        
        log_user_action(admin_id, "ADMIN_REJECT", f"Rejected claim #{claim_id}")
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)}")
        log_user_action(admin_id, "ERROR", f"Failed to reject claim #{claim_id}: {str(e)}")

def handle_bot_settings_callback(call):
    """Меню настроек бота для админов"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🎛️ Режимы лимитов", callback_data="rate_modes_menu"))
    keyboard.add(InlineKeyboardButton("✅ Активировать бота", callback_data="activate_bot"))
    keyboard.add(InlineKeyboardButton("⏸️ Деактивировать бота", callback_data="deactivate_bot"))
    keyboard.add(InlineKeyboardButton("💬 Изменить текст напоминания", callback_data="change_reminder"))
    keyboard.add(InlineKeyboardButton("🗑️ Очистить данные", callback_data="clear_data_menu"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_actions"))
    
    bot.edit_message_text(
        "🎛️ **Настройки бота**",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_setmode_callback(call):
    """Установка режима лимитов"""
    mode_name = call.data.split('_')[1]  # conservative, normal, burst, adminburst
    admin_id = call.from_user.id
    
    mode_map = {
        'conservative': LimitMode.CONSERVATIVE,
        'normal': LimitMode.NORMAL,
        'burst': LimitMode.BURST,
        'adminburst': LimitMode.ADMIN_BURST
    }
    
    new_mode = mode_map.get(mode_name)
    if new_mode:
        update_limit_mode(new_mode, admin_id)
        mode_settings = LIMIT_MODES[new_mode]
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад к режимам", callback_data="rate_modes_menu"))
        
        bot.edit_message_text(
            f"✅ **Режим изменен на {new_mode.value}**\n\n"
            f"📊 Лимит: {mode_settings['max_hour']}/час\n"
            f"⏱️ Задержка: {mode_settings['cooldown']}с",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    else:
        bot.answer_callback_query(call.id, "❌ Неизвестный режим")

def handle_diagnostics_callback(call):
    """Меню диагностики для админов"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("💓 Тест Keep Alive", callback_data="test_keepalive"))
    keyboard.add(InlineKeyboardButton("🔧 Проверка системы", callback_data="test_system"))
    keyboard.add(InlineKeyboardButton("📊 Статус бота", callback_data="bot_status_info"))
    keyboard.add(InlineKeyboardButton("📈 Метрики производительности", callback_data="performance_metrics"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        "🔧 **Диагностика системы**",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_help_callback(call):
    """Показ справки через callback"""
    user_id = call.from_user.id
    is_admin = validate_admin(user_id)
    
    help_text = """
❓ **Справка по боту**

🎵 **Основные функции:**
• Автоматические напоминания о пресейвах при публикации ссылок
• Интерактивная подача объявлений о просьбе пресейва
• Система заявок на аппрув совершенных пресейвов
• Статистика и рейтинги участников

📱 **Команды:**
/menu - главное меню
/mystat - ваша статистика
/presavestats - общий рейтинг
/recent - последние 10 ссылок

🏆 **Звания за подтвержденные пресейвы:**
🥉 Новенький (1-5 аппрувов)
🥈 Надежный пресейвер (6-15) - доверенный
🥇 Мега-человечище (16-30) - доверенный
💎 Амбассадорище (31+) - доверенный
"""
    
    if is_admin:
        help_text += """

👑 **Админские функции:**
• Проверка заявок на аппрувы
• Настройки режимов лимитов  
• Управление активностью бота
• Расширенная аналитика
• Диагностика системы
"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        help_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_rate_modes_menu_callback(call):
    """Меню режимов лимитов"""
    current_mode = get_current_limit_mode()
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton(f"🟢 Conservative{' (активен)' if current_mode == LimitMode.CONSERVATIVE else ''}", callback_data="setmode_conservative"))
    keyboard.add(InlineKeyboardButton(f"🟡 Normal{' (активен)' if current_mode == LimitMode.NORMAL else ''}", callback_data="setmode_normal"))
    keyboard.add(InlineKeyboardButton(f"🟠 Burst{' (активен)' if current_mode == LimitMode.BURST else ''}", callback_data="setmode_burst"))
    keyboard.add(InlineKeyboardButton(f"🔴 Admin Burst{' (активен)' if current_mode == LimitMode.ADMIN_BURST else ''}", callback_data="setmode_adminburst"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="bot_settings"))
    
    mode_info = LIMIT_MODES[current_mode]
    text = f"""🎛️ **Режимы лимитов**

**Текущий режим:** {current_mode.value}
📊 Лимит: {mode_info['max_hour']}/час
⏱️ Задержка: {mode_info['cooldown']}с

Выберите новый режим:"""
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_activate_bot_callback(call):
    """Активация бота"""
    admin_id = call.from_user.id
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к настройкам", callback_data="bot_settings"))
    
    try:
        db_manager.set_bot_active(True)
        bot_status["enabled"] = True
        
        bot.edit_message_text(
            "✅ **Бот активирован**\n\nБот теперь отвечает на сообщения с ссылками",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        log_user_action(admin_id, "SUCCESS", "Bot activated")
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ **Ошибка активации:** {str(e)}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        log_user_action(admin_id, "ERROR", f"Failed to activate bot: {str(e)}")

def handle_deactivate_bot_callback(call):
    """Деактивация бота"""
    admin_id = call.from_user.id
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к настройкам", callback_data="bot_settings"))
    
    try:
        db_manager.set_bot_active(False)
        bot_status["enabled"] = False
        
        bot.edit_message_text(
            "⏸️ **Бот деактивирован**\n\nБот больше не отвечает на сообщения с ссылками",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        log_user_action(admin_id, "SUCCESS", "Bot deactivated")
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ **Ошибка деактивации:** {str(e)}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        log_user_action(admin_id, "ERROR", f"Failed to deactivate bot: {str(e)}")

def handle_change_reminder_callback(call):
    """Начало изменения текста напоминания"""
    admin_id = call.from_user.id
    
    # Устанавливаем состояние ожидания нового текста
    user_sessions[admin_id] = UserSession(
        state=UserState.EDITING_REMINDER,
        data={'type': 'reminder_edit'},
        timestamp=datetime.now()
    )
    
    current_reminder = db_manager.get_setting('reminder_text', REMINDER_TEXT)
    
    text = f"""💬 **Изменение текста напоминания**

**Текущий текст:**
{current_reminder}

Отправьте новый текст напоминания в личных сообщениях боту."""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data="bot_settings"))
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_clear_data_menu_callback(call):
    """Меню очистки данных"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🗑️ Очистить ссылки", callback_data="clear_links"))
    keyboard.add(InlineKeyboardButton("🗑️ Очистить заявки на аппрувы", callback_data="clear_approvals"))
    keyboard.add(InlineKeyboardButton("🗑️ Очистить просьбы о пресейвах", callback_data="clear_asks"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="bot_settings"))
    
    bot.edit_message_text(
        "🗑️ **Очистка данных**\n\nВыберите что очистить:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_check_approvals_callback(call):
    """Переход к проверке заявок на аппрув"""
    admin_id = call.from_user.id
    
    pending_claims = db_manager.get_pending_claims()
    
    if not pending_claims:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню Действия", 
                                        callback_data="admin_actions"))
        bot.edit_message_text(
            "✅ **Заявок на рассмотрение нет**",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return
    
    # Показываем первую заявку для рассмотрения
    show_claim_for_approval(call.message.chat.id, pending_claims[0], 0, len(pending_claims))
    log_user_action(admin_id, "ADMIN_APPROVE", f"Checking {len(pending_claims)} pending claims")

def handle_recent_links_callback(call):
    """Показ последних ссылок"""
    # Извлекаем количество из callback_data
    if "recent_links_30" in call.data:
        limit = 30
    elif "recent_links_10" in call.data:
        limit = 10
    else:
        limit = 10
    
    recent_links = db_manager.get_recent_links(limit)
    
    if not recent_links:
        text = f"📎 **Последние {limit} ссылок**\n\nПока нет ссылок в сообществе"
    else:
        text = f"📎 **Последние {limit} ссылок:**\n\n"
        for i, link_data in enumerate(recent_links, 1):
            username = link_data['username'] or 'Unknown'
            message_id = link_data['message_id']
            message_link = f"https://t.me/c/{abs(GROUP_ID)}/{message_id}"
            text += f"{i}. @{username} - [перейти к посту]({message_link})\n"
    
    keyboard = InlineKeyboardMarkup()
    if call.from_user.id in ADMIN_IDS:
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_actions"))
    else:
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="user_actions"))
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

def handle_user_analytics_callback(call):
    """Пользовательская аналитика"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("📊 Ссылки по @username", callback_data="user_links_search"))
    keyboard.add(InlineKeyboardButton("✅ Аппрувы по @username", callback_data="user_approvals_search"))
    keyboard.add(InlineKeyboardButton("⚖️ Соотношение по @username", callback_data="user_comparison_search"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        "📊 **Аналитика пользователей**",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_test_keepalive_callback(call):
    """Тест keep alive через callback"""
    render_url = os.getenv('RENDER_EXTERNAL_URL', 'localhost')
    url = f"https://{render_url}/keepalive"
    
    start_time = time.time()
    success = make_keep_alive_request(url)
    duration = round((time.time() - start_time) * 1000, 2)
    
    status = "✅ OK" if success else "❌ FAILED"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к диагностике", callback_data="diagnostics"))
    
    bot.edit_message_text(
        f"💓 **Keep Alive Test**\n\n{status}\nДлительность: {duration}ms\nURL: {url}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_test_system_callback(call):
    """Проверка системы через callback"""
    # Проверка всех компонентов
    checks = {}
    
    # БД
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            user_count = cursor.fetchone()[0]
        checks['database'] = f"✅ OK ({user_count} пользователей)"
    except Exception as e:
        checks['database'] = f"❌ ERROR: {str(e)}"
    
    # Telegram API
    try:
        bot_info = bot.get_me()
        checks['telegram_api'] = f"✅ OK (@{bot_info.username})"
    except Exception as e:
        checks['telegram_api'] = f"❌ ERROR: {str(e)}"
    
    # Скриншоты
    try:
        screenshots_count = db_manager.get_active_screenshots_count()
        checks['screenshots'] = f"✅ OK ({screenshots_count} активных)"
    except Exception as e:
        checks['screenshots'] = f"❌ ERROR: {str(e)}"
    
    system_text = "🔧 **Проверка системы:**\n\n"
    for component, status in checks.items():
        system_text += f"**{component}:** {status}\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к диагностике", callback_data="diagnostics"))
    
    bot.edit_message_text(
        system_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_bot_status_info_callback(call):
    """Информация о статусе бота через callback"""
    uptime = datetime.now() - bot_status["start_time"]
    current_mode = get_current_limit_mode()
    active = db_manager.is_bot_active()
    
    status_text = f"""
🤖 **Статус бота:**

📊 Активность: {'✅ Активен' if active else '⏸️ Деактивирован'}
⏱️ Uptime: {str(uptime).split('.')[0]}
🎛️ Режим лимитов: {current_mode.value}
📸 Активных скриншотов: {db_manager.get_active_screenshots_count()}
💾 Сессий пользователей: {len(user_sessions)}

🔗 Webhook: настроен
💓 Keep alive: активен
"""
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к диагностике", callback_data="diagnostics"))
    
    bot.edit_message_text(
        status_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_performance_metrics_callback(call):
    """Метрики производительности через callback"""
    metrics_summary = metrics.get_summary()
    
    metrics_text = "📈 **Метрики производительности:**\n\n"
    
    # Счетчики
    if metrics_summary.get('counters'):
        metrics_text += "**Счетчики:**\n"
        for metric, count in metrics_summary['counters'].items():
            metrics_text += f"• {metric}: {count}\n"
        metrics_text += "\n"
    
    # Времена выполнения
    if metrics_summary.get('timings'):
        metrics_text += "**Производительность (мс):**\n"
        for metric, timing in metrics_summary['timings'].items():
            avg = timing['avg_ms']
            metrics_text += f"• {metric}: {avg}ms (avg)\n"
    
    if not metrics_summary.get('counters') and not metrics_summary.get('timings'):
        metrics_text += "Данных пока нет"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к диагностике", callback_data="diagnostics"))
    
    bot.edit_message_text(
        metrics_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_clear_specific_data_callback(call):
    """Очистка конкретных данных"""
    admin_id = call.from_user.id
    data_type = call.data.split('_')[1]  # links, approvals, asks
    
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            
            if data_type == 'links':
                cursor.execute('DELETE FROM user_links')
                cleared = cursor.rowcount
                message = f"✅ **Очищено {cleared} ссылок**"
                
            elif data_type == 'approvals':
                cursor.execute('DELETE FROM approval_claims WHERE status = "pending"')
                cleared = cursor.rowcount
                message = f"✅ **Очищено {cleared} заявок на аппрув**"
                
            elif data_type == 'asks':
                cursor.execute('DELETE FROM presave_requests')
                cleared = cursor.rowcount
                message = f"✅ **Очищено {cleared} просьб о пресейвах**"
            else:
                message = "❌ **Неизвестный тип данных**"
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="clear_data_menu"))
        
        bot.edit_message_text(
            message,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        log_user_action(admin_id, "SUCCESS", f"Cleared {data_type}: {cleared} items")
        
    except Exception as e:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="clear_data_menu"))
        
        bot.edit_message_text(
            f"❌ **Ошибка очистки:** {str(e)}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        log_user_action(admin_id, "ERROR", f"Failed to clear {data_type}: {str(e)}")

def handle_admin_analytics_callback(call):
    """Меню админской аналитики"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("📊 Ссылки по @username", callback_data="admin_user_links"))
    keyboard.add(InlineKeyboardButton("✅ Аппрувы по @username", callback_data="admin_user_approvals"))
    keyboard.add(InlineKeyboardButton("⚖️ Соотношение по @username", callback_data="admin_user_comparison"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    
    bot.edit_message_text(
        "📊 **Расширенная аналитика**",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

def handle_admin_user_links_callback(call):
    """Запрос username для просмотра ссылок (админ)"""
    admin_id = call.from_user.id
    
    user_sessions[admin_id] = UserSession(
        state=UserState.WAITING_USERNAME_FOR_ANALYTICS,
        data={'analytics_type': 'links'},
        timestamp=datetime.now()
    )
    
    bot.edit_message_text(
        "📊 **Аналитика ссылок**\n\nОтправьте username (без @) для анализа:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

def handle_admin_user_approvals_callback(call):
    """Запрос username для просмотра аппрувов (админ)"""
    admin_id = call.from_user.id
    
    user_sessions[admin_id] = UserSession(
        state=UserState.WAITING_USERNAME_FOR_ANALYTICS,
        data={'analytics_type': 'approvals'},
        timestamp=datetime.now()
    )
    
    bot.edit_message_text(
        "✅ **Аналитика аппрувов**\n\nОтправьте username (без @) для анализа:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

def handle_admin_user_comparison_callback(call):
    """Запрос username для сравнительной аналитики (админ)"""
    admin_id = call.from_user.id
    
    user_sessions[admin_id] = UserSession(
        state=UserState.WAITING_USERNAME_FOR_ANALYTICS,
        data={'analytics_type': 'comparison'},
        timestamp=datetime.now()
    )
    
    bot.edit_message_text(
        "⚖️ **Сравнительная аналитика**\n\nОтправьте username (без @) для анализа:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

def handle_user_links_search_callback(call):
    """Поиск ссылок по username (пользователь)"""
    user_id = call.from_user.id
    
    user_sessions[user_id] = UserSession(
        state=UserState.WAITING_USERNAME_FOR_ANALYTICS,
        data={'analytics_type': 'links'},
        timestamp=datetime.now()
    )
    
    bot.edit_message_text(
        "📊 **Поиск ссылок**\n\nОтправьте username (без @) для поиска:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

def handle_user_approvals_search_callback(call):
    """Поиск аппрувов по username (пользователь)"""
    user_id = call.from_user.id
    
    user_sessions[user_id] = UserSession(
        state=UserState.WAITING_USERNAME_FOR_ANALYTICS,
        data={'analytics_type': 'approvals'},
        timestamp=datetime.now()
    )
    
    bot.edit_message_text(
        "✅ **Поиск аппрувов**\n\nОтправьте username (без @) для поиска:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

def handle_user_comparison_search_callback(call):
    """Поиск сравнительной статистики (пользователь)"""
    user_id = call.from_user.id
    
    user_sessions[user_id] = UserSession(
        state=UserState.WAITING_USERNAME_FOR_ANALYTICS,
        data={'analytics_type': 'comparison'},
        timestamp=datetime.now()
    )
    
    bot.edit_message_text(
        "⚖️ **Сравнительная статистика**\n\nОтправьте username (без @) для анализа:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

def handle_proceed_to_comment_callback(call):
    """Переход к комментарию в заявке на аппрув"""
    user_id = call.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id].state != UserState.CLAIMING_PRESAVE_SCREENSHOTS:
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return
    
    # Переводим в состояние ввода комментария
    user_sessions[user_id].state = UserState.CLAIMING_PRESAVE_COMMENT
    
    bot.edit_message_text(
        "💬 **Шаг 2: Комментарий к заявке**\n\nОтправьте комментарий о совершенном пресейве:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

def handle_next_claim_callback(call):
    """Переход к следующей заявке на аппрув"""
    admin_id = call.from_user.id
    
    if admin_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ Нет прав доступа")
        return
    
    next_index = int(call.data.split('_')[2])
    pending_claims = db_manager.get_pending_claims()
    
    if next_index < len(pending_claims):
        show_claim_for_approval(call.message.chat.id, pending_claims[next_index], next_index, len(pending_claims))
    else:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню Действия", callback_data="admin_actions"))
        
        bot.edit_message_text(
            "✅ **Все заявки рассмотрены**",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

def handle_add_screenshot_callback(call):
    """Добавление еще одного скриншота"""
    user_id = call.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id].state != UserState.CLAIMING_PRESAVE_SCREENSHOTS:
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return
    
    bot.edit_message_text(
        "📸 **Отправьте еще один скриншот**\n\nВы можете добавить дополнительные доказательства:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

# ================================
# 13. СИСТЕМА KEEP ALIVE И WEBHOOK
# ================================

def keep_alive_worker():
    """
    Фоновый поток для поддержания активности каждые 5 минут
    Использует urllib для HTTP запросов (без внешних зависимостей)
    Предотвращает засыпание сервиса на Render.com
    """
    while True:
        try:
            time.sleep(300)  # 5 минут
            
            # Очистка просроченных данных
            cleanup_expired_sessions()
            cleanup_expired_screenshots()
            db_manager.cleanup_expired_screenshots()
            
            # Keep alive запрос
            render_url = os.getenv('RENDER_EXTERNAL_URL')
            if render_url:
                url = f"https://{render_url}/keepalive"
                
                start_time = time.time()
                success = make_keep_alive_request(url)
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                log_user_action(
                    user_id=0,
                    action="KEEP_ALIVE_PING",
                    details=f"Success: {success}, Duration: {duration_ms}ms, URL: {url}"
                )
                
                if success:
                    metrics.increment('keepalive.success')
                else:
                    metrics.increment('keepalive.failure')
                
                metrics.timing('keepalive.duration', duration_ms)
            
        except Exception as e:
            centralized_error_logger(
                error=e,
                context="Keep alive worker"
            )
            metrics.increment('keepalive.error')

class WebhookHandler(BaseHTTPRequestHandler):
    """
    Продвинутый HTTP handler для webhook с детальным логированием
    Оптимизирован для Render.com диагностики
    """
    
    def do_POST(self):
        client_ip = self.client_address[0]
        correlation_id = f"webhook_{int(time.time() * 1000)}_{os.getpid()}"
        
        with request_context(correlation_id=correlation_id, client_ip=client_ip):
            start_time = time.time()
            
            log_user_action(
                user_id=0,
                action="HTTP_REQUEST_POST",
                details=f"Path: {self.path}, Client: {client_ip}",
                correlation_id=correlation_id,
                client_ip=client_ip
            )
            
            # Rate limiting проверка
            if client_ip != '127.0.0.1' and not rate_limiter.is_allowed(client_ip):
                log_user_action(
                    user_id=0,
                    action="WEBHOOK_RATE_LIMITED",
                    details=f"Client: {client_ip}",
                    correlation_id=correlation_id,
                    client_ip=client_ip
                )
                metrics.increment('webhook.rate_limited')
                self.send_response(429)
                self.end_headers()
                return
            
            # Определение пути webhook
            webhook_path = f"/{BOT_TOKEN}"
            
            if self.path == webhook_path:
                self._handle_telegram_webhook(correlation_id, client_ip, start_time)
            elif self.path == '/' or self.path == '/health':
                self._handle_health_check(correlation_id)
            elif self.path == '/keepalive':
                self._handle_keepalive_request(correlation_id, client_ip)
            else:
                log_user_action(
                    user_id=0,
                    action="WEBHOOK_UNKNOWN_PATH",
                    details=f"Path: {self.path}",
                    correlation_id=correlation_id,
                    client_ip=client_ip
                )
                metrics.increment('webhook.unknown_path')
                self.send_response(404)
                self.end_headers()
    
    def do_GET(self):
        client_ip = self.client_address[0]
        correlation_id = f"get_{int(time.time() * 1000)}_{os.getpid()}"
        
        with request_context(correlation_id=correlation_id, client_ip=client_ip):
            log_user_action(
                user_id=0,
                action="HTTP_REQUEST_GET",
                details=f"Path: {self.path}, Client: {client_ip}",
                correlation_id=correlation_id,
                client_ip=client_ip
            )
            
            if self.path == '/' or self.path == '/health':
                self._handle_health_check(correlation_id)
            elif self.path == '/keepalive':
                self._handle_keepalive_request(correlation_id, client_ip)
            elif self.path == '/metrics':
                self._handle_metrics_request(correlation_id)
            elif self.path == f"/{BOT_TOKEN}":
                self._handle_webhook_info_page(correlation_id)
            else:
                log_user_action(
                    user_id=0,
                    action="HTTP_UNKNOWN_PATH",
                    details=f"Path: {self.path}",
                    correlation_id=correlation_id,
                    client_ip=client_ip
                )
                metrics.increment('http.unknown_path')
                self.send_response(404)
                self.end_headers()
    
    def _handle_telegram_webhook(self, correlation_id: str, client_ip: str, start_time: float):
        """Обработка webhook'а от Telegram с детальным логированием"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Проверка безопасности
            security_check = security.verify_telegram_request(self.headers, content_length, client_ip)
            if not security_check:
                log_user_action(
                    user_id=0,
                    action="WEBHOOK_SECURITY_FAILED",
                    details=f"Client: {client_ip}, Content-Length: {content_length}",
                    correlation_id=correlation_id,
                    client_ip=client_ip
                )
                metrics.increment('webhook.security_failed')
                self.send_response(401)
                self.end_headers()
                return
            
            # Чтение данных
            post_data = self.rfile.read(content_length)
            
            log_user_action(
                user_id=0,
                action="WEBHOOK_DATA_RECEIVED",
                details=f"Bytes: {content_length}, Client: {client_ip}",
                correlation_id=correlation_id,
                client_ip=client_ip
            )
            
            # Health check (пустой запрос)
            if content_length == 0:
                log_user_action(
                    user_id=0,
                    action="WEBHOOK_HEALTH_CHECK",
                    details=f"Empty request from {client_ip}",
                    correlation_id=correlation_id,
                    client_ip=client_ip
                )
                metrics.increment('webhook.health_check')
                self.send_response(200)
                self.end_headers()
                return
            
            # Парсинг JSON
            try:
                update_data = json.loads(post_data.decode('utf-8'))
                
                # Логирование типа обновления
                update_type = "unknown"
                if 'message' in update_data:
                    update_type = "message"
                elif 'callback_query' in update_data:
                    update_type = "callback_query"
                elif 'inline_query' in update_data:
                    update_type = "inline_query"
                
                log_user_action(
                    user_id=0,
                    action="WEBHOOK_UPDATE_PARSED",
                    details=f"Type: {update_type}, UpdateID: {update_data.get('update_id', 'unknown')}",
                    correlation_id=correlation_id
                )
                
                # Пропуск неподдерживаемых типов
                if any(key in update_data for key in ['story', 'business_connection', 'business_message']):
                    log_user_action(
                        user_id=0,
                        action="WEBHOOK_UNSUPPORTED_TYPE",
                        details=f"Skipped unsupported update type",
                        correlation_id=correlation_id
                    )
                    metrics.increment('webhook.unsupported_type')
                    self.send_response(200)
                    self.end_headers()
                    return
                
                # Создание Telegram Update объекта
                update = telebot.types.Update.de_json(update_data)
                
                if update:
                    # Установка корреляционного ID в контекст для обработчиков
                    if hasattr(update, 'message') and update.message:
                        setattr(update.message, '_correlation_id', correlation_id)
                    elif hasattr(update, 'callback_query') and update.callback_query:
                        setattr(update.callback_query, '_correlation_id', correlation_id)
                    
                    # Обработка обновления
                    processing_start = time.time()
                    bot.process_new_updates([update])
                    processing_duration = round((time.time() - processing_start) * 1000, 2)
                    
                    total_duration = round((time.time() - start_time) * 1000, 2)
                    
                    log_user_action(
                        user_id=0,
                        action="WEBHOOK_UPDATE_PROCESSED",
                        details=f"Type: {update_type}, Processing: {processing_duration}ms, Total: {total_duration}ms",
                        correlation_id=correlation_id
                    )
                    
                    metrics.increment(f'webhook.processed.{update_type}')
                    metrics.timing('webhook.processing_duration', processing_duration)
                    metrics.timing('webhook.total_duration', total_duration)
                else:
                    log_user_action(
                        user_id=0,
                        action="WEBHOOK_UPDATE_NULL",
                        details="Failed to create Update object",
                        correlation_id=correlation_id
                    )
                    metrics.increment('webhook.update_null')
                
            except (ValueError, TypeError, json.JSONDecodeError) as parse_error:
                centralized_error_logger(
                    error=parse_error,
                    context=f"Webhook JSON parsing from {client_ip}",
                    correlation_id=correlation_id
                )
                metrics.increment('webhook.parse_error')
                
                # Возвращаем 200 чтобы Telegram не повторял запрос
                self.send_response(200)
                self.end_headers()
                return
            
            # Успешный ответ
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            
        except Exception as e:
            centralized_error_logger(
                error=e,
                context=f"Webhook processing from {client_ip}",
                correlation_id=correlation_id
            )
            metrics.increment('webhook.critical_error')
            
            self.send_response(500)
            self.end_headers()
    
    def _handle_health_check(self, correlation_id: str):
        """Health check endpoint оптимизированный для Render.com"""
        try:
            # Быстрые проверки системы
            health_data = {
                "status": "healthy",
                "service": "do-presave-reminder-bot",
                "version": "v24-bug-fixes",
                "timestamp": time.time(),
                "correlation_id": correlation_id
            }
            
            # Проверка базы данных
            try:
                with database_transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT 1')
                    db_healthy = cursor.fetchone() is not None
                health_data["database"] = "connected" if db_healthy else "error"
            except Exception as db_error:
                health_data["database"] = "error"
                health_data["database_error"] = str(db_error)
            
            # Проверка Telegram API
            try:
                bot_info = bot.get_me()
                health_data["telegram_api"] = "connected"
                health_data["bot_username"] = bot_info.username
            except Exception as api_error:
                health_data["telegram_api"] = "error"
                health_data["api_error"] = str(api_error)
            
            # Информация о скриншотах
            try:
                screenshots_count = db_manager.get_active_screenshots_count()
                health_data["screenshots"] = {
                    "active_count": screenshots_count,
                    "ttl_days": SCREENSHOT_TTL_DAYS
                }
            except Exception:
                health_data["screenshots"] = "error"
            
            # Статус бота
            try:
                health_data["bot_active"] = db_manager.is_bot_active()
                health_data["current_mode"] = get_current_limit_mode().value
                health_data["uptime"] = str(datetime.now() - bot_status["start_time"]).split('.')[0]
            except Exception:
                health_data["bot_status"] = "error"
            
            # Добавление метрик
            health_data["metrics"] = metrics.get_summary()
            
            log_user_action(
                user_id=0,
                action="HEALTH_CHECK",
                details=f"DB: {health_data.get('database', 'unknown')}, API: {health_data.get('telegram_api', 'unknown')}",
                correlation_id=correlation_id
            )
            
            status_code = 200 if health_data.get("database") == "connected" and health_data.get("telegram_api") == "connected" else 503
            
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_json = json.dumps(health_data, indent=2, ensure_ascii=False)
            self.wfile.write(response_json.encode('utf-8'))
            
            metrics.increment('health_check.success' if status_code == 200 else 'health_check.degraded')
            
        except Exception as e:
            centralized_error_logger(
                error=e,
                context="Health check",
                correlation_id=correlation_id
            )
            metrics.increment('health_check.error')
            
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            error_response = json.dumps({
                "status": "error",
                "error": str(e),
                "correlation_id": correlation_id
            })
            self.wfile.write(error_response.encode('utf-8'))
    
    def _handle_keepalive_request(self, correlation_id: str, client_ip: str):
        """Keep alive endpoint с детальной диагностикой для UptimeRobot"""
        try:
            log_user_action(
                user_id=0,
                action="KEEP_ALIVE_REQUEST",
                details=f"Client: {client_ip}",
                correlation_id=correlation_id,
                client_ip=client_ip
            )
            
            # Подробная проверка системы
            diagnostic_data = {
                "status": "alive",
                "timestamp": time.time(),
                "correlation_id": correlation_id,
                "client_ip": client_ip,
                "uptime_check": "✅ OK"
            }
            
            # Проверки компонентов
            checks = {}
            
            # База данных
            try:
                with database_transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) FROM users')
                    user_count = cursor.fetchone()[0]
                checks["database"] = {"status": "ok", "user_count": user_count}
            except Exception as e:
                checks["database"] = {"status": "error", "error": str(e)}
            
            # Telegram API
            try:
                bot_info = bot.get_me()
                checks["telegram_api"] = {"status": "ok", "bot_username": bot_info.username}
            except Exception as e:
                checks["telegram_api"] = {"status": "error", "error": str(e)}
            
            # Статус бота
            try:
                bot_active = db_manager.is_bot_active()
                current_limits = get_current_limit_mode()
                checks["bot_status"] = {"active": bot_active, "limit_mode": current_limits.value}
            except Exception as e:
                checks["bot_status"] = {"status": "error", "error": str(e)}
            
            # Проверка скриншотов
            try:
                screenshots_count = db_manager.get_active_screenshots_count()
                checks["screenshots"] = {"status": "ok", "count": screenshots_count}
            except Exception as e:
                checks["screenshots"] = {"status": "error", "error": str(e)}
            
            # Сессии пользователей
            try:
                checks["user_sessions"] = {
                    "status": "ok", 
                    "active_sessions": len(user_sessions),
                    "request_sessions": len(presave_request_sessions),
                    "claim_sessions": len(presave_claim_sessions)
                }
            except Exception as e:
                checks["user_sessions"] = {"status": "error", "error": str(e)}
            
            diagnostic_data["checks"] = checks
            diagnostic_data["metrics"] = metrics.get_summary()
            
            # Определение общего статуса
            all_systems_ok = all(
                check.get("status") == "ok" for check in checks.values() 
                if isinstance(check, dict) and "status" in check
            )
            
            status_code = 200 if all_systems_ok else 503
            diagnostic_data["service_status"] = "operational" if all_systems_ok else "degraded"
            
            log_user_action(
                user_id=0,
                action="KEEP_ALIVE_RESPONSE",
                details=f"Status: {diagnostic_data['service_status']}, Client: {client_ip}",
                correlation_id=correlation_id,
                client_ip=client_ip
            )
            
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_json = json.dumps(diagnostic_data, indent=2, ensure_ascii=False)
            self.wfile.write(response_json.encode('utf-8'))
            
            metrics.increment('keepalive.request.success' if status_code == 200 else 'keepalive.request.degraded')
            
        except Exception as e:
            centralized_error_logger(
                error=e,
                context=f"Keep alive request from {client_ip}",
                correlation_id=correlation_id
            )
            metrics.increment('keepalive.request.error')
            
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            error_response = json.dumps({
                "status": "error",
                "error": str(e),
                "correlation_id": correlation_id,
                "uptime_check": "❌ CRITICAL_ERROR"
            })
            self.wfile.write(error_response.encode('utf-8'))
    
    def _handle_metrics_request(self, correlation_id: str):
        """Endpoint для получения метрик производительности"""
        try:
            metrics_data = {
                "timestamp": time.time(),
                "correlation_id": correlation_id,
                "metrics": metrics.get_summary(),
                "active_sessions": {
                    "user_sessions": len(user_sessions),
                    "request_sessions": len(presave_request_sessions),
                    "claim_sessions": len(presave_claim_sessions)
                },
                "database_stats": {
                    "active_screenshots": db_manager.get_active_screenshots_count()
                }
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_json = json.dumps(metrics_data, indent=2)
            self.wfile.write(response_json.encode('utf-8'))
            
            log_user_action(
                user_id=0,
                action="METRICS_REQUEST",
                details=f"Metrics delivered",
                correlation_id=correlation_id
            )
            
        except Exception as e:
            centralized_error_logger(
                error=e,
                context="Metrics request",
                correlation_id=correlation_id
            )
            
            self.send_response(500)
            self.end_headers()
    
    def _handle_webhook_info_page(self, correlation_id: str):
        """Информационная страница webhook"""
        try:
            info_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Do Presave Reminder Bot by Mister DMS v24 - Bug Fixes</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                    .status {{ background: #E8F5E8; padding: 15px; border-radius: 8px; }}
                    .metrics {{ background: #F0F8FF; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                    .feature {{ background: #FFF8DC; padding: 10px; border-radius: 5px; margin: 5px 0; }}
                </style>
            </head>
            <body>
                <h1>🤖 Do Presave Reminder Bot by Mister DMS v24</h1>
                <div class="status">
                    <h3>✅ Production Ready - Bug Fixes</h3>
                    <p>Advanced logging and monitoring active</p>
                    <p>Correlation ID: {correlation_id}</p>
                </div>
                <div class="feature">
                    <h4>🆕 v24 Features:</h4>
                    <p>📸 Screenshot support with 7-day TTL</p>
                    <p>🎵 Clear terminology: Request vs Claim</p>
                    <p>📊 Enhanced analytics and metrics</p>
                    <p>🔒 Improved security and rate limiting</p>
                </div>
                <div class="metrics">
                    <h4>📊 Real-time Monitoring</h4>
                    <p><a href="/metrics">View Metrics</a></p>
                    <p><a href="/health">Health Check</a></p>
                    <p><a href="/keepalive">Keep Alive</a></p>
                </div>
            </body>
            </html>
            """
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(info_html.encode('utf-8'))
            
        except Exception as e:
            centralized_error_logger(
                error=e,
                context="Webhook info page",
                correlation_id=correlation_id
            )
            self.send_response(500)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Отключаем стандартное логирование HTTP сервера - используем свое"""
        pass

def check_database_connection() -> bool:
    """Проверка подключения к базе данных"""
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            return cursor.fetchone() is not None
    except Exception:
        return False

# ================================
# 14. ЗАПУСК БОТА
# ================================

def main():
    """
    Основная функция запуска с поддержкой скриншотов
    1. Валидация переменных окружения
    2. Инициализация базы данных
    3. Установка webhook
    4. Запуск keep-alive потока  
    5. Запуск HTTP сервера
    """
    try:
        # Валидация обязательных переменных
        missing_vars = [var for var in REQUIRED_VARS if not os.getenv(var)]
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {missing_vars}")
            return
        
        # Дополнительная валидация критичных переменных
        try:
            group_id_test = int(os.getenv("GROUP_ID", "0"))
            thread_id_test = int(os.getenv("THREAD_ID", "0"))
            
            if group_id_test == 0 or thread_id_test == 0:
                logger.error("❌ GROUP_ID and THREAD_ID must be non-zero")
                return
            
            logger.info(f"✅ Target validation: Group {group_id_test}, Thread {thread_id_test}")
            logger.info(f"🎯 Target URL: https://t.me/c/{abs(group_id_test)}/{thread_id_test}")
            
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Invalid GROUP_ID or THREAD_ID format: {e}")
            return
        
        logger.info("🚀 Starting Do Presave Reminder Bot by Mister DMS v24 - Bug Fixes")
        logger.info("📸 Screenshot support enabled with 7-day TTL")
        logger.info("🎵 Clear terminology: Request (просьба) vs Claim (заявка)")
        logger.info(f"🔧 Admin IDs: {ADMIN_IDS}")
        logger.info(f"📊 Target Group: {GROUP_ID}, Target Thread: {THREAD_ID}")
        logger.info(f"🎯 Bot will work ONLY in:  https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID} and private chats")
        logger.info(f"⚙️ Environment variables: GROUP_ID={os.getenv('GROUP_ID')}, THREAD_ID={os.getenv('THREAD_ID')}")
        
        # Инициализация БД с поддержкой скриншотов
        db_manager.create_tables()
        logger.info("✅ Database initialized with screenshot support")
        
        # Установка webhook
        render_url = os.getenv('RENDER_EXTERNAL_URL')
        port = int(os.getenv('PORT', 5000))

        if not render_url:
            # Попытка автоматического определения URL для Render.com
            service_name = os.getenv('RENDER_SERVICE_NAME')
            if service_name:
                render_url = f"{service_name}.onrender.com"
                logger.info(f"🔧 Auto-detected Render URL: {render_url}")
            else:
                logger.error("❌ Не удалось определить URL автоматически")
                logger.error("❌ RENDER_EXTERNAL_URL не установлен и не удалось автоматически определить URL")
                logger.error("📝 Установите переменную окружения RENDER_EXTERNAL_URL в Render Dashboard")
                logger.error("💡 Пример: your-service-name.onrender.com")
                
                # Fallback на polling mode для локальной разработки
                logger.info("🔄 Переключаемся на polling mode...")
                start_polling_mode()
                return

        webhook_url = f"https://{clean_url(render_url)}/{BOT_TOKEN}"
        
        # Дополнительная валидация очищенного URL
        cleaned_url = clean_url(render_url)
        if not cleaned_url or '://' in cleaned_url:
            logger.error(f"❌ Invalid URL after cleaning: {cleaned_url}")
            logger.error("💡 RENDER_EXTERNAL_URL должен быть: domain.com (без протокола)")
            return

        # Валидация webhook URL
        if not webhook_url.startswith('https://'):
            logger.error("❌ Webhook URL must use HTTPS")
            return

        if len(webhook_url) > 2048:
            logger.error("❌ Webhook URL too long (max 2048 characters)")
            return

        # Проверка доступности URL (опционально)
        try:
            import urllib.request
            test_url = f"https://{clean_url(render_url)}/health"
            urllib.request.urlopen(test_url, timeout=5)
            logger.info(f"✅ Service URL is accessible: {test_url}")
        except Exception as url_check_error:
            logger.warning(f"⚠️ Could not verify URL accessibility: {url_check_error}")
            logger.warning("🔄 Proceeding with webhook setup anyway...")
        
        try:
            logger.info(f"🔧 Setting up webhook: {webhook_url}")
            logger.info(f"🌐 Cleaned URL: {clean_url(render_url)}")
            logger.info(f"🔑 Secret token: {'configured' if WEBHOOK_SECRET != 'your_secret' else 'not set'}")
            
            webhook_set = bot.set_webhook(
                webhook_url, 
                secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET != "your_secret" else None
            )
            
            if webhook_set:
                logger.info(f"✅ Webhook successfully set: {webhook_url}")
                if WEBHOOK_SECRET != "your_secret":
                    logger.info("🔒 Secret token configured for webhook security")
            else:
                logger.error("❌ Failed to set webhook - Telegram API returned False")
                logger.error("💡 Check if the URL is accessible from internet")
                return
                
        except Exception as webhook_error:
            logger.error(f"❌ Webhook setup failed: {webhook_error}")
            logger.error(f"🔗 Attempted URL: {webhook_url}")
            logger.error("📝 Проверьте:")
            logger.error("   1. RENDER_EXTERNAL_URL установлен правильно")
            logger.error("   2. URL доступен из интернета")
            logger.error("   3. URL использует HTTPS")
            return
        
        # Запуск фоновых процессов
        logger.info("🔄 Starting background processes...")
        
        keep_alive_thread = threading.Thread(target=keep_alive_worker, daemon=True)
        keep_alive_thread.start()
        logger.info("💓 Keep-alive worker started")
        
        # Стартовая очистка просроченных данных
        try:
            cleanup_expired_sessions()
            cleanup_expired_screenshots()
            db_manager.cleanup_expired_screenshots()
            logger.info("🧹 Initial cleanup completed")
        except Exception as cleanup_error:
            logger.warning(f"⚠️ Initial cleanup warning: {cleanup_error}")
        
        # Установка начальных настроек
        try:
            # Устанавливаем напоминание если не задано
            current_reminder = db_manager.get_setting('reminder_text')
            logger.info(f"🔧 Current reminder setting: {current_reminder}")
            if not current_reminder:
                db_manager.update_setting('reminder_text', REMINDER_TEXT)
                logger.info(f"📝 Set default reminder: {REMINDER_TEXT[:50]}...")
            
            # Устанавливаем режим лимитов по умолчанию
            current_mode = db_manager.get_setting('limit_mode')
            logger.info(f"🎛️ Current limit mode: {current_mode}")
            if not current_mode:
                db_manager.update_setting('limit_mode', LimitMode.NORMAL.value)
                logger.info(f"⚙️ Set default limit mode: {LimitMode.NORMAL.value}")
            
            # Устанавливаем активность бота
            bot_active = db_manager.get_setting('bot_active')
            logger.info(f"🤖 Bot active setting: {bot_active}")
            if not bot_active:
                db_manager.update_setting('bot_active', 'true')
                logger.info("✅ Set bot active: true")
                
            logger.info("⚙️ Initial settings configured")
        except Exception as settings_error:
            logger.error(f"❌ Settings configuration failed: {settings_error}")
            centralized_error_logger(
                error=settings_error,
                context="Initial settings configuration"
            )
            logger.warning(f"⚠️ Bot will continue with default settings")
        
        # Запуск HTTP сервера
        port = int(os.getenv('PORT', 5000))
        
        logger.info("📡 Using standard http.server for webhook handling")
        start_http_server(port)
            
    except Exception as e:
        logger.error(f"🚨 Bot startup failed: {str(e)}")
        centralized_error_logger(
            error=e,
            context="Bot startup"
        )
        raise

def start_polling_mode():
    """
    Запуск бота в режиме polling (для локальной разработки или fallback)
    """
    try:
        logger.info("🔄 Starting bot in polling mode")
        logger.info("⚠️ This mode is for development only")
        
        # Удаляем webhook если он был установлен
        try:
            bot.remove_webhook()
            logger.info("✅ Webhook removed, switching to polling")
        except Exception as e:
            logger.warning(f"⚠️ Could not remove webhook: {e}")
        
        # Запуск keep-alive в отдельном потоке
        keep_alive_thread = threading.Thread(target=keep_alive_worker, daemon=True)
        keep_alive_thread.start()
        logger.info("💓 Keep-alive worker started")
        
        # Стартовая очистка
        cleanup_expired_sessions()
        cleanup_expired_screenshots()
        db_manager.cleanup_expired_screenshots()
        logger.info("🧹 Initial cleanup completed")
        
        # Запуск polling
        logger.info("🤖 Bot is now running in polling mode...")
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
        
    except Exception as e:
        logger.error(f"🚨 Polling mode failed: {e}")
        centralized_error_logger(error=e, context="Polling mode startup")
        raise

def start_http_server(port: int):
    """
    HTTP сервер используя стандартную библиотеку
    Работает без дополнительных зависимостей (только requirements.txt)
    """
    try:
        logger.info(f"🌐 Starting HTTP server on port {port}")
        render_url = clean_url(os.getenv('RENDER_EXTERNAL_URL', ''))
        logger.info(f"📱 Webhook URL: https://{render_url}/{BOT_TOKEN}")
        logger.info(f"🔧 Health check: https://{render_url}/health")
        logger.info(f"💓 Keep alive: https://{render_url}/keepalive")
        logger.info(f"📊 Metrics: https://{render_url}/metrics")
        
        # Информация о боте
        try:
            bot_info = bot.get_me()
            logger.info(f"🤖 Bot info: @{bot_info.username} (ID: {bot_info.id})")
            logger.info(f"🎯 Target group: {GROUP_ID}, thread: {THREAD_ID}")
            logger.info(f"🔗 Expected thread URL: https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}")
            logger.info(f"⚠️ Bot will ONLY respond to commands in thread {THREAD_ID} of group {GROUP_ID}")
        except Exception as bot_info_error:
            logger.warning(f"⚠️ Could not get bot info: {bot_info_error}")
        
        with HTTPServer(('0.0.0.0', port), WebhookHandler) as httpd:
            logger.info("✅ HTTP server is ready and serving requests")
            logger.info("🎵 Bot is monitoring for external links in the target thread")
            logger.info("📸 Screenshot uploads enabled with 7-day TTL")
            logger.info("🔄 Automatic cleanup processes active")
            httpd.serve_forever()
            
    except Exception as e:
        logger.error(f"🚨 HTTP server failed: {e}")
        centralized_error_logger(
            error=e,
            context="HTTP server startup"
        )
        raise

if __name__ == "__main__":
    main()
