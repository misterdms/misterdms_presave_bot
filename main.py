import asyncio
import logging
import re
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import Message
import aiosqlite
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_ID = int(os.getenv('GROUP_ID'))  # -1002811959953
THREAD_ID = int(os.getenv('THREAD_ID'))  # 3
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
DEFAULT_REMINDER = os.getenv('REMINDER_TEXT', '🎧 Напоминаем: не забудьте сделать пресейв артистов выше! ♥️')

# Константы безопасности
MAX_RESPONSES_PER_HOUR = 10
MIN_COOLDOWN_SECONDS = 30
BATCH_RESPONSE_WINDOW = 300  # 5 минут
RESPONSE_DELAY = 3

# Regex для поиска ссылок
URL_PATTERN = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
    
    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Таблица пользователей и их ссылок
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_links (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    total_links INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Детальная история ссылок
            await db.execute('''
                CREATE TABLE IF NOT EXISTS link_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    link_url TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_id INTEGER
                )
            ''')
            
            # Логи ответов бота
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bot_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    response_text TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Настройки бота
            await db.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            # Активность бота
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bot_activity (
                    id INTEGER PRIMARY KEY,
                    is_active BOOLEAN DEFAULT 1,
                    responses_today INTEGER DEFAULT 0,
                    last_response_time TIMESTAMP,
                    last_reset_date DATE DEFAULT CURRENT_DATE
                )
            ''')
            
            # Лимиты и cooldown
            await db.execute('''
                CREATE TABLE IF NOT EXISTS rate_limits (
                    id INTEGER PRIMARY KEY,
                    hourly_responses INTEGER DEFAULT 0,
                    last_hour_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cooldown_until TIMESTAMP
                )
            ''')
            
            # Инициализация базовых записей
            await db.execute('INSERT OR IGNORE INTO bot_activity (id, is_active) VALUES (1, 1)')
            await db.execute('INSERT OR IGNORE INTO rate_limits (id) VALUES (1)')
            await db.execute(
                'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                ('reminder_text', DEFAULT_REMINDER)
            )
            
            await db.commit()
            logger.info("База данных инициализирована")

    async def add_user_links(self, user_id: int, username: str, links: list, message_id: int):
        """Добавление ссылок пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Обновляем счётчик пользователя
            await db.execute('''
                INSERT OR REPLACE INTO user_links (user_id, username, total_links, last_updated)
                VALUES (?, ?, COALESCE((SELECT total_links FROM user_links WHERE user_id = ?), 0) + ?, CURRENT_TIMESTAMP)
            ''', (user_id, username, user_id, len(links)))
            
            # Добавляем детальную историю
            for link in links:
                await db.execute('''
                    INSERT INTO link_history (user_id, link_url, message_id)
                    VALUES (?, ?, ?)
                ''', (user_id, link, message_id))
            
            await db.commit()

    async def log_bot_response(self, user_id: int, response_text: str):
        """Логирование ответа бота"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO bot_responses (user_id, response_text)
                VALUES (?, ?)
            ''', (user_id, response_text))
            await db.commit()

    async def is_bot_active(self) -> bool:
        """Проверка активности бота"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT is_active FROM bot_activity WHERE id = 1')
            result = await cursor.fetchone()
            return bool(result[0]) if result else False

    async def set_bot_active(self, active: bool):
        """Установка статуса активности"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE bot_activity SET is_active = ? WHERE id = 1', (active,))
            await db.commit()

    async def can_send_response(self) -> tuple[bool, str]:
        """Проверка возможности отправки ответа с учетом лимитов"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT hourly_responses, last_hour_reset, cooldown_until
                FROM rate_limits WHERE id = 1
            ''')
            result = await cursor.fetchone()
            
            if not result:
                return False, "Ошибка получения лимитов"
            
            hourly_responses, last_hour_reset, cooldown_until = result
            now = datetime.now()
            
            # Проверяем cooldown
            if cooldown_until:
                cooldown_time = datetime.fromisoformat(cooldown_until)
                if now < cooldown_time:
                    remaining = int((cooldown_time - now).total_seconds())
                    return False, f"Cooldown активен. Осталось: {remaining} сек"
            
            # Сброс почасового счётчика
            if last_hour_reset:
                last_reset = datetime.fromisoformat(last_hour_reset)
                if now - last_reset > timedelta(hours=1):
                    await db.execute('''
                        UPDATE rate_limits 
                        SET hourly_responses = 0, last_hour_reset = ?
                        WHERE id = 1
                    ''', (now.isoformat(),))
                    hourly_responses = 0
            
            # Проверяем почасовой лимит
            if hourly_responses >= MAX_RESPONSES_PER_HOUR:
                return False, f"Достигнут лимит {MAX_RESPONSES_PER_HOUR} ответов в час"
            
            return True, "OK"

    async def update_response_limits(self):
        """Обновление лимитов после отправки ответа"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now()
            cooldown_until = now + timedelta(seconds=MIN_COOLDOWN_SECONDS)
            
            await db.execute('''
                UPDATE rate_limits 
                SET hourly_responses = hourly_responses + 1,
                    cooldown_until = ?
                WHERE id = 1
            ''', (cooldown_until.isoformat(),))
            
            await db.commit()

    async def get_user_stats(self, username: str = None):
        """Получение статистики пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            if username:
                # Статистика конкретного пользователя
                cursor = await db.execute('''
                    SELECT username, total_links, last_updated
                    FROM user_links 
                    WHERE username = ? AND total_links > 0
                ''', (username.replace('@', ''),))
                result = await cursor.fetchone()
                return result
            else:
                # Общая статистика
                cursor = await db.execute('''
                    SELECT username, total_links, last_updated
                    FROM user_links 
                    WHERE total_links > 0
                    ORDER BY total_links DESC
                ''')
                return await cursor.fetchall()

    async def get_bot_stats(self):
        """Статистика работы бота"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем лимиты
            cursor = await db.execute('''
                SELECT hourly_responses, cooldown_until FROM rate_limits WHERE id = 1
            ''')
            limits = await cursor.fetchone()
            
            # Получаем активность
            cursor = await db.execute('''
                SELECT is_active, last_response_time FROM bot_activity WHERE id = 1
            ''')
            activity = await cursor.fetchone()
            
            # Считаем ответы за сегодня
            cursor = await db.execute('''
                SELECT COUNT(*) FROM bot_responses 
                WHERE DATE(timestamp) = DATE('now')
            ''')
            today_responses = await cursor.fetchone()
            
            return {
                'hourly_responses': limits[0] if limits else 0,
                'hourly_limit': MAX_RESPONSES_PER_HOUR,
                'cooldown_until': limits[1] if limits else None,
                'is_active': bool(activity[0]) if activity else False,
                'last_response': activity[1] if activity else None,
                'today_responses': today_responses[0] if today_responses else 0
            }

    async def clear_link_history(self):
        """Очистка истории ссылок (счётчики остаются)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM link_history')
            await db.commit()

    async def get_reminder_text(self) -> str:
        """Получение текста напоминания"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT value FROM settings WHERE key = ?', ('reminder_text',))
            result = await cursor.fetchone()
            return result[0] if result else DEFAULT_REMINDER

    async def set_reminder_text(self, text: str):
        """Установка текста напоминания"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', ('reminder_text', text))
            await db.commit()

# Инициализация базы данных
db = Database()

def is_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in ADMIN_IDS

def extract_links(text: str) -> list:
    """Извлечение ссылок из текста"""
    return URL_PATTERN.findall(text)

async def safe_send_message(chat_id: int, text: str, message_thread_id: int = None, reply_to_message_id: int = None):
    """Безопасная отправка сообщения с обработкой ошибок"""
    try:
        await asyncio.sleep(RESPONSE_DELAY)  # Задержка перед отправкой
        await bot.send_message(
            chat_id=chat_id, 
            text=text, 
            message_thread_id=message_thread_id,
            reply_to_message_id=reply_to_message_id
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        return False

# === ОБРАБОТЧИКИ КОМАНД ===

@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    await message.answer("""
🤖 Presave Reminder Bot запущен!

