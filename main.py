# Current version: v21-fixed
# Presave Reminder Bot - Версия с исправлениями безопасности и критических багов
# Основано на стабильной v20, добавлены критические исправления + фикс webhook security для production

import logging
import re
import sqlite3
import time
import threading
import os
import json
import urllib.parse
import hmac
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
from collections import defaultdict
from contextlib import contextmanager
from queue import Queue

import telebot
from telebot import types
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))  # -1002811959953
THREAD_ID = int(os.getenv('THREAD_ID'))  # 3
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
DEFAULT_REMINDER = os.getenv('REMINDER_TEXT', '🎧 Напоминаем: не забудьте сделать пресейв артистов выше! ♥️')

# === НОВЫЕ НАСТРОЙКИ БЕЗОПАСНОСТИ v21 ===
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', None)
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
WEBHOOK_RATE_LIMIT = int(os.getenv('WEBHOOK_RATE_LIMIT', '100'))

# === ИСПРАВЛЕННАЯ СИСТЕМА РЕЖИМОВ ЛИМИТОВ ===
def load_rate_limit_modes():
    """Загружает конфигурацию режимов из переменных окружения"""
    return {
        'conservative': {
            'name': '🟢 CONSERVATIVE',
            'description': 'Безопасный режим - 5% от лимита Telegram',
            'max_responses_per_hour': int(os.getenv('CONSERVATIVE_MAX_HOUR', '60')),  # 60/час = 1/мин
            'min_cooldown_seconds': int(os.getenv('CONSERVATIVE_COOLDOWN', '60')),   # 1 минута между ответами
            'emoji': '🐢',
            'risk': 'Минимальный'
        },
        'normal': {
            'name': '🟡 NORMAL', 
            'description': 'Рабочий режим - 15% от лимита Telegram',
            'max_responses_per_hour': int(os.getenv('NORMAL_MAX_HOUR', '180')),     # 180/час = 3/мин
            'min_cooldown_seconds': int(os.getenv('NORMAL_COOLDOWN', '20')),        # 20 секунд между ответами
            'emoji': '⚖️',
            'risk': 'Низкий'
        },
        'burst': {
            'name': '🟠 BURST',
            'description': 'Быстрый режим - 50% от лимита Telegram',
            'max_responses_per_hour': int(os.getenv('BURST_MAX_HOUR', '600')),      # 600/час = 10/мин
            'min_cooldown_seconds': int(os.getenv('BURST_COOLDOWN', '6')),          # 6 секунд между ответами
            'emoji': '⚡',
            'risk': 'Средний'
        },
        'admin_burst': {
            'name': '🔴 ADMIN_BURST',
            'description': 'Максимальный режим - 100% лимита групп (только админы)',
            'max_responses_per_hour': int(os.getenv('ADMIN_BURST_MAX_HOUR', '1200')), # 1200/час = 20/мин (группа лимит)
            'min_cooldown_seconds': int(os.getenv('ADMIN_BURST_COOLDOWN', '3')),       # 3 секунды между ответами
            'emoji': '🚨',
            'risk': 'ВЫСОКИЙ',
            'admin_only': True
        }
    }

# Глобальная переменная для режимов
RATE_LIMIT_MODES = load_rate_limit_modes()

# Остальные константы безопасности
RESPONSE_DELAY = int(os.getenv('RESPONSE_DELAY', '3'))

# Webhook настройки
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', 'misterdms-presave-bot.onrender.com')
WEBHOOK_PORT = int(os.getenv('PORT', 10000))
WEBHOOK_PATH = f"/{BOT_TOKEN}/"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Regex для поиска ссылок
URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === НОВЫЕ СИСТЕМЫ БЕЗОПАСНОСТИ v21 ===

class WebhookRateLimiter:
    """Rate limiting для webhook endpoint"""
    def __init__(self, max_requests: int = WEBHOOK_RATE_LIMIT, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = threading.Lock()
    
    def is_allowed(self, client_ip: str) -> bool:
        with self.lock:
            now = time.time()
            # Очищаем старые запросы
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip] 
                if now - req_time < self.window_seconds
            ]
            
            # Проверяем лимит
            if len(self.requests[client_ip]) >= self.max_requests:
                logger.warning(f"🚨 RATE_LIMIT: Blocked {client_ip} ({len(self.requests[client_ip])} requests)")
                return False
            
            # Добавляем текущий запрос
            self.requests[client_ip].append(now)
            return True

class DatabasePool:
    """Connection pooling для оптимизации БД"""
    def __init__(self, db_path: str, pool_size: int = DB_POOL_SIZE):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        
        # Создаем пул соединений
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")  # Улучшение производительности
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            self.pool.put(conn)
        
        logger.info(f"✅ DB_POOL: Created connection pool with {pool_size} connections")
    
    @contextmanager
    def get_connection(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)

class SecurityValidator:
    """Валидация данных для защиты от SQL Injection"""
    
    @staticmethod
    def sanitize_username(username: str) -> str:
        """Безопасная санитизация username"""
        if not username:
            return "anonymous"
        
        # Удаляем все кроме букв, цифр и подчеркиваний
        clean = re.sub(r'[^\w]', '', username.replace('@', ''))
        
        # Ограничиваем длину
        return clean[:50] if clean else "anonymous"
    
    @staticmethod
    def validate_text_input(text: str, max_length: int = 1000) -> str:
        """Валидация текстового ввода"""
        if not text or not isinstance(text, str):
            return ""
        
        # Удаляем потенциально опасные символы
        safe_text = re.sub(r'[<>"\']', '', text)
        return safe_text[:max_length]
    
    @staticmethod
    def verify_telegram_request(headers: dict, content_length: int) -> bool:
        """Проверка подлинности webhook от Telegram - ИСПРАВЛЕНО для production"""
        
        # Проверка размера (критично)
        if content_length > 1024 * 1024:  # 1MB лимит
            logger.warning(f"🚨 SECURITY: Payload too large: {content_length}")
            return False
        
        # Проверка secret token (если установлен) - основная защита
        if WEBHOOK_SECRET:
            received_token = headers.get('X-Telegram-Bot-Api-Secret-Token')
            if received_token != WEBHOOK_SECRET:
                logger.warning(f"🚨 SECURITY: Invalid webhook secret")
                return False
        
        # Логируем User-Agent для диагностики, но НЕ блокируем
        user_agent = headers.get('User-Agent', 'Not provided')
        logger.info(f"🔍 WEBHOOK_UA: User-Agent: {user_agent}")
        
        # В production Telegram может использовать разные User-Agent'ы или прокси
        # Поэтому полагаемся на secret token и размер payload
        
        return True

