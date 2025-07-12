"""
Keep-Alive система Do Presave Reminder Bot v25+
Предотвращение засыпания сервиса на Render.com через автоматические HTTP запросы
"""

import os
import time
import threading
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from typing import Optional

from utils.logger import get_logger, log_api_call

logger = get_logger(__name__)

class KeepAliveManager:
    """Менеджер keep-alive запросов"""
    
    def __init__(self, external_url: str = None, interval: int = 300, enabled: bool = True):
        """
        Инициализация keep-alive менеджера
        
        Args:
            external_url: URL сервиса (из RENDER_EXTERNAL_URL)
            interval: Интервал между запросами в секундах (по умолчанию 5 минут)
            enabled: Включен ли keep-alive
        """
        self.external_url = external_url or os.getenv('RENDER_EXTERNAL_URL')
        self.interval = interval
        self.enabled = enabled and bool(self.external_url)
        
        # Внутреннее состояние
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_ping_time: Optional[datetime] = None
        self._ping_count = 0
        self._error_count = 0
        self._consecutive_errors = 0
        
        # Статистика
        self.stats = {
            'total_pings': 0,
            'successful_pings': 0,
            'failed_pings': 0,
            'uptime_start': datetime.now(),
            'last_successful_ping': None,
            'last_error': None
        }
        
        if self.enabled:
            logger.info(f"KeepAliveManager инициализирован: {self.external_url} каждые {interval}с")
        else:
            logger.info("KeepAliveManager отключен (нет RENDER_EXTERNAL_URL)")
    
    def start_keepalive(self):
        """Запуск keep-alive в фоновом потоке"""
        if not self.enabled:
            logger.info("Keep-alive отключен, запуск пропущен")
            return
        
        if self._thread and self._thread.is_alive():
            logger.warning("Keep-alive уже запущен")
            return
        
        try:
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._keepalive_worker,
                daemon=True,
                name="KeepAlive"
            )
            
            self._thread.start()
            logger.info(f"💓 Keep-alive запущен: пинг каждые {self.interval} секунд")
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска keep-alive: {e}")
            raise
    
    def stop(self):
        """Остановка keep-alive"""
        if not self.enabled:
            return
        
        try:
            logger.info("🛑 Остановка keep-alive...")
            self._stop_event.set()
            
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=10)
                
                if self._thread.is_alive():
                    logger.warning("⚠️ Keep-alive поток не завершился в течение 10 секунд")
                else:
                    logger.info("✅ Keep-alive остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка остановки keep-alive: {e}")
    
    def _keepalive_worker(self):
        """Рабочая функция keep-alive потока"""
        logger.info("💓 Keep-alive поток запущен")
        
        # Ждем немного перед первым пингом, чтобы сервер успел запуститься
        time.sleep(30)
        
        while not self._stop_event.is_set():
            try:
                # Выполняем пинг
                self._perform_ping()
                
                # Ждем до следующего пинга
                self._wait_for_next_ping()
                
            except Exception as e:
                logger.error(f"❌ Критическая ошибка в keep-alive потоке: {e}")
                # Ждем немного перед повтором
                time.sleep(60)
        
        logger.info("💓 Keep-alive поток завершен")
    
    def _perform_ping(self):
        """Выполнение одного пинга"""
        if not self.external_url:
            return
        
        start_time = datetime.now()
        ping_url = f"https://{self.external_url}/health"
        
        try:
            # Подготавливаем запрос
            request = Request(
                ping_url,
                headers={
                    'User-Agent': 'KeepAlive-Bot/1.0',
                    'Accept': 'application/json',
                    'Connection': 'close'
                }
            )
            
            # Выполняем запрос с таймаутом
            with urlopen(request, timeout=30) as response:
                status_code = response.getcode()
                response_text = response.read().decode('utf-8', errors='ignore')[:100]
                
                # Обновляем статистику успеха
                self._update_success_stats(start_time, status_code, response_text)
                
        except (URLError, HTTPError) as e:
            # Обновляем статистику ошибок
            self._update_error_stats(start_time, str(e))
            
        except Exception as e:
            # Обновляем статистику критических ошибок
            self._update_error_stats(start_time, f"Критическая ошибка: {e}")
    
    def _update_success_stats(self, start_time: datetime, status_code: int, response_text: str):
        """Обновление статистики успешных пингов"""
        duration = (datetime.now() - start_time).total_seconds()
        
        self._ping_count += 1
        self._consecutive_errors = 0
        self._last_ping_time = datetime.now()
        
        # Обновляем общую статистику
        self.stats['total_pings'] += 1
        self.stats['successful_pings'] += 1
        self.stats['last_successful_ping'] = self._last_ping_time
        
        # Логируем в зависимости от частоты
        if self._ping_count % 10 == 1:  # Логируем каждый 10-й пинг
            logger.info(f"💓 Keep-alive: пинг #{self._ping_count}, {duration:.1f}с, HTTP {status_code}")
        else:
            logger.debug(f"💓 Keep-alive: пинг #{self._ping_count}, {duration:.1f}с, HTTP {status_code}")
        
        # Логируем статистику каждые 100 пингов
        if self._ping_count % 100 == 0:
            self._log_statistics()
    
    def _update_error_stats(self, start_time: datetime, error_message: str):
        """Обновление статистики ошибок"""
        duration = (datetime.now() - start_time).total_seconds()
        
        self._error_count += 1
        self._consecutive_errors += 1
        
        # Обновляем общую статистику
        self.stats['total_pings'] += 1
        self.stats['failed_pings'] += 1
        self.stats['last_error'] = {
            'time': datetime.now(),
            'message': error_message
        }
        
        # Определяем уровень логирования в зависимости от количества ошибок подряд
        if self._consecutive_errors == 1:
            logger.warning(f"⚠️ Keep-alive ошибка: {error_message} ({duration:.1f}с)")
        elif self._consecutive_errors <= 3:
            logger.error(f"❌ Keep-alive ошибка #{self._consecutive_errors}: {error_message}")
        else:
            logger.critical(f"🚨 Keep-alive: {self._consecutive_errors} ошибок подряд! {error_message}")
    
    def _wait_for_next_ping(self):
        """Ожидание до следующего пинга с возможностью прерывания"""
        # Адаптивный интервал в зависимости от ошибок
        wait_time = self.interval
        
        if self._consecutive_errors > 0:
            # Увеличиваем интервал при ошибках
            wait_time = min(self.interval * (1 + self._consecutive_errors * 0.5), self.interval * 3)
            logger.debug(f"💓 Адаптивный интервал: {wait_time:.0f}с (ошибок: {self._consecutive_errors})")
        
        # Ждем с возможностью прерывания
        self._stop_event.wait(wait_time)
    
    def _log_statistics(self):
        """Логирование статистики keep-alive"""
        uptime = datetime.now() - self.stats['uptime_start']
        success_rate = (self.stats['successful_pings'] / self.stats['total_pings'] * 100) if self.stats['total_pings'] > 0 else 0
        
        logger.info(
            f"📊 Keep-alive статистика: "
            f"{self.stats['successful_pings']}/{self.stats['total_pings']} успешных пингов "
            f"({success_rate:.1f}%), uptime: {uptime}"
        )
    
    def get_status(self) -> dict:
        """Получение статуса keep-alive"""
        if not self.enabled:
            return {
                'enabled': False,
                'reason': 'RENDER_EXTERNAL_URL не настроен'
            }
        
        is_running = self._thread and self._thread.is_alive()
        uptime = datetime.now() - self.stats['uptime_start']
        
        status = {
            'enabled': True,
            'running': is_running,
            'external_url': self.external_url,
            'interval_seconds': self.interval,
            'uptime_seconds': int(uptime.total_seconds()),
            'uptime_human': str(uptime).split('.')[0],  # Убираем микросекунды
            'statistics': self.stats.copy(),
            'last_ping_time': self._last_ping_time,
            'consecutive_errors': self._consecutive_errors,
            'health': self._get_health_status()
        }
        
        # Добавляем время последнего пинга в человекочитаемом формате
        if self._last_ping_time:
            time_since_ping = datetime.now() - self._last_ping_time
            status['seconds_since_last_ping'] = int(time_since_ping.total_seconds())
        
        return status
    
    def _get_health_status(self) -> str:
        """Определение состояния здоровья keep-alive"""
        if not self.enabled:
            return "disabled"
        
        if not (self._thread and self._thread.is_alive()):
            return "stopped"
        
        if self._consecutive_errors >= 5:
            return "critical"
        elif self._consecutive_errors >= 3:
            return "warning"
        elif self._last_ping_time and (datetime.now() - self._last_ping_time).total_seconds() > self.interval * 2:
            return "stale"
        else:
            return "healthy"
    
    def force_ping(self) -> dict:
        """Принудительный пинг (для тестирования)"""
        if not self.enabled:
            return {'error': 'Keep-alive отключен'}
        
        logger.info("🔧 Принудительный keep-alive пинг...")
        
        start_time = datetime.now()
        self._perform_ping()
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            'forced_ping': True,
            'duration_seconds': duration,
            'status': self._get_health_status(),
            'consecutive_errors': self._consecutive_errors
        }


