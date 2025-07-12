"""
Система логирования Do Presave Reminder Bot v25+
Структурированное логирование с эмодзи для всех планов развития
"""

import logging
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any

# Настройка цветного вывода (если доступен colorama)
try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

class EmojiFormatter(logging.Formatter):
    """Форматтер логов с эмодзи"""
    
    # Эмодзи для разных уровней логирования
    EMOJI_MAP = {
        'DEBUG': '🔍',
        'INFO': '✅',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    # Цвета для уровней (если colorama доступен)
    COLOR_MAP = {
        'DEBUG': Fore.CYAN if COLORAMA_AVAILABLE else '',
        'INFO': Fore.GREEN if COLORAMA_AVAILABLE else '',
        'WARNING': Fore.YELLOW if COLORAMA_AVAILABLE else '',
        'ERROR': Fore.RED if COLORAMA_AVAILABLE else '',
        'CRITICAL': Fore.RED + Style.BRIGHT if COLORAMA_AVAILABLE else ''
    }
    
    def __init__(self, include_timestamp=True, include_module=True):
        """Инициализация форматтера"""
        self.include_timestamp = include_timestamp
        self.include_module = include_module
        super().__init__()
    
    def format(self, record):
        """Форматирование записи лога"""
        # Получаем эмодзи и цвет для уровня
        emoji = self.EMOJI_MAP.get(record.levelname, '📝')
        color = self.COLOR_MAP.get(record.levelname, '')
        
        # Формируем части сообщения
        parts = []
        
        # Временная метка
        if self.include_timestamp:
            timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
            parts.append(f"[{timestamp}]")
        
        # Эмодзи и уровень
        if COLORAMA_AVAILABLE and color:
            level_part = f"{color}{emoji} {record.levelname}{Style.RESET_ALL}"
        else:
            level_part = f"{emoji} {record.levelname}"
        parts.append(level_part)
        
        # Модуль (если включен)
        if self.include_module and hasattr(record, 'name'):
            module_name = record.name.split('.')[-1]  # Только последняя часть
            parts.append(f"[{module_name}]")
        
        # Основное сообщение
        message = record.getMessage()
        parts.append(message)
        
        # Собираем все вместе
        formatted_message = " ".join(parts)
        
        # Добавляем исключение если есть
        if record.exc_info:
            formatted_message += "\n" + self.formatException(record.exc_info)
        
        return formatted_message


class StructuredLogger:
    """Структурированный логгер с дополнительными возможностями"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def set_context(self, **kwargs):
        """Установка контекста для логирования"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Очистка контекста"""
        self.context.clear()
    
    def _format_message(self, message: str, extra: Optional[Dict[str, Any]] = None) -> str:
        """Форматирование сообщения с контекстом"""
        if not self.context and not extra:
            return message
        
        # Объединяем контекст и дополнительные данные
        full_context = {**self.context}
        if extra:
            full_context.update(extra)
        
        # Добавляем контекст к сообщению
        if full_context:
            context_str = " | ".join([f"{k}={v}" for k, v in full_context.items()])
            return f"{message} | {context_str}"
        
        return message
    
    def debug(self, message: str, **extra):
        """Отладочное сообщение"""
        self.logger.debug(self._format_message(message, extra))
    
    def info(self, message: str, **extra):
        """Информационное сообщение"""
        self.logger.info(self._format_message(message, extra))
    
    def warning(self, message: str, **extra):
        """Предупреждение"""
        self.logger.warning(self._format_message(message, extra))
    
    def error(self, message: str, **extra):
        """Ошибка"""
        self.logger.error(self._format_message(message, extra))
    
    def critical(self, message: str, **extra):
        """Критическая ошибка"""
        self.logger.critical(self._format_message(message, extra))
    
    def exception(self, message: str, **extra):
        """Ошибка с исключением"""
        self.logger.exception(self._format_message(message, extra))


def setup_logging(level: str = None, log_format: str = None):
    """Настройка системы логирования"""
    
    # Получаем настройки из переменных окружения
    if level is None:
        level = os.getenv('LOG_LEVEL', 'INFO')
    if log_format is None:
        log_format = os.getenv('LOG_FORMAT', 'structured')
    
    # Преобразуем уровень
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Создаем форматтер
    if log_format.lower() == 'structured':
        formatter = EmojiFormatter(include_timestamp=True, include_module=True)
    else:
        # Простой форматтер без эмодзи
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    
    # Настраиваем root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Удаляем существующие handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Создаем handler для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    
    # Добавляем handler
    root_logger.addHandler(console_handler)
    
    # Настраиваем уровни для сторонних библиотек
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telebot').setLevel(logging.WARNING)
    
    # ПЛАН 3: Настройки для ИИ библиотек (ЗАГЛУШКИ)
    # logging.getLogger('openai').setLevel(logging.WARNING)
    # logging.getLogger('anthropic').setLevel(logging.WARNING)
    
    print(f"✅ Логирование настроено: уровень {level}, формат {log_format}")


def get_logger(name: str) -> StructuredLogger:
    """Получение структурированного логгера"""
    return StructuredLogger(name)


class LoggerContextManager:
    """Контекстный менеджер для логирования с дополнительным контекстом"""
    
    def __init__(self, logger: StructuredLogger, **context):
        self.logger = logger
        self.context = context
        self.old_context = None
    
    def __enter__(self):
        # Сохраняем старый контекст
        self.old_context = self.logger.context.copy()
        # Устанавливаем новый контекст
        self.logger.set_context(**self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Восстанавливаем старый контекст
        self.logger.context = self.old_context


# Специализированные логгеры для разных модулей

def log_user_action(logger: StructuredLogger, user_id: int, action: str, **extra):
    """Логирование действия пользователя"""
    logger.info(f"Пользователь {user_id}: {action}", user_id=user_id, action=action, **extra)

def log_admin_action(logger: StructuredLogger, admin_id: int, action: str, target: str = None, **extra):
    """Логирование действия администратора"""
    context = {'admin_id': admin_id, 'action': action}
    if target:
        context['target'] = target
    context.update(extra)
    
    logger.info(f"Админ {admin_id}: {action}" + (f" → {target}" if target else ""), **context)

def log_api_call(logger: StructuredLogger, method: str, endpoint: str, status: str, **extra):
    """Логирование API вызова"""
    logger.info(f"API {method} {endpoint}: {status}", 
                method=method, endpoint=endpoint, status=status, **extra)

def log_database_operation(logger: StructuredLogger, operation: str, table: str, count: int = None, **extra):
    """Логирование операции с базой данных"""
    context = {'operation': operation, 'table': table}
    if count is not None:
        context['count'] = count
    context.update(extra)
    
    count_str = f" ({count} записей)" if count is not None else ""
    logger.info(f"БД {operation} в {table}{count_str}", **context)

# ПЛАН 2: Логирование кармы (ЗАГЛУШКИ)
# def log_karma_change(logger: StructuredLogger, user_id: int, admin_id: int, 
#                      old_karma: int, new_karma: int, reason: str = None):
#     """Логирование изменения кармы"""
#     change = new_karma - old_karma
#     change_str = f"+{change}" if change > 0 else str(change)
#     
#     logger.info(f"Карма изменена: пользователь {user_id} {old_karma}→{new_karma} ({change_str})",
#                 user_id=user_id, admin_id=admin_id, old_karma=old_karma, 
#                 new_karma=new_karma, change=change, reason=reason)

# ПЛАН 3: Логирование ИИ (ЗАГЛУШКИ)
# def log_ai_interaction(logger: StructuredLogger, user_id: int, model: str, 
#                        prompt_tokens: int, completion_tokens: int, **extra):
#     """Логирование взаимодействия с ИИ"""
#     total_tokens = prompt_tokens + completion_tokens
#     logger.info(f"ИИ взаимодействие: пользователь {user_id}, модель {model}, токенов {total_tokens}",
#                 user_id=user_id, model=model, prompt_tokens=prompt_tokens,
#                 completion_tokens=completion_tokens, total_tokens=total_tokens, **extra)

# def log_gratitude_detection(logger: StructuredLogger, from_user: int, to_user: int, 
#                            trigger_word: str, karma_added: int):
#     """Логирование автоматического начисления кармы за благодарность"""
#     logger.info(f"Автокарма: {from_user}→{to_user} +{karma_added} за '{trigger_word}'",
#                 from_user=from_user, to_user=to_user, trigger_word=trigger_word, karma_added=karma_added)

# ПЛАН 4: Логирование backup (ЗАГЛУШКИ)
# def log_backup_operation(logger: StructuredLogger, operation: str, filename: str = None, 
#                          size_mb: float = None, duration_seconds: float = None, **extra):
#     """Логирование операций backup"""
#     context = {'operation': operation}
#     if filename:
#         context['filename'] = filename
#     if size_mb:
#         context['size_mb'] = round(size_mb, 2)
#     if duration_seconds:
#         context['duration_seconds'] = round(duration_seconds, 2)
#     context.update(extra)
#     
#     size_str = f" ({size_mb:.1f}MB)" if size_mb else ""
#     duration_str = f" за {duration_seconds:.1f}с" if duration_seconds else ""
#     
#     logger.info(f"Backup {operation}: {filename or 'неизвестно'}{size_str}{duration_str}", **context)


# Утилита для измерения производительности
class PerformanceLogger:
    """Логгер производительности"""
    
    def __init__(self, logger: StructuredLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        if os.getenv('ENABLE_PERFORMANCE_LOGS', 'false').lower() == 'true':
            from time import perf_counter
            self.start_time = perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            from time import perf_counter
            duration = perf_counter() - self.start_time
            self.logger.info(f"Производительность: {self.operation} выполнено за {duration:.3f}с",
                            operation=self.operation, duration_seconds=duration)


if __name__ == "__main__":
    """Тестирование системы логирования"""
    
    # Настройка логирования
    setup_logging('DEBUG', 'structured')
    
    # Создание тестового логгера
    logger = get_logger('test')
    
    # Тестирование разных уровней
    logger.debug("Это отладочное сообщение")
    logger.info("Это информационное сообщение")
    logger.warning("Это предупреждение")
    logger.error("Это ошибка")
    logger.critical("Это критическая ошибка")
    
    # Тестирование с контекстом
    logger.set_context(user_id=12345, action="test")
    logger.info("Сообщение с контекстом")
    
    # Тестирование контекстного менеджера
    with LoggerContextManager(logger, session_id="test_session", module="testing"):
        logger.info("Сообщение в контексте сессии")
    
    # Тестирование специализированных функций
    log_user_action(logger, 12345, "отправил команду /start")
    log_admin_action(logger, 67890, "изменил настройки", target="лимиты API")
    
    # Тестирование производительности
    with PerformanceLogger(logger, "тестовая операция"):
        import time
        time.sleep(0.1)
    
    print("✅ Тестирование логирования завершено")