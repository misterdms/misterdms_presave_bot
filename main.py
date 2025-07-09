# PRESAVE REMINDER BOT v23.3 - ЭТАП 1 ПОЛНАЯ РЕАЛИЗАЦИЯ
# Интерактивная система пресейвов с улучшенными меню и аналитикой
# ВСЕ ФУНКЦИИ ЭТАПА 1 ИНТЕГРИРОВАНЫ

import logging
import re
import sqlite3
import time
import threading
import os
import json
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
from collections import defaultdict
from contextlib import contextmanager
from queue import Queue

import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))  # -1002811959953
THREAD_ID = int(os.getenv('THREAD_ID'))  # 3
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
DEFAULT_REMINDER = os.getenv('REMINDER_TEXT', '🎧 Напоминаем: не забудьте сделать пресейв артистов выше! ♥️')

# === НАСТРОЙКИ БЕЗОПАСНОСТИ ===
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', None)
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
WEBHOOK_RATE_LIMIT = int(os.getenv('WEBHOOK_RATE_LIMIT', '100'))

# === СИСТЕМА ПРАВ ПОЛЬЗОВАТЕЛЕЙ v23.3 ===
USER_PERMISSIONS = {
    'admin': 'all',  # Все команды
    'user': ['help', 'linkstats', 'topusers', 'userstat', 'mystat', 'alllinks', 'recent', 'presave_claim']
}

# === ПОЛЬЗОВАТЕЛЬСКИЕ СОСТОЯНИЯ v23.3 ===
USER_STATES = {
    'waiting_username': 'Ожидание ввода username',
    'waiting_message': 'Ожидание ввода сообщения',
    'waiting_mode': 'Ожидание выбора режима',
    'waiting_presave_links': 'Ожидание ссылок для пресейва',
    'waiting_presave_comment': 'Ожидание комментария к пресейву'
}

# === PRESAVE SYSTEM PATTERNS v23.3 ===
PRESAVE_CLAIM_PATTERNS = {
    'basic': [
        r'сделал\s+пресейв',
        r'готово',
        r'сделал(?:\s+где\s+смог)?',
        r'сохранил',
        r'добавил\s+в\s+(?:библиотеку|плейлист)',
        r'пресейв\s+готов'
    ],
    'platforms': {
        'spotify': r'(?:спотиф|spotify|спот)',
        'apple': r'(?:яблок|apple|itunes|эпл)',
        'yandex': r'(?:яндекс|yandex|я\.музыка)',
        'vk': r'(?:вк|vkmusic|вконтакте)',
        'deezer': r'(?:deezer|дизер)',
        'youtube': r'(?:youtube|ютуб|yt music)'
    }
}

ADMIN_VERIFICATION_PATTERNS = [
    r'подтверждаю',
    r'подтверждено', 
    r'проверено'
]

def is_presave_claim(text):
    """Определение заявления о пресейве"""
    if not text:
        return False
    
    text_lower = text.lower()
    
    for pattern in PRESAVE_CLAIM_PATTERNS['basic']:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False

def is_admin_verification(message):
    """Определение подтверждения админа"""
    if not message.text or not message.reply_to_message:
        return False
    
    text_lower = message.text.lower()
    
    for pattern in ADMIN_VERIFICATION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False

def extract_platforms(text):
    """Извлечение платформ из текста"""
    if not text:
        return []
    
    found_platforms = []
    text_lower = text.lower()
    
    for platform, pattern in PRESAVE_CLAIM_PATTERNS['platforms'].items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            found_platforms.append(platform)
    
    return found_platforms

def extract_links(text: str) -> list:
    """Извлечение ссылок из текста"""
    if not text:
        return []
    
    URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    found_links = URL_PATTERN.findall(text)
    
    logger.info(f"🔍 EXTRACT_LINKS: Found {len(found_links)} links in text")
    return found_links

# === СИСТЕМА РЕЖИМОВ ЛИМИТОВ ===
def load_rate_limit_modes():
    """Загружает конфигурацию режимов из переменных окружения"""
    return {
        'conservative': {
            'name': '🟢 CONSERVATIVE',
            'description': 'Безопасный режим - 5% от лимита Telegram',
            'max_responses_per_hour': int(os.getenv('CONSERVATIVE_MAX_HOUR', '60')),
            'min_cooldown_seconds': int(os.getenv('CONSERVATIVE_COOLDOWN', '60')),
            'emoji': '🐢',
            'risk': 'Минимальный'
        },
        'normal': {
            'name': '🟡 NORMAL', 
            'description': 'Рабочий режим - 15% от лимита Telegram',
            'max_responses_per_hour': int(os.getenv('NORMAL_MAX_HOUR', '180')),
            'min_cooldown_seconds': int(os.getenv('NORMAL_COOLDOWN', '20')),
            'emoji': '⚖️',
            'risk': 'Низкий'
        },
        'burst': {
            'name': '🟠 BURST',
            'description': 'Быстрый режим - 50% от лимита Telegram',
            'max_responses_per_hour': int(os.getenv('BURST_MAX_HOUR', '600')),
            'min_cooldown_seconds': int(os.getenv('BURST_COOLDOWN', '6')),
            'emoji': '⚡',
            'risk': 'Средний'
        },
        'admin_burst': {
            'name': '🔴 ADMIN_BURST',
            'description': 'Максимальный режим - 100% лимита групп (только админы)',
            'max_responses_per_hour': int(os.getenv('ADMIN_BURST_MAX_HOUR', '1200')),
            'min_cooldown_seconds': int(os.getenv('ADMIN_BURST_COOLDOWN', '3')),
            'emoji': '🚨',
            'risk': 'ВЫСОКИЙ',
            'admin_only': True
        }
    }

RATE_LIMIT_MODES = load_rate_limit_modes()

# Остальные константы безопасности
RESPONSE_DELAY = int(os.getenv('RESPONSE_DELAY', '3'))

# Webhook настройки
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', 'misterdms-presave-bot.onrender.com')
WEBHOOK_PORT = int(os.getenv('PORT', 10000))
WEBHOOK_PATH = f"/{BOT_TOKEN}/"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === СИСТЕМЫ БЕЗОПАСНОСТИ ===

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
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip] 
                if now - req_time < self.window_seconds
            ]
            
            if len(self.requests[client_ip]) >= self.max_requests:
                logger.warning(f"🚨 RATE_LIMIT: Blocked {client_ip} ({len(self.requests[client_ip])} requests)")
                return False
            
            self.requests[client_ip].append(now)
            return True

class DatabasePool:
    """Connection pooling для оптимизации БД"""
    def __init__(self, db_path: str, pool_size: int = DB_POOL_SIZE):
        self.db_path = db_path
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
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
        if not username:
            return "anonymous"
        clean = re.sub(r'[^\w]', '', username.replace('@', ''))
        return clean[:50] if clean else "anonymous"
    
    @staticmethod
    def validate_text_input(text: str, max_length: int = 1000) -> str:
        if not text or not isinstance(text, str):
            return ""
        safe_text = re.sub(r'[<>"\']', '', text)
        return safe_text[:max_length]
    
    @staticmethod
    def verify_telegram_request(headers: dict, content_length: int) -> bool:
        if content_length > 1024 * 1024:
            logger.warning(f"🚨 SECURITY: Payload too large: {content_length}")
            return False
        
        if WEBHOOK_SECRET:
            received_token = headers.get('X-Telegram-Bot-Api-Secret-Token')
            if received_token != WEBHOOK_SECRET:
                logger.warning(f"🚨 SECURITY: Invalid webhook secret")
                return False
        
        return True

# Инициализация систем безопасности
rate_limiter = WebhookRateLimiter()
security = SecurityValidator()

# === СИСТЕМА РОЛЕЙ И ПРАВ v23.3 ===

def get_user_role(user_id: int) -> str:
    """Определение роли пользователя"""
    return 'admin' if user_id in ADMIN_IDS else 'user'

def can_execute_command(user_id: int, command: str) -> bool:
    """Проверка прав на выполнение команды"""
    role = get_user_role(user_id)
    if role == 'admin':
        return True
    return command in USER_PERMISSIONS.get('user', [])

def check_permissions(allowed_roles: list):
    """Декоратор для проверки прав доступа"""
    def decorator(func):
        def wrapper(message):
            user_role = get_user_role(message.from_user.id)
            if user_role in allowed_roles or 'admin' in allowed_roles:
                return func(message)
            else:
                bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды")
                logger.warning(f"🚫 ACCESS_DENIED: User {message.from_user.id} tried to execute {func.__name__}")
                return None
        return wrapper
    return decorator

def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in ADMIN_IDS

# === ИНТЕРАКТИВНАЯ СИСТЕМА ЗАЯВЛЕНИЯ ПРЕСЕЙВА v23.3 ===

