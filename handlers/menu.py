"""
ЦЕНТРАЛЬНЫЙ обработчик меню Do Presave Reminder Bot v25+
ВСЁ что касается меню бота: команды, кнопки, навигация, "НАЗАД", "ГЛАВНОЕ МЕНЮ"

ПЛАН 1: Базовое меню (АКТИВНО)
ПЛАН 2: Расширение для кармы (ЗАГЛУШКИ)
ПЛАН 3: Расширение для ИИ и форм (ЗАГЛУШКИ)  
ПЛАН 4: Расширение для backup (ЗАГЛУШКИ)
"""

from typing import List, Dict, Any, Optional, Tuple
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import os
from database.manager import DatabaseManager
from utils.security import SecurityManager, admin_required, whitelist_required
from utils.logger import get_logger, log_user_action
from utils.helpers import format_user_mention
from datetime import datetime

logger = get_logger(__name__)

def create_webapp_keyboard(webapp_url: str, additional_buttons: List[Tuple[str, str]] = None) -> telebot.types.InlineKeyboardMarkup:
    """Умная WebApp клавиатура с множественными fallback для сохранения функциональности"""
    try:
        markup = telebot.types.InlineKeyboardMarkup()
        
        # МЕТОД 1: Пробуем правильный синтаксис url=
        try:
            webapp_button = telebot.types.InlineKeyboardButton(
                "🌐 Интерактивный гайд",
                web_app=telebot.types.WebAppInfo(url=webapp_url)
            )
            markup.add(webapp_button)
            logger.info("✅ WebApp кнопка создана (синтаксис url=)")
        except Exception as method1_error:
            logger.warning(f"⚠️ Метод 1 (url=) не сработал: {method1_error}")
            
            # МЕТОД 2: Пробуем старый синтаксис без url=
            try:
                webapp_button = telebot.types.InlineKeyboardButton(
                    "🌐 Интерактивный гайд",
                    web_app=telebot.types.WebAppInfo(webapp_url)
                )
                markup.add(webapp_button)
                logger.info("✅ WebApp кнопка создана (старый синтаксис)")
            except Exception as method2_error:
                logger.warning(f"⚠️ Метод 2 (старый синтаксис) не сработал: {method2_error}")
                
                # МЕТОД 3: Создаем объект отдельно
                try:
                    webapp_info = telebot.types.WebAppInfo(url=webapp_url)
                    webapp_button = telebot.types.InlineKeyboardButton(
                        "🌐 Интерактивный гайд",
                        web_app=webapp_info
                    )
                    markup.add(webapp_button)
                    logger.info("✅ WebApp кнопка создана (отдельный объект)")
                except Exception as method3_error:
                    logger.warning(f"⚠️ Метод 3 (отдельный объект) не сработал: {method3_error}")
                    
                    # ПОСЛЕДНИЙ FALLBACK: URL кнопка (НЕ WebApp, но работает)
                    try:
                        webapp_button = telebot.types.InlineKeyboardButton(
                            "🌐 Открыть гайд (в браузере)",
                            url=webapp_url
                        )
                        markup.add(webapp_button)
                        logger.warning("⚠️ WebApp не поддерживается, используем URL кнопку")
                    except Exception as final_error:
                        logger.error(f"❌ Критическая ошибка: {final_error}")
                        # Создаем просто кнопку справки
                        markup.add(
                            telebot.types.InlineKeyboardButton("📋 Краткая справка", callback_data="about_quick")
                        )
        
        # Дополнительные кнопки
        if additional_buttons:
            for button_text, callback_data in additional_buttons:
                markup.add(telebot.types.InlineKeyboardButton(button_text, callback_data=callback_data))
        
        # Навигация
        markup.add(
            telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="menu_main"),
            telebot.types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")
        )
        
        return markup
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка create_webapp_keyboard: {e}")
        # Аварийная клавиатура
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(
            telebot.types.InlineKeyboardButton("📋 Краткая справка", callback_data="about_quick")
        )
        markup.add(
            telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="menu_main"),
            telebot.types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")
        )
        return markup

