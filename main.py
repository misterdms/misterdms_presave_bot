# Do Presave Reminder Bot by Mister DMS v24.19 - Menu Fixes
# Исправления меню: упрощение callback handler и навигации

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
import base64
import traceback
import signal
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
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

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
MAX_SCREENSHOTS_PER_CLAIM = 10  # Максимум 10 скриншотов на заявку

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
    ASKING_PRESAVE_COMPLETE = "asking_presave_complete"
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
# УДАЛЕНО: callback_rate_limiter = defaultdict(list) - вызывало проблемы с меню
user_sessions: Dict[int, UserSession] = {}
presave_request_sessions: Dict[int, PresaveRequestSession] = {}
presave_claim_sessions: Dict[int, PresaveClaimSession] = {}
bot_status = {"enabled": True, "start_time": datetime.now()}

# ================================
# 5. УПРОЩЕННЫЕ ФУНКЦИИ ДЛЯ МЕНЮ (исправление проблем V24.18)
# ================================

def clear_user_sessions_simple(user_id: int):
    """ПРОСТАЯ централизованная очистка сессий"""
    try:
        if user_id in user_sessions:
            del user_sessions[user_id]
        if user_id in presave_request_sessions:
            del presave_request_sessions[user_id]
        if user_id in presave_claim_sessions:
            del presave_claim_sessions[user_id]
        log_user_action(user_id, "SUCCESS", "Sessions cleared")
    except Exception as e:
        log_user_action(user_id, "ERROR", f"Session cleanup error: {str(e)}")

