"""
Core/exceptions.py - Кастомные исключения
Do Presave Reminder Bot v29.07

Иерархия исключений для типизированной обработки ошибок
"""

from typing import Optional, Dict, Any


class BotException(Exception):
    """Базовое исключение для всех ошибок бота"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, 
                 error_code: Optional[str] = None):
        """
        Инициализация базового исключения
        
        Args:
            message: Сообщение об ошибке
            details: Дополнительные детали ошибки
            error_code: Код ошибки для классификации
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = error_code or self.__class__.__name__
        
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование исключения в словарь"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


# === ИНИЦИАЛИЗАЦИЯ И КОНФИГУРАЦИЯ ===

class BotInitializationError(BotException):
    """Ошибка инициализации бота"""
    pass


class ConfigurationError(BotException):
    """Ошибка конфигурации"""
    pass


class EnvironmentError(BotException):
    """Ошибка переменных окружения"""
    pass


# === БАЗА ДАННЫХ ===

class DatabaseError(BotException):
    """Базовая ошибка базы данных"""
    pass


class DatabaseConnectionError(DatabaseError):
    """Ошибка подключения к базе данных"""
    pass


class DatabaseOperationError(DatabaseError):
    """Ошибка операции с базой данных"""
    pass


class DatabaseMigrationError(DatabaseError):
    """Ошибка миграции базы данных"""
    pass


class DatabaseIntegrityError(DatabaseError):
    """Ошибка целостности данных"""
    pass


# === МОДУЛИ ===

