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
        time.sleep(RESPONSE_DELAY)  # Задержка перед отправкой
        
        if message_thread_id:
            # Если есть thread_id, отправляем в топик
            bot.send_message(
                chat_id=chat_id, 
                text=text, 
                message_thread_id=message_thread_id,
                reply_to_message_id=reply_to_message_id
            )
        else:
            # Обычное сообщение
            if reply_to_message_id:
                bot.reply_to(reply_to_message_id, text)
            else:
                bot.send_message(chat_id, text)
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return False

# Webhook сервер
class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Обработка POST запросов от Telegram"""
        if self.path == WEBHOOK_PATH:
            try:
                # Получаем данные
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                # Парсим JSON
                update_data = json.loads(post_data.decode('utf-8'))
                
                # Создаем объект Update
                update = telebot.types.Update.de_json(update_data)
                
                # Обрабатываем update
                if update:
                    bot.process_new_updates([update])
                
                # Отвечаем Telegram
                self.send_response(200)
                self.end_headers()
                
            except Exception as e:
                logger.error(f"Ошибка обработки webhook: {e}")
                self.send_response(500)
                self.end_headers()
        
        elif self.path == '/' or self.path == '/health':
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
                "webhook_url": WEBHOOK_URL,
                "bot": "@misterdms_presave_bot"
            })
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Отключаем HTTP логи для чистоты
        pass

# === ОБРАБОТЧИКИ КОМАНД ===

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if not is_admin(message.from_user.id):
        return
    
    bot.reply_to(message, """
🤖 Presave Reminder Bot запущен!

Для управления используйте команду /help
Бот работает только в настроенном топике группы.
    """)

@bot.message_handler(commands=['help'])
def cmd_help(message):
    if not is_admin(message.from_user.id):
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

ℹ️ Бот автоматически отвечает на сообщения со ссылками в топике пресейвов
🛡️ Защита от спама: максимум 10 ответов в час, пауза 30 сек между ответами
    """
    
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['activate'])
def cmd_activate(message):
    if not is_admin(message.from_user.id):
        return
    
    # Проверяем, что команда в нужном топике
    if message.chat.id != GROUP_ID or message.message_thread_id != THREAD_ID:
        bot.reply_to(message, "❌ Команда должна выполняться в топике пресейвов")
        return
    
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
    logger.info(f"Бот активирован пользователем {message.from_user.id}")

@bot.message_handler(commands=['deactivate'])
def cmd_deactivate(message):
    if not is_admin(message.from_user.id):
        return
    
    db.set_bot_active(False)
    bot.reply_to(message, "🛑 Бот деактивирован. Для включения используйте /activate")
    logger.info(f"Бот деактивирован пользователем {message.from_user.id}")

@bot.message_handler(commands=['botstat'])
def cmd_bot_stat(message):
    if not is_admin(message.from_user.id):
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
        
        bot.reply_to(message, stat_text)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики бота: {e}")
        bot.reply_to(message, "❌ Ошибка получения статистики")

