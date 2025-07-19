"""
Config/env_loader.py - Загрузчик переменных окружения
Do Presave Reminder Bot v29.07

Безопасная загрузка и валидация переменных окружения с обработкой ошибок
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import sys

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logging.warning("python-dotenv не установлен, используем только системные переменные")


class EnvironmentLoader:
    """Загрузчик переменных окружения с валидацией"""
    
    def __init__(self):
        self.loaded_files = []
        self.missing_variables = []
        self.environment_type = "unknown"
        
    def load_environment(self, env_file: Optional[str] = None) -> bool:
        """
        Загрузка переменных окружения
        
        Args:
            env_file: Путь к .env файлу (опционально)
            
        Returns:
            bool: Успешность загрузки
        """
        try:
            # Определяем тип окружения
            self._detect_environment()
            
            # Загружаем .env файлы если доступны
            if DOTENV_AVAILABLE:
                self._load_dotenv_files(env_file)
            
            # Проверяем критически важные переменные
            if not self._validate_critical_variables():
                return False
            
            # Устанавливаем значения по умолчанию
            self._set_defaults()
            
            logging.info(f"✅ Переменные окружения загружены ({self.environment_type})")
            return True
            
        except Exception as e:
            logging.error(f"❌ Ошибка загрузки переменных окружения: {e}")
            return False
    
    def _detect_environment(self):
        """Определение типа окружения"""
        if os.getenv("RENDER"):
            self.environment_type = "render.com"
        elif os.getenv("HEROKU"):
            self.environment_type = "heroku"
        elif os.getenv("DOCKER"):
            self.environment_type = "docker"
        elif os.getenv("DEVELOPMENT_MODE", "").lower() == "true":
            self.environment_type = "development"
        elif os.getenv("TEST_MODE", "").lower() == "true":
            self.environment_type = "testing"
        else:
            self.environment_type = "production"
        
        logging.info(f"🔍 Обнаружено окружение: {self.environment_type}")
    
    def _load_dotenv_files(self, custom_env_file: Optional[str] = None):
        """Загрузка .env файлов по приоритету"""
        env_files = []
        
        # Пользовательский файл (наивысший приоритет)
        if custom_env_file and Path(custom_env_file).exists():
            env_files.append(custom_env_file)
        
        # Файлы по окружению
        env_files.extend([
            f".env.{self.environment_type}",
            ".env.local", 
            ".env"
        ])
        
        # Загружаем файлы по порядку
        for env_file in env_files:
            if Path(env_file).exists():
                try:
                    load_dotenv(env_file, override=False)  # Не перезаписываем уже установленные
                    self.loaded_files.append(env_file)
                    logging.info(f"📄 Загружен {env_file}")
                except Exception as e:
                    logging.warning(f"⚠️ Ошибка загрузки {env_file}: {e}")
    
    def _validate_critical_variables(self) -> bool:
        """Проверка критически важных переменных"""
        critical_vars = [
            "BOT_TOKEN",
            "DATABASE_URL",
            "GROUP_ID"
        ]
        
        missing = []
        for var in critical_vars:
            value = os.getenv(var)
            if not value or value.strip() == "":
                missing.append(var)
        
        if missing:
            self.missing_variables = missing
            logging.error(f"❌ Отсутствуют критические переменные: {', '.join(missing)}")
            self._print_setup_instructions(missing)
            return False
        
        return True
    
    def _set_defaults(self):
        """Установка значений по умолчанию для необязательных переменных"""
        defaults = {
            # Система
            "DEBUG": "false",
            "TEST_MODE": "false", 
            "DEVELOPMENT_MODE": "false",
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "structured",
            
            # База данных
            "DB_POOL_SIZE": "5",
            "FORCE_RECREATE_TABLES": "false",
            "ALLOW_DATA_LOSS_RECOVERY": "false",
            
            # WebApp
            "WEBAPP_SHORT_NAME": "about25",
            
            # Карма и звания
            "ADMIN_KARMA": "100500",
            "RANK_NEWBIE_MIN": "0",
            "RANK_NEWBIE_MAX": "5",
            "RANK_HOPE_MIN": "6", 
            "RANK_HOPE_MAX": "15",
            "RANK_MEGA_MIN": "16",
            "RANK_MEGA_MAX": "30",
            "RANK_AMBASSADOR_MIN": "31",
            
            # Rate limiting
            "NORMAL_COOLDOWN": "20",
            "NORMAL_MAX_HOUR": "180",
            "BURST_COOLDOWN": "6",
            "BURST_MAX_HOUR": "600",
            "CONSERVATIVE_COOLDOWN": "60",
            "CONSERVATIVE_MAX_HOUR": "60",
            "ADMIN_BURST_COOLDOWN": "3",
            "ADMIN_BURST_MAX_HOUR": "1200",
            
            # Планы разработки
            "ENABLE_PLAN_2_FEATURES": "false",
            "ENABLE_PLAN_3_FEATURES": "false", 
            "ENABLE_PLAN_4_FEATURES": "false",
            
            # ИИ сервисы
            "AI_ENABLED": "false",
            "AI_MODEL": "gpt-3.5-turbo",
            "AI_TEMPERATURE": "0.7",
            "AI_MAX_TOKENS": "1000",
            "OPENAI_API_KEY": "not_specified_yet",
            "ANTHROPIC_API_KEY": "not_specified_yet",
            
            # Backup
            "AUTO_BACKUP_ENABLED": "true",
            "BACKUP_CHECK_TIME": "10:00",
            "BACKUP_RETENTION_DAYS": "7",
            "BACKUP_MAX_SIZE_MB": "45",
            "BACKUP_COMPRESSION_LEVEL": "6",
            "BACKUP_ENCRYPT": "false",
            "BACKUP_INCLUDE_LOGS": "false",
            "BACKUP_VERIFICATION_ENABLED": "true",
            "BACKUP_NOTIFICATIONS_ENABLED": "true",
            "BACKUP_WARNING_DAYS": "25,28,30,44",
            
            # Формы
            "FORMS_ENABLED": "false",
            "FORM_TIMEOUT_MINUTES": "30",
            
            # Модерация
            "MAX_SCREENSHOTS_PER_CLAIM": "5",
            "SCREENSHOT_MAX_SIZE_MB": "10",
            
            # Сеть
            "HOST": "0.0.0.0",
            "REQUEST_TIMEOUT": "30",
            "RESPONSE_DELAY": "3",
            "WEBHOOK_MAX_CONNECTIONS": "40",
            "POLLING_INTERVAL": "1",
            "POLLING_TIMEOUT": "20",
            
            # Производительность
            "ASYNC_WORKERS": "2",
            "MAX_CONCURRENT_OPERATIONS": "10",
            "MIGRATION_TIMEOUT_MINUTES": "15",
            
            # Keep-Alive
            "KEEPALIVE_ENABLED": "true",
            "KEEPALIVE_INTERVAL": "300",
            
            # Мониторинг
            "ERROR_REPORTING": "true",
            "METRICS_COLLECTION": "true",
            "HEALTH_CHECK_ENABLED": "true",
            "ENABLE_PERFORMANCE_LOGS": "true",
            
            # Карма система
            "MIN_MESSAGE_LENGTH_FOR_KARMA": "10",
            "MAX_KARMA_CHANGE_PER_COMMAND": "100500",
            "KARMA_COOLDOWN_SECONDS": "60",
            "ENABLE_AUTO_KARMA": "true",
            "GRATITUDE_COOLDOWN_MINUTES": "60",
            
            # Безопасность
            "WHITELIST": "3",
            "CORRELATION_ID_HEADER": "X-Request-ID",
            
            # Напоминания
            "REMINDER_TEXT": "🎧 Напоминаем: не забудь сделать пресейв артистов выше! ♥️ Для твоего удобства нажми /last10links"
        }
        
        set_count = 0
        for key, default_value in defaults.items():
            if os.getenv(key) is None:
                os.environ[key] = default_value
                set_count += 1
        
        if set_count > 0:
            logging.info(f"⚙️ Установлено {set_count} значений по умолчанию")
    
    def _print_setup_instructions(self, missing_vars: list):
        """Инструкции по настройке переменных окружения"""
        print("\n" + "="*60)
        print("🚨 ОТСУТСТВУЮТ КРИТИЧЕСКИЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ")
        print("="*60)
        
        for var in missing_vars:
            print(f"\n❌ {var}")
            
            if var == "BOT_TOKEN":
                print("   Получите токен у @BotFather в Telegram")
                print("   Пример: 1234567890:ABCdefGHIjklMNOpqrsTUVwxy")
                
            elif var == "DATABASE_URL":
                print("   PostgreSQL connection string")
                print("   Пример: postgresql://user:pass@host:5432/database")
                
            elif var == "GROUP_ID":
                print("   ID вашей музыкальной супергруппы")
                print("   Пример: -1002811959953")
        
        print(f"\n📋 ВАРИАНТЫ НАСТРОЙКИ:")
        print(f"   1. Создайте файл .env в корне проекта")
        print(f"   2. Установите переменные в системе")
        print(f"   3. На Render.com используйте раздел Environment")
        
        print(f"\n📄 Пример содержимого .env:")
        for var in missing_vars:
            print(f"   {var}=ваше_значение")
        
        print("="*60)
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса загрузки"""
        return {
            "environment_type": self.environment_type,
            "loaded_files": self.loaded_files,
            "missing_variables": self.missing_variables,
            "total_env_vars": len(os.environ),
            "dotenv_available": DOTENV_AVAILABLE
        }


