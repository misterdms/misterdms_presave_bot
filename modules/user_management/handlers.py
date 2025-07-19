"""
Modules/user_management/handlers.py - Обработчики команд
Do Presave Reminder Bot v29.07

Обработчики команд для модуля управления пользователями
"""

import re
import time
from typing import Dict, Any, Optional, List
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from .services import UserService
from core.interfaces import rate_limit, log_execution_time
from core.exceptions import UserError, UserNotFoundError, KarmaError, ValidationError
from utils.logger import get_module_logger, log_command_execution, log_user_action


class UserManagementHandlers:
    """Класс обработчиков команд для управления пользователями"""
    
    def __init__(self, bot, database, settings, user_service: UserService):
        """
        Инициализация обработчиков
        
        Args:
            bot: Экземпляр Telegram бота
            database: Ядро базы данных
            settings: Настройки системы
            user_service: Сервис управления пользователями
        """
        self.bot = bot
        self.database = database
        self.settings = settings
        self.user_service = user_service
        self.logger = get_module_logger("user_handlers")
        
        # Сессии онбординга
        self.onboarding_sessions: Dict[int, Dict[str, Any]] = {}
        
        # Кулдауны команд
        self.command_cooldowns: Dict[int, Dict[str, float]] = {}
    
    # === ОСНОВНЫЕ КОМАНДЫ ПОЛЬЗОВАТЕЛЕЙ ===
    
    @log_execution_time("start_command")
    async def handle_start(self, message: Message):
        """Обработчик команды /start - онбординг"""
        try:
            user_id = message.from_user.id
            group_id = getattr(message.chat, 'id', None)
            
            # Проверяем, зарегистрирован ли пользователь
            existing_user = await self.user_service.get_user(user_id)
            if existing_user:
                # Пользователь уже зарегистрирован
                stats = await self.user_service.get_user_stats(user_id)
                
                welcome_back_text = (
                    f"👋 Привет, {message.from_user.first_name}!\n\n"
                    f"Ты уже зарегистрирован в системе.\n\n"
                    f"🏆 **Твоя карма:** {stats['karma']['points']}\n"
                    f"{stats['karma']['rank_emoji']} **Звание:** {stats['karma']['rank']}\n"
                    f"🎵 **Жанр:** {stats['user_info']['music_genre'] or 'Не указан'}\n\n"
                    f"Используй /mystat для подробной статистики."
                )
                
                await self.bot.bot.reply_to(message, welcome_back_text, parse_mode='Markdown')
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
    async def handle_mystat(self, message: Message):
        """Обработчик команды /mystat - личная статистика"""
        try:
            user_id = message.from_user.id
            
            # Получаем статистику пользователя
            stats = await self.user_service.get_user_stats(user_id)
            
            # Форматируем статистику
            stats_text = self._format_user_stats(stats)
            
            # Создаем клавиатуру с дополнительными действиями
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("📈 История кармы", callback_data="karma_history"),
                InlineKeyboardButton("👤 Профиль", callback_data="user_profile")
            )
            keyboard.row(
                InlineKeyboardButton("🏆 Лидерборд", callback_data="leaderboard"),
                InlineKeyboardButton("🔄 Обновить", callback_data="refresh_stats")
            )
            
            await self.bot.bot.reply_to(
                message, 
                stats_text, 
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
            # Обновляем время активности
            await self.user_service.update_last_activity(user_id)
            
            log_command_execution(user_id, "mystat", success=True)
            
        except UserNotFoundError:
            await self.bot.bot.reply_to(
                message,
                "👤 Вы не зарегистрированы в системе.\n"
                "Нажмите /start для регистрации."
            )
            log_command_execution(message.from_user.id, "mystat", success=False, error="user_not_found")
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /mystat: {e}")
            await self.bot.bot.reply_to(
                message,
                "❌ Ошибка получения статистики. Попробуйте позже."
            )
            log_command_execution(message.from_user.id, "mystat", success=False, error=str(e))
    
    @rate_limit(calls_per_minute=20)
    async def handle_mystats(self, message: Message):
        """Обработчик команды /mystats - подробная статистика"""
        try:
            user_id = message.from_user.id
            
            # Получаем подробную статистику
            stats = await self.user_service.get_user_stats(user_id)
            karma_history = await self.user_service.get_karma_history(user_id, limit=5)
            
            # Форматируем подробную статистику
            detailed_stats = self._format_detailed_stats(stats, karma_history)
            
            await self.bot.bot.reply_to(message, detailed_stats, parse_mode='Markdown')
            
            log_command_execution(user_id, "mystats", success=True)
            
        except UserNotFoundError:
            await self.bot.bot.reply_to(message, "👤 Пользователь не найден.")
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /mystats: {e}")
            await self.bot.bot.reply_to(message, "❌ Ошибка получения статистики.")
    
    async def handle_profile(self, message: Message):
        """Обработчик команды /profile - профиль пользователя"""
        try:
            user_id = message.from_user.id
            
            stats = await self.user_service.get_user_stats(user_id)
            profile_text = self._format_user_profile(stats)
            
            # Кнопки управления профилем
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("🎵 Сменить жанр", callback_data="change_genre"),
                InlineKeyboardButton("📊 Статистика", callback_data="show_stats")
            )
            keyboard.row(
                InlineKeyboardButton("📈 История кармы", callback_data="karma_history")
            )
            
            await self.bot.bot.reply_to(
                message, 
                profile_text, 
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /profile: {e}")
            await self.bot.bot.reply_to(message, "❌ Ошибка получения профиля.")
    
    async def handle_karma_history(self, message: Message):
        """Обработчик команды /karma_history - история изменений кармы"""
        try:
            user_id = message.from_user.id
            
            history = await self.user_service.get_karma_history(user_id, limit=10)
            
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
                    f"{change_icon} `{entry['change']:+d}` карма "
                    f"({entry['karma_before']} → {entry['karma_after']})\n"
                    f"💬 {entry['reason']}\n"
                    f"📅 {entry['date']}\n\n"
                )
            
            # Кнопка возврата к статистике
            keyboard = InlineKeyboardMarkup()
            keyboard.row(InlineKeyboardButton("📊 Моя статистика", callback_data="show_stats"))
            
            await self.bot.bot.reply_to(
                message, 
                history_text, 
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка команды /karma_history: {e}")
            await self.bot.bot.reply_to(message, "❌ Ошибка получения истории.")
    
    # === АДМИНСКИЕ КОМАНДЫ КАРМЫ ===
    
    async def handle_karma_admin(self, message: Message):
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
            await self.bot.bot.reply_to(message, "❌ Ошибка выполнения команды кармы.")
    
    async def handle_karma_ratio_admin(self, message: Message):
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
            await self.bot.bot.reply_to(message, "❌ Ошибка выполнения команды соотношения кармы.")
    
    # === ОБРАБОТЧИКИ БЛАГОДАРНОСТЕЙ ===
    
    async def handle_gratitude_message(self, message: Message):
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
            successful_thanks = 0
            
            # Начисляем карму каждому упомянутому пользователю
            for username in mentions:
                success = await self.user_service.give_gratitude_karma(
                    giver_id, 
                    username, 
                    message.text[:100]  # Ограничиваем контекст
                )
                if success:
                    successful_thanks += 1
            
            # Отправляем подтверждение, если были успешные благодарности
            if successful_thanks > 0:
                thank_text = (
                    f"💝 Спасибо передано! Карма начислена "
                    f"{successful_thanks} пользовател{'ю' if successful_thanks == 1 else 'ям'}."
                )
                await self.bot.bot.reply_to(message, thank_text)
            
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
                'last_name': message.from_user.last_name,
                'group_id': getattr(message.chat, 'id', None)
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
    
    async def handle_onboarding_callback(self, call: CallbackQuery):
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
    
    async def handle_genre_selection(self, call: CallbackQuery):
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
            
            # Создаем пользователя через сервис
            new_user = await self.user_service.create_user(user_data)
            
            success_text = (
                f"🎉 **Регистрация завершена!**\n\n"
                f"👤 **Имя:** {user_data.get('first_name', 'Не указано')}\n"
                f"🎵 **Жанр:** {genre}\n"
                f"🏆 **Стартовая карма:** {new_user.karma_points}\n"
                f"🎖️ **Звание:** {new_user.rank_title}\n\n"
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
            
            log_user_action(user_id, "registration_completed", {
                'genre': genre,
                'karma': new_user.karma_points
            })
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка завершения онбординга: {e}")
            await self.bot.bot.edit_message_text(
                "❌ Произошла ошибка при регистрации. Попробуйте /start заново.",
                call.message.chat.id,
                call.message.message_id
            )
    
    async def _onboarding_cancel(self, call: CallbackQuery):
        """Отмена онбординга"""
        user_id = call.from_user.id
        
        if user_id in self.onboarding_sessions:
            del self.onboarding_sessions[user_id]
        
        await self.bot.bot.edit_message_text(
            "❌ Регистрация отменена.\n\nВы можете начать заново командой /start",
            call.message.chat.id,
            call.message.message_id
        )
    
    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    
    def _format_user_stats(self, stats: Dict[str, Any]) -> str:
        """Форматирование статистики пользователя"""
        karma = stats['karma']
        activity = stats['activity']
        meta = stats['meta']
        
        stats_text = (
            f"📊 **Твоя статистика**\n\n"
            f"{karma['rank_emoji']} **Звание:** {karma['rank']}\n"
            f"🏆 **Карма:** {karma['points']}/{100500} ({karma['percentage']:.1f}%)\n"
            f"🎵 **Жанр:** {stats['user_info']['music_genre'] or 'Не указан'}\n\n"
            f"📈 **Активность:**\n"
            f"• Опубликовано ссылок: {activity['links_published']}\n"
            f"• Пресейвов сделано: {activity['presaves_given']}\n"
            f"• Пресейвов получено: {activity['presaves_received']}\n"
            f"• Соотношение дал/получил: {activity['presave_ratio']:.2f}\n"
            f"• Соотношение карма/ссылки: {activity['karma_to_links_ratio']:.2f}\n\n"
            f"📅 **Регистрация:** {meta['registration_date']}\n"
            f"🕐 **Последняя активность:** {meta['last_activity']}"
        )
        
        if meta['is_admin']:
            stats_text += f"\n\n👑 **Статус:** Администратор"
        
        return stats_text
    
    def _format_detailed_stats(self, stats: Dict[str, Any], karma_history: List[Dict]) -> str:
        """Форматирование подробной статистики"""
        basic_stats = self._format_user_stats(stats)
        
        # Добавляем историю кармы
        if karma_history:
            basic_stats += "\n\n📈 **Последние изменения кармы:**\n"
            for entry in karma_history[:3]:  # Показываем только 3 последних
                change_icon = "📈" if entry['change'] > 0 else "📉"
                basic_stats += f"{change_icon} {entry['change']:+d} | {entry['reason'][:30]}...\n"
        
        return basic_stats
    
    def _format_user_profile(self, stats: Dict[str, Any]) -> str:
        """Форматирование профиля пользователя"""
        user_info = stats['user_info']
        karma = stats['karma']
        meta = stats['meta']
        
        profile_text = (
            f"👤 **Профиль пользователя**\n\n"
            f"🆔 **ID:** `{user_info['user_id']}`\n"
            f"📝 **Имя:** {user_info['first_name'] or 'Не указано'}\n"
            f"🎵 **Жанр:** {user_info['music_genre'] or 'Не указан'}\n\n"
            f"{karma['rank_emoji']} **Звание:** {karma['rank']}\n"
            f"🏆 **Карма:** {karma['points']}\n\n"
            f"📅 **В сообществе с:** {meta['registration_date']}\n"
            f"📱 **Посещений WebApp:** {meta['webapp_visits']}"
        )
        
        return profile_text
    
    def _is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        admin_ids = getattr(self.settings, 'admin_ids', [])
        return user_id in admin_ids
    
    def _extract_mentions(self, text: str) -> List[str]:
        """Извлечение упоминаний пользователей из текста"""
        pattern = r'@(\w+)'
        mentions = re.findall(pattern, text)
        return mentions
    
    def _check_gratitude_cooldown(self, user_id: int) -> bool:
        """Проверка кулдауна для благодарностей"""
        now = time.time()
        cooldown = 60 * 60  # 60 минут кулдаун
        
        if user_id not in self.command_cooldowns:
            self.command_cooldowns[user_id] = {}
        
        last_gratitude = self.command_cooldowns[user_id].get('gratitude', 0)
        
        if now - last_gratitude < cooldown:
            return False
        
        self.command_cooldowns[user_id]['gratitude'] = now
        return True
    
    async def _send_karma_help(self, message: Message):
        """Отправка справки по команде /karma"""
        help_text = (
            "👑 **Команда /karma (только админы)**\n\n"
            "**Просмотр кармы:**\n"
            "`/karma @username` - показать карму пользователя\n\n"
            "**Изменение кармы:**\n"
            "`/karma @username +5` - добавить 5 кармы\n"
            "`/karma @username -3` - снять 3 кармы\n"
            "`/karma @username 50` - установить точно 50 кармы\n\n"
            "**Ограничения:**\n"
            "• Минимум: 0 кармы\n"
            "• Максимум: 100500 кармы\n"
            "• Только для админов"
        )
        
        await self.bot.bot.reply_to(message, help_text, parse_mode='Markdown')
    
    async def _send_karma_ratio_help(self, message: Message):
        """Отправка справки по команде /karma_ratio"""
        help_text = (
            "⚖️ **Команда /karma_ratio (только админы)**\n\n"
            "**Просмотр соотношения:**\n"
            "`/karma_ratio @username` - показать соотношение\n\n"
            "**Изменение соотношения:**\n"
            "`/karma_ratio @username 10:8` - установить 10 кармы за 8 ссылок\n\n"
            "**Примеры:**\n"
            "`/karma_ratio @user 15:5` - 15 кармы, 5 ссылок\n"
            "`/karma_ratio @user 0:0` - сбросить статистику"
        )
        
        await self.bot.bot.reply_to(message, help_text, parse_mode='Markdown')
    
    async def _show_user_karma(self, message: Message, username: str):
        """Показ кармы пользователя (админская функция)"""
        try:
            user = await self.user_service.get_user_by_username(username)
            if not user:
                await self.bot.bot.reply_to(
                    message,
                    f"❌ Пользователь @{username} не найден."
                )
                return
            
            stats = await self.user_service.get_user_stats(user.user_id)
            
            karma_info = (
                f"🏆 **Карма пользователя @{username}**\n\n"
                f"{stats['karma']['rank_emoji']} **Звание:** {stats['karma']['rank']}\n"
                f"🏆 **Карма:** {stats['karma']['points']}/{100500}\n"
                f"📊 **Процент:** {stats['karma']['percentage']:.1f}%\n\n"
                f"📈 **Активность:**\n"
                f"• Ссылок: {stats['activity']['links_published']}\n"
                f"• Соотношение: {stats['activity']['karma_to_links_ratio']:.2f}\n"
                f"• Пресейвов дал/получил: {stats['activity']['presaves_given']}/{stats['activity']['presaves_received']}"
            )
            
            await self.bot.bot.reply_to(message, karma_info, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка показа кармы @{username}: {e}")
            await self.bot.bot.reply_to(message, "❌ Ошибка получения кармы пользователя.")
    
    async def _change_user_karma(self, message: Message, username: str, operation: str):
        """Изменение кармы пользователя (админская функция)"""
        try:
            user = await self.user_service.get_user_by_username(username)
            if not user:
                await self.bot.bot.reply_to(
                    message,
                    f"❌ Пользователь @{username} не найден."
                )
                return
            
            # Парсим операцию
            if operation.startswith('+'):
                # Добавление кармы
                change_amount = int(operation[1:])
                reason = f"Админское начисление +{change_amount}"
            elif operation.startswith('-'):
                # Снятие кармы
                change_amount = -int(operation[1:])
                reason = f"Админское снятие {change_amount}"
            else:
                # Установка точного значения
                new_karma = int(operation)
                current_karma = await self.user_service.get_karma(user.user_id)
                change_amount = new_karma - current_karma
                reason = f"Админская установка кармы на {new_karma}"
            
            # Применяем изменение
            await self.user_service.change_karma(
                user.user_id,
                change_amount,
                reason,
                changed_by=message.from_user.id,
                change_type="admin_adjustment"
            )
            
            # Получаем обновленную карму
            new_karma = await self.user_service.get_karma(user.user_id)
            
            result_text = (
                f"✅ **Карма изменена**\n\n"
                f"👤 **Пользователь:** @{username}\n"
                f"🏆 **Новая карма:** {new_karma}\n"
                f"📝 **Изменение:** {change_amount:+d}\n"
                f"💬 **Причина:** {reason}"
            )
            
            await self.bot.bot.reply_to(message, result_text, parse_mode='Markdown')
            
        except ValueError:
            await self.bot.bot.reply_to(
                message,
                "❌ Неверный формат числа. Используйте: +5, -3 или 50"
            )
        except KarmaError as e:
            await self.bot.bot.reply_to(message, f"❌ {e.message}")
        except Exception as e:
            self.logger.error(f"❌ Ошибка изменения кармы @{username}: {e}")
            await self.bot.bot.reply_to(message, "❌ Ошибка изменения кармы.")
    
    async def _show_karma_ratio(self, message: Message, username: str):
        """Показ соотношения карма:ссылки"""
        try:
            user = await self.user_service.get_user_by_username(username)
            if not user:
                await self.bot.bot.reply_to(
                    message,
                    f"❌ Пользователь @{username} не найден."
                )
                return
            
            stats = await self.user_service.get_user_stats(user.user_id)
            
            ratio_info = (
                f"⚖️ **Соотношение @{username}**\n\n"
                f"🏆 **Карма:** {stats['karma']['points']}\n"
                f"🔗 **Ссылок:** {stats['activity']['links_published']}\n"
                f"📊 **Соотношение:** {stats['activity']['karma_to_links_ratio']:.2f}\n\n"
                f"📈 **Пресейвы:**\n"
                f"• Дал: {stats['activity']['presaves_given']}\n"
                f"• Получил: {stats['activity']['presaves_received']}\n"
                f"• Соотношение: {stats['activity']['presave_ratio']:.2f}"
            )
            
            await self.bot.bot.reply_to(message, ratio_info, parse_mode='Markdown')
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка показа соотношения @{username}: {e}")
            await self.bot.bot.reply_to(message, "❌ Ошибка получения соотношения.")
    
    async def _change_karma_ratio(self, message: Message, username: str, ratio_str: str):
        """Изменение соотношения карма:ссылки"""
        try:
            # Парсим соотношение
            if ':' not in ratio_str:
                await self.bot.bot.reply_to(
                    message,
                    "❌ Неверный формат. Используйте: карма:ссылки (например, 10:5)"
                )
                return
            
            karma_str, links_str = ratio_str.split(':', 1)
            karma = int(karma_str)
            links = int(links_str)
            
            user = await self.user_service.get_user_by_username(username)
            if not user:
                await self.bot.bot.reply_to(
                    message,
                    f"❌ Пользователь @{username} не найден."
                )
                return
            
            # Устанавливаем соотношение
            await self.user_service.set_karma_ratio(user.user_id, links, karma)
            
            result_text = (
                f"✅ **Соотношение изменено**\n\n"
                f"👤 **Пользователь:** @{username}\n"
                f"🏆 **Карма:** {karma}\n"
                f"🔗 **Ссылок:** {links}\n"
                f"📊 **Соотношение:** {karma/max(links, 1):.2f}"
            )
            
            await self.bot.bot.reply_to(message, result_text, parse_mode='Markdown')
            
        except ValueError:
            await self.bot.bot.reply_to(
                message,
                "❌ Неверный формат чисел. Используйте: карма:ссылки (например, 15:3)"
            )
        except Exception as e:
            self.logger.error(f"❌ Ошибка изменения соотношения @{username}: {e}")
            await self.bot.bot.reply_to(message, "❌ Ошибка изменения соотношения.")


if __name__ == "__main__":
    print("🧪 Модуль UserManagementHandlers готов к использованию")
    print("📋 Основные обработчики:")
    print("  • handle_start - команда /start")
    print("  • handle_mystat - команда /mystat")
    print("  • handle_karma_admin - команда /karma (админы)")
    print("  • handle_gratitude_message - благодарности")
    print("✅ Обработчики команд инициализированы")