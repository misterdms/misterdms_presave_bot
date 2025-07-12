"""
🔧 Helper Functions - Do Presave Reminder Bot v25+
Вспомогательные функции для форматирования, клавиатур и общих операций
"""

import re
import math
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Union
from urllib.parse import urlparse
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import config
from database.models import User, UserKarma, UserRank, Link
from utils.logger import get_logger

logger = get_logger(__name__)

# ============================================
# ФОРМАТИРОВАНИЕ СООБЩЕНИЙ
# ============================================

class MessageFormatter:
    """Класс для форматирования сообщений с эмодзи"""
    
    # Эмодзи для разных типов сообщений
    EMOJIS = {
        # Основные действия
        'menu': '🎛️',
        'back': '🔙',
        'home': '🏠',
        'info': 'ℹ️',
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'loading': '🔄',
        
        # Статистика и аналитика
        'stats': '📊',
        'user': '👤',
        'admin': '👑',
        'leaderboard': '🏆',
        'rank': '🎖️',
        'progress': '📈',
        
        # Карма и звания
        'karma': '🏆',
        'newbie': '🥉',
        'hope': '🥈', 
        'mega': '🥇',
        'ambassador': '💎',
        'plus_karma': '⬆️',
        'minus_karma': '⬇️',
        
        # Ссылки и пресейвы
        'link': '🔗',
        'presave': '🎵',
        'music': '🎶',
        'spotify': '🎵',
        'apple_music': '🍎',
        'youtube': '📺',
        
        # Формы и заявки
        'form': '📝',
        'claim': '✅',
        'screenshot': '📸',
        'pending': '⏳',
        'approved': '✅',
        'rejected': '❌',
        
        # ИИ и автоматизация
        'ai': '🤖',
        'auto': '⚡',
        'gratitude': '🙏',
        'thank_you': '💖',
        
        # Backup и техническое
        'backup': '💾',
        'database': '🗃️',
        'system': '⚙️',
        'health': '💊',
        'time': '⏰',
        
        # Навигация
        'next': '▶️',
        'prev': '◀️',
        'up': '⬆️',
        'down': '⬇️',
        'refresh': '🔄'
    }
    
    @classmethod
    def get_emoji(cls, key: str) -> str:
        """Получение эмодзи по ключу"""
        return cls.EMOJIS.get(key, '📝')
    
    @classmethod
    def format_user_mention(cls, user: User, include_emoji: bool = True) -> str:
        """Форматирование упоминания пользователя"""
        emoji = cls.get_emoji('admin' if user.is_admin else 'user') if include_emoji else ''
        
        if user.username:
            return f"{emoji} @{user.username}"
        else:
            name = user.first_name or "Пользователь"
            if user.last_name:
                name += f" {user.last_name}"
            return f"{emoji} {name}"
    
    @classmethod
    def format_karma_info(cls, karma_record: UserKarma, show_progress: bool = True) -> str:
        """Форматирование информации о карме"""
        if not karma_record:
            return f"{cls.get_emoji('newbie')} Новенький (0 кармы)"
        
        # Основная информация
        rank_emoji = {
            UserRank.NEWBIE: cls.get_emoji('newbie'),
            UserRank.HOPE: cls.get_emoji('hope'),
            UserRank.MEGA: cls.get_emoji('mega'),
            UserRank.AMBASSADOR: cls.get_emoji('ambassador')
        }.get(karma_record.rank, cls.get_emoji('karma'))
        
        result = f"{rank_emoji} {karma_record.rank.value} ({karma_record.karma_points} кармы)"
        
        # Прогресс до следующего уровня
        if show_progress and karma_record.rank != UserRank.AMBASSADOR:
            from database.models import get_karma_threshold_for_next_rank
            next_threshold = get_karma_threshold_for_next_rank(karma_record.karma_points)
            
            if next_threshold:
                progress_bar = cls.create_progress_bar(
                    karma_record.karma_points, 
                    next_threshold,
                    length=10
                )
                remaining = next_threshold - karma_record.karma_points
                result += f"\n📈 До следующего уровня: {progress_bar} {remaining} кармы"
        
        return result
    
    @classmethod
    def create_progress_bar(cls, current: int, total: int, length: int = 10, 
                           filled_char: str = '█', empty_char: str = '░') -> str:
        """Создание прогресс-бара"""
        if total <= 0:
            return empty_char * length
            
        filled_length = int(length * current / total)
        filled_length = min(filled_length, length)  # Не больше максимума
        
        bar = filled_char * filled_length + empty_char * (length - filled_length)
        percentage = min(int(100 * current / total), 100)
        
        return f"{bar} {percentage}%"
    
    @classmethod
    def format_time_ago(cls, dt: datetime) -> str:
        """Форматирование времени "назад" """
        if not dt:
            return "никогда"
            
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} дн. назад"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} ч. назад"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} мин. назад"
        else:
            return "только что"
    
    @classmethod
    def format_file_size(cls, size_bytes: int) -> str:
        """Форматирование размера файла"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        
        return f"{s} {size_names[i]}"
    
    @classmethod
    def format_number(cls, number: int) -> str:
        """Форматирование чисел с разделителями"""
        if number >= 1000000:
            return f"{number/1000000:.1f}M"
        elif number >= 1000:
            return f"{number/1000:.1f}K"
        else:
            return str(number)
    
    @classmethod
    def truncate_text(cls, text: str, max_length: int = 50) -> str:
        """Обрезка текста с многоточием"""
        if len(text) <= max_length:
            return text
        return text[:max_length-3] + "..."
    
    @classmethod
    def format_url_domain(cls, url: str) -> str:
        """Извлечение и форматирование домена из URL"""
        try:
            domain = urlparse(url).netloc.lower()
            
            # Убираем www.
            if domain.startswith('www.'):
                domain = domain[4:]
                
            # Красивые названия для популярных сервисов
            domain_mapping = {
                'spotify.com': '🎵 Spotify',
                'music.apple.com': '🍎 Apple Music',
                'music.youtube.com': '📺 YouTube Music',
                'soundcloud.com': '🔊 SoundCloud',
                'bandcamp.com': '🎸 Bandcamp',
                'deezer.com': '🎧 Deezer',
                'tidal.com': '🌊 Tidal',
                'music.amazon.com': '📦 Amazon Music',
                'linktr.ee': '🔗 Linktree',
                'fanlink.to': '🔗 FanLink',
                'smarturl.it': '🔗 SmartURL',
                'ffm.to': '🔗 Feature.fm'
            }
            
            return domain_mapping.get(domain, f"🔗 {domain}")
            
        except:
            return "🔗 Ссылка"

# ============================================
# СОЗДАНИЕ КЛАВИАТУР
# ============================================

class KeyboardBuilder:
    """Класс для создания клавиатур Telegram"""
    
    @staticmethod
    def create_inline_keyboard(buttons: List[List[Dict[str, str]]], 
                             row_width: int = 2) -> InlineKeyboardMarkup:
        """Создание inline клавиатуры из списка кнопок"""
        keyboard = InlineKeyboardMarkup(row_width=row_width)
        
        for row in buttons:
            button_row = []
            for button in row:
                btn = InlineKeyboardButton(
                    text=button['text'],
                    callback_data=button.get('callback_data'),
                    url=button.get('url'),
                    switch_inline_query=button.get('switch_inline_query'),
                    switch_inline_query_current_chat=button.get('switch_inline_query_current_chat')
                )
                button_row.append(btn)
            keyboard.row(*button_row)
        
        return keyboard
    
    @staticmethod
    def create_main_menu_keyboard() -> InlineKeyboardMarkup:
        """Создание главного меню (План 1)"""
        buttons = [
            [{'text': f"{MessageFormatter.get_emoji('stats')} Моя статистика", 'callback_data': 'menu_mystat'}],
            [{'text': f"{MessageFormatter.get_emoji('leaderboard')} Лидерборд Топ-10", 'callback_data': 'menu_leaderboard'}],
            [{'text': f"{MessageFormatter.get_emoji('form')} Действия", 'callback_data': 'menu_actions'}],
            [{'text': f"{MessageFormatter.get_emoji('stats')} Расширенная аналитика", 'callback_data': 'menu_analytics'}],
            [{'text': f"{MessageFormatter.get_emoji('system')} Диагностика", 'callback_data': 'menu_diagnostics'}],
            [{'text': f"{MessageFormatter.get_emoji('info')} Команды и описание", 'callback_data': 'menu_help'}]
        ]
        
        # Добавляем разделы для включенных планов
        if config.ENABLE_PLAN_3_FEATURES:
            ai_button = [{'text': f"{MessageFormatter.get_emoji('ai')} ИИ и автоматизация", 'callback_data': 'menu_ai'}]
            buttons.insert(-2, ai_button)  # Вставляем перед диагностикой
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
    
    @staticmethod
    def create_leaderboard_keyboard() -> InlineKeyboardMarkup:
        """Создание меню лидербордов (План 2)"""
        buttons = [
            [{'text': f"{MessageFormatter.get_emoji('presave')} По просьбам о пресейвах", 'callback_data': 'leaderboard_requests'}],
            [{'text': f"{MessageFormatter.get_emoji('karma')} По карме", 'callback_data': 'leaderboard_karma'}],
            [{'text': f"{MessageFormatter.get_emoji('progress')} По соотношению Просьба-Карма", 'callback_data': 'leaderboard_ratio'}],
            [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': 'menu_main'}]
        ]
        
        # Если План 2 не включен, показываем "в разработке"
        if not config.ENABLE_PLAN_2_FEATURES:
            buttons = [
                [{'text': f"{MessageFormatter.get_emoji('loading')} Лидерборды в разработке", 'callback_data': 'under_development'}],
                [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': 'menu_main'}]
            ]
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
    
    @staticmethod
    def create_actions_keyboard() -> InlineKeyboardMarkup:
        """Создание меню действий"""
        buttons = []
        
        # Интерактивные формы (План 3)
        if config.ENABLE_PLAN_3_FEATURES:
            buttons.extend([
                [{'text': f"{MessageFormatter.get_emoji('presave')} Попросить о пресейве", 'callback_data': 'action_ask_presave'}],
                [{'text': f"{MessageFormatter.get_emoji('claim')} Заявить о совершенном пресейве", 'callback_data': 'action_claim_presave'}],
                [{'text': f"{MessageFormatter.get_emoji('pending')} Проверить заявки на аппрувы", 'callback_data': 'action_check_approvals'}]
            ])
        else:
            buttons.extend([
                [{'text': f"{MessageFormatter.get_emoji('loading')} Попросить о пресейве (в разработке)", 'callback_data': 'under_development'}],
                [{'text': f"{MessageFormatter.get_emoji('loading')} Заявить о пресейве (в разработке)", 'callback_data': 'under_development'}],
                [{'text': f"{MessageFormatter.get_emoji('loading')} Проверить заявки (в разработке)", 'callback_data': 'under_development'}]
            ])
        
        # Основные действия (План 1)
        buttons.extend([
            [{'text': f"{MessageFormatter.get_emoji('link')} Последние 30 ссылок", 'callback_data': 'action_last30_links'}],
            [{'text': f"{MessageFormatter.get_emoji('link')} Последние 10 ссылок", 'callback_data': 'action_last10_links'}],
            [{'text': f"{MessageFormatter.get_emoji('system')} Настройки бота", 'callback_data': 'menu_settings'}],
            [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': 'menu_main'}]
        ])
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
    
    @staticmethod
    def create_settings_keyboard() -> InlineKeyboardMarkup:
        """Создание меню настроек"""
        buttons = [
            [{'text': f"{MessageFormatter.get_emoji('system')} Режимы лимитов", 'callback_data': 'settings_limits'}],
            [{'text': f"{MessageFormatter.get_emoji('refresh')} Перезагрузить режимы", 'callback_data': 'settings_reload_modes'}],
            [{'text': f"{MessageFormatter.get_emoji('success')} Активировать бота", 'callback_data': 'settings_enable_bot'}],
            [{'text': f"{MessageFormatter.get_emoji('error')} Деактивировать бота", 'callback_data': 'settings_disable_bot'}],
        ]
        
        # Настройки для включенных планов
        if config.ENABLE_PLAN_3_FEATURES:
            buttons.append([{'text': f"{MessageFormatter.get_emoji('form')} Изменить напоминание", 'callback_data': 'settings_edit_reminder'}])
            buttons.append([{'text': f"{MessageFormatter.get_emoji('error')} Очистить заявки на аппрувы", 'callback_data': 'settings_clear_approvals'}])
            buttons.append([{'text': f"{MessageFormatter.get_emoji('error')} Очистить историю просьб", 'callback_data': 'settings_clear_asks'}])
        
        buttons.extend([
            [{'text': f"{MessageFormatter.get_emoji('error')} Очистить историю ссылок", 'callback_data': 'settings_clear_links'}],
            [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': 'menu_actions'}]
        ])
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
    
    @staticmethod
    def create_limits_keyboard() -> InlineKeyboardMarkup:
        """Создание меню режимов лимитов"""
        buttons = [
            [{'text': f"{MessageFormatter.get_emoji('down')} Conservative", 'callback_data': 'limits_conservative'}],
            [{'text': f"{MessageFormatter.get_emoji('user')} Normal", 'callback_data': 'limits_normal'}],
            [{'text': f"{MessageFormatter.get_emoji('up')} Burst (по умолчанию)", 'callback_data': 'limits_burst'}],
            [{'text': f"{MessageFormatter.get_emoji('admin')} Admin Burst", 'callback_data': 'limits_admin_burst'}],
            [{'text': f"{MessageFormatter.get_emoji('info')} Текущий режим", 'callback_data': 'limits_current'}],
            [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': 'menu_settings'}]
        ]
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
    
    @staticmethod
    def create_back_button(callback_data: str = 'menu_main') -> InlineKeyboardMarkup:
        """Создание простой кнопки "Назад" """
        buttons = [
            [{'text': f"{MessageFormatter.get_emoji('back')} Назад", 'callback_data': callback_data}]
        ]
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=1)
    
    @staticmethod
    def create_pagination_keyboard(current_page: int, total_pages: int, 
                                  callback_prefix: str) -> InlineKeyboardMarkup:
        """Создание клавиатуры с пагинацией"""
        buttons = []
        
        # Кнопки навигации
        nav_buttons = []
        if current_page > 1:
            nav_buttons.append({
                'text': f"{MessageFormatter.get_emoji('prev')} Пред.",
                'callback_data': f"{callback_prefix}_page_{current_page - 1}"
            })
        
        nav_buttons.append({
            'text': f"{current_page}/{total_pages}",
            'callback_data': f"{callback_prefix}_page_info"
        })
        
        if current_page < total_pages:
            nav_buttons.append({
                'text': f"След. {MessageFormatter.get_emoji('next')}",
                'callback_data': f"{callback_prefix}_page_{current_page + 1}"
            })
        
        buttons.append(nav_buttons)
        
        # Кнопка назад
        buttons.append([{
            'text': f"{MessageFormatter.get_emoji('back')} Назад",
            'callback_data': 'menu_main'
        }])
        
        return KeyboardBuilder.create_inline_keyboard(buttons, row_width=3)

# ============================================
# ПАРСИНГ И ОБРАБОТКА КОМАНД
# ============================================

class CommandParser:
    """Класс для парсинга команд и их аргументов"""
    
    @staticmethod
    def parse_karma_command(text: str) -> Optional[Tuple[str, int]]:
        """Парсинг команды /karma @username +/-число"""
        # Паттерн: /karma @username +5 или /karma @username -3
        pattern = r'/karma\s+@?(\w+)\s+([\+\-]?\d+)'
        match = re.match(pattern, text.strip())
        
        if match:
            username = match.group(1)
            try:
                karma_change = int(match.group(2))
                return username, karma_change
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def parse_ratio_command(text: str) -> Optional[Tuple[str, int, int]]:
        """Парсинг команды /ratiostat @username 15:12"""
        # Паттерн: /ratiostat @username 15:12 или 15-12
        pattern = r'/ratiostat\s+@?(\w+)\s+(\d+)[:\-/](\d+)'
        match = re.match(pattern, text.strip())
        
        if match:
            username = match.group(1)
            try:
                requests = int(match.group(2))
                karma = int(match.group(3))
                return username, requests, karma
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def parse_user_query(text: str) -> Optional[str]:
        """Парсинг команд с @username"""
        # Паттерны для команд типа /linksby @username
        patterns = [
            r'/\w+\s+@?(\w+)',  # /linksby @username
            r'@(\w+)',          # просто @username
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.strip())
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def extract_links_from_text(text: str) -> List[str]:
        """Извлечение всех ссылок из текста"""
        # Паттерн для URL
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        
        return re.findall(url_pattern, text)
    
    @staticmethod
    def is_mention_bot(text: str, bot_username: str) -> bool:
        """Проверка упоминается ли бот в сообщении"""
        if not text or not bot_username:
            return False
        
        # Убираем @ если есть
        bot_username = bot_username.lstrip('@')
        
        # Ищем упоминание
        pattern = rf'@{re.escape(bot_username)}'
        return bool(re.search(pattern, text, re.IGNORECASE))

# ============================================
# РАБОТА С ПОЛЬЗОВАТЕЛЯМИ И ДАННЫМИ
# ============================================

class UserHelper:
    """Помощник для работы с пользователями"""
    
    @staticmethod
    def get_user_display_name(user: User) -> str:
        """Получение отображаемого имени пользователя"""
        if user.username:
            return f"@{user.username}"
        
        name_parts = []
        if user.first_name:
            name_parts.append(user.first_name)
        if user.last_name:
            name_parts.append(user.last_name)
        
        return " ".join(name_parts) if name_parts else f"Пользователь #{user.telegram_id}"
    
    @staticmethod
    def is_user_admin(user_id: int) -> bool:
        """Проверка является ли пользователь админом"""
        return user_id in config.ADMIN_IDS
    
    @staticmethod
    def format_user_stats_message(stats: Dict[str, Any]) -> str:
        """Форматирование сообщения со статистикой пользователя"""
        if not stats.get('user_info'):
            return f"{MessageFormatter.get_emoji('error')} Пользователь не найден"
        
        user_info = stats['user_info']
        
        # Заголовок
        emoji = MessageFormatter.get_emoji('admin' if user_info['is_admin'] else 'user')
        username = user_info['username'] or 'без username'
        result = f"{emoji} **Статистика пользователя @{username}**\n\n"
        
        # Основные метрики
        result += f"{MessageFormatter.get_emoji('link')} **Ссылок опубликовано:** {stats['links_count']}\n"
        
        # Карма (План 2)
        if stats.get('karma_info'):
            karma_info = stats['karma_info']
            result += f"{MessageFormatter.get_emoji('karma')} **Карма:** {karma_info['karma_points']}\n"
            result += f"{MessageFormatter.get_emoji('rank')} **Звание:** {karma_info['rank']}\n"
            
            if karma_info['progress_to_next']:
                progress_bar = MessageFormatter.create_progress_bar(
                    karma_info['karma_points'],
                    karma_info['next_rank_threshold'] or karma_info['karma_points']
                )
                result += f"{MessageFormatter.get_emoji('progress')} **Прогресс:** {progress_bar}\n"
        
        # Активность по топикам
        if stats.get('message_stats'):
            result += f"\n{MessageFormatter.get_emoji('stats')} **Активность по топикам:**\n"
            for thread_id, thread_stats in stats['message_stats'].items():
                result += f"• Топик {thread_id}: {thread_stats['message_count']} сообщений\n"
        
        # ИИ взаимодействия (План 3)
        if stats.get('ai_interactions', 0) > 0:
            result += f"{MessageFormatter.get_emoji('ai')} **ИИ взаимодействий:** {stats['ai_interactions']}\n"
        
        # Время регистрации
        if user_info.get('created_at'):
            created_time = MessageFormatter.format_time_ago(user_info['created_at'])
            result += f"\n{MessageFormatter.get_emoji('time')} **Зарегистрирован:** {created_time}\n"
        
        return result

class DataHelper:
    """Помощник для работы с данными"""
    
    @staticmethod
    def format_links_list(links: List[Link], max_links: int = 10) -> str:
        """Форматирование списка ссылок"""
        if not links:
            return f"{MessageFormatter.get_emoji('info')} Ссылки не найдены"
        
        result = f"{MessageFormatter.get_emoji('link')} **Последние ссылки:**\n\n"
        
        for i, link in enumerate(links[:max_links], 1):
            # Форматируем домен
            domain = MessageFormatter.format_url_domain(link.url)
            
            # Время публикации
            time_ago = MessageFormatter.format_time_ago(link.created_at)
            
            # Автор (если есть связь с пользователем)
            author = ""
            if hasattr(link, 'user') and link.user:
                author = f" от {UserHelper.get_user_display_name(link.user)}"
            
            result += f"{i}. {domain}{author} ({time_ago})\n"
        
        if len(links) > max_links:
            result += f"\n... и ещё {len(links) - max_links} ссылок"
        
        return result
    
    @staticmethod
    def format_leaderboard(data: List[Tuple], leaderboard_type: str) -> str:
        """Форматирование лидерборда"""
        if not data:
            return f"{MessageFormatter.get_emoji('info')} Данные для рейтинга отсутствуют"
        
        # Заголовки для разных типов
        headers = {
            'karma': f"{MessageFormatter.get_emoji('karma')} **Топ по карме:**",
            'requests': f"{MessageFormatter.get_emoji('presave')} **Топ по просьбам о пресейвах:**",
            'ratio': f"{MessageFormatter.get_emoji('progress')} **Топ по соотношению:**"
        }
        
        result = headers.get(leaderboard_type, f"{MessageFormatter.get_emoji('leaderboard')} **Рейтинг:**")
        result += "\n\n"
        
        # Эмодзи для позиций
        position_emojis = ['🥇', '🥈', '🥉'] + ['🏅'] * 7
        
        for i, item in enumerate(data, 1):
            emoji = position_emojis[i-1] if i <= len(position_emojis) else '📍'
            
            if leaderboard_type == 'karma' and len(item) >= 2:
                user, karma_record = item
                username = UserHelper.get_user_display_name(user)
                value = f"{karma_record.karma_points} кармы"
                rank = karma_record.rank.value
                result += f"{emoji} {i}. {username} - {value} ({rank})\n"
                
            elif leaderboard_type == 'requests' and len(item) >= 2:
                user, count = item
                username = UserHelper.get_user_display_name(user)
                result += f"{emoji} {i}. {username} - {count} просьб\n"
                
            else:
                # Общий формат
                result += f"{emoji} {i}. {item}\n"
        
        return result
    
    @staticmethod
    def validate_and_clean_data(data: Any, data_type: str) -> Any:
        """Валидация и очистка данных"""
        if data_type == 'username':
            if isinstance(data, str):
                return data.lstrip('@').strip()
        elif data_type == 'karma_change':
            if isinstance(data, (int, str)):
                try:
                    change = int(data)
                    return max(-50, min(50, change))  # Ограничиваем диапазон
                except ValueError:
                    pass
        elif data_type == 'url':
            if isinstance(data, str) and data.startswith(('http://', 'https://')):
                return data.strip()
        
        return None

# ============================================
# РАБОТА С ФАЙЛАМИ И МЕДИА
# ============================================

class FileHelper:
    """Помощник для работы с файлами"""
    
    @staticmethod
    def is_image_file(file_type: Optional[str]) -> bool:
        """Проверка является ли файл изображением"""
        if not file_type:
            return False
        
        image_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        return file_type.lower() in image_types
    
    @staticmethod
    def generate_safe_filename(original_name: str, max_length: int = 100) -> str:
        """Генерация безопасного имени файла"""
        if not original_name:
            return f"file_{int(datetime.now().timestamp())}"
        
        # Убираем опасные символы
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', original_name)
        
        # Ограничиваем длину
        if len(safe_name) > max_length:
            name_part, ext = safe_name.rsplit('.', 1) if '.' in safe_name else (safe_name, '')
            safe_name = name_part[:max_length-len(ext)-1] + '.' + ext if ext else name_part[:max_length]
        
        return safe_name

# ============================================
# УТИЛИТЫ КОНФИГУРАЦИИ
# ============================================

class ConfigHelper:
    """Помощник для работы с конфигурацией"""
    
    @staticmethod
    def get_current_limit_mode() -> str:
        """Получение текущего режима лимитов"""
        from database.manager import get_database_manager
        
        try:
            db = get_database_manager()
            mode = db.get_setting('current_limit_mode')
            return mode or config.DEFAULT_LIMIT_MODE
        except:
            return config.DEFAULT_LIMIT_MODE
    
    @staticmethod
    def format_limit_mode_info(mode: str) -> str:
        """Форматирование информации о режиме лимитов"""
        limit_config = config.get_limit_config(mode)
        
        mode_descriptions = {
            'CONSERVATIVE': 'Консервативный - минимальная нагрузка на API',
            'NORMAL': 'Обычный - сбалансированный режим',
            'BURST': 'Burst - повышенная производительность (по умолчанию)',
            'ADMIN_BURST': 'Admin Burst - максимальная производительность для админов'
        }
        
        description = mode_descriptions.get(mode, 'Неизвестный режим')
        
        return f"{MessageFormatter.get_emoji('system')} **Режим:** {mode}\n" \
               f"{MessageFormatter.get_emoji('info')} **Описание:** {description}\n" \
               f"{MessageFormatter.get_emoji('stats')} **Лимит:** {limit_config['max_hour']} запросов/час\n" \
               f"{MessageFormatter.get_emoji('time')} **Cooldown:** {limit_config['cooldown']} сек"
    
    @staticmethod
    def is_bot_enabled() -> bool:
        """Проверка включен ли бот"""
        from database.manager import get_database_manager
        
        try:
            db = get_database_manager()
            enabled = db.get_setting('bot_enabled')
            return enabled == 'true' if enabled else True
        except:
            return True

# ============================================
# СИСТЕМНЫЙ МОНИТОР (ЗАГЛУШКА ДЛЯ ПЛАН 1)
# ============================================

class SystemMonitor:
    """Заглушка системного монитора для Plan 1"""
    
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
    
    def get_system_info(self):
        """Получение базовой информации о системе"""
        return {
            'status': 'ok',
            'uptime': (datetime.now(timezone.utc) - self.start_time).total_seconds(),
            'memory_usage': 0,
            'cpu_usage': 0
        }
    
    def is_healthy(self):
        """Проверка здоровья системы"""
        return True

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = [
    # Основные классы
    'MessageFormatter', 'KeyboardBuilder', 'CommandParser', 
    'UserHelper', 'DataHelper', 'FileHelper', 'ConfigHelper'
]

if __name__ == "__main__":
    # Тестирование вспомогательных функций
    print("🧪 Тестирование Helper Functions...")
    
    # Тест форматирования
    progress_bar = MessageFormatter.create_progress_bar(25, 50, 10)
    print(f"✅ Прогресс-бар: {progress_bar}")
    
    # Тест парсинга команд
    karma_result = CommandParser.parse_karma_command("/karma @testuser +5")
    print(f"✅ Парсинг кармы: {karma_result}")
    
    # Тест извлечения ссылок
    links = CommandParser.extract_links_from_text("Послушайте https://spotify.com/track/123 и https://music.apple.com/track/456")
    print(f"✅ Извлечение ссылок: {len(links)} найдено")
    
    # Тест форматирования домена
    domain = MessageFormatter.format_url_domain("https://music.apple.com/us/album/test")
    print(f"✅ Форматирование домена: {domain}")
    
    # Тест создания клавиатуры
    keyboard = KeyboardBuilder.create_main_menu_keyboard()
    print(f"✅ Главное меню создано: {len(keyboard.keyboard)} рядов")
    
    print("✅ Все тесты helpers пройдены!")