def create_keepalive_manager() -> KeepAliveManager:
    """Фабрика для создания keep-alive менеджера"""
    
    # Получаем настройки из переменных окружения
    external_url = os.getenv('RENDER_EXTERNAL_URL')
    interval = int(os.getenv('KEEPALIVE_INTERVAL', '300'))  # 5 минут по умолчанию
    enabled = os.getenv('KEEPALIVE_ENABLED', 'true').lower() == 'true'
    
    return KeepAliveManager(
        external_url=external_url,
        interval=interval,
        enabled=enabled
    )


if __name__ == "__main__":
    """Тестирование keep-alive системы"""
    import time
    
    print("🧪 Тестирование KeepAliveManager...")
    
    # Создание тестового менеджера
    print("💓 Создание тестового keep-alive...")
    manager = KeepAliveManager(
        external_url="httpbin.org",  # Тестовый сервис
        interval=10,  # Каждые 10 секунд для теста
        enabled=True
    )
    
    try:
        # Запуск keep-alive
        print("🚀 Запуск keep-alive...")
        manager.start_keepalive()
        
        # Ждем несколько пингов
        print("⏳ Ожидание тестовых пингов...")
        time.sleep(25)
        
        # Проверяем статус
        status = manager.get_status()
        print(f"📊 Статус: {status['health']}")
        print(f"📈 Пингов: {status['statistics']['total_pings']}")
        print(f"✅ Успешных: {status['statistics']['successful_pings']}")
        print(f"❌ Ошибок: {status['statistics']['failed_pings']}")
        
        # Принудительный пинг
        print("🔧 Тестовый принудительный пинг...")
        force_result = manager.force_ping()
        print(f"⚡ Результат: {force_result}")
        
    finally:
        print("🛑 Остановка тестового keep-alive...")
        manager.stop()
        print("✅ Тестирование завершено!")