#!/usr/bin/env python3
"""
Do Presave Reminder Bot v25+ - Главный файл запуска
Модульная архитектура с поэтапным развитием функционала

ПЛАН 1: Базовый функционал (АКТИВЕН)
ПЛАН 2: Система кармы (ЗАГЛУШКИ)  
ПЛАН 3: ИИ и формы (ЗАГЛУШКИ)
ПЛАН 4: Backup система (ЗАГЛУШКИ)
"""

import os
import sys
import time
import threading
from typing import Optional

# Основные импорты
import telebot
from telebot.types import Message, CallbackQuery

# Конфигурация и утилиты
from config import Config, validate_config
from utils.logger import get_logger, setup_logging
from utils.security import SecurityManager
from utils.helpers import format_user_mention

# База данных
from database.manager import DatabaseManager
from database.models import init_database_models

# Обработчики ПЛАН 1 (АКТИВНЫЕ)
from handlers.menu import MenuHandler
from handlers.commands import CommandHandler  
from handlers.callbacks import CallbackHandler
from handlers.messages import MessageHandler
from handlers.links import LinkHandler

# ПЛАН 2: Система кармы (ЗАГЛУШКИ)
# from services.karma import KarmaManager, init_karma_system
# from database.analytics import AnalyticsManager

# ПЛАН 3: ИИ и формы (ЗАГЛУШКИ)
# from services.ai import AIManager, init_ai_system
# from services.gratitude import GratitudeDetector, init_gratitude_system
# from services.forms import FormManager, init_forms_system
# from handlers.ai_handlers import AIHandler
# from handlers.form_handlers import FormHandler

# ПЛАН 4: Backup система (ЗАГЛУШКИ)
# from services.backup_restore import BackupRestoreManager, init_backup_manager
# from services.backup_scheduler import BackupScheduler, init_backup_scheduler
# from handlers.backup_commands import BackupCommandHandler

# HTTP сервер и keep-alive
from webhooks.server import WebhookServer
from webhooks.keepalive import KeepAliveManager

# Инициализация логирования
logger = get_logger(__name__)

