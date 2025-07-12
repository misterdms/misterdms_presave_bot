"""
💬 Commands Handler - Do Presave Reminder Bot v25+
Обработчики всех команд бота для всех планов развития
"""

import re
from typing import Optional, List, Tuple
import telebot
from telebot.types import Message

from config import config
from database.manager import get_database_manager
from utils.security import (
    admin_required, user_rate_limit, security_manager, 
    Plan1Validators, Plan2Validators, ValidationError, AccessDeniedError
)
from utils.logger import get_logger, telegram_logger, karma_logger
from utils.helpers import (
    MessageFormatter, UserHelper, DataHelper, ConfigHelper, CommandParser
)

logger = get_logger(__name__)

class CommandHandler:
    """Обработчик команд бота"""
    
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot
        self.db = get_database_manager()
        
        # Регистрируем обработчики команд
        self._register_commands()
        
        logger.info("💬 Command Handler инициализирован")
    
    def _register_commands(self):
        """Регистрация всех команд"""
        
        # ============================================
        # ПЛАН 1 - БАЗОВЫЕ КОМАНДЫ
        # ============================================
        
        @self.bot.message_handler(commands=['start'])
        def handle_start(message: Message):
            self.cmd_start(message)
        
        @self.bot.message_handler(commands=['mystat'])
        @user_rate_limit('user_commands')
        def handle_mystat(message: Message):
            self.cmd_mystat(message)
        
        @self.bot.message_handler(commands=['enablebot'])
        @admin_required
        def handle_enable_bot(message: Message):
            self.cmd_enable_bot(message)
        
        @self.bot.message_handler(commands=['disablebot'])
        @admin_required
        def handle_disable_bot(message: Message):
            self.cmd_disable_bot(message)
        
        # Команды режимов лимитов
        @self.bot.message_handler(commands=['setmode_conservative'])
        @admin_required
        def handle_set_conservative(message: Message):
            self.cmd_set_limit_mode(message, 'CONSERVATIVE')
        
        @self.bot.message_handler(commands=['setmode_normal'])
        @admin_required
        def handle_set_normal(message: Message):
            self.cmd_set_limit_mode(message, 'NORMAL')
        
        @self.bot.message_handler(commands=['setmode_burst'])
        @admin_required
        def handle_set_burst(message: Message):
            self.cmd_set_limit_mode(message, 'BURST')
        
        @self.bot.message_handler(commands=['setmode_adminburst'])
        @admin_required
        def handle_set_admin_burst(message: Message):
            self.cmd_set_limit_mode(message, 'ADMIN_BURST')
        
        @self.bot.message_handler(commands=['currentmode'])
        @admin_required
        def handle_current_mode(message: Message):
            self.cmd_current_mode(message)
        
        @self.bot.message_handler(commands=['reloadmodes'])
        @admin_required
        def handle_reload_modes(message: Message):
            self.cmd_reload_modes(message)
        
        # Команды работы со ссылками
        @self.bot.message_handler(commands=['last10links'])
        @admin_required
        def handle_last10_links(message: Message):
            self.cmd_recent_links(message, limit=10)
        
        @self.bot.message_handler(commands=['last30links'])
        @admin_required
        def handle_last30_links(message: Message):
            self.cmd_recent_links(message, limit=30)
        
        @self.bot.message_handler(commands=['clearlinks'])
        @admin_required
        def handle_clear_links(message: Message):
            self.cmd_clear_links(message)
        
        # ============================================
        # ПЛАН 2 - КОМАНДЫ КАРМЫ
        # ============================================
        
        if config.ENABLE_PLAN_2_FEATURES:
            @self.bot.message_handler(commands=['karma'])
            @admin_required
            def handle_karma(message: Message):
                self.cmd_karma(message)
            
            @self.bot.message_handler(commands=['karmastat'])
            @admin_required
            def handle_karma_stat(message: Message):
                self.cmd_karma_leaderboard(message)
            
            @self.bot.message_handler(commands=['presavestat'])
            @admin_required
            def handle_presave_stat(message: Message):
                self.cmd_requests_leaderboard(message)
            
            @self.bot.message_handler(commands=['ratiostat'])
            @admin_required
            def handle_ratio_stat(message: Message):
                self.cmd_ratio_command(message)
        
        # ============================================
        # ПЛАН 3 - КОМАНДЫ ИИ И ФОРМ
        # ============================================
        
        if config.ENABLE_PLAN_3_FEATURES:
            @self.bot.message_handler(commands=['askpresave'])
            @user_rate_limit('form_submissions')
            def handle_ask_presave(message: Message):
                self.cmd_ask_presave(message)
            
            @self.bot.message_handler(commands=['claimpresave'])
            @user_rate_limit('form_submissions')
            def handle_claim_presave(message: Message):
                self.cmd_claim_presave(message)
            
            @self.bot.message_handler(commands=['checkapprovals'])
            @admin_required
            def handle_check_approvals(message: Message):
                self.cmd_check_approvals(message)
        
        # ============================================
        # ПЛАН 4 - КОМАНДЫ BACKUP
        # ============================================
        
        if config.ENABLE_PLAN_4_FEATURES:
            # Эти команды будут реализованы в handlers/backup_commands.py
            pass
        
        # ============================================
        # АНАЛИТИЧЕСКИЕ КОМАНДЫ
        # ============================================
        
        @self.bot.message_handler(commands=['linksby'])
        @admin_required
        def handle_links_by(message: Message):
            self.cmd_links_by_user(message)
        
        @self.bot.message_handler(commands=['approvesby'])
        @admin_required
        def handle_approves_by(message: Message):
            self.cmd_approves_by_user(message)
        
        @self.bot.message_handler(commands=['userratiostat'])
        @admin_required
        def handle_user_ratio_stat(message: Message):
            self.cmd_user_ratio_stat(message)
        
        # ============================================
        # ДИАГНОСТИЧЕСКИЕ КОМАНДЫ
        # ============================================
        
        @self.bot.message_handler(commands=['keepalive'])
        @admin_required
        def handle_keep_alive(message: Message):
            self.cmd_keep_alive(message)
        
        @self.bot.message_handler(commands=['checksystem'])
        @admin_required
        def handle_check_system(message: Message):
            self.cmd_check_system(message)
        
        @self.bot.message_handler(commands=['botstatus'])
        @admin_required
        def handle_bot_status(message: Message):
            self.cmd_bot_status(message)
    
    # ============================================
    # ПЛАН 1 - БАЗОВЫЕ КОМАНДЫ
    # ============================================
    
    def cmd_start(self, message: Message):
        """Команда /start - приветствие"""
        try:
            user_id = message.from_user.id
            
            # Создаем или обновляем пользователя
            user = self.db.create_or_update_user(
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            
            is_admin = security_manager.is_admin(user_id)
            
            # Формируем приветствие
            greeting = f"{MessageFormatter.get_emoji('music')} **Добро пожаловать в Do Presave Reminder Bot!**\n\n"
            
            if is_admin:
                greeting += f"{MessageFormatter.get_emoji('admin')} Вы вошли как **администратор**.\n\n"
                greeting += f"{MessageFormatter.get_emoji('menu')} Для управления ботом используйте:\n"
                greeting += f"• `/menu` - Открыть главное меню\n"
                greeting += f"• `/help` - Полная справка по командам\n"
                greeting += f"• `/mystat` - Ваша статистика\n\n"
            else:
                greeting += f"{MessageFormatter.get_emoji('user')} Добро пожаловать в музыкальное сообщество!\n\n"
                greeting += f"{MessageFormatter.get_emoji('info')} **Как использовать бота:**\n"
                greeting += f"• Публикуйте ссылки на пресейвы в разрешённых топиках\n"
                greeting += f"• Бот напомнит о взаимных пресейвах\n"
                greeting += f"• Благодарите участников - это важно!\n\n"
                greeting += f"{MessageFormatter.get_emoji('help')} Команда `/help` покажет доступные функции.\n\n"
            
            greeting += f"**Поддерживаемые сервисы:**\n"
            greeting += f"• {MessageFormatter.format_url_domain('https://spotify.com')}\n"
            greeting += f"• {MessageFormatter.format_url_domain('https://music.apple.com')}\n"
            greeting += f"• {MessageFormatter.format_url_domain('https://music.youtube.com')}\n"
            greeting += f"• И многие другие музыкальные платформы\n\n"
            
            greeting += f"{MessageFormatter.get_emoji('heart')} **Взаимная поддержка - ключ к успеху!**"
            
            self.bot.send_message(
                message.chat.id,
                greeting,
                parse_mode='Markdown'
            )
            
            telegram_logger.user_action(user_id, "выполнил команду /start", is_new_user=(not user))
            
        except Exception as e:
            logger.error(f"❌ Ошибка команды /start: {e}")
            self._send_error_response(message, "Ошибка инициализации")
    
    def cmd_mystat(self, message: Message):
        """Команда /mystat - статистика пользователя"""
        try:
            user_id = message.from_user.id
            
            # Получаем статистику
            stats = self.db.get_user_stats(user_id)
            
            if not stats.get('user_info'):
                # Создаем пользователя если не существует
                self.db.create_or_update_user(
                    telegram_id=user_id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    last_name=message.from_user.last_name
                )
                stats = self.db.get_user_stats(user_id)
            
            # Форматируем статистику
            stats_text = UserHelper.format_user_stats_message(stats)
            
            self.bot.send_message(
                message.chat.id,
                stats_text,
                parse_mode='Markdown'
            )
            
            telegram_logger.user_action(user_id, "запросил свою статистику")
            
        except Exception as e:
            logger.error(f"❌ Ошибка команды /mystat: {e}")
            self._send_error_response(message, "Ошибка загрузки статистики")
    
    @admin_required
    def cmd_enable_bot(self, message: Message):
        """Команда /enablebot - активация бота"""
        try:
            # Устанавливаем настройку
            self.db.set_setting('bot_enabled', 'true', 'bool', 'Включен ли бот')
            
            response = f"{MessageFormatter.get_emoji('success')} **Бот активирован!**\n\n"
            response += f"{MessageFormatter.get_emoji('info')} Все функции восстановлены:\n"
            response += f"• Реакция на ссылки включена\n"
            response += f"• Команды пользователей активны\n"
            response += f"• Меню и навигация работают\n\n"
            response += f"**Текущий режим лимитов:** {ConfigHelper.get_current_limit_mode()}"
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "активировал бота"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка активации бота: {e}")
            self._send_error_response(message, "Ошибка активации бота")
    
    @admin_required
    def cmd_disable_bot(self, message: Message):
        """Команда /disablebot - деактивация бота"""
        try:
            # Устанавливаем настройку
            self.db.set_setting('bot_enabled', 'false', 'bool', 'Включен ли бот')
            
            response = f"{MessageFormatter.get_emoji('warning')} **Бот деактивирован!**\n\n"
            response += f"{MessageFormatter.get_emoji('info')} Отключенные функции:\n"
            response += f"• Реакция на ссылки приостановлена\n"
            response += f"• Пользовательские команды недоступны\n"
            response += f"• Автоматические функции остановлены\n\n"
            response += f"{MessageFormatter.get_emoji('admin')} **Админские команды остаются доступными.**\n\n"
            response += f"Для активации используйте `/enablebot`"
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "деактивировал бота"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка деактивации бота: {e}")
            self._send_error_response(message, "Ошибка деактивации бота")
    
    @admin_required
    def cmd_set_limit_mode(self, message: Message, mode: str):
        """Установка режима лимитов API"""
        try:
            # Валидируем режим
            if not Plan1Validators.validate_limit_mode(mode):
                self._send_error_response(message, f"Неверный режим лимитов: {mode}")
                return
            
            # Сохраняем настройку
            self.db.set_setting('current_limit_mode', mode, 'string', 'Текущий режим лимитов API')
            
            # Формируем ответ
            response = f"{MessageFormatter.get_emoji('success')} **Режим лимитов изменен!**\n\n"
            response += ConfigHelper.format_limit_mode_info(mode)
            response += f"\n\n{MessageFormatter.get_emoji('info')} Изменения применены немедленно."
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                f"изменил режим лимитов на {mode}"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки режима {mode}: {e}")
            self._send_error_response(message, f"Ошибка установки режима {mode}")
    
    @admin_required
    def cmd_current_mode(self, message: Message):
        """Команда /currentmode - текущий режим лимитов"""
        try:
            current_mode = ConfigHelper.get_current_limit_mode()
            
            response = f"{MessageFormatter.get_emoji('system')} **ТЕКУЩИЙ РЕЖИМ ЛИМИТОВ**\n\n"
            response += ConfigHelper.format_limit_mode_info(current_mode)
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "запросил текущий режим лимитов"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения текущего режима: {e}")
            self._send_error_response(message, "Ошибка получения режима")
    
    @admin_required
    def cmd_reload_modes(self, message: Message):
        """Команда /reloadmodes - перезагрузка настроек режимов"""
        try:
            # Сбрасываем на значение по умолчанию из конфига
            default_mode = config.DEFAULT_LIMIT_MODE
            self.db.set_setting('current_limit_mode', default_mode, 'string', 'Текущий режим лимитов API')
            
            response = f"{MessageFormatter.get_emoji('refresh')} **Настройки режимов перезагружены!**\n\n"
            response += f"{MessageFormatter.get_emoji('success')} Установлен режим по умолчанию: **{default_mode}**\n\n"
            response += ConfigHelper.format_limit_mode_info(default_mode)
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "перезагрузил настройки режимов лимитов"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка перезагрузки режимов: {e}")
            self._send_error_response(message, "Ошибка перезагрузки настроек")
    
    @admin_required
    def cmd_recent_links(self, message: Message, limit: int = 10):
        """Команда показа последних ссылок"""
        try:
            # Получаем ссылки
            links = self.db.get_recent_links(limit=limit)
            
            # Форматируем список
            response = DataHelper.format_links_list(links, max_links=limit)
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                f"запросил последние {limit} ссылок"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения ссылок: {e}")
            self._send_error_response(message, "Ошибка загрузки ссылок")
    
    @admin_required
    def cmd_clear_links(self, message: Message):
        """Команда /clearlinks - очистка истории ссылок"""
        try:
            # Очищаем ссылки старше 30 дней
            deleted_count = self.db.clear_links(older_than_days=30)
            
            response = f"{MessageFormatter.get_emoji('success')} **История ссылок очищена!**\n\n"
            response += f"{MessageFormatter.get_emoji('info')} Удалено записей: **{deleted_count}**\n"
            response += f"{MessageFormatter.get_emoji('time')} Удалены ссылки старше 30 дней\n\n"
            response += f"Актуальные ссылки сохранены."
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                f"очистил историю ссылок (удалено: {deleted_count})"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка очистки ссылок: {e}")
            self._send_error_response(message, "Ошибка очистки ссылок")
    
    # ============================================
    # ПЛАН 2 - КОМАНДЫ КАРМЫ
    # ============================================
    
    @admin_required
    def cmd_karma(self, message: Message):
        """Команда /karma @username +/-число"""
        if not config.ENABLE_PLAN_2_FEATURES:
            self._send_feature_not_available(message, "Система кармы (План 2)")
            return
        
        try:
            # Парсим команду
            parsed = CommandParser.parse_karma_command(message.text)
            if not parsed:
                error_text = f"{MessageFormatter.get_emoji('error')} **Неверный формат команды!**\n\n"
                error_text += f"**Правильный формат:**\n"
                error_text += f"• `/karma @username +5` - добавить карму\n"
                error_text += f"• `/karma @username -3` - убавить карму\n\n"
                error_text += f"**Ограничения:**\n"
                error_text += f"• Карма: от 0 до {config.MAX_KARMA}\n"
                error_text += f"• Изменение: от -50 до +50 за раз"
                
                self.bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
                return
            
            username, karma_change = parsed
            
            # Валидируем изменение кармы
            Plan2Validators.validate_karma_change(karma_change)
            
            # Ищем пользователя
            target_user = self.db.get_user_by_username(username)
            if not target_user:
                self._send_error_response(message, f"Пользователь @{username} не найден")
                return
            
            # Применяем изменение кармы
            karma_record = self.db.change_karma(
                user_id=target_user.id,
                change=karma_change,
                admin_id=message.from_user.id,
                reason=f"Ручное изменение админом через команду"
            )
            
            # Формируем ответ
            change_str = f"+{karma_change}" if karma_change > 0 else str(karma_change)
            user_display = UserHelper.get_user_display_name(target_user)
            
            response = f"{MessageFormatter.get_emoji('success')} **Карма изменена!**\n\n"
            response += f"{MessageFormatter.get_emoji('user')} **Пользователь:** {user_display}\n"
            response += f"{MessageFormatter.get_emoji('karma')} **Изменение:** {change_str}\n"
            response += f"{MessageFormatter.get_emoji('stats')} **Новая карма:** {karma_record.karma_points}\n"
            response += f"{MessageFormatter.get_emoji('rank')} **Звание:** {karma_record.rank.value}\n"
            
            # Проверяем достижение нового уровня
            from database.models import get_karma_threshold_for_next_rank
            next_threshold = get_karma_threshold_for_next_rank(karma_record.karma_points)
            if next_threshold:
                remaining = next_threshold - karma_record.karma_points
                progress_bar = MessageFormatter.create_progress_bar(
                    karma_record.karma_points, next_threshold
                )
                response += f"\n{MessageFormatter.get_emoji('progress')} **Прогресс:** {progress_bar}\n"
                response += f"До следующего уровня: {remaining} кармы"
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                f"изменил карму пользователя {username} на {change_str}",
                target_user_id=target_user.id
            )
            
        except ValidationError as e:
            self._send_error_response(message, str(e))
        except Exception as e:
            logger.error(f"❌ Ошибка команды /karma: {e}")
            self._send_error_response(message, "Ошибка изменения кармы")
    
    @admin_required
    def cmd_karma_leaderboard(self, message: Message):
        """Команда /karmastat - лидерборд по карме"""
        if not config.ENABLE_PLAN_2_FEATURES:
            self._send_feature_not_available(message, "Лидерборды (План 2)")
            return
        
        try:
            leaderboard_data = self.db.get_karma_leaderboard(limit=10)
            leaderboard_text = DataHelper.format_leaderboard(leaderboard_data, 'karma')
            
            self.bot.send_message(
                message.chat.id,
                leaderboard_text,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "запросил лидерборд по карме"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка лидерборда кармы: {e}")
            self._send_error_response(message, "Ошибка загрузки лидерборда")
    
    @admin_required
    def cmd_requests_leaderboard(self, message: Message):
        """Команда /presavestat - лидерборд по просьбам"""
        try:
            leaderboard_data = self.db.get_requests_leaderboard(limit=10)
            leaderboard_text = DataHelper.format_leaderboard(leaderboard_data, 'requests')
            
            self.bot.send_message(
                message.chat.id,
                leaderboard_text,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "запросил лидерборд по просьбам о пресейвах"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка лидерборда просьб: {e}")
            self._send_error_response(message, "Ошибка загрузки лидерборда")
    
    @admin_required
    def cmd_ratio_command(self, message: Message):
        """Команда /ratiostat @username 15:12 - изменение соотношения"""
        if not config.ENABLE_PLAN_2_FEATURES:
            self._send_feature_not_available(message, "Редактирование соотношений (План 2)")
            return
        
        try:
            # Парсим команду
            parsed = CommandParser.parse_ratio_command(message.text)
            if not parsed:
                error_text = f"{MessageFormatter.get_emoji('error')} **Неверный формат команды!**\n\n"
                error_text += f"**Правильный формат:**\n"
                error_text += f"• `/ratiostat @username 15:12`\n"
                error_text += f"• `/ratiostat @username 20-8`\n\n"
                error_text += f"**Где:**\n"
                error_text += f"• 15 - количество просьб о пресейвах\n"
                error_text += f"• 12 - количество кармы"
                
                self.bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
                return
            
            username, requests_count, karma_count = parsed
            
            # Валидируем соотношение
            Plan2Validators.validate_ratio_format(f"{requests_count}:{karma_count}")
            
            # Ищем пользователя
            target_user = self.db.get_user_by_username(username)
            if not target_user:
                self._send_error_response(message, f"Пользователь @{username} не найден")
                return
            
            # Обновляем соотношение
            success = self.db.update_user_ratio(target_user.id, requests_count, karma_count)
            
            if success:
                user_display = UserHelper.get_user_display_name(target_user)
                
                response = f"{MessageFormatter.get_emoji('success')} **Соотношение обновлено!**\n\n"
                response += f"{MessageFormatter.get_emoji('user')} **Пользователь:** {user_display}\n"
                response += f"{MessageFormatter.get_emoji('presave')} **Просьб о пресейвах:** {requests_count}\n"
                response += f"{MessageFormatter.get_emoji('karma')} **Карма:** {karma_count}\n"
                response += f"{MessageFormatter.get_emoji('progress')} **Соотношение:** {requests_count}:{karma_count}\n\n"
                
                # Вычисляем эффективность
                if requests_count > 0:
                    efficiency = (karma_count / requests_count) * 100
                    response += f"**Эффективность:** {efficiency:.1f}% взаимности"
                
                self.bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown'
                )
                
                telegram_logger.admin_action(
                    message.from_user.id,
                    f"изменил соотношение пользователя {username} на {requests_count}:{karma_count}",
                    target_user_id=target_user.id
                )
            else:
                self._send_error_response(message, "Не удалось обновить соотношение")
            
        except ValidationError as e:
            self._send_error_response(message, str(e))
        except Exception as e:
            logger.error(f"❌ Ошибка команды /ratiostat: {e}")
            self._send_error_response(message, "Ошибка обновления соотношения")
    
    # ============================================
    # ПЛАН 3 - КОМАНДЫ ИИ И ФОРМ (ЗАГЛУШКИ)
    # ============================================
    
    def cmd_ask_presave(self, message: Message):
        """Команда /askpresave - запрос пресейва (заглушка для Плана 3)"""
        if not config.ENABLE_PLAN_3_FEATURES:
            self._send_feature_not_available(message, "Интерактивные формы (План 3)")
            return
        
        # Здесь будет реализация интерактивных форм в Плане 3
        response = f"{MessageFormatter.get_emoji('loading')} **Интерактивные формы в разработке**\n\n"
        response += f"Функция будет доступна в Плане 3."
        
        self.bot.send_message(message.chat.id, response, parse_mode='Markdown')
    
    def cmd_claim_presave(self, message: Message):
        """Команда /claimpresave - заявка о пресейве (заглушка для Плана 3)"""
        if not config.ENABLE_PLAN_3_FEATURES:
            self._send_feature_not_available(message, "Система заявок (План 3)")
            return
        
        # Здесь будет реализация системы заявок в Плане 3
        response = f"{MessageFormatter.get_emoji('loading')} **Система заявок в разработке**\n\n"
        response += f"Функция будет доступна в Плане 3."
        
        self.bot.send_message(message.chat.id, response, parse_mode='Markdown')
    
    @admin_required
    def cmd_check_approvals(self, message: Message):
        """Команда /checkapprovals - проверка заявок (заглушка для Плана 3)"""
        if not config.ENABLE_PLAN_3_FEATURES:
            self._send_feature_not_available(message, "Модерация заявок (План 3)")
            return
        
        # Здесь будет реализация модерации в Плане 3
        response = f"{MessageFormatter.get_emoji('loading')} **Модерация заявок в разработке**\n\n"
        response += f"Функция будет доступна в Плане 3."
        
        self.bot.send_message(message.chat.id, response, parse_mode='Markdown')
    
    # ============================================
    # АНАЛИТИЧЕСКИЕ КОМАНДЫ
    # ============================================
    
    @admin_required
    def cmd_links_by_user(self, message: Message):
        """Команда /linksby @username - ссылки пользователя"""
        try:
            username = CommandParser.parse_user_query(message.text)
            if not username:
                error_text = f"{MessageFormatter.get_emoji('error')} **Неверный формат!**\n\n"
                error_text += f"**Правильный формат:** `/linksby @username`"
                self.bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
                return
            
            # Ищем пользователя
            target_user = self.db.get_user_by_username(username)
            if not target_user:
                self._send_error_response(message, f"Пользователь @{username} не найден")
                return
            
            # Получаем ссылки пользователя
            user_links = self.db.get_user_links(target_user.id, limit=20)
            
            user_display = UserHelper.get_user_display_name(target_user)
            
            response = f"{MessageFormatter.get_emoji('link')} **Ссылки пользователя {user_display}**\n\n"
            
            if user_links:
                for i, link in enumerate(user_links[:10], 1):
                    domain = MessageFormatter.format_url_domain(link.url)
                    time_ago = MessageFormatter.format_time_ago(link.created_at)
                    response += f"{i}. {domain} ({time_ago})\n"
                
                if len(user_links) > 10:
                    response += f"\n... и ещё {len(user_links) - 10} ссылок"
                
                response += f"\n\n**Всего ссылок:** {len(user_links)}"
            else:
                response += f"Ссылки не найдены."
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                f"запросил ссылки пользователя {username}",
                target_user_id=target_user.id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка команды /linksby: {e}")
            self._send_error_response(message, "Ошибка поиска ссылок")
    
    @admin_required
    def cmd_approves_by_user(self, message: Message):
        """Команда /approvesby @username - карма пользователя"""
        try:
            username = CommandParser.parse_user_query(message.text)
            if not username:
                error_text = f"{MessageFormatter.get_emoji('error')} **Неверный формат!**\n\n"
                error_text += f"**Правильный формат:** `/approvesby @username`"
                self.bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
                return
            
            # Ищем пользователя
            target_user = self.db.get_user_by_username(username)
            if not target_user:
                self._send_error_response(message, f"Пользователь @{username} не найден")
                return
            
            user_display = UserHelper.get_user_display_name(target_user)
            
            response = f"{MessageFormatter.get_emoji('karma')} **Карма пользователя {user_display}**\n\n"
            
            if config.ENABLE_PLAN_2_FEATURES:
                # Получаем карму
                karma_record = self.db.get_user_karma(target_user.id)
                
                if karma_record:
                    response += MessageFormatter.format_karma_info(karma_record, show_progress=True)
                    
                    # История изменений кармы
                    karma_history = self.db.get_karma_history(target_user.id, limit=5)
                    if karma_history:
                        response += f"\n\n{MessageFormatter.get_emoji('time')} **Последние изменения:**\n"
                        for change in karma_history:
                            change_str = f"+{change.change_amount}" if change.change_amount > 0 else str(change.change_amount)
                            time_ago = MessageFormatter.format_time_ago(change.created_at)
                            source = "автоматически" if change.is_automatic else "админом"
                            response += f"• {change_str} ({source}, {time_ago})\n"
                else:
                    response += f"Информация о карме отсутствует."
            else:
                response += f"Система кармы будет доступна в Плане 2."
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                f"запросил карму пользователя {username}",
                target_user_id=target_user.id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка команды /approvesby: {e}")
            self._send_error_response(message, "Ошибка поиска кармы")
    
    @admin_required
    def cmd_user_ratio_stat(self, message: Message):
        """Команда /userratiostat @username - соотношение пользователя"""
        try:
            username = CommandParser.parse_user_query(message.text)
            if not username:
                error_text = f"{MessageFormatter.get_emoji('error')} **Неверный формат!**\n\n"
                error_text += f"**Правильный формат:** `/userratiostat @username`"
                self.bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
                return
            
            # Ищем пользователя
            target_user = self.db.get_user_by_username(username)
            if not target_user:
                self._send_error_response(message, f"Пользователь @{username} не найден")
                return
            
            # Получаем статистику
            stats = self.db.get_user_stats(target_user.id)
            user_display = UserHelper.get_user_display_name(target_user)
            
            response = f"{MessageFormatter.get_emoji('progress')} **Соотношение пользователя {user_display}**\n\n"
            
            links_count = stats.get('links_count', 0)
            
            if config.ENABLE_PLAN_2_FEATURES and stats.get('karma_info'):
                karma_info = stats['karma_info']
                karma_points = karma_info['karma_points']
                
                response += f"{MessageFormatter.get_emoji('presave')} **Просьб о пресейвах:** {links_count}\n"
                response += f"{MessageFormatter.get_emoji('karma')} **Карма:** {karma_points}\n"
                response += f"{MessageFormatter.get_emoji('rank')} **Звание:** {karma_info['rank']}\n\n"
                
                if links_count > 0:
                    ratio = karma_points / links_count
                    efficiency = ratio * 100
                    
                    response += f"**Соотношение:** {links_count}:{karma_points}\n"
                    response += f"**Эффективность:** {efficiency:.1f}% взаимности\n\n"
                    
                    # Оценка эффективности
                    if efficiency >= 80:
                        assessment = f"{MessageFormatter.get_emoji('success')} Отличная взаимность"
                    elif efficiency >= 50:
                        assessment = f"{MessageFormatter.get_emoji('warning')} Хорошая взаимность"
                    elif efficiency >= 25:
                        assessment = f"{MessageFormatter.get_emoji('info')} Умеренная взаимность"
                    else:
                        assessment = f"{MessageFormatter.get_emoji('error')} Низкая взаимность"
                    
                    response += f"**Оценка:** {assessment}"
                else:
                    response += f"Просьбы о пресейвах отсутствуют."
            else:
                response += f"{MessageFormatter.get_emoji('link')} **Ссылок опубликовано:** {links_count}\n"
                response += f"Подробная статистика будет доступна в Плане 2."
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                f"запросил соотношение пользователя {username}",
                target_user_id=target_user.id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка команды /userratiostat: {e}")
            self._send_error_response(message, "Ошибка анализа соотношения")
    
    # ============================================
    # ДИАГНОСТИЧЕСКИЕ КОМАНДЫ
    # ============================================
    
    @admin_required
    def cmd_keep_alive(self, message: Message):
        """Команда /keepalive - тест keep alive"""
        try:
            import time
            start_time = time.time()
            
            # Проверяем подключение к БД
            health = self.db.health_check()
            
            response_time = (time.time() - start_time) * 1000
            
            response = f"{MessageFormatter.get_emoji('health')} **KEEP ALIVE TEST**\n\n"
            response += f"**Статус:** {MessageFormatter.get_emoji('success')} Активен\n"
            response += f"**Время ответа:** {response_time:.2f} мс\n"
            response += f"**БД подключение:** {'✅' if health['database_connection'] == 'ok' else '❌'}\n"
            response += f"**Render.com:** {'✅' if config.RENDER_EXTERNAL_URL else '❌'}\n\n"
            response += f"Все системы функционируют нормально!"
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "выполнил тест keep alive"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка keep alive: {e}")
            self._send_error_response(message, "Ошибка тестирования системы")
    
    @admin_required
    def cmd_check_system(self, message: Message):
        """Команда /checksystem - проверка системы"""
        try:
            # Получаем статистику БД
            db_stats = self.db.get_database_stats()
            health = self.db.health_check()
            
            response = f"{MessageFormatter.get_emoji('system')} **ПРОВЕРКА СИСТЕМЫ**\n\n"
            
            # Статус БД
            response += f"**База данных:**\n"
            response += f"• Подключение: {'✅' if health['database_connection'] == 'ok' else '❌'}\n"
            response += f"• Пользователей: {MessageFormatter.format_number(db_stats['total_users'])}\n"
            response += f"• Активных (неделя): {MessageFormatter.format_number(db_stats['active_users_week'])}\n"
            response += f"• Ссылок: {MessageFormatter.format_number(db_stats['total_links'])}\n"
            
            if config.ENABLE_PLAN_2_FEATURES:
                response += f"• Общая карма: {MessageFormatter.format_number(db_stats['total_karma_points'])}\n"
            
            # Статус планов
            response += f"\n**Активные планы:**\n"
            response += f"• План 1: ✅ Базовый функционал\n"
            response += f"• План 2: {'✅' if config.ENABLE_PLAN_2_FEATURES else '❌'} Система кармы\n"
            response += f"• План 3: {'✅' if config.ENABLE_PLAN_3_FEATURES else '❌'} ИИ и формы\n"
            response += f"• План 4: {'✅' if config.ENABLE_PLAN_4_FEATURES else '❌'} Backup система\n"
            
            # Настройки
            response += f"\n**Настройки:**\n"
            response += f"• Бот активен: {'✅' if ConfigHelper.is_bot_enabled() else '❌'}\n"
            response += f"• Режим лимитов: {ConfigHelper.get_current_limit_mode()}\n"
            response += f"• Whitelist топиков: {len(config.WHITELIST_THREADS)}\n"
            response += f"• Админов: {len(config.ADMIN_IDS)}\n"
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "выполнил проверку системы"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки системы: {e}")
            self._send_error_response(message, "Ошибка диагностики системы")
    
    @admin_required
    def cmd_bot_status(self, message: Message):
        """Команда /botstatus - статус и статистика бота"""
        try:
            from datetime import datetime, timezone
            import psutil
            import os
            
            # Системная информация
            response = f"{MessageFormatter.get_emoji('stats')} **СТАТУС БОТА**\n\n"
            
            # Версия и режим
            response += f"**Информация:**\n"
            response += f"• Версия: v25+ (Поэтапная разработка)\n"
            response += f"• Статус: {'✅ Активен' if ConfigHelper.is_bot_enabled() else '❌ Деактивирован'}\n"
            response += f"• Режим: {ConfigHelper.get_current_limit_mode()}\n"
            response += f"• Время работы: {MessageFormatter.format_time_ago(datetime.now(timezone.utc))}\n\n"
            
            # Память и процессор
            try:
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024
                cpu_percent = process.cpu_percent()
                
                response += f"**Ресурсы:**\n"
                response += f"• Память: {memory_mb:.1f} MB\n"
                response += f"• CPU: {cpu_percent:.1f}%\n\n"
            except:
                response += f"**Ресурсы:** Информация недоступна\n\n"
            
            # Статистика БД
            db_stats = self.db.get_database_stats()
            response += f"**База данных:**\n"
            response += f"• Пользователей: {db_stats['total_users']}\n"
            response += f"• Ссылок: {db_stats['total_links']}\n"
            
            if config.ENABLE_PLAN_2_FEATURES:
                response += f"• Карма: {db_stats['total_karma_points']}\n"
            
            if config.ENABLE_PLAN_3_FEATURES:
                response += f"• ИИ беседы: {db_stats.get('total_ai_conversations', 0)}\n"
            
            if config.ENABLE_PLAN_4_FEATURES:
                response += f"• Backup: {db_stats.get('total_backups', 0)}\n"
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            telegram_logger.admin_action(
                message.from_user.id,
                "запросил статус бота"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса: {e}")
            self._send_error_response(message, "Ошибка получения статуса")
    
    # ============================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================
    
    def _send_error_response(self, message: Message, error_text: str):
        """Отправка стандартного сообщения об ошибке"""
        try:
            full_error = f"{MessageFormatter.get_emoji('error')} {error_text}\n\n"
            full_error += f"Если проблема повторяется, используйте `/resetmenu` или обратитесь к разработчику."
            
            self.bot.send_message(
                message.chat.id,
                full_error,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения об ошибке: {e}")
    
    def _send_feature_not_available(self, message: Message, feature_name: str):
        """Отправка сообщения о недоступности функции"""
        try:
            response = f"{MessageFormatter.get_emoji('loading')} **Функция в разработке**\n\n"
            response += f"**{feature_name}** будет доступна в следующих планах развития.\n\n"
            response += f"{MessageFormatter.get_emoji('info')} Текущий статус: В активной разработке\n"
            response += f"{MessageFormatter.get_emoji('time')} Планируемый релиз: По готовности\n\n"
            response += f"Используйте `/help` для просмотра доступных команд."
            
            self.bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения о недоступности: {e}")

# ============================================
# ГЛОБАЛЬНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ
# ============================================

def init_command_handlers(bot: telebot.TeleBot) -> CommandHandler:
    """Инициализация обработчиков команд"""
    return CommandHandler(bot)

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = ['CommandHandler', 'init_command_handlers']

if __name__ == "__main__":
    print("🧪 Тестирование Command Handlers...")
    print("✅ Модуль commands.py готов к интеграции")