# Инициализация систем безопасности
rate_limiter = WebhookRateLimiter()
security = SecurityValidator()

# === ФУНКЦИИ УПРАВЛЕНИЯ РЕЖИМАМИ ===

def get_current_limits():
    """Получение текущих лимитов - ИСПРАВЛЕНО"""
    try:
        current_mode = db.get_current_rate_mode()
        
        # Проверяем что режим существует
        if current_mode not in RATE_LIMIT_MODES:
            logger.warning(f"Unknown rate mode: {current_mode}, falling back to conservative")
            current_mode = 'conservative'
            db.set_current_rate_mode('conservative')
        
        mode_config = RATE_LIMIT_MODES[current_mode]
        
        return {
            'max_responses_per_hour': max(mode_config.get('max_responses_per_hour', 60), 1),
            'min_cooldown_seconds': max(mode_config.get('min_cooldown_seconds', 60), 1),
            'mode_name': mode_config.get('name', '🟢 CONSERVATIVE'),
            'mode_emoji': mode_config.get('emoji', '🐢')
        }
    except Exception as e:
        logger.error(f"Error getting current limits: {e}")
        # Fallback к безопасным значениям
        return {
            'max_responses_per_hour': 60,
            'min_cooldown_seconds': 60, 
            'mode_name': '🟢 CONSERVATIVE (FALLBACK)',
            'mode_emoji': '🐢'
        }

def set_rate_limit_mode(new_mode: str, user_id: int) -> tuple[bool, str]:
    """Установка нового режима лимитов с валидацией"""
    if new_mode not in RATE_LIMIT_MODES:
        return False, f"❌ Неизвестный режим: {new_mode}"
    
    mode_config = RATE_LIMIT_MODES[new_mode]
    
    # Проверка админских прав для admin_burst
    if mode_config.get('admin_only', False) and not is_admin(user_id):
        return False, f"❌ Режим {mode_config['name']} доступен только администраторам"
    
    old_mode = db.get_current_rate_mode()
    old_config = RATE_LIMIT_MODES.get(old_mode, {})
    
    # Сохраняем новый режим в базу данных
    db.set_current_rate_mode(new_mode)
    
    # Сброс текущих лимитов при смене режима
    db.reset_rate_limits()
    
    change_text = f"""
🔄 Режим лимитов изменён!

📉 Было: {old_config.get('name', 'Неизвестно')}
• Ответов/час: {old_config.get('max_responses_per_hour', 'N/A')}
• Cooldown: {old_config.get('min_cooldown_seconds', 'N/A')} сек

📈 Стало: {mode_config['name']}
• Ответов/час: {mode_config['max_responses_per_hour']}
• Cooldown: {mode_config['min_cooldown_seconds']} сек

⚠️ Уровень риска: {mode_config['risk']}

✅ Лимиты сброшены, бот готов к работе в новом режиме
    """
    
    logger.info(f"🔄 RATE_MODE: Changed from {old_mode} to {new_mode} by user {user_id}")
    logger.info(f"📊 NEW_LIMITS: {mode_config['max_responses_per_hour']}/hour, {mode_config['min_cooldown_seconds']}s cooldown")
    
    return True, change_text

