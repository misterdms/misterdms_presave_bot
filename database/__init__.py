"""
Модуль работы с базой данных - Do Presave Reminder Bot v25+
Инициализация PostgreSQL подключения, моделей и менеджеров данных

ПЛАН 1: Базовые модели и операции (АКТИВНЫЕ)
ПЛАН 2: Модели и операции кармы (ЗАГЛУШКИ)
ПЛАН 3: Модели и операции ИИ/форм (ЗАГЛУШКИ) 
ПЛАН 4: Модели и операции backup (ЗАГЛУШКИ)
"""

from utils.logger import get_logger

logger = get_logger(__name__)

# ============================================
# ПЛАН 1: БАЗОВЫЕ КОМПОНЕНТЫ БД (АКТИВНЫЕ)
# ============================================

# Основные компоненты - всегда импортируются
from .models import (
    init_database_models,
    # Базовые модели ПЛАН 1
    User,
    Link,
    Settings,
    # Заглушки моделей для будущих планов
    # UserKarma,      # ПЛАН 2
    # KarmaHistory,   # ПЛАН 2
    # PresaveRequest, # ПЛАН 3
    # ApprovalClaim,  # ПЛАН 3
    # ClaimScreenshot,# ПЛАН 3
    # BackupLog,      # ПЛАН 4
)

from .manager import DatabaseManager

# ПЛАН 1: Аналитика (АКТИВНАЯ)
from .analytics import AnalyticsManager

# ============================================
# ПЛАН 2: КОМПОНЕНТЫ КАРМЫ (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 2
# from .karma_manager import KarmaDataManager

# ============================================
# ПЛАН 3: КОМПОНЕНТЫ ИИ И ФОРМ (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 3
# from .forms_manager import FormsDataManager
# from .ai_manager import AIDataManager

# ============================================
# ПЛАН 4: КОМПОНЕНТЫ BACKUP (ЗАГЛУШКИ)
# ============================================

# TODO: Импорт будет активирован в ПЛАНЕ 4
# from .migrations import MigrationsManager
# from .backup_manager import BackupDataManager

# ============================================
# ЭКСПОРТ АКТИВНЫХ КОМПОНЕНТОВ
# ============================================

__all__ = [
    # Инициализация
    'init_database_models',
    
    # ПЛАН 1 (АКТИВНЫЕ)
    'DatabaseManager',
    'AnalyticsManager',
    'User',
    'Link', 
    'Settings',
    
    # ПЛАН 2 (ЗАГЛУШКИ)
    # 'KarmaDataManager',
    # 'UserKarma',
    # 'KarmaHistory',
    
    # ПЛАН 3 (ЗАГЛУШКИ)
    # 'FormsDataManager',
    # 'AIDataManager',
    # 'PresaveRequest',
    # 'ApprovalClaim',
    # 'ClaimScreenshot',
    
    # ПЛАН 4 (ЗАГЛУШКИ)
    # 'MigrationsManager',
    # 'BackupDataManager',
    # 'BackupLog',
]

# ============================================
# ФУНКЦИИ ИНИЦИАЛИЗАЦИИ
# ============================================

def init_database(database_url: str = None):
    """
    Инициализация базы данных со всеми таблицами
    
    Args:
        database_url: URL подключения к PostgreSQL
        
    Returns:
        DatabaseManager: Инициализированный менеджер БД
    """
    try:
        logger.info("🔄 Инициализация базы данных...")
        
        # Создание менеджера БД
        db_manager = DatabaseManager(database_url)
        
        # Инициализация моделей
        init_database_models(db_manager.engine)
        
        # Создание таблиц
        db_manager.create_tables()
        
        # Инициализация начальных данных
        db_manager.init_default_settings()
        
        logger.info("✅ База данных инициализирована")
        return db_manager
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise

