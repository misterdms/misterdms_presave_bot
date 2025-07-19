"""
Modules/user_management/module.py - Модуль управления пользователями
Do Presave Reminder Bot v29.07

МОДУЛЬ 1: Управление пользователями-музыкантами, система кармы, звания, онбординг
Приоритет: 1 (критически важный)
"""

import asyncio
import re
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta

from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from core.interfaces import BaseModule, ModuleInfo, EventTypes, log_execution_time, rate_limit
from core.exceptions import UserError, UserNotFoundError, KarmaError, ValidationError
from utils.logger import get_module_logger, log_user_action, log_command_execution


class UserManagementModule(BaseModule):
    """Модуль управления пользователями и системы кармы"""
    
    def __init__(self, bot, database, config, event_dispatcher=None):
        """Инициализация модуля"""
        super().__init__(bot, database, config, event_dispatcher)
        self.logger = get_module_logger("user_management")
        
        # Сессии онбординга
        self.onboarding_sessions: Dict[int, Dict[str, Any]] = {}
        
        # Кулдауны команд
        self.command_cooldowns: Dict[int, Dict[str, float]] = {}
        
        # Настройки кармы из конфигурации
        self.karma_settings = {
            'max_karma': 100500,
            'min_karma': 0,
            'admin_karma': 100500,
            'newbie_karma': 0,
            'cooldown_seconds': config.get('karma_cooldown_seconds', 60),
            'gratitude_cooldown_minutes': config.get('gratitude_cooldown_minutes', 60)
        }
        
        # Система званий
        self.rank_thresholds = {
            'Новенький': (0, 5),
            'Надежда сообщества': (6, 15), 
            'Мега-помощничье': (16, 30),
            'Амбассадорище': (31, 100500)
        }
        
    def get_info(self) -> ModuleInfo:
        """Информация о модуле"""
        return ModuleInfo(
            name="user_management",
            version="1.0.0", 
            description="Управление пользователями, карма, звания, онбординг",
            author="Mister DMS",
            dependencies=[],
            plan=1,
            priority=1
        )
    
    async def initialize(self) -> bool:
        """Инициализация модуля"""
        try:
            self.logger.info("🔧 Инициализация модуля управления пользователями...")
            
            # Создаем таблицы в БД
            await self._ensure_database_tables()
            
            # Обновляем карму админов
            await self._update_admin_karma()
            
            self.logger.info("✅ Модуль управления пользователями инициализирован")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации модуля: {e}")
            return False
    
    async def start(self) -> bool:
        """Запуск модуля"""
        try:
            self.logger.info("🚀 Запуск модуля управления пользователями...")
            
            # Запускаем задачу очистки старых сессий
            cleanup_task = asyncio.create_task(self._cleanup_old_sessions())
            self._tasks.append(cleanup_task)
            
            self.logger.info("✅ Модуль управления пользователями запущен")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка запуска модуля: {e}")
            return False
    
    async def stop(self) -> bool:
        """Остановка модуля"""
        try:
            self.logger.info("🛑 Остановка модуля управления пользователей...")
            
            # Очищаем состояния
            self.onboarding_sessions.clear()
            self.command_cooldowns.clear()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка остановки модуля: {e}")
            return False
    
    def register_handlers(self):
        """Регистрация обработчиков команд"""
        
        # Основные команды пользователей
        self.bot.register_command_handler('start', self._handle_start)
        self.bot.register_command_handler('mystat', self._handle_mystat)
        self.bot.register_command_handler('mystats', self._handle_mystats)
        self.bot.register_command_handler('profile', self._handle_profile)
        self.bot.register_command_handler('karma_history', self._handle_karma_history)
        
        # Админские команды кармы
        self.bot.register_command_handler('karma', self._handle_karma_admin)
        self.bot.register_command_handler('karma_ratio', self._handle_karma_ratio_admin)
        
        # Обработчики callback query для онбординга
        self.bot.register_callback_handler('onboarding_', self._handle_onboarding_callback)
        self.bot.register_callback_handler('genre_', self._handle_genre_selection)
        
        # Обработчик благодарностей
        self.bot.register_message_handler(
            self._handle_gratitude_message,
            func=lambda message: self._is_gratitude_message(message)
        )
        
        # Команды в списке
        self._commands = ['start', 'mystat', 'mystats', 'profile', 'karma_history', 'karma', 'karma_ratio']
        
        self.logger.info(f"📝 Зарегистрировано {len(self._commands)} команд")
    
    # === ОБРАБОТЧИКИ КОМАНД ===
    
    @log_execution_time("start_command")
    async def _handle_start(self, message: Message):
        """Обработчик команды /start - онбординг"""
        try:
            user_id = message.from_user.id
            group_id = getattr(message.chat, 'id', None)
            
            # Проверяем, зарегистрирован ли пользователь
            async with self.database.get_async_session() as session:
                from .models import MusicUser
                
                existing_user = await session.get(MusicUser, user_id)
                if existing_user:
                    # Пользователь уже зарегистрирован
                    await self.bot.bot.reply_to(
                        message,
                        f"👋 Привет, {message.from_user.first_name}!\n\n"
                        f"Ты уже зарегистрирован в системе.\n"
                        f"🏆 Твоя карма: {existing_user.karma_points}\n"
                        f"🎵 Звание: {existing_user.rank_title}\n\n"
                        f"Используй /mystat для подробной статистики."
                    )
                    return
            
            # Начинаем онбординг
            await self._start_onboarding(message)
            
            log_user_action(user_id, "start_onboarding", {"group_id": group_id})
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /start: {e}")
            await self.bot.bot.reply_to(
                message,
                "❌ Произошла ошибка при регистрации. Попробуйте позже."
            )
    
    @rate_limit(calls_per_minute=30)
    async def _handle_mystat(self, message: Message):
        """Обработчик команды /mystat - личная статистика"""
        try:
            user_id = message.from_user.id
            
            # Получаем данные пользователя
            user = await self._get_user(user_id)
            if not user:
                await self.bot.bot.reply_to(
                    message,
                    "👤 Вы не зарегистрированы в системе.\n"
                    "Нажмите /start для регистрации."
                )
                return
            
            # Формируем статистику
            stats_text = await self._format_user_stats(user)
            
            await self.bot.bot.reply_to(message, stats_text, parse_mode='Markdown')
            
            log_command_execution(user_id, "mystat", success=True)
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /mystat: {e}")
            log_command_execution(message.from_user.id, "mystat", success=False, error=str(e))
    
    @rate_limit(calls_per_minute=20)
    async def _handle_mystats(self, message: Message):
        """Обработчик команды /mystats - подробная статистика"""
        try:
            user_id = message.from_user.id
            
            user = await self._get_user(user_id)
            if not user:
                await self.bot.bot.reply_to(
                    message,
                    "👤 Вы не зарегистрированы в системе."
                )
                return
            
            # Получаем подробную статистику
            detailed_stats = await self._get_detailed_user_stats(user)
            
            await self.bot.bot.reply_to(message, detailed_stats, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /mystats: {e}")
    
    async def _handle_profile(self, message: Message):
        """Обработчик команды /profile - профиль пользователя"""
        try:
            user_id = message.from_user.id
            
            user = await self._get_user(user_id)
            if not user:
                await self.bot.bot.reply_to(message, "👤 Пользователь не найден.")
                return
            
            profile_text = await self._format_user_profile(user)
            
            # Кнопки управления профилем
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🎵 Сменить жанр", callback_data="change_genre"),
                InlineKeyboardButton("📊 Статистика", callback_data="show_stats")
            )
            
            await self.bot.bot.reply_to(
                message, 
                profile_text, 
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /profile: {e}")
    
    async def _handle_karma_history(self, message: Message):
        """Обработчик команды /karma_history - история изменений кармы"""
        try:
            user_id = message.from_user.id
            
            history = await self._get_karma_history(user_id, limit=10)
            
            if not history:
                await self.bot.bot.reply_to(
                    message,
                    "📈 История изменений кармы пуста."
                )
                return
            
            history_text = "📈 **История изменений кармы (последние 10):**\n\n"
            
            for entry in history:
                change_icon = "📈" if entry['change'] > 0 else "📉"
                history_text += (
                    f"{change_icon} `{entry['change']:+d}` карма\n"
                    f"💬 {entry['reason']}\n"
                    f"📅 {entry['date']}\n\n"
                )
            
            await self.bot.bot.reply_to(message, history_text, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /karma_history: {e}")
    
    # === АДМИНСКИЕ КОМАНДЫ КАРМЫ ===
    
    async def _handle_karma_admin(self, message: Message):
        """Обработчик команды /karma (только админы)"""
        try:
            # Проверяем права админа
            if not self._is_admin(message.from_user.id):
                return  # Игнорируем команду для не-админов
            
            parts = message.text.split()
            
            if len(parts) < 2:
                await self._send_karma_help(message)
                return
            
            # Извлекаем упоминание пользователя
            target_mention = parts[1]
            if not target_mention.startswith('@'):
                await self._send_karma_help(message)
                return
            
            target_username = target_mention[1:]  # Убираем @
            
            if len(parts) == 2:
                # Просто показать карму
                await self._show_user_karma(message, target_username)
            else:
                # Изменение кармы
                operation = parts[2]
                await self._change_user_karma(message, target_username, operation)
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /karma: {e}")
    
    async def _handle_karma_ratio_admin(self, message: Message):
        """Обработчик команды /karma_ratio (только админы)"""
        try:
            if not self._is_admin(message.from_user.id):
                return
            
            parts = message.text.split()
            
            if len(parts) < 2:
                await self._send_karma_ratio_help(message)
                return
            
            target_mention = parts[1]
            if not target_mention.startswith('@'):
                await self._send_karma_ratio_help(message)
                return
            
            target_username = target_mention[1:]
            
            if len(parts) == 2:
                # Показать текущее соотношение
                await self._show_karma_ratio(message, target_username)
            else:
                # Изменить соотношение
                ratio_str = parts[2]
                await self._change_karma_ratio(message, target_username, ratio_str)
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /karma_ratio: {e}")
    
    # === ОБРАБОТЧИКИ БЛАГОДАРНОСТЕЙ ===
    
    async def _handle_gratitude_message(self, message: Message):
        """Обработчик сообщений с благодарностями"""
        try:
            # Проверяем кулдаун
            if not self._check_gratitude_cooldown(message.from_user.id):
                return
            
            # Извлекаем упоминания пользователей
            mentions = self._extract_mentions(message.text)
            if not mentions:
                return
            
            giver_id = message.from_user.id
            
            # Начисляем карму каждому упомянутому пользователю
            for username in mentions:
                await self._give_gratitude_karma(giver_id, username, message.text)
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка обработки благодарности: {e}")
    
    # === ОНБОРДИНГ ===
    
    async def _start_onboarding(self, message: Message):
        """Начало процесса онбординга"""
        user_id = message.from_user.id
        
        # Сохраняем сессию онбординга
        self.onboarding_sessions[user_id] = {
            'step': 'welcome',
            'started_at': time.time(),
            'user_data': {
                'user_id': user_id,
                'username': message.from_user.username,
                'first_name': message.from_user.first_name,
                'last_name': message.from_user.last_name
            }
        }
        
        welcome_text = (
            f"🎵 **Добро пожаловать, {message.from_user.first_name}!**\n\n"
            f"Я Do Presave Reminder Bot — помогаю музыкантам "
            f"находить поддержку и развивать карьеру!\n\n"
            f"🎯 **Что я умею:**\n"
            f"• Веду систему кармы за взаимопомощь\n"
            f"• Помогаю найти поддержку для треков\n"
            f"• Напоминаю о пресейвах и бустах\n"
            f"• Показываю статистику и рейтинги\n\n"
            f"🚀 Готов зарегистрироваться?"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("✅ Да, регистрируюсь!", callback_data="onboarding_start"),
            InlineKeyboardButton("❌ Отмена", callback_data="onboarding_cancel")
        )
        
        await self.bot.bot.reply_to(
            message,
            welcome_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    async def _handle_onboarding_callback(self, call: CallbackQuery):
        """Обработчик callback для онбординга"""
        try:
            user_id = call.from_user.id
            action = call.data.replace('onboarding_', '')
            
            if user_id not in self.onboarding_sessions:
                await self.bot.bot.answer_callback_query(
                    call.id,
                    "❌ Сессия онбординга истекла. Нажмите /start"
                )
                return
            
            if action == 'start':
                await self._onboarding_choose_genre(call)
            elif action == 'cancel':
                await self._onboarding_cancel(call)
                
            await self.bot.bot.answer_callback_query(call.id)
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка onboarding callback: {e}")
    
    async def _onboarding_choose_genre(self, call: CallbackQuery):
        """Выбор музыкального жанра"""
        user_id = call.from_user.id
        self.onboarding_sessions[user_id]['step'] = 'genre'
        
        genre_text = (
            "🎵 **Выбери свой основной музыкальный жанр:**\n\n"
            "Это поможет другим музыкантам найти единомышленников "
            "и лучше понимать твою музыку."
        )
        
        # Кнопки жанров
        keyboard = InlineKeyboardMarkup()
        genres = [
            ('🎸 Рок', 'rock'), ('🎤 Поп', 'pop'), ('🎵 Хип-хоп', 'hiphop'),
            ('🎹 Электронная', 'electronic'), ('🎺 Джаз', 'jazz'), ('🎻 Классика', 'classical'),
            ('🪕 Фолк', 'folk'), ('🎸 Блюз', 'blues'), ('🥁 Другое', 'other')
        ]
        
        for i in range(0, len(genres), 2):
            row = []
            for j in range(2):
                if i + j < len(genres):
                    name, code = genres[i + j]
                    row.append(InlineKeyboardButton(name, callback_data=f"genre_{code}"))
            keyboard.row(*row)
        
        keyboard.row(InlineKeyboardButton("⬅️ Назад", callback_data="onboarding_back"))
        
        await self.bot.bot.edit_message_text(
            genre_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    async def _handle_genre_selection(self, call: CallbackQuery):
        """Обработчик выбора жанра"""
        try:
            user_id = call.from_user.id
            genre_code = call.data.replace('genre_', '')
            
            if user_id not in self.onboarding_sessions:
                await self.bot.bot.answer_callback_query(call.id, "Сессия истекла")
                return
            
            # Маппинг кодов в названия
            genre_names = {
                'rock': 'Рок', 'pop': 'Поп', 'hiphop': 'Хип-хоп',
                'electronic': 'Электронная музыка', 'jazz': 'Джаз',
                'classical': 'Классическая музыка', 'folk': 'Фолк',
                'blues': 'Блюз', 'other': 'Другое'
            }
            
            genre_name = genre_names.get(genre_code, 'Не указан')
            
            # Сохраняем жанр
            self.onboarding_sessions[user_id]['user_data']['music_genre'] = genre_name
            
            # Завершаем регистрацию
            await self._complete_onboarding(call, genre_name)
            
            await self.bot.bot.answer_callback_query(call.id)
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка выбора жанра: {e}")
    
    async def _complete_onboarding(self, call: CallbackQuery, genre: str):
        """Завершение онбординга"""
        try:
            user_id = call.from_user.id
            session = self.onboarding_sessions[user_id]
            user_data = session['user_data']
            
            # Создаем пользователя в БД
            async with self.database.get_async_session() as db_session:
                from .models import MusicUser
                
                new_user = MusicUser(
                    user_id=user_data['user_id'],
                    group_id=call.message.chat.id,
                    username=user_data.get('username'),
                    first_name=user_data.get('first_name'),
                    last_name=user_data.get('last_name'),
                    music_genre=genre,
                    karma_points=self.karma_settings['newbie_karma'],
                    rank_title=self._get_rank_title(self.karma_settings['newbie_karma']),
                    is_admin=self._is_admin(user_id)
                )
                
                db_session.add(new_user)
                await db_session.commit()
            
            # Если админ, устанавливаем админскую карму
            if self._is_admin(user_id):
                await self._set_user_karma(user_id, self.karma_settings['admin_karma'], "Админские права")
            
            success_text = (
                f"🎉 **Регистрация завершена!**\n\n"
                f"👤 **Имя:** {user_data.get('first_name', 'Не указано')}\n"
                f"🎵 **Жанр:** {genre}\n"
                f"🏆 **Стартовая карма:** {self.karma_settings['newbie_karma']}\n"
                f"🎖️ **Звание:** {self._get_rank_title(self.karma_settings['newbie_karma'])}\n\n"
                f"🚀 **Что дальше?**\n"
                f"• Используй /mystat для просмотра статистики\n"
                f"• Публикуй ссылки на поддержку в топике #3\n"
                f"• Поддерживай других музыкантов\n"
                f"• Благодари участников за помощь\n\n"
                f"🎵 Добро пожаловать в музыкальное сообщество!"
            )
            
            await self.bot.bot.edit_message_text(
                success_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
            
            # Удаляем сессию
            del self.onboarding_sessions[user_id]
            
            # Генерируем событие
            if self.event_dispatcher:
                await self.event_dispatcher.emit(
                    EventTypes.USER_REGISTERED,
                    {
                        'user_id': user_id,
                        'username': user_data.get('username'),
                        'genre': genre,
                        'karma': self.karma_settings['newbie_karma']
                    }
                )
            
            log_user_action(user_id, "registration_completed", {
                'genre': genre,
                'karma': self.karma_settings['newbie_karma']
            })
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка завершения онбординга: {e}")
    
    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    
    async def _get_user(self, user_id: int):
        """Получение пользователя из БД"""
        try:
            async with self.database.get_async_session() as session:
                from .models import MusicUser
                user = await session.get(MusicUser, user_id)
                return user
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения пользователя {user_id}: {e}")
            return None
    
    def _is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        # Получаем список админов из настроек
        admin_ids = getattr(self.config, 'admin_ids', [])
        return user_id in admin_ids
    
    def _get_rank_title(self, karma: int) -> str:
        """Получение звания по карме"""
        for title, (min_karma, max_karma) in self.rank_thresholds.items():
            if min_karma <= karma <= max_karma:
                return title
        return "Новенький"  # По умолчанию
    
    def _is_gratitude_message(self, message: Message) -> bool:
        """Проверка, является ли сообщение благодарностью"""
        if not message.text:
            return False
        
        gratitude_words = [
            'спасибо', 'благодарю', 'thanks', 'thank you',
            'мерси', 'респект', 'лайк', 'топ', 'огонь'
        ]
        
        text_lower = message.text.lower()
        has_gratitude = any(word in text_lower for word in gratitude_words)
        has_mention = '@' in message.text
        
        return has_gratitude and has_mention
    
    def _extract_mentions(self, text: str) -> List[str]:
        """Извлечение упоминаний пользователей из текста"""
        pattern = r'@(\w+)'
        mentions = re.findall(pattern, text)
        return mentions
    
    def _check_gratitude_cooldown(self, user_id: int) -> bool:
        """Проверка кулдауна для благодарностей"""
        now = time.time()
        cooldown = self.karma_settings['gratitude_cooldown_minutes'] * 60
        
        if user_id not in self.command_cooldowns:
            self.command_cooldowns[user_id] = {}
        
        last_gratitude = self.command_cooldowns[user_id].get('gratitude', 0)
        
        if now - last_gratitude < cooldown:
            return False
        
        self.command_cooldowns[user_id]['gratitude'] = now
        return True
    
    async def _format_user_stats(self, user) -> str:
        """Форматирование статистики пользователя"""
        rank_emoji = {
            'Новенький': '🥉',
            'Надежда сообщества': '🥈', 
            'Мега-помощничье': '🥇',
            'Амбассадорище': '💎'
        }
        
        emoji = rank_emoji.get(user.rank_title, '🎵')
        
        stats = (
            f"📊 **Твоя статистика**\n\n"
            f"{emoji} **Звание:** {user.rank_title}\n"
            f"🏆 **Карма:** {user.karma_points}/{self.karma_settings['max_karma']}\n"
            f"🎵 **Жанр:** {user.music_genre or 'Не указан'}\n\n"
            f"📈 **Активность:**\n"
            f"• Опубликовано ссылок: {user.links_published}\n"
            f"• Пресейвов сделано: {user.presaves_given}\n"
            f"• Пресейвов получено: {user.presaves_received}\n"
            f"• Соотношение дал/получил: {user.presave_ratio:.2f}\n"
            f"• Соотношение карма/ссылки: {user.karma_to_links_ratio:.2f}\n\n"
            f"📅 **Регистрация:** {user.registration_date.strftime('%d.%m.%Y')}\n"
            f"🕐 **Последняя активность:** {user.last_activity.strftime('%d.%m.%Y %H:%M')}"
        )
        
        return stats
    
    async def _ensure_database_tables(self):
        """Обеспечение создания таблиц БД"""
        try:
            # Здесь будет создание таблиц через SQLAlchemy
            # Пока заглушка, таблицы создаются в database_core
            pass
        except Exception as e:
            self.logger.error(f"❌ Ошибка создания таблиц: {e}")
            raise
    
    async def _update_admin_karma(self):
        """Обновление кармы админов до 100500"""
        try:
            admin_ids = getattr(self.config, 'admin_ids', [])
            if not admin_ids:
                return
            
            async with self.database.get_async_session() as session:
                from .models import MusicUser
                
                for admin_id in admin_ids:
                    user = await session.get(MusicUser, admin_id)
                    if user and user.karma_points != self.karma_settings['admin_karma']:
                        user.karma_points = self.karma_settings['admin_karma']
                        user.rank_title = self._get_rank_title(self.karma_settings['admin_karma'])
                        user.is_admin = True
                
                await session.commit()
                
            self.logger.info(f"✅ Обновлена карма {len(admin_ids)} админов")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка обновления кармы админов: {e}")
    
    async def _cleanup_old_sessions(self):
        """Очистка старых сессий онбординга"""
        while True:
            try:
                current_time = time.time()
                expired_sessions = []
                
                for user_id, session in self.onboarding_sessions.items():
                    if current_time - session['started_at'] > 1800:  # 30 минут
                        expired_sessions.append(user_id)
                
                for user_id in expired_sessions:
                    del self.onboarding_sessions[user_id]
                    self.logger.debug(f"🧹 Удалена истекшая сессия онбординга: {user_id}")
                
                await asyncio.sleep(300)  # Проверяем каждые 5 минут
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"❌ Ошибка очистки сессий: {e}")
                await asyncio.sleep(60)
    
    # === WEBAPP ИНТЕГРАЦИЯ ===
    
    async def handle_webapp_command(self, session, command: str, data: Dict[str, Any], message):
        """Обработка команд от WebApp"""
        try:
            if command == 'get_user_stats':
                user = await self._get_user(session.user_id)
                if user:
                    stats = await self._format_user_stats(user)
                    # Отправляем статистику в WebApp формате
                    response = {
                        "action": "user_stats_response",
                        "data": {
                            "karma": user.karma_points,
                            "rank": user.rank_title,
                            "genre": user.music_genre,
                            "stats": stats
                        }
                    }
                    await self.bot.bot.reply_to(message, str(response))
                
            elif command == 'get_leaderboard':
                # Реализация лидерборда для WebApp
                pass
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка WebApp команды {command}: {e}")


# === ЭКСПОРТ ===

# Псевдоним для загрузчика модулей
Module = UserManagementModule