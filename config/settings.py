"""
Config/Settings.py - Основные настройки Do Presave Reminder Bot v29.07

Этот модуль управляет всеми настройками бота, загружая их из переменных окружения
и предоставляя удобный API для доступа к конфигурации модулей.

Особенности:
- Валидация всех настроек при загрузке
- Поддержка разных режимов (dev, test, production)
- Конфигурация для всех модулей ПЛАНОВ 1-4
- WebApp интеграция настройки
- Безопасная работа с API ключами ИИ
"""

import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

from utils.logger import get_logger


@dataclass
class DatabaseConfig:
    """Конфигурация базы данных"""
    url: str
    pool_size: int = 5
    pool_timeout: int = 30
    max_retries: int = 3
    created_date: Optional[str] = None
    force_recreate_tables: bool = False
    allow_data_loss_recovery: bool = False


@dataclass  
class TelegramConfig:
    """Конфигурация Telegram бота"""
    bot_token: str
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    webhook_max_connections: int = 40
    polling_interval: int = 1
    polling_timeout: int = 20
    request_timeout: int = 30


@dataclass
class WebAppConfig:
    """Конфигурация WebApp"""
    url: str
    short_name: str
    external_url: str
    analytics_enabled: bool = True
    session_timeout: int = 3600  # 1 час


@dataclass
class KarmaConfig:
    """Конфигурация системы кармы"""
    # Звания
    newbie_min: int = 0
    newbie_max: int = 5
    hope_min: int = 6
    hope_max: int = 15
    mega_min: int = 16
    mega_max: int = 30
    ambassador_min: int = 31
    
    # Настройки кармы
    admin_karma: int = 100500
    min_message_length: int = 10
    max_karma_change: int = 100500
    cooldown_seconds: int = 60
    auto_karma_enabled: bool = True
    gratitude_cooldown_minutes: int = 60


@dataclass
class RateLimitConfig:
    """Конфигурация ограничений частоты запросов"""
    # Обычные пользователи
    normal_cooldown: int = 20
    normal_max_hour: int = 180
    
    # Интенсивное использование
    burst_cooldown: int = 6
    burst_max_hour: int = 600
    
    # Консервативный режим
    conservative_cooldown: int = 60
    conservative_max_hour: int = 60
    
    # Администраторы
    admin_burst_cooldown: int = 3
    admin_burst_max_hour: int = 1200


@dataclass
class AIConfig:
    """Конфигурация ИИ сервисов"""
    enabled: bool = False
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 1000
    
    # API ключи (зашифрованы в БД)
    openai_key_set: bool = False
    anthropic_key_set: bool = False


@dataclass
class BackupConfig:
    """Конфигурация системы backup"""
    auto_enabled: bool = True
    check_time: str = "10:00"
    retention_days: int = 7
    max_size_mb: int = 45
    compression_level: int = 6
    encrypt: bool = False
    include_logs: bool = False
    verification_enabled: bool = True
    notifications_enabled: bool = True
    warning_days: List[int] = field(default_factory=lambda: [25, 28, 30, 44])


@dataclass
class ModuleConfig:
    """Конфигурация модуля"""
    name: str
    enabled: bool = True
    priority: int = 50
    config: Dict[str, Any] = field(default_factory=dict)


