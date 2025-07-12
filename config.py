"""
Конфигурация Do Presave Reminder Bot v25+
Загрузка и валидация переменных окружения для всех планов развития
"""

import os
from typing import List, Optional
from dotenv import load_dotenv

# Загрузка переменных из .env файла
load_dotenv()

class Config:
    """Класс конфигурации с переменными для всех планов"""
    
    def __init__(self):
        """Инициализация конфигурации"""
        
        # ============================================
        # ПЛАН 1: БАЗОВЫЕ ПЕРЕМЕННЫЕ (ОБЯЗАТЕЛЬНЫЕ)
        # ============================================
        
        # Telegram Bot API
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        self.GROUP_ID = int(os.getenv('GROUP_ID', '0'))
        self.WHITELIST = self._parse_int_list(os.getenv('WHITELIST', ''))
        self.ADMIN_IDS = self._parse_int_list(os.getenv('ADMIN_IDS', ''))
        
        # Render.com Deployment
        self.RENDER_EXTERNAL_URL = os.getenv('RENDER_EXTERNAL_URL')
        self.WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
        
        # Текстовые сообщения
        self.REMINDER_TEXT = os.getenv(
            'REMINDER_TEXT', 
            '🎧 Напоминаем: не забудь сделать пресейв артистов выше! ♥️ Для твоего удобства нажми /last10links'
        )
        self.RESPONSE_DELAY = int(os.getenv('RESPONSE_DELAY', '3'))
        
        # Режимы лимитов API (4 режима)
        self.CONSERVATIVE_MAX_HOUR = int(os.getenv('CONSERVATIVE_MAX_HOUR', '60'))
        self.CONSERVATIVE_COOLDOWN = int(os.getenv('CONSERVATIVE_COOLDOWN', '60'))
        
        self.NORMAL_MAX_HOUR = int(os.getenv('NORMAL_MAX_HOUR', '180'))
        self.NORMAL_COOLDOWN = int(os.getenv('NORMAL_COOLDOWN', '20'))
        
        self.BURST_MAX_HOUR = int(os.getenv('BURST_MAX_HOUR', '600'))
        self.BURST_COOLDOWN = int(os.getenv('BURST_COOLDOWN', '6'))
        
        self.ADMIN_BURST_MAX_HOUR = int(os.getenv('ADMIN_BURST_MAX_HOUR', '1200'))
        self.ADMIN_BURST_COOLDOWN = int(os.getenv('ADMIN_BURST_COOLDOWN', '3'))
        
        # База данных
        self.DATABASE_URL = os.getenv('DATABASE_URL')
        self.DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
        
        # HTTP сервер и keep-alive
        self.HOST = os.getenv('HOST', '0.0.0.0')
        self.WEBHOOK_MAX_CONNECTIONS = int(os.getenv('WEBHOOK_MAX_CONNECTIONS', '40'))
        self.KEEPALIVE_ENABLED = os.getenv('KEEPALIVE_ENABLED', 'true').lower() == 'true'
        self.KEEPALIVE_INTERVAL = int(os.getenv('KEEPALIVE_INTERVAL', '300'))
        self.POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', '1'))
        self.POLLING_TIMEOUT = int(os.getenv('POLLING_TIMEOUT', '20'))
        
        # Логирование и мониторинг
        self.LOG_FORMAT = os.getenv('LOG_FORMAT', 'structured')
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.ENABLE_PERFORMANCE_LOGS = os.getenv('ENABLE_PERFORMANCE_LOGS', 'true').lower() == 'true'
        self.CORRELATION_ID_HEADER = os.getenv('CORRELATION_ID_HEADER', 'X-Request-ID')
        
        # Дополнительные настройки
        self.DEBUG = os.getenv('DEBUG', 'false').lower() == 'true'
        self.DEVELOPMENT_MODE = os.getenv('DEVELOPMENT_MODE', 'false').lower() == 'true'
        self.TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'
        
        # ============================================
        # ПЛАН 2: СИСТЕМА КАРМЫ (ЗАГЛУШКИ)
        # ============================================
        
        # Настройки кармы
        # self.MAX_KARMA = int(os.getenv('MAX_KARMA', '100500'))
        # self.ADMIN_KARMA = int(os.getenv('ADMIN_KARMA', '100500'))
        # self.KARMA_COOLDOWN_SECONDS = int(os.getenv('KARMA_COOLDOWN_SECONDS', '60'))
        # self.ENABLE_AUTO_KARMA = os.getenv('ENABLE_AUTO_KARMA', 'true').lower() == 'true'
        
        # Система званий
        # self.RANK_NEWBIE_MIN = int(os.getenv('RANK_NEWBIE_MIN', '0'))
        # self.RANK_NEWBIE_MAX = int(os.getenv('RANK_NEWBIE_MAX', '5'))
        # self.RANK_HOPE_MIN = int(os.getenv('RANK_HOPE_MIN', '6'))
        # self.RANK_HOPE_MAX = int(os.getenv('RANK_HOPE_MAX', '15'))
        # self.RANK_MEGA_MIN = int(os.getenv('RANK_MEGA_MIN', '16'))
        # self.RANK_MEGA_MAX = int(os.getenv('RANK_MEGA_MAX', '30'))
        # self.RANK_AMBASSADOR_MIN = int(os.getenv('RANK_AMBASSADOR_MIN', '31'))
        
        # ============================================
        # ПЛАН 3: ИИ И ИНТЕРАКТИВНЫЕ ФОРМЫ (ЗАГЛУШКИ)
        # ============================================
        
        # AI API Keys
        # self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        # self.ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
        # self.AI_MODEL = os.getenv('AI_MODEL', 'gpt-3.5-turbo')
        # self.AI_MAX_TOKENS = int(os.getenv('AI_MAX_TOKENS', '1000'))
        # self.AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', '0.7'))
        # self.AI_ENABLED = os.getenv('AI_ENABLED', 'false').lower() == 'true'
        
        # Автоматическое распознавание благодарностей
        # self.AUTO_KARMA_ENABLED = os.getenv('AUTO_KARMA_ENABLED', 'false').lower() == 'true'
        # self.GRATITUDE_COOLDOWN_MINUTES = int(os.getenv('GRATITUDE_COOLDOWN_MINUTES', '60'))
        # self.MIN_MESSAGE_LENGTH_FOR_KARMA = int(os.getenv('MIN_MESSAGE_LENGTH_FOR_KARMA', '10'))
        
        # Система интерактивных форм
        # self.FORMS_ENABLED = os.getenv('FORMS_ENABLED', 'false').lower() == 'true'
        # self.MAX_SCREENSHOTS_PER_CLAIM = int(os.getenv('MAX_SCREENSHOTS_PER_CLAIM', '5'))
        # self.SCREENSHOT_MAX_SIZE_MB = int(os.getenv('SCREENSHOT_MAX_SIZE_MB', '10'))
        # self.FORM_TIMEOUT_MINUTES = int(os.getenv('FORM_TIMEOUT_MINUTES', '30'))
        
        # ============================================
        # ПЛАН 4: BACKUP СИСТЕМА (ЗАГЛУШКИ)
        # ============================================
        
        # Мониторинг базы данных
        # self.DATABASE_CREATED_DATE = os.getenv('DATABASE_CREATED_DATE', '2025-01-15')
        # self.BACKUP_WARNING_DAYS = self._parse_int_list(os.getenv('BACKUP_WARNING_DAYS', '25,28,30,44'))
        # self.BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '7'))
        # self.AUTO_BACKUP_ENABLED = os.getenv('AUTO_BACKUP_ENABLED', 'true').lower() == 'true'
        # self.BACKUP_NOTIFICATIONS_ENABLED = os.getenv('BACKUP_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
        # self.BACKUP_CHECK_TIME = os.getenv('BACKUP_CHECK_TIME', '10:00')
        
        # Настройки backup
        # self.BACKUP_COMPRESSION_LEVEL = int(os.getenv('BACKUP_COMPRESSION_LEVEL', '6'))
        # self.BACKUP_MAX_SIZE_MB = int(os.getenv('BACKUP_MAX_SIZE_MB', '45'))
        # self.BACKUP_INCLUDE_LOGS = os.getenv('BACKUP_INCLUDE_LOGS', 'false').lower() == 'true'
        # self.BACKUP_ENCRYPT = os.getenv('BACKUP_ENCRYPT', 'false').lower() == 'true'
        
        # Настройки миграции
        # self.MIGRATION_TIMEOUT_MINUTES = int(os.getenv('MIGRATION_TIMEOUT_MINUTES', '15'))
        # self.ALLOW_DATA_LOSS_RECOVERY = os.getenv('ALLOW_DATA_LOSS_RECOVERY', 'false').lower() == 'true'
        # self.BACKUP_VERIFICATION_ENABLED = os.getenv('BACKUP_VERIFICATION_ENABLED', 'true').lower() == 'true'
        
        # ============================================
        # FEATURE FLAGS (ДЛЯ ПОЭТАПНОГО ВКЛЮЧЕНИЯ)
        # ============================================
        
        self.ENABLE_PLAN_2_FEATURES = os.getenv('ENABLE_PLAN_2_FEATURES', 'false').lower() == 'true'
        self.ENABLE_PLAN_3_FEATURES = os.getenv('ENABLE_PLAN_3_FEATURES', 'false').lower() == 'true'
        self.ENABLE_PLAN_4_FEATURES = os.getenv('ENABLE_PLAN_4_FEATURES', 'false').lower() == 'true'
        
        # ============================================
        # ФЛАГИ УПРАВЛЕНИЯ БАЗОЙ ДАННЫХ
        # ============================================

        # КРИТИЧЕСКИЙ ФЛАГ: Принудительное пересоздание таблиц при старте
        self.FORCE_RECREATE_TABLES = os.getenv('FORCE_RECREATE_TABLES', 'false').lower() == 'true'
        self.FORCE_DROP_CASCADE = os.getenv('FORCE_DROP_CASCADE', 'true').lower() == 'true'
        
        
    def _parse_int_list(self, value: str) -> List[int]:
        """Парсинг списка целых чисел из строки через запятую"""
        if not value:
            return []
        try:
            return [int(x.strip()) for x in value.split(',') if x.strip()]
        except ValueError:
            return []
    
    def get_current_limit_mode(self) -> str:
        """Получение текущего режима лимитов (по умолчанию BURST)"""
        return os.getenv('CURRENT_LIMIT_MODE', 'BURST')
    
    def set_limit_mode(self, mode: str) -> bool:
        """Установка режима лимитов"""
        valid_modes = ['CONSERVATIVE', 'NORMAL', 'BURST', 'ADMIN_BURST']
        if mode.upper() in valid_modes:
            os.environ['CURRENT_LIMIT_MODE'] = mode.upper()
            return True
        return False
    
    def get_limit_config(self, mode: Optional[str] = None) -> dict:
        """Получение конфигурации лимитов для указанного режима"""
        if not mode:
            mode = self.get_current_limit_mode()
            
        mode = mode.upper()
        
        configs = {
            'CONSERVATIVE': {
                'max_hour': self.CONSERVATIVE_MAX_HOUR,
                'cooldown': self.CONSERVATIVE_COOLDOWN,
                'name': 'Conservative',
                'emoji': '🐌'
            },
            'NORMAL': {
                'max_hour': self.NORMAL_MAX_HOUR,
                'cooldown': self.NORMAL_COOLDOWN,
                'name': 'Normal',
                'emoji': '⚡'
            },
            'BURST': {
                'max_hour': self.BURST_MAX_HOUR,
                'cooldown': self.BURST_COOLDOWN,
                'name': 'Burst',
                'emoji': '🚀'
            },
            'ADMIN_BURST': {
                'max_hour': self.ADMIN_BURST_MAX_HOUR,
                'cooldown': self.ADMIN_BURST_COOLDOWN,
                'name': 'Admin Burst',
                'emoji': '⚡⚡'
            }
        }
        
        return configs.get(mode, configs['BURST'])
    
    def is_feature_enabled(self, plan: int) -> bool:
        """Проверка включения функций конкретного плана"""
        if plan == 2:
            return self.ENABLE_PLAN_2_FEATURES
        elif plan == 3:
            return self.ENABLE_PLAN_3_FEATURES
        elif plan == 4:
            return self.ENABLE_PLAN_4_FEATURES
        return True  # План 1 всегда включен


