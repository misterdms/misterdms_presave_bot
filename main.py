#!/usr/bin/env python3
"""
Do Presave Reminder Bot v29.07 - Main Entry Point
by Mister DMS

Модульная архитектура для музыкальных сообществ
"""

import asyncio
import logging
import signal
import sys
from typing import Optional

from config.settings import Settings
from core.bot_instance import BotManager
from core.module_registry import ModuleRegistry
from utils.logger import setup_logger

# Глобальные объекты
bot_manager: Optional[BotManager] = None
module_registry: Optional[ModuleRegistry] = None

async def setup_application() -> bool:
    """Инициализация приложения"""
    global bot_manager, module_registry
    
    try:
        logger = logging.getLogger(__name__)
        logger.info("🎵 Инициализация Do Presave Reminder Bot v29.07...")
        
        # Проверяем конфигурацию
        settings = Settings()
        if not settings.validate():
            logger.error("❌ Некорректная конфигурация")
            return False
        
        logger.info(f"🚀 Режим: {'DEVELOPMENT' if settings.DEVELOPMENT_MODE else 'PRODUCTION'}")
        logger.info(f"📊 WebApp URL: {settings.WEBAPP_URL}")
        
        # Создаем менеджер бота
        bot_manager = BotManager(settings)
        
        # Создаем реестр модулей
        module_registry = ModuleRegistry(bot_manager)
        
        # Инициализируем базу данных
        if not await bot_manager.initialize_database():
            logger.error("❌ Ошибка инициализации базы данных")
            return False
        
        # Загружаем модули ПЛАНА 1
        plan1_modules = [
            'user_management',      # МОДУЛЬ 1: Пользователи и карма
            'track_support_system', # МОДУЛЬ 2: Система поддержки треков  
            'karma_system',         # МОДУЛЬ 3: Автоматическая карма
            'navigation_system',    # МОДУЛЬ 10: Навигация
            'module_settings'       # МОДУЛЬ 12: Настройки модулей
        ]
        
        # Загружаем модули
        for module_name in plan1_modules:
            if not await module_registry.load_module(module_name):
                logger.error(f"❌ Ошибка загрузки модуля: {module_name}")
                return False
        
        # Инициализируем WebApp интеграцию
        await bot_manager.setup_webapp_integration()
        
        logger.info("✅ Приложение инициализировано успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        return False

async def start_bot():
    """Запуск бота"""
    global bot_manager
    
    logger = logging.getLogger(__name__)
    
    try:
        if not bot_manager:
            logger.error("❌ BotManager не инициализирован")
            return
        
        # Стартуем все модули
        await module_registry.start_all_modules()
        
        # Запускаем Keep-Alive если включен
        if bot_manager.settings.KEEPALIVE_ENABLED:
            await bot_manager.start_keepalive()
        
        # Запускаем бота
        logger.info("🚀 Запуск Telegram бота...")
        await bot_manager.start_polling()
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        raise

async def shutdown_application():
    """Корректное завершение работы"""
    global bot_manager, module_registry
    
    logger = logging.getLogger(__name__)
    logger.info("🛑 Завершение работы...")
    
    try:
        if module_registry:
            await module_registry.stop_all_modules()
        
        if bot_manager:
            await bot_manager.stop()
        
        logger.info("✅ Завершение работы выполнено")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при завершении: {e}")

def signal_handler(signum, frame):
    """Обработчик сигналов завершения"""
    logger = logging.getLogger(__name__)
    logger.info(f"📡 Получен сигнал {signum}")
    
    # Создаем новый event loop для shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(shutdown_application())
    finally:
        loop.close()
    
    sys.exit(0)

async def main():
    """Главная функция"""
    # Настраиваем логирование
    setup_logger()
    logger = logging.getLogger(__name__)
    
    logger.info("🎵 Do Presave Reminder Bot v29.07 by Mister DMS")
    logger.info("📋 ПЛАН 1: Базовый функционал + WebApp интеграция")
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Инициализация
        if not await setup_application():
            logger.error("❌ Не удалось инициализировать приложение")
            sys.exit(1)
        
        # Запуск
        await start_bot()
        
    except KeyboardInterrupt:
        logger.info("⌨️ Получен Ctrl+C")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        await shutdown_application()

if __name__ == "__main__":
    # Проверяем версию Python
    if sys.version_info < (3, 11):
        print("❌ Требуется Python 3.11 или выше")
        sys.exit(1)
    
    # Запускаем приложение
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)