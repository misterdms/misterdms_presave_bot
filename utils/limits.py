"""
🎛️ API Limits Manager - Do Presave Reminder Bot v25+
Управление 4 режимами лимитов API для стабильной работы с Telegram

РЕЖИМЫ ЛИМИТОВ:
- Conservative: 60 запросов/час, cooldown 60с (для проблемных периодов)
- Normal: 180 запросов/час, cooldown 20с (обычный режим)  
- Burst: 600 запросов/час, cooldown 6с (активный режим по умолчанию)
- Admin Burst: 1200 запросов/час, cooldown 3с (для админских операций)
"""

import os
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from enum import Enum

from config import config
from utils.logger import get_logger
from utils.helpers import MessageFormatter
from database.manager import get_database_manager

logger = get_logger(__name__)

class LimitMode(Enum):
    """Режимы лимитов API"""
    CONSERVATIVE = "conservative"
    NORMAL = "normal"
    BURST = "burst"
    ADMIN_BURST = "admin_burst"

@dataclass
class LimitConfig:
    """Конфигурация лимитов для режима"""
    mode: LimitMode
    max_requests_per_hour: int
    cooldown_seconds: int
    description: str
    emoji: str
    recommended_for: str

class RateLimitTracker:
    """Трекер использования API запросов"""
    
    def __init__(self):
        self.requests_history: List[datetime] = []
        self.last_request_time: Optional[datetime] = None
        self.total_requests = 0
        self.lock = threading.Lock()
    
    def add_request(self):
        """Добавление нового запроса в историю"""
        with self.lock:
            now = datetime.now(timezone.utc)
            self.requests_history.append(now)
            self.last_request_time = now
            self.total_requests += 1
            
            # Очистка старых запросов (старше часа)
            cutoff_time = now - timedelta(hours=1)
            self.requests_history = [
                req_time for req_time in self.requests_history 
                if req_time > cutoff_time
            ]
    
    def get_requests_last_hour(self) -> int:
        """Получение количества запросов за последний час"""
        with self.lock:
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=1)
            return len([
                req_time for req_time in self.requests_history 
                if req_time > cutoff_time
            ])
    
    def get_requests_last_minute(self) -> int:
        """Получение количества запросов за последнюю минуту"""
        with self.lock:
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(minutes=1)
            return len([
                req_time for req_time in self.requests_history 
                if req_time > cutoff_time
            ])
    
    def time_since_last_request(self) -> float:
        """Время с последнего запроса в секундах"""
        if self.last_request_time is None:
            return float('inf')
        
        now = datetime.now(timezone.utc)
        return (now - self.last_request_time).total_seconds()
    
    def reset_stats(self):
        """Сброс статистики"""
        with self.lock:
            self.requests_history = []
            self.last_request_time = None