def validate_config() -> bool:
    """Валидация критически важных переменных окружения"""
    
    # Критически важные переменные ПЛАН 1
    required_vars = [
        'BOT_TOKEN',
        'GROUP_ID', 
        'ADMIN_IDS',
        'DATABASE_URL'
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.strip() == '':
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        print("💡 Проверьте файл .env или настройки на Render.com")
        return False
    
    # Валидация BOT_TOKEN
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token.count(':') == 1 or len(bot_token) < 40:
        print("❌ Неверный формат BOT_TOKEN")
        return False
    
    # Валидация GROUP_ID (должен быть отрицательным для супергрупп)
    try:
        group_id = int(os.getenv('GROUP_ID', '0'))
        if group_id >= 0:
            print("❌ GROUP_ID должен быть отрицательным для супергрупп")
            return False
    except ValueError:
        print("❌ GROUP_ID должен быть числом")
        return False
    
    # Валидация ADMIN_IDS
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    try:
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]
        if len(admin_ids) == 0:
            print("❌ Должен быть указан хотя бы один ADMIN_ID")
            return False
    except ValueError:
        print("❌ ADMIN_IDS должны быть числами через запятую")
        return False
    
    # Валидация DATABASE_URL
    database_url = os.getenv('DATABASE_URL', '')
    if not database_url.startswith('postgresql://'):
        print("❌ DATABASE_URL должен быть PostgreSQL connection string")
        return False
    
    print("✅ Конфигурация прошла валидацию")
    return True