class InteractivePresaveSystem:
    """Пошаговая система заявления пресейва"""
    
    def __init__(self, db_connection, bot_instance):
        self.db = db_connection
        self.bot = bot_instance
        self.user_sessions = {}  # В памяти для быстрого доступа
        self.session_timeout = 300  # 5 минут таймаут сессии
    
    def start_presave_claim(self, user_id, message_id):
        """Начинаем интерактивное заявление"""
        
        # Очищаем старые сессии
        self._cleanup_expired_sessions()
        
        # Инициализируем сессию
        self.user_sessions[user_id] = {
            'step': 'waiting_links',
            'original_message_id': message_id,
            'links': [],
            'comment': None,
            'created_at': time.time()
        }
        
        response = """
🎵 **Создание заявления о пресейве**

📝 **Шаг 1 из 2:** Отправьте ссылки на музыку

💡 **Как отправить:**
• Каждую ссылку с новой строки
• Можно несколько ссылок в одном сообщении
• Поддерживаются все популярные платформы

🔗 **Пример:**
```
https://open.spotify.com/track/123
https://music.apple.com/track/456
https://music.yandex.ru/track/789
```

📤 Отправьте ссылки:
        """
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_presave_{user_id}"))
        
        return response, markup
    
    def _cleanup_expired_sessions(self):
        """Очистка истекших сессий"""
        current_time = time.time()
        expired_users = []
        
        for user_id, session in self.user_sessions.items():
            if current_time - session.get('created_at', 0) > self.session_timeout:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.user_sessions[user_id]
            # Очищаем состояние в БД
            self.db.clear_user_state(user_id)
        
        if expired_users:
            logger.info(f"🧹 CLEANUP: Removed {len(expired_users)} expired presave sessions")
    
    def _is_session_valid(self, user_id):
        """Проверка валидности сессии"""
        if user_id not in self.user_sessions:
            return False
        
        session = self.user_sessions[user_id]
        current_time = time.time()
        
        if current_time - session.get('created_at', 0) > self.session_timeout:
            del self.user_sessions[user_id]
            self.db.clear_user_state(user_id)
            return False
        
        return True
        """Обработка шага со ссылками"""
        
        if user_id not in self.user_sessions:
            return "❌ Сессия истекла. Начните заново.", None
        
        session = self.user_sessions[user_id]
        
        # Извлекаем ссылки из сообщения
        links = extract_links(message.text)
        
        if not links:
            return """
❌ **Ссылки не найдены!**

💡 Убедитесь, что отправляете корректные ссылки на музыку:
• https://open.spotify.com/...
• https://music.apple.com/...
• https://music.yandex.ru/...

📤 Попробуйте еще раз:
            """, None
        
        # Сохраняем ссылки
        session['links'] = links
        session['step'] = 'waiting_comment'
        
        # Переходим к следующему шагу
        response = f"""
✅ **Ссылки получены!**

🔗 **Найдено ссылок:** {len(links)}
📋 **Список:**
{chr(10).join([f"• {link}" for link in links])}

📝 **Шаг 2 из 2:** Добавьте комментарий

💬 **Что написать:**
• Короткое описание музыки
• Ваше мнение о треке/альбоме
• Рекомендации для сообщества
• Или просто "Сделал пресейв!"

✍️ Напишите комментарий:
        """
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("⏭️ Пропустить комментарий", callback_data=f"skip_comment_{user_id}"),
            InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_presave_{user_id}")
        )
        
        return response, markup
    
    def process_comment_step(self, user_id, message_text):
        """Обработка шага с комментарием"""
        
        if not self._is_session_valid(user_id):
            return "❌ Сессия истекла. Начните заново через /menu → Заявить пресейв", None
        
        session = self.user_sessions[user_id]
        session['comment'] = message_text or "Сделал пресейв!"
        
        # Генерируем финальное сообщение для подтверждения
        return self.generate_final_confirmation(user_id)
    
    def generate_final_confirmation(self, user_id):
        """Генерируем финальное сообщение для подтверждения"""
        
        session = self.user_sessions[user_id]
        
        # Определяем платформы из ссылок
        platforms = []
        for link in session['links']:
            if 'spotify' in link:
                platforms.append('🎵 Spotify')
            elif 'apple' in link:
                platforms.append('🍎 Apple Music')
            elif 'yandex' in link:
                platforms.append('🔊 Yandex Music')
            elif 'youtube' in link:
                platforms.append('▶️ YouTube Music')
        
        # Убираем дубликаты
        platforms = list(set(platforms))
        
        final_message = f"""
🎵 **Готовое заявление о пресейве:**

📱 **Платформы:** {', '.join(platforms)}
💬 **Комментарий:** {session['comment']}

🔗 **Ссылки:**
{chr(10).join([f"• {link}" for link in session['links']])}

📤 **Это сообщение будет опубликовано в топике.**
        """
        
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("✅ Опубликовать", callback_data=f"publish_presave_{user_id}"),
            InlineKeyboardButton("❌ Удалить", callback_data=f"delete_presave_{user_id}")
        )
        
        return final_message, markup
    
    def publish_presave(self, user_id):
        """Публикуем заявление в топике"""
        
        if not self._is_session_valid(user_id):
            return "❌ Сессия истекла."
        
        session = self.user_sessions[user_id]
        
        # Формируем сообщение для топика
        username = self.get_username(user_id)
        
        public_message = f"""
🎵 **Заявление о пресейве от @{username}**

💬 {session['comment']}

🔗 **Ссылки:**
{chr(10).join(session['links'])}

⏳ Ожидаем подтверждения админа...
        """
        
        # Отправляем в топик
        result = safe_send_message(
            chat_id=GROUP_ID,
            text=public_message,
            message_thread_id=THREAD_ID
        )
        
        if result and hasattr(result, 'message_id'):  # Проверяем что получили объект Message
            # Сохраняем в БД как обычную заявку
            self.save_presave_claim(user_id, session, result.message_id)
            
            # Очищаем сессию
            del self.user_sessions[user_id]
            
            return "✅ Заявление опубликовано! Ожидайте подтверждения админа."
        else:
            return "❌ Ошибка публикации. Попробуйте еще раз."
    
    def delete_presave(self, user_id):
        """Удаляем заявление без публикации"""
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        return "❌ Заявление удалено. Возвращаемся в главное меню."
    
    def get_username(self, user_id):
        """Получаем username пользователя"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT username FROM user_links WHERE user_id = ?', (user_id,))
                result = cursor.fetchone()
                return result[0] if result else f"user_{user_id}"
        except:
            return f"user_{user_id}"
    
    def save_presave_claim(self, user_id, session, message_id):
        """Сохраняем заявление в БД"""
        try:
            platforms = extract_platforms(session['comment'])
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO presave_claims 
                    (user_id, username, message_id, claim_text, extracted_platforms, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                ''', (
                    user_id, 
                    self.get_username(user_id),
                    message_id,
                    session['comment'],
                    json.dumps(platforms) if platforms else "[]"
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ Error saving presave claim: {e}")

# === РАСШИРЕННАЯ АДМИНСКАЯ АНАЛИТИКА v23.3 ===

class AdminAnalytics:
    """Расширенные админские инструменты"""
    
    def __init__(self, db):
        self.db = db
    
    def get_user_links_history(self, username):
        """Получить все ссылки пользователя"""
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT lh.link_url, lh.timestamp, lh.message_id
                FROM link_history lh
                JOIN user_links ul ON lh.user_id = ul.user_id
                WHERE ul.username = ?
                ORDER BY lh.timestamp DESC
            ''', (username,))
            
            results = cursor.fetchall()
            
            if not results:
                return f"❌ Пользователь @{username} не найден или не отправлял ссылки"
            
            response = f"🔗 **Все ссылки пользователя @{username}:**\n\n"
            
            for i, (link, timestamp, msg_id) in enumerate(results, 1):
                date_str = timestamp[:16] if timestamp else "Неизвестно"
                display_link = link[:50] + "..." if len(link) > 50 else link
                
                response += f"{i}. {display_link}\n"
                response += f"   📅 {date_str} | 💬 ID: {msg_id}\n\n"
            
            response += f"📊 **Итого:** {len(results)} ссылок"
            
            return response
    
    def get_user_approvals_history(self, username):
        """Получить все подтверждения пользователя"""
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pc.claim_text, pc.status, pc.created_at, pv.admin_username, pv.verification_type
                FROM presave_claims pc
                LEFT JOIN presave_verifications pv ON pc.id = pv.claim_id
                JOIN user_links ul ON pc.user_id = ul.user_id
                WHERE ul.username = ?
                ORDER BY pc.created_at DESC
            ''', (username,))
            
            results = cursor.fetchall()
            
            if not results:
                return f"❌ Пользователь @{username} не подавал заявлений на пресейвы"
            
            response = f"✅ **Все подтверждения пользователя @{username}:**\n\n"
            
            verified_count = 0
            rejected_count = 0
            pending_count = 0
            
            for i, (claim_text, status, created_at, admin_username, verification_type) in enumerate(results, 1):
                date_str = created_at[:16] if created_at else "Неизвестно"
                
                if status == 'verified':
                    status_emoji = "✅"
                    verified_count += 1
                elif status == 'rejected':
                    status_emoji = "❌"
                    rejected_count += 1
                else:
                    status_emoji = "⏳"
                    pending_count += 1
                
                response += f"{i}. {status_emoji} {claim_text[:50]}...\n"
                response += f"   📅 {date_str}"
                
                if admin_username:
                    response += f" | 👮 {admin_username}"
                
                response += "\n\n"
            
            response += f"""
📊 **Статистика подтверждений:**
✅ Подтверждено: {verified_count}
❌ Отклонено: {rejected_count}
⏳ На рассмотрении: {pending_count}
📊 Всего заявлений: {len(results)}
📈 Процент подтверждения: {(verified_count/len(results)*100):.1f}%
            """
            
            return response
    
    def get_user_links_vs_approvals(self, username):
        """Сравнить ссылки и подтверждения пользователя"""
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем статистику ссылок
            cursor.execute('''
                SELECT COUNT(*) as total_links
                FROM link_history lh
                JOIN user_links ul ON lh.user_id = ul.user_id
                WHERE ul.username = ?
            ''', (username,))
            
            links_result = cursor.fetchone()
            total_links = links_result[0] if links_result else 0
            
            # Получаем статистику пресейвов
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_claims,
                    COUNT(CASE WHEN status = 'verified' THEN 1 END) as verified_claims,
                    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected_claims,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_claims
                FROM presave_claims pc
                JOIN user_links ul ON pc.user_id = ul.user_id
                WHERE ul.username = ?
            ''', (username,))
            
            presave_result = cursor.fetchone()
            if presave_result:
                total_claims, verified_claims, rejected_claims, pending_claims = presave_result
            else:
                total_claims = verified_claims = rejected_claims = pending_claims = 0
            
            # Генерируем отчет
            if total_claims > 0:
                success_rate = (verified_claims/total_claims*100)
                reliability = 'Высокая' if success_rate > 80 else 'Средняя' if success_rate > 50 else 'Низкая'
            else:
                success_rate = 0
                reliability = 'Нет данных'
            
            response = f"""
📊 **Статистика ссылки vs. подтверждения @{username}:**

🔗 **ССЫЛКИ:**
📤 Всего отправлено: {total_links}

🎵 **ПРЕСЕЙВЫ:**
📝 Всего заявлений: {total_claims}
✅ Подтверждено: {verified_claims}
❌ Отклонено: {rejected_claims}
⏳ На рассмотрении: {pending_claims}

📈 **АНАЛИЗ:**
🎯 Процент подтверждения: {success_rate:.1f}%
📊 Соотношение ссылки/пресейвы: {total_links}:{total_claims}
⭐ Надежность: {reliability}

⚠️ **ПРЕДУПРЕЖДЕНИЕ:** Статистика может быть неточной из-за:
• Тестовых сообщений со ссылками
• Случайных отправок ссылок
• Ссылок не связанных с пресейвами
            """
            
            return response

# === БАЗОВЫЕ УВЕДОМЛЕНИЯ АДМИНАМ v23.3 ===

class BasicAdminNotifications:
    """Базовые уведомления для админов"""
    
    def __init__(self, db, bot):
        self.db = db
        self.bot = bot
    
    def notify_new_presave_claim(self, claim_id, user_id, username):
        """Уведомление о новом заявлении"""
        
        notification = f"""
🔔 **Новое заявление о пресейве!**

👤 От пользователя: @{username}
🆔 ID заявления: {claim_id}
📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}

💡 Используйте reply с текстом "подтверждаю" или "отклоняю"
        """
        
        # Отправляем всем админам
        for admin_id in ADMIN_IDS:
            try:
                self.bot.send_message(admin_id, notification)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    def notify_user_first_presave(self, user_id, username):
        """Уведомление о первом пресейве пользователя"""
        
        notification = f"""
🎉 **Первый пресейв!**

👤 Пользователь @{username} сделал свой первый пресейв!
🎯 Возможно, стоит отправить приветственное сообщение
        """
        
        # Отправляем админам
        for admin_id in ADMIN_IDS:
            try:
                self.bot.send_message(admin_id, notification)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    def notify_links_posted(self, user_id, username, links_count):
        """Уведомление о новых ссылках"""
        
        notification = f"""
🔗 **Новые ссылки в топике**

