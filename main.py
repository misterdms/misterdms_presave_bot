#!/usr/bin/env python3
"""
Do Presave Reminder Bot v25+ - Главный файл запуска
Модульная архитектура с поэтапным развитием функционала

ПЛАН 1: Базовый функционал (АКТИВЕН) ✅
ПЛАН 2: Система кармы (ЗАГЛУШКИ + КОММЕНТАРИИ) 🚧
ПЛАН 3: ИИ и формы (ЗАГЛУШКИ + КОММЕНТАРИИ) 🚧
ПЛАН 4: Backup система (ЗАГЛУШКИ + КОММЕНТАРИИ) 🚧
"""

import os
import sys
import time
import threading
from typing import Optional

# ============================================
# ИМПОРТЫ ПЛАН 1 (АКТИВНЫЕ) ✅
# ============================================
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

# HTTP сервер и keep-alive
from webhooks.server import WebhookServer
from webhooks.keepalive import KeepAliveManager

# ============================================
# ИМПОРТЫ ПЛАН 2: Система кармы (ЗАГЛУШКИ)
# ============================================
# TODO ПЛАН 2: Раскомментировать когда будем реализовывать карму
# from services.karma_manager import KarmaManager, init_karma_system
# from database.analytics import AnalyticsManager
# from handlers.karma_handlers import KarmaHandler
# from services.karma_calculator import KarmaCalculator
# from services.ranking_system import RankingSystem

# ============================================
# ИМПОРТЫ ПЛАН 3: ИИ и формы (ЗАГЛУШКИ)
# ============================================
# TODO ПЛАН 3: Раскомментировать когда будем реализовывать ИИ
# from services.ai_manager import AIManager, init_ai_system
# from services.gratitude_detector import GratitudeDetector, init_gratitude_system
# from services.forms_manager import FormManager, init_forms_system
# from handlers.ai_handlers import AIHandler
# from handlers.form_handlers import FormHandler
# from services.openai_integration import OpenAIConnector
# from services.anthropic_integration import AnthropicConnector

# ============================================
# ИМПОРТЫ ПЛАН 4: Backup система (ЗАГЛУШКИ)
# ============================================
# TODO ПЛАН 4: Раскомментировать когда будем реализовывать backup
# from services.backup_restore import BackupRestoreManager, init_backup_manager
# from services.backup_scheduler import BackupScheduler, init_backup_scheduler
# from handlers.backup_commands import BackupCommandHandler
# from services.database_migration import DatabaseMigrator
# from services.backup_compression import BackupCompressor

# Инициализация логирования
logger = get_logger(__name__)