def print_config_summary():
    """Вывод краткой сводки конфигурации"""
    config = Config()
    
    print("=" * 50)
    print("📋 КОНФИГУРАЦИЯ DO PRESAVE REMINDER BOT v25+")
    print("=" * 50)
    
    print(f"🤖 Bot Token: {config.BOT_TOKEN[:10]}...{config.BOT_TOKEN[-5:]}")
    print(f"👥 Group ID: {config.GROUP_ID}")
    print(f"📝 Whitelist: {config.WHITELIST}")
    print(f"👑 Admins: {len(config.ADMIN_IDS)} админов")
    print(f"🌐 External URL: {config.RENDER_EXTERNAL_URL or 'Не указан (polling mode)'}")
    
    # Текущий режим лимитов
    current_mode = config.get_current_limit_mode()
    limit_config = config.get_limit_config(current_mode)
    print(f"⚡ Режим лимитов: {limit_config['emoji']} {limit_config['name']}")
    
    # Статус feature flags
    print(f"🏆 ПЛАН 2 (карма): {'✅ Включен' if config.ENABLE_PLAN_2_FEATURES else '⏸️ Отключен'}")
    print(f"🤖 ПЛАН 3 (ИИ): {'✅ Включен' if config.ENABLE_PLAN_3_FEATURES else '⏸️ Отключен'}")
    print(f"💾 ПЛАН 4 (backup): {'✅ Включен' if config.ENABLE_PLAN_4_FEATURES else '⏸️ Отключен'}")
    
    print("=" * 50)


if __name__ == "__main__":
    """Тестирование конфигурации"""
    if validate_config():
        print_config_summary()
    else:
        print("❌ Конфигурация содержит ошибки!")
        exit(1)