"""
Core/interfaces.py - Интерфейсы и базовые классы
Do Presave Reminder Bot v29.07

Стандартизированные интерфейсы для модульной архитектуры
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
import functools
import logging


class ModuleStatus(Enum):
    """Статусы модулей"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ModuleInfo:
    """Информация о модуле"""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str]
    plan: int  # План разработки (1, 2, 3, 4)
    priority: int  # Приоритет загрузки (чем меньше, тем раньше)
    enabled: bool = True


class BaseModule(ABC):
    """Базовый класс для всех модулей"""
    
    def __init__(self, bot, database, config, event_dispatcher=None):
        """
        Инициализация базового модуля
        
        Args:
            bot: Экземпляр Telegram бота
            database: Ядро базы данных
            config: Конфигурация модуля
            event_dispatcher: Диспетчер событий (опционально)
        """
        self.bot = bot
        self.database = database
        self.config = config
        self.event_dispatcher = event_dispatcher
        self.logger = logging.getLogger(f"module.{self.get_name()}")
        self.status = ModuleStatus.UNLOADED
        self._tasks = []
        self._handlers = []
        self._commands = []
        
    @abstractmethod
    def get_info(self) -> ModuleInfo:
        """Получить информацию о модуле"""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Инициализация модуля"""
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """Запуск модуля"""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """Остановка модуля"""
        pass
    
    def get_name(self) -> str:
        """Получить имя модуля"""
        return self.get_info().name
    
    def get_status(self) -> ModuleStatus:
        """Получить статус модуля"""
        return self.status
    
    def is_running(self) -> bool:
        """Проверить, запущен ли модуль"""
        return self.status == ModuleStatus.RUNNING
    
    def is_enabled(self) -> bool:
        """Проверить, включен ли модуль"""
        return self.config.get('enabled', True)
    
    def register_handlers(self):
        """Регистрация обработчиков команд/сообщений"""
        pass
    
    def get_commands(self) -> List[str]:
        """Получить список команд модуля"""
        return self._commands
    
    def get_handlers(self) -> List[Any]:
        """Получить список обработчиков модуля"""
        return self._handlers
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья модуля"""
        return {
            "healthy": self.is_running(),
            "status": self.status.value,
            "last_check": time.time(),
            "name": self.get_name()
        }
    
    async def emit_event(self, event_type: str, event_data: Dict[str, Any]):
        """Отправка события через диспетчер"""
        if self.event_dispatcher:
            await self.event_dispatcher.emit(event_type, event_data)
    
    async def cleanup(self):
        """Очистка ресурсов модуля"""
        # Остановка всех задач
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._tasks.clear()
        self._handlers.clear()
        self._commands.clear()


class CommandHandler(ABC):
    """Интерфейс обработчика команд"""
    
    @abstractmethod
    def can_handle(self, command: str) -> bool:
        """Может ли обработчик обработать команду"""
        pass
    
    @abstractmethod
    async def handle(self, message, command: str) -> bool:
        """Обработать команду"""
        pass


class MessageProcessor(ABC):
    """Интерфейс процессора сообщений"""
    
    @abstractmethod
    def can_process(self, message) -> bool:
        """Может ли процессор обработать сообщение"""
        pass
    
    @abstractmethod
    async def process(self, message) -> Optional[Dict[str, Any]]:
        """Обработать сообщение"""
        pass


class WebAppHandler(ABC):
    """Интерфейс обработчика WebApp данных"""
    
    @abstractmethod
    def can_handle(self, data_type: str) -> bool:
        """Может ли обработчик обработать тип данных"""
        pass
    
    @abstractmethod
    async def handle(self, message, webapp_data: Dict[str, Any]) -> bool:
        """Обработать данные WebApp"""
        pass


class DatabaseModel(ABC):
    """Базовый класс для моделей БД"""
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        pass
    
    @abstractmethod
    def from_dict(self, data: Dict[str, Any]) -> 'DatabaseModel':
        """Создать из словаря"""
        pass


class EventListener(ABC):
    """Интерфейс слушателя событий"""
    
    @abstractmethod
    def get_event_types(self) -> List[str]:
        """Получить типы событий, которые слушает"""
        pass
    
    @abstractmethod
    async def on_event(self, event_type: str, event_data: Dict[str, Any]):
        """Обработать событие"""
        pass


class Validator(ABC):
    """Интерфейс валидатора"""
    
    @abstractmethod
    def validate(self, data: Any) -> tuple[bool, Optional[str]]:
        """
        Валидация данных
        
        Returns:
            tuple: (is_valid, error_message)
        """
        pass


