"""
Модуль HTTP сервера и keep-alive - Do Presave Reminder Bot v25+
Webhook сервер для Telegram и система предотвращения засыпания на Render.com

ПЛАН 1: HTTP сервер и keep-alive (АКТИВНЫЕ)
ПЛАН 2-4: Расширения webhook функционала (ЗАГЛУШКИ)
"""

from utils.logger import get_logger

logger = get_logger(__name__)

# ============================================
# ПЛАН 1: БАЗОВЫЕ КОМПОНЕНТЫ (АКТИВНЫЕ)
# ============================================

# Основные компоненты - всегда импортируются
from .server import WebhookServer, init_webhook_server
from .keepalive import KeepAliveManager, init_keepalive

# ============================================
# ПЛАН 2-4: РАСШИРЕНИЯ (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в будущих планах
# from .monitoring import WebhookMonitoring    # ПЛАН 4
# from .health import HealthChecker           # ПЛАН 4

# ============================================
# ЭКСПОРТ АКТИВНЫХ КОМПОНЕНТОВ
# ============================================

__all__ = [
    # ПЛАН 1 (АКТИВНЫЕ)
    'WebhookServer',
    'init_webhook_server',
    'KeepAliveManager',
    'init_keepalive',
    
    # ПЛАН 4 (ЗАГЛУШКИ)
    # 'WebhookMonitoring',
    # 'HealthChecker',
]

# ============================================
# ГЛОБАЛЬНЫЕ ЭКЗЕМПЛЯРЫ
# ============================================

_webhook_server = None
_keepalive_manager = None

# ============================================
# ФУНКЦИИ ИНИЦИАЛИЗАЦИИ
# ============================================

def init_webhook_system(config, bot):
    """
    Инициализация всей webhook системы
    
    Args:
        config: Конфигурация бота
        bot: Экземпляр телеграм бота
        
    Returns:
        dict: Инициализированные компоненты webhook системы
    """
    global _webhook_server, _keepalive_manager
    
    try:
        logger.info("🔄 Инициализация webhook системы...")
        
        components = {}
        
        # ПЛАН 1: Инициализация базовых компонентов
        
        # Инициализация webhook сервера
        logger.info("🌐 Инициализация webhook сервера...")
        _webhook_server = init_webhook_server(config, bot)
        components['server'] = _webhook_server
        
        # Инициализация keep-alive менеджера
        logger.info("💓 Инициализация keep-alive...")
        _keepalive_manager = init_keepalive(config)
        components['keepalive'] = _keepalive_manager
        
        logger.info("✅ Webhook система инициализирована")
        
        # ПЛАН 4: Инициализация мониторинга (ЗАГЛУШКИ)
        if getattr(config, 'ENABLE_PLAN_4_FEATURES', False):
            logger.info("🔄 Инициализация мониторинга webhook...")
            # TODO: Активировать в ПЛАНЕ 4
            # components['monitoring'] = init_webhook_monitoring(config)
            # components['health'] = init_health_checker(config)
            logger.info("⏸️ Мониторинг webhook - в разработке (ПЛАН 4)")
        
        return components
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации webhook системы: {e}")
        raise

def start_webhook_system(components):
    """
    Запуск всех компонентов webhook системы
    
    Args:
        components: Словарь с инициализированными компонентами
    """
    try:
        logger.info("🚀 Запуск webhook системы...")
        
        # Запуск keep-alive (должен быть первым!)
        if 'keepalive' in components:
            components['keepalive'].start()
            logger.info("💓 Keep-alive запущен")
        
        # Запуск webhook сервера
        if 'server' in components:
            components['server'].start()
            logger.info("🌐 Webhook сервер запущен")
        
        # ПЛАН 4: Запуск мониторинга (ЗАГЛУШКИ)
        if 'monitoring' in components:
            # TODO: Активировать в ПЛАНЕ 4
            # components['monitoring'].start()
            logger.info("⏸️ Мониторинг - в разработке")
        
        logger.info("✅ Webhook система полностью запущена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска webhook системы: {e}")
        raise

def stop_webhook_system(components):
    """
    Остановка всех компонентов webhook системы
    
    Args:
        components: Словарь с запущенными компонентами
    """
    try:
        logger.info("🛑 Остановка webhook системы...")
        
        # Остановка в обратном порядке
        
        # ПЛАН 4: Остановка мониторинга (ЗАГЛУШКИ)
        if 'monitoring' in components:
            # TODO: Активировать в ПЛАНЕ 4
            # components['monitoring'].stop()
            logger.info("⏸️ Мониторинг остановлен")
        
        # Остановка webhook сервера
        if 'server' in components:
            components['server'].stop()
            logger.info("🌐 Webhook сервер остановлен")
        
        # Остановка keep-alive (должен быть последним!)
        if 'keepalive' in components:
            components['keepalive'].stop()
            logger.info("💓 Keep-alive остановлен")
        
        logger.info("✅ Webhook система остановлена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка остановки webhook системы: {e}")