@bot.message_handler(commands=['linkstats'])
def cmd_link_stats(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        users = db.get_user_stats()
        
        if not users:
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
        
        bot.reply_to(message, stats_text)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики ссылок: {e}")
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
        logger.error(f"Ошибка получения топа: {e}")
        bot.reply_to(message, "❌ Ошибка получения топа")

@bot.message_handler(commands=['userstat'])
def cmd_user_stat(message):
    if not is_admin(message.from_user.id):
        return
    
    # Извлекаем username из команды
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
        
        bot.reply_to(message, stat_text)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики пользователя: {e}")
        bot.reply_to(message, "❌ Ошибка получения статистики пользователя")

@bot.message_handler(commands=['setmessage'])
def cmd_set_message(message):
    if not is_admin(message.from_user.id):
        return
    
    # Извлекаем новый текст
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
        logger.error(f"Ошибка обновления текста: {e}")
        bot.reply_to(message, "❌ Ошибка обновления текста")

@bot.message_handler(commands=['clearhistory'])
def cmd_clear_history(message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        db.clear_link_history()
        bot.reply_to(message, "🧹 История ссылок очищена (общие счётчики сохранены)")
        
    except Exception as e:
        logger.error(f"Ошибка очистки истории: {e}")
        bot.reply_to(message, "❌ Ошибка очистки истории")

@bot.message_handler(commands=['test_regex'])
def cmd_test_regex(message):
    if not is_admin(message.from_user.id):
        return
    
    # Получаем текст для тестирования
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "🧪 Отправьте: /test_regex ваш текст со ссылками")
        return
    
    test_text = args[1]
    links = extract_links(test_text)
    
    result_text = f"🧪 Результат тестирования:\n\n📝 Текст: {test_text}\n\n"
    
    if links:
        result_text += f"✅ Найдено ссылок: {len(links)}\n"
        for i, link in enumerate(links, 1):
            result_text += f"{i}. {link}\n"
        result_text += "\n👍 Бот ответит на такое сообщение"
    else:
        result_text += "❌ Ссылки не найдены\n👎 Бот НЕ ответит на такое сообщение"
    
    bot.reply_to(message, result_text)

# === ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ===

@bot.message_handler(func=lambda message: message.chat.id == GROUP_ID and message.message_thread_id == THREAD_ID)
def handle_topic_message(message):
    """Обработка сообщений в топике пресейвов"""
    
    # Игнорируем команды и сообщения от ботов
    if message.text and message.text.startswith('/'):
        return
    
    if message.from_user.is_bot:
        return
    
    # Проверяем активность бота
    if not db.is_bot_active():
        return
    
    # Извлекаем ссылки из сообщения
    message_text = message.text or message.caption or ""
    links = extract_links(message_text)
    
    if not links:
        return  # Нет ссылок - не отвечаем
    
    # Проверяем лимиты
    can_respond, reason = db.can_send_response()
    
    if not can_respond:
        logger.warning(f"Ответ заблокирован: {reason}")
        return
    
    try:
        # Сохраняем ссылки в базу
        username = message.from_user.username or f"user_{message.from_user.id}"
        db.add_user_links(
            user_id=message.from_user.id,
            username=username,
            links=links,
            message_id=message.message_id
        )
        
        # Получаем текст напоминания
        reminder_text = db.get_reminder_text()
        
        # Отправляем ответ
        success = safe_send_message(
            chat_id=GROUP_ID,
            text=reminder_text,
            message_thread_id=THREAD_ID,
            reply_to_message_id=message.message_id
        )
        
        if success:
            # Обновляем лимиты
            db.update_response_limits()
            
            # Логируем ответ
            db.log_bot_response(message.from_user.id, reminder_text)
            
            logger.info(f"Ответ отправлен пользователю {username} ({len(links)} ссылок)")
        
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")

def setup_webhook():
    """Настройка webhook"""
    try:
        # Удаляем старый webhook
        bot.remove_webhook()
        logger.info("✅ Старый webhook удален")
        
        # Устанавливаем новый webhook
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"✅ Webhook установлен: {WEBHOOK_URL}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка установки webhook: {e}")
        return False

def main():
    """Основная функция запуска бота"""
    try:
        # Инициализация базы данных
        db.init_db()
        
        logger.info("🤖 Presave Reminder Bot запущен и готов к работе!")
        logger.info(f"👥 Группа: {GROUP_ID}")
        logger.info(f"📋 Топик: {THREAD_ID}")
        logger.info(f"👑 Админы: {ADMIN_IDS}")
        
        # Настройка webhook
        if setup_webhook():
            logger.info("🔗 Webhook режим активен")
        else:
            logger.error("❌ Ошибка настройки webhook")
            return
        
        # Запуск webhook сервера
        with socketserver.TCPServer(("", WEBHOOK_PORT), WebhookHandler) as httpd:
            logger.info(f"🌐 Webhook сервер запущен на порту {WEBHOOK_PORT}")
            logger.info(f"🔗 URL: {WEBHOOK_URL}")
            httpd.serve_forever()
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        # Очищаем webhook при остановке
        try:
            bot.remove_webhook()
            logger.info("🧹 Webhook очищен при остановке")
        except:
            pass
        logger.info("Бот остановлен")

if __name__ == "__main__":
    main()
