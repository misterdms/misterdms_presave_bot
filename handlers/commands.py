"""
Обработчик команд Do Presave Reminder Bot v25+
Все команды бота с проверкой прав и валидацией

ПЛАН 1: Базовые команды (АКТИВНЫЕ)
ПЛАН 2: Команды кармы (ЗАГЛУШКИ)
ПЛАН 3: Команды ИИ и форм (ЗАГЛУШКИ)
ПЛАН 4: Команды backup (ЗАГЛУШКИ)
"""

import os
from datetime import datetime
from typing import List, Optional
import telebot
from telebot.types import Message

from database.manager import DatabaseManager
from utils.security import SecurityManager, admin_required, whitelist_required, extract_command_args
from utils.logger import get_logger, log_user_action, log_admin_action
from utils.helpers import format_user_mention

logger = get_logger(__name__)

class CommandHandler:
    """Обработчик всех команд бота"""
    
    def __init__(self, bot: telebot.TeleBot, db_manager: DatabaseManager, security_manager: SecurityManager):
        """Инициализация обработчика команд"""
        self.bot = bot
        self.db = db_manager
        self.security = security_manager
        
        logger.info("CommandHandler инициализирован")
    
    def register_handlers(self):  # ← ПРАВИЛЬНОЕ ИМЯ!
        """Регистрация всех обработчиков команд"""
        
        # ПЛАН 1: Базовые команды (АКТИВНЫЕ)
        self.bot.register_message_handler(
            self.cmd_start,
            commands=['start']
        )
        
        self.bot.register_message_handler(
            self.cmd_help,
            commands=['help']
        )
        
        self.bot.register_message_handler(
            self.cmd_mystat,
            commands=['mystat']
        )
        
        self.bot.register_message_handler(
            self.cmd_last10links,
            commands=['last10links']
        )
        
        self.bot.register_message_handler(
            self.cmd_last30links,
            commands=['last30links']
        )

        # Команды меню (только админы)
        self.bot.register_message_handler(
            self.cmd_menu,
            commands=['menu']
        )
        
        self.bot.register_message_handler(
            self.cmd_resetmenu,
            commands=['resetmenu']
        )

        # Команды управления ботом (только админы)
        self.bot.register_message_handler(
            self.cmd_enablebot,
            commands=['enablebot']
        )
        
        self.bot.register_message_handler(
            self.cmd_disablebot,
            commands=['disablebot']
        )
        
        # Команды режимов лимитов (только админы)
        self.bot.register_message_handler(
            self.cmd_setmode_conservative,
            commands=['setmode_conservative']
        )
        
        self.bot.register_message_handler(
            self.cmd_setmode_normal,
            commands=['setmode_normal']
        )
        
        self.bot.register_message_handler(
            self.cmd_setmode_burst,
            commands=['setmode_burst']
        )
        
        self.bot.register_message_handler(
            self.cmd_setmode_adminburst,
            commands=['setmode_adminburst']
        )
        
        self.bot.register_message_handler(
            self.cmd_currentmode,
            commands=['currentmode']
        )
        
        # Команды аналитики (только админы)
        self.bot.register_message_handler(
            self.cmd_linksby,
            commands=['linksby']
        )
        
        # ПЛАН 2: Команды кармы (ЗАГЛУШКИ)
        # self.bot.register_message_handler(
        #     self.cmd_karma,
        #     commands=['karma']
        # )
        
        # self.bot.register_message_handler(
        #     self.cmd_karmastat,
        #     commands=['karmastat']
        # )
        
        # self.bot.register_message_handler(
        #     self.cmd_presavestat,
        #     commands=['presavestat']
        # )
        
        # self.bot.register_message_handler(
        #     self.cmd_ratiostat,
        #     commands=['ratiostat']
        # )
        
        # ПЛАН 3: Команды ИИ и форм (ЗАГЛУШКИ)
        # self.bot.register_message_handler(
        #     self.cmd_askpresave,
        #     commands=['askpresave']
        # )
        
        # self.bot.register_message_handler(
        #     self.cmd_claimpresave,
        #     commands=['claimpresave']
        # )
        
        # self.bot.register_message_handler(
        #     self.cmd_checkapprovals,
        #     commands=['checkapprovals']
        # )
        
        # ПЛАН 4: Команды backup (ЗАГЛУШКИ)
        # self.bot.register_message_handler(
        #     self.cmd_downloadsql,
        #     commands=['downloadsql']
        # )
        
        # self.bot.register_message_handler(
        #     self.cmd_backupstatus,
        #     commands=['backupstatus']
        # )
        
        # self.bot.register_message_handler(
        #     self.cmd_backuphelp,
        #     commands=['backuphelp']
        # )
        
        logger.info("Все обработчики команд зарегистрированы")
    
    # ============================================
    # ПЛАН 1: БАЗОВЫЕ КОМАНДЫ (АКТИВНЫЕ)
    # ============================================
    
    @admin_required
    @whitelist_required
    def cmd_start(self, message: Message):
        """Команда /start - приветствие"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            username = message.from_user.username
            first_name = message.from_user.first_name
            
            # Регистрируем пользователя в БД
            user = self.db.get_or_create_user(user_id, username, first_name)
            
            log_user_action(logger, user_id, "выполнил команду /start")
            
            # Проверяем является ли пользователь админом
            is_admin = self.security.is_admin(user_id)
            
            if is_admin:
                welcome_text = f"""🎵 <b>Добро пожаловать, администратор!</b>