class LimitManager:
    """Центральный менеджер лимитов API"""
    
    def __init__(self):
        """Инициализация менеджера лимитов"""
        self.current_mode = LimitMode.BURST  # По умолчанию BURST
        self.rate_tracker = RateLimitTracker()
        self.lock = threading.Lock()
        
        # Загрузка конфигураций лимитов
        self.limit_configs = self._load_limit_configs()
        
        # Загрузка сохраненного режима из БД
        self._load_saved_mode()
        
        logger.info(f"🎛️ LimitManager инициализирован в режиме {self.current_mode.value}")
        self._log_current_config()
    
    def _load_limit_configs(self) -> Dict[LimitMode, LimitConfig]:
        """Загрузка конфигураций лимитов из environment variables"""
        
        configs = {
            LimitMode.CONSERVATIVE: LimitConfig(
                mode=LimitMode.CONSERVATIVE,
                max_requests_per_hour=config.CONSERVATIVE_MAX_HOUR,
                cooldown_seconds=config.CONSERVATIVE_COOLDOWN,
                description="Консервативный режим",
                emoji="🐌",
                recommended_for="При проблемах с API или высокой нагрузке"
            ),
            LimitMode.NORMAL: LimitConfig(
                mode=LimitMode.NORMAL,
                max_requests_per_hour=config.NORMAL_MAX_HOUR,
                cooldown_seconds=config.NORMAL_COOLDOWN,
                description="Обычный режим",
                emoji="🚶",
                recommended_for="Стандартная работа в обычное время"
            ),
            LimitMode.BURST: LimitConfig(
                mode=LimitMode.BURST,
                max_requests_per_hour=config.BURST_MAX_HOUR,
                cooldown_seconds=config.BURST_COOLDOWN,
                description="Активный режим",
                emoji="🏃",
                recommended_for="Активные периоды, быстрые ответы"
            ),
            LimitMode.ADMIN_BURST: LimitConfig(
                mode=LimitMode.ADMIN_BURST,
                max_requests_per_hour=config.ADMIN_BURST_MAX_HOUR,
                cooldown_seconds=config.ADMIN_BURST_COOLDOWN,
                description="Админский турбо-режим",
                emoji="🚀",
                recommended_for="Админские операции и экстренные ситуации"
            )
        }
        
        logger.info("✅ Конфигурации лимитов загружены из environment variables")
        return configs
    
    def _load_saved_mode(self):
        """Загрузка сохраненного режима из базы данных"""
        try:
            db = get_database_manager()
            saved_mode = db.get_setting('current_limit_mode')
            
            if saved_mode and saved_mode in [mode.value for mode in LimitMode]:
                self.current_mode = LimitMode(saved_mode)
                logger.info(f"📂 Загружен сохраненный режим: {self.current_mode.value}")
            else:
                logger.info(f"📂 Режим не найден в БД, используем BURST по умолчанию")
                self._save_current_mode()
                
        except Exception as e:
            logger.warning(f"⚠️ Не удалось загрузить режим из БД: {e}")
            logger.info("📂 Используем BURST режим по умолчанию")
    
    def _save_current_mode(self):
        """Сохранение текущего режима в базу данных"""
        try:
            db = get_database_manager()
            db.set_setting('current_limit_mode', self.current_mode.value)
            logger.debug(f"💾 Режим {self.current_mode.value} сохранен в БД")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения режима: {e}")
    
    def _log_current_config(self):
        """Логирование текущей конфигурации"""
        config = self.get_current_config()
        logger.info(f"🎛️ Активный режим: {config.emoji} {config.description}")
        logger.info(f"📊 Лимиты: {config.max_requests_per_hour}/час, cooldown {config.cooldown_seconds}с")
    
    def get_current_mode(self) -> LimitMode:
        """Получение текущего режима лимитов"""
        return self.current_mode
    
    def get_current_config(self) -> LimitConfig:
        """Получение текущей конфигурации лимитов"""
        return self.limit_configs[self.current_mode]
    
    def set_mode(self, new_mode: LimitMode, save_to_db: bool = True) -> bool:
        """
        Установка нового режима лимитов
        
        Args:
            new_mode: Новый режим лимитов
            save_to_db: Сохранить ли в базу данных
            
        Returns:
            bool: Успешность операции
        """
        try:
            with self.lock:
                old_mode = self.current_mode
                self.current_mode = new_mode
                
                if save_to_db:
                    self._save_current_mode()
                
                logger.info(f"🔄 Режим изменен: {old_mode.value} → {new_mode.value}")
                self._log_current_config()
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка смены режима: {e}")
            return False
    
    def set_mode_by_name(self, mode_name: str, save_to_db: bool = True) -> bool:
        """
        Установка режима по имени
        
        Args:
            mode_name: Имя режима (conservative, normal, burst, admin_burst)
            save_to_db: Сохранить ли в базу данных
            
        Returns:
            bool: Успешность операции
        """
        try:
            new_mode = LimitMode(mode_name.lower())
            return self.set_mode(new_mode, save_to_db)
        except ValueError:
            logger.error(f"❌ Неизвестный режим: {mode_name}")
            return False
    
    def can_make_request(self, force: bool = False) -> bool:
        """
        Проверка возможности выполнения API запроса
        
        Args:
            force: Принудительно разрешить запрос (для критических операций)
            
        Returns:
            bool: Можно ли выполнить запрос
        """
        if force:
            return True
        
        config = self.get_current_config()
        
        # Проверка лимита на час
        requests_last_hour = self.rate_tracker.get_requests_last_hour()
        if requests_last_hour >= config.max_requests_per_hour:
            logger.warning(f"⚠️ Превышен часовой лимит: {requests_last_hour}/{config.max_requests_per_hour}")
            return False
        
        # Проверка cooldown
        time_since_last = self.rate_tracker.time_since_last_request()
        if time_since_last < config.cooldown_seconds:
            logger.debug(f"⏱️ Cooldown активен: осталось {config.cooldown_seconds - time_since_last:.1f}с")
            return False
        
        return True
    
    def wait_for_cooldown(self) -> float:
        """
        Ожидание завершения cooldown
        
        Returns:
            float: Время ожидания в секундах
        """
        config = self.get_current_config()
        time_since_last = self.rate_tracker.time_since_last_request()
        
        if time_since_last >= config.cooldown_seconds:
            return 0.0
        
        wait_time = config.cooldown_seconds - time_since_last
        logger.debug(f"⏱️ Ожидание cooldown: {wait_time:.1f}с")
        time.sleep(wait_time)
        
        return wait_time
    
    def register_request(self):
        """Регистрация выполненного API запроса"""
        self.rate_tracker.add_request()
        
        # Логирование каждый 10-й запрос
        if self.rate_tracker.total_requests % 10 == 0:
            stats = self.get_usage_stats()
            logger.debug(f"📊 API Stats: {stats['requests_last_hour']}/час, total: {stats['total_requests']}")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Получение статистики использования API
        
        Returns:
            Dict: Статистика использования
        """
        config = self.get_current_config()
        
        return {
            'current_mode': self.current_mode.value,
            'mode_description': config.description,
            'mode_emoji': config.emoji,
            'max_requests_per_hour': config.max_requests_per_hour,
            'cooldown_seconds': config.cooldown_seconds,
            'requests_last_hour': self.rate_tracker.get_requests_last_hour(),
            'requests_last_minute': self.rate_tracker.get_requests_last_minute(),
            'total_requests': self.rate_tracker.total_requests,
            'time_since_last_request': round(self.rate_tracker.time_since_last_request(), 1),
            'can_make_request': self.can_make_request(),
            'usage_percentage': round(
                (self.rate_tracker.get_requests_last_hour() / config.max_requests_per_hour) * 100, 1
            )
        }
    
    def get_formatted_stats(self) -> str:
        """
        Получение отформатированной статистики для отображения
        
        Returns:
            str: Форматированная статистика
        """
        stats = self.get_usage_stats()
        
        usage_bar = self._create_usage_bar(stats['usage_percentage'])
        
        return f"""🎛️ **РЕЖИМ ЛИМИТОВ API**