Для управления используйте команду /help
Бот работает только в настроенном топике группы.
    """)

@dp.message(Command("help"))
async def cmd_help(message: Message):
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
    
    await message.answer(help_text)

@dp.message(Command("activate"))
async def cmd_activate(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    # Проверяем, что команда в нужном топике
    if message.chat.id != GROUP_ID or message.message_thread_id != THREAD_ID:
        await message.answer("❌ Команда должна выполняться в топике пресейвов")
        return
    
    await db.set_bot_active(True)
    
    welcome_text = """
🤖 Привет! Я бот для напоминаний о пресейвах!

✅ Активирован в топике "Пресейвы"
🎯 Буду отвечать на сообщения со ссылками
⚙️ Управление: /help
🛑 Отключить: /deactivate

Готов к работе! 🎵
    """
    
    await message.answer(welcome_text)
    logger.info(f"Бот активирован пользователем {message.from_user.id}")

@dp.message(Command("deactivate"))
async def cmd_deactivate(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    await db.set_bot_active(False)
    await message.answer("🛑 Бот деактивирован. Для включения используйте /activate")
    logger.info(f"Бот деактивирован пользователем {message.from_user.id}")

@dp.message(Command("botstat"))
async def cmd_bot_stat(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        stats = await db.get_bot_stats()
        
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

⚠️ Предупреждений: {'🟡 Приближение к лимиту' if stats['hourly_responses'] >= 8 else '✅ Всё в порядке'}
        """
        
        await message.answer(stat_text)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики бота: {e}")
        await message.answer("❌ Ошибка получения статистики")