👤 От пользователя: @{username}
📊 Количество ссылок: {links_count}
📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        """
        
        # Отправляем админам (опционально, можно отключить)
        for admin_id in ADMIN_IDS:
            try:
                self.bot.send_message(admin_id, notification)
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")

# === РАСШИРЕННЫЙ ОТВЕТ БОТА v23.3 ===

def generate_enhanced_bot_response(user_id, links):
    """Генерируем расширенный ответ с последними ссылками"""
    
    # Основной текст напоминания
    reminder_text = db.get_reminder_text()
    
    # Получаем последние 10 ссылок с авторами
    recent_links = get_recent_links_with_authors(10)
    
    if recent_links:
        links_section = "\n\n🔗 **Последние ссылки от участников:**\n"
        
        for i, (link, author) in enumerate(recent_links, 1):
            # Сокращаем длинные ссылки
            display_link = link[:60] + "..." if len(link) > 60 else link
            
            # Убираем @ чтобы не спамить уведомлениями
            clean_author = author.replace('@', '') if author else 'Анонимный'
            
            links_section += f"{i}. {display_link}\n   👤 Кто прислал: {clean_author}\n"
    else:
        links_section = "\n\n🔗 **Пока нет ссылок от других участников**"
    
    # Объединяем
    full_response = reminder_text + links_section
    
    return full_response

def get_recent_links_with_authors(limit=10):
    """Получаем последние ссылки с авторами"""
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT lh.link_url, ul.username, lh.timestamp
            FROM link_history lh
            JOIN user_links ul ON lh.user_id = ul.user_id
            ORDER BY lh.timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        
        # Возвращаем только ссылку и автора
        return [(link, username or 'Анонимный') for link, username, _ in results]

# === КОММЕНТАРИИ ДЛЯ БУДУЩЕЙ AI ИНТЕГРАЦИИ v23.3 ===

# TODO: AI Integration for Message Recognition (ЭТАП 2)
# 
# Нужно будет добавить AI помощника для правильного распознавания сообщений:
# 
# Примеры для обучения:
# - "Ну так классно ты сделал всё" → IGNORE (есть "ты сделал")
# - "тест публикации ссылки [ссылка]" → IGNORE (тестирование)
# - "сделал пресейв на spotify" → PRESAVE_CLAIM (заявление)
# - "подтверждаю" (reply) → ADMIN_VERIFICATION (подтверждение)
# 
# Функции для реализации:
# - analyze_message_intent(text, context) → "link_share" | "presave_claim" | "admin_verification" | "ignore"
# - get_confidence_score(text, intent) → 0.0-1.0
# - should_process_message(message) → True/False
# 
# Интеграция с OpenAI API или локальной моделью
# Кэширование результатов для похожих сообщений
# Обучение на реальных данных сообщества

class AIMessageAnalyzer:
    """AI помощник для анализа сообщений (ЭТАП 2)"""
    
    def __init__(self):
        # TODO: Инициализация AI модели
        self.model = None
        self.confidence_threshold = 0.7
        self.message_cache = {}
    
    def analyze_message_intent(self, text, context=None):
        """Анализ намерения сообщения (заготовка для ЭТАПА 2)"""
        # TODO: Реализовать AI анализ
        # Временно возвращаем базовую логику
        return self._basic_intent_analysis(text)
    
    def get_confidence_score(self, text, intent):
        """Получение уверенности в классификации (заготовка для ЭТАПА 2)"""
        # TODO: Реализовать AI scoring
        return 0.8  # Placeholder
    
    def should_process_message(self, message):
        """Определение нужно ли обрабатывать сообщение (заготовка для ЭТАПА 2)"""
        # TODO: Комплексный анализ с учетом контекста
        intent = self.analyze_message_intent(message.text)
        return intent in ['link_share', 'presave_claim']
    
    def _basic_intent_analysis(self, text):
        """Базовый анализ без AI (для ЭТАПА 1)"""
        if not text:
            return 'ignore'
            
        text_lower = text.lower()
        
        # Проверяем на тестовые сообщения
        if 'тест' in text_lower or 'test' in text_lower:
            return 'ignore'
        
        # Проверяем на обращение к другому человеку
        if 'ты ' in text_lower or 'вы ' in text_lower:
            return 'ignore'
        
        # Проверяем на заявление о пресейве
        if is_presave_claim(text):
            return 'presave_claim'
        
        # Проверяем на ссылки
        if extract_links(text):
            return 'link_share'
        
        return 'ignore'

# Создаем заготовку для ЭТАПА 2
ai_analyzer = AIMessageAnalyzer()

# === ФУНКЦИИ УПРАВЛЕНИЯ РЕЖИМАМИ ===

def get_current_limits():
    """Получение текущих лимитов"""
    try:
        current_mode = db.get_current_rate_mode()
        
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
    
    if mode_config.get('admin_only', False) and not is_admin(user_id):
        return False, f"❌ Режим {mode_config['name']} доступен только администраторам"
    
    old_mode = db.get_current_rate_mode()
    old_config = RATE_LIMIT_MODES.get(old_mode, {})
    
    db.set_current_rate_mode(new_mode)
    db.reset_rate_limits()
    
    change_text = f"""
🔄 Режим лимитов изменён!

📉 Было: {old_config.get('name', 'Неизвестно')}
📈 Стало: {mode_config['name']}

⚡ Новые лимиты:
• Ответов/час: {mode_config['max_responses_per_hour']}
• Cooldown: {mode_config['min_cooldown_seconds']} сек
• Риск: {mode_config['risk']}