👋 Привет, {format_user_mention(user_id, username, first_name)}!

Вы успешно подключились к <b>Do Presave Reminder Bot v25+</b>

👑 <b>Админские возможности:</b>
• /menu - панель управления ботом
• /help - список всех команд
• /mystat - ваша статистика

🎯 <b>Основные функции:</b>
• Автоматические напоминания о пресейвах
• Статистика ссылок и активности
• Управление режимами лимитов API
• Диагностика и мониторинг системы

🚀 <b>В разработке:</b>
• ПЛАН 2: Система кармы и званий
• ПЛАН 3: ИИ помощник и интерактивные формы  
• ПЛАН 4: Автоматический backup системы

Используйте /menu для доступа ко всем функциям!"""
            else:
                welcome_text = f"""🎵 <b>Добро пожаловать!</b>

👋 Привет, {format_user_mention(user_id, username, first_name)}!

Вы подключились к <b>Do Presave Reminder Bot v25+</b>

ℹ️ Этот бот предназначен для администраторов музыкального сообщества.

🎵 <b>Как это работает:</b>
• Опубликуйте ссылку на пресейв в разрешенном топике
• Бот автоматически напомнит о взаимности
• Следите за статистикой через /mystat

💡 Если у вас есть вопросы, обратитесь к администраторам сообщества."""
            
            self.bot.send_message(
                message.chat.id,
                welcome_text,
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_start: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при выполнении команды /start",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    def cmd_help(self, message: Message):
        """Команда /help - список команд с описанием"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            log_user_action(logger, user_id, "запросил помощь /help")
            
            is_admin = self.security.is_admin(user_id)
            
            if is_admin:
                help_text = """📋 <b>Список команд Do Presave Reminder Bot v25+</b>

🎛️ <b>Навигация и основное:</b>
/start - Приветствие и информация о боте
/help - Этот список команд
/menu - Главное меню управления (интерактивное)
/resetmenu - Сброс меню при проблемах

📊 <b>Статистика и данные:</b>
/mystat - Моя статистика и активность
/last10links - Последние 10 ссылок в сообществе
/last30links - Последние 30 ссылок в сообществе
/linksby @username - Ссылки конкретного пользователя

⚙️ <b>Управление ботом:</b>
/enablebot - Активировать бота
/disablebot - Деактивировать бота

⚡ <b>Режимы лимитов API:</b>
/setmode_conservative - Режим Conservative (60/час)
/setmode_normal - Режим Normal (180/час)
/setmode_burst - Режим Burst (600/час, по умолчанию)
/setmode_adminburst - Режим Admin Burst (1200/час)
/currentmode - Показать текущий режим

🚧 <b>В разработке (ПЛАН 2-4):</b>
• /karma @username +/-число - Управление кармой
• /karmastat - Рейтинг по карме
• /askpresave - Интерактивная форма пресейва
• /claimpresave - Заявка о совершенном пресейве
• /downloadsql - Backup базы данных
• И многое другое...

💡 <b>Примеры использования:</b>
• <code>/linksby @username</code> - ссылки пользователя
• <code>/setmode_burst</code> - установить быстрый режим
• <code>/menu</code> - открыть интерактивное меню

🎯 <b>Интерактивное меню /menu предоставляет доступ ко всем функциям через удобные кнопки!</b>"""
            else:
                help_text = """📋 <b>Помощь Do Presave Reminder Bot v25+</b>

🎵 <b>Доступные команды:</b>
/start - Приветствие
/help - Эта справка  
/mystat - Моя статистика

🤖 <b>Как пользоваться ботом:</b>
1. Опубликуйте ссылку на пресейв в разрешенном топике
2. Бот автоматически отправит напоминание о взаимности
3. Используйте /mystat для просмотра своей статистики

📞 <b>Нужна помощь?</b>
Обратитесь к администраторам сообщества.

🚀 <b>Скоро:</b> Система кармы, ИИ помощник и многое другое!"""
            
            self.bot.send_message(
                message.chat.id,
                help_text,
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_help: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при получении справки",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    def cmd_mystat(self, message: Message):
        """Команда /mystat - статистика пользователя"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            log_user_action(logger, user_id, "запросил статистику /mystat")
            
            # Получаем статистику пользователя
            stats = self.db.get_user_stats(user_id)
            
            if not stats:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Не удалось получить статистику. Используйте /start для регистрации.",
                    message_thread_id=thread_id
                )
                return
            
            # Формируем сообщение со статистикой
            stat_parts = [
                f"📊 <b>Статистика пользователя</b>",
                f"👤 {format_user_mention(user_id, stats.get('username'), stats.get('first_name'))}",
                ""
            ]
            
            # Базовая статистика ПЛАН 1
            stat_parts.extend([
                "📎 <b>Ссылки:</b>",
                f"• Всего опубликовано: {stats.get('total_links', 0)}",
                f"• В этом месяце: {stats.get('links_this_month', 0)}",
                ""
            ])
            
            # ПЛАН 2: Статистика кармы (ЗАГЛУШКА)
            # stat_parts.extend([
            #     "🏆 <b>Карма и звание:</b>",
            #     f"• Карма: {stats.get('karma_points', 0)} ⭐",
            #     f"• Звание: {stats.get('rank', '🥉 Новенький')}",
            #     f"• Подтвержденных пресейвов: {stats.get('total_approvals', 0)}",
            #     ""
            # ])
            
            # ПЛАН 3: Статистика ИИ и форм (ЗАГЛУШКА)
            # stat_parts.extend([
            #     "🤖 <b>Активность:</b>",
            #     f"• Взаимодействий с ИИ: {stats.get('ai_interactions', 0)}",
            #     f"• Заявок на пресейвы: {stats.get('presave_requests', 0)}",
            #     f"• Заявок о пресейвах: {stats.get('approval_claims', 0)}",
            #     f"• Сообщений в топиках: {stats.get('messages_count', 0)}",
            #     ""
            # ])
            
            # Информация об аккаунте
            member_since = stats.get('member_since')
            last_seen = stats.get('last_seen')
            
            stat_parts.extend([
                "👤 <b>Аккаунт:</b>",
                f"• Зарегистрирован: {member_since.strftime('%d.%m.%Y') if member_since else 'Неизвестно'}",
                f"• Последняя активность: {last_seen.strftime('%d.%m.%Y %H:%M') if last_seen else 'Сейчас'}",
            ])
            
            if stats.get('is_admin'):
                stat_parts.extend([
                    "",
                    "👑 <b>Статус:</b> Администратор"
                ])
            
            stat_parts.extend([
                "",
                "💡 Используйте /menu для доступа к дополнительным функциям!"
            ])
            
            self.bot.send_message(
                message.chat.id,
                "\n".join(stat_parts),
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_mystat: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при получении статистики",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    def cmd_last10links(self, message: Message):
        """Команда /last10links - последние 10 ссылок"""
        self._show_recent_links(message, 10)
    
    def cmd_last30links(self, message: Message):
        """Команда /last30links - последние 30 ссылок"""
        self._show_recent_links(message, 30)
    
    def _show_recent_links(self, message: Message, count: int):
        """Общая функция показа последних ссылок"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            log_user_action(logger, user_id, f"запросил последние {count} ссылок")
            
            # Получаем ссылки
            links = self.db.get_recent_links(count)
            
            if not links:
                self.bot.send_message(
                    message.chat.id,
                    f"📎 <b>Последние {count} ссылок</b>\n\n🤷 Ссылок пока нет в базе данных.",
                    parse_mode='HTML',
                    message_thread_id=thread_id
                )
                return
            
            # Формируем сообщение
            text_parts = [f"📎 <b>Последние {count} ссылок</b>\n"]
            
            for i, link in enumerate(links, 1):
                user = self.db.get_user_by_id(link.user_id)
                username = f"@{user.username}" if user and user.username else f"ID{link.user_id}"
                date_str = link.created_at.strftime("%d.%m %H:%M")
                
                # Обрезаем URL если очень длинный
                display_url = link.url if len(link.url) <= 60 else link.url[:57] + "..."
                
                text_parts.append(f"{i}. <b>{username}</b> ({date_str})")
                text_parts.append(f"   🔗 {display_url}")
                
                if i < len(links):
                    text_parts.append("")
            
            # Разбиваем на части если сообщение слишком длинное
            full_text = "\n".join(text_parts)
            
            if len(full_text) <= 4000:
                self.bot.send_message(
                    message.chat.id,
                    full_text,
                    parse_mode='HTML',
                    message_thread_id=thread_id
                )
            else:
                # Отправляем по частям
                chunk_size = 3500
                for i in range(0, len(full_text), chunk_size):
                    chunk = full_text[i:i + chunk_size]
                    self.bot.send_message(
                        message.chat.id,
                        chunk,
                        parse_mode='HTML',
                        message_thread_id=thread_id
                    )
            
        except Exception as e:
            logger.error(f"❌ Ошибка _show_recent_links: {e}")
            self.bot.send_message(
                message.chat.id,
                f"❌ Ошибка при получении последних {count} ссылок",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    # ============================================
    # КОМАНДЫ УПРАВЛЕНИЯ БОТОМ (ТОЛЬКО АДМИНЫ)
    # ============================================
    
    @admin_required
    def cmd_enablebot(self, message: Message):
        """Команда /enablebot - активация бота"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            
            self.db.set_setting('bot_enabled', True, 'bool', 
                               'Статус активности бота', user_id)
            
            log_admin_action(logger, user_id, "активировал бота")
            
            self.bot.send_message(
                message.chat.id,
                "✅ <b>Бот активирован!</b>\n\nВсе функции включены и готовы к работе.",
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_enablebot: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при активации бота",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    @admin_required
    def cmd_disablebot(self, message: Message):
        """Команда /disablebot - деактивация бота"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            
            self.db.set_setting('bot_enabled', False, 'bool',
                               'Статус активности бота', user_id)
            
            log_admin_action(logger, user_id, "деактивировал бота")
            
            self.bot.send_message(
                message.chat.id,
                "⏸️ <b>Бот деактивирован!</b>\n\nБот временно приостановлен. Для включения используйте /enablebot",
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_disablebot: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при деактивации бота",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    # ============================================
    # КОМАНДЫ РЕЖИМОВ ЛИМИТОВ (ТОЛЬКО АДМИНЫ)
    # ============================================
    
    @admin_required
    @whitelist_required
    def cmd_setmode_conservative(self, message: Message):
        """Команда /setmode_conservative"""
        self._set_limit_mode(message, 'CONSERVATIVE')
    
    @admin_required
    @whitelist_required
    def cmd_setmode_normal(self, message: Message):
        """Команда /setmode_normal"""
        self._set_limit_mode(message, 'NORMAL')
    
    @admin_required
    @whitelist_required
    def cmd_setmode_burst(self, message: Message):
        """Команда /setmode_burst"""
        self._set_limit_mode(message, 'BURST')
    
    @admin_required
    @whitelist_required
    def cmd_setmode_adminburst(self, message: Message):
        """Команда /setmode_adminburst"""
        self._set_limit_mode(message, 'ADMIN_BURST')
    
    def _set_limit_mode(self, message: Message, mode: str):
        """Общая функция установки режима лимитов"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            
            # Получаем конфигурацию режима
            mode_configs = {
                'CONSERVATIVE': {'emoji': '🐌', 'name': 'Conservative', 'max_hour': 60, 'cooldown': 60},
                'NORMAL': {'emoji': '⚡', 'name': 'Normal', 'max_hour': 180, 'cooldown': 20},
                'BURST': {'emoji': '🚀', 'name': 'Burst', 'max_hour': 600, 'cooldown': 6},
                'ADMIN_BURST': {'emoji': '⚡⚡', 'name': 'Admin Burst', 'max_hour': 1200, 'cooldown': 3}
            }
            
            if mode not in mode_configs:
                self.bot.send_message(
                    message.chat.id,
                    "❌ Неизвестный режим лимитов",
                    message_thread_id=thread_id
                )
                return
            
            config = mode_configs[mode]
            
            # Сохраняем режим
            self.db.set_setting('current_limit_mode', mode, 'string',
                               'Текущий режим лимитов API', user_id)
            
            log_admin_action(logger, user_id, f"установил режим лимитов {mode}")
            
            self.bot.send_message(
                message.chat.id,
                f"{config['emoji']} <b>Режим лимитов изменен!</b>\n\n"
                f"🎯 <b>Новый режим:</b> {config['name']}\n"
                f"📊 <b>Лимиты:</b> {config['max_hour']} запросов/час\n"
                f"⏱️ <b>Cooldown:</b> {config['cooldown']} секунд\n\n"
                f"Изменения применены немедленно.",
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка _set_limit_mode: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при изменении режима лимитов",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    @admin_required
    @whitelist_required
    def cmd_currentmode(self, message: Message):
        """Команда /currentmode - показ текущего режима"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            current_mode = self.db.get_setting('current_limit_mode', 'BURST')
            
            mode_configs = {
                'CONSERVATIVE': {'emoji': '🐌', 'name': 'Conservative', 'max_hour': 60, 'cooldown': 60},
                'NORMAL': {'emoji': '⚡', 'name': 'Normal', 'max_hour': 180, 'cooldown': 20},
                'BURST': {'emoji': '🚀', 'name': 'Burst', 'max_hour': 600, 'cooldown': 6},
                'ADMIN_BURST': {'emoji': '⚡⚡', 'name': 'Admin Burst', 'max_hour': 1200, 'cooldown': 3}
            }
            
            config = mode_configs.get(current_mode, mode_configs['BURST'])
            
            self.bot.send_message(
                message.chat.id,
                f"📊 <b>Текущий режим лимитов</b>\n\n"
                f"{config['emoji']} <b>Режим:</b> {config['name']}\n"
                f"🎯 <b>Лимит:</b> {config['max_hour']} запросов в час\n"
                f"⏱️ <b>Cooldown:</b> {config['cooldown']} секунд между запросами\n\n"
                f"💡 Для смены режима используйте команды /setmode_*",
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_currentmode: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при получении текущего режима",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    # ============================================
    # КОМАНДЫ АНАЛИТИКИ (ТОЛЬКО АДМИНЫ)
    # ============================================
    
    @admin_required
    @whitelist_required
    def cmd_linksby(self, message: Message):
        """Команда /linksby @username - ссылки пользователя"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            args = extract_command_args(message)
            
            if not args:
                self.bot.send_message(
                    message.chat.id,
                    "❌ <b>Неверный формат команды!</b>\n\n"
                    "📝 <b>Правильный формат:</b>\n"
                    "<code>/linksby @username</code>\n\n"
                    "💡 <b>Пример:</b>\n"
                    "<code>/linksby @testuser</code>",
                    parse_mode='HTML',
                    message_thread_id=thread_id
                )
                return
            
            username = args[0].lstrip('@')
            
            # Получаем ссылки пользователя
            links = self.db.get_links_by_username(username)
            
            if not links:
                self.bot.send_message(
                    message.chat.id,
                    f"🔍 <b>Ссылки пользователя @{username}</b>\n\n"
                    f"🤷 Пользователь не найден или у него нет ссылок.",
                    parse_mode='HTML',
                    message_thread_id=thread_id
                )
                return
            
            # Формируем отчет
            text_parts = [
                f"🔍 <b>Ссылки пользователя @{username}</b>",
                f"📊 <b>Всего найдено:</b> {len(links)} ссылок\n"
            ]
            
            for i, link in enumerate(links[:20], 1):  # Показываем максимум 20
                date_str = link.created_at.strftime("%d.%m.%Y %H:%M")
                display_url = link.url if len(link.url) <= 50 else link.url[:47] + "..."
                
                text_parts.append(f"{i}. {date_str}")
                text_parts.append(f"   🔗 {display_url}")
                
                if i < min(len(links), 20):
                    text_parts.append("")
            
            if len(links) > 20:
                text_parts.append(f"\n... и еще {len(links) - 20} ссылок")
            
            log_admin_action(logger, user_id, f"запросил ссылки пользователя @{username}")
            
            self.bot.send_message(
                message.chat.id,
                "\n".join(text_parts),
                parse_mode='HTML',
                message_thread_id=thread_id
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_linksby: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка при получении ссылок пользователя",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )
    
    @admin_required
    @whitelist_required
    def cmd_menu(self, message: Message):
        """Команда /menu - главное меню администратора"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            chat_id = message.chat.id
            chat_type = message.chat.type
            
            # ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
            logger.info(f"🔍 DEBUG cmd_menu: user={user_id}, chat={chat_id}, type={chat_type}, thread={thread_id}")
            
            log_admin_action(logger, user_id, "открыл главное меню")
            
            # Получаем MenuHandler из main.py через ссылку
            menu_handler = getattr(self.bot, '_menu_handler', None)
            if menu_handler:
                logger.info(f"🔍 DEBUG передаем в menu_handler.cmd_menu для chat_id={chat_id}")
                menu_handler.cmd_menu(message)
            else:
                # Fallback - простое меню
                self.bot.send_message(
                    message.chat.id,
                    "🎵 <b>Do Presave Reminder Bot v25+</b>\n\n"
                    "📱 Главное меню временно недоступно.\n"
                    "Попробуйте /resetmenu",
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
        
    @admin_required
    @whitelist_required
    def cmd_resetmenu(self, message: Message):
        """Команда /resetmenu - сброс меню"""
        # Определяем thread_id СРАЗУ, до try блока
        thread_id = getattr(message, 'message_thread_id', None)
        
        try:
            user_id = message.from_user.id
            chat_id = message.chat.id
            chat_type = message.chat.type
            
            # ОТЛАДОЧНОЕ ЛОГИРОВАНИЕ
            logger.info(f"🔍 DEBUG cmd_resetmenu: user={user_id}, chat={chat_id}, type={chat_type}, thread={thread_id}")
            
            log_admin_action(logger, user_id, "сбросил меню")
             
            # Получаем MenuHandler из main.py через ссылку
            menu_handler = getattr(self.bot, '_menu_handler', None)
            if menu_handler:
                logger.info(f"🔍 DEBUG передаем в menu_handler.cmd_resetmenu для chat_id={chat_id}")
                menu_handler.cmd_resetmenu(message)
            else:
                # Fallback - простой сброс
                self.bot.send_message(
                    message.chat.id,
                    "🔄 <b>Меню сброшено!</b>\n\n"
                    "Восстановление функционала...\n"
                    "Попробуйте снова /menu",
                    parse_mode='HTML',
                    message_thread_id=thread_id
                )
                    
        except Exception as e:
            logger.error(f"❌ Ошибка cmd_resetmenu: {e}")
            self.bot.send_message(
                message.chat.id,
                "❌ Ошибка сброса меню. Обратитесь к разработчику.",
                message_thread_id=getattr(message, 'message_thread_id', None)
            )

    # ============================================
    # ПЛАН 2: КОМАНДЫ КАРМЫ (ЗАГЛУШКИ)
    # ============================================
    
    # @admin_required
    # def cmd_karma(self, message: Message):
    #     """Команда /karma @username +/-число"""
    #     # Определяем thread_id СРАЗУ, до try блока
    #     thread_id = getattr(message, 'message_thread_id', None)
    #     
    #     try:
    #         user_id = message.from_user.id
    #         args = extract_command_args(message)
    #         
    #         if len(args) < 2:
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 "❌ <b>Неверный формат команды!</b>\n\n"
    #                 "📝 <b>Правильный формат:</b>\n"
    #                 "<code>/karma @username +/-число</code>\n\n"
    #                 "💡 <b>Примеры:</b>\n"
    #                 "<code>/karma @testuser +5</code>\n"
    #                 "<code>/karma @testuser -2</code>",
    #                 parse_mode='HTML',
    #                 message_thread_id=thread_id
    #             )
    #             return
    #         
    #         target_username = args[0].lstrip('@')
    #         karma_change_str = args[1]
    #         
    #         # Валидация изменения кармы
    #         karma_change = self.security.validate_karma_amount(karma_change_str)
    #         if karma_change is None:
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 "❌ Неверное количество кармы! Используйте числа от -1000 до +1000.",
    #                 message_thread_id=thread_id
    #             )
    #             return
    #         
    #         # Получаем пользователя
    #         target_user = self.db.get_user_by_username(target_username)
    #         if not target_user:
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 f"❌ Пользователь @{target_username} не найден в базе данных.",
    #                 message_thread_id=thread_id
    #             )
    #             return
    #         
    #         # Обновляем карму
    #         old_karma = self.db.get_user_karma(target_user.user_id)
    #         new_karma = max(0, min(old_karma + karma_change, int(os.getenv('MAX_KARMA', '100500'))))
    #         
    #         success = self.db.update_karma(target_user.user_id, new_karma, user_id, 
    #                                       f"Ручное изменение админом")
    #         
    #         if success:
    #             change_emoji = "📈" if karma_change > 0 else "📉"
    #             change_str = f"+{karma_change}" if karma_change > 0 else str(karma_change)
    #             
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 f"{change_emoji} <b>Карма изменена!</b>\n\n"
    #                 f"👤 <b>Пользователь:</b> @{target_username}\n"
    #                 f"🔄 <b>Изменение:</b> {change_str}\n"
    #                 f"🏆 <b>Было:</b> {old_karma} → <b>Стало:</b> {new_karma}\n"
    #                 f"🎖️ <b>Звание:</b> {self.db.get_user_rank(target_user.user_id)}",
    #                 parse_mode='HTML',
    #                 message_thread_id=thread_id
    #             )
    #             
    #             log_admin_action(logger, user_id, f"изменил карму @{target_username}: {old_karma}→{new_karma}")
    #         else:
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 "❌ Ошибка при изменении кармы",
    #                 message_thread_id=thread_id
    #             )
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка cmd_karma: {e}")
    #         self.bot.send_message(
    #             message.chat.id,
    #             "❌ Ошибка при выполнении команды /karma",
    #             message_thread_id=getattr(message, 'message_thread_id', None)
    #         )
    
    # ============================================
    # ПЛАН 3: КОМАНДЫ ИИ И ФОРМ (ЗАГЛУШКИ)
    # ============================================
    
    # @admin_required  
    # def cmd_askpresave(self, message: Message):
    #     """Команда /askpresave - интерактивная форма пресейва"""
    #     # Определяем thread_id СРАЗУ, до try блока
    #     thread_id = getattr(message, 'message_thread_id', None)
    #     
    #     try:
    #         # Запуск интерактивной формы для пресейва
    #         from services.forms import FormManager
    #         form_manager = FormManager(self.db, None)  # Передаем config
    #         form_manager.start_presave_request(message.from_user.id, message.chat.id)
    #         
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка cmd_askpresave: {e}")
    #         self.bot.send_message(
    #             message.chat.id,
    #             "❌ Ошибка при запуске формы пресейва",
    #             message_thread_id=getattr(message, 'message_thread_id', None)
    #         )
    
    # ============================================
    # ПЛАН 4: КОМАНДЫ BACKUP (ЗАГЛУШКИ)
    # ============================================
    
    # @admin_required
    # def cmd_downloadsql(self, message: Message):
    #     """Команда /downloadsql - создание backup БД"""
    #     # Определяем thread_id СРАЗУ, до try блока
    #     thread_id = getattr(message, 'message_thread_id', None)
    #     
    #     try:
    #         # Проверяем что это личка
    #         if message.chat.type != 'private':
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 "❌ Команда /downloadsql доступна только в личных сообщениях боту!",
    #                 message_thread_id=thread_id
    #             )
    #             return
    #         
    #         from services.backup_restore import BackupRestoreManager
    #         backup_manager = BackupRestoreManager(self.db, None)  # Передаем config
    #         
    #         # Создаем backup
    #         backup_file, filename = backup_manager.export_full_database()
    #         
    #         # Отправляем файл
    #         self.bot.send_document(
    #             message.chat.id,
    #             backup_file,
    #             visible_file_name=filename,
    #             caption="💾 Backup базы данных создан успешно!"
    #         )
    #         
    #         log_admin_action(logger, message.from_user.id, f"создал backup БД: {filename}")
    #         
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка cmd_downloadsql: {e}")
    #         self.bot.send_message(
    #             message.chat.id,
    #             "❌ Ошибка при создании backup",
    #             message_thread_id=getattr(message, 'message_thread_id', None)
    #         )


if __name__ == "__main__":
    """Тестирование CommandHandler"""
    print("🧪 Тестирование CommandHandler...")
    
    # Тестирование извлечения аргументов
    test_message = type('TestMessage', (), {
        'text': '/karma @testuser +5',
        'from_user': type('User', (), {'id': 12345})()
    })()
    
    args = extract_command_args(test_message)
    print(f"Аргументы команды '/karma @testuser +5': {args}")
    
    print("✅ Тестирование CommandHandler завершено!")
