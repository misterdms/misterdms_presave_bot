"""
💓 Keep-Alive Manager - Do Presave Reminder Bot v25+
Предотвращение "засыпания" на Render.com и других хостингах

КРИТИЧЕСКАЯ ВАЖНОСТЬ:
- Render.com приостанавливает бесплатные сервисы после бездействия
- UptimeRobot мониторит доступность и "будит" сервис
- Внутренний keep-alive дублирует проверки для надежности
"""

import asyncio
import threading
import time
import requests
import schedule
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from config import config
from utils.logger import get_logger
from utils.helpers import SystemMonitor

logger = get_logger(__name__)

class KeepAliveManager:
    """Менеджер keep-alive соединений"""
    
    def __init__(self, target_url: str, interval: int = 300, enabled: bool = True):
        """
        Инициализация keep-alive менеджера
        
        Args:
            target_url: URL для ping запросов
            interval: Интервал между запросами в секундах (по умолчанию 5 минут)
            enabled: Включен ли keep-alive
        """
        self.target_url = target_url
        self.interval = interval
        self.enabled = enabled
        self.is_running = False
        self.stop_event = threading.Event()
        
        # Статистика
        self.start_time = datetime.now(timezone.utc)
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.last_request_time = None
        self.last_request_status = None
        self.consecutive_failures = 0
        
        # Мониторинг системы
        self.system_monitor = SystemMonitor()
        
        logger.info(f"💓 KeepAliveManager инициализирован")
        logger.info(f"🎯 Target URL: {target_url}")
        logger.info(f"⏱️ Interval: {interval} секунд")
        logger.info(f"🔌 Enabled: {'Yes' if enabled else 'No'}")
        
        if not enabled:
            logger.warning("⚠️ Keep-alive отключен! Сервис может заснуть на Render.com")
    
    def ping_service(self) -> bool:
        """
        Выполнение ping запроса к сервису
        
        Returns:
            bool: True если запрос успешен, False иначе
        """
        if not self.enabled:
            return True
            
        start_time = time.time()
        
        try:
            response = requests.get(
                self.target_url,
                timeout=30,
                headers={
                    'User-Agent': 'PresaveBot-KeepAlive/1.0',
                    'X-KeepAlive': 'true',
                    'X-Request-ID': f"keepalive-{int(time.time())}"
                }
            )
            
            response_time = time.time() - start_time
            
            self.total_requests += 1
            self.last_request_time = datetime.now(timezone.utc)
            
            if response.status_code == 200:
                self.successful_requests += 1
                self.last_request_status = f"✅ 200 OK ({response_time:.2f}s)"
                self.consecutive_failures = 0
                
                logger.debug(f"💓 Keep-alive успешен: {response.status_code} за {response_time:.2f}s")
                return True
            else:
                self.failed_requests += 1
                self.last_request_status = f"⚠️ {response.status_code} ({response_time:.2f}s)"
                self.consecutive_failures += 1
                
                logger.warning(f"⚠️ Keep-alive получил {response.status_code}: {self.target_url}")
                return False
                
        except requests.exceptions.Timeout:
            self.failed_requests += 1
            self.consecutive_failures += 1
            self.last_request_status = "⏱️ Timeout"
            logger.warning(f"⏱️ Keep-alive timeout: {self.target_url}")
            return False
            
        except requests.exceptions.ConnectionError:
            self.failed_requests += 1
            self.consecutive_failures += 1
            self.last_request_status = "🔌 Connection Error"
            logger.warning(f"🔌 Keep-alive connection error: {self.target_url}")
            return False
            
        except Exception as e:
            self.failed_requests += 1
            self.consecutive_failures += 1
            self.last_request_status = f"❌ Error: {str(e)[:50]}"
            logger.error(f"❌ Keep-alive error: {e}")
            return False
    
    def keepalive_loop(self):
        """Основной цикл keep-alive"""
        logger.info(f"🔄 Запуск keep-alive цикла (интервал: {self.interval}s)")
        
        while not self.stop_event.is_set():
            try:
                # Выполняем ping
                success = self.ping_service()
                
                # Проверяем критические ситуации
                if self.consecutive_failures >= 3:
                    logger.error(f"🚨 КРИТИЧНО: {self.consecutive_failures} подряд неудачных keep-alive запросов!")
                    
                    # Попытка экстренного восстановления
                    if self.consecutive_failures >= 5:
                        logger.error("💥 ЭКСТРЕННАЯ СИТУАЦИЯ: попытка смены URL...")
                        self._try_alternative_endpoints()
                
                # Адаптивный интервал
                sleep_interval = self._calculate_adaptive_interval(success)
                
                # Ожидание до следующего запроса
                self.stop_event.wait(sleep_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в keep-alive цикле: {e}")
                self.stop_event.wait(60)  # Ждем минуту при ошибке
    
    def _calculate_adaptive_interval(self, last_success: bool) -> int:
        """
        Расчет адаптивного интервала между запросами
        
        Args:
            last_success: Был ли последний запрос успешным
            
        Returns:
            int: Интервал в секундах
        """
        base_interval = self.interval
        
        # Если есть ошибки - увеличиваем частоту
        if self.consecutive_failures > 0:
            # При ошибках пингуем чаще (но не чаще раза в минуту)
            return max(60, base_interval // (self.consecutive_failures + 1))
        
        # Если все ОК - стандартный интервал
        return base_interval
    
    def _try_alternative_endpoints(self):
        """Попытка использования альтернативных endpoints для восстановления"""
        try:
            parsed_url = urlparse(self.target_url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Пробуем альтернативные endpoints
            alternative_endpoints = [
                f"{base_url}/health",
                f"{base_url}/ping", 
                f"{base_url}/status",
                f"{base_url}/",
                self.target_url  # Возвращаемся к оригинальному
            ]
            
            for endpoint in alternative_endpoints:
                logger.info(f"🔄 Пробуем альтернативный endpoint: {endpoint}")
                
                original_url = self.target_url
                self.target_url = endpoint
                
                if self.ping_service():
                    logger.info(f"✅ Восстановление через {endpoint}")
                    return
                else:
                    self.target_url = original_url
                    
            logger.error("💥 Все альтернативные endpoints недоступны")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при попытке восстановления: {e}")
    
    def start_keepalive(self):
        """Запуск keep-alive в отдельном потоке"""
        if not self.enabled:
            logger.info("⏭️ Keep-alive отключен")
            return
            
        if self.is_running:
            logger.warning("⚠️ Keep-alive уже запущен")
            return
        
        self.is_running = True
        logger.info("🚀 Запуск keep-alive системы...")
        
        try:
            # Первый ping для проверки доступности
            initial_success = self.ping_service()
            if not initial_success:
                logger.warning("⚠️ Первоначальный ping неуспешен, но продолжаем...")
            
            # Запуск основного цикла
            self.keepalive_loop()
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска keep-alive: {e}")
        finally:
            self.is_running = False
            logger.info("🛑 Keep-alive остановлен")
    
    def stop(self):
        """Остановка keep-alive"""
        logger.info("🔄 Остановка keep-alive...")
        self.stop_event.set()
        self.is_running = False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики keep-alive
        
        Returns:
            Dict: Статистика работы
        """
        uptime = datetime.now(timezone.utc) - self.start_time
        success_rate = (self.successful_requests / max(1, self.total_requests)) * 100
        
        return {
            'enabled': self.enabled,
            'is_running': self.is_running,
            'target_url': self.target_url,
            'interval': self.interval,
            'uptime_seconds': int(uptime.total_seconds()),
            'uptime_human': str(uptime).split('.')[0],
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'success_rate': round(success_rate, 2),
            'consecutive_failures': self.consecutive_failures,
            'last_request_time': self.last_request_time.isoformat() if self.last_request_time else None,
            'last_request_status': self.last_request_status,
            'system_stats': self.system_monitor.get_system_stats() if hasattr(self, 'system_monitor') else {}
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Получение статуса здоровья keep-alive системы
        
        Returns:
            Dict: Статус здоровья
        """
        stats = self.get_stats()
        
        # Определяем статус здоровья
        if not self.enabled:
            status = "disabled"
            health = "unknown"
        elif self.consecutive_failures >= 5:
            status = "critical"
            health = "unhealthy"
        elif self.consecutive_failures >= 3:
            status = "warning" 
            health = "degraded"
        elif stats['success_rate'] < 90:
            status = "warning"
            health = "degraded"
        else:
            status = "healthy"
            health = "healthy"
        
        return {
            'status': status,
            'health': health,
            'message': self._get_health_message(status),
            'stats': stats
        }
    
    def _get_health_message(self, status: str) -> str:
        """Получение человекочитаемого сообщения о статусе"""
        messages = {
            'healthy': '✅ Keep-alive работает нормально',
            'warning': '⚠️ Keep-alive работает с проблемами',
            'critical': '🚨 Keep-alive в критическом состоянии',
            'disabled': '⏭️ Keep-alive отключен'
        }
        return messages.get(status, '❓ Неизвестный статус')

# ============================================
# ИНТЕГРАЦИЯ С SCHEDULER ДЛЯ ДОПОЛНИТЕЛЬНЫХ ПРОВЕРОК
# ============================================

class EnhancedKeepAlive(KeepAliveManager):
    """Расширенный keep-alive с дополнительными функциями"""
    
    def __init__(self, target_url: str, interval: int = 300, enabled: bool = True):
        super().__init__(target_url, interval, enabled)
        
        # Настройка планировщика для дополнительных проверок
        if enabled:
            self._setup_scheduler()
    
    def _setup_scheduler(self):
        """Настройка планировщика дополнительных проверок"""
        try:
            # Проверка каждые 10 минут
            schedule.every(10).minutes.do(self._health_check)
            
            # Ежечасный отчет
            schedule.every().hour.do(self._hourly_report)
            
            # Ежедневная очистка статистики
            schedule.every().day.at("00:00").do(self._daily_cleanup)
            
            logger.info("📅 Планировщик keep-alive настроен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка настройки планировщика: {e}")
    
    def _health_check(self):
        """Дополнительная проверка здоровья"""
        try:
            health = self.get_health_status()
            
            if health['status'] in ['critical', 'warning']:
                logger.warning(f"⚠️ Keep-alive health check: {health['message']}")
                
                # При критических проблемах - принудительный ping
                if health['status'] == 'critical':
                    logger.info("🔄 Принудительная попытка восстановления...")
                    self.ping_service()
                    
        except Exception as e:
            logger.error(f"❌ Ошибка health check: {e}")
    
    def _hourly_report(self):
        """Ежечасный отчет о работе"""
        try:
            stats = self.get_stats()
            
            if stats['total_requests'] > 0:
                logger.info(
                    f"📊 Keep-alive hourly: "
                    f"{stats['successful_requests']}/{stats['total_requests']} "
                    f"({stats['success_rate']:.1f}%) "
                    f"failures: {stats['consecutive_failures']}"
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка hourly report: {e}")
    
    def _daily_cleanup(self):
        """Ежедневная очистка старой статистики"""
        try:
            logger.info("🧹 Ежедневная очистка keep-alive статистики")
            
            # Сброс счетчиков, но сохранение основной статистики
            old_total = self.total_requests
            old_success_rate = (self.successful_requests / max(1, self.total_requests)) * 100
            
            # Частичный сброс (оставляем последние 24 часа данных)
            self.total_requests = min(288, self.total_requests)  # 288 = 24 часа * 12 (каждые 5 минут)
            self.successful_requests = int(self.total_requests * old_success_rate / 100)
            self.failed_requests = self.total_requests - self.successful_requests
            
            logger.info(f"📊 Статистика за сутки: {old_total} запросов, {old_success_rate:.1f}% успех")
            
        except Exception as e:
            logger.error(f"❌ Ошибка daily cleanup: {e}")
    
    def run_scheduled_tasks(self):
        """Запуск запланированных задач"""
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения запланированных задач: {e}")
    
    def keepalive_loop(self):
        """Расширенный цикл keep-alive с планировщиком"""
        logger.info(f"🔄 Запуск расширенного keep-alive цикла")
        
        while not self.stop_event.is_set():
            try:
                # Выполняем основной ping
                success = self.ping_service()
                
                # Выполняем запланированные задачи
                self.run_scheduled_tasks()
                
                # Проверяем критические ситуации
                if self.consecutive_failures >= 3:
                    logger.error(f"🚨 КРИТИЧНО: {self.consecutive_failures} подряд неудачных keep-alive запросов!")
                    
                    if self.consecutive_failures >= 5:
                        logger.error("💥 ЭКСТРЕННАЯ СИТУАЦИЯ: попытка смены URL...")
                        self._try_alternative_endpoints()
                
                # Адаптивный интервал
                sleep_interval = self._calculate_adaptive_interval(success)
                
                # Ожидание до следующего запроса
                self.stop_event.wait(sleep_interval)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в расширенном keep-alive цикле: {e}")
                self.stop_event.wait(60)

# ============================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ
# ============================================

# Глобальный экземпляр
_keepalive_manager: Optional[EnhancedKeepAlive] = None

def get_keepalive_manager() -> Optional[EnhancedKeepAlive]:
    """Получение глобального экземпляра keep-alive менеджера"""
    return _keepalive_manager

def init_keepalive(target_url: str, interval: int = 300, enabled: bool = True) -> EnhancedKeepAlive:
    """
    Инициализация глобального keep-alive менеджера
    
    Args:
        target_url: URL для ping запросов
        interval: Интервал между запросами в секундах
        enabled: Включен ли keep-alive
        
    Returns:
        EnhancedKeepAlive: Инициализированный менеджер
    """
    global _keepalive_manager
    
    _keepalive_manager = EnhancedKeepAlive(
        target_url=target_url,
        interval=interval,
        enabled=enabled
    )
    
    logger.info("✅ Глобальный keep-alive менеджер инициализирован")
    return _keepalive_manager

def start_keepalive_thread(target_url: str, interval: int = 300, enabled: bool = True):
    """
    Быстрый запуск keep-alive в отдельном потоке
    
    Args:
        target_url: URL для ping запросов
        interval: Интервал между запросами в секундах
        enabled: Включен ли keep-alive
    """
    if not enabled:
        logger.info("⏭️ Keep-alive отключен")
        return
    
    manager = init_keepalive(target_url, interval, enabled)
    
    keepalive_thread = threading.Thread(
        target=manager.start_keepalive,
        daemon=True,
        name="KeepAliveThread"
    )
    keepalive_thread.start()
    
    logger.info(f"🚀 Keep-alive запущен в отдельном потоке для {target_url}")

# ============================================
# ТЕСТИРОВАНИЕ
# ============================================

if __name__ == "__main__":
    """Тестирование keep-alive системы"""
    
    # Настройка логирования для тестирования
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Тест локального сервера
    test_url = "http://localhost:8000/health"
    
    print("🧪 Тестирование KeepAlive системы...")
    print(f"🎯 Test URL: {test_url}")
    
    # Создание и запуск менеджера
    manager = EnhancedKeepAlive(test_url, interval=10, enabled=True)
    
    try:
        # Тест ping
        print("📡 Тестирование ping...")
        result = manager.ping_service()
        print(f"Результат ping: {'✅ Успех' if result else '❌ Ошибка'}")
        
        # Получение статистики
        print("📊 Статистика:")
        stats = manager.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Тест статуса здоровья
        print("💓 Статус здоровья:")
        health = manager.get_health_status()
        print(f"  Статус: {health['status']}")
        print(f"  Сообщение: {health['message']}")
        
        print("✅ Тестирование завершено")
        
    except KeyboardInterrupt:
        print("⌨️ Остановка по запросу пользователя")
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
    finally:
        manager.stop()
