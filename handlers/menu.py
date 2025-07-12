"""
🎛️ Menu System - Do Presave Reminder Bot v25+
Центральная система меню с навигацией для всех планов развития
"""

from typing import Optional, Dict, Any, List, Tuple
import telebot
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup

from config import config
from database.manager import get_database_manager
from utils.security import admin_required, security_manager, AccessDeniedError
from utils.logger import get_logger, telegram_logger
from utils.helpers import (
    MessageFormatter, KeyboardBuilder, UserHelper, 
    DataHelper, ConfigHelper
)

logger = get_logger(__name__)

class MenuManager:
    """Центральный менеджер системы меню"""
    
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot
        self.db = get_database_manager()
        
        # Регистрируем обработчики
        self._register_handlers()
        
        logger.info("🎛️ Menu Manager инициализирован")
    
    def _register_handlers(self):
        """Регистрация всех обработчиков меню"""
        
        # Основные команды меню
        @self.bot.message_handler(commands=['menu'])
        @admin_required
        def handle_menu_command(message: Message):
            self.show_main_menu(message)
        
        @self.bot.message_handler(commands=['resetmenu'])
        @admin_required
        def handle_reset_menu_command(message: Message):
            self.reset_menu(message)
        
        @self.bot.message_handler(commands=['help'])
        def handle_help_command(message: Message):
            self.show_help(message)
        
        # Обработчики callback'ов меню
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('menu_'))
        def handle_menu_callbacks(call: CallbackQuery):
            self.handle_menu_callback(call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('leaderboard_'))
        def handle_leaderboard_callbacks(call: CallbackQuery):
            self.handle_leaderboard_callback(call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('action_'))
        def handle_action_callbacks(call: CallbackQuery):
            self.handle_action_callback(call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('settings_'))
        def handle_settings_callbacks(call: CallbackQuery):
            self.handle_settings_callback(call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith('limits_'))
        def handle_limits_callbacks(call: CallbackQuery):
            self.handle_limits_callback(call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data == 'under_development')
        def handle_under_development(call: CallbackQuery):
            self.show_under_development(call)
    
    # ============================================
    # ОСНОВНЫЕ ФУНКЦИИ МЕНЮ
    # ============================================
    
    @admin_required
    def show_main_menu(self, message_or_call, edit_message: bool = False):
        """Показ главного меню (только для админов)"""
        try:
            # Определяем тип объекта
            if isinstance(message_or_call, CallbackQuery):
                user_id = message_or_call.from_user.id
                chat_id = message_or_call.message.chat.id
                message_id = message_or_call.message.message_id
                edit_message = True
            else:
                user_id = message_or_call.from_user.id
                chat_id = message_or_call.chat.id
                message_id = None
            
            # Проверяем права админа
            if not security_manager.is_admin(user_id):
                error_text = f"{MessageFormatter.get_emoji('error')} Доступ запрещен!\n\n" \
                           f"Меню доступно только администраторам."
                
                if edit_message and message_id:
                    self.bot.edit_message_text(error_text, chat_id, message_id)
                else:
                    self.bot.send_message(chat_id, error_text)
                return
            
            # Формируем текст меню
            menu_text = self._generate_main_menu_text()
            
            # Создаем клавиатуру
            keyboard = KeyboardBuilder.create_main_menu_keyboard()
            
            # Отправляем или редактируем
            if edit_message and message_id:
                self.bot.edit_message_text(
                    menu_text, 
                    chat_id, 
                    message_id,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            else:
                self.bot.send_message(
                    chat_id,
                    menu_text,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
            
            telegram_logger.admin_action(user_id, "открыл главное меню")
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа главного меню: {e}")
            self._send_error_message(message_or_call, "Ошибка отображения меню")
    
    def _generate_main_menu_text(self) -> str:
        """Генерация текста главного меню"""
        text = f"{MessageFormatter.get_emoji('menu')} **ГЛАВНОЕ МЕНЮ**\n\n"
        
        # Статус бота
        bot_enabled = ConfigHelper.is_bot_enabled()
        status_emoji = MessageFormatter.get_emoji('success' if bot_enabled else 'error')
        status_text = "Активен" if bot_enabled else "Деактивирован"
        text += f"{status_emoji} **Статус бота:** {status_text}\n"
        
        # Текущий режим лимитов
        current_mode = ConfigHelper.get_current_limit_mode()
        text += f"{MessageFormatter.get_emoji('system')} **Режим лимитов:** {current_mode}\n"
        
        # Включенные планы
        text += f"\n{MessageFormatter.get_emoji('info')} **Активные функции:**\n"
        text += f"• {MessageFormatter.get_emoji('success')} План 1: Базовый функционал\n"
        
        if config.ENABLE_PLAN_2_FEATURES:
            text += f"• {MessageFormatter.get_emoji('success')} План 2: Система кармы\n"
        else:
            text += f"• {MessageFormatter.get_emoji('loading')} План 2: В разработке\n"
        
        if config.ENABLE_PLAN_3_FEATURES:
            text += f"• {MessageFormatter.get_emoji('success')} План 3: ИИ и интерактивные формы\n"
        else:
            text += f"• {MessageFormatter.get_emoji('loading')} План 3: В разработке\n"
        
        if config.ENABLE_PLAN_4_FEATURES:
            text += f"• {MessageFormatter.get_emoji('success')} План 4: Backup система\n"
        else:
            text += f"• {MessageFormatter.get_emoji('loading')} План 4: В разработке\n"
        
        text += f"\n{MessageFormatter.get_emoji('info')} Выберите раздел для управления:"
        
        return text
    
    @admin_required 
    def reset_menu(self, message: Message):
        """Сброс и перезапуск меню"""
        try:
            # Отправляем уведомление о сбросе
            reset_text = f"{MessageFormatter.get_emoji('loading')} Перезапуск системы меню...\n\n" \
                        f"{MessageFormatter.get_emoji('success')} Все функции восстановлены!\n" \
                        f"{MessageFormatter.get_emoji('info')} Статистика и настройки сохранены."
            
            self.bot.send_message(
                message.chat.id,
                reset_text,
                parse_mode='Markdown'
            )
            
            # Показываем главное меню
            self.show_main_menu(message)
            
            telegram_logger.admin_action(
                message.from_user.id, 
                "выполнил сброс меню"
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка сброса меню: {e}")
            self._send_error_message(message, "Ошибка сброса меню")
    
    def show_help(self, message: Message):
        """Показ справки по командам"""
        try:
            help_text = self._generate_help_text(message.from_user.id)
            
            # Разбиваем на части если слишком длинное
            max_length = 4000
            if len(help_text) > max_length:
                parts = [help_text[i:i+max_length] for i in range(0, len(help_text), max_length)]
                for i, part in enumerate(parts):
                    if i == 0:
                        self.bot.send_message(message.chat.id, part, parse_mode='Markdown')
                    else:
                        self.bot.send_message(message.chat.id, f"*Продолжение справки:*\n\n{part}", parse_mode='Markdown')
            else:
                self.bot.send_message(message.chat.id, help_text, parse_mode='Markdown')
            
            telegram_logger.user_action(message.from_user.id, "запросил справку")
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа справки: {e}")
            self._send_error_message(message, "Ошибка отображения справки")
    
    def _generate_help_text(self, user_id: int) -> str:
        """Генерация текста справки"""
        is_admin = security_manager.is_admin(user_id)
        
        text = f"{MessageFormatter.get_emoji('info')} **СПРАВКА ПО КОМАНДАМ**\n\n"
        
        if is_admin:
            text += f"{MessageFormatter.get_emoji('admin')} **АДМИНСКИЕ КОМАНДЫ:**\n\n"
            
            # План 1 - Базовые команды
            text += f"**{MessageFormatter.get_emoji('menu')} Основное управление:**\n"
            text += f"• `/menu` - Открыть главное меню\n"
            text += f"• `/resetmenu` - Перезапустить систему меню\n"
            text += f"• `/help` - Показать эту справку\n"
            text += f"• `/enablebot` - Активировать бота\n"
            text += f"• `/disablebot` - Деактивировать бота\n\n"
            
            text += f"**{MessageFormatter.get_emoji('system')} Режимы лимитов:**\n"
            text += f"• `/setmode_conservative` - Консервативный режим\n"
            text += f"• `/setmode_normal` - Обычный режим\n"
            text += f"• `/setmode_burst` - Burst режим (по умолчанию)\n"
            text += f"• `/setmode_adminburst` - Admin Burst режим\n"
            text += f"• `/currentmode` - Текущий режим лимитов\n"
            text += f"• `/reloadmodes` - Перезагрузить настройки режимов\n\n"
            
            text += f"**{MessageFormatter.get_emoji('link')} Работа со ссылками:**\n"
            text += f"• `/last10links` - Последние 10 ссылок\n"
            text += f"• `/last30links` - Последние 30 ссылок\n"
            text += f"• `/clearlinks` - Очистить историю ссылок\n\n"
            
            # План 2 - Система кармы
            if config.ENABLE_PLAN_2_FEATURES:
                text += f"**{MessageFormatter.get_emoji('karma')} Система кармы:**\n"
                text += f"• `/karma @username +5` - Изменить карму пользователя\n"
                text += f"• `/karmastat` - Лидерборд по карме\n"
                text += f"• `/presavestat` - Лидерборд по просьбам о пресейвах\n"
                text += f"• `/ratiostat @username 15:12` - Изменить соотношение пользователя\n\n"
            else:
                text += f"**{MessageFormatter.get_emoji('loading')} Система кармы (в разработке):**\n"
                text += f"• Команды кармы будут доступны в Плане 2\n\n"
            
            # План 3 - ИИ и формы
            if config.ENABLE_PLAN_3_FEATURES:
                text += f"**{MessageFormatter.get_emoji('ai')} ИИ и интерактивные формы:**\n"
                text += f"• `/checkapprovals` - Проверить заявки на аппрувы\n"
                text += f"• `/editreminder` - Изменить текст напоминания\n"
                text += f"• `/clearapprovals` - Очистить заявки на аппрувы\n"
                text += f"• `/clearasks` - Очистить историю просьб\n\n"
            else:
                text += f"**{MessageFormatter.get_emoji('loading')} ИИ и формы (в разработке):**\n"
                text += f"• Интерактивные функции будут доступны в Плане 3\n\n"
            
            # План 4 - Backup система
            if config.ENABLE_PLAN_4_FEATURES:
                text += f"**{MessageFormatter.get_emoji('backup')} Backup система:**\n"
                text += f"• `/downloadsql` - Создать backup базы данных\n"
                text += f"• `/backupstatus` - Статус и возраст базы данных\n"
                text += f"• `/backuphelp` - Инструкции по backup/restore\n\n"
            else:
                text += f"**{MessageFormatter.get_emoji('loading')} Backup система (в разработке):**\n"
                text += f"• Функции backup будут доступны в Плане 4\n\n"
            
            text += f"**{MessageFormatter.get_emoji('stats')} Аналитика:**\n"
            text += f"• `/mystat` - Моя статистика\n"
            text += f"• `/linksby @username` - Ссылки пользователя\n"
            text += f"• `/approvesby @username` - Карма пользователя\n"
            text += f"• `/userratiostat @username` - Соотношение пользователя\n\n"
            
            text += f"**{MessageFormatter.get_emoji('system')} Диагностика:**\n"
            text += f"• `/keepalive` - Тест Keep Alive\n"
            text += f"• `/checksystem` - Проверка системы\n"
            text += f"• `/botstatus` - Статус и статистика бота\n\n"
        
        else:
            text += f"{MessageFormatter.get_emoji('user')} **ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ:**\n\n"
            text += f"• `/help` - Показать эту справку\n"
            text += f"• `/mystat` - Моя статистика\n\n"
            
            text += f"{MessageFormatter.get_emoji('info')} **Как использовать бота:**\n"
            text += f"• Публикуйте ссылки на пресейвы в разрешённых топиках\n"
            text += f"• Бот автоматически напомнит о взаимных пресейвах\n"
            text += f"• Благодарите других участников - это влияет на карму\n"
            text += f"• Для доступа к расширенным функциям обратитесь к админам\n\n"
        
        # Общая информация
        text += f"**{MessageFormatter.get_emoji('info')} ОБЩАЯ ИНФОРМАЦИЯ:**\n\n"
        text += f"**Версия бота:** v25+ (поэтапная разработка)\n"
        text += f"**Разработчик:** @Mister_DMS\n"
        text += f"**Назначение:** Автоматизация взаимных пресейвов в музыкальном сообществе\n\n"
        
        text += f"**Поддерживаемые сервисы:**\n"
        text += f"• {MessageFormatter.get_emoji('spotify')} Spotify\n"
        text += f"• {MessageFormatter.get_emoji('apple_music')} Apple Music\n"
        text += f"• {MessageFormatter.get_emoji('youtube')} YouTube Music\n"
        text += f"• {MessageFormatter.get_emoji('music')} SoundCloud, Bandcamp, Deezer и другие\n\n"
        
        if is_admin:
            text += f"{MessageFormatter.get_emoji('warning')} **ВАЖНО:** Все админские команды логируются и мониторятся."
        
        return text
    
    # ============================================
    # ОБРАБОТЧИКИ CALLBACK'ОВ
    # ============================================
    
    def handle_menu_callback(self, call: CallbackQuery):
        """Обработка callback'ов основного меню"""
        try:
            data = call.data
            
            if data == 'menu_main':
                self.show_main_menu(call, edit_message=True)
            
            elif data == 'menu_mystat':
                self.show_my_statistics(call)
            
            elif data == 'menu_leaderboard':
                self.show_leaderboard_menu(call)
            
            elif data == 'menu_actions':
                self.show_actions_menu(call)
            
            elif data == 'menu_analytics':
                self.show_analytics_menu(call)
            
            elif data == 'menu_diagnostics':
                self.show_diagnostics_menu(call)
            
            elif data == 'menu_ai':
                self.show_ai_menu(call)
            
            elif data == 'menu_help':
                self.show_help_from_menu(call)
            
            elif data == 'menu_settings':
                self.show_settings_menu(call)
            
            # Подтверждаем callback
            self.bot.answer_callback_query(call.id)
            
        except AccessDeniedError:
            self.bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
        except Exception as e:
            logger.error(f"❌ Ошибка обработки callback меню: {e}")
            self.bot.answer_callback_query(call.id, "❌ Произошла ошибка", show_alert=True)
    
    @admin_required
    def show_my_statistics(self, call: CallbackQuery):
        """Показ статистики текущего пользователя"""
        try:
            user_id = call.from_user.id
            stats = self.db.get_user_stats(user_id)
            
            stats_text = UserHelper.format_user_stats_message(stats)
            
            keyboard = KeyboardBuilder.create_back_button('menu_main')
            
            self.bot.edit_message_text(
                stats_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа статистики: {e}")
            self._send_callback_error(call, "Ошибка загрузки статистики")
    
    @admin_required
    def show_leaderboard_menu(self, call: CallbackQuery):
        """Показ меню лидербордов"""
        try:
            text = f"{MessageFormatter.get_emoji('leaderboard')} **ЛИДЕРБОРДЫ**\n\n"
            
            if config.ENABLE_PLAN_2_FEATURES:
                text += f"{MessageFormatter.get_emoji('info')} Выберите тип рейтинга:\n\n"
                text += f"• **По просьбам о пресейвах** - кто больше всех просил поддержки\n"
                text += f"• **По карме** - рейтинг по заработанной карме\n"
                text += f"• **По соотношению** - эффективность взаимной поддержки"
            else:
                text += f"{MessageFormatter.get_emoji('loading')} Лидерборды будут доступны после активации Плана 2 (Система кармы).\n\n"
                text += f"Пока доступна только базовая статистика ссылок."
            
            keyboard = KeyboardBuilder.create_leaderboard_keyboard()
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа меню лидербордов: {e}")
            self._send_callback_error(call, "Ошибка меню лидербордов")
    
    @admin_required
    def show_actions_menu(self, call: CallbackQuery):
        """Показ меню действий"""
        try:
            text = f"{MessageFormatter.get_emoji('form')} **ДЕЙСТВИЯ**\n\n"
            text += f"{MessageFormatter.get_emoji('info')} Доступные операции:\n\n"
            
            if config.ENABLE_PLAN_3_FEATURES:
                text += f"• **Интерактивные формы** - удобная подача заявок\n"
                text += f"• **Модерация аппрувов** - проверка заявок пользователей\n"
            else:
                text += f"• **Интерактивные формы** - будут доступны в Плане 3\n"
            
            text += f"• **Просмотр ссылок** - последние запросы пресейвов\n"
            text += f"• **Настройки бота** - конфигурация системы"
            
            keyboard = KeyboardBuilder.create_actions_keyboard()
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа меню действий: {e}")
            self._send_callback_error(call, "Ошибка меню действий")
    
    @admin_required
    def show_settings_menu(self, call: CallbackQuery):
        """Показ меню настроек"""
        try:
            text = f"{MessageFormatter.get_emoji('system')} **НАСТРОЙКИ БОТА**\n\n"
            
            # Текущие настройки
            bot_enabled = ConfigHelper.is_bot_enabled()
            current_mode = ConfigHelper.get_current_limit_mode()
            
            text += f"**Текущее состояние:**\n"
            text += f"• Статус: {'✅ Активен' if bot_enabled else '❌ Деактивирован'}\n"
            text += f"• Режим лимитов: {current_mode}\n\n"
            
            text += f"{MessageFormatter.get_emoji('info')} Выберите настройку для изменения:"
            
            keyboard = KeyboardBuilder.create_settings_keyboard()
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа настроек: {e}")
            self._send_callback_error(call, "Ошибка меню настроек")
    
    def show_under_development(self, call: CallbackQuery):
        """Показ сообщения о разработке"""
        try:
            text = f"{MessageFormatter.get_emoji('loading')} **ФУНКЦИЯ В РАЗРАБОТКЕ**\n\n"
            text += f"{MessageFormatter.get_emoji('info')} Эта функция будет доступна в следующих планах развития:\n\n"
            text += f"• **План 2** - Система кармы и лидерборды\n"
            text += f"• **План 3** - ИИ и интерактивные формы\n"
            text += f"• **План 4** - Расширенная backup система\n\n"
            text += f"{MessageFormatter.get_emoji('time')} Разработка ведется поэтапно для обеспечения стабильности.\n\n"
            text += f"**Текущий статус:** В активной разработке\n"
            text += f"**Разработчик:** @Mister_DMS"
            
            keyboard = KeyboardBuilder.create_back_button('menu_main')
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
            self.bot.answer_callback_query(
                call.id, 
                "🔄 Функция в разработке", 
                show_alert=False
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа сообщения о разработке: {e}")
    
    # ============================================
    # ЗАГЛУШКИ ДЛЯ БУДУЩИХ ПЛАНОВ
    # ============================================
    
    def handle_leaderboard_callback(self, call: CallbackQuery):
        """Обработчик лидербордов (заглушка для Плана 2)"""
        if not config.ENABLE_PLAN_2_FEATURES:
            self.show_under_development(call)
            return
        
        # Здесь будет реализация лидербордов в Плане 2
        self.bot.answer_callback_query(call.id, "Лидерборды в разработке")
    
    def handle_action_callback(self, call: CallbackQuery):
        """Обработчик действий"""
        data = call.data
        
        if data.startswith('action_last'):
            # Обработка просмотра ссылок
            if data == 'action_last10_links':
                self.show_recent_links(call, limit=10)
            elif data == 'action_last30_links':
                self.show_recent_links(call, limit=30)
        
        elif data.startswith('action_ask') or data.startswith('action_claim') or data.startswith('action_check'):
            # Интерактивные формы (План 3)
            if not config.ENABLE_PLAN_3_FEATURES:
                self.show_under_development(call)
            else:
                # Здесь будет реализация форм в Плане 3
                self.bot.answer_callback_query(call.id, "Интерактивные формы в разработке")
        
        self.bot.answer_callback_query(call.id)
    
    def handle_settings_callback(self, call: CallbackQuery):
        """Обработчик настроек"""
        data = call.data
        
        if data == 'settings_limits':
            self.show_limits_menu(call)
        else:
            # Остальные настройки будут реализованы позже
            self.bot.answer_callback_query(call.id, "Настройка в разработке")
    
    def handle_limits_callback(self, call: CallbackQuery):
        """Обработчик режимов лимитов"""
        # Будет реализовано в handlers/commands.py
        self.bot.answer_callback_query(call.id, "Переключение режимов в разработке")
    
    @admin_required
    def show_recent_links(self, call: CallbackQuery, limit: int = 10):
        """Показ последних ссылок"""
        try:
            links = self.db.get_recent_links(limit=limit)
            
            text = DataHelper.format_links_list(links, max_links=limit)
            
            keyboard = KeyboardBuilder.create_back_button('menu_actions')
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа ссылок: {e}")
            self._send_callback_error(call, "Ошибка загрузки ссылок")
    
    @admin_required
    def show_limits_menu(self, call: CallbackQuery):
        """Показ меню режимов лимитов"""
        try:
            current_mode = ConfigHelper.get_current_limit_mode()
            
            text = f"{MessageFormatter.get_emoji('system')} **РЕЖИМЫ ЛИМИТОВ API**\n\n"
            text += ConfigHelper.format_limit_mode_info(current_mode)
            text += f"\n\n{MessageFormatter.get_emoji('info')} Выберите новый режим:"
            
            keyboard = KeyboardBuilder.create_limits_keyboard()
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа меню лимитов: {e}")
            self._send_callback_error(call, "Ошибка меню лимитов")
    
    # ============================================
    # ЗАГЛУШКИ ДЛЯ БУДУЩИХ РАЗДЕЛОВ
    # ============================================
    
    @admin_required
    def show_analytics_menu(self, call: CallbackQuery):
        """Заглушка для меню аналитики"""
        text = f"{MessageFormatter.get_emoji('loading')} **РАСШИРЕННАЯ АНАЛИТИКА**\n\n"
        text += f"Функции аналитики будут доступны после реализации соответствующих планов."
        
        keyboard = KeyboardBuilder.create_back_button('menu_main')
        
        self.bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    @admin_required
    def show_diagnostics_menu(self, call: CallbackQuery):
        """Заглушка для меню диагностики"""
        text = f"{MessageFormatter.get_emoji('loading')} **ДИАГНОСТИКА СИСТЕМЫ**\n\n"
        text += f"Функции диагностики будут доступны после реализации соответствующих планов."
        
        keyboard = KeyboardBuilder.create_back_button('menu_main')
        
        self.bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    @admin_required
    def show_ai_menu(self, call: CallbackQuery):
        """Заглушка для меню ИИ"""
        if not config.ENABLE_PLAN_3_FEATURES:
            self.show_under_development(call)
            return
        
        text = f"{MessageFormatter.get_emoji('ai')} **ИИ И АВТОМАТИЗАЦИЯ**\n\n"
        text += f"Настройки ИИ и автоматизации будут доступны в Плане 3."
        
        keyboard = KeyboardBuilder.create_back_button('menu_main')
        
        self.bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
    
    def show_help_from_menu(self, call: CallbackQuery):
        """Показ справки из меню"""
        try:
            help_text = self._generate_help_text(call.from_user.id)
            
            # Ограничиваем длину для callback
            if len(help_text) > 4000:
                help_text = help_text[:4000] + "\n\n*Используйте /help для полной справки*"
            
            keyboard = KeyboardBuilder.create_back_button('menu_main')
            
            self.bot.edit_message_text(
                help_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа справки из меню: {e}")
            self._send_callback_error(call, "Ошибка отображения справки")
    
    # ============================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================
    
    def _send_error_message(self, message_or_call, error_text: str):
        """Отправка сообщения об ошибке"""
        try:
            full_error = f"{MessageFormatter.get_emoji('error')} {error_text}\n\n" \
                        f"Попробуйте выполнить команду /resetmenu для восстановления."
            
            if isinstance(message_or_call, CallbackQuery):
                chat_id = message_or_call.message.chat.id
            else:
                chat_id = message_or_call.chat.id
            
            self.bot.send_message(chat_id, full_error, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки сообщения об ошибке: {e}")
    
    def _send_callback_error(self, call: CallbackQuery, error_text: str):
        """Отправка ошибки для callback"""
        try:
            self.bot.answer_callback_query(call.id, f"❌ {error_text}", show_alert=True)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки callback ошибки: {e}")

# ============================================
# ГЛОБАЛЬНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ
# ============================================

def init_menu_system(bot: telebot.TeleBot) -> MenuManager:
    """Инициализация системы меню"""
    return MenuManager(bot)

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = ['MenuManager', 'init_menu_system']

if __name__ == "__main__":
    print("🧪 Тестирование Menu System...")
    print("✅ Модуль menu.py готов к интеграции")
