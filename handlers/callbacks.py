"""
Обработчик callback'ов (кнопок) Do Presave Reminder Bot v25+
Обработка всех нажатий кнопок с интеграцией в MenuHandler

ПЛАН 1: Базовые callback'ы (АКТИВНЫЕ)
ПЛАН 2: Callback'ы кармы (ЗАГЛУШКИ)
ПЛАН 3: Callback'ы ИИ и форм (ЗАГЛУШКИ)
ПЛАН 4: Callback'ы backup (ЗАГЛУШКИ)
"""

from typing import Dict, Callable, Any
import telebot
from telebot.types import CallbackQuery

from database.manager import DatabaseManager
from utils.security import SecurityManager
from utils.logger import get_logger, log_user_action
from handlers.menu import MenuHandler

logger = get_logger(__name__)

class CallbackHandler:
    """Обработчик всех callback'ов (нажатий кнопок)"""
    
    def __init__(self, bot: telebot.TeleBot, db_manager: DatabaseManager, security_manager: SecurityManager):
        """Инициализация обработчика callback'ов"""
        self.bot = bot
        self.db = db_manager
        self.security = security_manager
        
        # Создаем интеграцию с MenuHandler
        self.menu_handler = MenuHandler(bot, db_manager, security_manager)
        
        # Регистр обработчиков callback'ов
        self.callback_handlers: Dict[str, Callable] = {}
        self._register_callback_handlers()
        
        logger.info("CallbackHandler инициализирован")
    
    def _register_callback_handlers(self):
        """Регистрация всех обработчиков callback'ов"""
        
        # ПЛАН 1: Базовые callback'ы (АКТИВНЫЕ)
        
        # Навигация по меню - делегируем в MenuHandler
        menu_callbacks = [
            'menu_main', 'menu_mystats', 'menu_leaderboard', 'menu_actions',
            'menu_settings', 'menu_limits', 'menu_analytics', 'menu_diagnostics', 'menu_help'
        ]
        
        for callback in menu_callbacks:
            self.callback_handlers[callback] = self.menu_handler.handle_menu_callback
        
        # Действия лидерборда - делегируем в MenuHandler
        leaderboard_callbacks = [
            'leaderboard_requests', 'leaderboard_karma', 'leaderboard_ratio'
        ]
        
        for callback in leaderboard_callbacks:
            self.callback_handlers[callback] = self.menu_handler.handle_menu_callback
        
        # Основные действия - делегируем в MenuHandler
        action_callbacks = [
            'action_last30links', 'action_last10links', 'action_enable_bot',
            'action_disable_bot', 'action_clear_links', 'action_current_mode',
            'action_reload_modes'
        ]
        
        for callback in action_callbacks:
            self.callback_handlers[callback] = self.menu_handler.handle_menu_callback
        
        # Настройки лимитов - делегируем в MenuHandler
        limit_callbacks = [
            'limit_conservative', 'limit_normal', 'limit_burst', 'limit_admin_burst'
        ]
        
        for callback in limit_callbacks:
            self.callback_handlers[callback] = self.menu_handler.handle_menu_callback
        
        # Аналитика - делегируем в MenuHandler
        analytics_callbacks = [
            'analytics_links_by_user', 'analytics_karma_by_user', 'analytics_ratio_by_user'
        ]
        
        for callback in analytics_callbacks:
            self.callback_handlers[callback] = self.menu_handler.handle_menu_callback
        
        # Диагностика - делегируем в MenuHandler
        diagnostics_callbacks = [
            'diag_keepalive', 'diag_system_check', 'diag_bot_status'
        ]
        
        for callback in diagnostics_callbacks:
            self.callback_handlers[callback] = self.menu_handler.handle_menu_callback
        
        # Помощь - делегируем в MenuHandler
        help_callbacks = [
            'help_commands', 'help_user_guide', 'help_admin_guide'
        ]
        
        for callback in help_callbacks:
            self.callback_handlers[callback] = self.menu_handler.handle_menu_callback
            
        # Статистика пользователя - делегируем в MenuHandler
        mystats_callbacks = [
            'mystats_my_links', 'mystats_daily_activity', 'mystats_my_ranking'
        ]

        for callback in mystats_callbacks:
            self.callback_handlers[callback] = self.menu_handler.handle_menu_callback
        
        # Callback'ы "в разработке"
        self.callback_handlers['dev_*'] = self._handle_dev_callback
        
        # ПЛАН 2: Callback'ы кармы (ЗАГЛУШКИ)
        # karma_callbacks = [
        #     'karma_add_1', 'karma_add_5', 'karma_subtract_1', 'karma_subtract_5',
        #     'karma_confirm', 'karma_cancel', 'karma_history'
        # ]
        # 
        # for callback in karma_callbacks:
        #     self.callback_handlers[callback] = self._handle_karma_callback
        
        # ПЛАН 3: Callback'ы ИИ и форм (ЗАГЛУШКИ)
        # ai_callbacks = [
        #     'ai_enable', 'ai_disable', 'ai_settings', 'ai_model_select',
        #     'form_start_presave', 'form_start_claim', 'form_cancel', 'form_submit',
        #     'approval_approve', 'approval_reject', 'approval_next'
        # ]
        # 
        # for callback in ai_callbacks:
        #     self.callback_handlers[callback] = self._handle_ai_form_callback
        
        # ПЛАН 4: Callback'ы backup (ЗАГЛУШКИ)
        # backup_callbacks = [
        #     'backup_create', 'backup_download', 'backup_restore', 'backup_schedule',
        #     'backup_confirm_restore', 'backup_cancel_restore'
        # ]
        # 
        # for callback in backup_callbacks:
        #     self.callback_handlers[callback] = self._handle_backup_callback
        
        logger.info(f"Зарегистрировано {len(self.callback_handlers)} обработчиков callback'ов")
    
    def register_handlers(self):
        """Регистрация callback handler в боте"""
        
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_all_callbacks(callback_query: CallbackQuery):
            """Универсальный обработчик всех callback'ов"""
            try:
                self._process_callback(callback_query)
            except Exception as e:
                logger.error(f"❌ Критическая ошибка callback handler: {e}")
                try:
                    self.bot.answer_callback_query(
                        callback_query.id,
                        "❌ Внутренняя ошибка. Попробуйте /resetmenu",
                        show_alert=True
                    )
                except:
                    pass
        
        logger.info("Callback handler зарегистрирован в боте")
    
    def _process_callback(self, callback_query: CallbackQuery):
        """Обработка callback'а"""
        try:
            user_id = callback_query.from_user.id
            data = callback_query.data
            
            log_user_action(logger, user_id, f"нажал кнопку: {data}")
            
            # Проверка базовой безопасности
            if not self.security.validate_admin_callback(callback_query):
                self.bot.answer_callback_query(
                    callback_query.id,
                    "❌ Доступ запрещен! Только для администраторов.",
                    show_alert=True
                )
                return
            
            # Проверка на callback'ы "в разработке"
            if data.startswith('dev_'):
                self._handle_dev_callback(callback_query)
                return
            
            # Поиск подходящего обработчика
            handler = self._find_callback_handler(data)
            
            if handler:
                handler(callback_query)
            else:
                # Неизвестный callback - показываем уведомление
                self._handle_unknown_callback(callback_query)
                
        except Exception as e:
            logger.error(f"❌ Ошибка _process_callback: {e}")
            try:
                self.bot.answer_callback_query(
                    callback_query.id,
                    "❌ Ошибка обработки действия"
                )
            except:
                pass
    
    def _find_callback_handler(self, data: str) -> Callable:
        """Поиск обработчика для callback'а"""
        
        # Прямое совпадение
        if data in self.callback_handlers:
            return self.callback_handlers[data]
        
        # Поиск по префиксам
        callback_prefixes = {
            'menu_': self.menu_handler.handle_menu_callback,
            'leaderboard_': self.menu_handler.handle_menu_callback,
            'action_': self.menu_handler.handle_menu_callback,
            'limit_': self.menu_handler.handle_menu_callback,
            'analytics_': self.menu_handler.handle_menu_callback,
            'diag_': self.menu_handler.handle_menu_callback,
            'help_': self.menu_handler.handle_menu_callback,
            'mystats_': self.menu_handler.handle_menu_callback,
            'dev_': self._handle_dev_callback,
            
            # ПЛАН 2: Префиксы кармы (ЗАГЛУШКИ)
            # 'karma_': self._handle_karma_callback,
            # 'rank_': self._handle_rank_callback,
            
            # ПЛАН 3: Префиксы ИИ и форм (ЗАГЛУШКИ)
            # 'ai_': self._handle_ai_callback,
            # 'form_': self._handle_form_callback,
            # 'approval_': self._handle_approval_callback,
            
            # ПЛАН 4: Префиксы backup (ЗАГЛУШКИ)
            # 'backup_': self._handle_backup_callback,
            # 'restore_': self._handle_restore_callback,
        }
        
        for prefix, handler in callback_prefixes.items():
            if data.startswith(prefix):
                return handler
        
        return None
    
    def _handle_dev_callback(self, callback_query: CallbackQuery):
        """Обработка callback'ов "в разработке" """
        original_action = callback_query.data.replace('dev_', '')
        
        # Определяем к какому плану относится функция
        plan_info = self._get_plan_info(original_action)
        
        message = f"🚧 Бро, эта команда пока не работает, давай не сейчас\n\n" \
                 f"📋 Функция будет доступна в {plan_info['plan']}\n" \
                 f"🎯 Описание: {plan_info['description']}"
        
        self.bot.answer_callback_query(
            callback_query.id,
            message,
            show_alert=True
        )
    
    def _get_plan_info(self, action: str) -> Dict[str, str]:
        """Получение информации о плане для действия"""
        
        plan2_actions = {
            'leaderboard_requests': 'Лидерборд по просьбам о пресейвах',
            'leaderboard_karma': 'Лидерборд по карме',
            'leaderboard_ratio': 'Лидерборд по соотношению',
            'analytics_karma_by_user': 'Аналитика кармы по пользователю',
            'analytics_ratio_by_user': 'Аналитика соотношения по пользователю'
        }
        
        plan3_actions = {
            'action_ask_presave': 'Интерактивная форма пресейва',
            'action_claim_presave': 'Форма заявки о пресейве',
            'action_check_approvals': 'Модерация заявок',
            'action_edit_reminder': 'Редактирование напоминаний',
            'action_clear_approvals': 'Очистка заявок',
            'action_clear_asks': 'Очистка просьб',
            'menu_ai': 'ИИ и автоматизация',
            'ai_settings': 'Настройки ИИ',
            'ai_gratitude_dict': 'Словарь благодарностей',
            'ai_auto_karma_log': 'История автоначислений',
            'ai_stats': 'Статистика ИИ'
        }
        
        plan4_actions = {
            'diag_backup_status': 'Статус backup системы',
            'action_backup_download': 'Скачивание backup',
            'action_backup_help': 'Помощь по backup'
        }
        
        if action in plan2_actions:
            return {
                'plan': 'ПЛАНЕ 2 (Система кармы)',
                'description': plan2_actions[action]
            }
        elif action in plan3_actions:
            return {
                'plan': 'ПЛАНЕ 3 (ИИ и формы)',
                'description': plan3_actions[action]
            }
        elif action in plan4_actions:
            return {
                'plan': 'ПЛАНЕ 4 (Backup система)',
                'description': plan4_actions[action]
            }
        else:
            return {
                'plan': 'одном из следующих планов',
                'description': 'Новая функция'
            }
    
    def _handle_unknown_callback(self, callback_query: CallbackQuery):
        """Обработка неизвестного callback'а"""
        logger.warning(f"Неизвестный callback: {callback_query.data} от пользователя {callback_query.from_user.id}")
        
        self.bot.answer_callback_query(
            callback_query.id,
            "❓ Неизвестное действие. Попробуйте /resetmenu",
            show_alert=True
        )
    
    # ============================================
    # ПЛАН 2: ОБРАБОТЧИКИ КАРМЫ (ЗАГЛУШКИ)
    # ============================================
    
    # def _handle_karma_callback(self, callback_query: CallbackQuery):
    #     """Обработка callback'ов системы кармы"""
    #     data = callback_query.data
    #     
    #     if data == 'karma_add_1':
    #         self._quick_karma_change(callback_query, 1)
    #     elif data == 'karma_add_5':
    #         self._quick_karma_change(callback_query, 5)
    #     elif data == 'karma_subtract_1':
    #         self._quick_karma_change(callback_query, -1)
    #     elif data == 'karma_subtract_5':
    #         self._quick_karma_change(callback_query, -5)
    #     elif data == 'karma_confirm':
    #         self._confirm_karma_operation(callback_query)
    #     elif data == 'karma_cancel':
    #         self._cancel_karma_operation(callback_query)
    #     elif data == 'karma_history':
    #         self._show_karma_history(callback_query)
    #     else:
    #         self._handle_unknown_callback(callback_query)
    
    # def _quick_karma_change(self, callback_query: CallbackQuery, amount: int):
    #     """Быстрое изменение кармы через кнопки"""
    #     try:
    #         # Получаем данные о пользователе из context или state
    #         # Обновляем карму
    #         # Показываем результат
    #         pass
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _quick_karma_change: {e}")
    #         self.bot.answer_callback_query(
    #             callback_query.id,
    #             "❌ Ошибка изменения кармы"
    #         )
    
    # ============================================
    # ПЛАН 3: ОБРАБОТЧИКИ ИИ И ФОРМ (ЗАГЛУШКИ)
    # ============================================
    
    # def _handle_ai_form_callback(self, callback_query: CallbackQuery):
    #     """Обработка callback'ов ИИ и форм"""
    #     data = callback_query.data
    #     
    #     if data.startswith('ai_'):
    #         self._handle_ai_callback(callback_query)
    #     elif data.startswith('form_'):
    #         self._handle_form_callback(callback_query)
    #     elif data.startswith('approval_'):
    #         self._handle_approval_callback(callback_query)
    #     else:
    #         self._handle_unknown_callback(callback_query)
    
    # def _handle_ai_callback(self, callback_query: CallbackQuery):
    #     """Обработка callback'ов ИИ"""
    #     data = callback_query.data
    #     
    #     if data == 'ai_enable':
    #         self._toggle_ai(callback_query, True)
    #     elif data == 'ai_disable':
    #         self._toggle_ai(callback_query, False)
    #     elif data == 'ai_settings':
    #         self._show_ai_settings(callback_query)
    #     elif data.startswith('ai_model_'):
    #         model = data.replace('ai_model_', '')
    #         self._change_ai_model(callback_query, model)
    #     else:
    #         self._handle_unknown_callback(callback_query)
    
    # def _handle_form_callback(self, callback_query: CallbackQuery):
    #     """Обработка callback'ов форм"""
    #     data = callback_query.data
    #     
    #     if data == 'form_start_presave':
    #         self._start_presave_form(callback_query)
    #     elif data == 'form_start_claim':
    #         self._start_claim_form(callback_query)
    #     elif data == 'form_cancel':
    #         self._cancel_form(callback_query)
    #     elif data == 'form_submit':
    #         self._submit_form(callback_query)
    #     else:
    #         self._handle_unknown_callback(callback_query)
    
    # def _handle_approval_callback(self, callback_query: CallbackQuery):
    #     """Обработка callback'ов модерации"""
    #     data = callback_query.data
    #     
    #     if data.startswith('approval_approve_'):
    #         claim_id = int(data.replace('approval_approve_', ''))
    #         self._approve_claim(callback_query, claim_id)
    #     elif data.startswith('approval_reject_'):
    #         claim_id = int(data.replace('approval_reject_', ''))
    #         self._reject_claim(callback_query, claim_id)
    #     elif data == 'approval_next':
    #         self._show_next_approval(callback_query)
    #     else:
    #         self._handle_unknown_callback(callback_query)
    
    # ============================================
    # ПЛАН 4: ОБРАБОТЧИКИ BACKUP (ЗАГЛУШКИ)
    # ============================================
    
    # def _handle_backup_callback(self, callback_query: CallbackQuery):
    #     """Обработка callback'ов backup системы"""
    #     data = callback_query.data
    #     
    #     if data == 'backup_create':
    #         self._create_backup(callback_query)
    #     elif data == 'backup_download':
    #         self._download_backup(callback_query)
    #     elif data == 'backup_restore':
    #         self._show_restore_options(callback_query)
    #     elif data == 'backup_schedule':
    #         self._show_backup_schedule(callback_query)
    #     elif data == 'backup_confirm_restore':
    #         self._confirm_restore(callback_query)
    #     elif data == 'backup_cancel_restore':
    #         self._cancel_restore(callback_query)
    #     else:
    #         self._handle_unknown_callback(callback_query)
    
    # def _create_backup(self, callback_query: CallbackQuery):
    #     """Создание backup через callback"""
    #     try:
    #         # Проверяем что это ЛС
    #         if callback_query.message.chat.type != 'private':
    #             self.bot.answer_callback_query(
    #                 callback_query.id,
    #                 "❌ Backup можно создавать только в личных сообщениях!",
    #                 show_alert=True
    #             )
    #             return
    #         
    #         self.bot.answer_callback_query(callback_query.id)
    #         
    #         # Показываем процесс создания
    #         self.bot.edit_message_text(
    #             "🔄 <b>Создание backup...</b>\n\nПожалуйста, подождите...",
    #             callback_query.message.chat.id,
    #             callback_query.message.message_id,
    #             parse_mode='HTML'
    #         )
    #         
    #         # Создаем backup (заглушка)
    #         # В реальности здесь будет вызов BackupRestoreManager
    #         
    #         # Показываем результат
    #         self.bot.edit_message_text(
    #             "✅ <b>Backup создан успешно!</b>\n\nФайл будет отправлен отдельным сообщением.",
    #             callback_query.message.chat.id,
    #             callback_query.message.message_id,
    #             parse_mode='HTML'
    #         )
    #         
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _create_backup: {e}")
    #         self.bot.answer_callback_query(
    #             callback_query.id,
    #             "❌ Ошибка создания backup"
    #         )
    
    # ============================================
    # УТИЛИТЫ ДЛЯ CALLBACK'ОВ
    # ============================================
    
    def create_confirmation_keyboard(self, confirm_data: str, cancel_data: str = "cancel") -> telebot.types.InlineKeyboardMarkup:
        """Создание клавиатуры подтверждения"""
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            telebot.types.InlineKeyboardButton("✅ Подтвердить", callback_data=confirm_data),
            telebot.types.InlineKeyboardButton("❌ Отменить", callback_data=cancel_data)
        )
        return keyboard
    
    def create_navigation_keyboard(self, back_data: str = "menu_main", home_data: str = "menu_main") -> telebot.types.InlineKeyboardMarkup:
        """Создание навигационной клавиатуры"""
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            telebot.types.InlineKeyboardButton("🔙 Назад", callback_data=back_data),
            telebot.types.InlineKeyboardButton("🏠 Главное меню", callback_data=home_data)
        )
        return keyboard
    
    def create_pagination_keyboard(self, page: int, total_pages: int, prefix: str) -> telebot.types.InlineKeyboardMarkup:
        """Создание клавиатуры с пагинацией"""
        keyboard = telebot.types.InlineKeyboardMarkup(row_width=3)
        
        buttons = []
        
        # Кнопка "Предыдущая страница"
        if page > 1:
            buttons.append(telebot.types.InlineKeyboardButton("⬅️", callback_data=f"{prefix}_page_{page-1}"))
        
        # Информация о текущей странице
        buttons.append(telebot.types.InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
        
        # Кнопка "Следующая страница"
        if page < total_pages:
            buttons.append(telebot.types.InlineKeyboardButton("➡️", callback_data=f"{prefix}_page_{page+1}"))
        
        if buttons:
            keyboard.add(*buttons)
        
        # Кнопки навигации
        keyboard.add(
            telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="menu_main"),
            telebot.types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")
        )
        
        return keyboard
    
    def safe_answer_callback(self, callback_query: CallbackQuery, text: str, show_alert: bool = False):
        """Безопасная отправка ответа на callback"""
        try:
            self.bot.answer_callback_query(
                callback_query.id,
                text,
                show_alert=show_alert
            )
        except Exception as e:
            logger.error(f"❌ Ошибка safe_answer_callback: {e}")
    
    def safe_edit_message(self, callback_query: CallbackQuery, text: str, reply_markup=None, parse_mode='HTML'):
        """Безопасное редактирование сообщения"""
        try:
            self.bot.edit_message_text(
                text,
                callback_query.message.chat.id,
                callback_query.message.message_id,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"❌ Ошибка safe_edit_message: {e}")
            # Если не получилось отредактировать, отправляем новое сообщение
            try:
                self.bot.send_message(
                    callback_query.message.chat.id,
                    text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            except Exception as e2:
                logger.error(f"❌ Ошибка fallback отправки: {e2}")


if __name__ == "__main__":
    """Тестирование CallbackHandler"""
    from database.manager import DatabaseManager
    from utils.security import SecurityManager
    
    print("🧪 Тестирование CallbackHandler...")
    
    # Создание тестовых компонентов  
    db = DatabaseManager("sqlite:///:memory:")
    db.create_tables()
    
    security = SecurityManager([12345], [2, 3])
    
    # Тестирование callback handler
    callback_handler = CallbackHandler(None, db, security)
    
    # Тестирование поиска обработчиков
    print("\n🔍 Тестирование поиска обработчиков:")
    
    test_callbacks = [
        'menu_main',
        'action_last10links', 
        'limit_burst',
        'dev_leaderboard_karma',
        'unknown_callback'
    ]
    
    for callback_data in test_callbacks:
        handler = callback_handler._find_callback_handler(callback_data)
        status = "✅ Найден" if handler else "❌ Не найден"
        print(f"• {callback_data}: {status}")
    
    # Тестирование информации о планах
    print("\n📋 Тестирование информации о планах:")
    test_actions = ['leaderboard_karma', 'action_ask_presave', 'diag_backup_status']
    
    for action in test_actions:
        plan_info = callback_handler._get_plan_info(action)
        print(f"• {action}: {plan_info['plan']} - {plan_info['description']}")
    
    print("\n✅ Тестирование CallbackHandler завершено!")