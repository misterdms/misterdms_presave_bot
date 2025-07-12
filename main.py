#!/usr/bin/env python3
"""
🚀 Do Presave Reminder Bot v25+ - Main Entry Point
Центральная точка запуска с поэтапной загрузкой модулей
"""

import os
import sys
import asyncio
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Optional

# Сторонние зависимости
import telebot
from telebot import types
import psutil

# Локальные модули
from config import config, ConfigError
from database.manager import get_database_manager, DatabaseError
from utils.logger import get_logger, setup_main_logger
from utils.security import security_manager
from utils.helpers import MessageFormatter, SystemMonitor

# HTTP сервер и keep-alive
from webhooks.server import WebhookServer
from webhooks.keepalive import EnhancedKeepAlive as KeepAliveManager

# ============================================
# ОСНОВНЫЕ КОМПОНЕНТЫ ПЛАН 1
# ============================================

# Обработчики событий
from handlers.menu import MenuManager
from handlers.commands import register_basic_commands
from handlers.callbacks import register_callback_handlers
from handlers.messages import MessageHandler
from handlers.links import LinkHandler

# ============================================
# УСЛОВНАЯ ЗАГРУЗКА ПЛАНОВ 2-4
# ============================================

# План 2 - Система кармы (загружается при ENABLE_PLAN_2_FEATURES=true)
if config.ENABLE_PLAN_2_FEATURES:
    from services.karma import KarmaManager, init_karma_system
    from handlers.karma_commands import register_karma_commands

# План 3 - ИИ и формы (загружается при ENABLE_PLAN_3_FEATURES=true)  
if config.ENABLE_PLAN_3_FEATURES:
    from services.ai import AIManager, init_ai_system
    from services.gratitude import GratitudeDetector, init_gratitude_system
    from forms.form_manager import FormManager, init_forms_system
    from handlers.ai_handlers import register_ai_handlers
    from handlers.form_handlers import register_form_handlers

# План 4 - Backup система (загружается ВСЕГДА для PostgreSQL!)
if config.ENABLE_PLAN_4_FEATURES:
    from services.backup_restore import BackupRestoreManager, init_backup_manager
    from services.backup_scheduler import BackupScheduler, init_backup_scheduler
    from handlers.backup_commands import register_backup_commands

# ============================================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# ============================================

logger = get_logger(__name__)
bot: Optional[telebot.TeleBot] = None
webhook_server: Optional[WebhookServer] = None
keepalive_manager: Optional[KeepAliveManager] = None
shutdown_flag = threading.Event()

# Менеджеры компонентов
database_manager = None
menu_manager = None
message_handler = None
link_handler = None

# Менеджеры планов (условные)
karma_manager = None
ai_manager = None
gratitude_detector = None
form_manager = None
backup_manager = None
backup_scheduler = None

# ============================================
# КЛАСС ОСНОВНОГО ПРИЛОЖЕНИЯ
# ============================================