class PresaveBot:
    """Основной класс бота с модульной архитектурой"""
    
    def __init__(self):
        """Инициализация бота"""
        self.bot: Optional[telebot.TeleBot] = None
        self.config: Optional[Config] = None
        self.db_manager: Optional[DatabaseManager] = None
        
        # Менеджеры модулей ПЛАН 1 (АКТИВНЫЕ)
        self.security_manager: Optional[SecurityManager] = None
        self.menu_handler: Optional[MenuHandler] = None
        self.command_handler: Optional[CommandHandler] = None
        self.callback_handler: Optional[CallbackHandler] = None
        self.message_handler: Optional[MessageHandler] = None
        self.link_handler: Optional[LinkHandler] = None
        
        # HTTP сервер и keep-alive
        self.webhook_server: Optional[WebhookServer] = None
        self.keepalive_manager: Optional[KeepAliveManager] = None
        
        # ПЛАН 2: Система кармы (ЗАГЛУШКИ)
        # self.karma_manager: Optional[KarmaManager] = None
        # self.analytics_manager: Optional[AnalyticsManager] = None
        
        # ПЛАН 3: ИИ и формы (ЗАГЛУШКИ)
        # self.ai_manager: Optional[AIManager] = None
        # self.gratitude_detector: Optional[GratitudeDetector] = None
        # self.form_manager: Optional[FormManager] = None
        # self.ai_handler: Optional[AIHandler] = None
        # self.form_handler: Optional[FormHandler] = None
        
        # ПЛАН 4: Backup система (ЗАГЛУШКИ)
        # self.backup_manager: Optional[BackupRestoreManager] = None
        # self.backup_scheduler: Optional[BackupScheduler] = None
        # self.backup_handler: Optional[BackupCommandHandler] = None
        
        self.is_running = False
        
    def initialize(self):
        """Инициализация всех компонентов бота"""
        logger.info("🚀 Начинаем инициализацию Do Presave Reminder Bot v25+...")
        
        try:
            # 1. Загрузка и валидация конфигурации
            self._init_config()
            
            # 2. Инициализация бота
            self._init_bot()
            
            # 3. Инициализация базы данных
            self._init_database()
            
            # 4. Инициализация менеджеров безопасности
            self._init_security()
            
            # 5. Инициализация обработчиков ПЛАН 1
            self._init_plan1_handlers()
            
            # 6. ПЛАН 2: Инициализация системы кармы (ЗАГЛУШКИ)
            # self._init_plan2_karma()
            
            # 7. ПЛАН 3: Инициализация ИИ и форм (ЗАГЛУШКИ)
            # self._init_plan3_ai_forms()
            
            # 8. ПЛАН 4: Инициализация backup системы (ЗАГЛУШКИ)
            # self._init_plan4_backup()
            
            # 9. Регистрация обработчиков
            self._register_handlers()
            
            # 10. Инициализация HTTP сервера и keep-alive
            self._init_webhook_keepalive()
            
            logger.info("✅ Инициализация завершена успешно!")
            self.is_running = True
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            sys.exit(1)
    
    def _init_config(self):
        """Инициализация конфигурации"""
        logger.info("🔧 Загрузка конфигурации...")
        
        self.config = Config()
        
        # Валидация обязательных переменных
        if not validate_config():
            logger.error("❌ Конфигурация не прошла валидацию!")
            sys.exit(1)
            
        logger.info("✅ Конфигурация загружена и валидирована")
    
    def _init_bot(self):
            """Инициализация Telegram бота"""
            logger.info("🤖 Инициализация Telegram бота...")
            
            self.bot = telebot.TeleBot(
                self.config.BOT_TOKEN,
                parse_mode='HTML',
                threaded=True
            )
            
            logger.info("✅ Telegram бот инициализирован")
    
    def _init_database(self):
        """Инициализация базы данных"""
        logger.info("🗃️ Инициализация базы данных...")
        
        self.db_manager = DatabaseManager(self.config.DATABASE_URL)
        
        # Инициализация моделей БД
        init_database_models(self.db_manager.engine)
        
        # Создание таблиц если не существуют
        self.db_manager.create_tables()
        
        logger.info("✅ База данных инициализирована")
    
    def _init_security(self):
        """Инициализация менеджера безопасности"""
        logger.info("🛡️ Инициализация системы безопасности...")
        
        self.security_manager = SecurityManager(
            admin_ids=self.config.ADMIN_IDS,
            whitelist_threads=self.config.WHITELIST
        )
        
        logger.info("✅ Система безопасности инициализирована")
    
    def _init_plan1_handlers(self):
        """Инициализация обработчиков ПЛАН 1 (АКТИВНЫЕ)"""
        logger.info("📱 Инициализация обработчиков ПЛАН 1...")
        
        # Обработчик меню
        self.menu_handler = MenuHandler(self.bot, self.db_manager, self.security_manager)
        
        # Обработчик команд
        self.command_handler = CommandHandler(self.bot, self.db_manager, self.security_manager)
        
        # Обработчик callback'ов (кнопки)
        self.callback_handler = CallbackHandler(self.bot, self.db_manager, self.security_manager)
        
        # Обработчик сообщений
        self.message_handler = MessageHandler(self.bot, self.db_manager, self.security_manager)
        
        # Обработчик ссылок
        self.link_handler = LinkHandler(self.bot, self.db_manager, self.security_manager, self.config)
        
        logger.info("✅ Обработчики ПЛАН 1 инициализированы")
    
    # def _init_plan2_karma(self):
    #     """Инициализация системы кармы ПЛАН 2 (ЗАГЛУШКА)"""
    #     if not self.config.ENABLE_PLAN_2_FEATURES:
    #         logger.info("⏸️ ПЛАН 2 (карма) отключен через feature flag")
    #         return
    #         
    #     logger.info("🏆 Инициализация системы кармы ПЛАН 2...")
    #     
    #     # Инициализация менеджера кармы
    #     self.karma_manager = KarmaManager(self.db_manager, self.config)
    #     init_karma_system(self.karma_manager)
    #     
    #     # Инициализация аналитики
    #     self.analytics_manager = AnalyticsManager(self.db_manager)
    #     
    #     logger.info("✅ Система кармы ПЛАН 2 инициализирована")
    
    # def _init_plan3_ai_forms(self):
    #     """Инициализация ИИ и форм ПЛАН 3 (ЗАГЛУШКА)"""
    #     if not self.config.ENABLE_PLAN_3_FEATURES:
    #         logger.info("⏸️ ПЛАН 3 (ИИ + формы) отключен через feature flag")
    #         return
    #         
    #     logger.info("🤖 Инициализация ИИ и форм ПЛАН 3...")
    #     
    #     # Инициализация ИИ
    #     if self.config.AI_ENABLED:
    #         self.ai_manager = AIManager(self.config)
    #         init_ai_system(self.ai_manager)
    #         
    #         # Обработчики ИИ
    #         self.ai_handler = AIHandler(self.bot, self.ai_manager, self.security_manager)
    #     
    #     # Инициализация детектора благодарностей
    #     if self.config.AUTO_KARMA_ENABLED:
    #         self.gratitude_detector = GratitudeDetector(self.db_manager, self.karma_manager)
    #         init_gratitude_system(self.gratitude_detector)
    #     
    #     # Инициализация системы форм
    #     if self.config.FORMS_ENABLED:
    #         self.form_manager = FormManager(self.db_manager, self.config)
    #         init_forms_system(self.form_manager)
    #         
    #         # Обработчики форм
    #         self.form_handler = FormHandler(self.bot, self.form_manager, self.security_manager)
    #     
    #     logger.info("✅ ИИ и формы ПЛАН 3 инициализированы")
    
    # def _init_plan4_backup(self):
    #     """Инициализация backup системы ПЛАН 4 (ЗАГЛУШКА)"""
    #     if not self.config.ENABLE_PLAN_4_FEATURES:
    #         logger.info("⏸️ ПЛАН 4 (backup) отключен через feature flag")
    #         return
    #         
    #     logger.info("💾 Инициализация backup системы ПЛАН 4...")
    #     
    #     # Инициализация менеджера backup
    #     self.backup_manager = BackupRestoreManager(self.db_manager, self.config)
    #     init_backup_manager(self.backup_manager)
    #     
    #     # Инициализация планировщика
    #     if self.config.AUTO_BACKUP_ENABLED:
    #         self.backup_scheduler = BackupScheduler(self.bot, self.backup_manager, self.config)
    #         init_backup_scheduler(self.backup_scheduler)
    #     
    #     # Обработчики backup команд
    #     self.backup_handler = BackupCommandHandler(self.bot, self.backup_manager, self.security_manager)
    #     
    #     logger.info("✅ Backup система ПЛАН 4 инициализирована")
    
    def _register_handlers(self):
        """Регистрация всех обработчиков"""
        logger.info("📝 Регистрация обработчиков сообщений...")
        
        # ПЛАН 1: Регистрация основных обработчиков (АКТИВНЫЕ)
        self.command_handler.register_handlers()
        self.callback_handler.register_handlers()
        self.message_handler.register_handlers()
        
        # ПЛАН 2: Регистрация обработчиков кармы (ЗАГЛУШКИ)
        # if self.karma_manager:
        #     self.karma_manager.register_handlers()
        
        # ПЛАН 3: Регистрация ИИ и форм (ЗАГЛУШКИ)  
        # if self.ai_handler:
        #     self.ai_handler.register_handlers()
        # if self.form_handler:
        #     self.form_handler.register_handlers()
        
        # ПЛАН 4: Регистрация backup обработчиков (ЗАГЛУШКИ)
        # if self.backup_handler:
        #     self.backup_handler.register_handlers()
        
        logger.info("✅ Все обработчики зарегистрированы")
    
    def _init_webhook_keepalive(self):
            """Инициализация HTTP сервера и keep-alive"""
            logger.info("🌐 Инициализация webhook сервера и keep-alive...")
            
            # Инициализация keep-alive менеджера
            self.keepalive_manager = KeepAliveManager(
                external_url=self.config.RENDER_EXTERNAL_URL,
                interval=self.config.KEEPALIVE_INTERVAL
            )
            
            # Инициализация webhook сервера
            if self.config.RENDER_EXTERNAL_URL:
                self.webhook_server = WebhookServer(
                    bot=self.bot,
                    webhook_secret=self.config.WEBHOOK_SECRET,
                    host=self.config.HOST,
                    port=int(os.getenv('PORT', 8080))
                )
                
                # Запуск сервера в отдельном потоке
                server_thread = threading.Thread(
                    target=self.webhook_server.start_server,
                    daemon=True
                )
                server_thread.start()
                
                # Ждем запуска сервера
                logger.info("⏳ Ожидание запуска HTTP сервера...")
                time.sleep(5)
                
                # Теперь устанавливаем webhook
                try:
                    webhook_url = f"https://{self.config.RENDER_EXTERNAL_URL}/webhook"
                    logger.info(f"🔗 Установка webhook: {webhook_url}")
                    
                    self.bot.remove_webhook()
                    time.sleep(2)
                    self.bot.set_webhook(webhook_url)
                    logger.info(f"✅ Webhook установлен успешно: {webhook_url}")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка установки webhook: {e}")
                    logger.info("🔄 Переключаемся на polling режим...")
                    self.config.RENDER_EXTERNAL_URL = None  # Отключаем webhook
            else:
                logger.info("✅ Режим polling (без webhook)")
                
            # Запуск keep-alive в отдельном потоке
            keepalive_thread = threading.Thread(
                target=self.keepalive_manager.start_keepalive,
                daemon=True
            )
            keepalive_thread.start()
            
            logger.info("✅ Webhook сервер и keep-alive запущены")
    
    def run(self):
        """Запуск бота"""
        if not self.is_running:
            logger.error("❌ Бот не инициализирован!")
            return
            
        logger.info("🚀 Запуск Do Presave Reminder Bot v25+...")
        
        try:
            if self.config.RENDER_EXTERNAL_URL:
                # Режим webhook - бесконечный цикл
                logger.info("🌐 Режим webhook - ожидание сообщений...")
                while True:
                    time.sleep(1)
            else:
                # Режим polling
                logger.info("📡 Режим polling - запуск...")
                self.bot.infinity_polling(
                    timeout=self.config.POLLING_TIMEOUT,
                    long_polling_timeout=self.config.POLLING_INTERVAL
                )
                
        except KeyboardInterrupt:
            logger.info("⏸️ Получен сигнал остановки...")
            self.shutdown()
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            self.shutdown()
    
    def shutdown(self):
        """Корректное завершение работы бота"""
        logger.info("🛑 Завершение работы бота...")
        
        try:
            # Остановка keep-alive
            if self.keepalive_manager:
                self.keepalive_manager.stop()
            
            # Остановка webhook сервера
            if self.webhook_server:
                self.webhook_server.stop()
            
            # ПЛАН 4: Остановка backup планировщика (ЗАГЛУШКА)
            # if self.backup_scheduler:
            #     self.backup_scheduler.stop()
            
            # Закрытие соединений с БД
            if self.db_manager:
                self.db_manager.close()
            
            self.is_running = False
            logger.info("✅ Бот корректно завершил работу")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при завершении: {e}")


def main():
    """Главная функция запуска"""
    # Настройка логирования
    setup_logging()
    
    logger.info("=" * 50)
    logger.info("🎵 Do Presave Reminder Bot v25+ Starting...")
    logger.info("📋 ПЛАН 1: Базовый функционал (АКТИВЕН)")
    logger.info("🏆 ПЛАН 2: Система кармы (ЗАГЛУШКИ)")
    logger.info("🤖 ПЛАН 3: ИИ и формы (ЗАГЛУШКИ)")
    logger.info("💾 ПЛАН 4: Backup система (ЗАГЛУШКИ)")
    logger.info("=" * 50)
    
    try:
        # Создание и запуск бота
        bot = PresaveBot()
        bot.initialize()
        bot.run()
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