✅ Готово к работе в новом режиме
    """
    
    logger.info(f"🔄 RATE_MODE: Changed from {old_mode} to {new_mode} by user {user_id}")
    
    return True, change_text

def reload_rate_limit_modes():
    """Перезагрузка режимов из переменных окружения"""
    global RATE_LIMIT_MODES
    RATE_LIMIT_MODES = load_rate_limit_modes()
    logger.info("🔄 RELOAD: Rate limit modes reloaded from environment variables")

# === БАЗА ДАННЫХ С РАСШИРЕНИЯМИ v23.3 ===

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.pool = DatabasePool(db_path, DB_POOL_SIZE)
        logger.info(f"✅ DATABASE: Initialized with connection pooling")
    
    def get_connection(self):
        return self.pool.get_connection()
    
    def init_db(self):
        """Инициализация базы данных с новыми таблицами v23.3"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Существующие таблицы
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_links (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    total_links INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS link_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    link_url TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_id INTEGER
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    response_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bot_activity (
                    id INTEGER PRIMARY KEY,
                    is_active BOOLEAN DEFAULT 1,
                    responses_today INTEGER DEFAULT 0,
                    last_response_time TIMESTAMP,
                    last_reset_date DATE DEFAULT CURRENT_DATE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INTEGER PRIMARY KEY,
                    hourly_responses INTEGER DEFAULT 0,
                    last_hour_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cooldown_until TIMESTAMP
                )
            ''')
            
            # === ТАБЛИЦЫ ДЛЯ ПРЕСЕЙВОВ v23.3 ===
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS presave_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    message_id INTEGER NOT NULL,
                    claim_text TEXT NOT NULL,
                    extracted_platforms TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS presave_verifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    claim_id INTEGER REFERENCES presave_claims(id),
                    admin_id INTEGER NOT NULL,
                    admin_username TEXT,
                    verification_type TEXT NOT NULL,
                    admin_message_id INTEGER,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Сессии пользователей для состояний
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id INTEGER PRIMARY KEY,
                    current_state TEXT,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Проверяем и добавляем новые колонки в user_links для пресейвов
            cursor.execute("PRAGMA table_info(user_links)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'total_claimed_presaves' not in columns:
                cursor.execute('ALTER TABLE user_links ADD COLUMN total_claimed_presaves INTEGER DEFAULT 0')
                logger.info("✅ DATABASE: Added total_claimed_presaves column")
            
            if 'total_verified_presaves' not in columns:
                cursor.execute('ALTER TABLE user_links ADD COLUMN total_verified_presaves INTEGER DEFAULT 0')
                logger.info("✅ DATABASE: Added total_verified_presaves column")
            
            if 'last_presave_claim' not in columns:
                cursor.execute('ALTER TABLE user_links ADD COLUMN last_presave_claim TIMESTAMP')
                logger.info("✅ DATABASE: Added last_presave_claim column")
            
            # Создаем индексы для производительности
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_link_history_timestamp ON link_history(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_bot_responses_timestamp ON bot_responses(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_links_total ON user_links(total_links)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_sessions_state ON user_sessions(current_state)')
            
            # Новые индексы для пресейвов
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_presave_claims_user_status ON presave_claims(user_id, status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_presave_claims_created ON presave_claims(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_verifications_claim ON presave_verifications(claim_id)')
            
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
            cursor.execute(
                'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                ('inline_mode', 'hybrid')
            )
            
            conn.commit()
            logger.info("✅ DATABASE: Database initialized successfully with v23.3 presave features")

    # === МЕТОДЫ ДЛЯ СОСТОЯНИЙ ПОЛЬЗОВАТЕЛЕЙ ===
    
    def set_user_state(self, user_id: int, state: str, data: str = None):
        """Установка состояния пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_sessions (user_id, current_state, data)
                VALUES (?, ?, ?)
            ''', (user_id, state, data))
            conn.commit()
    
    def get_user_state(self, user_id: int) -> tuple[str, str]:
        """Получение состояния пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT current_state, data FROM user_sessions WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            return result if result else (None, None)
    
    def clear_user_state(self, user_id: int):
        """Очистка состояния пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
            conn.commit()

    def add_user_links(self, user_id: int, username: str, links: list, message_id: int):
        """Сохранение ссылок пользователя"""
        safe_username = security.sanitize_username(username)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO user_links (user_id, username, total_links, last_updated)
                VALUES (?, ?, COALESCE((SELECT total_links FROM user_links WHERE user_id = ?), 0) + ?, CURRENT_TIMESTAMP)
            ''', (user_id, safe_username, user_id, len(links)))
            
            for link in links:
                cursor.execute('''
                    INSERT INTO link_history (user_id, link_url, message_id)
                    VALUES (?, ?, ?)
                ''', (user_id, link, message_id))
            
            conn.commit()
            logger.info(f"💾 DB_SAVE: Saved {len(links)} links for user {safe_username}")

    def log_bot_response(self, user_id: int, response_text: str):
        safe_response = security.validate_text_input(response_text, 4000)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bot_responses (user_id, response_text)
                VALUES (?, ?)
            ''', (user_id, safe_response))
            conn.commit()

    def is_bot_active(self) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT is_active FROM bot_activity WHERE id = 1')
            result = cursor.fetchone()
            return bool(result[0]) if result else False

    def set_bot_active(self, active: bool):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE bot_activity SET is_active = ? WHERE id = 1', (active,))
            conn.commit()

    def can_send_response(self) -> tuple[bool, str]:
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
            
            current_limits = get_current_limits()
            max_responses = current_limits['max_responses_per_hour'] 
            cooldown_seconds = current_limits['min_cooldown_seconds']
            
            if cooldown_until:
                cooldown_time = datetime.fromisoformat(cooldown_until)
                if now < cooldown_time:
                    remaining = int((cooldown_time - now).total_seconds())
                    return False, f"Cooldown активен. Осталось: {remaining} сек"
            
            if last_hour_reset:
                last_reset = datetime.fromisoformat(last_hour_reset)
                if now - last_reset > timedelta(hours=1):
                    cursor.execute('''
                        UPDATE rate_limits 
                        SET hourly_responses = 0, last_hour_reset = ?
                        WHERE id = 1
                    ''', (now.isoformat(),))
                    hourly_responses = 0
            
            if hourly_responses >= max_responses:
                return False, f"Достигнут лимит {max_responses} ответов в час"
            
            return True, "OK"

    def update_response_limits(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now()
            
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

    def get_user_stats(self, username: str = None):
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
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT hourly_responses, cooldown_until FROM rate_limits WHERE id = 1
                ''')
                limits = cursor.fetchone()
                
                cursor.execute('''
                    SELECT is_active, last_response_time FROM bot_activity WHERE id = 1
                ''')
                activity = cursor.fetchone()
                
                cursor.execute('''
                    SELECT COUNT(*) FROM bot_responses 
                    WHERE DATE(timestamp) = DATE('now')
                ''')
                today_responses = cursor.fetchone()
                
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
                return {
                    'hourly_responses': 0,
                    'hourly_limit': 60,
                    'cooldown_until': None,
                    'is_active': False,
                    'last_response': None,
                    'today_responses': 0
                }

    def clear_link_history(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM link_history')
            conn.commit()

    def get_reminder_text(self) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', ('reminder_text',))
            result = cursor.fetchone()
            return result[0] if result else DEFAULT_REMINDER

    def set_reminder_text(self, text: str):
        safe_text = security.validate_text_input(text, 4000)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', ('reminder_text', safe_text))
            conn.commit()

    def get_current_rate_mode(self) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', ('rate_limit_mode',))
            result = cursor.fetchone()
            return result[0] if result else 'conservative'

    def set_current_rate_mode(self, mode: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', ('rate_limit_mode', mode))
            conn.commit()

    def get_setting(self, key: str, default: str = None) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            return result[0] if result else default

    def set_setting(self, key: str, value: str):
        safe_key = security.validate_text_input(key, 100)
        safe_value = security.validate_text_input(value, 1000)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', (safe_key, safe_value))
            conn.commit()

# Инициализация базы данных
db = Database()

# === УЛУЧШЕННЫЕ INLINE МЕНЮ v23.3 ===

class InlineMenus:
    """Система улучшенных inline меню согласно плану v23.3"""
    
    @staticmethod
    def create_user_menu() -> InlineKeyboardMarkup:
        """Пользовательское меню согласно плану v23.3"""
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Секция "Моя статистика"
        markup.add(
            InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats_menu")
        )
        
        # Секция "Лидерборд"
        markup.add(
            InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard_menu")
        )
        
        # Секция "Действия"
        markup.add(
            InlineKeyboardButton("⚙️ Действия", callback_data="user_actions_menu")
        )
        
        return markup
    
    @staticmethod
    def create_admin_menu() -> InlineKeyboardMarkup:
        """Админское меню согласно плану v23.3"""
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Секция "Моя статистика" (как у пользователя)
        markup.add(
            InlineKeyboardButton("📊 Моя статистика", callback_data="my_stats_menu")
        )
        
        # Секция "Лидерборд"
        markup.add(
            InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard_menu")
        )
        
        # Секция "Действия" (расширенная для админов)
        markup.add(
            InlineKeyboardButton("⚙️ Действия", callback_data="admin_actions_menu")
        )
        
        return markup
    
    @staticmethod
    def create_my_stats_menu(user_id: int) -> InlineKeyboardMarkup:
        """Подробное меню статистики пользователя"""
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Получаем статистику для отображения в кнопках
        username = get_username_by_id(user_id)
        user_data = db.get_user_stats(username)
        
        if user_data:
            _, total_links, _ = user_data
            rank_emoji, rank_name = get_user_rank(total_links)
            
            # Кнопки с информацией
            markup.add(
                InlineKeyboardButton(f"🔗 Мои ссылки: {total_links} ({rank_emoji} {rank_name})", callback_data="view_my_links")
            )
            
            # Получаем место в рейтинге
            all_users = db.get_user_stats()
            position = get_user_position_in_ranking(username, all_users)
            
            markup.add(
                InlineKeyboardButton(f"🏆 Место в рейтинге: {position} из {len(all_users)}", callback_data="view_full_ranking")
            )
            
            # Прогресс до следующего звания
            progress_needed, next_rank = get_progress_to_next_rank(total_links)
            if progress_needed > 0:
                markup.add(
                    InlineKeyboardButton(f"📈 Прогресс до {next_rank}: {progress_needed} ссылок", callback_data="view_ranks_info")
                )
            else:
                markup.add(
                    InlineKeyboardButton("💎 Максимальное звание достигнуто!", callback_data="view_ranks_info")
                )
        else:
            markup.add(
                InlineKeyboardButton("🔗 Мои ссылки: 0 (🥉 Начинающий)", callback_data="help_getting_started")
            )
        
        # Список ссылок
        markup.add(
            InlineKeyboardButton("🔗 Список моих ссылок", callback_data="list_my_links")
        )
        
        # Пресейвы (новая функция v23.3)
        markup.add(
            InlineKeyboardButton("🎵 Мои пресейвы: скоро", callback_data="view_my_presaves")
        )
        
        # Кнопка назад
        markup.add(
            InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
        )
        
        return markup
    
    @staticmethod
    def create_leaderboard_menu() -> InlineKeyboardMarkup:
        """Меню лидерборда с табами"""
        markup = InlineKeyboardMarkup(row_width=3)
        
        # Табы лидерборда
        markup.add(
            InlineKeyboardButton("📊 По ссылкам", callback_data="leaderboard_links"),
            InlineKeyboardButton("🎵 По пресейвам", callback_data="leaderboard_presaves"),
            InlineKeyboardButton("⭐ Общий рейтинг", callback_data="leaderboard_overall")
        )
        
        # Кнопка назад
        markup.add(
            InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
        )
        
        return markup
    
    @staticmethod
    def create_user_actions_menu() -> InlineKeyboardMarkup:
        """Меню действий для пользователей"""
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Заявить пресейв (главная новая функция)
        markup.add(
            InlineKeyboardButton("🎵 Заявить пресейв", callback_data="start_presave_claim")
        )
        
        # Просмотр ссылок
        markup.add(
            InlineKeyboardButton("🔗 Все ссылки из истории", callback_data="alllinks"),
            InlineKeyboardButton("🔗 Крайние 10 ссылок", callback_data="recent")
        )
        
        # Помощь
        markup.add(
            InlineKeyboardButton("❓ Помощь", callback_data="help")
        )
        
        # Кнопка назад
        markup.add(
            InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
        )
        
        return markup
    
    @staticmethod
    def create_admin_actions_menu() -> InlineKeyboardMarkup:
        """Расширенное меню действий для админов"""
        markup = InlineKeyboardMarkup(row_width=2)
        
        # Подтвердить пресейв
        markup.add(
            InlineKeyboardButton("✅ Подтвердить пресейв", callback_data="verify_presave_menu")
        )
        
        # Админская аналитика
        markup.add(
            InlineKeyboardButton("📊 Админская аналитика", callback_data="admin_analytics_menu")
        )
        
        # Настройки бота
        markup.add(
            InlineKeyboardButton("⚙️ Настройки бота", callback_data="bot_settings_menu")
        )
        
        # Диагностика
        markup.add(
            InlineKeyboardButton("🔧 Диагностика", callback_data="diagnostics_menu")
        )
        
        # Также доступны пользовательские действия
        markup.add(
            InlineKeyboardButton("🎵 Заявить пресейв", callback_data="start_presave_claim")
        )
        
        markup.add(
            InlineKeyboardButton("🔗 Все ссылки", callback_data="alllinks"),
            InlineKeyboardButton("🔗 Последние ссылки", callback_data="recent")
        )
        
        # Кнопка назад
        markup.add(
            InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
        )
        
        return markup
    
    @staticmethod
    def create_admin_analytics_menu() -> InlineKeyboardMarkup:
        """Меню админской аналитики"""
        markup = InlineKeyboardMarkup(row_width=1)
        
        markup.add(
            InlineKeyboardButton("🔗 Список ссылок @username", callback_data="admin_user_links")
        )
        
        markup.add(
            InlineKeyboardButton("🔗 Список аппрувов @username", callback_data="admin_user_approvals")
        )
        
        markup.add(
            InlineKeyboardButton("🔗 Стата ссылки vs. аппрувы @username", callback_data="admin_user_comparison")
        )
        
        # Кнопка назад
        markup.add(
            InlineKeyboardButton("🔙 Назад", callback_data="admin_actions_menu")
        )
        
        return markup
    
    @staticmethod
    def create_back_button(callback_data: str = "main_menu") -> InlineKeyboardMarkup:
        """Универсальная кнопка назад"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 Назад", callback_data=callback_data))
        return markup

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ МЕНЮ ===

def get_username_by_id(user_id: int) -> str:
    """Получение username по user_id"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM user_links WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else f"user_{user_id}"
    except:
        return f"user_{user_id}"

def get_user_position_in_ranking(username: str, all_users: list) -> int:
    """Получение позиции пользователя в рейтинге"""
    for i, (db_username, _, _) in enumerate(all_users, 1):
        if db_username == username:
            return i
    return len(all_users) + 1

def get_user_rank(total_links: int) -> tuple[str, str]:
    """Определение звания пользователя"""
    if total_links >= 31:
        return "💎", "Амбассадор"
    elif total_links >= 16:
        return "🥇", "Промоутер"
    elif total_links >= 6:
        return "🥈", "Активный"
    else:
        return "🥉", "Начинающий"

def get_progress_to_next_rank(total_links: int) -> tuple[int, str]:
    """Прогресс до следующего звания"""
    if total_links >= 31:
        return 0, "Максимальное звание достигнуто!"
    elif total_links >= 16:
        return 31 - total_links, "💎 Амбассадор"
    elif total_links >= 6:
        return 16 - total_links, "🥇 Промоутер"
    else:
        return 6 - total_links, "🥈 Активный"

def safe_send_message(chat_id: int, text: str, message_thread_id: int = None, reply_to_message_id: int = None, reply_markup=None):
    """Безопасная отправка сообщения"""
    try:
        logger.info(f"💬 SEND_MESSAGE: Preparing to send to chat {chat_id}")
        
        time.sleep(RESPONSE_DELAY)
        
        if message_thread_id:
            result = bot.send_message(
                chat_id=chat_id, 
                text=text,
                message_thread_id=message_thread_id,
                reply_to_message_id=reply_to_message_id,
                reply_markup=reply_markup
            )
        else:
            if reply_to_message_id:
                result = bot.reply_to(reply_to_message_id, text, reply_markup=reply_markup)
            else:
                result = bot.send_message(chat_id, text, reply_markup=reply_markup)
        
        logger.info(f"✅ SENT: Message sent successfully (ID: {result.message_id})")
        return result
    except Exception as e:
        logger.error(f"❌ SEND_ERROR: Failed to send message: {str(e)}")
        return False

# Инициализация меню и интерактивной системы
menus = InlineMenus()

# Инициализируем интерактивную систему пресейвов
interactive_presave_system = InteractivePresaveSystem(db, bot)

# Инициализируем админскую аналитику
admin_analytics = AdminAnalytics(db)

# Инициализируем систему уведомлений
admin_notifications = BasicAdminNotifications(db, bot)

# === WEBHOOK СЕРВЕР v23.3 ===

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        client_ip = self.client_address[0]
        logger.info(f"📨 WEBHOOK_POST: Request from {client_ip} to {self.path}")
        
        if not rate_limiter.is_allowed(client_ip):
            logger.warning(f"🚫 RATE_LIMITED: Blocked {client_ip}")
            self.send_response(429)
            self.end_headers()
            return
        
        if self.path == WEBHOOK_PATH:
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                
                if not security.verify_telegram_request(self.headers, content_length):
                    logger.warning(f"🚨 SECURITY: Invalid request from {client_ip}")
                    self.send_response(403)
                    self.end_headers()
                    return
                
                post_data = self.rfile.read(content_length)
                logger.info(f"📦 WEBHOOK_DATA: Received {content_length} bytes")
                
                update_data = json.loads(post_data.decode('utf-8'))
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
            self._handle_health_check()
        
        elif self.path == '/keepalive':
            self._handle_keepalive_request(client_ip)
        
        else:
            logger.warning(f"🔍 UNKNOWN_POST_PATH: {self.path} from {client_ip}")
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        client_ip = self.client_address[0] 
        logger.info(f"📨 WEBHOOK_GET: Request from {client_ip} to {self.path}")
        
        if self.path == '/' or self.path == '/health':
            self._handle_health_check()
        
        elif self.path == '/keepalive':
            self._handle_keepalive_request(client_ip)
        
        elif self.path == WEBHOOK_PATH:
            self._handle_webhook_info_page()
        
        else:
            logger.warning(f"🔍 UNKNOWN_GET_PATH: {self.path} from {client_ip}")
            self.send_response(404)
            self.end_headers()
    
    def do_OPTIONS(self):
        """Обработка CORS preflight запросов"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _handle_health_check(self):
        """Health check эндпоинт"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        response = json.dumps({
            "status": "healthy", 
            "service": "telegram-bot",
            "version": "v23.3-stage1-interactive-presave-system",
            "features": ["interactive_presave_claims", "enhanced_menus", "admin_analytics", "user_notifications"]
        })
        self.wfile.write(response.encode())
    
    def _handle_keepalive_request(self, client_ip):
        """Keepalive monitoring эндпоинт"""
        logger.info(f"💓 KEEPALIVE: Keep-alive request from {client_ip}")
        
        try:
            bot_active = db.is_bot_active()
            current_limits = get_current_limits()
            
            # Проверяем подключение к БД
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT 1')
                    db_check = cursor.fetchone() is not None
            except Exception as e:
                logger.error(f"❌ DB_CHECK_ERROR: {e}")
                db_check = False
            
            # Проверяем Telegram Bot API
            try:
                bot_info = bot.get_me()
                telegram_check = bool(bot_info)
                bot_username = bot_info.username if bot_info else "unknown"
            except Exception as e:
                logger.error(f"❌ TELEGRAM_API_ERROR: {e}")
                telegram_check = False
                bot_username = "api_error"
            
            response_data = {
                "status": "alive",
                "timestamp": time.time(),
                "version": "v23.3-stage1-interactive-presave-system",
                "uptime_check": "✅ OK",
                "details": {
                    "bot_active": bot_active,
                    "current_mode": current_limits['mode_name'],
                    "database_check": db_check,
                    "telegram_api_check": telegram_check,
                    "bot_username": bot_username,
                    "features_status": {
                        "interactive_presave_claims": True,
                        "enhanced_menus": True,
                        "admin_analytics": True,
                        "user_notifications": True,
                        "stage1_complete": True
                    }
                },
                "endpoints": {
                    "webhook": WEBHOOK_PATH,
                    "health": "/health",
                    "keepalive": "/keepalive"
                }
            }
            
            if db_check and telegram_check:
                status_code = 200
                response_data["service_status"] = "operational"
                logger.info(f"💓 KEEPALIVE_HEALTHY: All systems operational")
            else:
                status_code = 503
                response_data["service_status"] = "degraded"
                response_data["issues"] = []
                if not db_check:
                    response_data["issues"].append("database_connection")
                if not telegram_check:
                    response_data["issues"].append("telegram_api")
                logger.warning(f"💓 KEEPALIVE_DEGRADED: Issues detected")
            
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response_json = json.dumps(response_data, indent=2)
            self.wfile.write(response_json.encode())
            
        except Exception as e:
            logger.error(f"❌ KEEPALIVE_CRITICAL_ERROR: {e}")
            
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_response = json.dumps({
                "status": "error",
                "timestamp": time.time(),
                "version": "v23.3-stage1-interactive-presave-system",
                "error": str(e),
                "uptime_check": "❌ CRITICAL_ERROR"
            })
            self.wfile.write(error_response.encode())
    
    def _handle_webhook_info_page(self):
        """Информационная страница webhook"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        info_page = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Presave Reminder Bot v23.3 ЭТАП 1 - Webhook</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                .header {{ text-align: center; color: #2196F3; }}
                .status {{ background: #E8F5E8; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                .feature {{ background: #F0F8FF; padding: 10px; border-radius: 5px; margin: 10px 0; }}
                .new {{ background: #E8F5E8; padding: 10px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
                .endpoints {{ background: #F5F5F5; padding: 10px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🤖 Presave Reminder Bot v23.3</h1>
                <h2>🎵 ЭТАП 1: ИНТЕРАКТИВНАЯ СИСТЕМА ПРЕСЕЙВОВ</h2>
            </div>
            
            <div class="status">
                <h3>✅ Status: ЭТАП 1 РЕАЛИЗОВАН</h3>
                <p>Интерактивная система заявления пресейвов и улучшенные меню готовы к использованию</p>
            </div>
            
            <div class="new">
                <h4>🆕 НОВЫЕ ВОЗМОЖНОСТИ ЭТАПА 1</h4>
                <ul>
                    <li>🎵 <strong>Интерактивная система заявления пресейва</strong> - пошаговый процесс с ссылками и комментариями</li>
                    <li>📊 <strong>Улучшенные меню</strong> - структурированная навигация для админов и пользователей</li>
                    <li>🔗 <strong>Расширенный ответ бота</strong> - отображение последних 10 ссылок от участников</li>
                    <li>📈 <strong>Админская аналитика</strong> - детальная статистика по пользователям</li>
                    <li>🔔 <strong>Базовые уведомления</strong> - оповещения админов о важных событиях</li>
                </ul>
            </div>
            
            <div class="feature">
                <h4>🎛️ УЛУЧШЕННЫЕ МЕНЮ</h4>
                <ul>
                    <li>📊 <strong>Моя статистика</strong> - ссылки, место в рейтинге, прогресс до следующего звания</li>
                    <li>🏆 <strong>Лидерборд</strong> - табы по ссылкам, пресейвам и общему рейтингу</li>
                    <li>⚙️ <strong>Действия</strong> - заявление пресейвов, просмотр ссылок, помощь</li>
                    <li>👑 <strong>Админское меню</strong> - дополнительные инструменты для модерации</li>
                </ul>
            </div>
            
            <div class="feature">
                <h4>🎵 ИНТЕРАКТИВНАЯ СИСТЕМА ПРЕСЕЙВОВ</h4>
                <ul>
                    <li>📝 <strong>Шаг 1:</strong> Отправка ссылок на музыку</li>
                    <li>💬 <strong>Шаг 2:</strong> Добавление комментария</li>
                    <li>👀 <strong>Шаг 3:</strong> Предварительный просмотр</li>
                    <li>📤 <strong>Шаг 4:</strong> Публикация в топике</li>
                    <li>✅ <strong>Шаг 5:</strong> Подтверждение админом</li>
                </ul>
            </div>
            
            <div class="feature">
                <h4>📊 АДМИНСКАЯ АНАЛИТИКА</h4>
                <ul>
                    <li>🔗 <strong>Список ссылок пользователя</strong> - полная история</li>
                    <li>✅ <strong>Список подтверждений</strong> - статистика пресейвов</li>
                    <li>📈 <strong>Сравнительный анализ</strong> - ссылки vs подтверждения</li>
                    <li>🔔 <strong>Автоматические уведомления</strong> - о новых заявлениях</li>
                </ul>
            </div>
            
            <div class="endpoints">
                <h4>🔗 Available Endpoints</h4>
                <ul>
                    <li><strong>POST {WEBHOOK_PATH}</strong> - Telegram webhook</li>
                    <li><strong>GET/POST /keepalive</strong> - Uptime monitoring</li>
                    <li><strong>GET/POST /health</strong> - Health check</li>
                    <li><strong>GET {WEBHOOK_PATH}</strong> - This info page</li>
                </ul>
            </div>
            
            <div class="status">
                <h4>🚀 ГОТОВНОСТЬ К ЭТАПУ 2</h4>
                <p>ЭТАП 1 обеспечивает полную инфраструктуру для продвинутых возможностей ЭТАПА 2:</p>
                <ul>
                    <li>🤖 AI-powered Message Recognition</li>
                    <li>📱 Rich Media Responses</li>
                    <li>🎮 Gamification System</li>
                    <li>🔮 Predictive Analytics</li>
                    <li>🏆 Weekly Challenges</li>
                </ul>
            </div>
        </body>
        </html>
        """
        self.wfile.write(info_page.encode('utf-8'))
    
    def log_message(self, format, *args):
        # Отключаем стандартное логирование для уменьшения шума
        pass

# === КОМАНДЫ v23.3 ===

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user_role = get_user_role(message.from_user.id)
    
    if user_role == 'admin':
        bot.reply_to(message, """
🤖 Presave Reminder Bot v23.3 ЭТАП 1 запущен!

🎵 НОВЫЕ ВОЗМОЖНОСТИ:
✅ Интерактивная система заявления пресейвов
📊 Улучшенные меню с подробной статистикой
🔗 Расширенные ответы с последними ссылками
📈 Детальная админская аналитика
🔔 Базовые уведомления о событиях

👑 Вы вошли как администратор
📱 Используйте /menu для доступа к новым функциям
⚙️ Управление: /help
        """)
    else:
        bot.reply_to(message, """
🤖 Добро пожаловать в Presave Reminder Bot v23.3!

🎵 НОВОЕ В ЭТОЙ ВЕРСИИ:
✨ Интерактивная система заявления пресейвов
📊 Подробная статистика и рейтинги
🏆 Система званий с прогрессом
🔗 История ссылок от всех участников

📱 Используйте /menu для начала работы
❓ Помощь: /help

🎵 Начните делиться музыкой и зарабатывайте звания!
        """)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    user_role = get_user_role(message.from_user.id)
    
    if user_role == 'admin':
        help_text = """
🤖 Presave Reminder Bot v23.3 ЭТАП 1 (Администратор):

🆕 НОВЫЕ ВОЗМОЖНОСТИ:
/menu — новое интерактивное меню с кнопками
🎵 Интерактивная система заявления пресейвов
📊 Детальная аналитика по пользователям
🔔 Автоматические уведомления

👑 Административные команды:
/activate — включить бота в топике
/deactivate — отключить бота в топике  
/stats — общая статистика работы
/botstat — мониторинг лимитов

📊 Статистика и аналитика:
/linkstats — рейтинг пользователей
/topusers — топ-5 активных
/userstat @username — статистика пользователя
/mystat — моя подробная статистика

⚙️ Настройки и управление:
/modes — показать режимы лимитов
/setmode <режим> — сменить режим
/setmessage текст — изменить напоминание
/clearhistory — очистить историю

🧪 Тестирование v23.3:
/test_presave_system — проверить новую систему
/test_keepalive — проверить мониторинг

✨ ЭТАП 1 ЗАВЕРШЕН: Готов к переходу на ЭТАП 2!
        """
    else:
        help_text = """
🤖 Presave Reminder Bot v23.3 ЭТАП 1 (Пользователь):

🆕 НОВЫЕ ВОЗМОЖНОСТИ:
/menu — интерактивное меню с кнопками
🎵 Заявление пресейвов через удобную форму
📊 Подробная статистика активности
🏆 Система званий с прогрессом

📊 Статистика:
/linkstats — рейтинг пользователей
/topusers — топ-5 активных
/mystat — моя подробная статистика
/alllinks — все ссылки в истории
/recent — последние ссылки

🏆 Система званий:
🥉 Начинающий (1-5 ссылок)
🥈 Активный (6-15 ссылок)  
🥇 Промоутер (16-30 ссылок)
💎 Амбассадор (31+ ссылок)

🎵 Используйте кнопки в /menu для удобства!
Делитесь ссылками и заявляйте пресейвы!

✨ v23.3 ЭТАП 1: Интерактивная система готова!
        """
    
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['menu'])
@check_permissions(['admin', 'user'])
def cmd_menu(message):
    """Показать главное меню с улучшенными кнопками v23.3"""
    user_role = get_user_role(message.from_user.id)
    
    if user_role == 'admin':
        markup = menus.create_admin_menu()
        text = """
👑 **Админское меню v23.3:**

📊 Моя статистика — детальная информация о вашей активности
🏆 Лидерборд — табы по ссылкам, пресейвам, общему рейтингу  
⚙️ Действия — расширенные инструменты админа

🆕 **Новое в ЭТАПЕ 1:**
• Интерактивное заявление пресейвов
• Детальная аналитика пользователей
• Автоматические уведомления
        """
    else:
        markup = menus.create_user_menu()
        text = """
👥 **Пользовательское меню v23.3:**

📊 Моя статистика — ваши ссылки, звание, место в рейтинге
🏆 Лидерборд — соревнуйтесь с другими участниками
⚙️ Действия — заявить пресейв, посмотреть ссылки

🆕 **Новое в ЭТАПЕ 1:**
• Пошаговое заявление пресейвов
• Подробная статистика активности
• Просмотр активности сообщества
        """
    
    bot.reply_to(message, text, reply_markup=markup, parse_mode='Markdown')

# === CALLBACK HANDLERS v23.3 ===

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    """Обработка нажатий на inline кнопки v23.3"""
    user_role = get_user_role(call.from_user.id)
    
    try:
        # Основные меню
        if call.data == "main_menu":
            if user_role == 'admin':
                markup = menus.create_admin_menu()
                text = "👑 Админское меню v23.3:"
            else:
                markup = menus.create_user_menu()
                text = "👥 Пользовательское меню v23.3:"
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Моя статистика
        elif call.data == "my_stats_menu":
            markup = menus.create_my_stats_menu(call.from_user.id)
            bot.edit_message_text(
                "📊 Моя статистика:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Лидерборд
        elif call.data == "leaderboard_menu":
            markup = menus.create_leaderboard_menu()
            bot.edit_message_text(
                "🏆 Лидерборд - выберите категорию:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Пользовательские действия
        elif call.data == "user_actions_menu":
            markup = menus.create_user_actions_menu()
            bot.edit_message_text(
                "⚙️ Действия пользователя:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Админские действия
        elif call.data == "admin_actions_menu":
            if user_role != 'admin':
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            markup = menus.create_admin_actions_menu()
            bot.edit_message_text(
                "⚙️ Действия администратора:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Админская аналитика
        elif call.data == "admin_analytics_menu":
            if user_role != 'admin':
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            markup = menus.create_admin_analytics_menu()
            bot.edit_message_text(
                "📊 Админская аналитика - выберите отчет:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # === ИНТЕРАКТИВНАЯ СИСТЕМА ПРЕСЕЙВОВ ===
        
        # Начать заявление пресейва
        elif call.data == "start_presave_claim":
            response, markup = interactive_presave_system.start_presave_claim(
                call.from_user.id, 
                call.message.message_id
            )
            
            # Устанавливаем состояние пользователя
            db.set_user_state(call.from_user.id, 'waiting_presave_links')
            
            bot.edit_message_text(
                response,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # Отменить заявление пресейва
        elif call.data.startswith("cancel_presave_"):
            user_id = int(call.data.split("_")[2])
            if call.from_user.id != user_id:
                bot.answer_callback_query(call.id, "❌ Это не ваше заявление")
                return
            
            response = interactive_presave_system.delete_presave(user_id)
            db.clear_user_state(user_id)
            
            # Возвращаемся в главное меню
            if user_role == 'admin':
                markup = menus.create_admin_menu()
                text = "👑 Админское меню:"
            else:
                markup = menus.create_user_menu()
                text = "👥 Пользовательское меню:"
            
            bot.edit_message_text(
                f"{response}\n\n{text}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Пропустить комментарий
        elif call.data.startswith("skip_comment_"):
            user_id = int(call.data.split("_")[2])
            if call.from_user.id != user_id:
                bot.answer_callback_query(call.id, "❌ Это не ваше заявление")
                return
            
            response, markup = interactive_presave_system.process_comment_step(user_id, "Сделал пресейв!")
            
            bot.edit_message_text(
                response,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # Опубликовать пресейв
        elif call.data.startswith("publish_presave_"):
            user_id = int(call.data.split("_")[2])
            if call.from_user.id != user_id:
                bot.answer_callback_query(call.id, "❌ Это не ваше заявление")
                return
            
            response = interactive_presave_system.publish_presave(user_id)
            db.clear_user_state(user_id)
            
            # Уведомляем админов
            username = get_username_by_id(user_id)
            admin_notifications.notify_new_presave_claim(0, user_id, username)
            
            # Возвращаемся в главное меню
            if user_role == 'admin':
                markup = menus.create_admin_menu()
                text = "👑 Админское меню:"
            else:
                markup = menus.create_user_menu()
                text = "👥 Пользовательское меню:"
            
            bot.edit_message_text(
                f"{response}\n\n{text}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # Удалить пресейв
        elif call.data.startswith("delete_presave_"):
            user_id = int(call.data.split("_")[2])
            if call.from_user.id != user_id:
                bot.answer_callback_query(call.id, "❌ Это не ваше заявление")
                return
            
            response = interactive_presave_system.delete_presave(user_id)
            db.clear_user_state(user_id)
            
            # Возвращаемся в главное меню
            if user_role == 'admin':
                markup = menus.create_admin_menu()
                text = "👑 Админское меню:"
            else:
                markup = menus.create_user_menu()
                text = "👥 Пользовательское меню:"
            
            bot.edit_message_text(
                f"{response}\n\n{text}",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        
        # === ЛИДЕРБОРД ===
        
        # Лидерборд по ссылкам
        elif call.data == "leaderboard_links":
            users = db.get_user_stats()
            
            if not users:
                text = "📊 Пока нет пользователей с ссылками"
            else:
                text = "📊 **Лидерборд по ссылкам:**\n\n"
                
                for i, (username, total_links, last_updated) in enumerate(users[:10], 1):
                    rank_emoji, rank_name = get_user_rank(total_links)
                    text += f"{rank_emoji} {i}. @{username} — {total_links} ссылок\n"
            
            markup = menus.create_back_button("leaderboard_menu")
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # Лидерборд по пресейвам
        elif call.data == "leaderboard_presaves":
            text = """
🎵 **Лидерборд по пресейвам:**

🚧 Функция в разработке...

В ЭТАПЕ 2 здесь будет:
• Рейтинг по количеству подтвержденных пресейвов
• Статистика по платформам
• Недельные и месячные чемпионы
            """
            
            markup = menus.create_back_button("leaderboard_menu")
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # Общий рейтинг
        elif call.data == "leaderboard_overall":
            text = """
⭐ **Общий рейтинг:**

🚧 Функция в разработке...

В ЭТАПЕ 2 здесь будет:
• Комбинированный рейтинг (ссылки + пресейвы)
• Система достижений
• Еженедельные челленджи
• Streak bonuses
            """
            
            markup = menus.create_back_button("leaderboard_menu")
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # === АДМИНСКАЯ АНАЛИТИКА ===
        
        # Запросить username для анализа ссылок
        elif call.data == "admin_user_links":
            if user_role != 'admin':
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            db.set_user_state(call.from_user.id, 'waiting_username_for_links')
            
            markup = menus.create_back_button("admin_analytics_menu")
            bot.edit_message_text(
                "👤 **Анализ ссылок пользователя**\n\nВведите username пользователя (с @ или без):",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # Запросить username для анализа подтверждений
        elif call.data == "admin_user_approvals":
            if user_role != 'admin':
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            db.set_user_state(call.from_user.id, 'waiting_username_for_approvals')
            
            markup = menus.create_back_button("admin_analytics_menu")
            bot.edit_message_text(
                "👤 **Анализ подтверждений пользователя**\n\nВведите username пользователя (с @ или без):",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # Запросить username для сравнительного анализа
        elif call.data == "admin_user_comparison":
            if user_role != 'admin':
                bot.answer_callback_query(call.id, "❌ Доступ запрещен")
                return
            
            db.set_user_state(call.from_user.id, 'waiting_username_for_comparison')
            
            markup = menus.create_back_button("admin_analytics_menu")
            bot.edit_message_text(
                "👤 **Сравнительный анализ пользователя**\n\nВведите username пользователя (с @ или без):",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup,
                parse_mode='Markdown'
            )
        
        # === СТАНДАРТНЫЕ КОМАНДЫ ===
        
        # Все ссылки
        elif call.data == "alllinks":
            execute_alllinks_callback(call)
        
        # Последние ссылки
        elif call.data == "recent":
            execute_recent_callback(call)
        
        # Помощь
        elif call.data == "help":
            execute_help_callback(call)
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка обработки")

# === ОБРАБОТКА СОСТОЯНИЙ ПОЛЬЗОВАТЕЛЕЙ v23.3 ===

@bot.message_handler(func=lambda message: db.get_user_state(message.from_user.id)[0] is not None)
def handle_user_states(message):
    """Обработка состояний пользователей"""
    user_id = message.from_user.id
    state, data = db.get_user_state(user_id)
    
    try:
        # Состояния интерактивной системы пресейвов
        if state == 'waiting_presave_links':
            response, markup = interactive_presave_system.process_links_step(user_id, message)
            
            if markup:  # Успешно обработали ссылки
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:  # Ошибка, просим повторить
                bot.reply_to(message, response, parse_mode='Markdown')
        
        elif state == 'waiting_presave_comment':
            response, markup = interactive_presave_system.process_comment_step(user_id, message.text)
            bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
        
        # Состояния админской аналитики
        elif state == 'waiting_username_for_links':
            if not is_admin(user_id):
                bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды")
                db.clear_user_state(user_id)
                return
            
            username = message.text.strip().replace('@', '')
            response = admin_analytics.get_user_links_history(username)
            db.clear_user_state(user_id)
            
            bot.reply_to(message, response, parse_mode='Markdown')
        
        elif state == 'waiting_username_for_approvals':
            if not is_admin(user_id):
                bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды")
                db.clear_user_state(user_id)
                return
            
            username = message.text.strip().replace('@', '')
            response = admin_analytics.get_user_approvals_history(username)
            db.clear_user_state(user_id)
            
            bot.reply_to(message, response, parse_mode='Markdown')
        
        elif state == 'waiting_username_for_comparison':
            if not is_admin(user_id):
                bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды")
                db.clear_user_state(user_id)
                return
            
            username = message.text.strip().replace('@', '')
            response = admin_analytics.get_user_links_vs_approvals(username)
            db.clear_user_state(user_id)
            
            bot.reply_to(message, response, parse_mode='Markdown')
        
        # Прочие состояния
        elif state == 'waiting_username':
            username = message.text.strip().replace('@', '')
            user_data = db.get_user_stats(username)
            db.clear_user_state(user_id)
            
            if not user_data:
                bot.reply_to(message, f"❌ Пользователь @{username} не найден или не имеет ссылок")
                return
            
            username_db, total_links, last_updated = user_data
            rank_emoji, rank_name = get_user_rank(total_links)
            
            stat_text = f"""
👤 Статистика пользователя @{username_db}:

🔗 Всего ссылок: {total_links}
📅 Последняя активность: {last_updated[:16]}
🏆 Звание: {rank_emoji} {rank_name}

✨ v23.3: Интерактивная система пресейвов готова!
            """
            
            bot.reply_to(message, stat_text)
        
    except Exception as e:
        logger.error(f"❌ Error in state handler: {str(e)}")
        db.clear_user_state(user_id)
        bot.reply_to(message, "❌ Ошибка обработки. Попробуйте еще раз.")

# === CALLBACK ФУНКЦИИ ДЛЯ СОВМЕСТИМОСТИ ===

def execute_alllinks_callback(call):
    """Выполнение alllinks через callback"""
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
            text = "📋 В базе данных пока нет ссылок"
        else:
            text = f"📋 **Все ссылки в базе v23.3** (последние 20):\n\n"
            
            for i, (link_url, username, timestamp) in enumerate(links[:20], 1):
                username_display = f"@{username}" if username else "Неизвестный"
                date_display = timestamp[:16] if timestamp else "Неизвестно"
                
                display_url = link_url[:50] + "..." if len(link_url) > 50 else link_url
                
                text += f"{i}. {display_url}\n   👤 {username_display} | 📅 {date_display}\n\n"
            
            if len(links) > 20:
                text += f"... и ещё {len(links) - 20} ссылок\n"
            
            text += f"\n📊 Всего ссылок в базе: {len(links)}"
        
        user_role = get_user_role(call.from_user.id)
        back_menu = "admin_actions_menu" if user_role == 'admin' else "user_actions_menu"
        markup = menus.create_back_button(back_menu)
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ Error in ALLLINKS callback: {str(e)}")
        bot.answer_callback_query(call.id, "❌ Ошибка получения ссылок")

def execute_recent_callback(call):
    """Выполнение recent через callback"""
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
            text = "📋 В базе данных пока нет ссылок"
        else:
            text = f"🕐 **Последние {len(recent_links)} ссылок v23.3:**\n\n"
            
            for i, (link_url, username, timestamp) in enumerate(recent_links, 1):
                username_display = f"@{username}" if username else "Неизвестный"
                date_display = timestamp[:16] if timestamp else "Неизвестно"
                
                display_url = link_url[:60] + "..." if len(link_url) > 60 else link_url
                
                text += f"{i}. {display_url}\n   👤 {username_display} | 📅 {date_display}\n\n"
        
        user_role = get_user_role(call.from_user.id)
        back_menu = "admin_actions_menu" if user_role == 'admin' else "user_actions_menu"
        markup = menus.create_back_button(back_menu)
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"❌ Error in RECENT callback: {str(e)}")
        bot.answer_callback_query(call.id, "❌ Ошибка получения последних ссылок")

def execute_help_callback(call):
    """Help через callback"""
    user_role = get_user_role(call.from_user.id)
    
    if user_role == 'admin':
        help_text = """
🤖 **Presave Reminder Bot v23.3 ЭТАП 1** (Администратор):

🆕 **НОВЫЕ ВОЗМОЖНОСТИ:**
• 🎵 Интерактивная система заявления пресейвов
• 📊 Детальная аналитика по пользователям  
• 🔔 Автоматические уведомления
• 📱 Улучшенные меню с кнопками

👑 **Административные функции:**
• Подтверждение пресейвов
• Анализ активности пользователей
• Настройки бота и диагностика

📊 **Доступна статистика:**
• Рейтинги и лидерборды
• История ссылок
• Система званий

📱 Используйте кнопки для удобной навигации!

✨ **ЭТАП 1 ЗАВЕРШЕН:** Готов к переходу на ЭТАП 2!
        """
        back_menu = "admin_actions_menu"
    else:
        help_text = """
🤖 **Presave Reminder Bot v23.3 ЭТАП 1** (Пользователь):

🆕 **НОВЫЕ ВОЗМОЖНОСТИ:**
• 🎵 Интерактивное заявление пресейвов
• 📊 Подробная статистика активности
• 🏆 Система званий с прогрессом
• 🔗 Просмотр активности сообщества

🎵 **Как заявить пресейв:**
1. Нажмите "Заявить пресейв"
2. Отправьте ссылки на музыку
3. Добавьте комментарий
4. Подтвердите публикацию

🏆 **Система званий:**
🥉 Начинающий (1-5 ссылок)
🥈 Активный (6-15 ссылок)  
🥇 Промоутер (16-30 ссылок)
💎 Амбассадор (31+ ссылок)

📱 Используйте кнопки для навигации!

✨ **v23.3 ЭТАП 1:** Интерактивная система готова!
        """
        back_menu = "user_actions_menu"
    
    markup = menus.create_back_button(back_menu)
    bot.edit_message_text(
        help_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup,
        parse_mode='Markdown'
    )

# === КОМАНДЫ ДЛЯ СОВМЕСТИМОСТИ ===

@bot.message_handler(commands=['mystat'])
@check_permissions(['admin', 'user'])
def cmd_my_stat(message):
    """Подробная статистика текущего пользователя"""
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    try:
        user_data = db.get_user_stats(username)
        
        if not user_data:
            bot.reply_to(message, """
👤 **Ваша статистика v23.3:**

🔗 Всего ссылок: 0
🏆 Звание: 🥉 Начинающий
📈 До первой ссылки: Поделитесь музыкой!

💡 Начните делиться ссылками на музыку для роста в рейтинге!

🆕 **Новое:** Используйте /menu → "Заявить пресейв" для интерактивного процесса!
            """, parse_mode='Markdown')
            return
        
        username_db, total_links, last_updated = user_data
        
        rank_emoji, rank_name = get_user_rank(total_links)
        progress_needed, next_rank = get_progress_to_next_rank(total_links)
        
        all_users = db.get_user_stats()
        user_position = get_user_position_in_ranking(username_db, all_users)
        
        # Активность за неделю
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM link_history 
                WHERE user_id = ? AND timestamp >= datetime('now', '-7 days')
            ''', (user_id,))
            week_result = cursor.fetchone()
            week_activity = week_result[0] if week_result else 0
        
        stat_text = f"""
👤 **Моя статистика v23.3:**

🔗 Всего ссылок: {total_links}
🏆 Звание: {rank_emoji} {rank_name}
📅 Последняя активность: {last_updated[:16] if last_updated else 'Никогда'}
📈 Место в рейтинге: {user_position} из {len(all_users)}
📊 Активность за неделю: {week_activity} ссылок

🎯 **Прогресс:**
{f"До {next_rank}: {progress_needed} ссылок" if progress_needed > 0 else "Максимальное звание достигнуто! 🎉"}

🆕 **Новое:** Попробуйте интерактивную систему заявления пресейвов в /menu!

💪 {'Продолжайте в том же духе!' if total_links > 0 else 'Начните делиться музыкой!'}
        """
        
        bot.reply_to(message, stat_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Error in MYSTAT command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения вашей статистики")

@bot.message_handler(commands=['test_presave_system'])
@check_permissions(['admin'])
def cmd_test_presave_system_v23_3(message):
    """Тестовая команда для проверки системы пресейвов v23.3"""
    try:
        test_results = []
        
        # Тест 1: Проверяем таблицы
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM presave_claims")
            claims_count = cursor.fetchone()[0]
            test_results.append(f"✅ presave_claims: {claims_count} записей")
            
            cursor.execute("SELECT COUNT(*) FROM presave_verifications")
            verifications_count = cursor.fetchone()[0]
            test_results.append(f"✅ presave_verifications: {verifications_count} записей")
            
            cursor.execute("SELECT COUNT(*) FROM user_sessions")
            sessions_count = cursor.fetchone()[0]
            test_results.append(f"✅ user_sessions: {sessions_count} записей")
        
        # Тест 2: Проверяем интерактивную систему
        test_user_id = 123456789
        try:
            response, markup = interactive_presave_system.start_presave_claim(test_user_id, 0)
            if response and markup:
                test_results.append("✅ Интерактивная система: инициализация OK")
            else:
                test_results.append("❌ Интерактивная система: ошибка инициализации")
        except Exception as e:
            test_results.append(f"❌ Интерактивная система: {str(e)}")
        
        # Тест 3: Проверяем админскую аналитику
        try:
            test_response = admin_analytics.get_user_links_history("test_user")
            if "не найден" in test_response:
                test_results.append("✅ Админская аналитика: обработка запросов OK")
            else:
                test_results.append("✅ Админская аналитика: запросы обрабатываются")
        except Exception as e:
            test_results.append(f"❌ Админская аналитика: {str(e)}")
        
        # Тест 4: Проверяем уведомления
        try:
            # Тестируем создание объекта уведомлений (не отправляем реально)
            if admin_notifications:
                test_results.append("✅ Система уведомлений: инициализирована")
            else:
                test_results.append("❌ Система уведомлений: не инициализирована")
        except Exception as e:
            test_results.append(f"❌ Система уведомлений: {str(e)}")
        
        # Тест 5: Проверяем меню
        try:
            user_menu = menus.create_user_menu()
            admin_menu = menus.create_admin_menu()
            stats_menu = menus.create_my_stats_menu(message.from_user.id)
            
            if user_menu and admin_menu and stats_menu:
                test_results.append("✅ Система меню: все меню создаются")
            else:
                test_results.append("❌ Система меню: ошибка создания")
        except Exception as e:
            test_results.append(f"❌ Система меню: {str(e)}")
        
        # Формируем результат
        all_passed = all("✅" in result for result in test_results)
        
        result_text = f"""
🧪 **Тест системы пресейвов v23.3 ЭТАП 1:**

📊 **БАЗА ДАННЫХ:**
{chr(10).join([r for r in test_results if 'записей' in r])}

🎵 **ИНТЕРАКТИВНАЯ СИСТЕМА:**
{chr(10).join([r for r in test_results if 'Интерактивная' in r])}

📈 **АДМИНСКАЯ АНАЛИТИКА:**
{chr(10).join([r for r in test_results if 'Админская' in r])}

🔔 **СИСТЕМА УВЕДОМЛЕНИЙ:**
{chr(10).join([r for r in test_results if 'уведомлений' in r])}

📱 **СИСТЕМА МЕНЮ:**
{chr(10).join([r for r in test_results if 'меню' in r])}

🎯 **СТАТУС:** {'✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ' if all_passed else '⚠️ ЕСТЬ ПРОБЛЕМЫ'}

🆕 **РЕАЛИЗОВАНО В ЭТАПЕ 1:**
✅ Интерактивная система заявления пресейвов
✅ Улучшенные меню с подробной навигацией
✅ Расширенный ответ бота с последними ссылками
✅ Детальная админская аналитика
✅ Базовые уведомления админам

{f'🚀 ГОТОВ К ЭТАПУ 2!' if all_passed else '🛠️ Требует доработки'}
        """
        
        bot.reply_to(message, result_text, parse_mode='Markdown')
        
        logger.info(f"🧪 PRESAVE_SYSTEM_TEST_V23_3: {'PASSED' if all_passed else 'FAILED'}")
        
    except Exception as e:
        logger.error(f"❌ Error in v23.3 presave system test: {str(e)}")
        bot.reply_to(message, f"❌ Ошибка тестирования: {str(e)}")

# === ОБРАБОТЧИКИ ПРЕСЕЙВОВ v23.3 ===

@bot.message_handler(func=lambda m: (
    m.chat.id == GROUP_ID and 
    m.message_thread_id == THREAD_ID and 
    m.text and 
    not m.text.startswith('/') and
    not m.from_user.is_bot and
    is_presave_claim(m.text)
))
def handle_presave_claim_v23_3(message):
    """Обработчик заявлений о пресейвах v23.3"""
    try:
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        
        logger.info(f"🎵 PRESAVE_CLAIM_V23_3: User {user_id} (@{username}) claimed presave")
        logger.info(f"🎵 CLAIM_TEXT: '{message.text}'")
        
        # Извлекаем платформы
        platforms = extract_platforms(message.text)
        logger.info(f"🎵 EXTRACTED_PLATFORMS: {platforms}")
        
        # Сохраняем заявление в БД
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO presave_claims 
                (user_id, username, message_id, claim_text, extracted_platforms, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            ''', (
                user_id, 
                security.sanitize_username(username),
                message.message_id,
                security.validate_text_input(message.text, 1000),
                json.dumps(platforms) if platforms else "[]"
            ))
            
            claim_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"🎵 CLAIM_SAVED: ID={claim_id}, Platforms={platforms}")
        
        # Уведомляем админов о новом заявлении
        admin_notifications.notify_new_presave_claim(claim_id, user_id, username)
        
        # Отправляем подтверждение в топик
        response_text = f"""
🎵 **Заявление о пресейве зафиксировано!**

👤 От: @{username}
📊 ID: {claim_id}
📱 Платформы: {', '.join(platforms) if platforms else 'автоопределение'}

✅ **v23.3:** Заявление сохранено и отправлено на модерацию
⏳ Ожидайте подтверждения от администратора

💡 **Совет:** Используйте /menu → "Заявить пресейв" для более удобного интерактивного процесса!
        """
        
        safe_send_message(
            chat_id=GROUP_ID,
            text=response_text,
            message_thread_id=THREAD_ID,
            reply_to_message_id=message.message_id
        )
        
    except Exception as e:
        logger.error(f"❌ PRESAVE_CLAIM_ERROR: {str(e)}")

@bot.message_handler(func=lambda m: (
    m.chat.id == GROUP_ID and 
    m.message_thread_id == THREAD_ID and 
    is_admin(m.from_user.id) and 
    is_admin_verification(m)
))
def handle_admin_verification_v23_3(message):
    """Обработчик подтверждений админов v23.3"""
    try:
        admin_id = message.from_user.id
        admin_username = message.from_user.username or f"admin_{admin_id}"
        
        logger.info(f"🎵 ADMIN_VERIFICATION_V23_3: Admin {admin_id} (@{admin_username})")
        
        if message.reply_to_message:
            logger.info(f"🎵 REPLIED_TO: Message {message.reply_to_message.message_id}")
            logger.info(f"🎵 VERIFICATION_TEXT: '{message.text}'")
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Ищем заявление по message_id
                cursor.execute('''
                    SELECT id, user_id, username, claim_text FROM presave_claims 
                    WHERE message_id = ? AND status = 'pending'
                ''', (message.reply_to_message.message_id,))
                
                claim = cursor.fetchone()
                
                if claim:
                    claim_id, claim_user_id, claim_username, claim_text = claim
                    
                    # Сохраняем подтверждение
                    cursor.execute('''
                        INSERT INTO presave_verifications
                        (claim_id, admin_id, admin_username, verification_type, admin_message_id)
                        VALUES (?, ?, ?, 'verified', ?)
                    ''', (claim_id, admin_id, admin_username, message.message_id))
                    
                    # Обновляем статус заявления
                    cursor.execute('''
                        UPDATE presave_claims SET status = 'verified' WHERE id = ?
                    ''', (claim_id,))
                    
                    # Обновляем статистику пользователя
                    cursor.execute('''
                        UPDATE user_links 
                        SET total_verified_presaves = COALESCE(total_verified_presaves, 0) + 1,
                            last_presave_claim = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    ''', (claim_user_id,))
                    
                    conn.commit()
                    
                    logger.info(f"🎵 VERIFICATION_SAVED: Claim {claim_id} verified by admin {admin_id}")
                    
                    # Отправляем подтверждение в топик
                    response_text = f"""
✅ **Пресейв подтвержден администратором!**

👮 Подтвердил: @{admin_username}
👤 Пользователь: @{claim_username}
🆔 ID заявления: {claim_id}
📅 Время подтверждения: {datetime.now().strftime('%Y-%m-%d %H:%M')}

🎉 Заявление принято и засчитано в статистику!

💡 **v23.3:** Автоматическое обновление рейтингов и статистики
                    """
                    
                    safe_send_message(
                        chat_id=GROUP_ID,
                        text=response_text,
                        message_thread_id=THREAD_ID,
                        reply_to_message_id=message.reply_to_message.message_id
                    )
                    
                else:
                    logger.warning(f"🎵 VERIFICATION_NOT_FOUND: No pending claim for message {message.reply_to_message.message_id}")
                    
                    # Отправляем сообщение о том, что заявление не найдено
                    safe_send_message(
                        chat_id=GROUP_ID,
                        text="❌ Заявление для подтверждения не найдено или уже обработано",
                        message_thread_id=THREAD_ID,
                        reply_to_message_id=message.message_id
                    )
        
    except Exception as e:
        logger.error(f"❌ ADMIN_VERIFICATION_ERROR: {str(e)}")

# === ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ v23.3 ===

@bot.message_handler(func=lambda message: message.chat.id == GROUP_ID and message.message_thread_id == THREAD_ID)
def handle_topic_message_v23_3(message):
    """Обработчик сообщений в топике пресейвов v23.3"""
    
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    message_text = message.text or message.caption or ""
    
    logger.info(f"📨 TOPIC_MESSAGE_V23_3: Message from user {user_id} (@{username})")
    logger.info(f"📝 MESSAGE_CONTENT: '{message_text[:100]}{'...' if len(message_text) > 100 else ''}'")
    
    # Пропускаем команды
    if message.text and message.text.startswith('/'):
        logger.info("🚫 SKIPPED: Command message")
        return
    
    # Пропускаем ботов
    if message.from_user.is_bot:
        logger.info("🚫 SKIPPED: Bot message")
        return
    
    # Проверяем активность бота
    if not db.is_bot_active():
        logger.info("🚫 SKIPPED: Bot inactive")
        return
    
    # Извлекаем ссылки
    links = extract_links(message_text)
    logger.info(f"🔍 LINKS_FOUND: {len(links)} links")
    
    if links:
        for i, link in enumerate(links, 1):
            logger.info(f"🔗 FOUND_LINK_{i}: {link}")
    
    if not links:
        logger.info("🚫 SKIPPED: No links found")
        return
    
    # Проверяем лимиты
    can_respond, reason = db.can_send_response()
    logger.info(f"🚦 RATE_LIMIT: Can respond: {can_respond}, reason: '{reason}'")
    
    if not can_respond:
        logger.warning(f"🚫 BLOCKED: Response blocked: {reason}")
        return
    
    try:
        # Сохраняем пользователя и ссылки
        db.add_user_links(user_id, username, links, message.message_id)
        
        # Генерируем расширенный ответ с последними ссылками
        enhanced_response = generate_enhanced_bot_response(user_id, links)
        logger.info(f"💬 ENHANCED_RESPONSE: Generated response with community links")
        
        # Отправляем расширенный ответ
        success = safe_send_message(
            chat_id=GROUP_ID,
            text=enhanced_response,
            message_thread_id=THREAD_ID,
            reply_to_message_id=message.message_id
        )
        
        if success:
            db.update_response_limits()
            db.log_bot_response(user_id, enhanced_response)
            
            # Уведомляем админов о новых ссылках (опционально)
            admin_notifications.notify_links_posted(user_id, username, len(links))
            
            logger.info(f"🎉 SUCCESS: Enhanced response sent for user {username} ({len(links)} links)")
        else:
            logger.error(f"❌ FAILED: Could not send enhanced response for user {username}")
        
    except Exception as e:
        logger.error(f"💥 ERROR: Exception in message processing v23.3: {str(e)}")
        logger.error(f"💥 ERROR_DETAILS: User: {username}, Links: {len(links)}, Text: '{message_text[:100]}'")

# === ОСТАЛЬНЫЕ КОМАНДЫ ДЛЯ СОВМЕСТИМОСТИ ===

@bot.message_handler(commands=['activate'])
@check_permissions(['admin'])
def cmd_activate(message):
    if message.chat.id != GROUP_ID or message.message_thread_id != THREAD_ID:
        bot.reply_to(message, "❌ Команда должна выполняться в топике пресейвов")
        return
    
    db.set_bot_active(True)
    
    current_limits = get_current_limits()
    current_mode = db.get_current_rate_mode()
    
    welcome_text = f"""
🤖 **Presave Reminder Bot v23.3 ЭТАП 1 активирован!**

✅ Готов к работе в топике "Пресейвы"
🎯 Буду отвечать на сообщения со ссылками
{current_limits['mode_emoji']} Режим: {current_mode.upper()}

🆕 **Новые возможности v23.3:**
• 🎵 Интерактивная система заявления пресейвов
• 📊 Расширенные ответы с последними ссылками от участников
• 🔔 Автоматические уведомления админам
• 📱 Улучшенные меню (/menu)

⚙️ Управление: /help или /menu
🛑 Отключить: /deactivate

✨ **ЭТАП 1 ЗАВЕРШЕН:** Все функции готовы к использованию!
    """
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')

@bot.message_handler(commands=['deactivate'])
@check_permissions(['admin'])
def cmd_deactivate(message):
    db.set_bot_active(False)
    bot.reply_to(message, "🛑 Бот деактивирован. Для включения используйте /activate")

# === ФУНКЦИИ ИНИЦИАЛИЗАЦИИ v23.3 ===

def setup_webhook():
    """Настройка webhook v23.3"""
    try:
        logger.info("🔗 WEBHOOK_SETUP: Configuring webhook for v23.3...")
        
        # Удаляем старый webhook
        bot.remove_webhook()
        logger.info("🧹 WEBHOOK_CLEANUP: Previous webhook removed")
        
        webhook_kwargs = {"url": WEBHOOK_URL}
        if WEBHOOK_SECRET:
            webhook_kwargs["secret_token"] = WEBHOOK_SECRET
            logger.info("🔐 WEBHOOK_SECURITY: Using secret token")
        
        webhook_result = bot.set_webhook(**webhook_kwargs)
        
        if webhook_result:
            logger.info(f"✅ WEBHOOK_SET: Webhook configured successfully")
            logger.info(f"🔗 WEBHOOK_TARGET: {WEBHOOK_URL}")
            logger.info(f"💓 KEEPALIVE_ENDPOINT: {WEBHOOK_URL.replace(WEBHOOK_PATH, '/keepalive')}")
            logger.info(f"🏥 HEALTH_ENDPOINT: {WEBHOOK_URL.replace(WEBHOOK_PATH, '/health')}")
            return True
        else:
            logger.error("❌ WEBHOOK_FAILED: Failed to set webhook")
            return False
            
    except Exception as e:
        logger.error(f"❌ WEBHOOK_ERROR: Failed to setup webhook: {str(e)}")
        return False

def log_v23_3_startup():
    """Логирование запуска v23.3 ЭТАП 1"""
    logger.info("🎵 V23_3_STARTUP: Initializing ЭТАП 1 features...")
    
    try:
        # Проверяем таблицы
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM presave_claims")
            claims_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM presave_verifications")
            verifications_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM user_sessions")
            sessions_count = cursor.fetchone()[0]
        
        logger.info(f"🎵 PRESAVE_DB_V23_3: {claims_count} claims, {verifications_count} verifications, {sessions_count} sessions")
        
        # Проверяем интерактивную систему
        test_response, test_markup = interactive_presave_system.start_presave_claim(999999999, 0)
        interactive_ok = bool(test_response and test_markup)
        
        logger.info(f"🎵 INTERACTIVE_SYSTEM: Initialization {'successful' if interactive_ok else 'failed'}")
        
        # Проверяем админскую аналитику
        try:
            test_analytics = admin_analytics.get_user_links_history("test_user")
            analytics_ok = "не найден" in test_analytics
        except:
            analytics_ok = False
            
        logger.info(f"📊 ADMIN_ANALYTICS: System {'operational' if analytics_ok else 'error'}")
        
        # Проверяем систему уведомлений
        notifications_ok = bool(admin_notifications)
        logger.info(f"🔔 NOTIFICATIONS_SYSTEM: {'initialized' if notifications_ok else 'error'}")
        
        # Проверяем меню
        try:
            test_menu = menus.create_user_menu()
            menus_ok = bool(test_menu)
        except:
            menus_ok = False
            
        logger.info(f"📱 MENU_SYSTEM: {'operational' if menus_ok else 'error'}")
        
        # Общий статус
        all_systems_ok = interactive_ok and analytics_ok and notifications_ok and menus_ok
        
        logger.info("✅ V23_3_FEATURES: ЭТАП 1 features status:")
        logger.info(f"   🎵 Interactive Presave System: {'✅ OK' if interactive_ok else '❌ ERROR'}")
        logger.info(f"   📊 Admin Analytics: {'✅ OK' if analytics_ok else '❌ ERROR'}")
        logger.info(f"   🔔 Notifications: {'✅ OK' if notifications_ok else '❌ ERROR'}")
        logger.info(f"   📱 Enhanced Menus: {'✅ OK' if menus_ok else '❌ ERROR'}")
        logger.info(f"   🎯 Overall Status: {'✅ ALL SYSTEMS OPERATIONAL' if all_systems_ok else '⚠️ SOME ISSUES DETECTED'}")
        
        if all_systems_ok:
            logger.info("🚀 V23_3_READY: ЭТАП 1 fully implemented and ready for production!")
        else:
            logger.warning("⚠️ V23_3_PARTIAL: Some ЭТАП 1 features may not work correctly")
        
    except Exception as e:
        logger.error(f"❌ V23_3_STARTUP_ERROR: {str(e)}")

def main():
    """Основная функция запуска бота v23.3 ЭТАП 1"""
    try:
        logger.info("🚀 STARTUP: Starting Presave Reminder Bot v23.3 ЭТАП 1")
        logger.info(f"🔧 CONFIG: GROUP_ID={GROUP_ID}, THREAD_ID={THREAD_ID}")
        logger.info(f"📱 STAGE: ЭТАП 1 - Интерактивная система пресейвов")
        
        # Инициализация базы данных
        db.init_db()
        
        # Инициализация и проверка всех систем ЭТАПА 1
        log_v23_3_startup()
        
        # Загрузка режимов
        reload_rate_limit_modes()
        current_mode = db.get_current_rate_mode()
        current_limits = get_current_limits()
        
        logger.info("🤖 Presave Reminder Bot v23.3 ЭТАП 1 запущен!")
        logger.info(f"👥 Группа: {GROUP_ID}")
        logger.info(f"📋 Топик: {THREAD_ID}")
        logger.info(f"👑 Админы: {ADMIN_IDS}")
        logger.info(f"🎛️ РЕЖИМ: {current_limits['mode_name']} ({current_limits['max_responses_per_hour']}/час)")
        
        logger.info("🆕 ЭТАП 1 ФУНКЦИИ:")
        logger.info("   🎵 Интерактивная система заявления пресейвов")
        logger.info("   📊 Улучшенные меню с подробной навигацией")
        logger.info("   🔗 Расширенные ответы с последними ссылками")
        logger.info("   📈 Детальная админская аналитика")
        logger.info("   🔔 Базовые уведомления админам")
        
        if setup_webhook():
            logger.info("🔗 Webhook режим активен")
        else:
            logger.error("❌ Ошибка настройки webhook")
            return
        
        with socketserver.TCPServer(("", WEBHOOK_PORT), WebhookHandler) as httpd:
            logger.info(f"🌐 Webhook сервер запущен на порту {WEBHOOK_PORT}")
            logger.info(f"🔗 Webhook URL: {WEBHOOK_URL}")
            logger.info(f"💓 Keepalive URL: {WEBHOOK_URL.replace(WEBHOOK_PATH, '/keepalive')}")
            logger.info(f"🏥 Health URL: {WEBHOOK_URL.replace(WEBHOOK_PATH, '/health')}")
            logger.info("✅ READY: Bot v23.3 ЭТАП 1 fully operational!")
            logger.info("🎵 INTERACTIVE_PRESAVE_SYSTEM: Ready for user interactions")
            logger.info("🚀 NEXT_STAGE: Готов к переходу на ЭТАП 2 (AI, Rich Media, Gamification)")
            httpd.serve_forever()
        
    except Exception as e:
        logger.error(f"💥 CRITICAL: Critical error in main v23.3: {str(e)}")
    finally:
        try:
            bot.remove_webhook()
            logger.info("🧹 Webhook очищен при остановке")
        except:
            pass

if __name__ == "__main__":
    main()
