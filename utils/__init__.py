"""
Модуль вспомогательных утилит - Do Presave Reminder Bot v25+
Общие функции, валидация, безопасность, логирование, форматирование

ПЛАН 1: Базовые утилиты (АКТИВНЫЕ)
ПЛАН 2: Утилиты кармы (ЗАГЛУШКИ)
ПЛАН 3: Утилиты ИИ и форм (ЗАГЛУШКИ)
ПЛАН 4: Утилиты backup (ЗАГЛУШКИ)
"""

from utils.logger import get_logger

logger = get_logger(__name__)

# ============================================
# ПЛАН 1: БАЗОВЫЕ УТИЛИТЫ (АКТИВНЫЕ)
# ============================================

# Основные утилиты - всегда импортируются
from .logger import get_logger, setup_logging, log_user_action, log_database_operation
from .security import SecurityManager, admin_required, whitelist_required, validate_admin
from .helpers import (
    format_user_mention,
    truncate_text,
    clean_text,
    format_datetime,
    time_ago,
    create_progress_bar,
    is_valid_url,
    validate_user_input,
    format_file_size,
    extract_numbers,
    generate_unique_id
)
from .limits import LimitManager, get_current_limits
from .validators import (
    BaseValidator,
    ConfigValidator,
    validate_all_required_env_vars,
    create_validation_report
)

# ============================================
# ПЛАН 2: УТИЛИТЫ КАРМЫ (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 2
# from .formatters import (
#     format_karma_display,
#     format_leaderboard,
#     create_karma_progress_bar,
#     format_user_stats
# )

# ============================================
# ПЛАН 3: УТИЛИТЫ ИИ И ФОРМ (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 3
# from .ai_helpers import (
#     clean_ai_response,
#     format_ai_message,
#     validate_ai_content
# )
# from .form_helpers import (
#     validate_form_data,
#     format_form_message,
#     handle_file_upload
# )

# ============================================
# ПЛАН 4: УТИЛИТЫ BACKUP (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 4
# from .backup_helpers import (
#     validate_backup_file,
#     format_backup_size,
#     compress_backup_data
# )

# ============================================
# ЭКСПОРТ АКТИВНЫХ УТИЛИТ
# ============================================

__all__ = [
    # Логирование
    'get_logger',
    'setup_logging', 
    'log_user_action',
    'log_database_operation',
    
    # Безопасность
    'SecurityManager',
    'admin_required',
    'whitelist_required',
    'validate_admin',
    
    # Вспомогательные функции
    'format_user_mention',
    'truncate_text',
    'clean_text',
    'format_datetime',
    'time_ago',
    'create_progress_bar',
    'is_valid_url',
    'validate_user_input',
    'format_file_size',
    'extract_numbers',
    'generate_unique_id',
    
    # Лимиты API
    'LimitManager',
    'get_current_limits',
    
    # Валидация
    'BaseValidator',
    'ConfigValidator',
    'validate_all_required_env_vars',
    'create_validation_report',
    
    # ПЛАН 2 (ЗАГЛУШКИ)
    # 'format_karma_display',
    # 'format_leaderboard',
    # 'create_karma_progress_bar',
    # 'format_user_stats',
    
    # ПЛАН 3 (ЗАГЛУШКИ)
    # 'clean_ai_response',
    # 'format_ai_message',
    # 'validate_ai_content',
    # 'validate_form_data',
    # 'format_form_message',
    # 'handle_file_upload',
    
    # ПЛАН 4 (ЗАГЛУШКИ)
    # 'validate_backup_file',
    # 'format_backup_size',
    # 'compress_backup_data',
]

# ============================================
# ГЛОБАЛЬНЫЕ КОНСТАНТЫ
# ============================================

# Лимиты и ограничения
MAX_MESSAGE_LENGTH = 4096
MAX_CALLBACK_DATA_LENGTH = 64
MAX_USERNAME_LENGTH = 32
MAX_TEXT_INPUT_LENGTH = 1000

# Эмодзи для UI
EMOJI = {
    'success': '✅',
    'error': '❌', 
    'warning': '⚠️',
    'info': 'ℹ️',
    'loading': '🔄',
    'menu': '📋',
    'stats': '📊',
    'user': '👤',
    'admin': '👑',
    'link': '🔗',
    'karma': '🏆',
    'ai': '🤖',
    'backup': '💾',
    'settings': '⚙️'
}

# Форматы времени
TIME_FORMATS = {
    'short': '%H:%M',
    'medium': '%d.%m %H:%M',
    'long': '%d.%m.%Y %H:%M',
    'full': '%d.%m.%Y %H:%M:%S'
}

# ============================================
# ИНИЦИАЛИЗАЦИЯ УТИЛИТ
# ============================================

