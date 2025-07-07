import logging
import re
import sqlite3
import time
import threading
from datetime import datetime, timedelta
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
import json
import ssl
import os

import telebot
from telebot import types
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))  # -1001992546193
THREAD_ID = int(os.getenv('THREAD_ID'))  # 10
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
DEFAULT_REMINDER = os.getenv('REMINDER_TEXT', '🎧 Напоминаем: не забудьте сделать пресейв артистов выше! ♥️')

# Константы безопасности
MAX_RESPONSES_PER_HOUR = 10
MIN_COOLDOWN_SECONDS = 30
BATCH_RESPONSE_WINDOW = 300  # 5 минут
RESPONSE_DELAY = 3

# Webhook настройки
WEBHOOK_HOST = "misterdms-presave-bot.onrender.com"  # Ваш Render URL
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

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
    
    def init_db(self):
        """Инициализация базы данных"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
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
            
            # Инициализация базовых записей
            cursor.execute('INSERT OR IGNORE INTO bot_activity (id, is_active) VALUES (1, 1)')
            cursor.execute('INSERT OR IGNORE INTO rate_limits (id) VALUES (1)')
            cursor.execute(
                'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                ('reminder_text', DEFAULT_REMINDER)
            )
            
            conn.commit()
            conn.close()
            logger.info("База данных инициализирована")

    def add_user_links(self, user_id: int, username: str, links: list, message_id: int):
        """Добавление ссылок пользователя"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Обновляем счётчик пользователя
            cursor.execute('''
                INSERT OR REPLACE INTO user_links (user_id, username, total_links, last_updated)
                VALUES (?, ?, COALESCE((SELECT total_links FROM user_links WHERE user_id = ?), 0) + ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, user_id, len(links)))
            
            # Добавляем детальную историю
            for link in links:
                cursor.execute('''
                    INSERT INTO link_history (user_id, link_url, message_id)
                    VALUES (?, ?, ?)
                ''', (user_id, link, message_id))
            
            conn.commit()
            conn.close()

    def log_bot_response(self, user_id: int, response_text: str):
        """Логирование ответа бота"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO bot_responses (user_id, response_text)
                VALUES (?, ?)
            ''', (user_id, response_text))
            conn.commit()
            conn.close()

    def is_bot_active(self) -> bool:
        """Проверка активности бота"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT is_active FROM bot_activity WHERE id = 1')
            result = cursor.fetchone()
            conn.close()
            return bool(result[0]) if result else False

    def set_bot_active(self, active: bool):
        """Установка статуса активности"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE bot_activity SET is_active = ? WHERE id = 1', (active,))
            conn.commit()
            conn.close()

    def can_send_response(self) -> tuple[bool, str]:
        """Проверка возможности отправки ответа с учетом лимитов"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT hourly_responses, last_hour_reset, cooldown_until
                FROM rate_limits WHERE id = 1
            ''')
            result = cursor.fetchone()
            
            if not result:
                conn.close()
                return False, "Ошибка получения лимитов"
            
            hourly_responses, last_hour_reset, cooldown_until = result
            now = datetime.now()
            
            # Проверяем cooldown
            if cooldown_until:
                cooldown_time = datetime.fromisoformat(cooldown_until)
                if now < cooldown_time:
                    remaining = int((cooldown_time - now).total_seconds())
                    conn.close()
                    return False, f"Cooldown активен. Осталось: {remaining} сек"
            
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
            if hourly_responses >= MAX_RESPONSES_PER_HOUR:
                conn.close()
                return False, f"Достигнут лимит {MAX_RESPONSES_PER_HOUR} ответов в час"
            
            conn.close()
            return True, "OK"

    def update_response_limits(self):
        """Обновление лимитов после отправки ответа"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now()
            cooldown_until = now + timedelta(seconds=MIN_COOLDOWN_SECONDS)
            
            cursor.execute('''
                UPDATE rate_limits 
                SET hourly_responses = hourly_responses + 1,
                    cooldown_until = ?
                WHERE id = 1
            ''', (cooldown_until.isoformat(),))
            
            conn.commit()
            conn.close()

    def get_user_stats(self, username: str = None):
        """Получение статистики пользователей"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if username:
                # Статистика конкретного пользователя
                cursor.execute('''
                    SELECT username, total_links, last_updated
                    FROM user_links 
                    WHERE username = ? AND total_links > 0
                ''', (username.replace('@', ''),))
                result = cursor.fetchone()
                conn.close()
                return result
            else:
                # Общая статистика
                cursor.execute('''
                    SELECT username, total_links, last_updated
                    FROM user_links 
                    WHERE total_links > 0
                    ORDER BY total_links DESC
                ''')
                result = cursor.fetchall()
                conn.close()
                return result

    def get_bot_stats(self):
        """Статистика работы бота"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Получаем лимиты
            cursor.execute('''
                SELECT hourly_responses, cooldown_until FROM rate_limits WHERE id = 1
            ''')
            limits = cursor.fetchone()
            
            # Получаем активность
            cursor.execute('''
                SELECT is_active, last_response_time FROM bot_activity WHERE id = 1
            ''')
            activity = cursor.fetchone()
            
            # Считаем ответы за сегодня
            cursor.execute('''
                SELECT COUNT(*) FROM bot_responses 
                WHERE DATE(timestamp) = DATE('now')
            ''')
            today_responses = cursor.fetchone()
            
            conn.close()
            
            return {
                'hourly_responses': limits[0] if limits else 0,
                'hourly_limit': MAX_RESPONSES_PER_HOUR,
                'cooldown_until': limits[1] if limits else None,
                'is_active': bool(activity[0]) if activity else False,
                'last_response': activity[1] if activity else None,
                'today_responses': today_responses[0] if today_responses else 0
            }

    def clear_link_history(self):
        """Очистка истории ссылок (счётчики остаются)"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM link_history')
            conn.commit()
            conn.close()

    def get_reminder_text(self) -> str:
        """Получение текста напоминания"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', ('reminder_text',))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else DEFAULT_REMINDER

    def set_reminder_text(self, text: str):
        """Установка текста напоминания"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', ('reminder_text', text))
            conn.commit()
            conn.close()

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
        logger.info(f"💬 SEND_MESSAGE: Preparing to send message to chat {chat_id}, thread {message_thread_id}")
        logger.info(f"⏱️ DELAY: Applying {RESPONSE_DELAY}s safety delay")
        
        time.sleep(RESPONSE_DELAY)  # Задержка перед отправкой
        
        if message_thread_id:
            logger.info(f"📨 SEND_THREAD: Sending to thread {message_thread_id}")
            # Если есть thread_id, отправляем в топик
            result = bot.send_message(
                chat_id=chat_id, 
                text=text, 
                message_thread_id=message_thread_id,
                reply_to_message_id=reply_to_message_id
            )
            logger.info(f"✅ SENT_THREAD: Message sent to thread successfully, message_id: {result.message_id}")
        else:
            logger.info(f"📨 SEND_DIRECT: Sending direct message")
            # Обычное сообщение
            if reply_to_message_id:
                result = bot.reply_to(reply_to_message_id, text)
                logger.info(f"✅ SENT_REPLY: Reply sent successfully, message_id: {result.message_id}")
            else:
                result = bot.send_message(chat_id, text)
                logger.info(f"✅ SENT_DIRECT: Direct message sent successfully, message_id: {result.message_id}")
        
        return True
    except Exception as e:
        logger.error(f"❌ SEND_ERROR: Failed to send message: {str(e)}")
        logger.error(f"❌ SEND_ERROR_TYPE: {type(e).__name__}: {e}")
        logger.error(f"❌ SEND_CONTEXT: chat_id={chat_id}, thread_id={message_thread_id}, reply_to={reply_to_message_id}")
        return False

# Webhook сервер
class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Обработка POST запросов от Telegram"""
        logger.info(f"📨 WEBHOOK_POST: Received POST request to {self.path}")
        
        if self.path == WEBHOOK_PATH:
            try:
                logger.info(f"✅ WEBHOOK_MATCH: Path matches webhook path {WEBHOOK_PATH}")
                
                # Получаем данные
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                logger.info(f"📦 WEBHOOK_DATA: Received {content_length} bytes of data")
                
                # Парсим JSON
                update_data = json.loads(post_data.decode('utf-8'))
                logger.info(f"📋 WEBHOOK_JSON: Successfully parsed JSON data")
                logger.info(f"🔍 WEBHOOK_UPDATE: Update keys: {list(update_data.keys())}")
                
                # Создаем объект Update
                update = telebot.types.Update.de_json(update_data)
                logger.info(f"📝 WEBHOOK_OBJECT: Created Update object, update_id: {getattr(update, 'update_id', 'unknown')}")
                
                # Обрабатываем update
                if update:
                    logger.info(f"🔄 WEBHOOK_PROCESS: Processing update through bot handlers")
                    bot.process_new_updates([update])
                    logger.info(f"✅ WEBHOOK_PROCESSED: Update processed successfully")
                else:
                    logger.warning(f"⚠️ WEBHOOK_EMPTY: Update object is None")
                
                # Отвечаем Telegram
                self.send_response(200)
                self.end_headers()
                logger.info(f"✅ WEBHOOK_RESPONSE: Sent 200 OK response to Telegram")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ WEBHOOK_JSON_ERROR: Failed to parse JSON: {e}")
                self.send_response(400)
                self.end_headers()
            except Exception as e:
                logger.error(f"❌ WEBHOOK_ERROR: Error processing webhook: {str(e)}")
                logger.error(f"❌ WEBHOOK_ERROR_TYPE: {type(e).__name__}: {e}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/' or self.path == '/health':
            logger.info(f"💚 HEALTH_CHECK: Health check request via POST")
            # Health check
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "status": "healthy", 
                "service": "telegram-bot",
                "webhook_url": WEBHOOK_URL,
                "bot": "@misterdms_presave_bot"
            })
            self.wfile.write(response.encode())
        else:
            logger.warning(f"❓ WEBHOOK_UNKNOWN: Unknown POST path: {self.path}")
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        """Обработка GET запросов"""
        logger.info(f"🌐 HTTP_GET: Received GET request to {self.path}")
        
        if self.path == '/' or self.path == '/health':
            logger.info(f"💚 HEALTH_CHECK: Health check request via GET")
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = json.dumps({
                "status": "healthy", 
                "service": "telegram-bot",
                "webhook_url": WEBHOOK_URL,
                "bot": "@misterdms_presave_bot"
            })
            self.wfile.write(response.encode())
            logger.info(f"✅ HEALTH_RESPONSE: Sent health check response")
        else:
            logger.warning(f"❓ HTTP_UNKNOWN: Unknown GET path: {self.path}")
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Отключаем HTTP логи для чистоты - мы ведем собственные логи
        pass

