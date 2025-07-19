"""
Modules/user_management/__init__.py - Инициализация модуля управления пользователями
Do Presave Reminder Bot v29.07

МОДУЛЬ 1: Управление пользователями-музыкантами, система кармы, звания, онбординг
Приоритет: 1 (критически важный)
"""

from .module import UserManagementModule
from .models import MusicUser, KarmaHistory
from .services import UserService
from .handlers import UserManagementHandlers
from .validators import (
    UserDataValidator, 
    KarmaValidator, 
    OnboardingValidator,
    validate_user_input,
    sanitize_username,
    sanitize_name,
    sanitize_genre
)
from .config import (
    UserManagementConfig,
    KarmaConfig,
    RankConfig,
    OnboardingConfig,
    ValidationConfig,
    WebAppConfig,
    # Константы
    COMMAND_START,
    COMMAND_MYSTAT,
    COMMAND_PROFILE,
    COMMAND_KARMA_HISTORY,
    COMMAND_KARMA,
    COMMAND_KARMA_RATIO,
    EVENT_USER_REGISTERED,
    EVENT_KARMA_CHANGED,
    EVENT_RANK_CHANGED,
    EVENT_ONBOARDING_COMPLETED
)

# Версия модуля
__version__ = "1.0.0"

# Информация о модуле
__module_info__ = {
    "name": "user_management",
    "version": __version__,
    "description": "Управление пользователями, карма, звания, онбординг",
    "author": "Mister DMS",
    "plan": 1,
    "priority": 1,
    "dependencies": [],
    "commands": [
        COMMAND_START,
        COMMAND_MYSTAT,
        COMMAND_PROFILE,
        COMMAND_KARMA_HISTORY,
        COMMAND_KARMA,
        COMMAND_KARMA_RATIO
    ],
    "events": [
        EVENT_USER_REGISTERED,
        EVENT_KARMA_CHANGED,
        EVENT_RANK_CHANGED,
        EVENT_ONBOARDING_COMPLETED
    ],
    "webapp_integration": True,
    "database_tables": ["music_users", "karma_history"]
}

# Экспорт основных классов и функций
__all__ = [
    # Основной модуль
    'UserManagementModule',
    
    # Модели данных
    'MusicUser',
    'KarmaHistory',
    
    # Сервисы
    'UserService',
    
    # Обработчики
    'UserManagementHandlers',
    
    # Валидаторы
    'UserDataValidator',
    'KarmaValidator',
    'OnboardingValidator',
    'validate_user_input',
    'sanitize_username',
    'sanitize_name',
    'sanitize_genre',
    
    # Конфигурация
    'UserManagementConfig',
    'KarmaConfig',
    'RankConfig',
    'OnboardingConfig',
    'ValidationConfig',
    'WebAppConfig',
    
    # Константы команд
    'COMMAND_START',
    'COMMAND_MYSTAT',
    'COMMAND_PROFILE',
    'COMMAND_KARMA_HISTORY',
    'COMMAND_KARMA',
    'COMMAND_KARMA_RATIO',
    
    # Константы событий
    'EVENT_USER_REGISTERED',
    'EVENT_KARMA_CHANGED',
    'EVENT_RANK_CHANGED',
    'EVENT_ONBOARDING_COMPLETED',
    
    # Информация о модуле
    '__version__',
    '__module_info__'
]


def get_module_info():
    """Получение информации о модуле"""
    return __module_info__.copy()


def get_module_class():
    """Получение класса модуля для загрузки"""
    return UserManagementModule


def validate_module_dependencies():
    """Проверка зависимостей модуля"""
    # Проверяем наличие необходимых библиотек
    required_packages = [
        'sqlalchemy',
        'psycopg2',
        'pydantic'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        raise ImportError(f"Отсутствуют необходимые пакеты: {', '.join(missing_packages)}")
    
    return True


def get_module_stats():
    """Получение статистики модуля"""
    return {
        "version": __version__,
        "commands_count": len(__module_info__["commands"]),
        "events_count": len(__module_info__["events"]),
        "tables_count": len(__module_info__["database_tables"]),
        "has_webapp": __module_info__["webapp_integration"],
        "plan": __module_info__["plan"],
        "priority": __module_info__["priority"]
    }


# Инициализация модуля при импорте
if __name__ != "__main__":
    # Проверяем зависимости только при импорте как модуль
    try:
        validate_module_dependencies()
    except ImportError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️ Проблемы с зависимостями модуля user_management: {e}")


if __name__ == "__main__":
    # Тестирование модуля при прямом запуске
    print("🧪 Тестирование модуля user_management...")
    
    # Проверяем зависимости
    try:
        validate_module_dependencies()
        print("✅ Все зависимости найдены")
    except ImportError as e:
        print(f"❌ Проблемы с зависимостями: {e}")
    
    # Выводим информацию о модуле
    info = get_module_info()
    print(f"\n📦 Информация о модуле:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Выводим статистику
    stats = get_module_stats()
    print(f"\n📊 Статистика модуля:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Проверяем, что можно создать экземпляр конфигурации
    try:
        config = UserManagementConfig()
        is_valid, errors = config.validate_config()
        print(f"\n⚙️ Валидация конфигурации: {'✅' if is_valid else '❌'}")
        if errors:
            for error in errors:
                print(f"  - {error}")
    except Exception as e:
        print(f"❌ Ошибка создания конфигурации: {e}")
    
    print("\n✅ Тестирование модуля завершено")
    print(f"🚀 Модуль {info['name']} v{info['version']} готов к использованию!")