class Settings:
    """Главный класс настроек Do Presave Reminder Bot"""
    
    def __init__(self):
        """Инициализация настроек"""
        self.logger = get_logger(__name__)
        
        # Основные настройки
        self.debug = self._get_bool("DEBUG", False)
        self.test_mode = self._get_bool("TEST_MODE", False)
        self.development_mode = self._get_bool("DEVELOPMENT_MODE", False)
        
        # ID группы и админов
        self.group_id = self._get_int("GROUP_ID", required=True)
        self.admin_ids = self._parse_admin_ids()
        
        # Настройки планов разработки
        self.plan2_enabled = self._get_bool("ENABLE_PLAN_2_FEATURES", False)
        self.plan3_enabled = self._get_bool("ENABLE_PLAN_3_FEATURES", False)
        self.plan4_enabled = self._get_bool("ENABLE_PLAN_4_FEATURES", False)
        
        # Загрузка конфигураций
        self._load_configurations()
        
        # Валидация настроек
        self._validate_settings()
        
        self.logger.info("✅ Настройки успешно загружены")
        
    def _load_configurations(self):
        """Загрузка всех конфигураций"""
        
        # База данных
        self.database = DatabaseConfig(
            url=os.getenv("DATABASE_URL", ""),
            pool_size=self._get_int("DB_POOL_SIZE", 5),
            created_date=os.getenv("DATABASE_CREATED_DATE"),
            force_recreate_tables=self._get_bool("FORCE_RECREATE_TABLES", False),
            allow_data_loss_recovery=self._get_bool("ALLOW_DATA_LOSS_RECOVERY", False)
        )
        
        # Telegram
        self.telegram = TelegramConfig(
            bot_token=os.getenv("BOT_TOKEN", ""),
            webhook_secret=os.getenv("WEBHOOK_SECRET"),
            webhook_max_connections=self._get_int("WEBHOOK_MAX_CONNECTIONS", 40),
            polling_interval=self._get_int("POLLING_INTERVAL", 1),
            polling_timeout=self._get_int("POLLING_TIMEOUT", 20),
            request_timeout=self._get_int("REQUEST_TIMEOUT", 30)
        )
        
        # WebApp
        self.webapp = WebAppConfig(
            url=os.getenv("WEBAPP_URL", ""),
            short_name=os.getenv("WEBAPP_SHORT_NAME", "about25"),
            external_url=os.getenv("RENDER_EXTERNAL_URL", ""),
            analytics_enabled=True
        )
        
        # Карма
        self.karma = KarmaConfig(
            newbie_min=self._get_int("RANK_NEWBIE_MIN", 0),
            newbie_max=self._get_int("RANK_NEWBIE_MAX", 5),
            hope_min=self._get_int("RANK_HOPE_MIN", 6),
            hope_max=self._get_int("RANK_HOPE_MAX", 15),
            mega_min=self._get_int("RANK_MEGA_MIN", 16),
            mega_max=self._get_int("RANK_MEGA_MAX", 30),
            ambassador_min=self._get_int("RANK_AMBASSADOR_MIN", 31),
            admin_karma=self._get_int("ADMIN_KARMA", 100500),
            min_message_length=self._get_int("MIN_MESSAGE_LENGTH_FOR_KARMA", 10),
            max_karma_change=self._get_int("MAX_KARMA_CHANGE_PER_COMMAND", 100500),
            cooldown_seconds=self._get_int("KARMA_COOLDOWN_SECONDS", 60),
            auto_karma_enabled=self._get_bool("ENABLE_AUTO_KARMA", True),
            gratitude_cooldown_minutes=self._get_int("GRATITUDE_COOLDOWN_MINUTES", 60)
        )
        
        # Rate limiting
        self.rate_limit = RateLimitConfig(
            normal_cooldown=self._get_int("NORMAL_COOLDOWN", 20),
            normal_max_hour=self._get_int("NORMAL_MAX_HOUR", 180),
            burst_cooldown=self._get_int("BURST_COOLDOWN", 6),
            burst_max_hour=self._get_int("BURST_MAX_HOUR", 600),
            conservative_cooldown=self._get_int("CONSERVATIVE_COOLDOWN", 60),
            conservative_max_hour=self._get_int("CONSERVATIVE_MAX_HOUR", 60),
            admin_burst_cooldown=self._get_int("ADMIN_BURST_COOLDOWN", 3),
            admin_burst_max_hour=self._get_int("ADMIN_BURST_MAX_HOUR", 1200)
        )
        
        # ИИ (ПЛАН 4)
        self.ai = AIConfig(
            enabled=self._get_bool("AI_ENABLED", False),
            model=os.getenv("AI_MODEL", "gpt-3.5-turbo"),
            temperature=self._get_float("AI_TEMPERATURE", 0.7),
            max_tokens=self._get_int("AI_MAX_TOKENS", 1000),
            openai_key_set=bool(os.getenv("OPENAI_API_KEY", "").strip()),
            anthropic_key_set=bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
        )
        
        # Backup (ПЛАН 3)
        self.backup = BackupConfig(
            auto_enabled=self._get_bool("AUTO_BACKUP_ENABLED", True),
            check_time=os.getenv("BACKUP_CHECK_TIME", "10:00"),
            retention_days=self._get_int("BACKUP_RETENTION_DAYS", 7),
            max_size_mb=self._get_int("BACKUP_MAX_SIZE_MB", 45),
            compression_level=self._get_int("BACKUP_COMPRESSION_LEVEL", 6),
            encrypt=self._get_bool("BACKUP_ENCRYPT", False),
            include_logs=self._get_bool("BACKUP_INCLUDE_LOGS", False),
            verification_enabled=self._get_bool("BACKUP_VERIFICATION_ENABLED", True),
            notifications_enabled=self._get_bool("BACKUP_NOTIFICATIONS_ENABLED", True),
            warning_days=self._parse_int_list("BACKUP_WARNING_DAYS", [25, 28, 30, 44])
        )
        
        # Модули
        self._load_module_configs()
    
    def _load_module_configs(self):
        """Загрузка конфигураций модулей"""
        self.modules: Dict[str, ModuleConfig] = {}
        
        # ПЛАН 1 модули (всегда включены)
        plan1_modules = [
            ("user_management", 1),
            ("track_support_system", 10),
            ("karma_system", 10),
            ("navigation_system", 50),
            ("module_settings", 1)
        ]
        
        # ПЛАН 2 модули
        plan2_modules = [
            ("interactive_forms", 50),
            ("leaderboards", 50)
        ]
        
        # ПЛАН 3 модули
        plan3_modules = [
            ("approval_system", 30),
            ("database_management", 20)
        ]
        
        # ПЛАН 4 модули
        plan4_modules = [
            ("ai_assistant", 100),
            ("ai_settings", 100),
            ("calendar_system", 100),
            ("canva_integration", 100)
        ]
        
        # Загружаем модули по планам
        all_modules = plan1_modules
        if self.plan2_enabled:
            all_modules.extend(plan2_modules)
        if self.plan3_enabled:
            all_modules.extend(plan3_modules)
        if self.plan4_enabled:
            all_modules.extend(plan4_modules)
        
        for module_name, default_priority in all_modules:
            self.modules[module_name] = ModuleConfig(
                name=module_name,
                enabled=self._get_bool(f"{module_name.upper()}_ENABLED", True),
                priority=default_priority,
                config=self._get_module_specific_config(module_name)
            )
    
    def _get_module_specific_config(self, module_name: str) -> Dict[str, Any]:
        """Получение специфичной конфигурации модуля"""
        config = {}
        
        if module_name == "interactive_forms":
            config.update({
                "enabled": self._get_bool("FORMS_ENABLED", False),
                "timeout_minutes": self._get_int("FORM_TIMEOUT_MINUTES", 30)
            })
        
        elif module_name == "approval_system":
            config.update({
                "max_screenshots": self._get_int("MAX_SCREENSHOTS_PER_CLAIM", 5),
                "screenshot_max_size_mb": self._get_int("SCREENSHOT_MAX_SIZE_MB", 10)
            })
        
        elif module_name == "ai_assistant":
            config.update({
                "enabled": self.ai.enabled,
                "model": self.ai.model,
                "temperature": self.ai.temperature,
                "max_tokens": self.ai.max_tokens
            })
        
        return config
    
    def _parse_admin_ids(self) -> List[int]:
        """Парсинг ID администраторов"""
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        if not admin_ids_str:
            return []
        
        try:
            return [int(id_str.strip()) for id_str in admin_ids_str.split(",") if id_str.strip()]
        except ValueError as e:
            self.logger.error(f"Ошибка парсинга ADMIN_IDS: {e}")
            return []
    
    def _parse_int_list(self, env_var: str, default: List[int]) -> List[int]:
        """Парсинг списка целых чисел из переменной окружения"""
        value = os.getenv(env_var, "")
        if not value:
            return default
        
        try:
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        except ValueError:
            self.logger.warning(f"Неверный формат {env_var}, используем значение по умолчанию")
            return default
    
    def _get_int(self, key: str, default: int = 0, required: bool = False) -> int:
        """Получение целого числа из переменной окружения"""
        value = os.getenv(key)
        if value is None:
            if required:
                raise ValueError(f"Обязательная переменная {key} не установлена")
            return default
        
        try:
            return int(value)
        except ValueError:
            self.logger.warning(f"Неверное значение {key}={value}, используем {default}")
            return default
    
    def _get_float(self, key: str, default: float = 0.0) -> float:
        """Получение числа с плавающей точкой из переменной окружения"""
        value = os.getenv(key)
        if value is None:
            return default
        
        try:
            return float(value)
        except ValueError:
            self.logger.warning(f"Неверное значение {key}={value}, используем {default}")
            return default
    
    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Получение булевого значения из переменной окружения"""
        value = os.getenv(key, "").lower()
        if value in ("true", "1", "yes", "on"):
            return True
        elif value in ("false", "0", "no", "off"):
            return False
        else:
            return default
    
    def _validate_settings(self):
        """Валидация всех настроек"""
        errors = []
        
        # Проверяем обязательные настройки
        if not self.database.url:
            errors.append("DATABASE_URL не установлен")
        
        if not self.telegram.bot_token:
            errors.append("BOT_TOKEN не установлен")
        
        if not self.webapp.url:
            errors.append("WEBAPP_URL не установлен")
        
        if not self.admin_ids:
            errors.append("ADMIN_IDS не установлен или пуст")
        
        # Проверяем карму
        if self.karma.admin_karma > 100500:
            errors.append("ADMIN_KARMA не может быть больше 100500")
        
        if errors:
            error_msg = "Ошибки конфигурации:\n" + "\n".join(f"- {error}" for error in errors)
            self.logger.error(error_msg)
            raise ValueError(error_msg)
    
    # === ПУБЛИЧНЫЕ МЕТОДЫ ===
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        return user_id in self.admin_ids
    
    def is_module_enabled(self, module_name: str) -> bool:
        """Проверка, включен ли модуль"""
        module = self.modules.get(module_name)
        return module.enabled if module else False
    
    def get_module_config(self, module_name: str) -> Dict[str, Any]:
        """Получение конфигурации модуля"""
        module = self.modules.get(module_name)
        return module.config if module else {}
    
    def get_karma_rank_title(self, karma: int) -> str:
        """Получение звания по карме"""
        if karma >= self.karma.ambassador_min:
            return "Амбассадорище"
        elif karma >= self.karma.mega_min:
            return "Мега-помощничье"
        elif karma >= self.karma.hope_min:
            return "Надежда сообщества"
        else:
            return "Новенький"
    
    def get_rate_limit_config(self, user_id: int) -> tuple[int, int]:
        """Получение настроек rate limiting для пользователя"""
        if self.is_admin(user_id):
            return self.rate_limit.admin_burst_cooldown, self.rate_limit.admin_burst_max_hour
        else:
            return self.rate_limit.normal_cooldown, self.rate_limit.normal_max_hour
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование настроек в словарь для логирования"""
        return {
            "debug": self.debug,
            "test_mode": self.test_mode,
            "development_mode": self.development_mode,
            "group_id": self.group_id,
            "admin_count": len(self.admin_ids),
            "plan2_enabled": self.plan2_enabled,
            "plan3_enabled": self.plan3_enabled,
            "plan4_enabled": self.plan4_enabled,
            "modules_enabled": [name for name, config in self.modules.items() if config.enabled],
            "webapp_url": self.webapp.url,
            "database_configured": bool(self.database.url),
            "telegram_configured": bool(self.telegram.bot_token)
        }