# === ОБРАБОТЧИКИ КОМАНД ===

@bot.message_handler(commands=['start'])
def cmd_start(message):
    logger.info(f"🔍 START command received from user {message.from_user.id} (@{message.from_user.username})")
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ START command denied - user {message.from_user.id} not in admin list")
        return
    
    logger.info(f"✅ START command processed for admin {message.from_user.id}")
    bot.reply_to(message, """
🤖 Presave Reminder Bot запущен!

Для управления используйте команду /help
Бот работает только в настроенном топике группы.
    """)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    logger.info(f"🔍 HELP command received from user {message.from_user.id} (@{message.from_user.username})")
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ HELP command denied - user {message.from_user.id} not in admin list")
        return
    
    help_text = """
🤖 Команды бота:

👑 Для администраторов:
/help — этот список команд
/activate — включить бота в топике
/deactivate — отключить бота в топике  
/stats — общая статистика работы бота
/linkstats — рейтинг пользователей по ссылкам
/topusers — топ-5 самых активных
/userstat @username — статистика конкретного пользователя
/setmessage текст — изменить текст напоминания
/clearhistory — очистить историю ссылок (счётчики сохраняются)
/botstat — мониторинг активности и лимитов бота
/test_regex — тестировать распознавание ссылок
/alllinks — показать все ссылки в базе
/recent — показать последние 10 ссылок

ℹ️ Бот автоматически отвечает на сообщения со ссылками в топике пресейвов
🛡️ Защита от спама: максимум 10 ответов в час, пауза 30 сек между ответами
    """
    
    logger.info(f"✅ HELP command processed for admin {message.from_user.id}")
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    logger.info(f"🔍 STATS command received from user {message.from_user.id} (@{message.from_user.username}) in chat {message.chat.id}")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ STATS command denied - user {message.from_user.id} not in admin list {ADMIN_IDS}")
        return
    
    logger.info(f"✅ STATS command authorized for admin {message.from_user.id}")
    
    try:
        # Получаем общую статистику
        bot_stats = db.get_bot_stats()
        user_stats = db.get_user_stats()
        
        # Подсчитываем общие показатели
        total_users = len(user_stats) if user_stats else 0
        total_links = sum(user[1] for user in user_stats) if user_stats else 0
        
        # Получаем последние активности
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Ссылки за сегодня
        cursor.execute('''
            SELECT COUNT(*) FROM link_history 
            WHERE DATE(timestamp) = DATE('now')
        ''')
        today_links = cursor.fetchone()[0]
        
        # Ссылки за неделю
        cursor.execute('''
            SELECT COUNT(*) FROM link_history 
            WHERE timestamp >= datetime('now', '-7 days')
        ''')
        week_links = cursor.fetchone()[0]
        
        # Самый активный пользователь
        cursor.execute('''
            SELECT username, total_links FROM user_links 
            WHERE total_links > 0
            ORDER BY total_links DESC LIMIT 1
        ''')
        top_user = cursor.fetchone()
        
        conn.close()
        
        # Формируем статистику
        status_emoji = "🟢" if bot_stats['is_active'] else "🔴"
        status_text = "Активен" if bot_stats['is_active'] else "Отключен"
        
        stats_text = f"""
📊 Общая статистика бота:

🤖 Статус: {status_emoji} {status_text}
👥 Активных пользователей: {total_users}
🔗 Всего ссылок: {total_links}

📅 За сегодня:
• Ссылок: {today_links}
• Ответов: {bot_stats['today_responses']}

📈 За неделю:
• Ссылок: {week_links}

⚡ Лимиты:
• Ответов в час: {bot_stats['hourly_responses']}/{bot_stats['hourly_limit']}

🏆 Лидер: {f"@{top_user[0]} ({top_user[1]} ссылок)" if top_user else "пока нет"}

🔗 Webhook: активен
        """
        
        logger.info(f"✅ STATS command response prepared for user {message.from_user.id}")
        logger.info(f"📊 Stats data: users={total_users}, links={total_links}, today_links={today_links}")
        
        bot.reply_to(message, stats_text)
        logger.info(f"✅ STATS command response sent successfully to user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Error in STATS command for user {message.from_user.id}: {str(e)}")
        logger.error(f"❌ Exception details: {type(e).__name__}: {e}")
        bot.reply_to(message, "❌ Ошибка получения статистики")

