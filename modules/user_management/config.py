"""
Modules/user_management/config.py - Конфигурация модуля управления пользователями
Do Presave Reminder Bot v29.07

Настройки для системы кармы, званий, онбординга и валидации
"""

import os
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass


@dataclass
class KarmaConfig:
    """Конфигурация системы кармы"""
    min_karma: int = 0
    max_karma: int = 100500
    admin_karma: int = 100500
    newbie_karma: int = 0
    
    # Кулдауны
    karma_cooldown_seconds: int = 60
    gratitude_cooldown_minutes: int = 60
    
    # Лимиты изменений
    max_karma_change_per_command: int = 100500
    min_message_length_for_karma: int = 10
    
    # Автоматическая карма
    auto_karma_enabled: bool = True
    gratitude_karma_amount: int = 1


@dataclass
class RankConfig:
    """Конфигурация системы званий"""
    # Пороги званий (включительно)
    newbie_min: int = 0
    newbie_max: int = 5
    
    hope_min: int = 6
    hope_max: int = 15
    
    mega_min: int = 16
    mega_max: int = 30
    
    ambassador_min: int = 31
    ambassador_max: int = 100500
    
    # Названия званий с эмодзи
    rank_titles: Dict[str, str] = None
    
    def __post_init__(self):
        if self.rank_titles is None:
            self.rank_titles = {
                'newbie': '🥉 Новенький',
                'hope': '🥈 Надежда сообщества', 
                'mega': '🥇 Мега-помощничье',
                'ambassador': '💎 Амбассадорище'
            }


@dataclass
class OnboardingConfig:
    """Конфигурация процесса онбординга"""
    max_steps: int = 3
    session_timeout_minutes: int = 30
    
    # Жанры музыки для выбора
    available_genres: List[str] = None
    
    # Тексты онбординга
    welcome_text: str = "🎵 Добро пожаловать в музыкальное сообщество!"
    genre_prompt: str = "🎼 Выберите ваш основной музыкальный жанр:"
    completion_text: str = "✅ Регистрация завершена! Добро пожаловать в команду!"
    
    def __post_init__(self):
        if self.available_genres is None:
            self.available_genres = [
                'Рок', 'Поп', 'Хип-хоп', 'Рэп', 'Электронная', 'Джаз', 'Блюз',
                'Кантри', 'Фолк', 'Классическая', 'Металл', 'Панк', 'Регги',
                'R&B', 'Соул', 'Фанк', 'Диско', 'Альтернатива', 'Инди', 'Гранж',
                'Техно', 'Хаус', 'Транс', 'Дабстеп', 'Драм-н-бэйс', 'Амбиент',
                'Другое'
            ]


@dataclass
class ValidationConfig:
    """Конфигурация валидации данных"""
    max_name_length: int = 100
    min_name_length: int = 1
    max_username_length: int = 32
    min_username_length: int = 3
    max_genre_length: int = 50
    max_reason_length: int = 500
    min_reason_length: int = 3


@dataclass
class WebAppConfig:
    """Конфигурация интеграции с WebApp"""
    stats_update_interval: int = 5  # секунд
    session_timeout: int = 3600  # час
    enable_realtime_updates: bool = True
    track_visit_analytics: bool = True