class PresaveBotApplication:
    """Главный класс приложения бота"""
    
    def __init__(self):
        """Инициализация приложения"""
        self.start_time = datetime.now(timezone.utc)
        self.system_monitor = SystemMonitor()
        self.is_running = False
        
        logger.info("🚀 Инициализация Do Presave Reminder Bot v25+")
        logger.info(f"📅 Время запуска: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
    def initialize_bot(self):
        """Инициализация Telegram бота"""
        global bot
        
        try:
            logger.info("🤖 Создание экземпляра Telegram бота...")
            bot = telebot.TeleBot(config.BOT_TOKEN, threaded=True)
            
            # Настройка webhook если нужно
            if config.WEBHOOK_URL:
                logger.info(f"🔗 Настройка webhook: {config.WEBHOOK_URL}")
                bot.remove_webhook()
                bot.set_webhook(
                    url=config.WEBHOOK_URL,
                    secret_token=config.WEBHOOK_SECRET,
                    max_connections=config.WEBHOOK_MAX_CONNECTIONS
                )
            else:
                logger.info("📡 Режим polling (без webhook)")
                bot.remove_webhook()
            
            logger.info("✅ Telegram бот инициализирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота: {e}")
            return False
    
    def initialize_database(self):
        """Инициализация базы данных"""
        global database_manager
        
        try:
            logger.info("🗄️ Инициализация базы данных...")
            database_manager = get_database_manager()
            
            # Создание таблиц
            database_manager.init_database()
            
            # Проверка подключения
            if database_manager.test_connection():
                logger.info("✅ База данных инициализирована и доступна")
                
                # Логирование статистики БД
                stats = database_manager.get_database_stats()
                logger.info(f"📊 Статистика БД: {stats.get('total_users', 0)} пользователей, {stats.get('total_links', 0)} ссылок")
                
                return True
            else:
                logger.error("❌ Не удается подключиться к базе данных")
                return False
                
        except DatabaseError as e:
            logger.error(f"❌ Ошибка базы данных: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка БД: {e}")
            return False
    
    def initialize_core_handlers(self):
        """Инициализация основных обработчиков План 1"""
        global menu_manager, message_handler, link_handler
        
        try:
            logger.info("🎛️ Инициализация основных обработчиков...")
            
            # Менеджер меню
            menu_manager = MenuManager(bot)
            logger.info("✅ MenuManager инициализирован")
            
            # Обработчик сообщений
            message_handler = MessageHandler(bot)
            logger.info("✅ MessageHandler инициализирован")
            
            # Обработчик ссылок
            link_handler = LinkHandler(bot)
            logger.info("✅ LinkHandler инициализирован")
            
            # Регистрация базовых команд
            register_basic_commands(bot)
            logger.info("✅ Базовые команды зарегистрированы")
            
            # Регистрация обработчиков callback
            register_callback_handlers(bot)
            logger.info("✅ Callback обработчики зарегистрированы")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации обработчиков: {e}")
            return False
    
    def initialize_plan_2_features(self):
        """Инициализация функций План 2 - Система кармы"""
        if not config.ENABLE_PLAN_2_FEATURES:
            logger.info("⏭️ План 2 отключен (ENABLE_PLAN_2_FEATURES=false)")
            return True
            
        global karma_manager
        
        try:
            logger.info("🏆 Инициализация системы кармы (План 2)...")
            
            # Инициализация системы кармы
            karma_manager = init_karma_system(database_manager)
            logger.info("✅ KarmaManager инициализирован")
            
            # Регистрация команд кармы
            register_karma_commands(bot, karma_manager)
            logger.info("✅ Команды кармы зарегистрированы")
            
            logger.info("🎉 План 2 (Система кармы) активирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации План 2: {e}")
            return False
    
    def initialize_plan_3_features(self):
        """Инициализация функций План 3 - ИИ и формы"""
        if not config.ENABLE_PLAN_3_FEATURES:
            logger.info("⏭️ План 3 отключен (ENABLE_PLAN_3_FEATURES=false)")
            return True
            
        global ai_manager, gratitude_detector, form_manager
        
        try:
            logger.info("🤖 Инициализация ИИ и форм (План 3)...")
            
            # Инициализация ИИ системы
            ai_manager = init_ai_system()
            logger.info("✅ AIManager инициализирован")
            
            # Инициализация детектора благодарностей
            gratitude_detector = init_gratitude_system(database_manager, karma_manager if config.ENABLE_PLAN_2_FEATURES else None)
            logger.info("✅ GratitudeDetector инициализирован")
            
            # Инициализация системы форм
            form_manager = init_forms_system(database_manager)
            logger.info("✅ FormManager инициализирован")
            
            # Регистрация обработчиков ИИ
            register_ai_handlers(bot, ai_manager)
            logger.info("✅ ИИ обработчики зарегистрированы")
            
            # Регистрация обработчиков форм
            register_form_handlers(bot, form_manager)
            logger.info("✅ Обработчики форм зарегистрированы")
            
            logger.info("🎉 План 3 (ИИ и формы) активирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации План 3: {e}")
            return False
    
    def initialize_plan_4_features(self):
        """Инициализация функций План 4 - Backup система"""
        if not config.ENABLE_PLAN_4_FEATURES:
            logger.warning("⚠️ План 4 отключен - КРИТИЧНО для PostgreSQL!")
            return True
            
        global backup_manager, backup_scheduler
        
        try:
            logger.info("💾 Инициализация backup системы (План 4)...")
            
            # Инициализация backup менеджера
            backup_manager = init_backup_manager(database_manager)
            logger.info("✅ BackupRestoreManager инициализирован")
            
            # Проверка возраста БД
            age_days = backup_manager.get_database_age_days()
            days_left = backup_manager.days_until_expiry()
            
            if days_left <= 5:
                logger.warning(f"🚨 КРИТИЧНО! БД истечет через {days_left} дней (возраст: {age_days} дней)")
            elif days_left <= 10:
                logger.warning(f"⚠️ Внимание! БД истечет через {days_left} дней (возраст: {age_days} дней)")
            else:
                logger.info(f"✅ БД в норме: осталось {days_left} дней (возраст: {age_days} дней)")
            
            # Инициализация планировщика
            backup_scheduler = init_backup_scheduler(bot)
            logger.info("✅ BackupScheduler инициализирован")
            
            # Регистрация backup команд
            register_backup_commands(bot, backup_manager)
            logger.info("✅ Backup команды зарегистрированы")
            
            logger.info("🎉 План 4 (Backup система) активирован")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации План 4: {e}")
            return False
    
    def initialize_http_server(self):
        """Инициализация HTTP сервера"""
        global webhook_server
        
        try:
            logger.info("🌐 Инициализация HTTP сервера...")
            
            # Создание webhook сервера
            webhook_server = WebhookServer(
                bot=bot,
                port=config.PORT,
                host=config.HOST,
                webhook_path=config.WEBHOOK_PATH,
                webhook_secret=config.WEBHOOK_SECRET
            )
            
            # Запуск сервера в отдельном потоке
            server_thread = threading.Thread(
                target=webhook_server.start_server,
                daemon=True,
                name="WebhookServer"
            )
            server_thread.start()
            
            logger.info(f"✅ HTTP сервер запущен на {config.HOST}:{config.PORT}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска HTTP сервера: {e}")
            return False
    
    def initialize_keepalive(self):
        """Инициализация keep-alive для Render.com"""
        global keepalive_manager
        
        try:
            logger.info("💓 Инициализация keep-alive системы...")
            
            # Создание keep-alive менеджера
            keepalive_manager = KeepAliveManager(
                target_url=config.KEEPALIVE_URL or f"https://{config.HOST}:{config.PORT}/health",
                interval=config.KEEPALIVE_INTERVAL,
                enabled=config.KEEPALIVE_ENABLED
            )
            
            # Запуск в отдельном потоке
            if keepalive_manager.enabled:
                keepalive_thread = threading.Thread(
                    target=keepalive_manager.start_keepalive,
                    daemon=True,
                    name="KeepAlive"
                )
                keepalive_thread.start()
                logger.info(f"✅ Keep-alive активирован (интервал: {config.KEEPALIVE_INTERVAL}с)")
            else:
                logger.info("⏭️ Keep-alive отключен")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации keep-alive: {e}")
            return False
    
    def start_bot(self):
        """Запуск основного цикла бота"""
        try:
            self.is_running = True
            logger.info("🔄 Запуск основного цикла бота...")
            
            if config.WEBHOOK_URL:
                logger.info("📡 Режим webhook - ожидание запросов...")
                # В режиме webhook просто ждем
                while self.is_running and not shutdown_flag.is_set():
                    time.sleep(1)
            else:
                logger.info("📡 Режим polling - начинаем опрос...")
                # В режиме polling активно опрашиваем
                bot.polling(
                    none_stop=True,
                    interval=config.POLLING_INTERVAL,
                    timeout=config.POLLING_TIMEOUT
                )
                
        except KeyboardInterrupt:
            logger.info("⌨️ Получен сигнал остановки от клавиатуры")
        except Exception as e:
            logger.error(f"❌ Ошибка в основном цикле: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Корректное завершение работы"""
        logger.info("🔄 Начинаем корректное завершение работы...")
        
        self.is_running = False
        shutdown_flag.set()
        
        try:
            # Остановка webhook сервера
            if webhook_server:
                webhook_server.shutdown()
                logger.info("✅ HTTP сервер остановлен")
            
            # Остановка keep-alive
            if keepalive_manager:
                keepalive_manager.stop()
                logger.info("✅ Keep-alive остановлен")
            
            # Остановка планировщика backup
            if backup_scheduler and config.ENABLE_PLAN_4_FEATURES:
                backup_scheduler.stop_scheduler()
                logger.info("✅ Backup планировщик остановлен")
            
            # Закрытие подключения к БД
            if database_manager:
                database_manager.close_connection()
                logger.info("✅ Подключение к БД закрыто")
            
            # Остановка бота
            if bot:
                bot.stop_polling()
                logger.info("✅ Бот остановлен")
            
            uptime = datetime.now(timezone.utc) - self.start_time
            logger.info(f"⏱️ Время работы: {uptime}")
            logger.info("👋 Do Presave Reminder Bot завершил работу")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при завершении: {e}")

# ============================================
# ОБРАБОТЧИКИ СИГНАЛОВ
# ============================================

def signal_handler(signum, frame):
    """Обработчик сигналов завершения"""
    logger.info(f"📨 Получен сигнал {signum}")
    shutdown_flag.set()

# ============================================
# ФУНКЦИЯ MAIN
# ============================================

def main():
    """Главная функция запуска приложения"""
    
    # Настройка логирования
    setup_main_logger()
    
    # Вывод информации о запуске
    logger.info("=" * 60)
    logger.info("🎵 DO PRESAVE REMINDER BOT v25+ 🎵")
    logger.info("Автоматизация взаимных пресейвов в музыкальном сообществе")
    logger.info(f"Разработчик: @Mister_DMS")
    logger.info(f"Архитектура: Модульная (4 плана развития)")
    logger.info(f"База данных: PostgreSQL")
    logger.info(f"Платформа: Render.com + UptimeRobot")
    logger.info("=" * 60)
    
    try:
        # Валидация конфигурации
        logger.info("🔧 Проверка конфигурации...")
        logger.info(f"📊 Планы: План1=✅ План2={'✅' if config.ENABLE_PLAN_2_FEATURES else '❌'} План3={'✅' if config.ENABLE_PLAN_3_FEATURES else '❌'} План4={'✅' if config.ENABLE_PLAN_4_FEATURES else '❌'}")
        logger.info(f"🗄️ БД: {config.DATABASE_URL.split('@')[1] if '@' in config.DATABASE_URL else 'локальная'}")
        logger.info(f"🔗 Webhook: {'включен' if config.WEBHOOK_URL else 'отключен (polling)'}")
        
        # Создание приложения
        app = PresaveBotApplication()
        
        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Пошаговая инициализация
        logger.info("🚀 Начинаем пошаговую инициализацию...")
        
        # Шаг 1: Инициализация бота
        if not app.initialize_bot():
            logger.error("💥 Критическая ошибка: не удалось инициализировать бота")
            sys.exit(1)
        
        # Шаг 2: Инициализация базы данных
        if not app.initialize_database():
            logger.error("💥 Критическая ошибка: не удалось инициализировать БД")
            sys.exit(1)
        
        # Шаг 3: Инициализация основных обработчиков
        if not app.initialize_core_handlers():
            logger.error("💥 Критическая ошибка: не удалось инициализировать обработчики")
            sys.exit(1)
        
        # Шаг 4: Инициализация План 2 (если включен)
        if not app.initialize_plan_2_features():
            logger.error("💥 Ошибка инициализации План 2")
            sys.exit(1)
        
        # Шаг 5: Инициализация План 3 (если включен)
        if not app.initialize_plan_3_features():
            logger.error("💥 Ошибка инициализации План 3")
            sys.exit(1)
        
        # Шаг 6: Инициализация План 4 (если включен)
        if not app.initialize_plan_4_features():
            logger.error("💥 Ошибка инициализации План 4")
            sys.exit(1)
        
        # Шаг 7: Запуск HTTP сервера
        if not app.initialize_http_server():
            logger.error("💥 Критическая ошибка: не удалось запустить HTTP сервер")
            sys.exit(1)
        
        # Шаг 8: Запуск keep-alive
        if not app.initialize_keepalive():
            logger.error("💥 Ошибка инициализации keep-alive")
            # Не критично, продолжаем
        
        # Финальная проверка
        logger.info("🏁 Все компоненты инициализированы успешно!")
        
        # Отправка уведомления админам
        try:
            for admin_id in config.ADMIN_IDS:
                bot.send_message(
                    admin_id,
                    f"""🚀 **Bot started successfully!**
                    
📊 **Status:**
• Version: v25+
• Database: Connected ✅
• Plans: {f'1✅ 2{"✅" if config.ENABLE_PLAN_2_FEATURES else "❌"} 3{"✅" if config.ENABLE_PLAN_3_FEATURES else "❌"} 4{"✅" if config.ENABLE_PLAN_4_FEATURES else "❌"}'}
• Mode: {'Webhook' if config.WEBHOOK_URL else 'Polling'}

🎯 Ready to help musicians with presaves!""",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить уведомление админам: {e}")
        
        # Запуск основного цикла
        logger.info("🎉 Запускаем бота! Удачных пресейвов! 🎵")
        app.start_bot()
        
    except ConfigError as e:
        logger.error(f"⚙️ Ошибка конфигурации: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("⌨️ Остановка по запросу пользователя")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

# ============================================
# ТОЧКА ВХОДА
# ============================================

if __name__ == "__main__":
    main()