@bot.message_handler(commands=['alllinks'])
def cmd_all_links(message):
    logger.info(f"🔍 ALLLINKS command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ ALLLINKS command denied - user {message.from_user.id} not in admin list")
        return
    
    logger.info(f"✅ ALLLINKS command authorized for admin {message.from_user.id}")
    
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Получаем все ссылки
        cursor.execute('''
            SELECT link_url, username, timestamp 
            FROM link_history 
            LEFT JOIN user_links ON link_history.user_id = user_links.user_id
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        
        links = cursor.fetchall()
        conn.close()
        
        if not links:
            logger.info(f"📝 No links found in database for ALLLINKS command")
            bot.reply_to(message, "📋 В базе данных пока нет ссылок")
            return
        
        # Формируем ответ
        links_text = f"📋 Все ссылки в базе (последние 50):\n\n"
        
        for i, (link_url, username, timestamp) in enumerate(links[:20], 1):  # Показываем только первые 20
            username_display = f"@{username}" if username else "Неизвестный"
            date_display = timestamp[:16] if timestamp else "Неизвестно"
            
            # Обрезаем длинные ссылки
            display_url = link_url[:50] + "..." if len(link_url) > 50 else link_url
            
            links_text += f"{i}. {display_url}\n   👤 {username_display} | 📅 {date_display}\n\n"
        
        if len(links) > 20:
            links_text += f"... и ещё {len(links) - 20} ссылок\n"
        
        links_text += f"\n📊 Всего ссылок в базе: {len(links)}"
        
        logger.info(f"✅ ALLLINKS response prepared: {len(links)} total links, showing first 20")
        bot.reply_to(message, links_text)
        logger.info(f"✅ ALLLINKS command response sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in ALLLINKS command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения списка ссылок")

@bot.message_handler(commands=['recent'])
def cmd_recent_links(message):
    logger.info(f"🔍 RECENT command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ RECENT command denied - user {message.from_user.id} not in admin list")
        return
    
    logger.info(f"✅ RECENT command authorized for admin {message.from_user.id}")
    
    try:
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Получаем последние 10 ссылок
        cursor.execute('''
            SELECT link_url, username, timestamp 
            FROM link_history 
            LEFT JOIN user_links ON link_history.user_id = user_links.user_id
            ORDER BY timestamp DESC
            LIMIT 10
        ''')
        
        recent_links = cursor.fetchall()
        conn.close()
        
        if not recent_links:
            logger.info(f"📝 No recent links found in database")
            bot.reply_to(message, "📋 В базе данных пока нет ссылок")
            return
        
        # Формируем ответ
        recent_text = f"🕐 Последние {len(recent_links)} ссылок:\n\n"
        
        for i, (link_url, username, timestamp) in enumerate(recent_links, 1):
            username_display = f"@{username}" if username else "Неизвестный"
            date_display = timestamp[:16] if timestamp else "Неизвестно"
            
            # Обрезаем длинные ссылки для читаемости
            display_url = link_url[:60] + "..." if len(link_url) > 60 else link_url
            
            recent_text += f"{i}. {display_url}\n   👤 {username_display} | 📅 {date_display}\n\n"
        
        logger.info(f"✅ RECENT response prepared: {len(recent_links)} recent links")
        bot.reply_to(message, recent_text)
        logger.info(f"✅ RECENT command response sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in RECENT command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения последних ссылок")

@bot.message_handler(commands=['activate'])
def cmd_activate(message):
    logger.info(f"🔍 ACTIVATE command received from user {message.from_user.id} (@{message.from_user.username}) in chat {message.chat.id}, thread {message.message_thread_id}")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ ACTIVATE command denied - user {message.from_user.id} not in admin list")
        return
    
    # Проверяем, что команда в нужном топике
    if message.chat.id != GROUP_ID or message.message_thread_id != THREAD_ID:
        logger.warning(f"❌ ACTIVATE command in wrong place: chat={message.chat.id} (need {GROUP_ID}), thread={message.message_thread_id} (need {THREAD_ID})")
        bot.reply_to(message, "❌ Команда должна выполняться в топике пресейвов")
        return
    
    logger.info(f"✅ ACTIVATE command in correct topic, processing...")
    db.set_bot_active(True)
    
    welcome_text = """
🤖 Привет! Я бот для напоминаний о пресейвах!

✅ Активирован в топике "Пресейвы"
🎯 Буду отвечать на сообщения со ссылками
⚙️ Управление: /help
🛑 Отключить: /deactivate

Готов к работе! 🎵
    """
    
    bot.reply_to(message, welcome_text)
    logger.info(f"✅ Bot activated by user {message.from_user.id}")

@bot.message_handler(commands=['deactivate'])
def cmd_deactivate(message):
    logger.info(f"🔍 DEACTIVATE command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ DEACTIVATE command denied - user {message.from_user.id} not in admin list")
        return
    
    db.set_bot_active(False)
    bot.reply_to(message, "🛑 Бот деактивирован. Для включения используйте /activate")
    logger.info(f"✅ Bot deactivated by user {message.from_user.id}")

@bot.message_handler(commands=['botstat'])
def cmd_bot_stat(message):
    logger.info(f"🔍 BOTSTAT command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ BOTSTAT command denied - user {message.from_user.id} not in admin list")
        return
    
    try:
        stats = db.get_bot_stats()
        
        # Расчёт времени до следующего ответа
        cooldown_text = "Готов к ответу"
        if stats['cooldown_until']:
            cooldown_time = datetime.fromisoformat(stats['cooldown_until'])
            now = datetime.now()
            if now < cooldown_time:
                remaining = int((cooldown_time - now).total_seconds())
                cooldown_text = f"Следующий ответ через: {remaining} сек"
        
        status_emoji = "🟢" if stats['is_active'] else "🔴"
        status_text = "Активен" if stats['is_active'] else "Отключен"
        
        stat_text = f"""
🤖 Статистика бота за сегодня:

{status_emoji} Статус: {status_text}
⚡ Ответов в час: {stats['hourly_responses']}/{stats['hourly_limit']}
📊 Ответов за сегодня: {stats['today_responses']}
⏱️ {cooldown_text}
🔗 Webhook: активен

⚠️ Предупреждений: {'🟡 Приближение к лимиту' if stats['hourly_responses'] >= 8 else '✅ Всё в порядке'}
        """
        
        logger.info(f"✅ BOTSTAT command processed for user {message.from_user.id}")
        bot.reply_to(message, stat_text)
        
    except Exception as e:
        logger.error(f"❌ Error in BOTSTAT command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения статистики")

@bot.message_handler(commands=['linkstats'])
def cmd_link_stats(message):
    logger.info(f"🔍 LINKSTATS command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ LINKSTATS command denied - user {message.from_user.id} not in admin list")
        return
    
    try:
        users = db.get_user_stats()
        
        if not users:
            logger.info(f"📝 No users with links found for LINKSTATS")
            bot.reply_to(message, "📊 Пока нет пользователей с ссылками")
            return
        
        stats_text = "📊 Статистика по ссылкам:\n\n"
        
        for i, (username, total_links, last_updated) in enumerate(users[:10], 1):
            # Определяем звание
            if total_links >= 31:
                rank = "💎"
            elif total_links >= 16:
                rank = "🥇"
            elif total_links >= 6:
                rank = "🥈"
            else:
                rank = "🥉"
            
            stats_text += f"{rank} {i}. @{username} — {total_links} ссылок\n"
        
        logger.info(f"✅ LINKSTATS response prepared: {len(users)} users, showing top 10")
        bot.reply_to(message, stats_text)
        logger.info(f"✅ LINKSTATS command response sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in LINKSTATS command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения статистики")

@bot.message_handler(commands=['topusers'])
def cmd_top_users(message):
    logger.info(f"🔍 TOPUSERS command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ TOPUSERS command denied - user {message.from_user.id} not in admin list")
        return
    
    try:
        users = db.get_user_stats()
        
        if not users:
            logger.info(f"📝 No active users found for TOPUSERS")
            bot.reply_to(message, "🏆 Пока нет активных пользователей")
            return
        
        top_text = "🏆 Топ-5 самых активных:\n\n"
        
        for i, (username, total_links, last_updated) in enumerate(users[:5], 1):
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            medal = medals[i-1] if i <= 5 else "▫️"
            
            top_text += f"{medal} @{username} — {total_links} ссылок\n"
        
        logger.info(f"✅ TOPUSERS response prepared: showing top {min(5, len(users))} users")
        bot.reply_to(message, top_text)
        logger.info(f"✅ TOPUSERS command response sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in TOPUSERS command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения топа")

@bot.message_handler(commands=['userstat'])
def cmd_user_stat(message):
    logger.info(f"🔍 USERSTAT command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ USERSTAT command denied - user {message.from_user.id} not in admin list")
        return
    
    # Извлекаем username из команды
    args = message.text.split()
    if len(args) < 2:
        logger.info(f"⚠️ USERSTAT command missing username argument")
        bot.reply_to(message, "❌ Укажите username: /userstat @username")
        return
    
    username = args[1].replace('@', '')
    logger.info(f"🔍 USERSTAT searching for user: '{username}'")
    
    try:
        user_data = db.get_user_stats(username)
        
        if not user_data:
            logger.info(f"❌ User '{username}' not found or has no links")
            bot.reply_to(message, f"❌ Пользователь @{username} не найден или не имеет ссылок")
            return
        
        username, total_links, last_updated = user_data
        
        # Определяем звание
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
        
        logger.info(f"✅ USERSTAT response prepared for user '{username}': {total_links} links")
        bot.reply_to(message, stat_text)
        logger.info(f"✅ USERSTAT command response sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in USERSTAT command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка получения статистики пользователя")

@bot.message_handler(commands=['setmessage'])
def cmd_set_message(message):
    logger.info(f"🔍 SETMESSAGE command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ SETMESSAGE command denied - user {message.from_user.id} not in admin list")
        return
    
    # Извлекаем новый текст
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        current_text = db.get_reminder_text()
        logger.info(f"📝 SETMESSAGE showing current text (length: {len(current_text)})")
        bot.reply_to(message, f"📝 Текущее сообщение:\n\n{current_text}\n\nДля изменения: /setmessage новый текст")
        return
    
    new_text = args[1]
    logger.info(f"📝 SETMESSAGE setting new text (length: {len(new_text)})")
    
    try:
        db.set_reminder_text(new_text)
        logger.info(f"✅ SETMESSAGE reminder text updated successfully")
        bot.reply_to(message, f"✅ Текст напоминания обновлён:\n\n{new_text}")
        logger.info(f"✅ SETMESSAGE command response sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in SETMESSAGE command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка обновления текста")

@bot.message_handler(commands=['clearhistory'])
def cmd_clear_history(message):
    logger.info(f"🔍 CLEARHISTORY command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ CLEARHISTORY command denied - user {message.from_user.id} not in admin list")
        return
    
    try:
        db.clear_link_history()
        logger.info(f"✅ CLEARHISTORY link history cleared successfully")
        bot.reply_to(message, "🧹 История ссылок очищена (общие счётчики сохранены)")
        logger.info(f"✅ CLEARHISTORY command response sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error in CLEARHISTORY command: {str(e)}")
        bot.reply_to(message, "❌ Ошибка очистки истории")

@bot.message_handler(commands=['test_regex'])
def cmd_test_regex(message):
    logger.info(f"🔍 TEST_REGEX command received from user {message.from_user.id} (@{message.from_user.username})")
    
    if not is_admin(message.from_user.id):
        logger.warning(f"❌ TEST_REGEX command denied - user {message.from_user.id} not in admin list")
        return
    
    # Получаем текст для тестирования
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        logger.info(f"⚠️ TEST_REGEX command missing text argument")
        bot.reply_to(message, "🧪 Отправьте: /test_regex ваш текст со ссылками")
        return
    
    test_text = args[1]
    logger.info(f"🧪 TEST_REGEX testing text: '{test_text[:100]}...' (length: {len(test_text)})")
    
    links = extract_links(test_text)
    logger.info(f"🔍 TEST_REGEX found {len(links)} links: {links}")
    
    result_text = f"🧪 Результат тестирования:\n\n📝 Текст: {test_text}\n\n"
    
    if links:
        result_text += f"✅ Найдено ссылок: {len(links)}\n"
        for i, link in enumerate(links, 1):
            result_text += f"{i}. {link}\n"
        result_text += "\n👍 Бот ответит на такое сообщение"
        logger.info(f"✅ TEST_REGEX positive result: {len(links)} links found")
    else:
        result_text += "❌ Ссылки не найдены\n👎 Бот НЕ ответит на такое сообщение"
        logger.info(f"❌ TEST_REGEX negative result: no links found")
    
    bot.reply_to(message, result_text)
    logger.info(f"✅ TEST_REGEX command response sent successfully")

# === СПЕЦИАЛЬНЫЙ ОБРАБОТЧИК ДЛЯ КОМАНД С @BOTNAME ===

@bot.message_handler(func=lambda message: message.text and '@misterdms_presave_bot' in message.text and message.text.strip().startswith('/'))
def handle_tagged_commands(message):
    """Специальный обработчик для команд вида /command@botname"""
    command_text = message.text.strip()
    logger.info(f"🎯 TAGGED_HANDLER: Processing tagged command: '{command_text}'")
    
    # Извлекаем команду без @botname
    clean_command = command_text.split('@')[0]
    logger.info(f"🧹 CLEANED: Extracted command: '{clean_command}'")
    
    # Создаем новое сообщение без @botname для обработки
    message.text = clean_command
    
    # Определяем и вызываем нужный обработчик
    if clean_command == '/stats':
        logger.info(f"🔄 REDIRECT: Redirecting to cmd_stats")
        cmd_stats(message)
    elif clean_command == '/help':
        logger.info(f"🔄 REDIRECT: Redirecting to cmd_help")
        cmd_help(message)
    elif clean_command == '/botstat':
        logger.info(f"🔄 REDIRECT: Redirecting to cmd_bot_stat")
        cmd_bot_stat(message)
    elif clean_command == '/linkstats':
        logger.info(f"🔄 REDIRECT: Redirecting to cmd_link_stats")
        cmd_link_stats(message)
    elif clean_command == '/alllinks':
        logger.info(f"🔄 REDIRECT: Redirecting to cmd_all_links")
        cmd_all_links(message)
    elif clean_command == '/recent':
        logger.info(f"🔄 REDIRECT: Redirecting to cmd_recent_links")
        cmd_recent_links(message)
    elif clean_command == '/activate':
        logger.info(f"🔄 REDIRECT: Redirecting to cmd_activate")
        cmd_activate(message)
    elif clean_command == '/deactivate':
        logger.info(f"🔄 REDIRECT: Redirecting to cmd_deactivate")
        cmd_deactivate(message)
    else:
        logger.warning(f"❓ UNKNOWN: Unknown tagged command: '{clean_command}'")

# === ГЛОБАЛЬНЫЙ ОБРАБОТЧИК КОМАНД (ДЛЯ ДИАГНОСТИКИ) ===

@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def global_command_logger(message):
    """Глобальный логгер всех команд для диагностики"""
    command_text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "No_username"
    chat_id = message.chat.id
    thread_id = getattr(message, 'message_thread_id', None)
    
    logger.info(f"🌐 GLOBAL: Command received: '{command_text}' from user {user_id} (@{username}) in chat {chat_id}, thread {thread_id}")
    
    # Проверяем команды с @botname
    if '@' in command_text:
        logger.info(f"🎯 TAGGED: Command contains @mention: '{command_text}'")
        if '@misterdms_presave_bot' in command_text:
            logger.info(f"✅ TARGETED: Command targeted at our bot: '{command_text}'")
        else:
            logger.info(f"➡️ OTHER_BOT: Command targeted at different bot: '{command_text}'")
    
    # Логируем админские права
    is_admin_user = is_admin(user_id)
    logger.info(f"👑 ADMIN_CHECK: User {user_id} admin status: {is_admin_user} (admin_list: {ADMIN_IDS})")
    
    # Логируем чат/топик
    in_correct_chat = (chat_id == GROUP_ID)
    in_correct_thread = (thread_id == THREAD_ID)
    logger.info(f"📍 LOCATION: Correct chat: {in_correct_chat} ({chat_id}=={GROUP_ID}), Correct thread: {in_correct_thread} ({thread_id}=={THREAD_ID})")

# === ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ===

@bot.message_handler(func=lambda message: message.chat.id == GROUP_ID and message.message_thread_id == THREAD_ID)
def handle_topic_message(message):
    """Обработка сообщений в топике пресейвов"""
    
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    message_text = message.text or message.caption or ""
    
    logger.info(f"📨 TOPIC_MESSAGE: Received message from user {user_id} (@{username}) in correct topic")
    logger.info(f"📝 MESSAGE_TEXT: '{message_text[:200]}...' (length: {len(message_text)})")
    
    # Игнорируем команды и сообщения от ботов
    if message.text and message.text.startswith('/'):
        logger.info(f"⏭️ SKIP: Message is a command, skipping link processing")
        return
    
    if message.from_user.is_bot:
        logger.info(f"🤖 SKIP: Message from bot, skipping")
        return
    
    # Проверяем активность бота
    bot_active = db.is_bot_active()
    logger.info(f"🔄 BOT_STATUS: Bot active status: {bot_active}")
    if not bot_active:
        logger.info(f"😴 INACTIVE: Bot inactive, skipping message processing")
        return
    
    # Извлекаем ссылки из сообщения
    links = extract_links(message_text)
    logger.info(f"🔍 LINKS_FOUND: Found {len(links)} links: {links}")
    
    if not links:
        logger.info(f"⏭️ NO_LINKS: No links found, skipping response")
        return  # Нет ссылок - не отвечаем
    
    # Проверяем лимиты
    can_respond, reason = db.can_send_response()
    logger.info(f"🚦 RATE_LIMIT: Can respond: {can_respond}, reason: '{reason}'")
    
    if not can_respond:
        logger.warning(f"🚫 BLOCKED: Response blocked by rate limiting: {reason}")
        return
    
    try:
        logger.info(f"💾 SAVING: Saving {len(links)} links to database for user {username}")
        
        # Сохраняем ссылки в базу
        db.add_user_links(
            user_id=user_id,
            username=username,
            links=links,
            message_id=message.message_id
        )
        
        logger.info(f"✅ SAVED: Links saved to database successfully")
        
        # Получаем текст напоминания
        reminder_text = db.get_reminder_text()
        logger.info(f"📝 REMINDER: Using reminder text (length: {len(reminder_text)})")
        
        # Отправляем ответ
        logger.info(f"📤 SENDING: Sending response with {RESPONSE_DELAY}s delay")
        success = safe_send_message(
            chat_id=GROUP_ID,
            text=reminder_text,
            message_thread_id=THREAD_ID,
            reply_to_message_id=message.message_id
        )
        
        if success:
            logger.info(f"✅ SENT: Response sent successfully")
            
            # Обновляем лимиты
            db.update_response_limits()
            logger.info(f"📊 LIMITS: Rate limits updated")
            
            # Логируем ответ
            db.log_bot_response(user_id, reminder_text)
            logger.info(f"📋 LOGGED: Response logged to database")
            
            logger.info(f"🎉 SUCCESS: Complete response cycle for user {username} ({len(links)} links)")
        else:
            logger.error(f"❌ FAILED: Failed to send response")
        
    except Exception as e:
        logger.error(f"💥 ERROR: Exception in message processing: {str(e)}")
        logger.error(f"💥 ERROR_TYPE: {type(e).__name__}: {e}")

def setup_webhook():
    """Настройка webhook"""
    try:
        logger.info("🔧 WEBHOOK_SETUP: Starting webhook configuration")
        
        # Удаляем старый webhook
        bot.remove_webhook()
        logger.info("✅ WEBHOOK_CLEAN: Old webhook removed successfully")
        
        # Устанавливаем новый webhook
        webhook_result = bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"✅ WEBHOOK_SET: New webhook set to {WEBHOOK_URL}, result: {webhook_result}")
        
        return True
    except Exception as e:
        logger.error(f"❌ WEBHOOK_ERROR: Failed to setup webhook: {str(e)}")
        logger.error(f"❌ WEBHOOK_ERROR_TYPE: {type(e).__name__}: {e}")
        return False

def main():
    """Основная функция запуска бота"""
    try:
        logger.info("🚀 STARTUP: Starting Presave Reminder Bot")
        logger.info(f"🔧 CONFIG: GROUP_ID={GROUP_ID}, THREAD_ID={THREAD_ID}, ADMIN_IDS={ADMIN_IDS}")
        logger.info(f"🌐 WEBHOOK: WEBHOOK_HOST={WEBHOOK_HOST}, WEBHOOK_PORT={WEBHOOK_PORT}")
        
        # Инициализация базы данных
        logger.info("💾 DATABASE: Initializing database")
        db.init_db()
        logger.info("✅ DATABASE: Database initialized successfully")
        
        logger.info("🤖 Presave Reminder Bot запущен и готов к работе!")
        logger.info(f"👥 Группа: {GROUP_ID}")
        logger.info(f"📋 Топик: {THREAD_ID}")
        logger.info(f"👑 Админы: {ADMIN_IDS}")
        
        # Настройка webhook
        logger.info("🔧 WEBHOOK: Setting up webhook")
        if setup_webhook():
            logger.info("🔗 Webhook режим активен")
        else:
            logger.error("❌ Ошибка настройки webhook")
            return
        
        # Запуск webhook сервера
        logger.info(f"🌐 SERVER: Starting webhook server on port {WEBHOOK_PORT}")
        with socketserver.TCPServer(("", WEBHOOK_PORT), WebhookHandler) as httpd:
            logger.info(f"🌐 Webhook сервер запущен на порту {WEBHOOK_PORT}")
            logger.info(f"🔗 URL: {WEBHOOK_URL}")
            logger.info("✅ READY: Bot is fully operational and ready to receive webhooks")
            httpd.serve_forever()
        
    except Exception as e:
        logger.error(f"💥 CRITICAL: Critical error in main: {str(e)}")
        logger.error(f"💥 CRITICAL_TYPE: {type(e).__name__}: {e}")
    finally:
        # Очищаем webhook при остановке
        try:
            logger.info("🧹 SHUTDOWN: Cleaning up webhook on shutdown")
            bot.remove_webhook()
            logger.info("🧹 Webhook очищен при остановке")
        except Exception as e:
            logger.error(f"⚠️ CLEANUP_ERROR: Error during webhook cleanup: {e}")
        logger.info("🛑 SHUTDOWN: Bot stopped")

if __name__ == "__main__":
    main()
