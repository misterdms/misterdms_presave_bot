"""
WebApp Integration/webapp_handler.py - Интеграция с WebApp
Do Presave Reminder Bot v29.07

Обработка данных от WebApp и синхронизация с модулями бота
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
import uuid

from core.interfaces import EventTypes
from core.exceptions import WebAppError, WebAppDataError, WebAppSessionError
from utils.logger import get_logger, log_webapp_interaction, log_performance_metric


@dataclass
class WebAppSession:
    """Сессия WebApp пользователя"""
    session_id: str
    user_id: int
    group_id: int
    created_at: float
    last_activity: float
    platform: str = "webapp"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    commands_sent: int = 0
    data: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}
    
    def is_expired(self, timeout: int = 3600) -> bool:
        """Проверка истечения сессии"""
        return time.time() - self.last_activity > timeout
    
    def update_activity(self):
        """Обновление времени последней активности"""
        self.last_activity = time.time()


class WebAppHandler:
    """Обработчик интеграции с WebApp"""
    
    def __init__(self, bot, module_registry, database):
        """
        Инициализация WebApp обработчика
        
        Args:
            bot: Экземпляр Telegram бота
            module_registry: Реестр модулей
            database: Ядро базы данных
        """
        self.bot = bot
        self.module_registry = module_registry
        self.database = database
        self.logger = get_logger(__name__)
        
        # Активные сессии
        self.active_sessions: Dict[str, WebAppSession] = {}
        self.sessions_by_user: Dict[int, List[str]] = {}
        
        # Обработчики команд WebApp
        self.command_handlers: Dict[str, Callable] = {}
        
        # Статистика
        self.total_sessions = 0
        self.total_commands = 0
        self.total_errors = 0
        
        # Задачи очистки
        self.cleanup_task: Optional[asyncio.Task] = None
        
    async def initialize(self):
        """Инициализация WebApp обработчика"""
        try:
            # Регистрируем обработчик WebApp данных в боте
            self.bot.register_webapp_handler(self.handle_webapp_data)
            
            # Регистрируем стандартные команды
            self._register_default_commands()
            
            # Запускаем задачу очистки сессий
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
            
            self.logger.info("🌐 WebApp обработчик инициализирован")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации WebApp обработчика: {e}")
            raise WebAppError(f"Не удалось инициализировать WebApp обработчик: {e}")
    
    async def handle_webapp_data(self, message, webapp_data: Dict[str, Any]):
        """
        Обработка данных от WebApp
        
        Args:
            message: Telegram сообщение
            webapp_data: Данные от WebApp
        """
        start_time = time.time()
        
        try:
            user_id = message.from_user.id
            group_id = getattr(message.chat, 'id', None)
            
            self.logger.debug(f"🌐 WebApp данные от {user_id}: {webapp_data}")
            
            # Валидируем данные
            if not self._validate_webapp_data(webapp_data):
                raise WebAppDataError("Неверный формат данных WebApp")
            
            # Получаем или создаем сессию
            session = await self._get_or_create_session(user_id, group_id, webapp_data)
            
            # Обрабатываем команду
            command = webapp_data.get('command')
            if command:
                await self._handle_command(session, command, webapp_data, message)
            
            # Обрабатываем аналитику
            await self._handle_analytics(session, webapp_data)
            
            # Логируем взаимодействие
            log_webapp_interaction(user_id, webapp_data.get('action', 'unknown'), webapp_data)
            
            # Метрики производительности
            processing_time = time.time() - start_time
            log_performance_metric("webapp_request_processing", processing_time * 1000, "ms")
            
            self.total_commands += 1
            
        except Exception as e:
            self.total_errors += 1
            self.logger.error(f"❌ Ошибка обработки WebApp данных: {e}")
            
            # Отправляем ошибку пользователю
            try:
                await self.bot.bot.reply_to(
                    message,
                    f"❌ Ошибка обработки команды WebApp: {str(e)[:100]}"
                )
            except:
                pass
    
    def _validate_webapp_data(self, data: Dict[str, Any]) -> bool:
        """Валидация данных WebApp"""
        required_fields = ['action']
        
        # Проверяем обязательные поля
        for field in required_fields:
            if field not in data:
                self.logger.warning(f"⚠️ Отсутствует обязательное поле: {field}")
                return False
        
        # Проверяем типы данных
        if not isinstance(data.get('action'), str):
            return False
        
        # Проверяем длину данных
        data_str = json.dumps(data)
        if len(data_str) > 4096:  # Telegram ограничение
            self.logger.warning("⚠️ WebApp данные слишком большие")
            return False
        
        return True
    
    async def _get_or_create_session(self, user_id: int, group_id: int, 
                                   webapp_data: Dict[str, Any]) -> WebAppSession:
        """Получение или создание сессии пользователя"""
        
        # Ищем активную сессию пользователя
        user_sessions = self.sessions_by_user.get(user_id, [])
        for session_id in user_sessions:
            session = self.active_sessions.get(session_id)
            if session and not session.is_expired():
                session.update_activity()
                return session
        
        # Создаем новую сессию
        session_id = str(uuid.uuid4())
        session = WebAppSession(
            session_id=session_id,
            user_id=user_id,
            group_id=group_id or 0,
            created_at=time.time(),
            last_activity=time.time(),
            platform=webapp_data.get('platform', 'webapp')
        )
        
        # Сохраняем сессию
        self.active_sessions[session_id] = session
        if user_id not in self.sessions_by_user:
            self.sessions_by_user[user_id] = []
        self.sessions_by_user[user_id].append(session_id)
        
        self.total_sessions += 1
        
        # Генерируем событие
        if self.module_registry.event_dispatcher:
            await self.module_registry.event_dispatcher.emit(
                EventTypes.WEBAPP_SESSION_STARTED,
                {
                    'session_id': session_id,
                    'user_id': user_id,
                    'group_id': group_id,
                    'platform': session.platform
                }
            )
        
        self.logger.info(f"🆕 Создана WebApp сессия {session_id} для пользователя {user_id}")
        return session
    
    async def _handle_command(self, session: WebAppSession, command: str, 
                            data: Dict[str, Any], message):
        """Обработка команды от WebApp"""
        
        try:
            # Обновляем счетчик команд в сессии
            session.commands_sent += 1
            
            # Ищем зарегистрированный обработчик
            handler = self.command_handlers.get(command)
            if handler:
                await handler(session, data, message)
            else:
                # Пытаемся передать команду модулям
                await self._route_command_to_modules(session, command, data, message)
            
            # Генерируем событие
            if self.module_registry.event_dispatcher:
                await self.module_registry.event_dispatcher.emit(
                    EventTypes.WEBAPP_COMMAND_SENT,
                    {
                        'session_id': session.session_id,
                        'user_id': session.user_id,
                        'command': command,
                        'data': data
                    }
                )
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка обработки команды {command}: {e}")
            raise
    
    async def _route_command_to_modules(self, session: WebAppSession, command: str, 
                                      data: Dict[str, Any], message):
        """Маршрутизация команды к модулям"""
        
        # Таблица маршрутизации команд WebApp к модулям
        command_routes = {
            # Пользователи и карма
            'get_user_stats': 'user_management',
            'get_leaderboard': 'user_management',
            'update_profile': 'user_management',
            
            # Поддержка треков
            'get_recent_links': 'track_support_system',
            'submit_track': 'track_support_system',
            'get_my_tracks': 'track_support_system',
            
            # Навигация
            'get_navigation': 'navigation_system',
            'get_topics': 'navigation_system',
            
            # Формы (План 2)
            'create_support_request': 'interactive_forms',
            'submit_approval': 'interactive_forms',
            
            # Статистика (План 2)
            'get_detailed_stats': 'leaderboards',
            'get_charts': 'leaderboards',
            
            # ИИ (План 4)
            'ai_chat': 'ai_assistant',
            'ai_advice': 'ai_assistant',
            
            # Настройки модулей
            'get_module_settings': 'module_settings',
            'update_module_settings': 'module_settings'
        }
        
        # Определяем целевой модуль
        target_module = command_routes.get(command)
        if not target_module:
            raise WebAppDataError(f"Неизвестная команда WebApp: {command}")
        
        # Проверяем, что модуль запущен
        if not self.module_registry.is_module_running(target_module):
            raise WebAppError(f"Модуль {target_module} недоступен")
        
        # Получаем модуль
        module = self.module_registry.get_module(target_module)
        if not module:
            raise WebAppError(f"Модуль {target_module} не найден")
        
        # Проверяем, есть ли обработчик WebApp в модуле
        if hasattr(module, 'handle_webapp_command'):
            await module.handle_webapp_command(session, command, data, message)
        else:
            # Преобразуем в стандартную команду бота
            await self._convert_to_bot_command(session, command, data, message)
    
    async def _convert_to_bot_command(self, session: WebAppSession, command: str, 
                                    data: Dict[str, Any], message):
        """Преобразование команды WebApp в команду бота"""
        
        # Маппинг команд WebApp в команды бота
        command_mapping = {
            'get_user_stats': '/mystat',
            'get_leaderboard': '/top10',
            'get_recent_links': '/last10links',
            'get_detailed_stats': '/mystats',
            'get_navigation': '/help'
        }
        
        bot_command = command_mapping.get(command)
        if not bot_command:
            raise WebAppDataError(f"Нет маппинга для команды {command}")
        
        # Имитируем сообщение с командой
        try:
            # Создаем фейковое сообщение для обработки командой бота
            fake_message = type('FakeMessage', (), {
                'from_user': message.from_user,
                'chat': message.chat,
                'text': bot_command,
                'message_id': message.message_id + 1
            })()
            
            # Находим обработчик команды в боте
            command_name = bot_command[1:]  # Убираем '/'
            handler = self.bot.command_handlers.get(command_name)
            
            if handler:
                await handler(fake_message)
            else:
                await self.bot.bot.reply_to(
                    message,
                    f"⚙️ Команда {bot_command} обрабатывается..."
                )
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка преобразования команды {command}: {e}")
            raise
    
    async def _handle_analytics(self, session: WebAppSession, data: Dict[str, Any]):
        """Обработка аналитических данных"""
        
        # Сохраняем аналитику в сессии
        analytics = data.get('analytics', {})
        if analytics:
            session.data.setdefault('analytics', []).append({
                'timestamp': time.time(),
                'data': analytics
            })
        
        # Сохраняем в базу данных (если модуль доступен)
        try:
            async with self.database.get_async_session() as db_session:
                # Здесь можно сохранить аналитику в таблицу webapp_analytics
                # Реализация зависит от схемы БД
                pass
        except Exception as e:
            self.logger.warning(f"⚠️ Не удалось сохранить аналитику WebApp: {e}")
    
    def _register_default_commands(self):
        """Регистрация стандартных команд WebApp"""
        
        async def handle_ping(session: WebAppSession, data: Dict[str, Any], message):
            """Обработка ping от WebApp"""
            await self.bot.bot.reply_to(
                message,
                json.dumps({
                    "action": "pong",
                    "session_id": session.session_id,
                    "server_time": time.time()
                })
            )
        
        async def handle_get_stats(session: WebAppSession, data: Dict[str, Any], message):
            """Получение статистики для WebApp"""
            stats = {
                "user_id": session.user_id,
                "session_duration": time.time() - session.created_at,
                "commands_sent": session.commands_sent,
                "server_time": time.time()
            }
            
            await self.bot.bot.reply_to(
                message,
                json.dumps({
                    "action": "stats_response",
                    "data": stats
                })
            )
        
        # Регистрируем обработчики
        self.command_handlers['ping'] = handle_ping
        self.command_handlers['get_stats'] = handle_get_stats
    
    def register_command_handler(self, command: str, handler: Callable):
        """Регистрация обработчика команды WebApp"""
        self.command_handlers[command] = handler
        self.logger.debug(f"📝 Зарегистрирован обработчик WebApp команды: {command}")
    
    async def _cleanup_expired_sessions(self):
        """Очистка истекших сессий"""
        while True:
            try:
                current_time = time.time()
                expired_sessions = []
                
                # Находим истекшие сессии
                for session_id, session in self.active_sessions.items():
                    if session.is_expired():
                        expired_sessions.append(session_id)
                
                # Удаляем истекшие сессии
                for session_id in expired_sessions:
                    session = self.active_sessions.pop(session_id, None)
                    if session:
                        # Удаляем из индекса по пользователям
                        user_sessions = self.sessions_by_user.get(session.user_id, [])
                        if session_id in user_sessions:
                            user_sessions.remove(session_id)
                        
                        self.logger.debug(f"🧹 Удалена истекшая сессия {session_id}")
                
                # Спим 5 минут до следующей очистки
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Ошибка очистки сессий: {e}")
                await asyncio.sleep(60)  # Спим минуту при ошибке
    
    def get_session(self, session_id: str) -> Optional[WebAppSession]:
        """Получение сессии по ID"""
        return self.active_sessions.get(session_id)
    
    def get_user_sessions(self, user_id: int) -> List[WebAppSession]:
        """Получение всех сессий пользователя"""
        session_ids = self.sessions_by_user.get(user_id, [])
        sessions = []
        for session_id in session_ids:
            session = self.active_sessions.get(session_id)
            if session and not session.is_expired():
                sessions.append(session)
        return sessions
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики WebApp"""
        active_sessions_count = len(self.active_sessions)
        active_users = len([
            user_id for user_id, sessions in self.sessions_by_user.items()
            if any(not self.active_sessions[sid].is_expired() for sid in sessions if sid in self.active_sessions)
        ])
        
        return {
            "total_sessions": self.total_sessions,
            "active_sessions": active_sessions_count,
            "active_users": active_users,
            "total_commands": self.total_commands,
            "total_errors": self.total_errors,
            "error_rate": self.total_errors / max(self.total_commands, 1),
            "registered_commands": len(self.command_handlers)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья WebApp интеграции"""
        try:
            stats = self.get_stats()
            
            return {
                "healthy": True,
                "active_sessions": stats["active_sessions"],
                "active_users": stats["active_users"],
                "error_rate": stats["error_rate"],
                "cleanup_task_running": self.cleanup_task and not self.cleanup_task.done()
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    async def cleanup(self):
        """Очистка ресурсов"""
        self.logger.info("🔄 Очистка WebApp обработчика...")
        
        # Останавливаем задачу очистки
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Очищаем сессии
        self.active_sessions.clear()
        self.sessions_by_user.clear()
        
        self.logger.info("✅ WebApp обработчик очищен")


if __name__ == "__main__":
    # Тестирование WebApp обработчика
    async def test_webapp_handler():
        print("🧪 Тестирование WebApp обработчика...")
        
        # Мок объекты
        class MockBot:
            def register_webapp_handler(self, handler):
                pass
        
        class MockRegistry:
            event_dispatcher = None
        
        class MockDatabase:
            async def get_async_session(self):
                return None
        
        # Создаем обработчик
        handler = WebAppHandler(MockBot(), MockRegistry(), MockDatabase())
        await handler.initialize()
        
        # Тестовые данные
        test_data = {
            "action": "test_command",
            "command": "ping",
            "platform": "webapp"
        }
        
        # Мок сообщения
        class MockMessage:
            class MockUser:
                id = 12345
            
            class MockChat:
                id = -1001234567890
            
            from_user = MockUser()
            chat = MockChat()
        
        # Тестируем обработку
        try:
            await handler.handle_webapp_data(MockMessage(), test_data)
            print("✅ Обработка данных WebApp работает")
        except Exception as e:
            print(f"❌ Ошибка обработки: {e}")
        
        # Показываем статистику
        stats = handler.get_stats()
        print(f"📊 Статистика: {stats}")
        
        # Проверяем здоровье
        health = await handler.health_check()
        print(f"🏥 Здоровье: {health}")
        
        await handler.cleanup()
        print("✅ Тестирование завершено")
    
    asyncio.run(test_webapp_handler())