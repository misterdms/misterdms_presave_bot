#!/usr/bin/env python3
"""
🚀 Do Presave Reminder Bot v25+ - ПЛАН 1 ТОЛЬКО
Минимальная версия без несуществующих модулей
"""

import os
import sys
from datetime import datetime, timezone

# Сторонние зависимости
import telebot
import psutil

# Локальные модули (только существующие!)
from config import config, ConfigError
from database.manager import get_database_manager, DatabaseError
from utils.logger import get_logger, setup_logging
from utils.helpers import MessageFormatter

# HTTP сервер
from webhooks.server import WebhookServer

# ============================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================

setup_logging()
logger = get_logger(__name__)

def main():
    """Главная функция - только Plan 1"""
    try:
        logger.info("🚀 Запуск Do Presave Reminder Bot v25+ (Plan 1)")
        logger.info(f"📅 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info(f"🌐 Порт: {config.PORT}")
        
        # 1. Создание бота
        logger.info("🤖 Создание Telegram бота...")
        bot = telebot.TeleBot(config.BOT_TOKEN, threaded=True)
        logger.info("✅ Telegram бот создан")
        
        # 2. Инициализация БД
        logger.info("🗄️ Подключение к PostgreSQL...")
        db = get_database_manager()
        db.init_database()
        logger.info("✅ База данных готова")
        
        # 3. Базовые команды (только существующие обработчики)
        @bot.message_handler(commands=['start'])
        def handle_start(message):
            try:
                bot.reply_to(message, """🎵 **Do Presave Reminder Bot v25+**

✅ План 1: Базовый функционал активен
⏳ План 2-4: В разработке

🤖 Бот работает в тестовом режиме
📊 Используйте /help для списка команд""", parse_mode='Markdown')
                logger.info(f"👤 Пользователь {message.from_user.id} использовал /start")
            except Exception as e:
                logger.error(f"❌ Ошибка /start: {e}")
        
        @bot.message_handler(commands=['help'])
        def handle_help(message):
            try:
                bot.reply_to(message, """📋 **ДОСТУПНЫЕ КОМАНДЫ:**

🎯 **Основные:**
• /start - Приветствие
• /help - Эта справка
• /status - Статус бота

⚙️ **Для админов:**
• /admin - Админское меню (в разработке)

🚀 **Версия:** v25+ (План 1)
📊 **Статус:** Базовый функционал""", parse_mode='Markdown')
                logger.info(f"👤 Пользователь {message.from_user.id} использовал /help")
            except Exception as e:
                logger.error(f"❌ Ошибка /help: {e}")
        
        @bot.message_handler(commands=['status'])
        def handle_status(message):
            try:
                bot.reply_to(message, f"""📊 **СТАТУС БОТА**

✅ План 1: Базовый функционал
⏳ План 2: Карма (в разработке)
⏳ План 3: ИИ и формы (в разработке)  
⏳ План 4: Backup (в разработке)

🗄️ **База данных:** PostgreSQL
🌐 **Сервер:** Render.com
⏰ **Время:** {datetime.now(timezone.utc).strftime('%H:%M UTC')}""", parse_mode='Markdown')
                logger.info(f"👤 Пользователь {message.from_user.id} использовал /status")
            except Exception as e:
                logger.error(f"❌ Ошибка /status: {e}")
        
        # 4. Создание webhook сервера
        logger.info("🌐 Создание webhook сервера...")
        webhook_server = WebhookServer(bot)
        
        # Добавляем простые endpoints
        @webhook_server.app.route('/test', methods=['GET'])
        def test_endpoint():
            return {
                'status': 'OK',
                'version': 'v25+',
                'plan': 1,
                'time': datetime.now(timezone.utc).isoformat(),
                'port': config.PORT
            }
        
        logger.info("✅ Webhook сервер готов")
        
        # 5. Уведомление админов
        for admin_id in config.ADMIN_IDS:
            try:
                bot.send_message(admin_id, f"""🚀 **Bot v25+ запущен!**

✅ План 1: Активен
🌐 Порт: {config.PORT}
🗄️ БД: PostgreSQL
⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}

🎯 Базовый функционал готов к работе!""", parse_mode='Markdown')
            except Exception as e:
                logger.warning(f"⚠️ Не удалось уведомить админа {admin_id}: {e}")
        
        # 6. ЗАПУСК FLASK СЕРВЕРА
        logger.info(f"🚀 ЗАПУСК на порту {config.PORT}...")
        webhook_server.app.run(
            host='0.0.0.0',
            port=config.PORT,
            debug=False,
            use_reloader=False,
            threaded=True
        )
        
    except ConfigError as e:
        logger.error(f"⚙️ Ошибка конфигурации: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