def init_utils(config):
    """
    Инициализация всех утилит
    
    Args:
        config: Конфигурация бота
        
    Returns:
        dict: Инициализированные утилиты
    """
    try:
        logger.info("🔄 Инициализация утилит...")
        
        utils = {}
        
        # ПЛАН 1: Инициализация базовых утилит
        utils['security'] = SecurityManager(config.ADMIN_IDS, config.WHITELIST)
        utils['limits'] = LimitManager(config)
        
        # Валидация конфигурации
        is_valid, errors = validate_all_required_env_vars()
        if not is_valid:
            logger.error(f"❌ Ошибки конфигурации: {errors}")
            raise ValueError(f"Некорректная конфигурация: {errors}")
        
        # ПЛАН 2: Инициализация утилит кармы (ЗАГЛУШКИ)
        if getattr(config, 'ENABLE_PLAN_2_FEATURES', False):
            logger.info("🔄 Инициализация утилит ПЛАН 2...")
            # TODO: Добавить инициализацию утилит кармы
            logger.info("⏸️ ПЛАН 2 - в разработке")
        
        # ПЛАН 3: Инициализация утилит ИИ и форм (ЗАГЛУШКИ)
        if getattr(config, 'ENABLE_PLAN_3_FEATURES', False):
            logger.info("🔄 Инициализация утилит ПЛАН 3...")
            # TODO: Добавить инициализацию утилит ИИ и форм
            logger.info("⏸️ ПЛАН 3 - в разработке")
        
        # ПЛАН 4: Инициализация утилит backup (ЗАГЛУШКИ)
        if getattr(config, 'ENABLE_PLAN_4_FEATURES', False):
            logger.info("🔄 Инициализация утилит ПЛАН 4...")
            # TODO: Добавить инициализацию утилит backup
            logger.info("⏸️ ПЛАН 4 - в разработке")
        
        logger.info(f"✅ Утилиты инициализированы: {len(utils)}")
        return utils
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации утилит: {e}")
        raise

def validate_system():
    """Валидация всей системы утилит"""
    try:
        logger.info("🔍 Валидация системы утилит...")
        
        # Проверка доступности модулей
        modules_status = {
            'logger': True,
            'security': True, 
            'helpers': True,
            'limits': True,
            'validators': True
        }
        
        # Проверка конфигурации
        config_valid, config_errors = validate_all_required_env_vars()
        
        # Создание отчета
        report = create_validation_report()
        
        # Итоговая валидация
        all_valid = all(modules_status.values()) and config_valid
        
        if all_valid:
            logger.info("✅ Валидация системы успешна")
        else:
            logger.error(f"❌ Ошибки валидации: {config_errors}")
        
        return {
            'valid': all_valid,
            'modules': modules_status,
            'config': config_valid,
            'errors': config_errors,
            'report': report
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка валидации системы: {e}")
        return {'valid': False, 'error': str(e)}

# ============================================
# ФУНКЦИИ ПОМОЩИ ДЛЯ РАЗРАБОТКИ
# ============================================

def get_available_utils():
    """Получение списка доступных утилит по планам"""
    return {
        'plan_1': [
            'logger - система логирования с эмодзи',
            'security - проверка прав и валидация',
            'helpers - вспомогательные функции',
            'limits - управление лимитами API',
            'validators - валидация данных'
        ],
        'plan_2': [
            # 'formatters - форматирование кармы и статистики'  # В разработке
        ],
        'plan_3': [
            # 'ai_helpers - утилиты для работы с ИИ',           # В разработке
            # 'form_helpers - утилиты для интерактивных форм'   # В разработке
        ],
        'plan_4': [
            # 'backup_helpers - утилиты для backup операций'   # В разработке
        ]
    }

def run_self_test():
    """Самотестирование модуля utils"""
    try:
        logger.info("🧪 Запуск самотестирования utils...")
        
        tests = {
            'format_user_mention': lambda: format_user_mention(12345, 'test'),
            'truncate_text': lambda: truncate_text('test text', 5),
            'is_valid_url': lambda: is_valid_url('https://example.com'),
            'generate_unique_id': lambda: generate_unique_id('test_'),
            'format_file_size': lambda: format_file_size(1024)
        }
        
        results = {}
        for test_name, test_func in tests.items():
            try:
                result = test_func()
                results[test_name] = {'success': True, 'result': result}
            except Exception as e:
                results[test_name] = {'success': False, 'error': str(e)}
        
        success_count = sum(1 for r in results.values() if r['success'])
        total_count = len(results)
        
        logger.info(f"🧪 Самотестирование завершено: {success_count}/{total_count}")
        return results
        
    except Exception as e:
        logger.error(f"❌ Ошибка самотестирования: {e}")
        return {}

# ============================================
# ИНФОРМАЦИЯ О МОДУЛЕ
# ============================================

def get_module_info():
    """Получение информации о модуле utils"""
    return {
        'name': 'utils',
        'version': 'v25+',
        'description': 'Вспомогательные утилиты для всех планов',
        'components': {
            'logger': 'Система логирования с эмодзи',
            'security': 'Проверка прав и безопасность', 
            'helpers': 'Общие вспомогательные функции',
            'limits': 'Управление лимитами Telegram API',
            'validators': 'Валидация конфигурации и данных'
        },
        'plans': {
            'plan_1': 'Базовые утилиты - АКТИВНЫ',
            'plan_2': 'Утилиты кармы - В РАЗРАБОТКЕ',
            'plan_3': 'Утилиты ИИ и форм - В РАЗРАБОТКЕ',
            'plan_4': 'Утилиты backup - В РАЗРАБОТКЕ'
        }
    }

logger.info("📦 Модуль utils/__init__.py загружен")