def reload_rate_limit_modes():
    """Перезагрузка режимов из переменных окружения"""
    global RATE_LIMIT_MODES
    RATE_LIMIT_MODES = load_rate_limit_modes()
    logger.info("🔄 RELOAD: Rate limit modes reloaded from environment variables")

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.pool = DatabasePool(db_path, DB_POOL_SIZE)
        logger.info(f"✅ DATABASE: Initialized with connection pooling")
    
    def get_connection(self):
        """Получение соединения из пула"""
        return self.pool.get_connection()
    
    def init_db(self):
        """Инициализация базы данных с улучшениями"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей и их ссылок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_links (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    total_links INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Детальная история ссылок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS link_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    link_url TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_id INTEGER
                )
            ''')
            
            # Логи ответов бота
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    response_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Настройки бота
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Активность бота
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_activity (
                    id INTEGER PRIMARY KEY,
                    is_active BOOLEAN DEFAULT 1,
                    responses_today INTEGER DEFAULT 0,
                    last_response_time TIMESTAMP,
                    last_reset_date DATE DEFAULT CURRENT_DATE
                )
            ''')
            
            # Лимиты и cooldown
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INTEGER PRIMARY KEY,
                    hourly_responses INTEGER DEFAULT 0,
                    last_hour_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cooldown_until TIMESTAMP
                )
            ''')
            
            # Создаем индексы для оптимизации
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_link_history_timestamp ON link_history(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_bot_responses_timestamp ON bot_responses(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_links_total ON user_links(total_links)')
            
            # Инициализация базовых записей
            cursor.execute('INSERT OR IGNORE INTO bot_activity (id, is_active) VALUES (1, 1)')
            cursor.execute('INSERT OR IGNORE INTO rate_limits (id) VALUES (1)')
            cursor.execute(
                'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                ('reminder_text', DEFAULT_REMINDER)
            )
            cursor.execute(
                'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                ('rate_limit_mode', 'conservative')
            )
            
            conn.commit()
            logger.info("✅ DATABASE: Database initialized successfully with v21 improvements")

    def add_user_links(self, user_id: int, username: str, links: list, message_id: int):
        """Добавление ссылок пользователя с безопасной валидацией"""
        # Валидация входных данных
        safe_username = security.sanitize_username(username)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Обновляем счётчик пользователя
            cursor.execute('''
                INSERT OR REPLACE INTO user_links (user_id, username, total_links, last_updated)
                VALUES (?, ?, COALESCE((SELECT total_links FROM user_links WHERE user_id = ?), 0) + ?, CURRENT_TIMESTAMP)
            ''', (user_id, safe_username, user_id, len(links)))
            
            # Добавляем детальную историю
            for link in links:
                safe_link = security.validate_text_input(link, 2000)  # Ограничиваем длину ссылки
                cursor.execute('''
                    INSERT INTO link_history (user_id, link_url, message_id)
                    VALUES (?, ?, ?)
                ''', (user_id, safe_link, message_id))
            
            conn.commit()

    def log_bot_response(self, user_id: int, response_text: str):
        """Логирование ответа бота"""
        safe_response = security.validate_text_input(response_text, 4000)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bot_responses (user_id, response_text)
                VALUES (?, ?)
            ''', (user_id, safe_response))
            conn.commit()

    def is_bot_active(self) -> bool:
        """Проверка активности бота"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_active FROM bot_activity WHERE id = 1')
            result = cursor.fetchone()
            return bool(result[0]) if result else False

    def set_bot_active(self, active: bool):
        """Установка статуса активности"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE bot_activity SET is_active = ? WHERE id = 1', (active,))
            conn.commit()

    def can_send_response(self) -> tuple[bool, str]:
        """Проверка лимитов с динамическим обновлением"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT hourly_responses, last_hour_reset, cooldown_until
                FROM rate_limits WHERE id = 1
            ''')
            result = cursor.fetchone()
            
            if not result:
                return False, "Ошибка получения лимитов"
            
            hourly_responses, last_hour_reset, cooldown_until = result
            now = datetime.now()
            
            # Получаем АКТУАЛЬНЫЕ лимиты из текущего режима
            current_limits = get_current_limits()
            max_responses = current_limits['max_responses_per_hour'] 
            cooldown_seconds = current_limits['min_cooldown_seconds']
            
            # Проверяем cooldown
            if cooldown_until:
                cooldown_time = datetime.fromisoformat(cooldown_until)
                if now < cooldown_time:
                    remaining = int((cooldown_time - now).total_seconds())
                    return False, f"Cooldown активен. Осталось: {remaining} сек (режим: {current_limits['mode_name']})"
            
            # Сброс почасового счётчика
            if last_hour_reset:
                last_reset = datetime.fromisoformat(last_hour_reset)
                if now - last_reset > timedelta(hours=1):
                    cursor.execute('''
                        UPDATE rate_limits 
                        SET hourly_responses = 0, last_hour_reset = ?
                        WHERE id = 1
                    ''', (now.isoformat(),))
                    hourly_responses = 0
            
            # Проверяем почасовой лимит
            if hourly_responses >= max_responses:
                return False, f"Достигнут лимит {max_responses} ответов в час (режим: {current_limits['mode_name']})"
            
            return True, "OK"

    def update_response_limits(self):
        """Обновление лимитов с учетом текущего режима"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            
            # Получаем АКТУАЛЬНЫЙ cooldown из текущего режима
            current_limits = get_current_limits()
            cooldown_seconds = current_limits['min_cooldown_seconds']
            cooldown_until = now + timedelta(seconds=cooldown_seconds)
            
            cursor.execute('''
                UPDATE rate_limits 
                SET hourly_responses = hourly_responses + 1,
                    cooldown_until = ?
                WHERE id = 1
            ''', (cooldown_until.isoformat(),))
            
            conn.commit()

    def reset_rate_limits(self):
        """Сброс лимитов при смене режима"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE rate_limits 
                SET hourly_responses = 0,
                    cooldown_until = NULL,
                    last_hour_reset = ?
                WHERE id = 1
            ''', (datetime.now().isoformat(),))
            conn.commit()
            logger.info("🔄 RATE_RESET: Rate limits reset due to mode change")

    def get_user_stats(self, username: str = None):
        """Получение статистики пользователей с безопасным поиском"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if username:
                safe_username = security.sanitize_username(username)
                cursor.execute('''
                    SELECT username, total_links, last_updated
                    FROM user_links 
                    WHERE username = ? AND total_links > 0
                ''', (safe_username,))
                result = cursor.fetchone()
                return result
            else:
                cursor.execute('''
                    SELECT username, total_links, last_updated
                    FROM user_links 
                    WHERE total_links > 0
                    ORDER BY total_links DESC
                    LIMIT 50
                ''')
                result = cursor.fetchall()
                return result

    def get_bot_stats(self):
        """Статистика работы бота - ИСПРАВЛЕНО"""
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                # Получаем лимиты с проверкой
                cursor.execute('''
                    SELECT hourly_responses, cooldown_until FROM rate_limits WHERE id = 1
                ''')
                limits = cursor.fetchone()
                
                # Получаем активность с проверкой
                cursor.execute('''
                    SELECT is_active, last_response_time FROM bot_activity WHERE id = 1
                ''')
                activity = cursor.fetchone()
                
                # Считаем ответы за сегодня с проверкой
                cursor.execute('''
                    SELECT COUNT(*) FROM bot_responses 
                    WHERE DATE(timestamp) = DATE('now')
                ''')
                today_responses = cursor.fetchone()
                
                # Получаем АКТУАЛЬНЫЕ лимиты из текущего режима с защитой
                current_limits = get_current_limits()
                
                return {
                    'hourly_responses': limits[0] if limits and limits[0] is not None else 0,
                    'hourly_limit': current_limits['max_responses_per_hour'],
                    'cooldown_until': limits[1] if limits else None,
                    'is_active': bool(activity[0]) if activity and activity[0] is not None else False,
                    'last_response': activity[1] if activity else None,
                    'today_responses': today_responses[0] if today_responses and today_responses[0] is not None else 0
                }
                
            except Exception as e:
                logger.error(f"Database error in get_bot_stats: {e}")
                # Возвращаем безопасные значения
                return {
                    'hourly_responses': 0,
                    'hourly_limit': 60,
                    'cooldown_until': None,
                    'is_active': False,
                    'last_response': None,
                    'today_responses': 0
                }

    def clear_link_history(self):
        """Очистка истории ссылок (счётчики остаются)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM link_history')
            conn.commit()

    def get_reminder_text(self) -> str:
        """Получение текста напоминания"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', ('reminder_text',))
            result = cursor.fetchone()
            return result[0] if result else DEFAULT_REMINDER

    def set_reminder_text(self, text: str):
        """Установка текста напоминания с валидацией"""
        safe_text = security.validate_text_input(text, 4000)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', ('reminder_text', safe_text))
            conn.commit()

    def get_current_rate_mode(self) -> str:
        """Получение текущего режима лимитов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', ('rate_limit_mode',))
            result = cursor.fetchone()
            return result[0] if result else 'conservative'

    def set_current_rate_mode(self, mode: str):
        """Установка текущего режима лимитов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', ('rate_limit_mode', mode))
            conn.commit()
            logger.info(f"🎛️ RATE_MODE: Saved mode '{mode}' to database")

# Инициализация базы данных
db = Database()

def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in ADMIN_IDS

def extract_links(text: str) -> list:
    """Извлечение ссылок из текста"""
    return URL_PATTERN.findall(text)

def safe_send_message(chat_id: int, text: str, message_thread_id: int = None, reply_to_message_id: int = None):
    """Безопасная отправка сообщения с обработкой ошибок"""
    try:
        logger.info(f"💬 SEND_MESSAGE: Preparing to send message to chat {chat_id}")
        
        time.sleep(RESPONSE_DELAY)  # Задержка перед отправкой
        
        if message_thread_id:
            result = bot.send_message(
                chat_id=chat_id, 
                text=text, 
                message_thread_id=message_thread_id,
                reply_to_message_id=reply_to_message_id
            )
        else:
            if reply_to_message_id:
                result = bot.reply_to(reply_to_message_id, text)
            else:
                result = bot.send_message(chat_id, text)
        
        logger.info(f"✅ SENT: Message sent successfully")
        return True
    except Exception as e:
        logger.error(f"❌ SEND_ERROR: Failed to send message: {str(e)}")
        return False

# === УЛУЧШЕННЫЙ WEBHOOK СЕРВЕР v21 ===

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Обработка POST запросов с улучшенной безопасностью"""
        client_ip = self.client_address[0]
        logger.info(f"📨 WEBHOOK_POST: Request from {client_ip} to {self.path}")
        
        # Проверка rate limiting
        if not rate_limiter.is_allowed(client_ip):
            logger.warning(f"🚫 RATE_LIMITED: Blocked {client_ip}")
            self.send_response(429)  # Too Many Requests
            self.end_headers()
            return
        
        if self.path == WEBHOOK_PATH:
            try:
                # Проверка размера содержимого
                content_length = int(self.headers.get('Content-Length', 0))
                
                # Валидация Telegram запроса
                if not security.verify_telegram_request(self.headers, content_length):
                    logger.warning(f"🚨 SECURITY: Invalid request from {client_ip}")
                    self.send_response(403)
                    self.end_headers()
                    return
                
                # Чтение данных
                post_data = self.rfile.read(content_length)
                logger.info(f"📦 WEBHOOK_DATA: Received {content_length} bytes")
                
                # Парсинг JSON
                update_data = json.loads(post_data.decode('utf-8'))
                
                # Создание и обработка update
                update = telebot.types.Update.de_json(update_data)
                
                if update:
                    bot.process_new_updates([update])
                    logger.info(f"✅ WEBHOOK_PROCESSED: Update processed successfully")
                
                self.send_response(200)
                self.end_headers()
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON_ERROR: {e}")
                self.send_response(400)
                self.end_headers()
            except Exception as e:
                logger.error(f"❌ WEBHOOK_ERROR: {str(e)}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "status": "healthy", 
                "service": "telegram-bot",
                "version": "v21-fixed",
                "security": "enhanced",
                "features": ["webhook_security", "connection_pooling", "keep_alive"]
            })
            self.wfile.write(response.encode())
        
        elif self.path == '/keepalive':
            # Специальный endpoint для внешних пинг-сервисов
            client_ip = self.client_address[0]
            logger.info(f"💓 KEEPALIVE: Keep-alive ping received from {client_ip}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Проверяем статус бота
            try:
                bot_active = db.is_bot_active()
                current_limits = get_current_limits()
                
                response = json.dumps({
                    "status": "alive",
                    "timestamp": time.time(),
                    "version": "v21-fixed",
                    "bot_active": bot_active,
                    "current_mode": current_limits['mode_name'],
                    "uptime_check": "✅ OK"
                })
            except Exception as e:
                logger.error(f"❌ KEEPALIVE_ERROR: {e}")
                response = json.dumps({
                    "status": "alive_with_errors",
                    "timestamp": time.time(),
                    "error": str(e)
                })
            
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        """Обработка GET запросов"""
        if self.path == '/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "status": "healthy", 
                "service": "telegram-bot",
                "version": "v21-fixed"
            })
            self.wfile.write(response.encode())
        
        elif self.path == '/keepalive':
            # Keep-alive endpoint для GET запросов (UptimeRobot использует GET)
            client_ip = self.client_address[0]
            logger.info(f"💓 KEEPALIVE_GET: Keep-alive ping (GET) from {client_ip}")
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            try:
                bot_active = db.is_bot_active()
                current_limits = get_current_limits()
                
                response = json.dumps({
                    "status": "alive",
                    "method": "GET",
                    "timestamp": time.time(),
                    "version": "v21-fixed",
                    "bot_active": bot_active,
                    "current_mode": current_limits['mode_name'],
                    "uptime_check": "✅ OK"
                })
            except Exception as e:
                logger.error(f"❌ KEEPALIVE_GET_ERROR: {e}")
                response = json.dumps({
                    "status": "alive_with_errors",
                    "method": "GET", 
                    "timestamp": time.time(),
                    "error": str(e)
                })
            
            self.wfile.write(response.encode())
        elif self.path == WEBHOOK_PATH:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            info_page = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Presave Reminder Bot v21-fixed - Webhook</title>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
                    .header {{ text-align: center; color: #2196F3; }}
                    .status {{ background: #E8F5E8; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                    .feature {{ background: #F0F8FF; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🤖 Presave Reminder Bot v21-fixed</h1>
                    <h2>Enhanced Security Webhook</h2>
                </div>
                
                <div class="status">
                    <h3>✅ Status: Active & Secured</h3>
                    <p>Production-ready version with fixed webhook security</p>
                </div>
                
                <div class="feature">
                    <h4>🔐 Security Features</h4>
                    <ul>
                        <li>Flexible webhook validation for production</li>
                        <li>Rate limiting protection</li>
                        <li>SQL injection prevention</li>
                        <li>Connection pooling</li>
                    </ul>
                </div>
                
                <div class="feature">
                    <h4>🐛 Bug Fixes</h4>
                    <ul>
                        <li>Fixed division by zero in currentmode</li>
                        <li>Enhanced error handling</li>
                        <li>Database connection stability</li>
                        <li>Production webhook compatibility</li>
                    </ul>
                </div>
            </body>
            </html>
            """
            self.wfile.write(info_page.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

# === ОБРАБОТЧИКИ КОМАНД v21 ===

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if not is_admin(message.from_user.id):
        return
    
    bot.reply_to(message, """
🤖 Presave Reminder Bot v21-fixed запущен!

🔧 Исправления v21-fixed:
✅ Фикс деления на ноль в /currentmode
✅ Улучшенная безопасность webhook для production
✅ Connection pooling для БД
✅ Защита от SQL injection

Для управления используйте /help
    """)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    """ИСПРАВЛЕННАЯ команда help с примерами режимов"""
    if not is_admin(message.from_user.id):
        return
    
    help_text = """
🤖 Команды бота v21:

👑 Основные команды:
/help — этот список команд
/activate — включить бота в топике
/deactivate — отключить бота в топике  
/stats — общая статистика работы
/botstat — мониторинг лимитов

📊 Статистика:
/linkstats — рейтинг пользователей
/topusers — топ-5 активных
/userstat @username — статистика пользователя

🎛️ Лимиты (ИСПРАВЛЕНО):
/modes — показать режимы лимитов
/setmode <режим> — сменить режим
  └ conservative — безопасный (60/час)
  └ normal — рабочий (180/час) 
  └ burst — быстрый (600/час)
  └ admin_burst — максимум (1200/час) 👑
  └ Пример: /setmode normal
/currentmode — текущий режим
/reloadmodes — обновить из Environment Variables

🔧 Настройки:
/setmessage текст — изменить напоминание
/clearhistory — очистить историю
/test_regex — тест ссылок
/alllinks — все ссылки
/recent — последние ссылки

🆕 v21-fixed исправления:
✅ Исправлены краши команд
✅ Безопасность webhook для production
✅ Connection pooling
✅ Защита от SQL injection
    """
    
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['modes'])
def cmd_modes(message):
    """Показать все доступные режимы с актуальными значениями"""
    if not is_admin(message.from_user.id):
        return
    
    reload_rate_limit_modes()
    
    modes_text = "🎛️ Доступные режимы лимитов (v21-fixed):\n\n"
    
    for mode_key, mode_config in RATE_LIMIT_MODES.items():
        is_current = "✅ " if mode_key == db.get_current_rate_mode() else "   "
        admin_mark = " 👑" if mode_config.get('admin_only', False) else ""
        
        msgs_per_min = round(mode_config['max_responses_per_hour'] / 60, 2)
        
        modes_text += f"{is_current}{mode_config['emoji']} **{mode_config['name']}**{admin_mark}\n"
        modes_text += f"   📝 {mode_config['description']}\n"
        modes_text += f"   📊 {mode_config['max_responses_per_hour']} ответов/час ({msgs_per_min}/мин)\n"
        modes_text += f"   ⏱️ {mode_config['min_cooldown_seconds']}с между ответами\n"
        modes_text += f"   ⚠️ Риск: {mode_config['risk']}\n\n"
    
    modes_text += "🔄 Переключение: `/setmode <название>`\n"
    modes_text += "📋 Режимы: conservative, normal, burst, admin_burst\n"
    modes_text += "🔧 Настройки загружаются из Environment Variables"
    
    bot.reply_to(message, modes_text, parse_mode='Markdown')

@bot.message_handler(commands=['setmode'])
def cmd_set_mode(message):
    """Установка режима лимитов с валидацией"""
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 2:
        current_limits = get_current_limits()
        current_text = f"""
🎛️ Текущий режим: {current_limits['mode_name']}

📊 Активные лимиты:
• Ответов в час: {current_limits['max_responses_per_hour']}
• Cooldown: {current_limits['min_cooldown_seconds']} секунд

🔄 Для смены: `/setmode <режим>`
📋 Режимы: conservative, normal, burst, admin_burst
💡 Пример: `/setmode normal`
        """
        bot.reply_to(message, current_text)
        return
    
    new_mode = security.validate_text_input(args[1].lower(), 50)
    logger.info(f"🔄 SETMODE attempting to set mode: {new_mode} by user {message.from_user.id}")
    
    reload_rate_limit_modes()
    
    success, result_text = set_rate_limit_mode(new_mode, message.from_user.id)
    
    if success:
        logger.info(f"✅ SETMODE successfully changed to {new_mode}")
    else:
        logger.warning(f"❌ SETMODE failed: {result_text}")
    
    bot.reply_to(message, result_text)

@bot.message_handler(commands=['currentmode'])
def cmd_current_mode(message):
    """Показать текущий режим и использование - ИСПРАВЛЕНО"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        current_limits = get_current_limits()
        current_mode_key = db.get_current_rate_mode()
        
        # Проверяем что режим существует
        if current_mode_key not in RATE_LIMIT_MODES:
            bot.reply_to(message, "❌ Ошибка: неизвестный текущий режим. Используйте /setmode conservative")
            return
            
        mode_config = RATE_LIMIT_MODES[current_mode_key]
        bot_stats = db.get_bot_stats()
        
        # ИСПРАВЛЕНИЕ: защита от деления на ноль
        max_responses = mode_config.get('max_responses_per_hour', 1)
        if max_responses <= 0:
            max_responses = 1
            
        usage_percent = round((bot_stats['hourly_responses'] / max_responses) * 100, 1)
        msgs_per_min = round(max_responses / 60, 2)
        
        current_text = f"""
🎛️ Текущий режим лимитов v21-fixed:

{mode_config['emoji']} **{mode_config['name']}**
📝 {mode_config['description']}

📊 Конфигурация режима:
• Максимум: {max_responses} ответов/час ({msgs_per_min}/мин)
• Cooldown: {mode_config['min_cooldown_seconds']} секунд
• Уровень риска: {mode_config['risk']}

📈 Использование:
• Отправлено в час: {bot_stats['hourly_responses']}/{max_responses} ({usage_percent}%)
• Ответов сегодня: {bot_stats['today_responses']}

🔧 Источник: Environment Variables
🔄 Сменить: `/setmode <режим>` | Все режимы: `/modes`
        """
        
        bot.reply_to(message, current_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Error in CURRENTMODE command: {str(e)}")
        bot.reply_to(message, f"❌ Ошибка получения режима: {str(e)}")

@bot.message_handler(commands=['reloadmodes'])
def cmd_reload_modes(message):
    """Перезагрузка режимов из переменных окружения"""
    if not is_admin(message.from_user.id):
        return
    
    old_modes = dict(RATE_LIMIT_MODES)
    reload_rate_limit_modes()
    
    reload_text = """
🔄 Режимы лимитов перезагружены из Environment Variables!

📋 Обновленные режимы:
"""
    
    for mode_key, mode_config in RATE_LIMIT_MODES.items():
        old_config = old_modes.get(mode_key, {})
        emoji = mode_config.get('emoji', '⚙️')
        
        reload_text += f"\n{emoji} {mode_config['name']}\n"
        reload_text += f"  📊 {mode_config['max_responses_per_hour']}/час, {mode_config['min_cooldown_seconds']}с\n"
        
        if old_config:
            if (old_config.get('max_responses_per_hour') != mode_config['max_responses_per_hour'] or 
                old_config.get('min_cooldown_seconds') != mode_config['min_cooldown_seconds']):
                reload_text += f"  🔄 ИЗМЕНЕНО!\n"
    
    reload_text += "\n✅ Готово к работе с новыми настройками"
    
    bot.reply_to(message, reload_text)
    logger.info(f"🔄 RELOAD: Modes reloaded by admin {message.from_user.id}")

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    """ИСПРАВЛЕННАЯ команда статистики"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        bot_stats = db.get_bot_stats()
        user_stats = db.get_user_stats()
        
        total_users = len(user_stats) if user_stats else 0
        total_links = sum(user[1] for user in user_stats) if user_stats else 0
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM link_history WHERE DATE(timestamp) = DATE("now")')
            today_links_result = cursor.fetchone()
            today_links = today_links_result[0] if today_links_result else 0
            
            cursor.execute('SELECT COUNT(*) FROM link_history WHERE timestamp >= datetime("now", "-7 days")')
            week_links_result = cursor.fetchone()
            week_links = week_links_result[0] if week_links_result else 0
            
            cursor.execute('SELECT username, total_links FROM user_links WHERE total_links > 0 ORDER BY total_links DESC LIMIT 1')
            top_user = cursor.fetchone()
        
        status_emoji = "🟢" if bot_stats['is_active'] else "🔴"
        status_text = "Активен" if bot_stats['is_active'] else "Отключен"
        
        current_limits = get_current_limits()
        current_mode = db.get_current_rate_mode()
        
        stats_text = f"""
📊 Статистика бота v21-fixed:

🤖 Статус: {status_emoji} {status_text}
👥 Активных пользователей: {total_users}
🔗 Всего ссылок: {total_links}

📅 За сегодня:
• Ссылок: {today_links}
• Ответов: {bot_stats['today_responses']}

📈 За неделю:
• Ссылок: {week_links}

⚡ Лимиты ({current_limits['mode_emoji']} {current_mode.upper()}):
• Ответов в час: {bot_stats['hourly_responses']}/{bot_stats['hourly_limit']}

🏆 Лидер: {f"@{top_user[0]} ({top_user[1]} ссылок)" if top_user else "пока нет"}

🔗 Webhook: активен | Версия: v21-fixed (исправленная)
        """
        
        bot.reply_to(message, stats_text)
        
    except Exception as e:
        logger.error(f"❌ Error in STATS command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения статистики")

@bot.message_handler(commands=['activate'])
def cmd_activate(message):
    if not is_admin(message.from_user.id):
        return
    
    if message.chat.id != GROUP_ID or message.message_thread_id != THREAD_ID:
        bot.reply_to(message, "❌ Команда должна выполняться в топике пресейвов")
        return
    
    db.set_bot_active(True)
    
    current_limits = get_current_limits()
    current_mode = db.get_current_rate_mode()
    
    welcome_text = f"""
🤖 Presave Reminder Bot v21 активирован!

✅ Готов к работе в топике "Пресейвы"
🎯 Буду отвечать на сообщения со ссылками
{current_limits['mode_emoji']} Режим: {current_mode.upper()} ({current_limits['max_responses_per_hour']}/час, {current_limits['min_cooldown_seconds']}с)
⚙️ Управление: /help
🛑 Отключить: /deactivate

🆕 v21-fixed: Исправлены краши команд! 🎵
    """
    
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['deactivate'])
def cmd_deactivate(message):
    if not is_admin(message.from_user.id):
        return
    
    db.set_bot_active(False)
    bot.reply_to(message, "🛑 Бот деактивирован. Для включения используйте /activate")

@bot.message_handler(commands=['botstat'])
def cmd_bot_stat(message):
    """ИСПРАВЛЕННАЯ команда статистики бота"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        stats = db.get_bot_stats()
        current_limits = get_current_limits()
        current_mode = db.get_current_rate_mode()
        
        cooldown_text = "Готов к ответу"
        if stats['cooldown_until']:
            try:
                cooldown_time = datetime.fromisoformat(stats['cooldown_until'])
                now = datetime.now()
                if now < cooldown_time:
                    remaining = int((cooldown_time - now).total_seconds())
                    cooldown_text = f"Следующий ответ через: {remaining} сек"
            except Exception as e:
                logger.error(f"Error parsing cooldown time: {e}")
                cooldown_text = "Ошибка определения cooldown"
        
        status_emoji = "🟢" if stats['is_active'] else "🔴"
        status_text = "Активен" if stats['is_active'] else "Отключен"
        
        # ИСПРАВЛЕНИЕ: защита от деления на ноль
        hourly_limit = max(stats['hourly_limit'], 1)
        usage_percent = round((stats['hourly_responses'] / hourly_limit) * 100, 1)
        
        stat_text = f"""
🤖 Статистика бота v21-fixed:

{status_emoji} Статус: {status_text}
{current_limits['mode_emoji']} Режим: {current_mode.upper()}
⚡ Ответов в час: {stats['hourly_responses']}/{hourly_limit} ({usage_percent}%)
📊 Ответов за сегодня: {stats['today_responses']}
⏱️ {cooldown_text}
🔗 Webhook: активен

⚠️ Статус: {'🟡 Приближение к лимиту' if usage_percent >= 80 else '✅ Всё в порядке'}

🆕 v21-fixed: Исправлены краши и улучшена безопасность
        """
        
        bot.reply_to(message, stat_text)
        
    except Exception as e:
        logger.error(f"❌ Error in BOTSTAT command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения статистики")

# [Остальные команды linkstats, topusers, userstat, setmessage, clearhistory, test_regex, alllinks, recent - остаются без изменений, но с улучшенной обработкой ошибок]

@bot.message_handler(commands=['linkstats'])
def cmd_link_stats(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        users = db.get_user_stats()
        
        if not users:
            bot.reply_to(message, "📊 Пока нет пользователей с ссылками")
            return
        
        stats_text = "📊 Статистика по ссылкам v21-fixed:\n\n"
        
        for i, (username, total_links, last_updated) in enumerate(users[:10], 1):
            if total_links >= 31:
                rank = "💎"
            elif total_links >= 16:
                rank = "🥇"
            elif total_links >= 6:
                rank = "🥈"
            else:
                rank = "🥉"
            
            stats_text += f"{rank} {i}. @{username} — {total_links} ссылок\n"
        
        bot.reply_to(message, stats_text)
        
    except Exception as e:
        logger.error(f"❌ Error in LINKSTATS command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения статистики")

@bot.message_handler(commands=['topusers'])
def cmd_top_users(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        users = db.get_user_stats()
        
        if not users:
            bot.reply_to(message, "🏆 Пока нет активных пользователей")
            return
        
        top_text = "🏆 Топ-5 самых активных:\n\n"
        
        for i, (username, total_links, last_updated) in enumerate(users[:5], 1):
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            medal = medals[i-1] if i <= 5 else "▫️"
            
            top_text += f"{medal} @{username} — {total_links} ссылок\n"
        
        bot.reply_to(message, top_text)
        
    except Exception as e:
        logger.error(f"❌ Error in TOPUSERS command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения топа")

@bot.message_handler(commands=['userstat'])
def cmd_user_stat(message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "❌ Укажите username: /userstat @username")
        return
    
    username = args[1].replace('@', '')
    
    try:
        user_data = db.get_user_stats(username)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь @{username} не найден или не имеет ссылок")
            return
        
        username, total_links, last_updated = user_data
        
        if total_links >= 31:
            rank = "💎 Амбассадор"
        elif total_links >= 16:
            rank = "🥇 Промоутер"
        elif total_links >= 6:
            rank = "🥈 Активный"
        else:
            rank = "🥉 Начинающий"
        
        stat_text = f"""
👤 Статистика пользователя @{username}:

🔗 Всего ссылок: {total_links}
📅 Последняя активность: {last_updated[:16]}
🏆 Звание: {rank}
        """
        
        bot.reply_to(message, stat_text)
        
    except Exception as e:
        logger.error(f"❌ Error in USERSTAT command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения статистики пользователя")

@bot.message_handler(commands=['setmessage'])
def cmd_set_message(message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        current_text = db.get_reminder_text()
        bot.reply_to(message, f"📝 Текущее сообщение:\n\n{current_text}\n\nДля изменения: /setmessage новый текст")
        return
    
    new_text = args[1]
    
    try:
        db.set_reminder_text(new_text)
        bot.reply_to(message, f"✅ Текст напоминания обновлён:\n\n{new_text}")
        
    except Exception as e:
        logger.error(f"❌ Error in SETMESSAGE command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка обновления текста")

@bot.message_handler(commands=['clearhistory'])
def cmd_clear_history(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        db.clear_link_history()
        bot.reply_to(message, "🧹 История ссылок очищена (общие счётчики сохранены)")
        
    except Exception as e:
        logger.error(f"❌ Error in CLEARHISTORY command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка очистки истории")

@bot.message_handler(commands=['test_regex'])
def cmd_test_regex(message):
    if not is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "🧪 Отправьте: /test_regex ваш текст со ссылками")
        return
    
    test_text = args[1]
    links = extract_links(test_text)
    
    result_text = f"🧪 Результат тестирования v21-fixed:\n\n📝 Текст: {test_text}\n\n"
    
    if links:
        result_text += f"✅ Найдено ссылок: {len(links)}\n"
        for i, link in enumerate(links, 1):
            result_text += f"{i}. {link}\n"
        result_text += "\n👍 Бот ответит на такое сообщение"
    else:
        result_text += "❌ Ссылки не найдены\n👎 Бот НЕ ответит на такое сообщение"
    
    bot.reply_to(message, result_text)

@bot.message_handler(commands=['alllinks'])
def cmd_all_links(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT link_url, username, timestamp 
                FROM link_history 
                LEFT JOIN user_links ON link_history.user_id = user_links.user_id
                ORDER BY timestamp DESC
                LIMIT 50
            ''')
            
            links = cursor.fetchall()
        
        if not links:
            bot.reply_to(message, "📋 В базе данных пока нет ссылок")
            return
        
        links_text = f"📋 Все ссылки в базе v21-fixed (последние 50):\n\n"
        
        for i, (link_url, username, timestamp) in enumerate(links[:20], 1):
            username_display = f"@{username}" if username else "Неизвестный"
            date_display = timestamp[:16] if timestamp else "Неизвестно"
            
            display_url = link_url[:50] + "..." if len(link_url) > 50 else link_url
            
            links_text += f"{i}. {display_url}\n   👤 {username_display} | 📅 {date_display}\n\n"
        
        if len(links) > 20:
            links_text += f"... и ещё {len(links) - 20} ссылок\n"
        
        links_text += f"\n📊 Всего ссылок в базе: {len(links)}"
        
        bot.reply_to(message, links_text)
        
    except Exception as e:
        logger.error(f"❌ Error in ALLLINKS command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения списка ссылок")

@bot.message_handler(commands=['recent'])
def cmd_recent_links(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT link_url, username, timestamp 
                FROM link_history 
                LEFT JOIN user_links ON link_history.user_id = user_links.user_id
                ORDER BY timestamp DESC
                LIMIT 10
            ''')
            
            recent_links = cursor.fetchall()
        
        if not recent_links:
            bot.reply_to(message, "📋 В базе данных пока нет ссылок")
            return
        
        recent_text = f"🕐 Последние {len(recent_links)} ссылок v21-fixed:\n\n"
        
        for i, (link_url, username, timestamp) in enumerate(recent_links, 1):
            username_display = f"@{username}" if username else "Неизвестный"
            date_display = timestamp[:16] if timestamp else "Неизвестно"
            
            display_url = link_url[:60] + "..." if len(link_url) > 60 else link_url
            
            recent_text += f"{i}. {display_url}\n   👤 {username_display} | 📅 {date_display}\n\n"
        
        bot.reply_to(message, recent_text)
        
    except Exception as e:
        logger.error(f"❌ Error in RECENT command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения последних ссылок")

# === СПЕЦИАЛЬНЫЕ ОБРАБОТЧИКИ ===

@bot.message_handler(func=lambda message: message.text and '@misterdms_presave_bot' in message.text and message.text.strip().startswith('/'))
def handle_tagged_commands(message):
    """Обработчик команд с @botname - ИСПРАВЛЕН"""
    try:
        command_text = message.text.strip()
        clean_command = command_text.split('@')[0]
        
        # Создаем временную копию сообщения с очищенной командой
        temp_message = message
        temp_message.text = clean_command
        
        # Маршрутизация команд
        command_map = {
            '/stats': cmd_stats,
            '/help': cmd_help,
            '/botstat': cmd_bot_stat,
            '/linkstats': cmd_link_stats,
            '/alllinks': cmd_all_links,
            '/recent': cmd_recent_links,
            '/activate': cmd_activate,
            '/deactivate': cmd_deactivate,
            '/modes': cmd_modes,
            '/setmode': cmd_set_mode,
            '/currentmode': cmd_current_mode,
            '/reloadmodes': cmd_reload_modes,
        }
        
        handler = command_map.get(clean_command)
        if handler:
            logger.info(f"🎯 TAGGED_COMMAND: Processing {clean_command} from {message.from_user.id}")
            handler(temp_message)
        else:
            logger.info(f"❓ UNKNOWN_TAGGED: Command {clean_command} not found")
            
    except Exception as e:
        logger.error(f"❌ Error in TAGGED_COMMANDS: {str(e)}")

@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def global_command_logger(message):
    """Глобальный логгер команд для диагностики"""
    command_text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "No_username"
    chat_id = message.chat.id
    thread_id = getattr(message, 'message_thread_id', None)
    
    logger.info(f"🌐 GLOBAL: Command '{command_text}' from user {user_id} (@{username}) in chat {chat_id}, thread {thread_id}")
    
    if '@' in command_text:
        if '@misterdms_presave_bot' in command_text:
            logger.info(f"✅ TARGETED: Command for our bot")
        else:
            logger.info(f"➡️ OTHER_BOT: Command for different bot")
    
    is_admin_user = is_admin(user_id)
    logger.info(f"👑 ADMIN_CHECK: User {user_id} admin status: {is_admin_user}")
    
    in_correct_chat = (chat_id == GROUP_ID)
    in_correct_thread = (thread_id == THREAD_ID)
    logger.info(f"📍 LOCATION: Correct chat: {in_correct_chat}, Correct thread: {in_correct_thread}")

# === ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ===

@bot.message_handler(func=lambda message: message.chat.id == GROUP_ID and message.message_thread_id == THREAD_ID)
def handle_topic_message(message):
    """Обработка сообщений в топике пресейвов"""
    
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    message_text = message.text or message.caption or ""
    
    logger.info(f"📨 TOPIC_MESSAGE: Message from user {user_id} (@{username})")
    
    if message.text and message.text.startswith('/'):
        return
    
    if message.from_user.is_bot:
        return
    
    if not db.is_bot_active():
        return
    
    links = extract_links(message_text)
    logger.info(f"🔍 LINKS_FOUND: {len(links)} links")
    
    if not links:
        return
    
    # Проверяем лимиты с АКТУАЛЬНЫМИ значениями
    can_respond, reason = db.can_send_response()
    logger.info(f"🚦 RATE_LIMIT: Can respond: {can_respond}, reason: '{reason}'")
    
    if not can_respond:
        logger.warning(f"🚫 BLOCKED: Response blocked: {reason}")
        return
    
    try:
        db.add_user_links(user_id, username, links, message.message_id)
        reminder_text = db.get_reminder_text()
        
        success = safe_send_message(
            chat_id=GROUP_ID,
            text=reminder_text,
            message_thread_id=THREAD_ID,
            reply_to_message_id=message.message_id
        )
        
        if success:
            db.update_response_limits()
            db.log_bot_response(user_id, reminder_text)
            logger.info(f"🎉 SUCCESS: Response sent for user {username} ({len(links)} links)")
        
    except Exception as e:
        logger.error(f"💥 ERROR: Exception in message processing: {str(e)}")

def setup_webhook():
    """Настройка webhook с улучшенной безопасностью"""
    try:
        bot.remove_webhook()
        
        # Настройка webhook с secret token для безопасности
        webhook_kwargs = {"url": WEBHOOK_URL}
        if WEBHOOK_SECRET:
            webhook_kwargs["secret_token"] = WEBHOOK_SECRET
            logger.info("🔐 WEBHOOK: Using secret token for enhanced security")
        
        webhook_result = bot.set_webhook(**webhook_kwargs)
        logger.info(f"✅ WEBHOOK_SET: Webhook configured successfully with security")
        return True
    except Exception as e:
        logger.error(f"❌ WEBHOOK_ERROR: Failed to setup webhook: {str(e)}")
        return False

def main():
    """Основная функция запуска бота v21"""
    try:
        logger.info("🚀 STARTUP: Starting Presave Reminder Bot v21-fixed")
        logger.info(f"🔧 CONFIG: GROUP_ID={GROUP_ID}, THREAD_ID={THREAD_ID}")
        logger.info(f"🔐 SECURITY: Enhanced webhook protection enabled")
        logger.info(f"⚡ DATABASE: Connection pooling with {DB_POOL_SIZE} connections")
        
        # Инициализация базы данных
        db.init_db()
        
        # Загружаем режимы из переменных окружения
        reload_rate_limit_modes()
        current_mode = db.get_current_rate_mode()
        current_limits = get_current_limits()
        
        logger.info("🤖 Presave Reminder Bot v21-fixed запущен!")
        logger.info(f"👥 Группа: {GROUP_ID}")
        logger.info(f"📋 Топик: {THREAD_ID}")
        logger.info(f"👑 Админы: {ADMIN_IDS}")
        logger.info(f"🎛️ РЕЖИМ: {current_limits['mode_name']} ({current_limits['max_responses_per_hour']}/час, {current_limits['min_cooldown_seconds']}с)")
        
        # Настройка webhook
        if setup_webhook():
            logger.info("🔗 Webhook режим активен с улучшенной безопасностью")
        else:
            logger.error("❌ Ошибка настройки webhook")
            return
        
        # Запуск webhook сервера
        with socketserver.TCPServer(("", WEBHOOK_PORT), WebhookHandler) as httpd:
            logger.info(f"🌐 Webhook сервер запущен на порту {WEBHOOK_PORT}")
            logger.info(f"🔗 URL: {WEBHOOK_URL}")
            logger.info("✅ READY: Bot v21-fixed is fully operational with enhanced stability")
            httpd.serve_forever()
        
    except Exception as e:
        logger.error(f"💥 CRITICAL: Critical error in main: {str(e)}")
    finally:
        try:
            bot.remove_webhook()
            logger.info("🧹 Webhook очищен при остановке")
        except:
            pass

if __name__ == "__main__":
    main()
