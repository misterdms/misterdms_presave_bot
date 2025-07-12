"""
utils/formatters.py - Форматирование данных для Telegram
Функции для красивого отображения статистики, меню, прогресс-баров и другой информации
ПЛАН 1: Базовое форматирование + заглушки для будущих планов
"""

from typing import List, Dict, Optional, Union, Any
from datetime import datetime, timedelta
import re

from utils.logger import get_logger

logger = get_logger(__name__)

class TelegramFormatter:
    """Класс для форматирования сообщений Telegram с эмодзи и markdown"""
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Экранирование специальных символов markdown"""
        if not text:
            return ""
        
        # Символы которые нужно экранировать в Telegram MarkdownV2
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        
        return text
    
    @staticmethod
    def bold(text: str) -> str:
        """Жирный текст"""
        return f"**{text}**"
    
    @staticmethod
    def italic(text: str) -> str:
        """Курсивный текст"""
        return f"*{text}*"
    
    @staticmethod
    def code(text: str) -> str:
        """Моноширинный шрифт"""
        return f"`{text}`"
    
    @staticmethod
    def pre(text: str, language: str = "") -> str:
        """Блок кода"""
        return f"```{language}\n{text}\n```"
    
    @staticmethod
    def link(text: str, url: str) -> str:
        """Ссылка"""
        return f"[{text}]({url})"
    
    @staticmethod
    def mention(text: str, user_id: int) -> str:
        """Упоминание пользователя"""
        return f"[{text}](tg://user?id={user_id})"

class ProgressBarFormatter:
    """Форматирование прогресс-баров для отображения прогресса"""
    
    @staticmethod
    def create_progress_bar(current: int, maximum: int, width: int = 10, 
                          filled_char: str = "▰", empty_char: str = "▱") -> str:
        """Создание текстового прогресс-бара"""
        if maximum <= 0:
            return empty_char * width
        
        # Вычисляем процент заполнения
        percentage = min(current / maximum, 1.0)
        filled_length = int(width * percentage)
        empty_length = width - filled_length
        
        return filled_char * filled_length + empty_char * empty_length
    
    @staticmethod
    def format_karma_progress(current_karma: int, rank_config: Dict) -> str:
        """ЗАГЛУШКА: Форматирование прогресса кармы для званий"""
        # TODO: Реализовать в Плане 2
        logger.debug("🔄 format_karma_progress - в разработке (План 2)")
        
        # Временная заглушка
        progress_bar = ProgressBarFormatter.create_progress_bar(current_karma, 5, 8)
        return f"{progress_bar} {current_karma}/5"
    
    @staticmethod
    def format_backup_countdown(days_left: int, total_days: int = 30) -> str:
        """ЗАГЛУШКА: Форматирование обратного отсчета до backup"""
        # TODO: Реализовать в Плане 4
        logger.debug("🔄 format_backup_countdown - в разработке (План 4)")
        
        if days_left <= 0:
            return "🔴▰▰▰▰▰▰▰▰ ПРОСРОЧЕНО!"
        elif days_left <= 5:
            return f"🔴▰▰▰▰▰▱▱▱ {days_left} дн."
        elif days_left <= 10:
            return f"🟡▰▰▰▰▱▱▱▱ {days_left} дн."
        else:
            return f"🟢▰▰▱▱▱▱▱▱ {days_left} дн."

class StatisticsFormatter:
    """Форматирование статистических данных"""
    
    @staticmethod
    def format_user_stats(stats: Dict) -> str:
        """Форматирование статистики пользователя"""
        try:
            username = stats.get('username', 'unknown')
            first_name = stats.get('first_name', 'Unknown')
            
            # Основная статистика
            result = f"📊 **Статистика пользователя**\n\n"
            result += f"👤 {TelegramFormatter.bold(first_name)} (@{username})\n\n"
            
            # Статистика активности
            result += f"🔗 **Активность:**\n"
            result += f"   • Всего ссылок: {stats.get('total_links', 0)}\n"
            result += f"   • За месяц: {stats.get('links_last_30_days', 0)}\n\n"
            
            # Система кармы (ПЛАН 2)
            karma = stats.get('karma_points', 0)
            rank = stats.get('rank', '🥉 Новенький')
            progress = stats.get('rank_progress', '0/5')
            
            result += f"🏆 **Карма и звание:**\n"
            result += f"   • Карма: {karma} баллов\n"
            result += f"   • Звание: {rank}\n"
            result += f"   • Прогресс: {progress}\n\n"
            
            # ПЛАН 3: Расширенная статистика (ЗАГЛУШКИ)
            if stats.get('presave_requests', 0) > 0 or stats.get('approved_presaves', 0) > 0:
                result += f"🎵 **Пресейвы:**\n"
                result += f"   • Запросов: {stats.get('presave_requests', 0)}\n"
                result += f"   • Одобрено: {stats.get('approved_presaves', 0)}\n"
                result += f"   • ИИ взаимодействий: {stats.get('ai_interactions', 0)}\n\n"
            
            # Даты
            reg_date = stats.get('registered_at')
            last_activity = stats.get('last_activity')
            
            result += f"📅 **Активность:**\n"
            if reg_date:
                result += f"   • Регистрация: {reg_date.strftime('%d.%m.%Y')}\n"
            if last_activity:
                result += f"   • Последняя активность: {last_activity.strftime('%d.%m.%Y %H:%M')}\n"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования статистики пользователя: {e}")
            return "❌ Ошибка отображения статистики"
    
    @staticmethod
    def format_community_stats(stats: Dict) -> str:
        """Форматирование статистики сообщества"""
        try:
            result = f"📊 **Статистика сообщества**\n\n"
            
            # Пользователи
            total_users = stats.get('total_users', 0)
            active_users = stats.get('active_users_30d', 0)
            result += f"👥 **Пользователи:**\n"
            result += f"   • Всего: {total_users}\n"
            result += f"   • Активных (30д): {active_users}\n\n"
            
            # Ссылки
            total_links = stats.get('total_links', 0)
            recent_links = stats.get('links_last_7d', 0)
            result += f"🔗 **Активность:**\n"
            result += f"   • Всего ссылок: {total_links}\n"
            result += f"   • За неделю: {recent_links}\n\n"
            
            # ПЛАН 2: Статистика кармы (ЗАГЛУШКИ)
            avg_karma = stats.get('avg_karma', 0)
            if avg_karma > 0:
                result += f"💎 **Карма:**\n"
                result += f"   • Средняя карма: {avg_karma} баллов\n\n"
            
            # ПЛАН 3: Расширенная аналитика (ЗАГЛУШКИ)
            forms_submitted = stats.get('total_forms_submitted', 0)
            ai_interactions = stats.get('ai_interactions_today', 0)
            if forms_submitted > 0 or ai_interactions > 0:
                result += f"🤖 **Дополнительно:**\n"
                result += f"   • Форм подано: {forms_submitted}\n"
                result += f"   • ИИ запросов сегодня: {ai_interactions}\n\n"
            
            # Время обновления
            updated = stats.get('updated_at')
            if updated:
                result += f"🕒 Обновлено: {updated.strftime('%d.%m.%Y %H:%M')}"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования статистики сообщества: {e}")
            return "❌ Ошибка отображения статистики"
    
    @staticmethod
    def format_links_list(links: List[Dict], title: str = "Последние ссылки") -> str:
        """Форматирование списка ссылок"""
        try:
            if not links:
                return f"📭 {title} - список пуст"
            
            result = f"🔗 **{title}**\n\n"
            
            for i, link in enumerate(links, 1):
                username = link.get('username') or 'unknown'
                first_name = link.get('first_name') or 'Unknown'
                url = link.get('url', '')
                created_at = link.get('created_at')
                
                # Укорачиваем URL если нужно
                display_url = url
                if len(url) > 60:
                    display_url = url[:57] + "..."
                
                result += f"{i}. **@{username}** ({first_name})\n"
                result += f"   🔗 {display_url}\n"
                
                if created_at:
                    result += f"   📅 {created_at.strftime('%d.%m %H:%M')}\n"
                
                result += "\n"
            
            result += f"💡 Показано ссылок: {len(links)}"
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования списка ссылок: {e}")
            return "❌ Ошибка отображения ссылок"

class MenuFormatter:
    """Форматирование меню и кнопок"""
    
    @staticmethod
    def format_main_menu_text() -> str:
        """Текст главного меню"""
        return """