class PresaveBot:
    """Основной класс бота с модульной архитектурой"""
    
    def __init__(self):
        """Инициализация бота"""
        self.bot: Optional[telebot.TeleBot] = None
        self.config: Optional[Config] = None
        self.db_manager: Optional[DatabaseManager] = None
        
        # ============================================
        # ПЛАН 1: Менеджеры модулей (АКТИВНЫЕ) ✅
        # ============================================
        self.security_manager: Optional[SecurityManager] = None
        self.menu_handler: Optional[MenuHandler] = None
        self.command_handler: Optional[CommandHandler] = None
        self.callback_handler: Optional[CallbackHandler] = None
        self.message_handler: Optional[MessageHandler] = None
        self.link_handler: Optional[LinkHandler] = None
        
        # HTTP сервер и keep-alive
        self.webhook_server: Optional[WebhookServer] = None
        self.keepalive_manager: Optional[KeepAliveManager] = None
        
        # ============================================
        # ПЛАН 2: Система кармы (ЗАГЛУШКИ) 🚧
        # ============================================
        # TODO ПЛАН 2: Раскомментировать и инициализировать
        # self.karma_manager: Optional[KarmaManager] = None
        # self.analytics_manager: Optional[AnalyticsManager] = None
        # self.karma_handler: Optional[KarmaHandler] = None
        # self.karma_calculator: Optional[KarmaCalculator] = None
        # self.ranking_system: Optional[RankingSystem] = None
        
        # ============================================
        # ПЛАН 3: ИИ и формы (ЗАГЛУШКИ) 🚧
        # ============================================
        # TODO ПЛАН 3: Раскомментировать и инициализировать
        # self.ai_manager: Optional[AIManager] = None
        # self.gratitude_detector: Optional[GratitudeDetector] = None
        # self.form_manager: Optional[FormManager] = None
        # self.ai_handler: Optional[AIHandler] = None
        # self.form_handler: Optional[FormHandler] = None
        # self.openai_connector: Optional[OpenAIConnector] = None
        # self.anthropic_connector: Optional[AnthropicConnector] = None
        
        # ============================================
        # ПЛАН 4: Backup система (ЗАГЛУШКИ) 🚧
        # ============================================
        # TODO ПЛАН 4: Раскомментировать и инициализировать
        # self.backup_manager: Optional[BackupRestoreManager] = None
        # self.backup_scheduler: Optional[BackupScheduler] = None
        # self.backup_handler: Optional[BackupCommandHandler] = None
        # self.database_migrator: Optional[DatabaseMigrator] = None
        # self.backup_compressor: Optional[BackupCompressor] = None
        
        self.is_running = False
        
        logger.info("🤖 PresaveBot инициализирован")
        
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
            
            # 5. ✅ ПЛАН 1: Инициализация основных обработчиков (АКТИВНО)
            self._init_plan1_handlers()
            
            # 6. 🚧 ПЛАН 2: Инициализация системы кармы (ЗАГЛУШКИ)
            self._init_plan2_karma_stub()
            
            # 7. 🚧 ПЛАН 3: Инициализация ИИ и форм (ЗАГЛУШКИ)
            self._init_plan3_ai_forms_stub()
            
            # 8. 🚧 ПЛАН 4: Инициализация backup системы (ЗАГЛУШКИ)
            self._init_plan4_backup_stub()
            
            # 9. 🔗 КРИТИЧЕСКАЯ ИНТЕГРАЦИЯ: LinkHandler с MessageHandler
            self._integrate_link_handler()
            
            # 10. Регистрация обработчиков
            self._register_handlers()
            
            # 11. Инициализация HTTP сервера и keep-alive
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
        
        # Проверяем флаг принудительного пересоздания
        force_recreate = getattr(self.config, 'FORCE_RECREATE_TABLES', False)
        if force_recreate:
            logger.warning("🚨 ОБНАРУЖЕН ФЛАГ FORCE_RECREATE_TABLES=true")
            logger.warning("🚨 ВСЕ ДАННЫЕ В БД БУДУТ УДАЛЕНЫ!")
        
        # Создание таблиц с учетом флага
        self.db_manager.create_tables(force_recreate=force_recreate)
        
        logger.info("✅ База данных инициализирована")

    def _init_security(self):
        """Инициализация менеджера безопасности"""
        logger.info("🛡️ Инициализация системы безопасности...")
        
        self.security_manager = SecurityManager(
            admin_ids=self.config.ADMIN_IDS,
            whitelist_threads=self.config.WHITELIST
        )
        
        logger.info("✅ Система безопасности инициализирована")
    
    # ============================================
    # ✅ ПЛАН 1: АКТИВНЫЕ ОБРАБОТЧИКИ
    # ============================================
    
    def _init_plan1_handlers(self):
        """✅ ПЛАН 1: Инициализация основных обработчиков (АКТИВНО)"""
        logger.info("📱 ✅ ПЛАН 1: Инициализация основных обработчиков...")
        
        # Обработчик меню
        self.menu_handler = MenuHandler(self.bot, self.db_manager, self.security_manager)
        
        # Обработчик команд
        self.command_handler = CommandHandler(self.bot, self.db_manager, self.security_manager)
        
        # Создаем ссылку на menu_handler в боте для доступа из CommandHandler
        self.bot._menu_handler = self.menu_handler
        
        # Обработчик callback'ов (кнопки)
        self.callback_handler = CallbackHandler(self.bot, self.db_manager, self.security_manager)
        
        # Обработчик сообщений
        self.message_handler = MessageHandler(self.bot, self.db_manager, self.security_manager)
        
        # Обработчик ссылок
        self.link_handler = LinkHandler(self.bot, self.db_manager, self.security_manager, self.config)
        
        logger.info("✅ ПЛАН 1: Основные обработчики инициализированы")
    
    def _integrate_link_handler(self):
        """🔗 КРИТИЧЕСКАЯ ИНТЕГРАЦИЯ: LinkHandler с MessageHandler"""
        logger.info("🔗 КРИТИЧЕСКАЯ ИНТЕГРАЦИЯ: LinkHandler с MessageHandler...")
        
        try:
            # Устанавливаем LinkHandler в MessageHandler
            self.message_handler.set_link_handler(self.link_handler)
            
            # Проверяем интеграцию
            integration_status = self.message_handler.get_integration_status()
            logger.info(f"🔗 Статус интеграции LinkHandler: {integration_status}")
            
            if not integration_status['status'] == 'ready':
                raise Exception("LinkHandler не готов к работе!")
            
            logger.info("✅ КРИТИЧЕСКАЯ ИНТЕГРАЦИЯ: LinkHandler успешно интегрирован!")
            
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА интеграции LinkHandler: {e}")
            raise
    
    # ============================================
    # 🚧 ПЛАН 2: ЗАГЛУШКИ СИСТЕМЫ КАРМЫ
    # ============================================
    
    def _init_plan2_karma_stub(self):
        """🚧 ПЛАН 2: Инициализация системы кармы (ЗАГЛУШКА)"""
        logger.info("🚧 ПЛАН 2: Заглушка системы кармы...")
        
        # TODO ПЛАН 2: Раскомментировать когда будем реализовывать
        # if not getattr(self.config, 'ENABLE_PLAN_2_FEATURES', False):
        #     logger.info("⏸️ ПЛАН 2 (карма) отключен через feature flag")
        #     return
        #     
        # logger.info("🏆 Инициализация системы кармы ПЛАН 2...")
        # 
        # # Инициализация менеджера кармы
        # self.karma_manager = KarmaManager(self.db_manager, self.config)
        # init_karma_system(self.karma_manager)
        # 
        # # Инициализация аналитики
        # self.analytics_manager = AnalyticsManager(self.db_manager)
        # 
        # # Инициализация обработчика кармы
        # self.karma_handler = KarmaHandler(self.bot, self.karma_manager, self.security_manager)
        # 
        # # Инициализация калькулятора кармы
        # self.karma_calculator = KarmaCalculator(self.db_manager)
        # 
        # # Инициализация системы рангов
        # self.ranking_system = RankingSystem(self.db_manager, self.karma_calculator)
        # 
        # logger.info("✅ Система кармы ПЛАН 2 инициализирована")
        
        logger.info("⏸️ ПЛАН 2: Заглушка - карма будет реализована позже")
    
    # ============================================
    # 🚧 ПЛАН 3: ЗАГЛУШКИ ИИ И ФОРМ
    # ============================================
    
    def _init_plan3_ai_forms_stub(self):
        """🚧 ПЛАН 3: Инициализация ИИ и форм (ЗАГЛУШКА)"""
        logger.info("🚧 ПЛАН 3: Заглушка ИИ и форм...")
        
        # TODO ПЛАН 3: Раскомментировать когда будем реализовывать
        # if not getattr(self.config, 'ENABLE_PLAN_3_FEATURES', False):
        #     logger.info("⏸️ ПЛАН 3 (ИИ + формы) отключен через feature flag")
        #     return
        #     
        # logger.info("🤖 Инициализация ИИ и форм ПЛАН 3...")
        # 
        # # Инициализация ИИ
        # if getattr(self.config, 'AI_ENABLED', False):
        #     self.ai_manager = AIManager(self.config)
        #     init_ai_system(self.ai_manager)
        #     
        #     # Обработчики ИИ
        #     self.ai_handler = AIHandler(self.bot, self.ai_manager, self.security_manager)
        #     
        #     # Коннекторы к ИИ сервисам
        #     if self.config.OPENAI_API_KEY and self.config.OPENAI_API_KEY != 'not_specified_yet':
        #         self.openai_connector = OpenAIConnector(self.config.OPENAI_API_KEY)
        #     
        #     if self.config.ANTHROPIC_API_KEY and self.config.ANTHROPIC_API_KEY != 'not_specified_yet':
        #         self.anthropic_connector = AnthropicConnector(self.config.ANTHROPIC_API_KEY)
        # 
        # # Инициализация детектора благодарностей
        # if getattr(self.config, 'AUTO_KARMA_ENABLED', False):
        #     self.gratitude_detector = GratitudeDetector(self.db_manager, self.karma_manager)
        #     init_gratitude_system(self.gratitude_detector)
        # 
        # # Инициализация системы форм
        # if getattr(self.config, 'FORMS_ENABLED', False):
        #     self.form_manager = FormManager(self.db_manager, self.config)
        #     init_forms_system(self.form_manager)
        #     
        #     # Обработчики форм
        #     self.form_handler = FormHandler(self.bot, self.form_manager, self.security_manager)
        # 
        # logger.info("✅ ИИ и формы ПЛАН 3 инициализированы")
        
        logger.info("⏸️ ПЛАН 3: Заглушка - ИИ и формы будут реализованы позже")
    
    # ============================================
    # 🚧 ПЛАН 4: ЗАГЛУШКИ BACKUP СИСТЕМЫ
    # ============================================
    
    def _init_plan4_backup_stub(self):
        """🚧 ПЛАН 4: Инициализация backup системы (ЗАГЛУШКА)"""
        logger.info("🚧 ПЛАН 4: Заглушка backup системы...")
        
        # TODO ПЛАН 4: Раскомментировать когда будем реализовывать
        # if not getattr(self.config, 'ENABLE_PLAN_4_FEATURES', False):
        #     logger.info("⏸️ ПЛАН 4 (backup) отключен через feature flag")
        #     return
        #     
        # logger.info("💾 Инициализация backup системы ПЛАН 4...")
        # 
        # # Инициализация менеджера backup
        # self.backup_manager = BackupRestoreManager(self.db_manager, self.config)
        # init_backup_manager(self.backup_manager)
        # 
        # # Инициализация планировщика
        # if getattr(self.config, 'AUTO_BACKUP_ENABLED', False):
        #     self.backup_scheduler = BackupScheduler(self.bot, self.backup_manager, self.config)
        #     init_backup_scheduler(self.backup_scheduler)
        # 
        # # Обработчики backup команд
        # self.backup_handler = BackupCommandHandler(self.bot, self.backup_manager, self.security_manager)
        # 
        # # Инициализация компрессора backup
        # self.backup_compressor = BackupCompressor(self.config)
        # 
        # # Инициализация мигратора БД
        # self.database_migrator = DatabaseMigrator(self.db_manager, self.backup_manager)
        # 
        # logger.info("✅ Backup система ПЛАН 4 инициализирована")
        
        logger.info("⏸️ ПЛАН 4: Заглушка - backup система будет реализована позже")
    
    # ============================================
    # РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ
    # ============================================
    
    def _register_handlers(self):
        """Регистрация всех обработчиков"""
        logger.info("📝 Регистрация обработчиков сообщений...")
        
        # ✅ ПЛАН 1: Регистрация основных обработчиков (АКТИВНЫЕ)
        self.command_handler.register_handlers()
        self.callback_handler.register_handlers()
        self.message_handler.register_handlers()
        
        # 🚧 ПЛАН 2: Регистрация обработчиков кармы (ЗАГЛУШКИ)
        # TODO ПЛАН 2: Раскомментировать
        # if hasattr(self, 'karma_handler') and self.karma_handler:
        #     self.karma_handler.register_handlers()
        #     logger.info("✅ ПЛАН 2: Обработчики кармы зарегистрированы")
        
        # 🚧 ПЛАН 3: Регистрация ИИ и форм (ЗАГЛУШКИ)  
        # TODO ПЛАН 3: Раскомментировать
        # if hasattr(self, 'ai_handler') and self.ai_handler:
        #     self.ai_handler.register_handlers()
        #     logger.info("✅ ПЛАН 3: ИИ обработчики зарегистрированы")
        # 
        # if hasattr(self, 'form_handler') and self.form_handler:
        #     self.form_handler.register_handlers()
        #     logger.info("✅ ПЛАН 3: Обработчики форм зарегистрированы")
        
        # 🚧 ПЛАН 4: Регистрация backup обработчиков (ЗАГЛУШКИ)
        # TODO ПЛАН 4: Раскомментировать
        # if hasattr(self, 'backup_handler') and self.backup_handler:
        #     self.backup_handler.register_handlers()
        #     logger.info("✅ ПЛАН 4: Backup обработчики зарегистрированы")
        
        logger.info("✅ Все доступные обработчики зарегистрированы")
    
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
                # Убираем https:// если уже есть в RENDER_EXTERNAL_URL
                external_url = self.config.RENDER_EXTERNAL_URL.replace('https://', '').replace('http://', '')
                webhook_url = f"https://{external_url}/webhook"
                logger.info(f"🔗 Установка webhook: {webhook_url}")
                
                # ВАЖНО: Сначала принудительно удаляем webhook для избежания 409 ошибки
                try:
                    self.bot.remove_webhook()
                    logger.info("✅ Старый webhook удален")
                    time.sleep(3)  # Даем Telegram время обработать
                except Exception as webhook_remove_error:
                    logger.warning(f"⚠️ Ошибка удаления webhook: {webhook_remove_error}")
                
                # Устанавливаем новый webhook
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
            
            # 🚧 ПЛАН 4: Остановка backup планировщика (ЗАГЛУШКА)
            # TODO ПЛАН 4: Раскомментировать
            # if hasattr(self, 'backup_scheduler') and self.backup_scheduler:
            #     self.backup_scheduler.stop()
            #     logger.info("✅ Backup планировщик остановлен")
            
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
    
    logger.info("=" * 60)
    logger.info("🎵 Do Presave Reminder Bot v25+ Starting...")
    logger.info("=" * 60)
    logger.info("✅ ПЛАН 1: Базовый функционал (АКТИВЕН)")
    logger.info("🚧 ПЛАН 2: Система кармы (ЗАГЛУШКИ + КОММЕНТАРИИ)")
    logger.info("🚧 ПЛАН 3: ИИ и формы (ЗАГЛУШКИ + КОММЕНТАРИИ)")
    logger.info("🚧 ПЛАН 4: Backup система (ЗАГЛУШКИ + КОММЕНТАРИИ)")
    logger.info("=" * 60)
    
    try:
        # Создание и запуск бота
        bot = PresaveBot()
        bot.initialize()
        
        # Дополнительная диагностика перед запуском
        logger.info("🔍 Финальная диагностика перед запуском:")
        logger.info(f"✅ Bot: {bot.bot is not None}")
        logger.info(f"✅ Database: {bot.db_manager is not None}")
        logger.info(f"✅ Security: {bot.security_manager is not None}")
        logger.info(f"✅ Menu Handler: {bot.menu_handler is not None}")
        logger.info(f"✅ Message Handler: {bot.message_handler is not None}")
        logger.info(f"✅ Link Handler: {bot.link_handler is not None}")
        
        # Проверка интеграции LinkHandler
        if bot.message_handler and bot.link_handler:
            integration_status = bot.message_handler.get_integration_status()
            logger.info(f"🔗 LinkHandler интеграция: {integration_status['status']}")
        
        logger.info("🚀 Все системы готовы - запуск бота!")
        bot.run()
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()