class UserManagementConfig:
    """Основной класс конфигурации модуля управления пользователями"""
    
    def __init__(self, env_config: Dict[str, Any] = None):
        """
        Инициализация конфигурации
        
        Args:
            env_config: Словарь с переменными окружения
        """
        self.env_config = env_config or {}
        
        # Инициализируем конфигурации
        self.karma = self._init_karma_config()
        self.ranks = self._init_rank_config()
        self.onboarding = self._init_onboarding_config()
        self.validation = self._init_validation_config()
        self.webapp = self._init_webapp_config()
        
        # Основные настройки модуля
        self.enabled = self._get_bool('USER_MANAGEMENT_ENABLED', True)
        self.debug_mode = self._get_bool('USER_MANAGEMENT_DEBUG', False)
        self.admin_ids = self._parse_admin_ids()
        
        # Настройки производительности
        self.max_concurrent_operations = self._get_int('MAX_CONCURRENT_OPERATIONS', 10)
        self.database_pool_size = self._get_int('DB_POOL_SIZE', 5)
        
        # Логирование
        self.log_level = self._get_str('LOG_LEVEL', 'INFO')
        self.enable_performance_logs = self._get_bool('ENABLE_PERFORMANCE_LOGS', True)
    
    def _init_karma_config(self) -> KarmaConfig:
        """Инициализация конфигурации кармы"""
        return KarmaConfig(
            min_karma=self._get_int('KARMA_MIN', 0),
            max_karma=self._get_int('KARMA_MAX', 100500),
            admin_karma=self._get_int('ADMIN_KARMA', 100500),
            newbie_karma=self._get_int('NEWBIE_KARMA', 0),
            karma_cooldown_seconds=self._get_int('KARMA_COOLDOWN_SECONDS', 60),
            gratitude_cooldown_minutes=self._get_int('GRATITUDE_COOLDOWN_MINUTES', 60),
            max_karma_change_per_command=self._get_int('MAX_KARMA_CHANGE_PER_COMMAND', 100500),
            min_message_length_for_karma=self._get_int('MIN_MESSAGE_LENGTH_FOR_KARMA', 10),
            auto_karma_enabled=self._get_bool('ENABLE_AUTO_KARMA', True),
            gratitude_karma_amount=self._get_int('GRATITUDE_KARMA_AMOUNT', 1)
        )
    
    def _init_rank_config(self) -> RankConfig:
        """Инициализация конфигурации званий"""
        return RankConfig(
            newbie_min=self._get_int('RANK_NEWBIE_MIN', 0),
            newbie_max=self._get_int('RANK_NEWBIE_MAX', 5),
            hope_min=self._get_int('RANK_HOPE_MIN', 6),
            hope_max=self._get_int('RANK_HOPE_MAX', 15),
            mega_min=self._get_int('RANK_MEGA_MIN', 16),
            mega_max=self._get_int('RANK_MEGA_MAX', 30),
            ambassador_min=self._get_int('RANK_AMBASSADOR_MIN', 31),
            ambassador_max=self._get_int('RANK_AMBASSADOR_MAX', 100500)
        )
    
    def _init_onboarding_config(self) -> OnboardingConfig:
        """Инициализация конфигурации онбординга"""
        return OnboardingConfig(
            max_steps=self._get_int('ONBOARDING_MAX_STEPS', 3),
            session_timeout_minutes=self._get_int('ONBOARDING_TIMEOUT_MINUTES', 30)
        )
    
    def _init_validation_config(self) -> ValidationConfig:
        """Инициализация конфигурации валидации"""
        return ValidationConfig(
            max_name_length=self._get_int('MAX_NAME_LENGTH', 100),
            min_name_length=self._get_int('MIN_NAME_LENGTH', 1),
            max_username_length=self._get_int('MAX_USERNAME_LENGTH', 32),
            min_username_length=self._get_int('MIN_USERNAME_LENGTH', 3),
            max_genre_length=self._get_int('MAX_GENRE_LENGTH', 50),
            max_reason_length=self._get_int('MAX_REASON_LENGTH', 500),
            min_reason_length=self._get_int('MIN_REASON_LENGTH', 3)
        )
    
    def _init_webapp_config(self) -> WebAppConfig:
        """Инициализация конфигурации WebApp"""
        return WebAppConfig(
            stats_update_interval=self._get_int('WEBAPP_STATS_UPDATE_INTERVAL', 5),
            session_timeout=self._get_int('WEBAPP_SESSION_TIMEOUT', 3600),
            enable_realtime_updates=self._get_bool('WEBAPP_REALTIME_UPDATES', True),
            track_visit_analytics=self._get_bool('WEBAPP_TRACK_ANALYTICS', True)
        )
    
    def _get_str(self, key: str, default: str = "") -> str:
        """Получение строкового значения из переменных окружения"""
        return self.env_config.get(key, os.getenv(key, default))
    
    def _get_int(self, key: str, default: int = 0) -> int:
        """Получение целочисленного значения из переменных окружения"""
        value = self.env_config.get(key, os.getenv(key, str(default)))
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def _get_bool(self, key: str, default: bool = False) -> bool:
        """Получение булевого значения из переменных окружения"""
        value = self.env_config.get(key, os.getenv(key, str(default).lower()))
        if isinstance(value, bool):
            return value
        return str(value).lower() in ('true', '1', 'yes', 'on', 'enabled')
    
    def _parse_admin_ids(self) -> List[int]:
        """Парсинг ID администраторов"""
        admin_ids_str = self._get_str('ADMIN_IDS', '')
        if not admin_ids_str:
            return []
        
        try:
            return [
                int(id_str.strip()) 
                for id_str in admin_ids_str.split(',') 
                if id_str.strip().isdigit()
            ]
        except ValueError:
            return []
    
    def get_rank_by_karma(self, karma: int) -> str:
        """Получение звания по количеству кармы"""
        if karma >= self.ranks.ambassador_min:
            return self.ranks.rank_titles['ambassador']
        elif karma >= self.ranks.mega_min:
            return self.ranks.rank_titles['mega']
        elif karma >= self.ranks.hope_min:
            return self.ranks.rank_titles['hope']
        else:
            return self.ranks.rank_titles['newbie']
    
    def get_rank_info(self, karma: int) -> Dict[str, Any]:
        """Получение детальной информации о звании"""
        current_rank = self.get_rank_by_karma(karma)
        
        if karma >= self.ranks.ambassador_min:
            return {
                'title': current_rank,
                'level': 'ambassador',
                'min_karma': self.ranks.ambassador_min,
                'max_karma': self.ranks.ambassador_max,
                'next_rank': None,
                'karma_to_next': 0,
                'progress_percent': 100
            }
        elif karma >= self.ranks.mega_min:
            return {
                'title': current_rank,
                'level': 'mega',
                'min_karma': self.ranks.mega_min,
                'max_karma': self.ranks.mega_max,
                'next_rank': self.ranks.rank_titles['ambassador'],
                'karma_to_next': self.ranks.ambassador_min - karma,
                'progress_percent': ((karma - self.ranks.mega_min) / 
                                   (self.ranks.mega_max - self.ranks.mega_min)) * 100
            }
        elif karma >= self.ranks.hope_min:
            return {
                'title': current_rank,
                'level': 'hope',
                'min_karma': self.ranks.hope_min,
                'max_karma': self.ranks.hope_max,
                'next_rank': self.ranks.rank_titles['mega'],
                'karma_to_next': self.ranks.mega_min - karma,
                'progress_percent': ((karma - self.ranks.hope_min) / 
                                   (self.ranks.hope_max - self.ranks.hope_min)) * 100
            }
        else:
            return {
                'title': current_rank,
                'level': 'newbie',
                'min_karma': self.ranks.newbie_min,
                'max_karma': self.ranks.newbie_max,
                'next_rank': self.ranks.rank_titles['hope'],
                'karma_to_next': self.ranks.hope_min - karma,
                'progress_percent': (karma / self.ranks.newbie_max) * 100 if self.ranks.newbie_max > 0 else 0
            }
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь администратором"""
        return user_id in self.admin_ids
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """Валидация конфигурации модуля"""
        errors = []
        
        # Проверка границ кармы
        if self.karma.min_karma < 0:
            errors.append("Минимальная карма не может быть отрицательной")
        
        if self.karma.max_karma <= self.karma.min_karma:
            errors.append("Максимальная карма должна быть больше минимальной")
        
        if self.karma.admin_karma > self.karma.max_karma:
            errors.append("Карма администратора не может превышать максимальную карму")
        
        # Проверка званий
        rank_thresholds = [
            (self.ranks.newbie_min, self.ranks.newbie_max),
            (self.ranks.hope_min, self.ranks.hope_max),
            (self.ranks.mega_min, self.ranks.mega_max),
            (self.ranks.ambassador_min, self.ranks.ambassador_max)
        ]
        
        for i, (min_val, max_val) in enumerate(rank_thresholds):
            if min_val > max_val:
                errors.append(f"Неверные границы для звания {i+1}: мин {min_val} > макс {max_val}")
        
        # Проверка непрерывности званий
        if self.ranks.hope_min != self.ranks.newbie_max + 1:
            errors.append("Пропуск в диапазоне кармы между Новенький и Надежда сообщества")
        
        if self.ranks.mega_min != self.ranks.hope_max + 1:
            errors.append("Пропуск в диапазоне кармы между Надежда сообщества и Мега-помощничье")
        
        if self.ranks.ambassador_min != self.ranks.mega_max + 1:
            errors.append("Пропуск в диапазоне кармы между Мега-помощничье и Амбассадорище")
        
        # Проверка кулдаунов
        if self.karma.karma_cooldown_seconds < 0:
            errors.append("Кулдаун кармы не может быть отрицательным")
        
        if self.karma.gratitude_cooldown_minutes < 0:
            errors.append("Кулдаун благодарностей не может быть отрицательным")
        
        # Проверка лимитов валидации
        if self.validation.max_name_length <= self.validation.min_name_length:
            errors.append("Максимальная длина имени должна быть больше минимальной")
        
        if self.validation.max_username_length <= self.validation.min_username_length:
            errors.append("Максимальная длина username должна быть больше минимальной")
        
        return len(errors) == 0, errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация конфигурации в словарь для логирования"""
        return {
            'module': 'user_management',
            'enabled': self.enabled,
            'debug_mode': self.debug_mode,
            'admin_count': len(self.admin_ids),
            'karma': {
                'min': self.karma.min_karma,
                'max': self.karma.max_karma,
                'admin': self.karma.admin_karma,
                'auto_enabled': self.karma.auto_karma_enabled
            },
            'ranks': {
                'newbie': f"{self.ranks.newbie_min}-{self.ranks.newbie_max}",
                'hope': f"{self.ranks.hope_min}-{self.ranks.hope_max}",
                'mega': f"{self.ranks.mega_min}-{self.ranks.mega_max}",
                'ambassador': f"{self.ranks.ambassador_min}+"
            },
            'onboarding': {
                'max_steps': self.onboarding.max_steps,
                'timeout_minutes': self.onboarding.session_timeout_minutes,
                'genres_count': len(self.onboarding.available_genres)
            },
            'webapp': {
                'realtime_updates': self.webapp.enable_realtime_updates,
                'track_analytics': self.webapp.track_visit_analytics
            }
        }