@dp.message(Command("linkstats"))
async def cmd_link_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        users = await db.get_user_stats()
        
        if not users:
            await message.answer("📊 Пока нет пользователей с ссылками")
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
        
        await message.answer(stats_text)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики ссылок: {e}")
        await message.answer("❌ Ошибка получения статистики")

@dp.message(Command("topusers"))
async def cmd_top_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        users = await db.get_user_stats()
        
        if not users:
            await message.answer("🏆 Пока нет активных пользователей")
            return
        
        top_text = "🏆 Топ-5 самых активных:\n\n"
        
        for i, (username, total_links, last_updated) in enumerate(users[:5], 1):
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            medal = medals[i-1] if i <= 5 else "▫️"
            
            top_text += f"{medal} @{username} — {total_links} ссылок\n"
        
        await message.answer(top_text)
        
    except Exception as e:
        logger.error(f"Ошибка получения топа: {e}")
        await message.answer("❌ Ошибка получения топа")

@dp.message(Command("userstat"))
async def cmd_user_stat(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    # Извлекаем username из команды
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите username: /userstat @username")
        return
    
    username = args[1].replace('@', '')
    
    try:
        user_data = await db.get_user_stats(username)
        
        if not user_data:
            await message.answer(f"❌ Пользователь @{username} не найден или не имеет ссылок")
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
        
        await message.answer(stat_text)
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики пользователя: {e}")
        await message.answer("❌ Ошибка получения статистики пользователя")

@dp.message(Command("setmessage"))
async def cmd_set_message(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    # Извлекаем новый текст
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        current_text = await db.get_reminder_text()
        await message.answer(f"📝 Текущее сообщение:\n\n{current_text}\n\nДля изменения: /setmessage новый текст")
        return
    
    new_text = args[1]
    
    try:
        await db.set_reminder_text(new_text)
        await message.answer(f"✅ Текст напоминания обновлён:\n\n{new_text}")
        
    except Exception as e:
        logger.error(f"Ошибка обновления текста: {e}")
        await message.answer("❌ Ошибка обновления текста")

@dp.message(Command("clearhistory"))
async def cmd_clear_history(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    try:
        await db.clear_link_history()
        await message.answer("🧹 История ссылок очищена (общие счётчики сохранены)")
        
    except Exception as e:
        logger.error(f"Ошибка очистки истории: {e}")
        await message.answer("❌ Ошибка очистки истории")

@dp.message(Command("test_regex"))
async def cmd_test_regex(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    # Получаем текст для тестирования
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("🧪 Отправьте: /test_regex ваш текст со ссылками")
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
    
    await message.answer(result_text)

# === ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ===

@dp.message(F.chat.id == GROUP_ID, F.message_thread_id == THREAD_ID)
async def handle_topic_message(message: Message):
    """Обработка сообщений в топике пресейвов"""
    
    # Игнорируем команды и сообщения от ботов
    if message.text and message.text.startswith('/'):
        return
    
    if message.from_user.is_bot:
        return
    
    # Проверяем активность бота
    if not await db.is_bot_active():
        return
    
    # Извлекаем ссылки из сообщения
    message_text = message.text or message.caption or ""
    links = extract_links(message_text)
    
    if not links:
        return  # Нет ссылок - не отвечаем
    
    # Проверяем лимиты
    can_respond, reason = await db.can_send_response()
    
    if not can_respond:
        logger.warning(f"Ответ заблокирован: {reason}")
        return
    
    try:
        # Сохраняем ссылки в базу
        username = message.from_user.username or f"user_{message.from_user.id}"
        await db.add_user_links(
            user_id=message.from_user.id,
            username=username,
            links=links,
            message_id=message.message_id
        )
        
        # Получаем текст напоминания
        reminder_text = await db.get_reminder_text()
        
        # Отправляем ответ
        success = await safe_send_message(
            chat_id=GROUP_ID,
            text=reminder_text,
            message_thread_id=THREAD_ID,
            reply_to_message_id=message.message_id
        )
        
        if success:
            # Обновляем лимиты
            await db.update_response_limits()
            
            # Логируем ответ
            await db.log_bot_response(message.from_user.id, reminder_text)
            
            logger.info(f"Ответ отправлен пользователю {username} ({len(links)} ссылок)")
        
    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")

async def main():
    """Основная функция запуска бота"""
    try:
        # Инициализация базы данных
        await db.init_db()
        
        logger.info("🤖 Presave Reminder Bot запущен и готов к работе!")
        logger.info(f"👥 Группа: {GROUP_ID}")
        logger.info(f"📋 Топик: {THREAD_ID}")
        logger.info(f"👑 Админы: {ADMIN_IDS}")
        
        # Запуск бота
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())