{stats['mode_emoji']} **Текущий режим:** {stats['mode_description']}

📊 **Использование:**
{usage_bar}
• За час: {stats['requests_last_hour']}/{stats['max_requests_per_hour']} ({stats['usage_percentage']}%)
• За минуту: {stats['requests_last_minute']}
• Всего: {stats['total_requests']} запросов

⏱️ **Параметры:**
• Cooldown: {stats['cooldown_seconds']}с
• Время с последнего запроса: {stats['time_since_last_request']}с
• Можно делать запрос: {'✅ Да' if stats['can_make_request'] else '❌ Нет'}"""
    
    def _create_usage_bar(self, percentage: float) -> str:
        """Создание визуального индикатора использования"""
        bar_length = 10
        filled_length = int(bar_length * percentage // 100)
        
        if percentage < 50:
            bar_char = "🟢"
        elif percentage < 80:
            bar_char = "🟡"
        else:
            bar_char = "🔴"
        
        bar = bar_char * filled_length + "⚪" * (bar_length - filled_length)
        return f"{bar} {percentage}%"
    
    def reload_from_config(self):
        """Перезагрузка конфигураций из environment variables"""
        logger.info("🔄 Перезагрузка конфигураций лимитов...")
        
        try:
            old_configs = self.limit_configs.copy()
            self.limit_configs = self._load_limit_configs()
            
            # Проверка на изменения
            current_config = self.get_current_config()
            old_config = old_configs.get(self.current_mode)
            
            if old_config and (
                old_config.max_requests_per_hour != current_config.max_requests_per_hour or
                old_config.cooldown_seconds != current_config.cooldown_seconds
            ):
                logger.info("📊 Обнаружены изменения в конфигурации лимитов")
                self._log_current_config()
            
            logger.info("✅ Конфигурации успешно перезагружены")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка перезагрузки конфигураций: {e}")
            return False
    
    def get_mode_recommendations(self) -> Dict[str, str]:
        """Получение рекомендаций по использованию режимов"""
        recommendations = {}
        
        for mode, config in self.limit_configs.items():
            recommendations[mode.value] = f"{config.emoji} {config.description}: {config.recommended_for}"
        
        return recommendations
    
    def auto_adjust_mode(self) -> Optional[LimitMode]:
        """
        Автоматическая подстройка режима на основе нагрузки
        
        Returns:
            Optional[LimitMode]: Рекомендуемый режим или None если изменений не нужно
        """
        stats = self.get_usage_stats()
        current_usage = stats['usage_percentage']
        
        # Логика автоподстройки
        if current_usage > 90 and self.current_mode != LimitMode.CONSERVATIVE:
            # При высокой нагрузке - переход на консервативный режим
            return LimitMode.CONSERVATIVE
        elif current_usage < 30 and self.current_mode == LimitMode.CONSERVATIVE:
            # При низкой нагрузке - переход на обычный режим
            return LimitMode.NORMAL
        elif current_usage < 10 and self.current_mode == LimitMode.NORMAL:
            # При очень низкой нагрузке - переход на burst режим
            return LimitMode.BURST
        
        return None
    
    def reset_stats(self):
        """Сброс статистики использования"""
        logger.info("🧹 Сброс статистики использования API")
        self.rate_tracker.reset_stats()

# ============================================
# ДЕКОРАТОРЫ ДЛЯ КОНТРОЛЯ ЛИМИТОВ
# ============================================

def rate_limit(force: bool = False, auto_wait: bool = True):
    """
    Декоратор для контроля лимитов API запросов
    
    Args:
        force: Принудительно выполнить запрос
        auto_wait: Автоматически ждать завершения cooldown
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            manager = get_limit_manager()
            
            # Проверка возможности выполнения запроса
            if not manager.can_make_request(force=force):
                if auto_wait:
                    manager.wait_for_cooldown()
                else:
                    logger.warning(f"⚠️ Запрос {func.__name__} заблокирован лимитами")
                    return None
            
            # Выполнение запроса
            try:
                result = func(*args, **kwargs)
                manager.register_request()
                return result
            except Exception as e:
                logger.error(f"❌ Ошибка в {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator

def critical_request(func):
    """Декоратор для критических запросов (игнорирует лимиты)"""
    return rate_limit(force=True, auto_wait=False)(func)

# ============================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ
# ============================================

# Глобальный экземпляр менеджера
_limit_manager: Optional[LimitManager] = None

def get_limit_manager() -> LimitManager:
    """Получение глобального экземпляра менеджера лимитов"""
    global _limit_manager
    
    if _limit_manager is None:
        _limit_manager = LimitManager()
    
    return _limit_manager

def init_limit_manager() -> LimitManager:
    """Инициализация глобального менеджера лимитов"""
    global _limit_manager
    
    _limit_manager = LimitManager()
    logger.info("✅ Глобальный LimitManager инициализирован")
    
    return _limit_manager

def get_current_mode() -> LimitMode:
    """Получение текущего режима лимитов"""
    return get_limit_manager().get_current_mode()

def set_mode(mode: LimitMode) -> bool:
    """Установка режима лимитов"""
    return get_limit_manager().set_mode(mode)

def set_mode_by_name(mode_name: str) -> bool:
    """Установка режима по имени"""
    return get_limit_manager().set_mode_by_name(mode_name)

def can_make_request(force: bool = False) -> bool:
    """Проверка возможности выполнения запроса"""
    return get_limit_manager().can_make_request(force)

def register_request():
    """Регистрация выполненного запроса"""
    get_limit_manager().register_request()

def get_usage_stats() -> Dict[str, Any]:
    """Получение статистики использования"""
    return get_limit_manager().get_usage_stats()

def get_formatted_stats() -> str:
    """Получение отформатированной статистики"""
    return get_limit_manager().get_formatted_stats()

# ============================================
# КОМАНДЫ ДЛЯ TELEGRAM БОТА
# ============================================

def get_mode_change_commands() -> Dict[str, tuple]:
    """Получение команд для смены режима"""
    return {
        'setmode_conservative': (LimitMode.CONSERVATIVE, "Переключение на консервативный режим"),
        'setmode_normal': (LimitMode.NORMAL, "Переключение на обычный режим"),
        'setmode_burst': (LimitMode.BURST, "Переключение на активный режим"),
        'setmode_adminburst': (LimitMode.ADMIN_BURST, "Переключение на админский турбо-режим")
    }

def handle_mode_change_command(command: str) -> tuple[bool, str]:
    """
    Обработка команды смены режима
    
    Args:
        command: Команда (например, 'setmode_burst')
        
    Returns:
        tuple: (успешность, сообщение)
    """
    mode_commands = get_mode_change_commands()
    
    if command not in mode_commands:
        return False, f"❌ Неизвестная команда: /{command}"
    
    mode, description = mode_commands[command]
    
    try:
        manager = get_limit_manager()
        old_mode = manager.get_current_mode()
        
        if old_mode == mode:
            return True, f"ℹ️ Режим {mode.value} уже активен"
        
        success = manager.set_mode(mode)
        
        if success:
            config = manager.get_current_config()
            return True, f"""✅ **{description}**

{config.emoji} **Новый режим:** {config.description}
📊 **Лимиты:** {config.max_requests_per_hour}/час, cooldown {config.cooldown_seconds}с
💡 **Рекомендуется:** {config.recommended_for}"""
        else:
            return False, f"❌ Ошибка переключения на режим {mode.value}"
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки команды {command}: {e}")
        return False, f"❌ Внутренняя ошибка при смене режима"

# ============================================
# ТЕСТИРОВАНИЕ И ОТЛАДКА
# ============================================

if __name__ == "__main__":
    """Тестирование системы лимитов"""
    
    # Настройка логирования для тестирования
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    print("🧪 Тестирование LimitManager...")
    
    # Создание менеджера
    manager = LimitManager()
    
    # Тест смены режимов
    print("\n🔄 Тест смены режимов:")
    for mode in LimitMode:
        success = manager.set_mode(mode, save_to_db=False)
        print(f"  {mode.value}: {'✅' if success else '❌'}")
    
    # Тест статистики
    print("\n📊 Тест статистики:")
    stats = manager.get_usage_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Тест декораторов
    print("\n🎯 Тест декораторов:")
    
    @rate_limit()
    def test_api_call():
        return "API call successful"
    
    for i in range(3):
        result = test_api_call()
        print(f"  Запрос {i+1}: {result}")
    
    # Финальная статистика
    print("\n📈 Финальная статистика:")
    print(manager.get_formatted_stats())
    
    print("✅ Тестирование завершено")