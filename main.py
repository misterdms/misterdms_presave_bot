#!/usr/bin/env python3
"""
🚀 Do Presave Reminder Bot v25+ - ОТЛАДОЧНАЯ ВЕРСИЯ
"""

import os
import sys
from datetime import datetime, timezone

print("=== DEBUG: Начало main.py ===")

try:
    print("DEBUG: Импорт telebot...")
    import telebot
    print("DEBUG: ✅ telebot импортирован")
    
    print("DEBUG: Импорт psutil...")
    import psutil
    print("DEBUG: ✅ psutil импортирован")
    
    print("DEBUG: Импорт config...")
    from config import config, ConfigError
    print("DEBUG: ✅ config импортирован")
    print(f"DEBUG: PORT = {config.PORT}")
    
    print("DEBUG: Импорт database.manager...")
    from database.manager import get_database_manager, DatabaseError
    print("DEBUG: ✅ database.manager импортирован")
    
    print("DEBUG: Импорт utils.logger...")
    from utils.logger import get_logger, setup_logging
    print("DEBUG: ✅ utils.logger импортирован")
    
    print("DEBUG: Настройка логирования...")
    setup_logging()
    logger = get_logger(__name__)
    print("DEBUG: ✅ логирование настроено")
    
    print("DEBUG: Импорт utils.helpers...")
    from utils.helpers import MessageFormatter
    print("DEBUG: ✅ utils.helpers импортирован")
    
    print("DEBUG: Импорт webhooks.server...")
    from webhooks.server import WebhookServer
    print("DEBUG: ✅ webhooks.server импортирован")
    
    print("DEBUG: Создание бота...")
    bot = telebot.TeleBot(config.BOT_TOKEN, threaded=True)
    print("DEBUG: ✅ бот создан")
    
    print("DEBUG: Инициализация БД...")
    db = get_database_manager()
    print("DEBUG: ✅ database manager получен")
    
    print("DEBUG: Создание webhook сервера...")
    webhook_server = WebhookServer(bot)
    print("DEBUG: ✅ webhook сервер создан")
    
    print(f"DEBUG: Запуск Flask на порту {config.PORT}...")
    
    # Добавляем простой route для тестирования
    @webhook_server.app.route('/debug', methods=['GET'])
    def debug_endpoint():
        return f"DEBUG OK! Port: {config.PORT}, Time: {datetime.now()}"
    
    print("DEBUG: Запускаем Flask сервер...")
    webhook_server.app.run(
        host='0.0.0.0',
        port=config.PORT,
        debug=False,
        use_reloader=False,
        threaded=True
    )
    
except Exception as e:
    print(f"DEBUG: ❌ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
