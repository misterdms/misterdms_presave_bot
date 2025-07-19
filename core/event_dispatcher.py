"""
Core/event_dispatcher.py - Система событий между модулями
Do Presave Reminder Bot v29.07

Асинхронная система событий для слабосвязанного взаимодействия между модулями
"""

import asyncio
import time
import traceback
from typing import Dict, List, Callable, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, deque

from core.interfaces import EventListener, EventTypes
from utils.logger import get_logger, log_performance_metric


@dataclass
class Event:
    """Структура события"""
    event_type: str
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    source_module: Optional[str] = None
    event_id: Optional[str] = None
    priority: int = 0  # 0 = низкий, 1 = нормальный, 2 = высокий


@dataclass
class EventSubscription:
    """Подписка на события"""
    listener: Callable
    event_types: Set[str]
    module_name: Optional[str] = None
    priority: int = 0
    is_async: bool = True


class EventDispatcher:
    """Диспетчер событий для модулей"""
    
    def __init__(self, max_history: int = 1000, enable_metrics: bool = True):
        """
        Инициализация диспетчера событий
        
        Args:
            max_history: Максимальное количество событий в истории
            enable_metrics: Включить сбор метрик производительности
        """
        self.logger = get_logger(__name__)
        
        # Подписчики по типам событий
        self.subscriptions: Dict[str, List[EventSubscription]] = defaultdict(list)
        
        # История событий
        self.event_history: deque = deque(maxlen=max_history)
        
        # Метрики
        self.enable_metrics = enable_metrics
        self.event_count = 0
        self.error_count = 0
        self.total_processing_time = 0.0
        self.metrics_by_type: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'count': 0,
            'total_time': 0.0,
            'error_count': 0,
            'last_event': None
        })
        
        # Очереди по приоритетам
        self.priority_queues = {
            0: asyncio.Queue(),  # Низкий приоритет
            1: asyncio.Queue(),  # Нормальный приоритет  
            2: asyncio.Queue()   # Высокий приоритет
        }
        
        # Задача обработки событий
        self.processing_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # Фильтры событий
        self.event_filters: List[Callable] = []
        
    async def start(self):
        """Запуск диспетчера событий"""
        if self.is_running:
            self.logger.warning("⚠️ Диспетчер событий уже запущен")
            return
        
        self.is_running = True
        self.processing_task = asyncio.create_task(self._process_events())
        self.logger.info("🎭 Диспетчер событий запущен")
    
    async def stop(self):
        """Остановка диспетчера событий"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("🔄 Диспетчер событий остановлен")
    
    def subscribe(self, event_types: List[str], listener: Callable, 
                 module_name: str = None, priority: int = 0) -> str:
        """
        Подписка на события
        
        Args:
            event_types: Список типов событий для прослушивания
            listener: Функция-обработчик событий
            module_name: Имя модуля (для логирования)
            priority: Приоритет обработки (0-2)
            
        Returns:
            str: ID подписки
        """
        subscription = EventSubscription(
            listener=listener,
            event_types=set(event_types),
            module_name=module_name,
            priority=priority,
            is_async=asyncio.iscoroutinefunction(listener)
        )
        
        # Добавляем подписку для каждого типа события
        for event_type in event_types:
            self.subscriptions[event_type].append(subscription)
            
            # Сортируем по приоритету (высокий приоритет первым)
            self.subscriptions[event_type].sort(key=lambda s: s.priority, reverse=True)
        
        subscription_id = f"{module_name or 'unknown'}_{id(subscription)}"
        
        self.logger.debug(f"📡 Подписка создана: {module_name} на {event_types}")
        return subscription_id
    
    def subscribe_listener(self, listener: EventListener) -> str:
        """
        Подписка объекта-слушателя на события
        
        Args:
            listener: Объект, реализующий EventListener
            
        Returns:
            str: ID подписки
        """
        event_types = listener.get_event_types()
        module_name = getattr(listener, '__class__', {}).get('__name__', 'unknown')
        
        return self.subscribe(
            event_types=event_types,
            listener=listener.on_event,
            module_name=module_name
        )
    
    def unsubscribe(self, subscription_id: str):
        """Отписка от событий по ID подписки"""
        # TODO: Реализовать отписку по ID
        # Пока простая реализация - полная очистка неактивных подписок
        pass
    
    def unsubscribe_module(self, module_name: str):
        """Отписка всех подписок модуля"""
        for event_type, subscriptions in self.subscriptions.items():
            self.subscriptions[event_type] = [
                sub for sub in subscriptions 
                if sub.module_name != module_name
            ]
        
        self.logger.debug(f"📡 Все подписки модуля {module_name} удалены")
    
    async def emit(self, event_type: str, data: Dict[str, Any], 
                  source_module: str = None, priority: int = 1) -> bool:
        """
        Отправка события
        
        Args:
            event_type: Тип события
            data: Данные события
            source_module: Модуль-источник события
            priority: Приоритет события (0-2)
            
        Returns:
            bool: Успешность отправки
        """
        try:
            # Создаем событие
            event = Event(
                event_type=event_type,
                data=data,
                source_module=source_module,
                priority=priority,
                event_id=f"{event_type}_{int(time.time() * 1000)}"
            )
            
            # Применяем фильтры
            if not self._apply_filters(event):
                self.logger.debug(f"🚫 Событие отфильтровано: {event_type}")
                return False
            
            # Добавляем в очередь по приоритету
            if priority in self.priority_queues:
                await self.priority_queues[priority].put(event)
            else:
                await self.priority_queues[1].put(event)  # По умолчанию нормальный приоритет
            
            # Добавляем в историю
            self.event_history.append(event)
            
            # Увеличиваем счетчик
            self.event_count += 1
            
            self.logger.debug(f"📤 Событие отправлено: {event_type} от {source_module}")
            return True
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"❌ Ошибка отправки события {event_type}: {e}")
            return False
    
    async def emit_and_wait(self, event_type: str, data: Dict[str, Any], 
                           timeout: float = 5.0) -> List[Any]:
        """
        Отправка события и ожидание результатов от всех обработчиков
        
        Args:
            event_type: Тип события
            data: Данные события
            timeout: Таймаут ожидания
            
        Returns:
            List[Any]: Результаты обработчиков
        """
        results = []
        
        # Получаем подписчиков
        subscriptions = self.subscriptions.get(event_type, [])
        if not subscriptions:
            return results
        
        # Создаем событие
        event = Event(event_type=event_type, data=data, priority=2)  # Высокий приоритет
        
        # Выполняем обработчики параллельно
        tasks = []
        for subscription in subscriptions:
            if subscription.is_async:
                task = asyncio.create_task(self._call_async_handler(subscription, event))
            else:
                task = asyncio.create_task(self._call_sync_handler(subscription, event))
            tasks.append(task)
        
        # Ждем результаты с таймаутом
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout)
        except asyncio.TimeoutError:
            self.logger.warning(f"⏰ Таймаут обработки события {event_type}")
            # Отменяем незавершенные задачи
            for task in tasks:
                if not task.done():
                    task.cancel()
        
        return results
    
    async def _process_events(self):
        """Основной цикл обработки событий"""
        self.logger.info("🔄 Запущен цикл обработки событий")
        
        while self.is_running:
            try:
                # Обрабатываем события по приоритетам (высокий -> низкий)
                event = None
                
                for priority in [2, 1, 0]:
                    try:
                        event = self.priority_queues[priority].get_nowait()
                        break
                    except asyncio.QueueEmpty:
                        continue
                
                if event is None:
                    # Если очереди пусты, ждем немного
                    await asyncio.sleep(0.01)
                    continue
                
                # Обрабатываем событие
                await self._handle_event(event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"❌ Ошибка в цикле обработки событий: {e}")
                await asyncio.sleep(0.1)  # Небольшая пауза при ошибке
    
    async def _handle_event(self, event: Event):
        """Обработка одного события"""
        start_time = time.time()
        
        try:
            # Получаем подписчиков для данного типа события
            subscriptions = self.subscriptions.get(event.event_type, [])
            
            if not subscriptions:
                self.logger.debug(f"📭 Нет подписчиков для события: {event.event_type}")
                return
            
            # Вызываем обработчики
            tasks = []
            for subscription in subscriptions:
                if subscription.is_async:
                    task = asyncio.create_task(self._call_async_handler(subscription, event))
                else:
                    task = asyncio.create_task(self._call_sync_handler(subscription, event))
                tasks.append(task)
            
            # Ждем завершения всех обработчиков
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обновляем метрики
            if self.enable_metrics:
                processing_time = time.time() - start_time
                self._update_metrics(event.event_type, processing_time, success=True)
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.error_count += 1
            self.logger.error(f"❌ Ошибка обработки события {event.event_type}: {e}")
            
            if self.enable_metrics:
                self._update_metrics(event.event_type, processing_time, success=False)
    
    async def _call_async_handler(self, subscription: EventSubscription, event: Event):
        """Вызов асинхронного обработчика"""
        try:
            await subscription.listener(event.event_type, event.data)
        except Exception as e:
            self.logger.error(f"❌ Ошибка в async обработчике {subscription.module_name}: {e}")
            self.logger.error(traceback.format_exc())
    
    async def _call_sync_handler(self, subscription: EventSubscription, event: Event):
        """Вызов синхронного обработчика"""
        try:
            # Выполняем синхронную функцию в executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, subscription.listener, event.event_type, event.data)
        except Exception as e:
            self.logger.error(f"❌ Ошибка в sync обработчике {subscription.module_name}: {e}")
            self.logger.error(traceback.format_exc())
    
    def _apply_filters(self, event: Event) -> bool:
        """Применение фильтров к событию"""
        for filter_func in self.event_filters:
            try:
                if not filter_func(event):
                    return False
            except Exception as e:
                self.logger.error(f"❌ Ошибка в фильтре событий: {e}")
        return True
    
    def _update_metrics(self, event_type: str, processing_time: float, success: bool):
        """Обновление метрик производительности"""
        metrics = self.metrics_by_type[event_type]
        metrics['count'] += 1
        metrics['total_time'] += processing_time
        metrics['last_event'] = time.time()
        
        if not success:
            metrics['error_count'] += 1
        
        self.total_processing_time += processing_time
        
        # Логируем медленные события
        if processing_time > 1.0:  # Более 1 секунды
            self.logger.warning(f"🐌 Медленная обработка события {event_type}: {processing_time:.3f}s")
        
        # Отправляем метрику производительности
        if self.enable_metrics:
            log_performance_metric(
                f"event_processing_{event_type}",
                processing_time * 1000,  # в миллисекундах
                "ms",
                {"success": success}
            )
    
    def add_filter(self, filter_func: Callable[[Event], bool]):
        """Добавление фильтра событий"""
        self.event_filters.append(filter_func)
        self.logger.debug("📋 Добавлен фильтр событий")
    
    def get_event_history(self, limit: int = 100, event_type: str = None) -> List[Event]:
        """Получение истории событий"""
        events = list(self.event_history)
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:] if limit else events
    
    def get_subscription_stats(self) -> Dict[str, Any]:
        """Получение статистики подписок"""
        stats = {
            'total_subscriptions': 0,
            'subscriptions_by_type': {},
            'subscriptions_by_module': defaultdict(int)
        }
        
        for event_type, subscriptions in self.subscriptions.items():
            stats['subscriptions_by_type'][event_type] = len(subscriptions)
            stats['total_subscriptions'] += len(subscriptions)
            
            for subscription in subscriptions:
                if subscription.module_name:
                    stats['subscriptions_by_module'][subscription.module_name] += 1
        
        return stats
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получение метрик производительности"""
        avg_processing_time = (
            self.total_processing_time / self.event_count 
            if self.event_count > 0 else 0
        )
        
        return {
            'event_count': self.event_count,
            'error_count': self.error_count,
            'error_rate': self.error_count / max(self.event_count, 1),
            'avg_processing_time': avg_processing_time,
            'total_processing_time': self.total_processing_time,
            'is_running': self.is_running,
            'queue_sizes': {
                priority: queue.qsize() 
                for priority, queue in self.priority_queues.items()
            },
            'metrics_by_type': dict(self.metrics_by_type),
            'history_size': len(self.event_history)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья диспетчера событий"""
        try:
            # Тестовое событие
            test_start = time.time()
            await self.emit("system.health_check", {"timestamp": test_start})
            test_time = time.time() - test_start
            
            metrics = self.get_metrics()
            subscription_stats = self.get_subscription_stats()
            
            return {
                "healthy": self.is_running and test_time < 1.0,
                "is_running": self.is_running,
                "test_response_time": test_time,
                "event_count": self.event_count,
                "error_rate": metrics['error_rate'],
                "total_subscriptions": subscription_stats['total_subscriptions'],
                "queue_sizes": metrics['queue_sizes']
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "is_running": self.is_running
            }


# === ПРЕДОПРЕДЕЛЕННЫЕ ФИЛЬТРЫ ===

def create_rate_limit_filter(max_events_per_second: int = 100) -> Callable:
    """Создание фильтра ограничения частоты событий"""
    event_times = deque(maxlen=max_events_per_second)
    
    def rate_limit_filter(event: Event) -> bool:
        now = time.time()
        event_times.append(now)
        
        # Проверяем, не превышен ли лимит
        if len(event_times) >= max_events_per_second:
            oldest = event_times[0]
            if now - oldest < 1.0:  # Менее секунды
                return False
        
        return True
    
    return rate_limit_filter


def create_duplicate_filter(window_seconds: float = 1.0) -> Callable:
    """Создание фильтра дубликатов событий"""
    recent_events = {}
    
    def duplicate_filter(event: Event) -> bool:
        now = time.time()
        event_key = f"{event.event_type}_{event.source_module}"
        
        # Очищаем старые события
        to_remove = [
            key for key, timestamp in recent_events.items()
            if now - timestamp > window_seconds
        ]
        for key in to_remove:
            del recent_events[key]
        
        # Проверяем дубликат
        if event_key in recent_events:
            return False
        
        recent_events[event_key] = now
        return True
    
    return duplicate_filter


if __name__ == "__main__":
    # Тестирование диспетчера событий
    async def test_event_dispatcher():
        print("🧪 Тестирование диспетчера событий...")
        
        dispatcher = EventDispatcher()
        await dispatcher.start()
        
        # Тестовый подписчик
        received_events = []
        
        async def test_listener(event_type: str, data: Dict[str, Any]):
            received_events.append((event_type, data))
            print(f"📨 Получено событие: {event_type} | {data}")
        
        # Подписываемся на события
        dispatcher.subscribe([EventTypes.USER_REGISTERED, EventTypes.MODULE_LOADED], test_listener, "test_module")
        
        # Отправляем тестовые события
        await dispatcher.emit(EventTypes.USER_REGISTERED, {"user_id": 12345})
        await dispatcher.emit(EventTypes.MODULE_LOADED, {"module_name": "test"})
        await dispatcher.emit("unknown_event", {"data": "test"})  # Не должно быть обработано
        
        # Ждем обработки
        await asyncio.sleep(0.1)
        
        # Проверяем результаты
        print(f"📊 Получено событий: {len(received_events)}")
        print(f"📈 Метрики: {dispatcher.get_metrics()}")
        print(f"📡 Подписки: {dispatcher.get_subscription_stats()}")
        
        # Проверяем здоровье
        health = await dispatcher.health_check()
        print(f"🏥 Здоровье: {health}")
        
        await dispatcher.stop()
        print("✅ Тестирование завершено")
    
    asyncio.run(test_event_dispatcher())