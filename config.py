"""
🔧 Configuration Manager - Do Presave Reminder Bot v25+
Центральная конфигурация всех планов развития с feature flags
"""

import os
import sys
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

class ConfigError(Exception):
    """Ошибка конфигурации"""
    pass

class Config:
    """Централизованная конфигурация бота для всех планов"""
    
    def __init__(self):
        """Инициализация и валидация конфигурации"""
        self._validate_required_variables()
        self._setup_feature_flags()
        self._setup_telegram_config()
        self._setup_database_config()
        self._setup_api_limits()
        self._setup_webhook_config()
        self._setup_logging_config()
        self._setup_plan_specific_configs()
    
    # ============================================
    # ПЛАН 1 - БАЗОВАЯ КОНФИГУРАЦИЯ (ОБЯЗАТЕЛЬНО)
    # ============================================
    
    def _validate_required_variables(self):
        """Валидация критически важных переменных"""
        required_vars = {
            'BOT_TOKEN': 'Токен от @BotFather',
            'GROUP_ID': 'ID супергруппы (с минусом!)',
            'WHITELIST_ID': 'ID топиков через запятую',
            'ADMIN_IDS': 'ID админов через запятую',
            'DATABASE_URL': 'PostgreSQL connection string'
        }
        
        missing_vars = []
        for var, description in required_vars.items():
            if not os.getenv(var):
                missing_vars.append(f"{var} ({description})")
        
        if missing_vars:
            raise ConfigError(
                f"❌ Отсутствуют обязательные переменные окружения:\n" +
                "\n".join(f"• {var}" for var in missing_vars) +
                f"\n\n📋 Проверьте настройки на Render.com или файл .env"
            )
    
    def _setup_feature_flags(self):
        """Настройка feature flags для поэтапной разработки"""
        # Всегда включено (основа)
        self.ENABLE_PLAN_1_FEATURES = True
        
        # План 2 - Система кармы (v26)
        self.ENABLE_PLAN_2_FEATURES = self._get_bool('ENABLE_PLAN_2_FEATURES', False)
        
        # План 3 - ИИ и интерактивные формы (v27)
        self.ENABLE_PLAN_3_FEATURES = self._get_bool('ENABLE_PLAN_3_FEATURES', False)
        
        # План 4 - Backup система (v27.1) - КРИТИЧНО ВАЖНО!
        self.ENABLE_PLAN_4_FEATURES = self._get_bool('ENABLE_PLAN_4_FEATURES', True)
    
    def _setup_telegram_config(self):
        """Настройка Telegram Bot API"""
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        self.GROUP_ID = int(os.getenv('GROUP_ID'))
        
        # WHITELIST топиков через запятую (исправляем переменную!)
        whitelist_raw = os.getenv('WHITELIST_ID', os.getenv('WHITELIST', ''))
        self.WHITELIST_THREADS = [
            int(x.strip()) for x in whitelist_raw.split(',') 
            if x.strip().isdigit()
        ]
        
        # Парсинг админов
        admin_str = os.getenv('ADMIN_IDS', '')
        self.ADMIN_IDS = [
            int(admin_id.strip()) 
            for admin_id in admin_str.split(',') 
            if admin_id.strip().isdigit()
        ]
        
        # Текстовые сообщения
        self.REMINDER_TEXT = os.getenv(
            'REMINDER_TEXT', 
            '🎧 Напоминаем: не забудь сделать пресейв артистов выше! ♥️ Для твоего удобства нажми /last10links'
        )
        
        # Задержки
        self.RESPONSE_DELAY = int(os.getenv('RESPONSE_DELAY', '3'))
    
    def _setup_database_config(self):
        """Настройка базы данных PostgreSQL"""
        self.DATABASE_URL = os.getenv('DATABASE_URL')
        self.DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
        self.DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
        self.DB_POOL_RECYCLE = int(os.getenv('DB_POOL_RECYCLE', '3600'))
    
    def _setup_api_limits(self):
        """Настройка 4 режимов лимитов API"""
        # Conservative mode
        self.CONSERVATIVE_MAX_HOUR = int(os.getenv('CONSERVATIVE_MAX_HOUR', '60'))
        self.CONSERVATIVE_COOLDOWN = int(os.getenv('CONSERVATIVE_COOLDOWN', '60'))
        
        # Normal mode
        self.NORMAL_MAX_HOUR = int(os.getenv('NORMAL_MAX_HOUR', '180'))
        self.NORMAL_COOLDOWN = int(os.getenv('NORMAL_COOLDOWN', '20'))
        
        # Burst mode (ПО УМОЛЧАНИЮ)
        self.BURST_MAX_HOUR = int(os.getenv('BURST_MAX_HOUR', '600'))
        self.BURST_COOLDOWN = int(os.getenv('BURST_COOLDOWN', '6'))
        
        # Admin Burst mode
        self.ADMIN_BURST_MAX_HOUR = int(os.getenv('ADMIN_BURST_MAX_HOUR', '1200'))
        self.ADMIN_BURST_COOLDOWN = int(os.getenv('ADMIN_BURST_COOLDOWN', '3'))
        
        # Режим по умолчанию - BURST
        self.DEFAULT_LIMIT_MODE = 'BURST'
    
    def _setup_webhook_config(self):
        """Настройка webhook и Render.com"""
        self.RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL', '')
        self.WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'presave_bot_secret_2025')
        self.WEBHOOK_PATH = f"/webhook/{self.WEBHOOK_SECRET}"
        self.HEALTH_CHECK_PATH = "/health"
        self.PORT = int(os.getenv('PORT', '10000'))  # Render.com default
        
        # ДОБАВЛЯЕМ ОТСУТСТВУЮЩИЕ ПЕРЕМЕННЫЕ
        self.HOST = os.getenv('HOST', '0.0.0.0')
        self.WEBHOOK_URL = f"https://{self.RENDER_EXTERNAL_URL}{self.WEBHOOK_PATH}" if self.RENDER_EXTERNAL_URL else None
        self.WEBHOOK_MAX_CONNECTIONS = int(os.getenv('WEBHOOK_MAX_CONNECTIONS', '40'))
        
        # Keep-alive настройки
        self.KEEPALIVE_URL = os.getenv('KEEPALIVE_URL', '')
        self.KEEPALIVE_INTERVAL = int(os.getenv('KEEPALIVE_INTERVAL', '300'))
        self.KEEPALIVE_ENABLED = self._get_bool('KEEPALIVE_ENABLED', True)
        
        # Polling настройки (для локальной разработки)
        self.POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '1'))
        self.POLLING_TIMEOUT = int(os.getenv('POLLING_TIMEOUT', '20'))
    
    def _setup_logging_config(self):
        """Настройка логирования"""
        self.LOG_FORMAT = os.getenv('LOG_FORMAT', 'structured')
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.ENABLE_PERFORMANCE_LOGS = self._get_bool('ENABLE_PERFORMANCE_LOGS', True)
        self.CORRELATION_ID_HEADER = os.getenv('CORRELATION_ID_HEADER', 'X-Request-ID')
    
    # ============================================
    # ПЛАН 2 - КОНФИГУРАЦИЯ СИСТЕМЫ КАРМЫ
    # ============================================
    
    def _setup_karma_config(self):
        """Настройка системы кармы (План 2)"""
        if not self.ENABLE_PLAN_2_FEATURES:
            return
            
        # Максимальная карма
        self.MAX_KARMA = int(os.getenv('MAX_KARMA', '100500'))
        self.ADMIN_KARMA = int(os.getenv('ADMIN_KARMA', '100500'))
        
        # Cooldown между начислениями
        self.KARMA_COOLDOWN_SECONDS = int(os.getenv('KARMA_COOLDOWN_SECONDS', '60'))
        
        # Пороги для званий
        self.RANK_THRESHOLDS = {
            0: "🥉 Новенький",
            6: "🥈 Надежда сообщества", 
            16: "🥇 Мега-человечище",
            31: "💎 Амбассадорище"
        }
        
        # Включить автоматическое начисление кармы
        self.ENABLE_AUTO_KARMA = self._get_bool('ENABLE_AUTO_KARMA', True)
    
    # ============================================
    # ПЛАН 3 - КОНФИГУРАЦИЯ ИИ И ФОРМ
    # ============================================
    
    def _setup_ai_config(self):
        """Настройка ИИ интеграции (План 3)"""
        if not self.ENABLE_PLAN_3_FEATURES:
            return
            
        # AI API Keys
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
        self.ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
        
        # AI Settings
        self.AI_MODEL = os.getenv('AI_MODEL', 'gpt-3.5-turbo')
        self.AI_MAX_TOKENS = int(os.getenv('AI_MAX_TOKENS', '1000'))
        self.AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', '0.7'))
        self.AI_ENABLED = self._get_bool('AI_ENABLED', True)
        
        # Автоматическое распознавание благодарностей
        self.AUTO_KARMA_ENABLED = self._get_bool('AUTO_KARMA_ENABLED', True)
        self.GRATITUDE_COOLDOWN_MINUTES = int(os.getenv('GRATITUDE_COOLDOWN_MINUTES', '60'))
        self.MIN_MESSAGE_LENGTH_FOR_KARMA = int(os.getenv('MIN_MESSAGE_LENGTH_FOR_KARMA', '10'))
        
        # Словарь благодарностей
        self.GRATITUDE_WORDS = {
            'ru': [
                'спасибо', 'спс', 'спасиб', 'спасибочки', 'спасибки', 'благодарю', 'благодарочка',
                'огонь', 'огонёк', 'крутяк', 'круто', 'классно', 'шикарно', 'офигенно',
                'полезно', 'помогло', 'выручил', 'выручила', 'выручайка', 'спас', 'спасла',
                'плюс в карму', '+карма', '+ в карму', 'плюсик', 'плюсанул', 'респект',
                'топ', 'топчик', 'лайк', 'зачёт', 'годно', 'тема', 'бомба', 'красава'
            ],
            'en': [
                'thx', 'thanks', 'thank you', 'ty', 'appreciate', 'grateful',
                'awesome', 'cool', 'nice', 'great', 'amazing', 'fantastic',
                'helped', 'helpful', 'useful', 'perfect', 'excellent',
                'props', 'respect', 'kudos', 'good job', 'well done'
            ]
        }
    
    def _setup_forms_config(self):
        """Настройка интерактивных форм (План 3)"""
        if not self.ENABLE_PLAN_3_FEATURES:
            return
            
        # Настройки форм
        self.FORMS_ENABLED = self._get_bool('FORMS_ENABLED', True)
        self.MAX_SCREENSHOTS_PER_CLAIM = int(os.getenv('MAX_SCREENSHOTS_PER_CLAIM', '5'))
        self.SCREENSHOT_MAX_SIZE_MB = int(os.getenv('SCREENSHOT_MAX_SIZE_MB', '10'))
        self.FORM_TIMEOUT_MINUTES = int(os.getenv('FORM_TIMEOUT_MINUTES', '30'))
    
    # ============================================
    # ПЛАН 4 - КОНФИГУРАЦИЯ BACKUP СИСТЕМЫ
    # ============================================
    
    def _setup_backup_config(self):
        """Настройка backup системы (План 4)"""
        if not self.ENABLE_PLAN_4_FEATURES:
            return
            
        # Мониторинг базы данных
        self.DATABASE_CREATED_DATE = os.getenv('DATABASE_CREATED_DATE', '2025-01-15')
        
        # Дни для уведомлений
        warning_days_str = os.getenv('BACKUP_WARNING_DAYS', '25,28,30,44')
        self.BACKUP_WARNING_DAYS = [
            int(day.strip()) 
            for day in warning_days_str.split(',') 
            if day.strip().isdigit()
        ]
        
        # Настройки backup
        self.BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '7'))
        self.AUTO_BACKUP_ENABLED = self._get_bool('AUTO_BACKUP_ENABLED', True)
        self.BACKUP_NOTIFICATIONS_ENABLED = self._get_bool('BACKUP_NOTIFICATIONS_ENABLED', True)
        self.BACKUP_CHECK_TIME = os.getenv('BACKUP_CHECK_TIME', '10:00')
        
        # Параметры архивации
        self.BACKUP_COMPRESSION_LEVEL = int(os.getenv('BACKUP_COMPRESSION_LEVEL', '6'))
        self.BACKUP_MAX_SIZE_MB = int(os.getenv('BACKUP_MAX_SIZE_MB', '45'))  # Лимит Telegram 50MB
        self.BACKUP_INCLUDE_LOGS = self._get_bool('BACKUP_INCLUDE_LOGS', False)
        self.BACKUP_ENCRYPT = self._get_bool('BACKUP_ENCRYPT', False)
        
        # Настройки миграции
        self.MIGRATION_TIMEOUT_MINUTES = int(os.getenv('MIGRATION_TIMEOUT_MINUTES', '15'))
        self.ALLOW_DATA_LOSS_RECOVERY = self._get_bool('ALLOW_DATA_LOSS_RECOVERY', False)
        self.BACKUP_VERIFICATION_ENABLED = self._get_bool('BACKUP_VERIFICATION_ENABLED', True)
    
    def _setup_plan_specific_configs(self):
        """Настройка конфигураций для включенных планов"""
        if self.ENABLE_PLAN_2_FEATURES:
            self._setup_karma_config()
            
        if self.ENABLE_PLAN_3_FEATURES:
            self._setup_ai_config()
            self._setup_forms_config()
            
        if self.ENABLE_PLAN_4_FEATURES:
            self._setup_backup_config()
    
    # ============================================
    # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ
    # ============================================
    
    def _setup_development_config(self):
        """Настройки для разработки"""
        self.DEBUG = self._get_bool('DEBUG', False)
        self.DEVELOPMENT_MODE = self._get_bool('DEVELOPMENT_MODE', False)
        self.TEST_MODE = self._get_bool('TEST_MODE', False)
    
    def _setup_performance_config(self):
        """Настройки производительности"""
        self.ASYNC_WORKERS = int(os.getenv('ASYNC_WORKERS', '2'))
        self.REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
        self.MAX_CONCURRENT_OPERATIONS = int(os.getenv('MAX_CONCURRENT_OPERATIONS', '10'))
    
    def _setup_monitoring_config(self):
        """Настройки мониторинга"""
        self.HEALTH_CHECK_ENABLED = self._get_bool('HEALTH_CHECK_ENABLED', True)
        self.METRICS_COLLECTION = self._get_bool('METRICS_COLLECTION', True)
        self.ERROR_REPORTING = self._get_bool('ERROR_REPORTING', True)
    
    # ============================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================
    
    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Получение boolean значения из environment variable"""
        value = os.getenv(key, str(default))
        return value.lower() in ('true', '1', 'yes', 'on')
    
    def _get_list(self, key: str, default: List[str] = None, separator: str = ',') -> List[str]:
        """Получение списка из environment variable"""
        if default is None:
            default = []
        value = os.getenv(key, '')
        if not value:
            return default
        return [item.strip() for item in value.split(separator) if item.strip()]
    
    def get_limit_config(self, mode: str) -> Dict[str, int]:
        """Получение конфигурации лимитов для указанного режима"""
        limit_configs = {
            'CONSERVATIVE': {
                'max_hour': self.CONSERVATIVE_MAX_HOUR,
                'cooldown': self.CONSERVATIVE_COOLDOWN
            },
            'NORMAL': {
                'max_hour': self.NORMAL_MAX_HOUR,
                'cooldown': self.NORMAL_COOLDOWN
            },
            'BURST': {
                'max_hour': self.BURST_MAX_HOUR,
                'cooldown': self.BURST_COOLDOWN
            },
            'ADMIN_BURST': {
                'max_hour': self.ADMIN_BURST_MAX_HOUR,
                'cooldown': self.ADMIN_BURST_COOLDOWN
            }
        }
        
        return limit_configs.get(mode.upper(), limit_configs['BURST'])
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка является ли пользователь админом"""
        return user_id in self.ADMIN_IDS
    
    def is_whitelisted_thread(self, thread_id: int) -> bool:
        """Проверка находится ли топик в whitelist"""
        return thread_id in self.WHITELIST_THREADS
    
    def get_webhook_url(self) -> str:
        """Получение полного URL webhook"""
        if not self.RENDER_EXTERNAL_URL:
            return ""
        return f"https://{self.RENDER_EXTERNAL_URL}{self.WEBHOOK_PATH}"
    
    def validate_ai_config(self) -> bool:
        """Валидация конфигурации ИИ"""
        if not self.ENABLE_PLAN_3_FEATURES:
            return True
            
        if not self.AI_ENABLED:
            return True
            
        # Проверяем наличие хотя бы одного API ключа
        has_openai = bool(self.OPENAI_API_KEY)
        has_anthropic = bool(self.ANTHROPIC_API_KEY)
        
        return has_openai or has_anthropic
    
    def get_enabled_features_summary(self) -> str:
        """Получение сводки включенных функций"""
        features = []
        
        if self.ENABLE_PLAN_1_FEATURES:
            features.append("✅ План 1: Базовый функционал")
            
        if self.ENABLE_PLAN_2_FEATURES:
            features.append("✅ План 2: Система кармы")
            
        if self.ENABLE_PLAN_3_FEATURES:
            features.append("✅ План 3: ИИ и интерактивные формы")
            
        if self.ENABLE_PLAN_4_FEATURES:
            features.append("✅ План 4: Backup система")
        
        return "\n".join(features)
    
    def __repr__(self) -> str:
        """Строковое представление конфигурации"""
        return f"""
🔧 Do Presave Reminder Bot Configuration v25+

📊 Включенные планы:
{self.get_enabled_features_summary()}

🤖 Telegram Bot:
• GROUP_ID: {self.GROUP_ID}
• WHITELIST топиков: {len(self.WHITELIST_THREADS)}
• Админов: {len(self.ADMIN_IDS)}

🗃️ База данных:
• PostgreSQL pool: {self.DB_POOL_SIZE}
• URL: {'✅ Настроена' if self.DATABASE_URL else '❌ Не настроена'}

⚡ Режим лимитов по умолчанию: {self.DEFAULT_LIMIT_MODE}

🔄 Webhook: {'✅ Настроен' if self.RENDER_EXTERNAL_URL else '❌ Не настроен'}
"""