🎛️ **Главное меню администратора**

Выберите раздел для управления ботом:

📊 Статистика и аналитика
🏆 Лидерборд и рейтинги  
⚙️ Действия и управление
📈 Аналитика и отчеты
🔧 Диагностика и настройки

💡 Используйте кнопки ниже для навигации
        """.strip()
    
    @staticmethod
    def format_limit_mode_info(current_mode: str, config: Dict) -> str:
        """Форматирование информации о текущем режиме лимитов"""
        emoji = config.get('emoji', '⚡')
        name = config.get('name', current_mode)
        max_hour = config.get('max_hour', 0)
        cooldown = config.get('cooldown', 0)
        
        result = f"{emoji} **Текущий режим: {name}**\n\n"
        result += f"📊 Параметры:\n"
        result += f"   • Запросов в час: {max_hour}\n"
        result += f"   • Задержка: {cooldown} сек\n\n"
        result += f"💡 Для смены режима используйте команды /setmode_*"
        
        return result
    
    @staticmethod
    def format_help_text() -> str:
        """Форматирование текста помощи /help"""
        return """
🤖 **Do Presave Reminder Bot v25+ - Помощь**

**📱 ОСНОВНЫЕ КОМАНДЫ:**
/start - Приветствие и информация о боте
/help - Эта справка с описанием команд
/menu - Главное меню (только для админов)
/resetmenu - Перезапуск меню при проблемах

