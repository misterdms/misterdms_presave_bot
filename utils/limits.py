"""
Управление лимитами API Do Presave Reminder Bot v25+
Система управления 4 режимами лимитов обращений к Telegram API
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from dataclasses import dataclass
from collections import defaultdict, deque

from utils.logger import get_logger, log_api_call

logger = get_logger(__name__)

@dataclass
class LimitConfig:
    """Конфигурация режима лимитов"""
    name: str
    emoji: str
    max_requests_per_hour: int
    cooldown_seconds: int
    description: str
    
    def __str__(self):
        return f"{self.emoji} {self.name}"

class LimitManager:
    """Менеджер лимитов API с поддержкой 4 режимов"""
    
    def __init__(self):
        """Инициализация менеджера лимитов"""
        
        # Режимы лимитов из переменных окружения
        self.limit_configs = {
            'CONSERVATIVE': LimitConfig(
                name='Conservative',
                emoji='🐌',
                max_requests_per_hour=int(os.getenv('CONSERVATIVE_MAX_HOUR', '60')),
                cooldown_seconds=int(os.getenv('CONSERVATIVE_COOLDOWN', '60')),
                description='Медленный и безопасный режим'
            ),
            'NORMAL': LimitConfig(
                name='Normal',
                emoji='⚡',
                max_requests_per_hour=int(os.getenv('NORMAL_MAX_HOUR', '180')),
                cooldown_seconds=int(os.getenv('NORMAL_COOLDOWN', '20')),
                description='Стандартный режим работы'
            ),
            'BURST': LimitConfig(
                name='Burst',
                emoji='🚀',
                max_requests_per_hour=int(os.getenv('BURST_MAX_HOUR', '600')),
                cooldown_seconds=int(os.getenv('BURST_COOLDOWN', '6')),
                description='Быстрый режим (по умолчанию)'
            ),
            'ADMIN_BURST': LimitConfig(
                name='Admin Burst',
                emoji='⚡⚡',
                max_requests_per_hour=int(os.getenv('ADMIN_BURST_MAX_HOUR', '1200')),
                cooldown_seconds=int(os.getenv('ADMIN_BURST_COOLDOWN', '3')),
                description='Максимально быстрый режим для админов'
            )
        }
        
        # Текущий режим (по умолчанию BURST)
        self.current_mode = os.getenv('CURRENT_LIMIT_MODE', 'BURST').upper()
        if self.current_mode not in self.limit_configs:
            logger.warning(f"Неизвестный режим {self.current_mode}, установлен BURST")
            self.current_mode = 'BURST'
        
        # Счетчики запросов (в памяти для ПЛАНА 1)
        self.request_history = defaultdict(deque)  # user_id -> deque of timestamps
        self.last_request_time = defaultdict(float)  # user_id -> timestamp
        
        # Статистика
        self.stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'mode_changes': 0,
            'startup_time': datetime.now()
        }
        
        logger.info(f"LimitManager инициализирован: режим {self.get_current_config()}")
    
    def get_current_config(self) -> LimitConfig:
        """Получение конфигурации текущего режима"""
        return self.limit_configs[self.current_mode]
    
    def set_mode(self, mode: str) -> bool:
        """Установка режима лимитов"""
        mode = mode.upper()
        
        if mode not in self.limit_configs:
            logger.error(f"Неизвестный режим лимитов: {mode}")
            return False
        
        old_mode = self.current_mode
        self.current_mode = mode
        
        # Сохраняем в переменную окружения (для текущей сессии)
        os.environ['CURRENT_LIMIT_MODE'] = mode
        
        self.stats['mode_changes'] += 1
        
        logger.info(f"Режим лимитов изменен: {old_mode} → {mode}")
        return True
    
    def get_all_modes(self) -> Dict[str, LimitConfig]:
        """Получение всех доступных режимов"""
        return self.limit_configs.copy()
    
    def check_rate_limit(self, user_id: int, is_admin: bool = False) -> Dict[str, Any]:
        """
        Проверка лимитов для пользователя
        
        Returns:
            dict: {'allowed': bool, 'reason': str, 'retry_after': int, 'config': LimitConfig}
        """
        
        current_time = time.time()
        config = self.get_current_config()
        
        # Админы в режиме ADMIN_BURST не ограничены строго
        if is_admin and self.current_mode == 'ADMIN_BURST':
            # Для админов только базовая проверка cooldown
            last_request = self.last_request_time.get(user_id, 0)
            time_since_last = current_time - last_request
            
            if time_since_last < config.cooldown_seconds:
                retry_after = int(config.cooldown_seconds - time_since_last)
                return {
                    'allowed': False,
                    'reason': f'Cooldown (админ): подождите {retry_after}с',
                    'retry_after': retry_after,
                    'config': config
                }
        
        # Обычная проверка лимитов
        result = self._check_hourly_limit(user_id, config, current_time)
        
        if not result['allowed']:
            self.stats['blocked_requests'] += 1
            return result
        
        # Проверка cooldown
        last_request = self.last_request_time.get(user_id, 0)
        time_since_last = current_time - last_request
        
        if time_since_last < config.cooldown_seconds:
            retry_after = int(config.cooldown_seconds - time_since_last)
            self.stats['blocked_requests'] += 1
            
            return {
                'allowed': False,
                'reason': f'Cooldown: подождите {retry_after}с',
                'retry_after': retry_after,
                'config': config
            }
        
        # Запрос разрешен
        self._record_request(user_id, current_time)
        self.stats['total_requests'] += 1
        
        return {
            'allowed': True,
            'reason': 'OK',
            'retry_after': 0,
            'config': config
        }
    
    def _check_hourly_limit(self, user_id: int, config: LimitConfig, current_time: float) -> Dict[str, Any]:
        """Проверка часового лимита"""
        
        # Получаем историю запросов пользователя
        user_history = self.request_history[user_id]
        
        # Убираем запросы старше часа
        hour_ago = current_time - 3600
        while user_history and user_history[0] < hour_ago:
            user_history.popleft()
        
        # Проверяем лимит
        if len(user_history) >= config.max_requests_per_hour:
            # Вычисляем когда можно будет сделать следующий запрос
            oldest_request = user_history[0]
            retry_after = int(oldest_request + 3600 - current_time)
            
            return {
                'allowed': False,
                'reason': f'Часовой лимит {config.max_requests_per_hour} запросов превышен',
                'retry_after': max(retry_after, 1),
                'config': config
            }
        
        return {
            'allowed': True,
            'reason': 'OK',
            'retry_after': 0,
            'config': config
        }
    
    def _record_request(self, user_id: int, timestamp: float):
        """Запись запроса в историю"""
        self.request_history[user_id].append(timestamp)
        self.last_request_time[user_id] = timestamp
        
        # Ограничиваем размер истории
        if len(self.request_history[user_id]) > 2000:
            self.request_history[user_id] = deque(
                list(self.request_history[user_id])[-1000:],
                maxlen=2000
            )
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики пользователя"""
        current_time = time.time()
        config = self.get_current_config()
        
        # Очищаем старые запросы
        user_history = self.request_history[user_id]
        hour_ago = current_time - 3600
        while user_history and user_history[0] < hour_ago:
            user_history.popleft()
        
        # Последний запрос
        last_request = self.last_request_time.get(user_id, 0)
        time_since_last = current_time - last_request if last_request > 0 else None
        
        return {
            'user_id': user_id,
            'current_mode': self.current_mode,
            'config': config,
            'requests_last_hour': len(user_history),
            'remaining_requests': max(0, config.max_requests_per_hour - len(user_history)),
            'last_request_time': datetime.fromtimestamp(last_request) if last_request > 0 else None,
            'seconds_since_last_request': int(time_since_last) if time_since_last is not None else None,
            'cooldown_remaining': max(0, int(config.cooldown_seconds - time_since_last)) if time_since_last is not None else 0
        }
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Получение глобальной статистики"""
        current_time = time.time()
        uptime = current_time - self.stats['startup_time'].timestamp()
        
        # Подсчет активных пользователей
        active_users = 0
        total_requests_last_hour = 0
        
        hour_ago = current_time - 3600
        
        for user_id, history in self.request_history.items():
            # Очищаем старые запросы
            while history and history[0] < hour_ago:
                history.popleft()
            
            if history:
                active_users += 1
                total_requests_last_hour += len(history)
        
        return {
            'current_mode': self.current_mode,
            'current_config': self.get_current_config(),
            'uptime_seconds': int(uptime),
            'uptime_human': str(timedelta(seconds=int(uptime))),
            'total_requests': self.stats['total_requests'],
            'blocked_requests': self.stats['blocked_requests'],
            'mode_changes': self.stats['mode_changes'],
            'active_users_last_hour': active_users,
            'total_requests_last_hour': total_requests_last_hour,
            'success_rate': (
                (self.stats['total_requests'] - self.stats['blocked_requests']) / 
                max(self.stats['total_requests'], 1) * 100
            )
        }
    
    def reset_user_limits(self, user_id: int):
        """Сброс лимитов пользователя (для админских нужд)"""
        if user_id in self.request_history:
            del self.request_history[user_id]
        if user_id in self.last_request_time:
            del self.last_request_time[user_id]
        
        logger.info(f"Лимиты сброшены для пользователя {user_id}")
    
    def cleanup_old_data(self):
        """Очистка старых данных (вызывается периодически)"""
        current_time = time.time()
        hour_ago = current_time - 3600
        
        # Очищаем историю запросов
        for user_id in list(self.request_history.keys()):
            history = self.request_history[user_id]
            
            # Убираем старые запросы
            while history and history[0] < hour_ago:
                history.popleft()
            
            # Удаляем пустые истории
            if not history:
                del self.request_history[user_id]
        
        # Очищаем last_request_time для неактивных пользователей
        for user_id in list(self.last_request_time.keys()):
            if user_id not in self.request_history:
                del self.last_request_time[user_id]
        
        logger.debug(f"Очистка данных: активных пользователей {len(self.request_history)}")
    
    def export_config(self) -> Dict[str, Any]:
        """Экспорт конфигурации лимитов"""
        return {
            'current_mode': self.current_mode,
            'modes': {
                mode: {
                    'name': config.name,
                    'emoji': config.emoji,
                    'max_requests_per_hour': config.max_requests_per_hour,
                    'cooldown_seconds': config.cooldown_seconds,
                    'description': config.description
                }
                for mode, config in self.limit_configs.items()
            },
            'stats': self.get_global_stats()
        }


# Глобальный экземпляр менеджера лимитов
_limit_manager: Optional[LimitManager] = None

def get_limit_manager() -> LimitManager:
    """Получение глобального менеджера лимитов"""
    global _limit_manager
    
    if _limit_manager is None:
        _limit_manager = LimitManager()
    
    return _limit_manager

def check_user_rate_limit(user_id: int, is_admin: bool = False) -> Dict[str, Any]:
    """Удобная функция проверки лимитов пользователя"""
    manager = get_limit_manager()
    return manager.check_rate_limit(user_id, is_admin)

def set_limit_mode(mode: str) -> bool:
    """Удобная функция установки режима лимитов"""
    manager = get_limit_manager()
    return manager.set_mode(mode)

def get_current_limit_mode() -> str:
    """Получение текущего режима лимитов"""
    manager = get_limit_manager()
    return manager.current_mode

def get_limit_stats() -> Dict[str, Any]:
    """Получение статистики лимитов"""
    manager = get_limit_manager()
    return manager.get_global_stats()

def get_current_limits() -> Dict[str, Any]:
    """Получение информации о текущих лимитах"""
    manager = get_limit_manager()
    current_config = manager.get_current_config()
    
    return {
        'current_mode': manager.current_mode,
        'mode_name': current_config.name,
        'mode_emoji': current_config.emoji,
        'max_requests_per_hour': current_config.max_requests_per_hour,
        'cooldown_seconds': current_config.cooldown_seconds,
        'description': current_config.description,
        'all_modes': {
            mode: {
                'name': config.name,
                'emoji': config.emoji,
                'max_hour': config.max_requests_per_hour,
                'cooldown': config.cooldown_seconds
            }
            for mode, config in manager.get_all_modes().items()
        }
    }

if __name__ == "__main__":
    """Тестирование системы лимитов"""
    import time
    
    print("🧪 Тестирование LimitManager...")
    
    # Создание менеджера
    manager = LimitManager()
    
    # Тестирование режимов
    print("\n⚙️ Тестирование режимов:")
    for mode_name, config in manager.get_all_modes().items():
        print(f"• {mode_name}: {config}")
    
    # Тестирование смены режимов
    print("\n🔄 Тестирование смены режимов:")
    print(f"Текущий: {manager.current_mode}")
    
    success = manager.set_mode('CONSERVATIVE')
    print(f"Смена на CONSERVATIVE: {'✅' if success else '❌'}")
    print(f"Новый режим: {manager.current_mode}")
    
    # Тестирование лимитов
    print("\n🚦 Тестирование лимитов:")
    test_user_id = 12345
    
    # Несколько быстрых запросов
    for i in range(3):
        result = manager.check_rate_limit(test_user_id, is_admin=False)
        status = "✅ Разрешен" if result['allowed'] else f"❌ Блокирован: {result['reason']}"
        print(f"Запрос {i+1}: {status}")
        
        if not result['allowed']:
            print(f"  Повтор через: {result['retry_after']}с")
        
        time.sleep(1)
    
    # Статистика пользователя
    print("\n📊 Статистика пользователя:")
    user_stats = manager.get_user_stats(test_user_id)
    print(f"Запросов за час: {user_stats['requests_last_hour']}")
    print(f"Осталось запросов: {user_stats['remaining_requests']}")
    print(f"Cooldown: {user_stats['cooldown_remaining']}с")
    
    # Глобальная статистика
    print("\n🌍 Глобальная статистика:")
    global_stats = manager.get_global_stats()
    print(f"Общий запросов: {global_stats['total_requests']}")
    print(f"Заблокированных: {global_stats['blocked_requests']}")
    print(f"Активных пользователей: {global_stats['active_users_last_hour']}")
    print(f"Успешность: {global_stats['success_rate']:.1f}%")
    
    print("\n✅ Тестирование LimitManager завершено!")
