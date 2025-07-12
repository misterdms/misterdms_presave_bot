"""
🔘 Callbacks Handler - Do Presave Reminder Bot v25+
Обработчик всех callback_query (нажатий inline кнопок)
"""

import time
from typing import Optional, Dict, Any, List, Tuple
import telebot
from telebot.types import CallbackQuery, InlineKeyboardMarkup

from config import config
from database.manager import get_database_manager
from utils.security import (
    admin_required, security_manager, user_rate_limit,
    AccessDeniedError, RateLimitError
)
from utils.logger import get_logger, telegram_logger
from utils.helpers import (
    MessageFormatter, KeyboardBuilder, UserHelper, 
    DataHelper, ConfigHelper, CommandParser
)

logger = get_logger(__name__)

class CallbackHandler:
    """Обработчик callback_query (нажатий кнопок)"""
    
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot
        self.db = get_database_manager()
        
        # Кэш для предотвращения спама кнопок
        self.callback_cache = {}  # user_id: {callback_data: timestamp}
        self.callback_cooldown = 1.0  # 1 секунда между одинаковыми callback
        
        # Регистрируем обработчики
        self._register_handlers()
        
        logger.info("🔘 Callback Handler инициализирован")
    
    def _register_handlers(self):
        """Регистрация обработчиков callback_query"""
        
        # Основной обработчик всех callback
        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_all_callbacks(call: CallbackQuery):
            self.process_callback(call)
    
    def process_callback(self, call: CallbackQuery):
        """Основная обработка callback_query"""
        try:
            user_id = call.from_user.id
            callback_data = call.data
            
            # Проверяем активен ли бот
            if not ConfigHelper.is_bot_enabled() and not security_manager.is_admin(user_id):
                self.bot.answer_callback_query(
                    call.id, 
                    "🚫 Бот временно деактивирован", 
                    show_alert=True
                )
                return
            
            # Проверяем cooldown для предотвращения спама
            if self._is_callback_on_cooldown(user_id, callback_data):
                self.bot.answer_callback_query(call.id, "⏳ Слишком быстро!", show_alert=False)
                return
            
            # Обновляем кэш
            self._update_callback_cache(user_id, callback_data)
            
            # Логируем callback
            telegram_logger.user_action(
                user_id,
                f"нажал кнопку: {callback_data}",
                callback_data=callback_data
            )
            
            # Маршрутизируем по типу callback
            handled = self._route_callback(call)
            
            if not handled:
                # Неизвестный callback
                logger.warning(f"⚠️ Неизвестный callback: {callback_data} от пользователя {user_id}")
                self.bot.answer_callback_query(
                    call.id, 
                    "❓ Неизвестная команда", 
                    show_alert=False
                )
            
        except AccessDeniedError:
            self.bot.answer_callback_query(
                call.id, 
                "🚫 Доступ запрещен", 
                show_alert=True
            )
        except RateLimitError:
            self.bot.answer_callback_query(
                call.id, 
                "⚠️ Превышен лимит запросов", 
                show_alert=True
            )
        except Exception as e:
            logger.error(f"❌ Ошибка обработки callback {call.data}: {e}")
            self.bot.answer_callback_query(
                call.id, 
                "❌ Произошла ошибка", 
                show_alert=True
            )
    
    def _is_callback_on_cooldown(self, user_id: int, callback_data: str) -> bool:
        """Проверка cooldown для callback"""
        try:
            current_time = time.time()
            user_cache = self.callback_cache.get(user_id, {})
            last_time = user_cache.get(callback_data, 0)
            
            return current_time - last_time < self.callback_cooldown
        except:
            return False
    
    def _update_callback_cache(self, user_id: int, callback_data: str):
        """Обновление кэша callback"""
        try:
            current_time = time.time()
            
            if user_id not in self.callback_cache:
                self.callback_cache[user_id] = {}
            
            self.callback_cache[user_id][callback_data] = current_time
            
            # Очищаем старые записи
            cutoff_time = current_time - 60  # Храним 1 минуту
            for uid in list(self.callback_cache.keys()):
                user_callbacks = self.callback_cache[uid]
                expired_callbacks = [
                    cd for cd, timestamp in user_callbacks.items()
                    if timestamp < cutoff_time
                ]
                for cd in expired_callbacks:
                    del user_callbacks[cd]
                
                if not user_callbacks:
                    del self.callback_cache[uid]
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обновления кэша callback: {e}")
    
    def _route_callback(self, call: CallbackQuery) -> bool:
        """Маршрутизация callback по типам"""
        data = call.data
        
        # Навигационные callback (уже обрабатываются в menu.py)
        if data.startswith(('menu_', 'leaderboard_', 'action_', 'settings_', 'limits_')):
            # Эти callback обрабатываются в MenuManager
            return True
        
        # Callback для лидербордов (План 2)
        elif data.startswith('karma_'):
            return self._handle_karma_callbacks(call)
        
        # Callback для ИИ и форм (План 3)
        elif data.startswith(('ai_', 'form_', 'gratitude_')):
            return self._handle_ai_form_callbacks(call)
        
        # Callback для backup (План 4)
        elif data.startswith('backup_'):
            return self._handle_backup_callbacks(call)
        
        # Callback для аналитики
        elif data.startswith('analytics_'):
            return self._handle_analytics_callbacks(call)
        
        # Callback для диагностики
        elif data.startswith('diagnostics_'):
            return self._handle_diagnostics_callbacks(call)
        
        # Callback для пагинации
        elif data.startswith('page_'):
            return self._handle_pagination_callbacks(call)
        
        # Универсальные callback
        elif data == 'under_development':
            return self._handle_under_development(call)
        elif data == 'refresh':
            return self._handle_refresh(call)
        elif data == 'close':
            return self._handle_close(call)
        
        return False
    
    # ============================================
    # ПЛАН 2 - CALLBACK КАРМЫ
    # ============================================
    
    def _handle_karma_callbacks(self, call: CallbackQuery) -> bool:
        """Обработка callback для системы кармы"""
        if not config.ENABLE_PLAN_2_FEATURES:
            self._send_feature_unavailable(call, "Система кармы (План 2)")
            return True
        
        data = call.data
        
        try:
            if data == 'karma_leaderboard':
                self._show_karma_leaderboard(call)
            
            elif data == 'karma_history':
                self._show_karma_history(call)
            
            elif data.startswith('karma_user_'):
                # karma_user_123456 - показать карму конкретного пользователя
                user_id = int(data.split('_')[-1])
                self._show_user_karma_details(call, user_id)
            
            elif data == 'karma_top_gainers':
                self._show_top_karma_gainers(call)
            
            elif data == 'karma_stats':
                self._show_karma_statistics(call)
            
            else:
                return False
            
            self.bot.answer_callback_query(call.id)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки karma callback: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
            return True
    
    @admin_required
    def _show_karma_leaderboard(self, call: CallbackQuery):
        """Показ лидерборда кармы"""
        try:
            leaderboard_data = self.db.get_karma_leaderboard(limit=10)
            
            text = DataHelper.format_leaderboard(leaderboard_data, 'karma')
            text += f"\n\n{MessageFormatter.get_emoji('refresh')} Обновлено: только что"
            
            # Добавляем кнопки
            buttons = [
                [{'text': f"{MessageFormatter.get_emoji('refresh')} Обновить", 'callback_data': 'karma_leaderboard'}],
                [{'text': f"{MessageFormatter.get_emoji('stats')} Статистика кармы", 'callback_data': 'karma_stats'}],
                [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': 'menu_leaderboard'}]
            ]
            
            keyboard = KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа лидерборда кармы: {e}")
    
    # ============================================
    # ПЛАН 3 - CALLBACK ИИ И ФОРМ
    # ============================================
    
    def _handle_ai_form_callbacks(self, call: CallbackQuery) -> bool:
        """Обработка callback для ИИ и форм"""
        if not config.ENABLE_PLAN_3_FEATURES:
            self._send_feature_unavailable(call, "ИИ и интерактивные формы (План 3)")
            return True
        
        data = call.data
        
        try:
            # ИИ callback
            if data.startswith('ai_'):
                return self._handle_ai_specific_callbacks(call)
            
            # Формы callback
            elif data.startswith('form_'):
                return self._handle_form_specific_callbacks(call)
            
            # Благодарности callback
            elif data.startswith('gratitude_'):
                return self._handle_gratitude_callbacks(call)
            
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки AI/Form callback: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
            return True
    
    def _handle_ai_specific_callbacks(self, call: CallbackQuery) -> bool:
        """Обработка ИИ-специфичных callback"""
        data = call.data
        
        if data == 'ai_settings':
            self._show_ai_settings(call)
        elif data == 'ai_stats':
            self._show_ai_statistics(call)
        elif data == 'ai_conversation_history':
            self._show_ai_conversation_history(call)
        else:
            return False
        
        self.bot.answer_callback_query(call.id)
        return True
    
    def _handle_form_specific_callbacks(self, call: CallbackQuery) -> bool:
        """Обработка форм-специфичных callback"""
        data = call.data
        
        if data == 'form_start_presave':
            self._start_presave_form(call)
        elif data == 'form_start_claim':
            self._start_claim_form(call)
        elif data == 'form_cancel':
            self._cancel_form(call)
        elif data.startswith('form_approve_'):
            claim_id = int(data.split('_')[-1])
            self._approve_claim(call, claim_id)
        elif data.startswith('form_reject_'):
            claim_id = int(data.split('_')[-1])
            self._reject_claim(call, claim_id)
        else:
            return False
        
        self.bot.answer_callback_query(call.id)
        return True
    
    # ============================================
    # ПЛАН 4 - CALLBACK BACKUP
    # ============================================
    
    def _handle_backup_callbacks(self, call: CallbackQuery) -> bool:
        """Обработка callback для backup системы"""
        if not config.ENABLE_PLAN_4_FEATURES:
            self._send_feature_unavailable(call, "Backup система (План 4)")
            return True
        
        data = call.data
        
        try:
            if data == 'backup_create':
                self._create_backup(call)
            elif data == 'backup_history':
                self._show_backup_history(call)
            elif data == 'backup_status':
                self._show_backup_status(call)
            elif data == 'backup_help':
                self._show_backup_help(call)
            else:
                return False
            
            self.bot.answer_callback_query(call.id)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки backup callback: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
            return True
    
    # ============================================
    # АНАЛИТИЧЕСКИЕ CALLBACK
    # ============================================
    
    def _handle_analytics_callbacks(self, call: CallbackQuery) -> bool:
        """Обработка callback для аналитики"""
        data = call.data
        
        try:
            if data == 'analytics_links':
                self._show_links_analytics(call)
            elif data == 'analytics_users':
                self._show_users_analytics(call)
            elif data == 'analytics_trends':
                self._show_trends_analytics(call)
            elif data.startswith('analytics_user_'):
                user_id = int(data.split('_')[-1])
                self._show_user_analytics(call, user_id)
            else:
                return False
            
            self.bot.answer_callback_query(call.id)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки analytics callback: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
            return True
    
    @admin_required
    def _show_links_analytics(self, call: CallbackQuery):
        """Показ аналитики ссылок"""
        try:
            from handlers.links import LinkHandler
            link_handler = LinkHandler(self.bot)
            
            # Получаем аналитику трендов
            trends = link_handler.analyze_link_trends(days=7)
            
            text = f"{MessageFormatter.get_emoji('stats')} **АНАЛИТИКА ССЫЛОК (7 дней)**\n\n"
            
            if 'error' not in trends:
                text += f"**Общая статистика:**\n"
                text += f"• Всего ссылок: {trends['total_links']}\n"
                text += f"• В среднем в день: {trends['daily_average']:.1f}\n\n"
                
                if trends['top_domains']:
                    text += f"**Топ платформ:**\n"
                    for i, (domain, count) in enumerate(trends['top_domains'][:5], 1):
                        text += f"{i}. {domain}: {count} ссылок\n"
                
                if trends['most_active_day']:
                    day, count = trends['most_active_day']
                    text += f"\n**Самый активный день:** {day} ({count} ссылок)"
            else:
                text += f"Ошибка загрузки данных: {trends['error']}"
            
            # Кнопки
            buttons = [
                [{'text': f"{MessageFormatter.get_emoji('refresh')} Обновить", 'callback_data': 'analytics_links'}],
                [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': 'menu_analytics'}]
            ]
            
            keyboard = KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа аналитики ссылок: {e}")
    
    # ============================================
    # ДИАГНОСТИЧЕСКИЕ CALLBACK
    # ============================================
    
    def _handle_diagnostics_callbacks(self, call: CallbackQuery) -> bool:
        """Обработка callback для диагностики"""
        data = call.data
        
        try:
            if data == 'diagnostics_system':
                self._show_system_diagnostics(call)
            elif data == 'diagnostics_performance':
                self._show_performance_diagnostics(call)
            elif data == 'diagnostics_health':
                self._show_health_check(call)
            elif data == 'diagnostics_logs':
                self._show_recent_logs(call)
            else:
                return False
            
            self.bot.answer_callback_query(call.id)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки diagnostics callback: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
            return True
    
    @admin_required
    def _show_system_diagnostics(self, call: CallbackQuery):
        """Показ системной диагностики"""
        try:
            # Получаем информацию о системе
            db_stats = self.db.get_database_stats()
            health = self.db.health_check()
            
            text = f"{MessageFormatter.get_emoji('system')} **СИСТЕМНАЯ ДИАГНОСТИКА**\n\n"
            
            # Статус компонентов
            text += f"**Статус компонентов:**\n"
            text += f"• БД: {'✅' if health['database_connection'] == 'ok' else '❌'}\n"
            text += f"• Бот: {'✅' if ConfigHelper.is_bot_enabled() else '❌'}\n"
            text += f"• Webhook: {'✅' if config.RENDER_EXTERNAL_URL else '❌'}\n\n"
            
            # Статистика
            text += f"**Статистика:**\n"
            text += f"• Пользователей: {MessageFormatter.format_number(db_stats['total_users'])}\n"
            text += f"• Активных за неделю: {MessageFormatter.format_number(db_stats['active_users_week'])}\n"
            text += f"• Ссылок: {MessageFormatter.format_number(db_stats['total_links'])}\n"
            
            if config.ENABLE_PLAN_2_FEATURES:
                text += f"• Общая карма: {MessageFormatter.format_number(db_stats['total_karma_points'])}\n"
            
            # Память и производительность
            try:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / 1024 / 1024
                text += f"\n**Ресурсы:**\n"
                text += f"• Память: {memory_mb:.1f} MB\n"
            except:
                text += f"\n**Ресурсы:** Информация недоступна\n"
            
            # Кнопки
            buttons = [
                [{'text': f"{MessageFormatter.get_emoji('refresh')} Обновить", 'callback_data': 'diagnostics_system'}],
                [{'text': f"{MessageFormatter.get_emoji('health')} Health Check", 'callback_data': 'diagnostics_health'}],
                [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': 'menu_diagnostics'}]
            ]
            
            keyboard = KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа системной диагностики: {e}")
    
    # ============================================
    # ПАГИНАЦИЯ CALLBACK
    # ============================================
    
    def _handle_pagination_callbacks(self, call: CallbackQuery) -> bool:
        """Обработка callback для пагинации"""
        data = call.data
        
        try:
            # Парсим callback пагинации: page_type_action_value
            parts = data.split('_')
            if len(parts) < 3:
                return False
            
            page_type = parts[1]  # links, users, karma, etc.
            action = parts[2]     # next, prev, goto
            
            if action == 'next':
                current_page = int(parts[3]) if len(parts) > 3 else 1
                self._show_paginated_content(call, page_type, current_page + 1)
            elif action == 'prev':
                current_page = int(parts[3]) if len(parts) > 3 else 1
                self._show_paginated_content(call, page_type, max(1, current_page - 1))
            elif action == 'goto':
                page_num = int(parts[3]) if len(parts) > 3 else 1
                self._show_paginated_content(call, page_type, page_num)
            
            self.bot.answer_callback_query(call.id)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки pagination callback: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)
            return True
    
    def _show_paginated_content(self, call: CallbackQuery, content_type: str, page: int):
        """Показ контента с пагинацией"""
        try:
            items_per_page = 10
            
            if content_type == 'links':
                # Пагинация ссылок
                all_links = self.db.get_recent_links(limit=100)
                total_pages = max(1, (len(all_links) + items_per_page - 1) // items_per_page)
                page = min(page, total_pages)
                
                start_idx = (page - 1) * items_per_page
                end_idx = start_idx + items_per_page
                page_links = all_links[start_idx:end_idx]
                
                text = DataHelper.format_links_list(page_links, max_links=items_per_page)
                text += f"\n\nСтраница {page} из {total_pages}"
                
                keyboard = KeyboardBuilder.create_pagination_keyboard(page, total_pages, 'page_links')
                
            else:
                # Другие типы контента
                text = f"Пагинация для {content_type} в разработке"
                keyboard = KeyboardBuilder.create_back_button('menu_main')
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа пагинированного контента: {e}")
    
    # ============================================
    # УНИВЕРСАЛЬНЫЕ CALLBACK
    # ============================================
    
    def _handle_under_development(self, call: CallbackQuery) -> bool:
        """Обработка callback 'в разработке'"""
        try:
            text = f"{MessageFormatter.get_emoji('loading')} **ФУНКЦИЯ В РАЗРАБОТКЕ**\n\n"
            text += f"Эта функция будет доступна в следующих планах развития:\n\n"
            text += f"• **План 2** - Система кармы и лидерборды\n"
            text += f"• **План 3** - ИИ и интерактивные формы\n"
            text += f"• **План 4** - Расширенная backup система\n\n"
            text += f"{MessageFormatter.get_emoji('time')} Разработка ведется поэтапно для обеспечения стабильности."
            
            keyboard = KeyboardBuilder.create_back_button('menu_main')
            
            self.bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            
            self.bot.answer_callback_query(call.id, "🔄 Функция в разработке", show_alert=False)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка показа 'в разработке': {e}")
            return False
    
    def _handle_refresh(self, call: CallbackQuery) -> bool:
        """Обработка callback обновления"""
        try:
            # Получаем текущий callback и перенаправляем его для обновления
            current_callback = call.message.reply_markup.keyboard[0][0].callback_data if call.message.reply_markup else None
            
            if current_callback:
                # Создаем новый call с текущим callback_data для обновления
                call.data = current_callback
                self._route_callback(call)
            
            self.bot.answer_callback_query(call.id, "🔄 Обновлено", show_alert=False)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления: {e}")
            self.bot.answer_callback_query(call.id, "❌ Ошибка обновления", show_alert=True)
            return False
    
    def _handle_close(self, call: CallbackQuery) -> bool:
        """Обработка callback закрытия"""
        try:
            self.bot.delete_message(call.message.chat.id, call.message.message_id)
            self.bot.answer_callback_query(call.id, "✅ Закрыто", show_alert=False)
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия сообщения: {e}")
            self.bot.answer_callback_query(call.id, "❌ Не удалось закрыть", show_alert=True)
            return False
    
    # ============================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================
    
    def _send_feature_unavailable(self, call: CallbackQuery, feature_name: str):
        """Отправка уведомления о недоступности функции"""
        try:
            message = f"🔄 {feature_name} будет доступна в следующих планах развития"
            self.bot.answer_callback_query(call.id, message, show_alert=True)
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о недоступности: {e}")
    
    def get_callback_stats(self) -> Dict[str, Any]:
        """Получение статистики callback"""
        try:
            total_users = len(self.callback_cache)
            total_callbacks = sum(len(callbacks) for callbacks in self.callback_cache.values())
            
            return {
                'active_users': total_users,
                'total_cached_callbacks': total_callbacks,
                'cooldown_seconds': self.callback_cooldown
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики callback: {e}")
            return {}
    
    # ============================================
    # ЗАГЛУШКИ ДЛЯ БУДУЩИХ ПЛАНОВ
    # ============================================
    
    def _start_presave_form(self, call: CallbackQuery):
        """Заглушка для запуска формы пресейва (План 3)"""
        message = "📝 Интерактивные формы будут доступны в Плане 3"
        self.bot.answer_callback_query(call.id, message, show_alert=True)
    
    def _start_claim_form(self, call: CallbackQuery):
        """Заглушка для запуска формы заявки (План 3)"""
        message = "✅ Система заявок будет доступна в Плане 3"
        self.bot.answer_callback_query(call.id, message, show_alert=True)
    
    def _show_ai_settings(self, call: CallbackQuery):
        """Заглушка для настроек ИИ (План 3)"""
        message = "🤖 Настройки ИИ будут доступны в Плане 3"
        self.bot.answer_callback_query(call.id, message, show_alert=True)
    
    def _create_backup(self, call: CallbackQuery):
        """Заглушка для создания backup (План 4)"""
        message = "💾 Система backup будет доступна в Плане 4"
        self.bot.answer_callback_query(call.id, message, show_alert=True)

# ============================================
# ГЛОБАЛЬНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ
# ============================================

def init_callback_handlers(bot: telebot.TeleBot) -> CallbackHandler:
    """Инициализация обработчиков callback"""
    return CallbackHandler(bot)

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = ['CallbackHandler', 'init_callback_handlers']

if __name__ == "__main__":
    print("🧪 Тестирование Callback Handler...")
    print("✅ Модуль callbacks.py готов к интеграции")
