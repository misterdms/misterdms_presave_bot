"""
Core/bot_instance.py - Экземпляр Telegram бота
Do Presave Reminder Bot v29.07

Управление экземпляром Telegram бота с WebApp интеграцией и модульной архитектурой
"""

import asyncio
import logging
import traceback
import time
from typing import Dict, Any, Optional, List, Callable
import json

try:
    import telebot
    from telebot.async_telebot import AsyncTeleBot
    from telebot.types import (
        Message, CallbackQuery, InlineQuery, 
        WebAppInfo, MenuButtonWebApp, BotCommand
    )
    from telebot import asyncio_filters
    from telebot.asyncio_storage import StateMemoryStorage
except ImportError as e:
    raise ImportError(f"pyTelegramBotAPI не установлен: {e}")

from config.settings import Settings
from utils.logger import get_logger
from core.interfaces import EventTypes
from core.exceptions import BotInitializationError


class BotInstance:
    """Экземпляр Telegram бота с модульной архитектурой"""
    
    def __init__(self, settings: Settings):
        """
        Инициализация экземпляра бота
        
        Args:
            settings: Настройки системы
        """
        self.settings = settings
        self.logger = get_logger(__name__)
        
        # Telegram bot
        self.bot: Optional[AsyncTeleBot] = None
        self.bot_info: Optional[Dict[str, Any]] = None
        
        # WebApp интеграция
        self.webapp_url = settings.webapp.url
        self.webapp_short_name = settings.webapp.short_name
        
        # Обработчики модулей
        self.command_handlers: Dict[str, Callable] = {}
        self.message_handlers: List[Callable] = []
        self.callback_handlers: Dict[str, Callable] = {}
        self.webapp_handlers: List[Callable] = []
        
        # Статистика и мониторинг
        self.start_time = time.time()
        self.message_count = 0
        self.command_count = 0
        self.error_count = 0
        self.webhook_info = None
        
        # Состояние
        self.is_running = False
        self.is_polling = False
        
    async def initialize(self) -> bool:
        """Инициализация бота"""
        try:
            self.logger.info("🤖 Инициализация Telegram бота...")
            
            # Создание экземпляра бота
            self.bot = AsyncTeleBot(
                token=self.settings.telegram.bot_token,
                state_storage=StateMemoryStorage()
            )
            
            # Добавление фильтров
            self.bot.add_custom_filter(asyncio_filters.StateFilter(self.bot))
            self.bot.add_custom_filter(asyncio_filters.IsDigitFilter())
            self.bot.add_custom_filter(asyncio_filters.ForwardFilter())
            self.bot.add_custom_filter(asyncio_filters.IsReplyFilter())
            
            # Получение информации о боте
            await self._get_bot_info()
            
            # Настройка WebApp
            await self._setup_webapp()
            
            # Регистрация базовых обработчиков
            await self._setup_base_handlers()
            
            # Настройка команд бота
            await self._setup_bot_commands()
            
            self.logger.info(f"✅ Telegram бот инициализирован: @{self.bot_info.get('username', 'unknown')}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации бота: {e}")
            self.logger.error(traceback.format_exc())
            raise BotInitializationError(f"Не удалось инициализировать бота: {e}")
    
    async def _get_bot_info(self):
        """Получение информации о боте"""
        try:
            bot_info = await self.bot.get_me()
            self.bot_info = {
                'id': bot_info.id,
                'username': bot_info.username,
                'first_name': bot_info.first_name,
                'is_bot': bot_info.is_bot,
                'can_join_groups': bot_info.can_join_groups,
                'can_read_all_group_messages': bot_info.can_read_all_group_messages,
                'supports_inline_queries': bot_info.supports_inline_queries
            }
            
            self.logger.info(f"📱 Бот: @{self.bot_info['username']} (ID: {self.bot_info['id']})")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения информации о боте: {e}")
            raise
    
    async def _setup_webapp(self):
        """Настройка WebApp интеграции"""
        try:
            if not self.webapp_url:
                self.logger.warning("⚠️ WEBAPP_URL не установлен, WebApp недоступен")
                return
            
            # Создание WebApp кнопки в меню
            webapp_info = WebAppInfo(url=self.webapp_url)
            menu_button = MenuButtonWebApp(
                type='web_app',
                text='📖 О боте',
                web_app=webapp_info
            )
            
            # Установка кнопки меню (только для приватных чатов)
            await self.bot.set_chat_menu_button(
                menu_button=menu_button
            )
            
            self.logger.info(f"🌐 WebApp настроен: {self.webapp_url}")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка настройки WebApp: {e}")
            # WebApp не критичен для работы бота
    
    async def _setup_base_handlers(self):
        """Регистрация базовых обработчиков"""
        
        # Обработчик команды /start
        @self.bot.message_handler(commands=['start'])
        async def handle_start(message: Message):
            await self._handle_start_command(message)
        
        # Обработчик команды /help
        @self.bot.message_handler(commands=['help'])
        async def handle_help(message: Message):
            await self._handle_help_command(message)
        
        # Обработчик WebApp данных
        @self.bot.message_handler(content_types=['web_app_data'])
        async def handle_webapp_data(message: Message):
            await self._handle_webapp_data(message)
        
        # Обработчик callback query
        @self.bot.callback_query_handler(func=lambda call: True)
        async def handle_callback_query(call: CallbackQuery):
            await self._handle_callback_query(call)
        
        # Обработчик ошибок
        @self.bot.middleware_handler(update_types=['message'])
        async def error_middleware(bot_instance, message: Message):
            try:
                await bot_instance.process_new_messages([message])
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"❌ Ошибка обработки сообщения: {e}")
                self.logger.error(traceback.format_exc())
                
                # Отправляем сообщение об ошибке пользователю
                try:
                    await self.bot.reply_to(
                        message,
                        "🚫 Произошла ошибка при обработке вашего сообщения. "
                        "Попробуйте позже или обратитесь к администратору."
                    )
                except:
                    pass  # Если даже ответ не удается отправить
        
        # Глобальный обработчик сообщений (для статистики)
        @self.bot.message_handler(func=lambda message: True)
        async def handle_all_messages(message: Message):
            self.message_count += 1
            
            # Логируем активность в группе
            if message.chat.id == self.settings.group_id:
                self.logger.debug(f"📝 Сообщение от @{message.from_user.username or 'unknown'} в группе")
    
    async def _setup_bot_commands(self):
        """Настройка команд бота в меню Telegram"""
        commands = [
            BotCommand("start", "🎯 Начать работу с ботом"),
            BotCommand("help", "❓ Помощь и список команд"),
            BotCommand("mystat", "📊 Моя статистика и карма"),
            BotCommand("mystats", "📈 Подробная статистика"),
            BotCommand("last10links", "🔗 Последние 10 ссылок"),
            BotCommand("top10", "🏆 ТОП-10 по карме"),
            BotCommand("leaderboard", "🏅 Полный рейтинг"),
            BotCommand("donate", "💝 Поддержать проект"),
        ]
        
        try:
            await self.bot.set_my_commands(commands)
            self.logger.info(f"⚙️ Настроено {len(commands)} команд в меню")
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка настройки команд: {e}")
    
    async def _handle_start_command(self, message: Message):
        """Обработка команды /start"""
        user = message.from_user
        
        welcome_text = f"""🎵 **Привет, {user.first_name}!**

Добро пожаловать в Do Presave Reminder Bot!

🎯 **Что я умею:**
• Помогаю музыкантам находить поддержку для треков
• Веду систему кармы за взаимопомощь  
• Напоминаю о пресейвах и бустах
• Показываю статистику и рейтинги

🌐 **WebApp:** Нажми кнопку "📖 О боте" в меню

⌨️ **Основные команды:**
/help - Полный список команд
/mystat - Твоя статистика
/last10links - Последние ссылки
/top10 - ТОП-10 участников

🎵 Присоединяйся к музыкальному сообществу и развивай карьеру вместе!"""
        
        try:
            await self.bot.reply_to(message, welcome_text, parse_mode='Markdown')
            self.logger.info(f"👋 Новый пользователь: @{user.username or 'unknown'} ({user.id})")
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки приветствия: {e}")
    
    async def _handle_help_command(self, message: Message):
        """Обработка команды /help"""
        help_text = """📖 **Справка по командам**

🎯 **ОСНОВНЫЕ КОМАНДЫ:**
/mystat - Моя статистика и карма
/mystats - Подробная статистика
/last10links - Последние 10 ссылок для поддержки
/top10 - ТОП-10 участников по карме
/leaderboard - Полный рейтинг сообщества

🔗 **ПОДДЕРЖКА ТРЕКОВ:**
Просто отправь ссылку на пресейв или стрим в соответствующий топик

💝 **БЛАГОДАРНОСТИ:**
Спасибо @username - поблагодарить участника

🌐 **WEBAPP:**
Нажми "📖 О боте" в меню для полного интерфейса

📞 **ПОДДЕРЖКА:**
@misterdms_presave_bot - обратиться к боту
/donate - поддержать развитие проекта

🎵 **Удачи в продвижении музыки!**"""
        
        try:
            await self.bot.reply_to(message, help_text, parse_mode='Markdown')
        except Exception as e:
            self.logger.error(f"❌ Ошибка отправки справки: {e}")
    
    async def _handle_webapp_data(self, message: Message):
        """Обработка данных от WebApp"""
        try:
            webapp_data = json.loads(message.web_app_data.data)
            self.logger.info(f"🌐 WebApp данные от {message.from_user.id}: {webapp_data}")
            
            # Передаем данные зарегистрированным обработчикам
            for handler in self.webapp_handlers:
                try:
                    await handler(message, webapp_data)
                except Exception as e:
                    self.logger.error(f"❌ Ошибка в WebApp обработчике: {e}")
            
            # Подтверждение получения
            await self.bot.reply_to(
                message,
                "✅ Команда от WebApp получена и обработана!"
            )
            
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Ошибка парсинга WebApp данных: {e}")
            await self.bot.reply_to(
                message,
                "❌ Ошибка обработки данных от WebApp"
            )
        except Exception as e:
            self.logger.error(f"❌ Ошибка обработки WebApp данных: {e}")
    
    async def _handle_callback_query(self, call: CallbackQuery):
        """Обработка callback query"""
        try:
            # Пытаемся найти зарегистрированный обработчик
            handler = self.callback_handlers.get(call.data)
            if handler:
                await handler(call)
            else:
                # Стандартная обработка
                await self.bot.answer_callback_query(
                    call.id,
                    "⚙️ Функция в разработке"
                )
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка обработки callback: {e}")
            try:
                await self.bot.answer_callback_query(
                    call.id,
                    "❌ Ошибка обработки"
                )
            except:
                pass
    
    # === МЕТОДЫ РЕГИСТРАЦИИ ОБРАБОТЧИКОВ ===
    
    def register_command_handler(self, command: str, handler: Callable):
        """Регистрация обработчика команды"""
        self.command_handlers[command] = handler
        
        # Регистрируем в telebot
        @self.bot.message_handler(commands=[command])
        async def command_wrapper(message: Message):
            self.command_count += 1
            try:
                await handler(message)
            except Exception as e:
                self.logger.error(f"❌ Ошибка в обработчике команды /{command}: {e}")
                await self.bot.reply_to(
                    message,
                    f"❌ Ошибка выполнения команды /{command}"
                )
        
        self.logger.debug(f"📝 Зарегистрирован обработчик команды: /{command}")
    
    def register_message_handler(self, handler: Callable, **kwargs):
        """Регистрация обработчика сообщений"""
        self.message_handlers.append(handler)
        self.bot.message_handler(**kwargs)(handler)
        self.logger.debug(f"📝 Зарегистрирован обработчик сообщений")
    
    def register_callback_handler(self, callback_data: str, handler: Callable):
        """Регистрация обработчика callback query"""
        self.callback_handlers[callback_data] = handler
        self.logger.debug(f"📝 Зарегистрирован обработчик callback: {callback_data}")
    
    def register_webapp_handler(self, handler: Callable):
        """Регистрация обработчика WebApp данных"""
        self.webapp_handlers.append(handler)
        self.logger.debug(f"📝 Зарегистрирован обработчик WebApp")
    
    # === МЕТОДЫ УПРАВЛЕНИЯ ===
    
    async def start_polling(self):
        """Запуск поллинга"""
        if self.is_polling:
            self.logger.warning("⚠️ Поллинг уже запущен")
            return
        
        try:
            self.is_polling = True
            self.is_running = True
            
            self.logger.info("🚀 Запуск поллинга Telegram API...")
            
            await self.bot.infinity_polling(
                timeout=self.settings.telegram.polling_timeout,
                long_polling_timeout=self.settings.telegram.polling_timeout,
                logger_level=logging.ERROR,  # Снижаем уровень логов telebot
                allowed_updates=['message', 'callback_query', 'inline_query']
            )
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка поллинга: {e}")
            self.is_polling = False
            self.is_running = False
            raise
    
    async def stop(self):
        """Остановка бота"""
        self.logger.info("🔄 Остановка Telegram бота...")
        
        self.is_running = False
        self.is_polling = False
        
        if self.bot:
            try:
                await self.bot.close_session()
                self.logger.info("✅ Telegram бот остановлен")
            except Exception as e:
                self.logger.error(f"❌ Ошибка остановки бота: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья бота"""
        try:
            # Простая проверка API
            if self.bot:
                await self.bot.get_me()
                api_status = "healthy"
            else:
                api_status = "not_initialized"
            
            uptime = time.time() - self.start_time
            
            return {
                "healthy": self.is_running and api_status == "healthy",
                "api_status": api_status,
                "is_polling": self.is_polling,
                "uptime_seconds": uptime,
                "message_count": self.message_count,
                "command_count": self.command_count,
                "error_count": self.error_count,
                "registered_commands": len(self.command_handlers),
                "registered_handlers": len(self.message_handlers),
                "webapp_url": self.webapp_url
            }
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка health check: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "uptime_seconds": time.time() - self.start_time
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики бота"""
        return {
            "bot_info": self.bot_info,
            "uptime_seconds": time.time() - self.start_time,
            "message_count": self.message_count,
            "command_count": self.command_count,
            "error_count": self.error_count,
            "is_running": self.is_running,
            "is_polling": self.is_polling,
            "webapp_configured": bool(self.webapp_url),
            "handlers_count": {
                "commands": len(self.command_handlers),
                "messages": len(self.message_handlers),
                "callbacks": len(self.callback_handlers),
                "webapp": len(self.webapp_handlers)
            }
        }