**📊 СТАТИСТИКА:**
/mystat - Твоя личная статистика
/last10links - Последние 10 ссылок в чате
/last30links - Последние 30 ссылок в чате

**⚙️ УПРАВЛЕНИЕ ЛИМИТАМИ (только админы):**
/setmode_conservative - Консервативный режим (60/час)
/setmode_normal - Обычный режим (180/час)
/setmode_burst - Быстрый режим (600/час) 🔥
/setmode_adminburst - Админский режим (1200/час)
/currentmode - Текущий режим лимитов

**🔧 УПРАВЛЕНИЕ БОТОМ (только админы):**
/enablebot - Включить бота
/disablebot - Выключить бота

**🏆 СИСТЕМА КАРМЫ (в разработке):**
/karma @username +5 - Начисление кармы (План 2)
/karma @username -2 - Снятие кармы (План 2)
/leaderboard - Топ по карме (План 2)

**🤖 ИИ ФУНКЦИИ (в разработке):**
Упомяните бота @{bot_username} для общения с ИИ (План 3)

**💾 BACKUP (в разработке):**
/downloadsql - Скачать backup БД (План 4)
/backupstatus - Статус backup системы (План 4)

💡 **Автоматические функции:**
• Напоминания о пресейвах при публикации ссылок
• Автоматическое распознавание благодарностей (План 3)
• Система backup каждые 28 дней (План 4)

