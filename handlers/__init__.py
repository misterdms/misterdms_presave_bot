"""
Модуль обработчиков событий Telegram Bot - Do Presave Reminder Bot v25+
Инициализация всех обработчиков с поддержкой модульной архитектуры

ПЛАН 1: Базовые обработчики (АКТИВНЫЕ)
ПЛАН 2: Обработчики кармы (ЗАГЛУШКИ)
ПЛАН 3: Обработчики ИИ и форм (ЗАГЛУШКИ)
ПЛАН 4: Обработчики backup (ЗАГЛУШКИ)
"""

from utils.logger import get_logger

logger = get_logger(__name__)

# ============================================
# ПЛАН 1: БАЗОВЫЕ ОБРАБОТЧИКИ (АКТИВНЫЕ)
# ============================================

# Основные обработчики - всегда импортируются
from .menu import MenuHandler
from .commands import CommandHandler
from .callbacks import CallbackHandler
from .messages import MessageHandler
from .links import LinkHandler

# ============================================
# ПЛАН 2: ОБРАБОТЧИКИ КАРМЫ (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 2
# from .karma_handlers import KarmaHandler

# ============================================
# ПЛАН 3: ОБРАБОТЧИКИ ИИ И ФОРМ (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 3
# from .ai_handlers import AIHandler
# from .form_handlers import FormHandler

# ============================================
# ПЛАН 4: ОБРАБОТЧИКИ BACKUP (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 4
# from .backup_commands import BackupCommandHandler

# ============================================
# ЭКСПОРТ АКТИВНЫХ ОБРАБОТЧИКОВ
# ============================================

__all__ = [
    # ПЛАН 1 (АКТИВНЫЕ)
    'MenuHandler',
    'CommandHandler', 
    'CallbackHandler',
    'MessageHandler',
    'LinkHandler',
    
    # ПЛАН 2 (ЗАГЛУШКИ)
    # 'KarmaHandler',
    
    # ПЛАН 3 (ЗАГЛУШКИ)
    # 'AIHandler',
    # 'FormHandler',
    
    # ПЛАН 4 (ЗАГЛУШКИ)
    # 'BackupCommandHandler',
]

# ============================================
# ФУНКЦИИ ИНИЦИАЛИЗАЦИИ
# ============================================

def get_available_handlers():
    """Получение списка доступных обработчиков"""
    return {
        'plan_1': [
            'MenuHandler',
            'CommandHandler', 
            'CallbackHandler',
            'MessageHandler',
            'LinkHandler'
        ],
        'plan_2': [
            # 'KarmaHandler'  # В разработке
        ],
        'plan_3': [
            # 'AIHandler',     # В разработке
            # 'FormHandler'    # В разработке
        ],
        'plan_4': [
            # 'BackupCommandHandler'  # В разработке
        ]
    }

def init_handlers(bot, db_manager, security_manager, config):
    """
    Инициализация всех активных обработчиков
    
    Args:
        bot: Экземпляр телеграм бота
        db_manager: Менеджер базы данных
        security_manager: Менеджер безопасности
        config: Конфигурация бота
        
    Returns:
        Dict с инициализированными обработчиками
    """
    handlers = {}
    
    try:
        # ПЛАН 1: Инициализация базовых обработчиков
        logger.info("🔄 Инициализация обработчиков ПЛАН 1...")
        
        handlers['menu'] = MenuHandler(bot, db_manager, security_manager)
        handlers['commands'] = CommandHandler(bot, db_manager, security_manager)
        handlers['callbacks'] = CallbackHandler(bot, db_manager, security_manager)
        handlers['messages'] = MessageHandler(bot, db_manager, security_manager)
        handlers['links'] = LinkHandler(bot, db_manager, security_manager)
        
        logger.info("✅ Обработчики ПЛАН 1 инициализированы")
        
        # ПЛАН 2: Инициализация обработчиков кармы (ЗАГЛУШКИ)
        if getattr(config, 'ENABLE_PLAN_2_FEATURES', False):
            logger.info("🔄 Инициализация обработчиков ПЛАН 2...")
            # TODO: Добавить инициализацию KarmaHandler
            logger.info("⏸️ ПЛАН 2 - в разработке")
        
        # ПЛАН 3: Инициализация обработчиков ИИ и форм (ЗАГЛУШКИ)
        if getattr(config, 'ENABLE_PLAN_3_FEATURES', False):
            logger.info("🔄 Инициализация обработчиков ПЛАН 3...")
            # TODO: Добавить инициализацию AIHandler, FormHandler
            logger.info("⏸️ ПЛАН 3 - в разработке")
        
        # ПЛАН 4: Инициализация обработчиков backup (ЗАГЛУШКИ)
        if getattr(config, 'ENABLE_PLAN_4_FEATURES', False):
            logger.info("🔄 Инициализация обработчиков ПЛАН 4...")
            # TODO: Добавить инициализацию BackupCommandHandler
            logger.info("⏸️ ПЛАН 4 - в разработке")
        
        logger.info(f"✅ Всего инициализировано обработчиков: {len(handlers)}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации обработчиков: {e}")
        raise
    
    return handlers

def register_handlers(bot, handlers):
    """
    Регистрация всех обработчиков в боте
    
    Args:
        bot: Экземпляр телеграм бота
        handlers: Словарь с инициализированными обработчиками
    """
    try:
        logger.info("🔄 Регистрация обработчиков в боте...")
        
        # Регистрация команд
        if 'commands' in handlers:
            handlers['commands'].register_commands()
        
        # Регистрация callback'ов
        if 'callbacks' in handlers:
            bot.callback_query_handler(func=lambda call: True)(
                handlers['callbacks'].handle_callback
            )
        
        # Регистрация обработчиков сообщений
        if 'messages' in handlers:
            bot.message_handler(func=lambda message: True)(
                handlers['messages'].handle_message
            )
        
        logger.info("✅ Все обработчики зарегистрированы в боте")
        
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации обработчиков: {e}")
        raise

# ============================================
# ИНФОРМАЦИЯ О МОДУЛЕ
# ============================================

def get_module_info():
    """Получение информации о модуле handlers"""
    return {
        'name': 'handlers',
        'version': 'v25+',
        'description': 'Обработчики событий Telegram Bot',
        'plans': {
            'plan_1': 'Базовые обработчики - АКТИВНЫ',
            'plan_2': 'Обработчики кармы - В РАЗРАБОТКЕ',
            'plan_3': 'Обработчики ИИ и форм - В РАЗРАБОТКЕ',
            'plan_4': 'Обработчики backup - В РАЗРАБОТКЕ'
        }
    }

logger.info("📦 Модуль handlers/__init__.py загружен")