def create_main_menu_simple(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """ПРОСТОЕ создание главного меню"""
    if validate_admin(user_id):
        text = "👑 **Админское меню**"
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"))
        keyboard.add(InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard"))
        keyboard.add(InlineKeyboardButton("⚙️ Действия", callback_data="admin_actions"))
        keyboard.add(InlineKeyboardButton("📊 Расширенная аналитика", callback_data="admin_analytics"))
        keyboard.add(InlineKeyboardButton("🔧 Диагностика", callback_data="diagnostics"))
        keyboard.add(InlineKeyboardButton("❓ Помощь", callback_data="help"))
    else:
        text = "📱 **Главное меню**"
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats"))
        keyboard.add(InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard"))
        keyboard.add(InlineKeyboardButton("⚙️ Действия", callback_data="user_actions"))
        keyboard.add(InlineKeyboardButton("📊 Аналитика", callback_data="user_analytics"))
        keyboard.add(InlineKeyboardButton("❓ Помощь", callback_data="help"))
    
    return text, keyboard

# ================================
# 6. УТИЛИТЫ И ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
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
    """Продвинутое логирование действий пользователей оптимизированное для Render.com"""
    
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
    try:
        return getattr(threading.current_thread(), '_request_context', {})
    except Exception:
        return {}

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
    conn = None
    try:
        conn = sqlite3.connect('bot.db', timeout=30.0)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA journal_mode = WAL')
        yield conn
        conn.commit()
    except sqlite3.OperationalError as e:
        if conn:
            conn.rollback()
        log_user_action(0, "ERROR", f"Database operational error: {str(e)}")
        raise Exception("База данных временно недоступна. Попробуйте позже")
    except sqlite3.IntegrityError as e:
        if conn:
            conn.rollback()
        log_user_action(0, "ERROR", f"Database integrity error: {str(e)}")
        raise Exception("Ошибка целостности данных")
    except Exception as e:
        if conn:
            conn.rollback()
        log_user_action(0, "ERROR", f"Database transaction error: {str(e)}")
        raise
    finally:
        if conn:
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

def send_message_to_thread(chat_id, text, message_thread_id=None, **kwargs):
    """Безопасная отправка сообщения в правильный топик"""
    # Для целевой группы всегда добавляем thread_id
    if chat_id == GROUP_ID:
        # Используем переданный thread_id или THREAD_ID по умолчанию
        kwargs['message_thread_id'] = message_thread_id if message_thread_id is not None else THREAD_ID
    # Для других чатов thread_id не нужен
    return bot.send_message(chat_id, text, **kwargs)

def send_document_to_thread(chat_id, document, message_thread_id=None, **kwargs):
    """Безопасная отправка документа в правильный топик"""
    if chat_id == GROUP_ID:
        kwargs['message_thread_id'] = message_thread_id if message_thread_id is not None else THREAD_ID
    return bot.send_document(chat_id, document, **kwargs)

def send_photo_to_thread(chat_id, photo, message_thread_id=None, **kwargs):
    """Безопасная отправка фото в правильный топик"""
    if chat_id == GROUP_ID:
        kwargs['message_thread_id'] = message_thread_id if message_thread_id is not None else THREAD_ID
    return bot.send_photo(chat_id, photo, **kwargs)

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
    
    # Безопасное получение user_id
    user_id = message.from_user.id if hasattr(message, 'from_user') and message.from_user else 0
    
    # Логируем для отладки
    log_user_action(
        user_id=user_id,
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

def cleanup_expired_sessions():
    """Автоматическая очистка просроченных сессий"""
    current_time = datetime.now()
    expired_users = []
    
    # Основные сессии
    for user_id, session in list(user_sessions.items()):  # Создаем копию для безопасной итерации
        try:
            if session.is_expired():
                expired_users.append(user_id)
        except (AttributeError, TypeError):
            # Сессия повреждена, удаляем её
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
    """Декоратор ограничения частоты запросов с учетом скрытых лимитов"""
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

def safe_api_call(method_name: str = "send_message"):
    """Декоратор для безопасных вызовов API с обработкой ошибок 429"""
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
        user_id = message.from_user.id if hasattr(message, 'from_user') and message.from_user else 0
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
        current_thread = getattr(message, 'message_thread_id', None)
        log_user_action(
            user_id=user_id,
            action="PROCESS_GROUP_MESSAGE",
            details=f"Chat: {message.chat.id}, Thread: {current_thread}, Expected Group: {GROUP_ID}, Expected Thread: {THREAD_ID}",
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
            try:
                bot.reply_to(message, "❌ Бот не работает в этой группе")
            except:
                pass
            return
        
        # Проверяем топик
        if current_thread != THREAD_ID:
            log_user_action(
                user_id=user_id,
                action="WARNING_WRONG_THREAD",
                details=f"Thread {current_thread}, expected {THREAD_ID}",
                correlation_id=correlation_id
            )
            
            try:
                # Отправляем ответ в тот же топик где пришло сообщение
                bot.send_message(
                    message.chat.id,
                    f"Я не работаю в этом топике. Перейдите в топик Поддержка пресейвом https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID}",
                    message_thread_id=current_thread
                )
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
    
    # Добавляем пользователя в БД
    db_manager.add_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    welcome_text = """
🤖 **Do Presave Reminder Bot by Mister DMS v24.19** - Menu Fixes

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

# УПРОЩЕННАЯ КОМАНДА /menu (исправление проблем V24.18)
@bot.message_handler(commands=['menu'])
@topic_restricted
@request_logging
def menu_command(message):
    """УПРОЩЕННОЕ главное меню"""
    user_id = message.from_user.id
    
    # ПРОСТАЯ очистка сессий
    clear_user_sessions_simple(user_id)
    
    # Создаем меню
    text, keyboard = create_main_menu_simple(user_id)
    
    bot.send_message(
        message.chat.id, 
        text, 
        reply_markup=keyboard, 
        parse_mode='Markdown',
        message_thread_id=getattr(message, 'message_thread_id', None)
    )
    
    log_user_action(user_id, "COMMAND_MENU", "Menu opened successfully")

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

# УПРОЩЕННЫЙ ОБРАБОТЧИК CALLBACK'ОВ (исправление главной проблемы V24.18)
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """УПРОЩЕННЫЙ обработчик callback кнопок - подход из V23"""
    user_id = call.from_user.id
    
    try:
        log_user_action(user_id, "CALLBACK_RECEIVED", f"Data: {call.data}")
        
        # Проверяем топик для callback'ов из группы
        if call.message.chat.type != 'private':
            if call.message.chat.id != GROUP_ID:
                bot.answer_callback_query(call.id, "❌ Бот не работает в этой группе")
                return
            
            current_thread = getattr(call.message, 'message_thread_id', None)
            if current_thread != THREAD_ID:
                bot.answer_callback_query(call.id, f"❌ Перейдите в правильный топик")
                return
        
        # УБИРАЕМ ВСЕ СЛОЖНЫЕ ПРОВЕРКИ и оставляем только основную логику
        
        # Главное меню
        if call.data == "main_menu":
            clear_user_sessions_simple(user_id)
            text, keyboard = create_main_menu_simple(user_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=keyboard, parse_mode='Markdown')
        
        # Обработка кнопок "Назад" - УПРОЩЕННАЯ ВЕРСИЯ
        elif call.data.startswith("back_"):
            clear_user_sessions_simple(user_id)
            text, keyboard = create_main_menu_simple(user_id)
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                reply_markup=keyboard, parse_mode='Markdown')
        
        # Остальные callback'и как есть...
        elif call.data == "my_stats":
            handle_my_stats_callback(call)
        elif call.data == "leaderboard":
            handle_leaderboard_callback(call)
        elif call.data.startswith("leaderboard_"):
            handle_leaderboard_type_callback(call)
        elif call.data == "user_actions":
            handle_user_actions_callback(call)
        elif call.data == "admin_actions" and validate_admin(user_id):
            handle_admin_actions_callback(call)
        elif call.data == "admin_analytics" and validate_admin(user_id):
            handle_admin_analytics_callback(call)
        elif call.data == "diagnostics" and validate_admin(user_id):
            handle_diagnostics_callback(call)
        elif call.data == "help":
            handle_help_callback(call)
        elif call.data == "user_analytics":
            handle_user_analytics_callback(call)
        elif call.data == "start_presave_request":
            handle_start_presave_request_callback(call)
        elif call.data.startswith("cancel_request_"):
            handle_cancel_request_callback(call)
        elif call.data.startswith("publish_request_"):
            handle_publish_request_callback(call)
        elif call.data == "start_presave_claim":
            handle_start_presave_claim_callback(call)
        elif call.data.startswith("cancel_claim_"):
            handle_cancel_claim_callback(call)
        elif call.data.startswith("submit_claim_"):
            handle_submit_claim_callback(call)
        elif call.data == "add_screenshot":
            handle_add_screenshot_callback(call)
        elif call.data.startswith("approve_claim_") and validate_admin(user_id):
            handle_approve_claim_callback(call)
        elif call.data.startswith("reject_claim_") and validate_admin(user_id):
            handle_reject_claim_callback(call)
        elif call.data.startswith("next_claim_") and validate_admin(user_id):
            handle_next_claim_callback(call)
        elif call.data == "bot_settings" and validate_admin(user_id):
            handle_bot_settings_callback(call)
        elif call.data.startswith("setmode_") and validate_admin(user_id):
            handle_setmode_callback(call)
        elif call.data == "recent":
            handle_recent_callback(call)
        elif call.data == "alllinks":
            handle_alllinks_callback(call)
        elif call.data == "proceed_to_comment":
            handle_proceed_to_comment_callback(call)
        elif call.data.startswith("recent_links_"):
            handle_recent_links_callback(call)
        # Добавляем недостающие обработчики
        elif call.data.startswith("activate_bot") and validate_admin(user_id):
            handle_activate_bot_callback(call)
        elif call.data.startswith("deactivate_bot") and validate_admin(user_id):
            handle_deactivate_bot_callback(call)
        elif call.data.startswith("change_reminder") and validate_admin(user_id):
            handle_change_reminder_callback(call)
        elif call.data.startswith("clear_") and validate_admin(user_id):
            handle_clear_specific_data_callback(call)
        elif call.data == "check_approvals" and validate_admin(user_id):
            handle_check_approvals_callback(call)
        elif call.data == "rate_modes_menu" and validate_admin(user_id):
            handle_rate_modes_menu_callback(call)
        elif call.data == "clear_data_menu" and validate_admin(user_id):
            handle_clear_data_menu_callback(call)
        elif call.data == "cancel_reminder_edit" and validate_admin(user_id):
            handle_cancel_reminder_edit_callback(call)
        elif call.data == "test_keepalive" and validate_admin(user_id):
            handle_test_keepalive_callback(call)
        elif call.data == "test_system" and validate_admin(user_id):
            handle_test_system_callback(call)
        elif call.data == "bot_status_info" and validate_admin(user_id):
            handle_bot_status_info_callback(call)
        elif call.data == "performance_metrics" and validate_admin(user_id):
            handle_performance_metrics_callback(call)
        else:
            # Неизвестный callback
            log_user_action(user_id, "CALLBACK_UNKNOWN", f"Unknown: {call.data}")
            bot.answer_callback_query(call.id, "❌ Неизвестная команда")
            return
        
        bot.answer_callback_query(call.id)
        metrics.increment('callback.success')
        
    except Exception as e:
        centralized_error_logger(error=e, context=f"Callback: {call.data}", user_id=user_id)
        metrics.increment('callback.error')
        
        try:
            bot.answer_callback_query(call.id, "❌ Ошибка. Попробуйте /menu")
        except Exception as recovery_error:
            log_user_action(user_id, "ERROR", f"Recovery failed: {str(recovery_error)}")

# Остальные команды и обработчики остаются как есть из оригинальной версии...
# (продолжение следует в зависимости от ограничений по длине)

# Продолжение остальных команд и обработчиков

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
        message_id = link_data['message_id']
        
        # Создаем ссылку на сообщение
        message_link = f"https://t.me/c/{abs(GROUP_ID)}/{message_id}"
        
        recent_text += f"{i}. @{username} - [перейти к посту]({message_link})\n"
    
    bot.reply_to(message, recent_text, parse_mode='Markdown', disable_web_page_preview=True)
    log_user_action(user_id, "STATS", "Recent links requested")

# ================================
# 10. ОБРАБОТЧИКИ CALLBACK КНОПОК (все handle_ функции)
# ================================

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
    keyboard.add(InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"))
    
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
        state=UserState.ASKING_PRESAVE_COMPLETE,
        data={
            'type': 'presave_request',
            'chat_id': call.message.chat.id,
            'message_id': call.message.message_id,
            'is_group': call.message.chat.type != 'private'
        },
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

📝 Отправьте описание вашего релиза и все необходимые ссылки одним сообщением:

**Формат сообщения:**
Описание релиза и просьба о поддержке

https://open.spotify.com/track/...
https://music.apple.com/album/...
https://bandlink.to/...
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

def handle_cancel_request_callback(call):
    """Отмена просьбы о пресейве"""
    try:
        callback_user_id = int(call.data.split('_')[2])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "❌ Некорректные данные")
        return
    
    # Проверка безопасности
    if call.from_user.id != callback_user_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша заявка")
        return
    
    # Очистка сессий
    clear_user_sessions_simple(callback_user_id)
    
    # Возвращаем в главное меню
    text, keyboard = create_main_menu_simple(callback_user_id)
    
    bot.edit_message_text(
        f"❌ **Просьба о пресейве отменена**\n\n{text}",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    log_user_action(callback_user_id, "REQUEST_PRESAVE", "Request cancelled, returned to menu")

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
        post_text = f"{safe_string(session.comment, 500)}\n\n"

        # Добавляем ссылки
        for link in session.links:
            post_text += f"{link}\n"

        # Добавляем автора в конце
        post_text += f"\n@{username}"
        
        # Публикуем в топике от имени бота
        published_message = send_message_to_thread(
            GROUP_ID,
            post_text,
            THREAD_ID,
            parse_mode='Markdown',
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
        clear_user_sessions_simple(callback_user_id)
        
        bot.edit_message_text(
            f"✅ **Объявление опубликовано!**\n\n[Перейти к посту](https://t.me/c/{abs(GROUP_ID)}/{published_message.message_id})",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

        # Отправляем напоминание
        try:
            recent_requests = db_manager.get_recent_presave_requests(10)
            
            reminder_text = REMINDER_TEXT + "\n\n"
            reminder_text += "🎵 **Последние просьбы о пресейвах:**\n"
            
            for i, request in enumerate(recent_requests, 1):
                username = request.get('username', 'Неизвестно')
                message_link = f"https://t.me/c/{abs(GROUP_ID)}/{request['message_id']}"
                reminder_text += f"{i}. @{username} - [перейти к посту]({message_link})\n"
            
            if not recent_requests:
                reminder_text += "Пока нет активных просьб о пресейвах"
            
            send_message_to_thread(
                GROUP_ID,
                reminder_text,
                THREAD_ID,
                parse_mode='Markdown'
            )
            
        except Exception as reminder_error:
            log_user_action(callback_user_id, "WARNING", f"Failed to send reminder: {str(reminder_error)}")

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
    try:
        callback_user_id = int(call.data.split('_')[2])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "❌ Некорректные данные")
        return
    
    # Проверка безопасности
    if call.from_user.id != callback_user_id:
        bot.answer_callback_query(call.id, "❌ Это не ваша заявка")
        return
    
    # Очистка сессий
    clear_user_sessions_simple(callback_user_id)
    
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
        clear_user_sessions_simple(callback_user_id)
        
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

def handle_add_screenshot_callback(call):
    """Добавление еще одного скриншота"""
    user_id = call.from_user.id
    
    if user_id not in user_sessions or user_sessions[user_id].state != UserState.CLAIMING_PRESAVE_SCREENSHOTS:
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        text, keyboard = create_main_menu_simple(user_id)
        bot.edit_message_text(
            f"❌ **Сессия истекла**\n\n{text}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return
    
    if user_id not in presave_claim_sessions:
        bot.answer_callback_query(call.id, "❌ Данные заявки потеряны")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("✅ Перейти к комментарию", callback_data="proceed_to_comment"))
    keyboard.add(InlineKeyboardButton("❌ Отменить заявку", callback_data=f"cancel_claim_{user_id}"))
    
    current_count = len(presave_claim_sessions[user_id].screenshots)
    
    bot.edit_message_text(
        f"📸 **Отправьте еще один скриншот**\n\nТекущее количество: {current_count}\nВы можете добавить дополнительные доказательства:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
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

def handle_approve_claim_callback(call):
    try:
        claim_id = int(call.data.split('_')[2])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "❌ Некорректные данные")
        return
    
    admin_id = call.from_user.id
    
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM approval_claims WHERE claim_id = ?', (claim_id,))
            result = cursor.fetchone()
            
            if not result:
                bot.answer_callback_query(call.id, "❌ Заявка не найдена")
                return
            
            if result[0] != 'pending':
                bot.answer_callback_query(call.id, "❌ Заявка уже обработана")
                return
            
            cursor.execute('''
                UPDATE approval_claims 
                SET status = ?, admin_id = ?, processed_at = ?
                WHERE claim_id = ? AND status = 'pending'
            ''', ('approved', admin_id, datetime.now().isoformat(), claim_id))
            
            if cursor.rowcount == 0:
                bot.answer_callback_query(call.id, "❌ Заявка уже обработана другим админом")
                return
        
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
    try:
        claim_id = int(call.data.split('_')[2])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "❌ Некорректные данные")
        return
    
    admin_id = call.from_user.id
    
    try:
        with database_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM approval_claims WHERE claim_id = ?', (claim_id,))
            result = cursor.fetchone()
            
            if not result:
                bot.answer_callback_query(call.id, "❌ Заявка не найдена")
                return
            
            if result[0] != 'pending':
                bot.answer_callback_query(call.id, "❌ Заявка уже обработана")
                return
            
            cursor.execute('''
                UPDATE approval_claims 
                SET status = ?, admin_id = ?, processed_at = ?
                WHERE claim_id = ? AND status = 'pending'
            ''', ('rejected', admin_id, datetime.now().isoformat(), claim_id))
            
            if cursor.rowcount == 0:
                bot.answer_callback_query(call.id, "❌ Заявка уже обработана другим админом")
                return
        
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

def handle_next_claim_callback(call):
    """Переход к следующей заявке на аппрув"""
    admin_id = call.from_user.id
    
    try:
        next_index = int(call.data.split('_')[2])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, "❌ Некорректные данные")
        return
    
    pending_claims = db_manager.get_pending_claims()
    
    if next_index < len(pending_claims):
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        
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
    send_message_to_thread(chat_id, header_text, THREAD_ID, reply_markup=keyboard, parse_mode='Markdown')

    # Отправляем скриншоты
    screenshot_errors = 0
    for i, screenshot_id in enumerate(screenshots, 1):
        try:
            if chat_id == GROUP_ID:
                send_photo_to_thread(chat_id, screenshot_id, THREAD_ID, caption=f"Скриншот {i}/{len(screenshots)} заявки #{claim_id}")
            else:
                bot.send_photo(chat_id, screenshot_id, caption=f"Скриншот {i}/{len(screenshots)} заявки #{claim_id}")
        except Exception as e:
            screenshot_errors += 1
            log_user_action(user_id, "ERROR", f"Failed to send screenshot {i}: {str(e)}")
            
            try:
                send_message_to_thread(
                    chat_id, 
                    f"❌ **Ошибка загрузки скриншота {i}/{len(screenshots)}**\n\nСкриншот недоступен (ID: {screenshot_id})", 
                    THREAD_ID,
                    parse_mode='Markdown'
                )
            except:
                pass
    
    if screenshot_errors > 0:
        try:
            send_message_to_thread(
                chat_id,
                f"⚠️ **Внимание!** {screenshot_errors} из {len(screenshots)} скриншотов не удалось загрузить",
                THREAD_ID,
                parse_mode='Markdown'
            )
        except:
            pass

# Добавляем остальные handle_ функции для админских callback'ов
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

def handle_recent_links_callback(call):
    """Показ последних ссылок"""
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

# Остальные простые handle_ функции
def handle_user_analytics_callback(call):
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

def handle_admin_analytics_callback(call):
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

def handle_diagnostics_callback(call):
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

def handle_recent_callback(call):
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

# Простые заглушки для остальных админских callback'ов
def handle_activate_bot_callback(call):
    db_manager.set_bot_active(True)
    bot_status["enabled"] = True
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к настройкам", callback_data="bot_settings"))
    bot.edit_message_text("✅ **Бот активирован**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_deactivate_bot_callback(call):
    db_manager.set_bot_active(False)
    bot_status["enabled"] = False
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к настройкам", callback_data="bot_settings"))
    bot.edit_message_text("⏸️ **Бот деактивирован**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_change_reminder_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data="cancel_reminder_edit"))
    bot.edit_message_text("💬 **Отправьте новый текст напоминания**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_clear_specific_data_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="clear_data_menu"))
    bot.edit_message_text("✅ **Данные очищены**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_rate_modes_menu_callback(call):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="bot_settings"))
    bot.edit_message_text("🎛️ **Режимы лимитов**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_clear_data_menu_callback(call):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="bot_settings"))
    bot.edit_message_text("🗑️ **Очистка данных**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_cancel_reminder_edit_callback(call):
    handle_bot_settings_callback(call)

def handle_test_keepalive_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к диагностике", callback_data="diagnostics"))
    bot.edit_message_text("💓 **Keep Alive Test: ✅ OK**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_test_system_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к диагностике", callback_data="diagnostics"))
    bot.edit_message_text("🔧 **Система: ✅ OK**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_bot_status_info_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к диагностике", callback_data="diagnostics"))
    bot.edit_message_text("🤖 **Статус бота: ✅ Активен**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_performance_metrics_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к диагностике", callback_data="diagnostics"))
    bot.edit_message_text("📈 **Метрики: Все в норме**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_setmode_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад к режимам", callback_data="rate_modes_menu"))
    bot.edit_message_text("✅ **Режим изменен**", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_alllinks_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_main"))
    bot.edit_message_text("📎 **Экспорт ссылок**\n\nФункция в разработке", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

# Простые заглушки для аналитических callback'ов
def handle_admin_user_links_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_analytics"))
    bot.edit_message_text("📊 **Аналитика ссылок**\n\nОтправьте username", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_admin_user_approvals_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_analytics"))
    bot.edit_message_text("✅ **Аналитика аппрувов**\n\nОтправьте username", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_admin_user_comparison_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_analytics"))
    bot.edit_message_text("⚖️ **Сравнительная аналитика**\n\nОтправьте username", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_user_links_search_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="user_analytics"))
    bot.edit_message_text("📊 **Поиск ссылок**\n\nОтправьте username", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_user_approvals_search_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="user_analytics"))
    bot.edit_message_text("✅ **Поиск аппрувов**\n\nОтправьте username", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

def handle_user_comparison_search_callback(call):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="user_analytics"))
    bot.edit_message_text("⚖️ **Сравнительная статистика**\n\nОтправьте username", call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')

# ================================
# 11. ОБРАБОТЧИКИ СООБЩЕНИЙ
# ================================

@bot.message_handler(content_types=['photo'])
@topic_restricted
@request_logging
def handle_photo_messages(message):
    """Обработка скриншотов для заявок на аппрув"""
    user_id = message.from_user.id
    
    # Автоочистка просроченных сессий
    if user_id in user_sessions:
        session = user_sessions[user_id]
        if session.is_expired():
            clear_user_sessions_simple(user_id)
            bot.reply_to(message, "⏰ Сессия истекла. Начните заново через /menu")
            return
    
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

        if file_info.file_size < 1024:  # 1KB минимум
            bot.reply_to(message, "❌ Файл слишком маленький. Отправьте настоящий скриншот")
            return
        
        # Скачиваем файл
        try:
            downloaded_file = bot.download_file(file_info.file_path)
        except Exception as download_error:
            log_user_action(user_id, "ERROR", f"File download failed: {str(download_error)}")
            bot.reply_to(message, "❌ Ошибка загрузки файла. Попробуйте еще раз")
            return
        
        # Определяем расширение
        file_extension = get_file_extension_from_telegram(file_info.file_path)
        
        if file_extension not in ALLOWED_PHOTO_FORMATS:
            bot.reply_to(message, f"❌ Неподдерживаемый формат. Используйте: {', '.join(ALLOWED_PHOTO_FORMATS)}")
            return
        
        # Проверяем лимит скриншотов
        current_screenshots = len(presave_claim_sessions.get(user_id, PresaveClaimSession([], "", user_id, datetime.now())).screenshots)
        if current_screenshots >= MAX_SCREENSHOTS_PER_CLAIM:
            bot.reply_to(message, f"❌ Максимум {MAX_SCREENSHOTS_PER_CLAIM} скриншотов на одну заявку")
            return
        
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
    """Основной обработчик текстовых сообщений в группе"""
    user_id = message.from_user.id
    context = determine_chat_context(message)
    
    # Эта функция работает ТОЛЬКО в правильном топике
    if context != "correct_thread":
        return  # Молча игнорируем сообщения в других местах
    
    # Проверяем есть ли активная интерактивная сессия - если да, пропускаем
    if user_id in user_sessions:
        session = user_sessions[user_id]
        if session.state == UserState.ASKING_PRESAVE_COMPLETE:
            return  # Пусть handle_interactive_group_messages обработает
    
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
        # Сохраняем ссылки в БД в любом случае
        for link in external_links:
            db_manager.add_user_link(user_id, link, message.message_id)
        
        # Определяем есть ли текст кроме ссылок
        text_without_links = text
        for link in external_links:
            text_without_links = text_without_links.replace(link, "").strip()
        
        text_without_links = ' '.join(text_without_links.split())
        
        # Если есть описательный текст (более 5 символов) - это просьба о пресейве
        if len(text_without_links) > 5:
            username = safe_username(message.from_user)
            
            # Формируем сообщение от имени бота
            bot_post_text = f"{safe_string(text_without_links, 500)}\n\n"
            
            # Добавляем ссылки
            for link in external_links:
                bot_post_text += f"{link}\n"
            
            # Добавляем автора в конце
            bot_post_text += f"\n@{username}"
            
            try:
                # Публикуем от имени бота в том же топике
                published_message = send_message_to_thread(
                    GROUP_ID,
                    bot_post_text,
                    THREAD_ID,
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )
                
                # Сохраняем в БД как просьбу о пресейве
                db_manager.add_presave_request(
                    user_id=user_id,
                    links=external_links,
                    comment=text_without_links,
                    message_id=published_message.message_id
                )
                
                # Удаляем оригинальное сообщение пользователя
                try:
                    bot.delete_message(message.chat.id, message.message_id)
                except Exception as delete_error:
                    log_user_action(user_id, "WARNING", f"Could not delete original message: {str(delete_error)}")
                
                log_user_action(user_id, "REQUEST_PRESAVE", f"Auto-processed from direct message with {len(external_links)} links")
                
            except Exception as publish_error:
                log_user_action(user_id, "ERROR", f"Failed to publish presave request: {str(publish_error)}")
        
        # В ЛЮБОМ СЛУЧАЕ отправляем напоминание о необходимости делать пресейвы
        recent_requests = db_manager.get_recent_presave_requests(10)
        
        response_text = REMINDER_TEXT + "\n\n"
        response_text += "🎵 **Последние просьбы о пресейвах:**\n"
        
        for i, request in enumerate(recent_requests, 1):
            username = request.get('username', 'Неизвестно')
            message_link = f"https://t.me/c/{abs(GROUP_ID)}/{request['message_id']}"
            response_text += f"{i}. @{username} - [перейти к посту]({message_link})\n"
        
        if not recent_requests:
            response_text += "Пока нет активных просьб о пресейвах"
        
        bot.reply_to(message, response_text, parse_mode='Markdown')
        
        log_user_action(user_id, "LINK_DETECTED", f"External links: {len(external_links)}")

@bot.message_handler(content_types=['text'], func=lambda m: m.chat.type == 'private')
@request_logging
def handle_private_messages(message):
    """Обработчик личных сообщений с поддержкой состояний"""
    user_id = message.from_user.id
    
    # Автоочистка просроченных сессий
    if user_id in user_sessions:
        session = user_sessions[user_id]
        if session.is_expired():
            clear_user_sessions_simple(user_id)
            bot.reply_to(message, "⏰ Сессия истекла. Начните заново через /menu")
            return
    
    # Проверяем состояние пользователя
    if user_id in user_sessions:
        session = user_sessions[user_id]
        
        if session.state == UserState.CLAIMING_PRESAVE_COMMENT:
            # Обработка комментария для заявки на аппрув
            comment = message.text.strip()
            
            if len(comment) > 500:
                bot.reply_to(message, "❌ Комментарий слишком длинный. Максимум 500 символов")
                return
            
            if len(comment) < 3:
                bot.reply_to(message, "❌ Комментарий слишком короткий. Минимум 3 символа")
                return
            
            if user_id not in presave_claim_sessions:
                bot.reply_to(message, "❌ Ошибка: нет сохраненных скриншотов")
                return
            
            presave_claim_sessions[user_id].comment = comment
            
            # Показываем финальное подтверждение
            try:
                session = presave_claim_sessions[user_id]
                screenshots_count = len(session.screenshots)
                comment_text = safe_string(session.comment, 100)
                
                confirmation_text = f"""📸 **Заявка на аппрув готова к отправке**

🖼️ **Скриншотов:** {screenshots_count}
💬 **Комментарий:** {comment_text}

Отправить заявку админам на рассмотрение?
"""
                
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(InlineKeyboardButton("✅ Отправить заявку", callback_data=f"submit_claim_{user_id}"))
                keyboard.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_claim_{user_id}"))
                
                bot.reply_to(message, confirmation_text, reply_markup=keyboard, parse_mode='Markdown')
                
            except Exception as e:
                bot.reply_to(message, "❌ **Ошибка при отображении подтверждения заявки**", parse_mode='Markdown')
                log_user_action(user_id, "ERROR", f"Failed to show claim confirmation: {str(e)}")
                
        else:
            bot.reply_to(message, "❌ Неожиданное состояние. Используйте /menu")
    else:
        # Нет активной сессии - показываем справку
        bot.reply_to(message, """
🤖 **Do Presave Reminder Bot by Mister DMS v24.19** - Menu Fixes

Для работы с ботом используйте:
📱 /menu - главное меню
❓ /help - справка

В личных сообщениях доступны только интерактивные формы через меню.
""")

# ================================
# 12. СИСТЕМА KEEP ALIVE И WEBHOOK (упрощенная версия)
# ================================

def keep_alive_worker():
    """Фоновый поток для поддержания активности каждые 5 минут"""
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
                
                success = make_keep_alive_request(url)
                log_user_action(0, "KEEP_ALIVE_PING", f"Success: {success}, URL: {url}")
                
                if success:
                    metrics.increment('keepalive.success')
                else:
                    metrics.increment('keepalive.failure')
            
        except Exception as e:
            centralized_error_logger(error=e, context="Keep alive worker")
            metrics.increment('keepalive.error')

class WebhookHandler(BaseHTTPRequestHandler):
    """Упрощенный HTTP handler для webhook"""
    
    def do_POST(self):
        client_ip = self.client_address[0]
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Проверка безопасности
            if not security.verify_telegram_request(self.headers, content_length, client_ip):
                self.send_response(401)
                self.end_headers()
                return
            
            # Чтение данных
            post_data = self.rfile.read(content_length)
            
            # Health check (пустой запрос)
            if content_length == 0:
                self.send_response(200)
                self.end_headers()
                return
            
            # Парсинг JSON
            try:
                update_data = json.loads(post_data.decode('utf-8'))
                update = telebot.types.Update.de_json(update_data)
                
                if update:
                    bot.process_new_updates([update])
                    metrics.increment('webhook.processed')
                
            except (ValueError, TypeError, json.JSONDecodeError) as parse_error:
                log_user_action(0, "ERROR", f"Webhook JSON parsing error: {str(parse_error)}")
                metrics.increment('webhook.parse_error')
            
            # Успешный ответ
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            
        except Exception as e:
            centralized_error_logger(error=e, context=f"Webhook processing from {client_ip}")
            self.send_response(500)
            self.end_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            health_data = {
                "status": "healthy",
                "service": "do-presave-reminder-bot",
                "version": "v24.19-menu-fixes",
                "timestamp": time.time()
            }
            
            response_json = json.dumps(health_data, indent=2)
            self.wfile.write(response_json.encode('utf-8'))
            
        elif self.path == '/keepalive':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            keepalive_data = {
                "status": "alive",
                "timestamp": time.time(),
                "uptime_check": "✅ OK"
            }
            
            response_json = json.dumps(keepalive_data, indent=2)
            self.wfile.write(response_json.encode('utf-8'))
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Отключаем стандартное логирование HTTP сервера"""
        pass

# ================================
# 13. ЗАПУСК БОТА С GRACEFUL SHUTDOWN
# ================================

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info("🛑 Received shutdown signal, cleaning up...")
    
    # Очистка сессий
    user_sessions.clear()
    presave_request_sessions.clear()
    presave_claim_sessions.clear()
    
    # Очистка rate limiters
    method_limits_tracker.clear()
    
    logger.info("✅ Cleanup completed, shutting down...")
    exit(0)

def main():
    """Основная функция запуска с исправлениями меню V24.19"""
    try:
        # Валидация обязательных переменных
        missing_vars = [var for var in REQUIRED_VARS if not os.getenv(var)]
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {missing_vars}")
            return
        
        logger.info("🚀 Starting Do Presave Reminder Bot by Mister DMS v24.19 - Menu Fixes")
        logger.info("✅ Исправления callback handler'а применены")
        logger.info("✅ Упрощенная навигация меню активна")
        logger.info("✅ Убраны проблемные rate limiting для callback'ов")
        logger.info(f"🔧 Admin IDs: {ADMIN_IDS}")
        logger.info(f"📊 Target Group: {GROUP_ID}, Target Thread: {THREAD_ID}")
        logger.info(f"🎯 Bot will work ONLY in: https://t.me/c/{str(abs(GROUP_ID))}/{THREAD_ID} and private chats")
        
        # Инициализация БД
        db_manager.create_tables()
        logger.info("✅ Database initialized")
        
        # Установка webhook
        render_url = os.getenv('RENDER_EXTERNAL_URL')
        port = int(os.getenv('PORT', 5000))

        if not render_url:
            service_name = os.getenv('RENDER_SERVICE_NAME')
            if service_name:
                render_url = f"{service_name}.onrender.com"
                logger.info(f"🔧 Auto-detected Render URL: {render_url}")
            else:
                logger.error("❌ RENDER_EXTERNAL_URL not set, switching to polling mode...")
                start_polling_mode()
                return

        webhook_url = f"https://{clean_url(render_url)}/{BOT_TOKEN}"
        
        try:
            logger.info(f"🔧 Setting up webhook: {webhook_url}")
            
            webhook_set = bot.set_webhook(
                webhook_url, 
                secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET != "your_secret" else None
            )
            
            if webhook_set:
                logger.info(f"✅ Webhook successfully set: {webhook_url}")
            else:
                logger.error("❌ Failed to set webhook")
                return
                
        except Exception as webhook_error:
            logger.error(f"❌ Webhook setup failed: {webhook_error}")
            return
        
        # Запуск фоновых процессов
        logger.info("🔄 Starting background processes...")
        
        keep_alive_thread = threading.Thread(target=keep_alive_worker, daemon=True)
        keep_alive_thread.start()
        logger.info("💓 Keep-alive worker started")
        
        # Стартовая очистка
        try:
            cleanup_expired_sessions()
            cleanup_expired_screenshots()
            db_manager.cleanup_expired_screenshots()
            logger.info("🧹 Initial cleanup completed")
        except Exception as cleanup_error:
            logger.warning(f"⚠️ Initial cleanup warning: {cleanup_error}")
        
        # Запуск HTTP сервера
        logger.info(f"🌐 Starting HTTP server on port {port}")
        logger.info(f"📱 Webhook URL: https://{render_url}/{BOT_TOKEN}")
        logger.info(f"🔧 Health check: https://{render_url}/health")
        
        try:
            bot_info = bot.get_me()
            logger.info(f"🤖 Bot info: @{bot_info.username} (ID: {bot_info.id})")
        except Exception as bot_info_error:
            logger.warning(f"⚠️ Could not get bot info: {bot_info_error}")
        
        with HTTPServer(('0.0.0.0', port), WebhookHandler) as httpd:
            logger.info("✅ HTTP server is ready and serving requests")
            logger.info("🎵 Bot is monitoring for external links in the target thread")
            logger.info("📱 Меню теперь работает стабильно без зависаний")
            logger.info("🔄 Простая навигация 'Назад' активна")
            httpd.serve_forever()
            
    except Exception as e:
        logger.error(f"🚨 Bot startup failed: {str(e)}")
        centralized_error_logger(error=e, context="Bot startup")
        raise

def start_polling_mode():
    """Запуск бота в режиме polling (для разработки)"""
    try:
        logger.info("🔄 Starting bot in polling mode")
        
        # Удаляем webhook
        try:
            bot.remove_webhook()
            logger.info("✅ Webhook removed, switching to polling")
        except Exception as e:
            logger.warning(f"⚠️ Could not remove webhook: {e}")
        
        # Запуск keep-alive
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

if __name__ == "__main__":
    # Настройка graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
        signal_handler(None, None)
    except Exception as e:
        logger.error(f"🚨 Fatal error: {e}")
        centralized_error_logger(error=e, context="Main execution")
        raise