# Константы для использования в модуле

# Команды модуля
COMMAND_START = 'start'
COMMAND_MYSTAT = 'mystat'
COMMAND_PROFILE = 'profile'
COMMAND_KARMA_HISTORY = 'karma_history'
COMMAND_KARMA = 'karma'
COMMAND_KARMA_RATIO = 'karma_ratio'

# События модуля
EVENT_USER_REGISTERED = 'user_registered'
EVENT_KARMA_CHANGED = 'karma_changed'
EVENT_RANK_CHANGED = 'rank_changed'
EVENT_ONBOARDING_COMPLETED = 'onboarding_completed'

# WebApp события
WEBAPP_EVENT_STATS_REQUESTED = 'webapp_stats_requested'
WEBAPP_EVENT_PROFILE_VIEWED = 'webapp_profile_viewed'
WEBAPP_EVENT_COMMAND_TRIGGERED = 'webapp_command_triggered'


if __name__ == "__main__":
    # Тестирование конфигурации
    print("🧪 Тестирование конфигурации модуля...")
    
    # Создаем конфигурацию
    config = UserManagementConfig()
    
    # Валидируем
    is_valid, errors = config.validate_config()
    print(f"⚙️ Валидация конфигурации: {'✅' if is_valid else '❌'}")
    
    if errors:
        for error in errors:
            print(f"  - {error}")
    else:
        print("  Конфигурация корректна!")
    
    # Тестируем получение званий
    test_karma_values = [0, 3, 10, 20, 50]
    print("\n🏆 Тестирование системы званий:")
    
    for karma in test_karma_values:
        rank_info = config.get_rank_info(karma)
        print(f"  Карма {karma}: {rank_info['title']}")
        if rank_info['next_rank']:
            print(f"    До следующего звания: {rank_info['karma_to_next']} кармы")
    
    # Выводим итоговую конфигурацию
    print(f"\n📊 Итоговая конфигурация:")
    config_dict = config.to_dict()
    for key, value in config_dict.items():
        print(f"  {key}: {value}")
    
    print("✅ Тестирование конфигурации завершено")