class CacheProvider(ABC):
    """Интерфейс провайдера кеша"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кеша"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Установить значение в кеш"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Удалить значение из кеша"""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """Очистить кеш"""
        pass


# === ДЕКОРАТОРЫ ===

def log_execution_time(func_name: str = None):
    """Декоратор для логирования времени выполнения"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                name = func_name or func.__name__
                logging.debug(f"⏱️ {name} выполнена за {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                name = func_name or func.__name__
                logging.error(f"❌ {name} завершилась с ошибкой за {execution_time:.3f}s: {e}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                name = func_name or func.__name__
                logging.debug(f"⏱️ {name} выполнена за {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                name = func_name or func.__name__
                logging.error(f"❌ {name} завершилась с ошибкой за {execution_time:.3f}s: {e}")
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def validate_user_exists(user_id_param: str = "user_id"):
    """Декоратор для проверки существования пользователя"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Получаем user_id из параметров
            user_id = kwargs.get(user_id_param)
            if not user_id and len(args) > 1:
                # Пытаемся получить из message.from_user.id
                try:
                    user_id = args[1].from_user.id
                except (AttributeError, IndexError):
                    pass
            
            if not user_id:
                logging.warning(f"Не удалось получить user_id для {func.__name__}")
                return False
            
            # Здесь должна быть проверка существования пользователя в БД
            # Пока просто логируем
            logging.debug(f"Проверка пользователя {user_id} для {func.__name__}")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def rate_limit(calls_per_minute: int = 60, per_user: bool = True):
    """Декоратор для ограничения частоты вызовов"""
    def decorator(func):
        # Хранилище для rate limiting
        if not hasattr(func, '_rate_limit_storage'):
            func._rate_limit_storage = {}
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_time = time.time()
            
            # Определяем ключ для rate limiting
            if per_user:
                try:
                    # Пытаемся получить user_id из сообщения
                    user_id = args[1].from_user.id if len(args) > 1 else "unknown"
                    key = f"{func.__name__}:{user_id}"
                except (AttributeError, IndexError):
                    key = f"{func.__name__}:global"
            else:
                key = f"{func.__name__}:global"
            
            # Проверяем rate limit
            if key in func._rate_limit_storage:
                last_call, call_count = func._rate_limit_storage[key]
                if current_time - last_call < 60:  # В течение минуты
                    if call_count >= calls_per_minute:
                        logging.warning(f"Rate limit превышен для {key}")
                        # Возвращаем сообщение о превышении лимита
                        if len(args) > 1 and hasattr(args[1], 'reply_text'):
                            await args[1].reply_text(
                                "⏱️ Слишком много запросов. Попробуйте позже."
                            )
                        return False
                    else:
                        func._rate_limit_storage[key] = (current_time, call_count + 1)
                else:
                    # Сброс счетчика через минуту
                    func._rate_limit_storage[key] = (current_time, 1)
            else:
                func._rate_limit_storage[key] = (current_time, 1)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# === КОНСТАНТЫ ===

class EventTypes:
    """Типы событий в системе"""
    USER_REGISTERED = "user.registered"
    USER_KARMA_CHANGED = "user.karma_changed"
    USER_RANK_CHANGED = "user.rank_changed"
    TRACK_SUPPORT_REQUESTED = "track.support_requested"
    TRACK_SUPPORT_CONFIRMED = "track.support_confirmed"
    MODULE_LOADED = "module.loaded"
    MODULE_STARTED = "module.started"
    MODULE_STOPPED = "module.stopped"
    MODULE_ERROR = "module.error"
    WEBAPP_SESSION_STARTED = "webapp.session_started"
    WEBAPP_COMMAND_SENT = "webapp.command_sent"
    ADMIN_COMMAND_EXECUTED = "admin.command_executed"


class NotificationTypes:
    """Типы уведомлений"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    URGENT = "urgent"


class ModulePriorities:
    """Приоритеты загрузки модулей"""
    CRITICAL = 1      # Основные модули (user_management)
    HIGH = 10         # Важные модули (track_support, karma)
    NORMAL = 50       # Обычные модули (navigation, forms)
    LOW = 100         # Дополнительные модули (ai, canva)


class CacheKeys:
    """Ключи для кеширования"""
    USER_STATS = "user_stats:{user_id}"
    NAVIGATION_MENU = "navigation_menu:{group_id}"
    MODULE_SETTINGS = "module_settings:{module_name}"
    WEBAPP_SESSION = "webapp_session:{session_id}"
    COMMAND_COOLDOWN = "command_cooldown:{user_id}:{command}"