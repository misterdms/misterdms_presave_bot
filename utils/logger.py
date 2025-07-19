"""
Utils/logger.py - Система логирования
Do Presave Reminder Bot v29.07

Настраиваемая система логирования с поддержкой структурированных логов
"""

import logging
import logging.handlers
import os
import sys
import time
import json
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    import colorlog
    COLORLOG_AVAILABLE = True
except ImportError:
    COLORLOG_AVAILABLE = False


class StructuredFormatter(logging.Formatter):
    """Форматтер для структурированных логов"""
    
    def format(self, record):
        # Базовая информация
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Добавляем дополнительные поля если есть
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'group_id'):
            log_entry['group_id'] = record.group_id
        if hasattr(record, 'command'):
            log_entry['command'] = record.command
        if hasattr(record, 'module_name'):
            log_entry['module_name'] = record.module_name
        if hasattr(record, 'execution_time'):
            log_entry['execution_time'] = record.execution_time
        
        # Исключения
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Цветной форматтер для консоли"""
    
    def __init__(self):
        if COLORLOG_AVAILABLE:
            super().__init__()
            self.colored_formatter = colorlog.ColoredFormatter(
                fmt='%(log_color)s%(asctime)s %(levelname)-8s %(name)-20s %(message)s',
                datefmt='%H:%M:%S',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
        else:
            super().__init__(
                fmt='%(asctime)s %(levelname)-8s %(name)-20s %(message)s',
                datefmt='%H:%M:%S'
            )
    
    def format(self, record):
        if COLORLOG_AVAILABLE:
            return self.colored_formatter.format(record)
        else:
            return super().format(record)


class BotLogger:
    """Главный класс логирования для бота"""
    
    def __init__(self):
        self.loggers = {}
        self.handlers = {}
        self.log_level = logging.INFO
        self.log_format = "simple"
        self.log_dir = Path("logs")
        self.max_log_size = 10 * 1024 * 1024  # 10MB
        self.backup_count = 5
        
    def setup_logging(self, settings=None):
        """Настройка системы логирования"""
        try:
            # Получаем настройки из переменных окружения или объекта настроек
            if settings:
                self.log_level = getattr(logging, settings.config.get('log_level', 'INFO').upper())
                self.log_format = settings.config.get('log_format', 'simple')
            else:
                self.log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper())
                self.log_format = os.getenv('LOG_FORMAT', 'simple')
            
            # Создаем директорию для логов
            self.log_dir.mkdir(exist_ok=True)
            
            # Настраиваем root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(self.log_level)
            
            # Очищаем существующие handlers
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # Добавляем handlers
            self._setup_console_handler(root_logger)
            self._setup_file_handler(root_logger)
            
            # Настраиваем специальные логгеры
            self._setup_module_loggers()
            
            # Подавляем слишком болтливые библиотеки
            self._suppress_noisy_loggers()
            
            logging.info("✅ Система логирования настроена")
            logging.info(f"📊 Уровень логирования: {logging.getLevelName(self.log_level)}")
            logging.info(f"🎨 Формат логов: {self.log_format}")
            
        except Exception as e:
            print(f"❌ Ошибка настройки логирования: {e}")
            raise
    
    def _setup_console_handler(self, logger):
        """Настройка консольного handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        
        if self.log_format == "structured":
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(ColoredFormatter())
        
        logger.addHandler(console_handler)
        self.handlers['console'] = console_handler
    
    def _setup_file_handler(self, logger):
        """Настройка файлового handler"""
        try:
            # Основной лог файл
            main_log_file = self.log_dir / "presave_bot.log"
            file_handler = logging.handlers.RotatingFileHandler(
                main_log_file,
                maxBytes=self.max_log_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(self.log_level)
            
            if self.log_format == "structured":
                file_handler.setFormatter(StructuredFormatter())
            else:
                file_handler.setFormatter(logging.Formatter(
                    fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))
            
            logger.addHandler(file_handler)
            self.handlers['file'] = file_handler
            
            # Отдельный файл для ошибок
            error_log_file = self.log_dir / "errors.log"
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=self.max_log_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(logging.Formatter(
                fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s\n%(pathname)s:%(lineno)d\n',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            
            logger.addHandler(error_handler)
            self.handlers['error'] = error_handler
            
        except Exception as e:
            print(f"⚠️ Не удалось настроить файловые логи: {e}")
    
    def _setup_module_loggers(self):
        """Настройка логгеров для модулей"""
        # Модули с отдельными лог файлами
        special_modules = {
            'module.user_management': 'user_management.log',
            'module.track_support': 'track_support.log',
            'module.karma_system': 'karma_system.log',
            'webapp': 'webapp.log',
            'database': 'database.log',
            'telegram_api': 'telegram.log'
        }
        
        for module_name, log_file in special_modules.items():
            try:
                module_logger = logging.getLogger(module_name)
                
                # Файловый handler для модуля
                log_path = self.log_dir / log_file
                module_handler = logging.handlers.RotatingFileHandler(
                    log_path,
                    maxBytes=5 * 1024 * 1024,  # 5MB для модулей
                    backupCount=3,
                    encoding='utf-8'
                )
                module_handler.setLevel(logging.DEBUG)
                module_handler.setFormatter(logging.Formatter(
                    fmt='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))
                
                module_logger.addHandler(module_handler)
                module_logger.propagate = True  # Также отправляем в основные логи
                
                self.handlers[f'module_{module_name}'] = module_handler
                
            except Exception as e:
                logging.warning(f"⚠️ Не удалось настроить логгер для {module_name}: {e}")
    
    def _suppress_noisy_loggers(self):
        """Подавление слишком болтливых библиотек"""
        noisy_loggers = [
            'urllib3.connectionpool',
            'requests.packages.urllib3.connectionpool',
            'asyncio',
            'telebot.async_telebot',
            'sqlalchemy.engine',
            'sqlalchemy.pool',
            'aiohttp.access'
        ]
        
        for logger_name in noisy_loggers:
            logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Получение логгера с именем"""
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]
    
    def get_module_logger(self, module_name: str) -> logging.Logger:
        """Получение логгера для модуля"""
        logger_name = f"module.{module_name}"
        return self.get_logger(logger_name)


# Глобальный экземпляр
_bot_logger = BotLogger()


def setup_logging(settings=None):
    """Публичная функция для настройки логирования"""
    _bot_logger.setup_logging(settings)


def get_logger(name: str = None) -> logging.Logger:
    """Получение логгера"""
    if name is None:
        name = __name__
    return _bot_logger.get_logger(name)


def get_module_logger(module_name: str) -> logging.Logger:
    """Получение логгера для модуля"""
    return _bot_logger.get_module_logger(module_name)


# === СПЕЦИАЛЬНЫЕ ФУНКЦИИ ЛОГИРОВАНИЯ ===

def log_user_action(user_id: int, action: str, details: Optional[Dict[str, Any]] = None, logger_name: str = "user_actions"):
    """Логирование действий пользователя"""
    logger = get_logger(logger_name)
    
    extra = {
        'user_id': user_id,
        'action': action
    }
    
    if details:
        extra.update(details)
    
    message = f"User {user_id} performed action: {action}"
    if details:
        message += f" | Details: {details}"
    
    logger.info(message, extra=extra)


def log_command_execution(user_id: int, command: str, execution_time: float = None, success: bool = True, error: str = None):
    """Логирование выполнения команд"""
    logger = get_logger("commands")
    
    extra = {
        'user_id': user_id,
        'command': command,
        'success': success
    }
    
    if execution_time is not None:
        extra['execution_time'] = execution_time
    
    if success:
        message = f"Command /{command} executed successfully by user {user_id}"
        if execution_time:
            message += f" in {execution_time:.3f}s"
        logger.info(message, extra=extra)
    else:
        message = f"Command /{command} failed for user {user_id}"
        if error:
            message += f": {error}"
        logger.error(message, extra=extra)


def log_module_activity(module_name: str, activity: str, details: Optional[Dict[str, Any]] = None):
    """Логирование активности модулей"""
    logger = get_module_logger(module_name)
    
    extra = {
        'module_name': module_name,
        'activity': activity
    }
    
    if details:
        extra.update(details)
    
    message = f"Module {module_name}: {activity}"
    if details:
        message += f" | {details}"
    
    logger.info(message, extra=extra)


def log_webapp_interaction(user_id: int, action: str, data: Optional[Dict[str, Any]] = None):
    """Логирование взаимодействий с WebApp"""
    logger = get_logger("webapp")
    
    extra = {
        'user_id': user_id,
        'webapp_action': action
    }
    
    if data:
        extra['webapp_data'] = data
    
    message = f"WebApp interaction from user {user_id}: {action}"
    if data:
        message += f" | Data: {data}"
    
    logger.info(message, extra=extra)


def log_database_operation(operation: str, table: str = None, execution_time: float = None, success: bool = True, error: str = None):
    """Логирование операций с базой данных"""
    logger = get_logger("database")
    
    extra = {
        'db_operation': operation,
        'success': success
    }
    
    if table:
        extra['table'] = table
    if execution_time is not None:
        extra['execution_time'] = execution_time
    
    if success:
        message = f"DB operation {operation}"
        if table:
            message += f" on {table}"
        if execution_time:
            message += f" completed in {execution_time:.3f}s"
        logger.debug(message, extra=extra)
    else:
        message = f"DB operation {operation} failed"
        if table:
            message += f" on {table}"
        if error:
            message += f": {error}"
        logger.error(message, extra=extra)


def log_performance_metric(metric_name: str, value: float, unit: str = "ms", context: Optional[Dict[str, Any]] = None):
    """Логирование метрик производительности"""
    if not os.getenv("ENABLE_PERFORMANCE_LOGS", "false").lower() == "true":
        return
    
    logger = get_logger("performance")
    
    extra = {
        'metric_name': metric_name,
        'metric_value': value,
        'metric_unit': unit
    }
    
    if context:
        extra['context'] = context
    
    message = f"Performance metric {metric_name}: {value}{unit}"
    if context:
        message += f" | Context: {context}"
    
    logger.info(message, extra=extra)


# === КОНТЕКСТНЫЕ МЕНЕДЖЕРЫ ===

class LogExecutionTime:
    """Контекстный менеджер для логирования времени выполнения"""
    
    def __init__(self, operation_name: str, logger_name: str = None, log_level: int = logging.INFO):
        self.operation_name = operation_name
        self.logger = get_logger(logger_name or __name__)
        self.log_level = log_level
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time
        
        if exc_type is None:
            self.logger.log(
                self.log_level,
                f"✅ {self.operation_name} completed in {execution_time:.3f}s",
                extra={'execution_time': execution_time, 'operation': self.operation_name}
            )
        else:
            self.logger.error(
                f"❌ {self.operation_name} failed after {execution_time:.3f}s: {exc_val}",
                extra={'execution_time': execution_time, 'operation': self.operation_name}
            )


# === УТИЛИТЫ ===

def get_log_stats() -> Dict[str, Any]:
    """Получение статистики логирования"""
    try:
        stats = {
            "log_level": logging.getLevelName(_bot_logger.log_level),
            "log_format": _bot_logger.log_format,
            "handlers_count": len(_bot_logger.handlers),
            "loggers_count": len(_bot_logger.loggers),
            "log_directory": str(_bot_logger.log_dir),
            "colorlog_available": COLORLOG_AVAILABLE
        }
        
        # Размеры лог файлов
        if _bot_logger.log_dir.exists():
            log_files = {}
            for log_file in _bot_logger.log_dir.glob("*.log"):
                try:
                    size = log_file.stat().st_size
                    log_files[log_file.name] = {
                        "size_bytes": size,
                        "size_mb": round(size / 1024 / 1024, 2)
                    }
                except OSError:
                    pass
            stats["log_files"] = log_files
        
        return stats
        
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # Тестирование системы логирования
    print("🧪 Тестирование системы логирования...")
    
    # Настраиваем логирование
    setup_logging()
    
    # Тестируем разные типы логов
    logger = get_logger("test")
    
    logger.debug("🔍 Debug сообщение")
    logger.info("ℹ️ Info сообщение")
    logger.warning("⚠️ Warning сообщение")
    logger.error("❌ Error сообщение")
    
    # Тестируем специальные функции
    log_user_action(12345, "test_action", {"test": "data"})
    log_command_execution(12345, "test", 0.123, True)
    log_module_activity("test_module", "test_activity", {"key": "value"})
    
    # Тестируем контекстный менеджер
    with LogExecutionTime("test_operation"):
        time.sleep(0.1)
    
    # Показываем статистику
    stats = get_log_stats()
    print(f"📊 Статистика логирования: {json.dumps(stats, indent=2, ensure_ascii=False)}")
    
    print("✅ Тестирование завершено")