# ============================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР КОНФИГУРАЦИИ
# ============================================

# Создаем глобальный экземпляр конфигурации
try:
    config = Config()
except ConfigError as e:
    print(f"\n{e}\n")
    sys.exit(1)

# Экспортируем для импорта в других модулях
__all__ = ['config', 'Config', 'ConfigError']

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИМПОРТА
# ============================================

def get_config() -> Config:
    """Получение глобального экземпляра конфигурации"""
    return config

def is_plan_enabled(plan_number: int) -> bool:
    """Проверка включен ли определённый план"""
    plan_flags = {
        1: config.ENABLE_PLAN_1_FEATURES,
        2: config.ENABLE_PLAN_2_FEATURES,
        3: config.ENABLE_PLAN_3_FEATURES,
        4: config.ENABLE_PLAN_4_FEATURES
    }
    return plan_flags.get(plan_number, False)

def get_bot_token() -> str:
    """Получение токена бота"""
    return config.BOT_TOKEN

def get_admin_ids() -> List[int]:
    """Получение списка ID админов"""
    return config.ADMIN_IDS

def get_whitelist_threads() -> List[int]:
    """Получение списка разрешённых топиков"""
    return config.WHITELIST_THREADS

if __name__ == "__main__":
    # Тестирование конфигурации
    print("🔧 Тестирование конфигурации...")
    print(config)
    
    print("🧪 Результаты валидации:")
    print(f"• Telegram Bot Token: {'✅' if config.BOT_TOKEN else '❌'}")
    print(f"• Database URL: {'✅' if config.DATABASE_URL else '❌'}")
    print(f"• Admin IDs: {'✅' if config.ADMIN_IDS else '❌'}")
    print(f"• Whitelist Threads: {'✅' if config.WHITELIST_THREADS else '❌'}")
    
    if config.ENABLE_PLAN_3_FEATURES:
        print(f"• AI Configuration: {'✅' if config.validate_ai_config() else '❌'}")
    
    print("\n🚀 Конфигурация готова к использованию!")