def get_database_info():
    """Получение информации о структуре БД"""
    return {
        'plan_1_tables': [
            'users - пользователи бота',
            'links - ссылки пользователей', 
            'settings - настройки бота'
        ],
        'plan_2_tables': [
            # 'user_karma - карма пользователей',        # В разработке
            # 'karma_history - история изменений кармы'   # В разработке
        ],
        'plan_3_tables': [
            # 'presave_requests - заявки на пресейвы',     # В разработке
            # 'approval_claims - заявки на аппрувы',       # В разработке
            # 'claim_screenshots - скриншоты заявок',      # В разработке
            # 'auto_karma_log - автоматические начисления' # В разработке
        ],
        'plan_4_tables': [
            # 'backup_logs - логи backup операций',        # В разработке
            # 'migration_logs - логи миграций'             # В разработке
        ]
    }

def validate_database_connection(db_manager: DatabaseManager) -> bool:
    """
    Валидация подключения к базе данных
    
    Args:
        db_manager: Менеджер базы данных
        
    Returns:
        bool: True если подключение работает
    """
    try:
        # Простая проверка подключения
        with db_manager.get_session() as session:
            result = session.execute('SELECT 1').scalar()
            return result == 1
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки подключения БД: {e}")
        return False

def get_database_stats(db_manager: DatabaseManager) -> dict:
    """
    Получение статистики базы данных
    
    Args:
        db_manager: Менеджер базы данных
        
    Returns:
        dict: Статистика по таблицам
    """
    try:
        stats = {}
        
        with db_manager.get_session() as session:
            # Статистика по основным таблицам ПЛАН 1
            stats['users'] = session.query(User).count()
            stats['links'] = session.query(Link).count()
            stats['settings'] = session.query(Settings).count()
            
            # TODO: Добавить статистику для остальных планов
            # if PLAN_2_ENABLED:
            #     stats['user_karma'] = session.query(UserKarma).count()
            
            # if PLAN_3_ENABLED:
            #     stats['presave_requests'] = session.query(PresaveRequest).count()
            
            # if PLAN_4_ENABLED:
            #     stats['backup_logs'] = session.query(BackupLog).count()
            
        logger.info(f"📊 Статистика БД получена: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики БД: {e}")
        return {}

# ============================================
# УТИЛИТЫ ДЛЯ РАЗРАБОТКИ
# ============================================

def create_test_data(db_manager: DatabaseManager):
    """
    Создание тестовых данных для разработки
    ТОЛЬКО для development режима!
    """
    try:
        logger.warning("🧪 Создание тестовых данных (только для development)...")
        
        # Проверяем что мы в режиме разработки
        import os
        if os.getenv('DEVELOPMENT_MODE', 'false').lower() != 'true':
            logger.warning("⚠️ Тестовые данные создаются только в DEVELOPMENT_MODE")
            return
        
        with db_manager.get_session() as session:
            # Создание тестового пользователя
            test_user = db_manager.get_or_create_user(
                user_id=12345,
                username='test_user',
                first_name='Test',
                last_name='User'
            )
            
            # Создание тестовой ссылки
            db_manager.save_link(
                user_id=12345,
                url='https://example.com/test',
                thread_id=3,
                message_id=100
            )
            
            session.commit()
            
        logger.info("✅ Тестовые данные созданы")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания тестовых данных: {e}")

# ============================================
# ИНФОРМАЦИЯ О МОДУЛЕ
# ============================================

def get_module_info():
    """Получение информации о модуле database"""
    return {
        'name': 'database',
        'version': 'v25+',
        'description': 'Работа с PostgreSQL базой данных',
        'engine': 'PostgreSQL + SQLAlchemy',
        'plans': {
            'plan_1': 'Базовые таблицы и операции - АКТИВНЫ',
            'plan_2': 'Таблицы и операции кармы - В РАЗРАБОТКЕ',
            'plan_3': 'Таблицы и операции ИИ/форм - В РАЗРАБОТКЕ',
            'plan_4': 'Таблицы и операции backup - В РАЗРАБОТКЕ'
        }
    }

logger.info("📦 Модуль database/__init__.py загружен")