❓ Возникли вопросы? Обратитесь к администраторам!
        """.strip()

class ErrorFormatter:
    """Форматирование сообщений об ошибках"""
    
    @staticmethod
    def format_error(error_type: str, message: str, user_friendly: bool = True) -> str:
        """Форматирование сообщения об ошибке"""
        if user_friendly:
            friendly_messages = {
                "permission_denied": "❌ У вас нет прав для выполнения этой команды",
                "user_not_found": "❌ Пользователь не найден",
                "invalid_input": "❌ Некорректные данные. Проверьте формат команды",
                "rate_limit": "⏳ Слишком много запросов. Попробуйте позже",
                "database_error": "❌ Временная ошибка базы данных. Попробуйте позже",
                "network_error": "❌ Проблемы с сетью. Попробуйте позже",
                "feature_unavailable": "🔄 Эта функция находится в разработке"
            }
            return friendly_messages.get(error_type, f"❌ {message}")
        else:
            return f"❌ [{error_type}] {message}"
    
    @staticmethod
    def format_validation_error(field: str, expected: str) -> str:
        """Форматирование ошибки валидации"""
        return f"❌ Поле '{field}' должно быть: {expected}"
    
    @staticmethod
    def format_development_message(feature_name: str) -> str:
        """Сообщение о функции в разработке"""
        return f"🔄 {feature_name} находится в разработке. Скоро будет доступно!"

class TimeFormatter:
    """Форматирование времени и дат"""
    
    @staticmethod
    def time_ago(dt: datetime) -> str:
        """Отображение времени в формате 'X времени назад'"""
        now = datetime.utcnow()
        diff = now - dt
        
        if diff.total_seconds() < 60:
            return "только что"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} мин назад"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} ч назад"
        elif diff.days == 1:
            return "вчера"
        elif diff.days < 7:
            return f"{diff.days} дн назад"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks} нед назад"
        else:
            months = diff.days // 30
            return f"{months} мес назад"
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """Форматирование продолжительности в читаемый вид"""
        if seconds < 60:
            return f"{seconds} сек"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} мин"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}ч {minutes}м"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}д {hours}ч"

# ============================================
# ПЛАН 2: ФОРМАТИРОВАНИЕ КАРМЫ (ЗАГЛУШКИ)
# ============================================

class KarmaFormatter:
    """ЗАГЛУШКА: Форматирование системы кармы"""
    
    @staticmethod
    def format_karma_change(user_id: int, old_karma: int, new_karma: int, reason: str) -> str:
        """ЗАГЛУШКА: Форматирование изменения кармы"""
        # TODO: Реализовать в Плане 2
        logger.debug("🔄 format_karma_change - в разработке (План 2)")
        return "🔄 Система кармы в разработке"
    
    @staticmethod
    def format_leaderboard(users: List[Dict]) -> str:
        """ЗАГЛУШКА: Форматирование лидерборда"""
        # TODO: Реализовать в Плане 2
        logger.debug("🔄 format_leaderboard - в разработке (План 2)")
        return "🔄 Лидерборд в разработке"

# ============================================
# ПЛАН 3: ФОРМАТИРОВАНИЕ ИИ (ЗАГЛУШКИ)
# ============================================

class AIFormatter:
    """ЗАГЛУШКА: Форматирование ответов ИИ"""
    
    @staticmethod
    def format_ai_response(response: str, model: str) -> str:
        """ЗАГЛУШКА: Форматирование ответа ИИ"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 format_ai_response - в разработке (План 3)")
        return "🤖 ИИ функции в разработке"
    
    @staticmethod
    def format_form_submission(form_data: Dict) -> str:
        """ЗАГЛУШКА: Форматирование заявки на пресейв"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 format_form_submission - в разработке (План 3)")
        return "📝 Формы в разработке"

# ============================================
# ПЛАН 4: ФОРМАТИРОВАНИЕ BACKUP (ЗАГЛУШКИ)
# ============================================

class BackupFormatter:
    """ЗАГЛУШКА: Форматирование информации о backup"""
    
    @staticmethod
    def format_backup_status(status: Dict) -> str:
        """ЗАГЛУШКА: Форматирование статуса backup"""
        # TODO: Реализовать в Плане 4
        logger.debug("🔄 format_backup_status - в разработке (План 4)")
        return "💾 Backup система в разработке"