class MenuHandler:
    """ЦЕНТРАЛЬНЫЙ обработчик всего функционала меню"""
    
    def __init__(self, bot: telebot.TeleBot, db_manager: DatabaseManager, security_manager: SecurityManager):
        """Инициализация обработчика меню"""
        self.bot = bot
        self.db = db_manager
        self.security = security_manager
        
        # Структура меню для всех планов
        self.menu_structure = self._build_menu_structure()
        
        logger.info("MenuHandler инициализирован")
    
    def _build_menu_structure(self) -> Dict[str, Any]:
        """Построение структуры меню для всех планов"""
        return {
            'main': {
                'title': '📋 Главное меню (v25+)',
                'description': 'Добро пожаловать в панель управления ботом!',
                'buttons': [
                    ('📊 Моя статистика', 'menu_mystats'),
                    ('🏆 Лидерборд Топ-10', 'menu_leaderboard'),
                    ('⚙️ Действия', 'menu_actions'),
                    ('📊 Расширенная аналитика', 'menu_analytics'),
                    ('🔧 Диагностика', 'menu_diagnostics'),
                    # ПЛАН 3: Кнопка ИИ (ЗАГЛУШКА)
                    # ('🤖 ИИ и автоматизация', 'menu_ai'),
                    ('📖 О боте v25.1', 'about_v25'),
                    ('❓ Помощь', 'menu_help')
                ]
            },

            'mystats': {
                'title': '📊 Моя статистика',
                'description': 'Персональная статистика и активность',
                'buttons': [
                    ('📎 Мои ссылки', 'mystats_my_links'),
                    ('📅 Активность по дням', 'mystats_daily_activity'),
                    ('🏆 Мой рейтинг', 'mystats_my_ranking'),
                    # ПЛАН 2: Статистика кармы (ЗАГЛУШКИ)
                    # ('⭐ Моя карма', 'mystats_my_karma'),
                    # ('🎖️ Мое звание', 'mystats_my_rank'),
                    ('🔙 Назад', 'menu_main'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            },

            'leaderboard': {
                'title': '🏆 Лидерборд Топ-10',
                'description': 'Рейтинги участников сообщества',
                'buttons': [
                    ('📝 По просьбам о пресейвах', 'leaderboard_requests'),  # ПЛАН 2
                    ('🏆 По карме', 'leaderboard_karma'),  # ПЛАН 2
                    ('⚖️ По соотношению Просьба-Карма', 'leaderboard_ratio'),  # ПЛАН 2
                    ('🔙 Назад', 'menu_main'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            },
            
            'actions': {
                'title': '⚙️ Действия',
                'description': 'Основные действия с ботом',
                'buttons': [
                    # ПЛАН 3: Интерактивные формы (ЗАГЛУШКИ)
                    # ('🎵 Попросить о пресейве', 'action_ask_presave'),
                    # ('✅ Заявить о совершенном пресейве', 'action_claim_presave'),
                    # ('📋 Проверить заявки на аппрувы', 'action_check_approvals'),
                    
                    ('📎 Последние 30 ссылок', 'action_last30links'),
                    ('📎 Последние 10 ссылок', 'action_last10links'),
                    ('🎛️ Настройки бота', 'menu_settings'),
                    ('🔙 Назад', 'menu_main'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            },
            
            'settings': {
                'title': '🎛️ Настройки бота',
                'description': 'Управление настройками и режимами',
                'buttons': [
                    ('⚡ Режимы лимитов', 'menu_limits'),
                    ('🔄 Перезагрузить режимы', 'action_reload_modes'),
                    ('✅ Активировать бота', 'action_enable_bot'),
                    ('⏸️ Деактивировать бота', 'action_disable_bot'),
                    # ПЛАН 3: Настройка напоминаний (ЗАГЛУШКА)
                    # ('💬 Изменить напоминание', 'action_edit_reminder'),
                    ('🗑️ Очистить историю ссылок', 'action_clear_links'),
                    # ПЛАН 3: Дополнительные очистки (ЗАГЛУШКИ)
                    # ('🗑️ Очистить заявки на аппрувы', 'action_clear_approvals'),
                    # ('🗑️ Очистить историю просьб', 'action_clear_asks'),
                    ('🔙 Назад', 'menu_actions'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            },
            
            'limits': {
                'title': '⚡ Режимы лимитов API',
                'description': 'Управление скоростью обращений к Telegram API',
                'buttons': [
                    ('⚫️ Консерва', 'limit_conservative'),
                    ('🔵 Покатит', 'limit_normal'),
                    ('🟢 Живенько', 'limit_burst'),
                    ('🔴 пИчОт!', 'limit_admin_burst'),
                    ('📊 Текущий режим', 'action_current_mode'),
                    ('🔙 Назад', 'menu_settings'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            },
            
            'analytics': {
                'title': '📊 Расширенная аналитика',
                'description': 'Детальная аналитика по пользователям',
                'buttons': [
                    ('🔗 Ссылки по @username', 'analytics_links_by_user'),
                    # ПЛАН 2: Аналитика кармы (ЗАГЛУШКА)
                    # ('🏆 Карма по @username', 'analytics_karma_by_user'),
                    # ('⚖️ Соотношение по @username', 'analytics_ratio_by_user'),
                    ('🔙 Назад', 'menu_main'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            },
            
            'diagnostics': {
                'title': '🔧 Диагностика',
                'description': 'Проверка состояния системы',
                'buttons': [
                    ('💓 Тест Keep Alive', 'diag_keepalive'),
                    ('🔍 Проверка системы', 'diag_system_check'),
                    ('📊 Статус и статистика бота', 'diag_bot_status'),
                    # ПЛАН 4: Backup диагностика (ЗАГЛУШКА)
                    # ('💾 Статус backup', 'diag_backup_status'),
                    ('🔙 Назад', 'menu_main'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            },
            
            'diagnostics': {
                'title': '🔧 Диагностика',
                'description': 'Проверка состояния системы',
                'buttons': [
                    ('💓 Тест Keep Alive', 'diag_keepalive'),
                    ('🔍 Проверка системы', 'diag_system_check'),
                    ('📊 Статус и статистика бота', 'diag_bot_status'),
                    ('🔗 Проверка LinkHandler', 'diag_link_integration'),  # ← НОВАЯ КНОПКА
                    ('🔙 Назад', 'menu_main'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            },
            
            # ПЛАН 3: Меню ИИ (ЗАГЛУШКА)
            # 'ai': {
            #     'title': '🤖 ИИ и автоматизация',
            #     'description': 'Управление ИИ функциями и автоматизацией',
            #     'buttons': [
            #         ('⚙️ Настройки ИИ', 'ai_settings'),
            #         ('📖 Словарь благодарностей', 'ai_gratitude_dict'),
            #         ('📈 История автоначислений', 'ai_auto_karma_log'),
            #         ('📊 Статистика ИИ', 'ai_stats'),
            #         ('🔙 Назад', 'menu_main'),
            #         ('🏠 Главное меню', 'menu_main')
            #     ]
            # },
            
            'help': {
                'title': '❓ Помощь и команды',
                'description': 'Выберите подраздел',
                'buttons': [
                    ('📋 Список команд', 'help_commands'),
                    ('📖 Руководство пользователя', 'help_user_guide'),
                    ('🔧 Руководство админа', 'help_admin_guide'),
                    ('🔙 Назад', 'menu_main'),
                    ('🏠 Главное меню', 'menu_main')
                ]
            }
        }
    
    def create_keyboard(self, menu_key: str) -> InlineKeyboardMarkup:
        """Создание клавиатуры для меню"""
        if menu_key not in self.menu_structure:
            return self.create_keyboard('main')
        
        menu = self.menu_structure[menu_key]
        keyboard = InlineKeyboardMarkup(row_width=1)
        
        # Получаем текущий режим для индикации активного
        current_mode = self.db.get_setting('current_limit_mode', 'BURST') if menu_key == 'limits' else None
        
        for button_text, callback_data in menu['buttons']:
            # Проверяем доступность функций планов
            if self._is_button_available(callback_data):
                # Для меню лимитов добавляем индикатор активного режима
                display_text = button_text
                if menu_key == 'limits' and self._is_active_limit_mode(callback_data, current_mode):
                    display_text = f"👉🏻 {button_text}"
                
                keyboard.add(InlineKeyboardButton(display_text, callback_data=callback_data))
            else:
                # Показываем кнопку "в разработке"
                dev_text = f"{button_text} (в разработке)"
                keyboard.add(InlineKeyboardButton(dev_text, callback_data=f"dev_{callback_data}"))
        
        return keyboard
    
    def _is_button_available(self, callback_data: str) -> bool:
        """Проверка доступности функции"""
        # ПЛАН 2: Функции кармы
        plan2_callbacks = [
            'leaderboard_requests', 'leaderboard_karma', 'leaderboard_ratio',
            'analytics_karma_by_user', 'analytics_ratio_by_user'
        ]
        
        # ПЛАН 3: Функции ИИ и форм
        plan3_callbacks = [
            'action_ask_presave', 'action_claim_presave', 'action_check_approvals',
            'action_edit_reminder', 'action_clear_approvals', 'action_clear_asks',
            'menu_ai', 'ai_settings', 'ai_gratitude_dict', 'ai_auto_karma_log', 'ai_stats'
        ]
        
        # ПЛАН 4: Функции backup
        plan4_callbacks = [
            'diag_backup_status', 'action_backup_download', 'action_backup_help'
        ]
        
        # Проверяем feature flags
        if callback_data in plan2_callbacks:
            return self.db.get_setting('karma_enabled', False)
        elif callback_data in plan3_callbacks:
            return self.db.get_setting('ai_enabled', False) or self.db.get_setting('forms_enabled', False)
        elif callback_data in plan4_callbacks:
            return self.db.get_setting('backup_enabled', False)
        
        # ПЛАН 1: Все остальное доступно
        return True
    
    def get_menu_message(self, menu_key: str) -> str:
        """Получение текста сообщения для меню"""
        if menu_key not in self.menu_structure:
            menu_key = 'main'
        
        menu = self.menu_structure[menu_key]
        
        # Базовый текст
        message_parts = [
            f"<b>{menu['title']}</b>",
            "",
            menu['description']
        ]
        
        # Добавляем дополнительную информацию в зависимости от меню
        if menu_key == 'main':
            message_parts.extend([
                "",
                "🔧 <b>Статус системы:</b>",
                f"• Бот: {'✅ Активен' if self.db.get_setting('bot_enabled', True) else '⏸️ Отключен'}",
                f"• Режим лимитов: {self._get_current_limit_emoji()} {self.db.get_setting('current_limit_mode', 'BURST')}",
                # ПЛАН 2: Статус кармы (ЗАГЛУШКА)
                # f"• Карма: {'✅ Включена' if self.db.get_setting('karma_enabled', False) else '⏸️ Отключена'}",
                # ПЛАН 3: Статус ИИ (ЗАГЛУШКА)
                # f"• ИИ: {'✅ Включен' if self.db.get_setting('ai_enabled', False) else '⏸️ Отключен'}",
                # ПЛАН 4: Статус backup (ЗАГЛУШКА)
                # f"• Backup: {'✅ Включен' if self.db.get_setting('backup_enabled', False) else '⏸️ Отключен'}",
            ])
        
        elif menu_key == 'limits':
            current_mode = self.db.get_setting('current_limit_mode', 'BURST')
            message_parts.extend([
                "",
                f"📊 <b>Текущий режим:</b> {self._get_current_limit_emoji()} {current_mode}",
                "",
                "🔧 <b>Доступные режимы:</b>",
                "• ⚫️ <b>Консерва:</b> 60/час, кулдаун 60с",
                "• 🔵 <b>Покатит:</b> 180/час, кулдаун 20с", 
                "• 🟢 <b>Живенько:</b> 600/час, кулдаун 6с (по умолчанию)",
                "• 🔴 <b>пИчОт!:</b> 1200/час, кулдаун 3с"
            ])
        
        elif menu_key == 'diagnostics':
            stats = self.db.get_basic_stats()
            message_parts.extend([
                "",
                "📊 <b>Краткая статистика:</b>",
                f"• Пользователей: {stats.get('total_users', 0)}",
                f"• Админов: {stats.get('total_admins', 0)}",
                f"• Ссылок всего: {stats.get('total_links', 0)}",
                f"• Ссылок сегодня: {stats.get('links_today', 0)}",
                f"• Активных за неделю: {stats.get('active_users_week', 0)}"
            ])
        
        return "\n".join(message_parts)
    
    def _get_current_limit_emoji(self) -> str:
        """Получение эмодзи для текущего режима лимитов"""
        mode = self.db.get_setting('current_limit_mode', 'BURST')
        emoji_map = {
            'CONSERVATIVE': '⚫️',
            'NORMAL': '🔵',
            'BURST': '🟢',
            'ADMIN_BURST': '🔴'
        }
        return emoji_map.get(mode, '🚀')

    def _is_active_limit_mode(self, callback_data: str, current_mode: str) -> bool:
        """Проверка является ли режим лимитов активным"""
        mode_mapping = {
            'limit_conservative': 'CONSERVATIVE',
            'limit_normal': 'NORMAL',
            'limit_burst': 'BURST',
            'limit_admin_burst': 'ADMIN_BURST'
        }
        
        return mode_mapping.get(callback_data) == current_mode

    def create_navigation_keyboard(self, back_data: str = "menu_main", home_data: str = "menu_main") -> telebot.types.InlineKeyboardMarkup:
        """Создание навигационной клавиатуры"""
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            telebot.types.InlineKeyboardButton("🔙 Назад", callback_data=back_data),
            telebot.types.InlineKeyboardButton("🏠 Главное меню", callback_data=home_data)
        )
        return keyboard

    def _create_fallback_about_message(self) -> str:
        """Создание fallback сообщения без WebApp"""
        return """🔥 <b>Do Presave Reminder Bot v25.1</b>

🎵 <b>Твой личный помощник для музыкального хайпа!</b>

✨ <b>Что умеет бот:</b>
- Автоматические напоминания о пресейвах
- Статистика и рейтинги участников
- Интерактивное меню с кнопками
- Система кармы (скоро в ПЛАНЕ 2)

🎯 <b>Основные команды:</b>
/menu - главное меню
/mystat - твоя статистика
/help - список всех команд

💡 <i>Если WebApp не открывается, используйте "Краткая справка" или обычные команды.</i>"""

    # ============================================
    # КОМАНДЫ МЕНЮ
    # ============================================
    
    # @admin_required # Если меню хочется сделать только админским
    @whitelist_required
    def cmd_menu(self, message: Message):
        """Команда /menu - показ главного меню"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            chat_id = message.chat.id
            chat_type = message.chat.type
            thread_id = getattr(message, 'message_thread_id', None)
            
            # Проверка разрешенного топика (если не ЛС)
            if chat_type != 'private' and thread_id:
                if not self.security.is_thread_allowed(thread_id):
                    logger.info(f"Команда /resetmenu в неразрешенном топике {thread_id} проигнорирована")
                    return
            
            # ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
            logger.info(f"🔍 DEBUG menu.py cmd_menu: user={user_id}, chat={chat_id}, type={chat_type}, thread={thread_id}")
            
            log_user_action(logger, user_id, "открыл главное меню")
            
            # Создаем и отправляем главное меню
            text = self.get_menu_message('main')
            keyboard = self.create_keyboard('main')
            
            # ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
            logger.info(f"🔍 DEBUG отправляем меню в chat_id={chat_id}")
            
            self.bot.send_message(
                chat_id,  # ← Явно используем chat_id
                text,
                reply_markup=keyboard,
                parse_mode='HTML',
                message_thread_id=thread_id
            )
                
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_menu: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка открытия меню. Попробуйте /resetmenu",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    # @admin_required # Если хочется ограничить юзеров
    @whitelist_required
    def cmd_resetmenu(self, message: Message):
        """Команда /resetmenu - сброс меню"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            chat_id = message.chat.id
            chat_type = message.chat.type
            thread_id = getattr(message, 'message_thread_id', None)
            
            # Проверка разрешенного топика (если не ЛС)
            if chat_type != 'private' and thread_id:
                if not self.security.is_thread_allowed(thread_id):
                    logger.info(f"Команда /resetmenu в неразрешенном топике {thread_id} проигнорирована")
                    return
            
            # ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
            logger.info(f"🔍 DEBUG menu.py cmd_resetmenu: user={user_id}, chat={chat_id}, type={chat_type}, thread={thread_id}")
            
            log_user_action(logger, user_id, "сбросил меню")
            
            # ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
            logger.info(f"🔍 DEBUG отправляем сброс в chat_id={chat_id}")
            
            # Отправляем сообщение о сбросе
            self.bot.send_message(
                chat_id,  # ← Явно используем chat_id
                "🔄 <b>Меню сброшено!</b>\n\nВосстановление функционала...",
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
            # Показываем новое меню
            text = self.get_menu_message('main')
            keyboard = self.create_keyboard('main')
            
            # ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
            logger.info(f"🔍 DEBUG отправляем новое меню в chat_id={chat_id}")
            
            self.bot.send_message(
                chat_id,  # ← Явно используем chat_id
                text,
                reply_markup=keyboard,
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_resetmenu: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Критическая ошибка меню. Обратитесь к разработчику.",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    # ============================================
    # ОБРАБОТЧИКИ CALLBACK'ОВ МЕНЮ
    # ============================================
    
    def handle_menu_callback(self, callback_query):
        """Обработка всех callback'ов меню"""
        try:
            user_id = callback_query.from_user.id
            data = callback_query.data
            
            # Список функций, доступных всем пользователям
            public_callbacks = [
                'about_v25', 'about_quick', 'about_telegram_app', 
                'help_commands', 'help_user_guide', 'help_admin_guide',
                'mystats_my_links', 'mystats_daily_activity', 'mystats_my_ranking',
                'menu_main', 'menu_help', 'menu_mystats'
            ]
            
            # Проверка прав: админские функции только для админов
            if data not in public_callbacks and not self.security.validate_admin_callback(callback_query):
                self.bot.answer_callback_query(
                    callback_query.id,
                    "❌ Эта функция доступна только администраторам.",
                    show_alert=True
                )
                return
            
            log_user_action(logger, user_id, f"нажал кнопку меню: {data}")
            
            # Обработка навигации по меню
            if data.startswith('menu_'):
                self._handle_menu_navigation(callback_query)
            
            # Обработка функций "в разработке"
            elif data.startswith('dev_'):
                self._handle_dev_function(callback_query)
            
            # Обработка действий лидерборда (ПЛАН 2)
            elif data.startswith('leaderboard_'):
                self._handle_leaderboard_action(callback_query)
            
            # Обработка действий
            elif data.startswith('action_'):
                self._handle_action(callback_query)
            
            # Обработка настроек лимитов
            elif data.startswith('limit_'):
                self._handle_limit_setting(callback_query)
            
            # Обработка аналитики
            elif data.startswith('analytics_'):
                self._handle_analytics_action(callback_query)
            
            # Обработка диагностики
            elif data.startswith('diag_'):
                self._handle_diagnostics_action(callback_query)
            
            # Обработка помощи
            elif data.startswith('help_'):
                self._handle_help_action(callback_query)

            # Обработка статистики пользователя
            elif data.startswith('mystats_'):
                self._handle_mystats_action(callback_query)

            # Обработка информации о боте
            elif data.startswith('about_'):
                self._handle_about_action(callback_query)

            # ПЛАН 3: Обработка ИИ (ЗАГЛУШКИ)
            # elif data.startswith('ai_'):
            #     self._handle_ai_action(callback_query)

            else:
                self.bot.answer_callback_query(
                    callback_query.id,
                    "❓ Неизвестное действие"
                )
            
        except Exception as e:
            logger.error(f"❌ Ошибка handle_menu_callback: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка обработки действия"
            )
    
    def _handle_menu_navigation(self, callback_query):
        """Обработка навигации по меню"""
        data = callback_query.data
        menu_key = data.replace('menu_', '')
        
        # Получаем текст и клавиатуру для меню
        text = self.get_menu_message(menu_key)
        keyboard = self.create_keyboard(menu_key)
        
        # Обновляем сообщение
        self.bot.edit_message_text(
            text,
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        self.bot.answer_callback_query(callback_query.id)
    
    def _handle_dev_function(self, callback_query):
        """Обработка функций в разработке"""
        original_action = callback_query.data.replace('dev_', '')
        
        self.bot.answer_callback_query(
            callback_query.id,
            "🚧 Бро, эта команда пока не работает, давай не сейчас",
            show_alert=True
        )
    
    def _handle_leaderboard_action(self, callback_query):
        """Обработка действий лидерборда"""
        data = callback_query.data
        
        # ПЛАН 2: Реализация лидербордов (ЗАГЛУШКА)
        if data == 'leaderboard_requests':
            # leaderboard_text = self._generate_requests_leaderboard()
            leaderboard_text = "🚧 Лидерборд по просьбам о пресейвах будет доступен в ПЛАНЕ 2"
        elif data == 'leaderboard_karma':
            # leaderboard_text = self._generate_karma_leaderboard()
            leaderboard_text = "🚧 Лидерборд по карме будет доступен в ПЛАНЕ 2"
        elif data == 'leaderboard_ratio':
            # leaderboard_text = self._generate_ratio_leaderboard()
            leaderboard_text = "🚧 Лидерборд по соотношению будет доступен в ПЛАНЕ 2"
        else:
            leaderboard_text = "❓ Неизвестный тип лидерборда"
        
        # Отправляем результат
        self.bot.edit_message_text(
            leaderboard_text,
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=self.create_keyboard('leaderboard'),
            parse_mode='HTML'
        )
        
        self.bot.answer_callback_query(callback_query.id)
    
    def _handle_action(self, callback_query):
        """Обработка основных действий"""
        data = callback_query.data
        
        if data == 'action_last30links':
            self._show_recent_links(callback_query, 30)
        elif data == 'action_last10links':
            self._show_recent_links(callback_query, 10)
        elif data == 'action_enable_bot':
            self._toggle_bot_status(callback_query, True)
        elif data == 'action_disable_bot':
            self._toggle_bot_status(callback_query, False)
        elif data == 'action_clear_links':
            self._clear_links(callback_query)
        elif data == 'action_current_mode':
            self._show_current_mode(callback_query)
        elif data == 'action_reload_modes':
            self._reload_modes(callback_query)
        elif data == 'mystats_my_links':
            self._show_my_links(callback_query)
        elif data == 'mystats_daily_activity':
            self._show_daily_activity(callback_query)
        elif data == 'mystats_my_ranking':
            self._show_my_ranking(callback_query)
        else:
            self.bot.answer_callback_query(
                callback_query.id,
                "❓ Неизвестное действие"
            )
    
    def _show_recent_links(self, callback_query, count: int):
        """Показ последних ссылок"""
        try:
            links = self.db.get_recent_links(count)
            
            if not links:
                text = f"📎 <b>Последние {count} ссылок</b>\n\n🤷 Ссылок пока нет"
            else:
                text_parts = [f"📎 <b>Последние {count} ссылок</b>\n"]
                
                for i, link in enumerate(links, 1):
                    user = self.db.get_user_by_id(link.user_id)
                    username = f"@{user.username}" if user and user.username else f"ID{link.user_id}"
                    date_str = link.created_at.strftime("%d.%m %H:%M")
                    
                    # Обрезаем URL если очень длинный
                    display_url = link.url if len(link.url) <= 50 else link.url[:47] + "..."
                    
                    text_parts.append(f"{i}. {username} ({date_str})")
                    text_parts.append(f"   🔗 {display_url}")
                    
                    if i < len(links):
                        text_parts.append("")
                
                text = "\n".join(text_parts)
            
            # Обновляем сообщение
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=self.create_keyboard('actions'),
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_recent_links: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка получения ссылок"
            )
    
    def _toggle_bot_status(self, callback_query, enabled: bool):
        """Переключение статуса бота"""
        try:
            self.db.set_setting('bot_enabled', enabled, 'bool', 
                               'Статус активности бота', callback_query.from_user.id)
            
            status_text = "активирован" if enabled else "деактивирован"
            emoji = "✅" if enabled else "⏸️"
            
            self.bot.answer_callback_query(
                callback_query.id,
                f"{emoji} Бот {status_text}",
                show_alert=True
            )
            
            # Обновляем главное меню
            text = self.get_menu_message('main')
            keyboard = self.create_keyboard('main')
            
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка _toggle_bot_status: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка изменения статуса"
            )
    
    def _clear_links(self, callback_query):
        """Очистка истории ссылок"""
        try:
            count = self.db.clear_all_links()
            
            self.bot.answer_callback_query(
                callback_query.id,
                f"🗑️ Очищено ссылок: {count}",
                show_alert=True
            )
            
            # Остаемся в меню настроек
            text = self.get_menu_message('settings')
            keyboard = self.create_keyboard('settings')
            
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка _clear_links: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка очистки ссылок"
            )
    
    def _handle_limit_setting(self, callback_query):
        """Обработка настройки лимитов"""
        data = callback_query.data
        mode_map = {
            'limit_conservative': 'CONSERVATIVE',
            'limit_normal': 'NORMAL',
            'limit_burst': 'BURST',
            'limit_admin_burst': 'ADMIN_BURST'
        }
        
        if data in mode_map:
            new_mode = mode_map[data]
            self.db.set_setting('current_limit_mode', new_mode, 'string',
                               'Текущий режим лимитов API', callback_query.from_user.id)
            
            emoji_map = {
                'CONSERVATIVE': '⚫️',
                'NORMAL': '🔵',
                'BURST': '🟢',
                'ADMIN_BURST': '🔴'
            }
            
            self.bot.answer_callback_query(
                callback_query.id,
                f"{emoji_map[new_mode]} Режим изменен на {new_mode}",
                show_alert=True
            )
            
            # Обновляем меню лимитов
            text = self.get_menu_message('limits')
            keyboard = self.create_keyboard('limits')
            
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            self.bot.answer_callback_query(
                callback_query.id,
                "❓ Неизвестный режим"
            )
    
    def _show_current_mode(self, callback_query):
        """Показ текущего режима лимитов"""
        current_mode = self.db.get_setting('current_limit_mode', 'BURST')
        emoji = self._get_current_limit_emoji()
        
        self.bot.answer_callback_query(
            callback_query.id,
            f"📊 Текущий режим: {emoji} {current_mode}",
            show_alert=True
        )
    
    def _reload_modes(self, callback_query):
        """Перезагрузка режимов лимитов"""
        # ПЛАН 1: Простая заглушка перезагрузки
        self.bot.answer_callback_query(
            callback_query.id,
            "🔄 Режимы лимитов перезагружены из конфигурации",
            show_alert=True
        )
    
    def _handle_analytics_action(self, callback_query):
        """Обработка аналитических действий"""
        data = callback_query.data
        
        if data == 'analytics_links_by_user':
            # Определяем thread_id для callback_query
            thread_id = getattr(callback_query.message, 'message_thread_id', None)
            
            # Запрашиваем username у пользователя
            self.bot.answer_callback_query(callback_query.id)
            self.bot.send_message(
                callback_query.message.chat.id,
                "👤 <b>Поиск ссылок по пользователю</b>\n\n"
                "Отправьте username пользователя в формате: @username",
                parse_mode='HTML',
                message_thread_id=thread_id
            )
        # ПЛАН 2: Дополнительная аналитика (ЗАГЛУШКИ)
        # elif data == 'analytics_karma_by_user':
        #     # Аналитика кармы по пользователю
        # elif data == 'analytics_ratio_by_user':
        #     # Аналитика соотношения по пользователю
        else:
            self.bot.answer_callback_query(
                callback_query.id,
                "🚧 Эта аналитика будет доступна в следующих планах"
            )
    
    def _handle_diagnostics_action(self, callback_query):
        """Обработка диагностических действий"""
        data = callback_query.data
        
        if data == 'diag_keepalive':
            self._test_keepalive(callback_query)
        elif data == 'diag_system_check':
            self._system_check(callback_query)
        elif data == 'diag_bot_status':
            self._show_bot_status(callback_query)
        elif data == 'diag_link_integration':
            self._check_link_integration(callback_query)
        else:
            self.bot.answer_callback_query(
                callback_query.id,
                "❓ Неизвестная диагностика"
            )
    
    def _test_keepalive(self, callback_query):
        """Тест keep-alive системы"""
        # ПЛАН 1: Простая проверка
        self.bot.answer_callback_query(
            callback_query.id,
            "💓 Keep-alive работает! Сервер активен.",
            show_alert=True
        )
    
    def _system_check(self, callback_query):
        """Проверка системы"""
        try:
            # Проверяем базовые компоненты
            checks = {
                'database': self._check_database(),
                'settings': self._check_settings(),
                'admin_access': True,  # Если мы здесь, то доступ есть
            }
            
            all_ok = all(checks.values())
            
            text_parts = [
                "🔍 <b>Проверка системы</b>\n",
                f"🗃️ База данных: {'✅' if checks['database'] else '❌'}",
                f"⚙️ Настройки: {'✅' if checks['settings'] else '❌'}",
                f"👑 Админ доступ: {'✅' if checks['admin_access'] else '❌'}",
                "",
                f"📊 <b>Общий статус:</b> {'✅ Все системы работают' if all_ok else '❌ Обнаружены проблемы'}"
            ]
            
            self.bot.edit_message_text(
                "\n".join(text_parts),
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=self.create_keyboard('diagnostics'),
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _system_check: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка проверки системы"
            )
    
    def _check_database(self) -> bool:
        """Проверка БД"""
        try:
            # Простая проверка - получаем количество пользователей
            stats = self.db.get_basic_stats()
            return 'total_users' in stats
        except:
            return False
    
    def _check_settings(self) -> bool:
        """Проверка настроек"""
        try:
            # Проверяем что можем читать настройки
            bot_enabled = self.db.get_setting('bot_enabled', True)
            return isinstance(bot_enabled, bool)
        except:
            return False
    
    def _show_bot_status(self, callback_query):
        """Показ статуса бота"""
        try:
            stats = self.db.get_basic_stats()
            settings = self.db.get_all_settings()
            
            text_parts = [
                "📊 <b>Статус и статистика бота</b>\n",
                "👥 <b>Пользователи:</b>",
                f"• Всего: {stats.get('total_users', 0)}",
                f"• Админов: {stats.get('total_admins', 0)}",
                f"• Активных за неделю: {stats.get('active_users_week', 0)}",
                "",
                "📎 <b>Ссылки:</b>",
                f"• Всего: {stats.get('total_links', 0)}",
                f"• Сегодня: {stats.get('links_today', 0)}",
                "",
                "⚙️ <b>Настройки:</b>",
                f"• Бот: {'✅ Активен' if settings.get('bot_enabled', True) else '⏸️ Отключен'}",
                f"• Режим лимитов: {self._get_current_limit_emoji()} {settings.get('current_limit_mode', 'BURST')}",
                "",
                # ПЛАН 2: Статистика кармы (ЗАГЛУШКА)
                # "🏆 <b>Карма:</b>",
                # f"• Система кармы: {'✅ Включена' if settings.get('karma_enabled', False) else '⏸️ Отключена'}",
                # "",
                # ПЛАН 3: Статистика ИИ (ЗАГЛУШКА)
                # "🤖 <b>ИИ:</b>",
                # f"• ИИ модуль: {'✅ Включен' if settings.get('ai_enabled', False) else '⏸️ Отключен'}",
                # "",
                f"🕐 <b>Время проверки:</b> {datetime.now().strftime('%H:%M:%S')}"
            ]
            
            self.bot.edit_message_text(
                "\n".join(text_parts),
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=self.create_keyboard('diagnostics'),
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_bot_status: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка получения статуса"
            )
    
    def _handle_help_action(self, callback_query):
        """Обработка действий помощи"""
        data = callback_query.data
        
        if data == 'help_commands':
            self._show_commands_list(callback_query)
        elif data == 'help_user_guide':
            self._show_user_guide(callback_query)
        elif data == 'help_admin_guide':
            self._show_admin_guide(callback_query)
        else:
            self.bot.answer_callback_query(
                callback_query.id,
                "❓ Неизвестный раздел помощи"
            )

    def _handle_about_action(self, callback_query):
        """Обработка действий информации о боте"""
        data = callback_query.data
        
        if data == 'about_v25':
            self._show_about_v25(callback_query)
        elif data == 'about_quick':
            self._show_about_quick(callback_query)
        elif data == 'about_telegram_app':
            self._open_telegram_web_app(callback_query)
        else:
            self.bot.answer_callback_query(
                callback_query.id,
                "❓ Неизвестный раздел информации"
            )

    def _handle_mystats_action(self, callback_query):
        """Обработка действий статистики пользователя"""
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if data == 'mystats_my_links':
            self._show_user_links(callback_query, user_id)
        elif data == 'mystats_daily_activity':
            self._show_user_activity(callback_query, user_id)
        elif data == 'mystats_my_ranking':
            self._show_user_rating(callback_query, user_id)
        else:
            self.bot.answer_callback_query(
                callback_query.id,
                "❓ Неизвестная статистика"
            )

    def _show_user_links(self, callback_query, user_id):
        """Показ ссылок пользователя"""
        try:
            links = self.db.get_user_links(user_id, limit=10)
            
            if not links:
                text = "🔗 <b>Мои ссылки</b>\n\nВы еще не отправляли ссылок."
            else:
                text = f"🔗 <b>Мои ссылки</b>\n\nПоследние {len(links)} ссылок:\n\n"
                for i, link in enumerate(links, 1):
                    # link это объект SQLAlchemy модели Link
                    date_str = link.created_at.strftime('%d.%m.%Y %H:%M')
                    url_display = link.url if len(link.url) <= 50 else link.url[:47] + "..."
                    text += f"{i}. {url_display}\n"
                    text += f"   📅 {date_str}\n\n"
            
            keyboard = self.create_keyboard('mystats')
            
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_user_links: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка загрузки ссылок"
            )

    def _show_user_activity(self, callback_query, user_id):
        """Показ активности пользователя по дням"""
        try:
            # Используем существующий метод get_user_stats для получения базовой статистики
            stats = self.db.get_user_stats(user_id)
            
            text = "📅 <b>Активность по дням</b>\n\n"
            if not stats:
                text += "Данных об активности пока нет."
            else:
                text += f"📊 Всего ссылок: {stats.get('total_links', 0)}\n"
                text += f"📅 Ссылок за месяц: {stats.get('links_this_month', 0)}\n"
                text += f"👤 Участник с: {stats.get('member_since', 'Неизвестно')}\n"
                text += f"🕒 Последняя активность: {stats.get('last_seen', 'Неизвестно')}\n\n"
                text += "⚠️ Детальная активность по дням будет доступна в следующих обновлениях."
            
            keyboard = self.create_keyboard('mystats')
            
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_user_activity: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка загрузки активности"
            )

    def _show_user_rating(self, callback_query, user_id):
        """Показ рейтинга пользователя"""
        try:
            # Используем существующий метод get_user_stats
            stats = self.db.get_user_stats(user_id)
            
            text = "🏆 <b>Мой рейтинг</b>\n\n"
            if not stats:
                text += "Данных о рейтинге пока нет."
            else:
                text += f"👤 @{stats.get('username', 'неизвестно')}\n"
                text += f"📊 Всего ссылок: {stats.get('total_links', 0)}\n"
                text += f"📅 Ссылок за месяц: {stats.get('links_this_month', 0)}\n"
                text += f"👑 Статус: {'Администратор' if stats.get('is_admin', False) else 'Пользователь'}\n"
                text += f"🕒 Участник с: {stats.get('member_since', 'Неизвестно')}\n\n"
                text += "⚠️ Система рангов и подробный рейтинг будут доступны в следующих обновлениях (План 2)."
            
            keyboard = self.create_keyboard('mystats')
            
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_user_rating: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка загрузки рейтинга"
            )

    def _show_commands_list(self, callback_query):
        """Показ списка команд"""
        text_parts = [
            "📋 <b>Список всех команд</b>\n",
            "🎛️ <b>Навигация:</b>",
            "/menu - Главное меню",
            "/resetmenu - Сброс меню",
            "/help - Список команд",
            "",
            "📊 <b>Статистика:</b>",
            "/mystat - Моя статистика",
            "/last10links - Последние 10 ссылок",
            "/last30links - Последние 30 ссылок",
            "",
            "⚙️ <b>Управление:</b>",
            "/enablebot - Активировать бота",
            "/disablebot - Деактивировать бота",
            "/setmode_conservative - Режим Консерва",
            "/setmode_normal - Режим Покатит",
            "/setmode_burst - Режим Живенько",
            "/setmode_adminburst - Режим пИчОт",
            "/currentmode - Текущий режим",
            "",
            # ПЛАН 2: Команды кармы (ЗАГЛУШКИ)
            # "🏆 <b>Карма (ПЛАН 2):</b>",
            # "/karma @username +/-число - Изменить карму",
            # "/karmastat - Рейтинг по карме",
            # "/ratiostat @username 15:12 - Изменить соотношение",
            # "",
            # ПЛАН 3: Команды ИИ и форм (ЗАГЛУШКИ)
            # "🤖 <b>ИИ и формы (ПЛАН 3):</b>",
            # "/askpresave - Попросить о пресейве",
            # "/claimpresave - Заявить о пресейве",
            # "/checkapprovals - Проверить заявки",
            # "",
            # ПЛАН 4: Команды backup (ЗАГЛУШКИ)
            # "💾 <b>Backup (ПЛАН 4):</b>",
            # "/downloadsql - Скачать backup БД",
            # "/backupstatus - Статус backup",
            # "/backuphelp - Помощь по backup",
            # "",
            "💡 <b>Примечание:</b> Все команды пока доступны только администраторам. Ну, иногда и вам (скоро) ✌🏻😁 А ещё грядёт масштабное пополнение функционала! 🌟 Ждите!"
        ]
        
        self.bot.edit_message_text(
            "\n".join(text_parts),
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=self.create_keyboard('help'),
            parse_mode='HTML'
        )
        
        self.bot.answer_callback_query(callback_query.id)
    
    def _show_user_guide(self, callback_query):
        """Показ руководства пользователя"""
        text = """📖 <b>Краткое руководство пользователя</b>

🎵 <b>Как пользоваться ботом:</b>

1️⃣ <b>Просьба о пресейве:</b>
   • Опубликуйте ссылку в разрешенном топике
   • Бот автоматически отправит напоминание
   • Другие участники увидят призыв к взаимности

2️⃣ <b>Статистика:</b>
   • Используйте /mystat для просмотра статистики
   • /last10links покажет последние ссылки
   • Следите за своей активностью

3️⃣ <b>Админские функции:</b>
   • /menu - доступ к панели управления
   • Настройка режимов работы бота
   • Управление статистикой и данными

🔮 <b>Планы развития:</b>
ПЛАН 2: Система кармы и званий
ПЛАН 3: ИИ помощник и интерактивные формы
ПЛАН 4: Автоматический backup системы

💡 Подробности: docs/user_guide.md"""
        
        self.bot.edit_message_text(
            text,
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=self.create_keyboard('help'),
            parse_mode='HTML'
        )
        
        self.bot.answer_callback_query(callback_query.id)
    
    def _show_admin_guide(self, callback_query):
        """Показ руководства админа"""
        text = """🔧 <b>Руководство администратора</b>

👑 <b>Админские возможности:</b>

🎛️ <b>Меню управления:</b>
   • /menu - главная панель управления
   • Навигация через кнопки "Назад" и "Главное меню"
   • /resetmenu при любых проблемах

⚡ <b>Режимы лимитов:</b>
   • Консерва: 60/час, кулдаун 60с
   • Normal: 180/час, кулдаун 20с  
   • Burst: 600/час, кулдаун 6с (по умолчанию)
   • Admin Burst: 1200/час, кулдаун 3с

📊 <b>Мониторинг:</b>
   • Диагностика системы
   • Статистика пользователей
   • Keep-alive проверки

🗑️ <b>Управление данными:</b>
   • Очистка истории ссылок
   • Включение/отключение бота
   • Перезагрузка настроек

🚀 <b>В разработке:</b>
ПЛАН 2: Управление кармой пользователей
ПЛАН 3: Модерация форм и ИИ настройки
ПЛАН 4: Backup и восстановление БД

💡 Подробности: docs/admin_guide.md"""
        
        self.bot.edit_message_text(
            text,
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=self.create_keyboard('help'),
            parse_mode='HTML'
        )
        
        self.bot.answer_callback_query(callback_query.id)

    def _show_about_v25(self, callback_query):
        """Показ меню информации о боте v25.1"""
        try:
            logger.info(f"🔍 DEBUG _show_about_v25: попытка создать WebApp для user={callback_query.from_user.id}")
            
            # Получаем URL из переменной окружения с валидацией
            webapp_url = os.getenv('WEBAPP_URL')
            if not webapp_url:
                logger.warning("⚠️ WEBAPP_URL не найден в переменных окружения")
                webapp_url = 'https://misterdms.github.io/misterdms_presave_bot/about25/'
                
            # Валидация URL
            if not webapp_url.startswith(('http://', 'https://')):
                logger.error(f"❌ Некорректный WEBAPP_URL: {webapp_url}")
                webapp_url = 'https://misterdms.github.io/misterdms_presave_bot/about25/'
            
            # Создаем клавиатуру через единый метод
            additional_buttons = [
                ("📋 Краткая справка", "about_quick"),
                ("🔗 Telegram App", "about_telegram_app")
            ]
            markup = create_webapp_keyboard(webapp_url, additional_buttons)
            
            text = f"""🔥 <b>Do Presave Reminder Bot v25.1</b>

    🎵 <b>Твой личный помощник для музыкального хайпа!</b>

    📖 <b>Что внутри интерактивного гайда:</b>

    ✨ <b>Уже работает:</b>
       • Умное меню с кнопками
       • Автоматические напоминания
       • Базовая статистика
       • Настройки для админов

    🔮 <b>Скоро будет:</b>
       • Система кармы и званий
       • Интерактивные формы
       • ИИ-помощник
       • Система backup

    🌐 <b>Нажми "Интерактивный гайд"</b> для просмотра красивой HTML-страницы с анимированными градиентами!

    💡 <i>Адаптивный дизайн оптимизирован для всех устройств</i>"""

            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_about_v25: {e}")
            
            # Fallback без WebApp
            fallback_text = self._create_fallback_about_message()
            fallback_markup = self.create_navigation_keyboard("menu_main", "menu_main")
            
            try:
                self.bot.edit_message_text(
                    fallback_text,
                    callback_query.message.chat.id,
                    callback_query.message.message_id,
                    reply_markup=fallback_markup,
                    parse_mode='HTML'
                )
                self.bot.answer_callback_query(callback_query.id, "⚠️ Загружена упрощенная версия")
            except:
                self.bot.answer_callback_query(
                    callback_query.id,
                    "❌ Ошибка загрузки информации о боте",
                    show_alert=True
                )

    def _show_about_quick(self, callback_query):
        """Показ краткой справки о боте"""
        try:
            text = """📋 <b>Краткая справка v25.1</b>

    🎯 <b>Главная цель:</b> 
    Автоматизация взаимных пресейвов в музыкальном сообществе

    ⚡ <b>Работает сейчас:</b>
    - <code>/menu</code> - главное меню с кнопками
    - Автонапоминания при публикации ссылок
    - <code>/mystat</code> - личная статистика
    - <code>/last10links</code>, <code>/last30links</code> - свежие просьбы

    🔮 <b>В разработке (Планы 2-4):</b>
    - Карма и звания за взаимопомощь
    - Интерактивные формы подачи заявок
    - ИИ-помощник для ответов на вопросы
    - Автоматический backup данных

    💬 <b>Где работает:</b>
    - ЛС с ботом (админы - все команды)
    - Супергруппа, топики #2 и #3

    👑 <b>Разработчик:</b> @Mister_DMS

    🔥 <b>Новое в v25.1:</b>
    - Анимированные градиенты
    - Улучшенная адаптивность
    - Web App интеграция"""

            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(
                telebot.types.InlineKeyboardButton("🌐 Полный гайд", callback_data="about_v25"),
                telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="about_v25")
            )

            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_about_quick: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка отображения краткой справки"
            )

    def _open_telegram_web_app(self, callback_query):
        """Открытие Web App через ссылку в Telegram"""
        try:
            # Получаем short_name из переменной окружения с валидацией
            webapp_short_name = os.getenv('WEBAPP_SHORT_NAME')
            if not webapp_short_name:
                logger.warning("⚠️ WEBAPP_SHORT_NAME не найден в переменных окружения")
                self.bot.answer_callback_query(
                    callback_query.id,
                    "❌ Telegram Web App не настроен. Обратитесь к администратору.",
                    show_alert=True
                )
                return

            try:
                bot_username = self.bot.get_me().username
                if not bot_username:
                    raise Exception("Не удалось получить username бота")
            except Exception as e:
                logger.error(f"❌ Ошибка получения username бота: {e}")
                self.bot.answer_callback_query(
                    callback_query.id,
                    "❌ Ошибка настройки Telegram App",
                    show_alert=True
                )
                return
            
            # Формируем ссылку на Telegram Web App
            telegram_app_url = f"https://t.me/{bot_username}/{webapp_short_name}"
            
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(
                telebot.types.InlineKeyboardButton("🚀 Открыть в Telegram", url=telegram_app_url)
            )
            markup.add(
                telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="about_v25")
            )
            
            text = f"""📱 <b>Telegram Web App</b>

    🚀 <b>Откройте гайд как нативное приложение!</b>

    Ссылка: <code>{telegram_app_url}</code>

    💡 <b>Преимущества Telegram App:</b>
    - Полноэкранный режим
    - Нативная интеграция
    - Быстрая загрузка
    - Тактильная обратная связь

    ⚡ Нажмите кнопку ниже для открытия!"""

            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _open_telegram_web_app: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка получения ссылки на Web App"
            )

    def _show_my_links(self, callback_query):
        """Показ ссылок текущего пользователя"""
        try:
            user_id = callback_query.from_user.id
            
            # Получаем ссылки пользователя (последние 10)
            links = self.db.get_links_by_user_id(user_id, limit=10)
            
            if not links:
                text = "📎 <b>Мои ссылки</b>\n\n🤷 У вас пока нет опубликованных ссылок"
            else:
                text_parts = [f"📎 <b>Мои ссылки</b> (последние {len(links)})\n"]
                
                for i, link in enumerate(links, 1):
                    date_str = link.created_at.strftime("%d.%m %H:%M")
                    display_url = link.url if len(link.url) <= 50 else link.url[:47] + "..."
                    
                    text_parts.append(f"{i}. {date_str}")
                    text_parts.append(f"   🔗 {display_url}")
                    
                    if i < len(links):
                        text_parts.append("")
                
                text = "\n".join(text_parts)
            
            # Обновляем сообщение
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=self.create_keyboard('mystats'),
                parse_mode='HTML'
            )
            
            self.bot.answer_callback_query(callback_query.id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_my_links: {e}")
            self.bot.answer_callback_query(
                callback_query.id,
                "❌ Ошибка получения ссылок"
            )

    def _show_daily_activity(self, callback_query):
        """ЗАГЛУШКА: Показ активности по дням"""
        self.bot.answer_callback_query(
            callback_query.id,
            "📅 Статистика активности по дням будет доступна в следующих версиях",
            show_alert=True
        )

    def _show_my_ranking(self, callback_query):
        """ЗАГЛУШКА: Показ рейтинга пользователя"""
        self.bot.answer_callback_query(
            callback_query.id,
            "🏆 Персональный рейтинг будет доступен в ПЛАНЕ 2",
            show_alert=True
        )

if __name__ == "__main__":
    """Тестирование MenuHandler"""
    from database.manager import DatabaseManager
    from utils.security import SecurityManager
    
    print("🧪 Тестирование MenuHandler...")
    
    # Создание тестовых компонентов
    db = DatabaseManager("sqlite:///:memory:")
    db.create_tables()
    
    security = SecurityManager([12345], [2, 3])
    
    # Тестирование меню
    menu_handler = MenuHandler(None, db, security)
    
    # Тестирование структуры меню
    print("\n📋 Тестирование структуры меню:")
    for menu_key, menu_data in menu_handler.menu_structure.items():
        print(f"• {menu_key}: {menu_data['title']} ({len(menu_data['buttons'])} кнопок)")
    
    # Тестирование создания клавиатуры
    print("\n⌨️ Тестирование клавиатуры:")
    keyboard = menu_handler.create_keyboard('main')
    print(f"Главное меню: {len(keyboard.keyboard)} рядов кнопок")
    
    # Тестирование сообщений меню
    print("\n💬 Тестирование сообщений меню:")
    main_message = menu_handler.get_menu_message('main')
    print(f"Главное меню: {len(main_message)} символов")
    
    print("\n✅ Тестирование MenuHandler завершено!")