class ModuleError(BotException):
    """Базовая ошибка модуля"""
    
    def __init__(self, message: str, module_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.module_name = module_name


class ModuleLoadError(ModuleError):
    """Ошибка загрузки модуля"""
    pass


class ModuleNotFoundError(ModuleError):
    """Модуль не найден"""
    pass


class ModuleDependencyError(ModuleError):
    """Ошибка зависимостей модуля"""
    pass


class ModuleInitializationError(ModuleError):
    """Ошибка инициализации модуля"""
    pass


class ModuleRuntimeError(ModuleError):
    """Ошибка выполнения модуля"""
    pass


# === TELEGRAM API ===

class TelegramError(BotException):
    """Базовая ошибка Telegram API"""
    pass


class TelegramConnectionError(TelegramError):
    """Ошибка подключения к Telegram API"""
    pass


class TelegramRateLimitError(TelegramError):
    """Превышение лимитов Telegram API"""
    pass


class TelegramBadRequestError(TelegramError):
    """Неверный запрос к Telegram API"""
    pass


class TelegramUnauthorizedError(TelegramError):
    """Ошибка авторизации в Telegram API"""
    pass


# === ПОЛЬЗОВАТЕЛИ И КАРМА ===

class UserError(BotException):
    """Базовая ошибка пользователя"""
    
    def __init__(self, message: str, user_id: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.user_id = user_id


class UserNotFoundError(UserError):
    """Пользователь не найден"""
    pass


class UserAlreadyExistsError(UserError):
    """Пользователь уже существует"""
    pass


class UserPermissionError(UserError):
    """Недостаточно прав пользователя"""
    pass


class KarmaError(UserError):
    """Ошибка системы кармы"""
    pass


class KarmaLimitError(KarmaError):
    """Превышение лимитов кармы"""
    pass


class KarmaCalculationError(KarmaError):
    """Ошибка расчета кармы"""
    pass


# === WEBAPP ===

class WebAppError(BotException):
    """Базовая ошибка WebApp"""
    pass


class WebAppDataError(WebAppError):
    """Ошибка данных WebApp"""
    pass


class WebAppSessionError(WebAppError):
    """Ошибка сессии WebApp"""
    pass


class WebAppIntegrationError(WebAppError):
    """Ошибка интеграции WebApp"""
    pass


# === ВАЛИДАЦИЯ ===

class ValidationError(BotException):
    """Ошибка валидации"""
    
    def __init__(self, message: str, field: Optional[str] = None, 
                 value: Any = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value


class InvalidInputError(ValidationError):
    """Неверные входные данные"""
    pass


class InvalidCommandError(ValidationError):
    """Неверная команда"""
    pass


class InvalidFileError(ValidationError):
    """Неверный файл"""
    pass


# === ВНЕШНИЕ СЕРВИСЫ ===

class ExternalServiceError(BotException):
    """Базовая ошибка внешнего сервиса"""
    
    def __init__(self, message: str, service_name: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.service_name = service_name


class AIServiceError(ExternalServiceError):
    """Ошибка ИИ сервиса"""
    pass


class AIQuotaExceededError(AIServiceError):
    """Превышение квоты ИИ сервиса"""
    pass


class AIInvalidKeyError(AIServiceError):
    """Неверный API ключ ИИ сервиса"""
    pass


class CanvaServiceError(ExternalServiceError):
    """Ошибка сервиса Canva"""
    pass


class N8nServiceError(ExternalServiceError):
    """Ошибка сервиса n8n"""
    pass


# === БЕЗОПАСНОСТЬ ===

class SecurityError(BotException):
    """Базовая ошибка безопасности"""
    pass


class AccessDeniedError(SecurityError):
    """Доступ запрещен"""
    pass


class RateLimitExceededError(SecurityError):
    """Превышение лимита запросов"""
    
    def __init__(self, message: str, user_id: Optional[int] = None, 
                 limit: Optional[int] = None, window: Optional[int] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.user_id = user_id
        self.limit = limit
        self.window = window


class SpamDetectedError(SecurityError):
    """Обнаружен спам"""
    pass


class SuspiciousActivityError(SecurityError):
    """Подозрительная активность"""
    pass


# === СИСТЕМА ФОРМ ===

class FormError(BotException):
    """Базовая ошибка форм"""
    pass


class FormNotFoundError(FormError):
    """Форма не найдена"""
    pass


class FormTimeoutError(FormError):
    """Истек срок действия формы"""
    pass


class FormValidationError(FormError):
    """Ошибка валидации формы"""
    pass


# === ФАЙЛЫ И МЕДИА ===

class FileError(BotException):
    """Базовая ошибка работы с файлами"""
    pass


class FileSizeError(FileError):
    """Превышение размера файла"""
    pass


class FileTypeError(FileError):
    """Неподдерживаемый тип файла"""
    pass


class FileProcessingError(FileError):
    """Ошибка обработки файла"""
    pass


# === СИСТЕМА СОБЫТИЙ ===

class EventError(BotException):
    """Базовая ошибка системы событий"""
    pass


class EventDispatchError(EventError):
    """Ошибка отправки события"""
    pass


class EventHandlerError(EventError):
    """Ошибка обработчика события"""
    pass


# === BACKUP И ВОССТАНОВЛЕНИЕ ===

class BackupError(BotException):
    """Базовая ошибка backup"""
    pass


class BackupCreationError(BackupError):
    """Ошибка создания backup"""
    pass


class BackupRestoreError(BackupError):
    """Ошибка восстановления backup"""
    pass


class BackupCorruptedError(BackupError):
    """Поврежденный backup"""
    pass


# === УТИЛИТАРНЫЕ ФУНКЦИИ ===

def handle_exception(exception: Exception) -> BotException:
    """
    Преобразование стандартного исключения в BotException
    
    Args:
        exception: Исходное исключение
        
    Returns:
        BotException: Типизированное исключение бота
    """
    if isinstance(exception, BotException):
        return exception
    
    # Маппинг стандартных исключений
    exception_map = {
        ConnectionError: DatabaseConnectionError,
        TimeoutError: DatabaseOperationError,
        ValueError: ValidationError,
        TypeError: ValidationError,
        KeyError: InvalidInputError,
        FileNotFoundError: FileError,
        PermissionError: AccessDeniedError,
        OSError: FileError
    }
    
    exception_class = exception_map.get(type(exception), BotException)
    return exception_class(
        message=str(exception),
        details={"original_exception": type(exception).__name__}
    )


def get_user_friendly_message(exception: BotException) -> str:
    """
    Получение понятного пользователю сообщения об ошибке
    
    Args:
        exception: Исключение бота
        
    Returns:
        str: Сообщение для пользователя
    """
    user_messages = {
        # База данных
        DatabaseConnectionError: "🔌 Временные проблемы с базой данных. Попробуйте позже.",
        DatabaseOperationError: "💾 Ошибка сохранения данных. Попробуйте повторить операцию.",
        
        # Пользователи
        UserNotFoundError: "👤 Пользователь не найден. Возможно, нужна регистрация.",
        UserPermissionError: "🚫 Недостаточно прав для выполнения действия.",
        
        # Карма
        KarmaLimitError: "⚖️ Достигнут лимит изменения кармы. Попробуйте позже.",
        
        # Валидация
        ValidationError: "❌ Проверьте правильность введенных данных.",
        InvalidCommandError: "⚠️ Неверная команда. Используйте /help для справки.",
        
        # Rate limiting
        RateLimitExceededError: "⏱️ Слишком много запросов. Подождите немного.",
        
        # Файлы
        FileSizeError: "📁 Файл слишком большой. Максимальный размер: 10MB.",
        FileTypeError: "📎 Неподдерживаемый тип файла.",
        
        # Формы
        FormTimeoutError: "⏰ Время заполнения формы истекло. Начните заново.",
        
        # Внешние сервисы
        AIServiceError: "🤖 Сервис ИИ временно недоступен.",
        AIQuotaExceededError: "💳 Исчерпана квота ИИ сервиса. Обратитесь к администратору.",
        
        # WebApp
        WebAppDataError: "📱 Ошибка данных WebApp. Обновите страницу.",
        
        # Модули
        ModuleError: "🧩 Ошибка модуля. Обратитесь к администратору."
    }
    
    # Пытаемся найти точное соответствие
    message = user_messages.get(type(exception))
    if message:
        return message
    
    # Ищем по родительским классам
    for exception_type, user_message in user_messages.items():
        if isinstance(exception, exception_type):
            return user_message
    
    # Общее сообщение
    return "❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору."


def log_exception(exception: BotException, logger, context: Optional[Dict[str, Any]] = None):
    """
    Логирование исключения с контекстом
    
    Args:
        exception: Исключение для логирования
        logger: Логгер
        context: Дополнительный контекст
    """
    log_data = exception.to_dict()
    if context:
        log_data["context"] = context
    
    # Определяем уровень логирования
    if isinstance(exception, (ValidationError, UserPermissionError, RateLimitExceededError)):
        logger.warning(f"⚠️ {exception.message}", extra=log_data)
    elif isinstance(exception, (DatabaseError, ModuleError, TelegramError)):
        logger.error(f"❌ {exception.message}", extra=log_data)
    elif isinstance(exception, (SecurityError, BackupError)):
        logger.critical(f"🚨 {exception.message}", extra=log_data)
    else:
        logger.info(f"ℹ️ {exception.message}", extra=log_data)


if __name__ == "__main__":
    # Тестирование исключений
    print("🧪 Тестирование системы исключений...")
    
    # Тестируем создание исключений
    try:
        raise UserNotFoundError("Пользователь не найден", user_id=12345, details={"action": "get_profile"})
    except BotException as e:
        print(f"📋 Исключение: {e.to_dict()}")
        print(f"👤 Сообщение для пользователя: {get_user_friendly_message(e)}")
    
    # Тестируем преобразование стандартных исключений
    try:
        raise ValueError("Неверное значение")
    except Exception as e:
        bot_exception = handle_exception(e)
        print(f"🔄 Преобразованное исключение: {bot_exception.to_dict()}")
    
    # Тестируем вложенные исключения
    try:
        raise KarmaLimitError(
            "Превышен лимит кармы",
            user_id=67890,
            details={"current_karma": 5, "attempted_change": 10, "daily_limit": 5}
        )
    except KarmaError as e:
        print(f"⚖️ Ошибка кармы: {e.to_dict()}")
    
    print("✅ Тестирование завершено")