# ============================================
# ГЕТТЕРЫ ДЛЯ ГЛОБАЛЬНЫХ ЭКЗЕМПЛЯРОВ
# ============================================

def get_webhook_server():
    """Получение экземпляра webhook сервера"""
    global _webhook_server
    return _webhook_server

def get_keepalive_manager():
    """Получение экземпляра keep-alive менеджера"""
    global _keepalive_manager
    return _keepalive_manager

# ============================================
# УТИЛИТЫ ДЛЯ ДИАГНОСТИКИ
# ============================================

def check_webhook_health():
    """Проверка состояния webhook системы"""
    try:
        health = {
            'server': False,
            'keepalive': False,
            'overall': False
        }
        
        # Проверка webhook сервера
        if _webhook_server:
            health['server'] = _webhook_server.is_running()
        
        # Проверка keep-alive
        if _keepalive_manager:
            health['keepalive'] = _keepalive_manager.is_running()
        
        # Общее состояние
        health['overall'] = health['server'] and health['keepalive']
        
        logger.info(f"🔍 Проверка webhook: {'✅ OK' if health['overall'] else '❌ ISSUES'}")
        return health
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки webhook: {e}")
        return {'overall': False, 'error': str(e)}

def get_webhook_stats():
    """Получение статистики webhook системы"""
    try:
        stats = {
            'server': {},
            'keepalive': {},
            'uptime': None
        }
        
        # Статистика сервера
        if _webhook_server:
            stats['server'] = _webhook_server.get_stats()
        
        # Статистика keep-alive
        if _keepalive_manager:
            stats['keepalive'] = _keepalive_manager.get_stats()
        
        logger.info("📊 Статистика webhook получена")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики webhook: {e}")
        return {}

def restart_webhook_system(config, bot):
    """Перезапуск webhook системы"""
    try:
        logger.info("🔄 Перезапуск webhook системы...")
        
        # Получаем текущие компоненты
        components = {
            'server': _webhook_server,
            'keepalive': _keepalive_manager
        }
        
        # Останавливаем
        stop_webhook_system(components)
        
        # Инициализируем заново
        new_components = init_webhook_system(config, bot)
        
        # Запускаем
        start_webhook_system(new_components)
        
        logger.info("✅ Webhook система перезапущена")
        return new_components
        
    except Exception as e:
        logger.error(f"❌ Ошибка перезапуска webhook системы: {e}")
        raise

# ============================================
# ЗАГЛУШКИ ДЛЯ БУДУЩИХ ПЛАНОВ
# ============================================

def webhook_monitoring_stub():
    """ЗАГЛУШКА: Функции мониторинга webhook"""
    logger.info("📊 ПЛАН 4 - Мониторинг webhook в разработке")
    return {
        'description': 'Мониторинг производительности webhook',
        'features': [
            'Отслеживание времени ответа',
            'Счетчики запросов и ошибок',
            'Мониторинг доступности',
            'Алерты при проблемах'
        ],
        'status': 'В разработке'
    }

def health_checker_stub():
    """ЗАГЛУШКА: Функции проверки здоровья системы"""
    logger.info("🏥 ПЛАН 4 - Health checker в разработке")
    return {
        'description': 'Проверка состояния всех компонентов',
        'features': [
            'Проверка БД подключения',
            'Проверка Telegram API',
            'Проверка внешних сервисов',
            'Проверка свободного места'
        ],
        'endpoints': [
            '/health - общее состояние',
            '/health/db - состояние БД',
            '/health/telegram - состояние Telegram API'
        ],
        'status': 'В разработке'
    }

# ============================================
# ИНФОРМАЦИОННЫЕ ФУНКЦИИ
# ============================================

def get_available_components():
    """Получение списка доступных компонентов по планам"""
    return {
        'plan_1': [
            'WebhookServer - HTTP сервер для Telegram',
            'KeepAliveManager - предотвращение засыпания'
        ],
        'plan_4': [
            'WebhookMonitoring - мониторинг производительности',
            'HealthChecker - проверка состояния системы'
        ]
    }

def get_component_status():
    """Получение статуса всех компонентов"""
    return {
        'plan_1': {
            'webhook_server': 'Активен',
            'keepalive': 'Активен'
        },
        'plan_4': {
            'monitoring': 'В разработке',
            'health_checker': 'В разработке'
        }
    }

# ============================================
# ИНФОРМАЦИЯ О МОДУЛЕ
# ============================================

def get_module_info():
    """Получение информации о модуле webhooks"""
    return {
        'name': 'webhooks',
        'version': 'v25+',
        'description': 'HTTP сервер и keep-alive система',
        'components': {
            'server': 'Webhook сервер для Telegram',
            'keepalive': 'Предотвращение засыпания на Render.com'
        },
        'plans': {
            'plan_1': 'Базовый webhook и keep-alive - АКТИВНЫ',
            'plan_4': 'Мониторинг и health checks - В РАЗРАБОТКЕ'
        },
        'critical': 'Keep-alive работает ВСЕГДА!'
    }

logger.info("📦 Модуль webhooks/__init__.py загружен")