def load_environment(env_file: Optional[str] = None) -> bool:
    """
    Публичная функция для загрузки переменных окружения
    
    Args:
        env_file: Путь к .env файлу (опционально)
        
    Returns:
        bool: Успешность загрузки
    """
    loader = EnvironmentLoader()
    return loader.load_environment(env_file)


def validate_environment() -> tuple[bool, list]:
    """
    Валидация текущих переменных окружения
    
    Returns:
        tuple: (все_ли_переменные_есть, список_отсутствующих)
    """
    loader = EnvironmentLoader()
    
    # Проверяем критические переменные
    critical_vars = ["BOT_TOKEN", "DATABASE_URL", "GROUP_ID"]
    missing = []
    
    for var in critical_vars:
        if not os.getenv(var, "").strip():
            missing.append(var)
    
    return len(missing) == 0, missing


def get_env_info() -> Dict[str, Any]:
    """Получение информации об окружении для логирования"""
    return {
        "python_version": sys.version,
        "environment_type": os.getenv("RENDER", "local"),
        "debug_mode": os.getenv("DEBUG", "false").lower() == "true",
        "test_mode": os.getenv("TEST_MODE", "false").lower() == "true",
        "development_mode": os.getenv("DEVELOPMENT_MODE", "false").lower() == "true",
        "has_bot_token": bool(os.getenv("BOT_TOKEN", "").strip()),
        "has_database_url": bool(os.getenv("DATABASE_URL", "").strip()),
        "webapp_url": os.getenv("WEBAPP_URL", "не_установлен"),
        "total_env_vars": len(os.environ)
    }


if __name__ == "__main__":
    # Тестирование загрузчика
    print("🧪 Тестирование загрузчика переменных окружения...")
    
    success = load_environment()
    
    if success:
        print("✅ Переменные окружения загружены успешно")
        
        # Показываем информацию
        info = get_env_info()
        print("\n📊 Информация об окружении:")
        for key, value in info.items():
            print(f"   {key}: {value}")
    else:
        print("❌ Ошибка загрузки переменных окружения")
        sys.exit(1)