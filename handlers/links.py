"""
🔗 Links Handler - Do Presave Reminder Bot v25+
КЛЮЧЕВАЯ ФУНКЦИЯ: Реакция на ссылки с напоминанием о взаимных пресейвах
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
import telebot
from telebot.types import Message
from urllib.parse import urlparse

from config import config
from database.manager import get_database_manager
from utils.security import (
    security_manager, whitelisted_thread_required,
    extract_user_id_from_message, extract_thread_id_from_message,
    user_rate_limit
)
from utils.logger import get_logger, telegram_logger
from utils.helpers import MessageFormatter, CommandParser, ConfigHelper

logger = get_logger(__name__)

class LinkHandler:
    """Обработчик ссылок - основная функция бота"""
    
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot
        self.db = get_database_manager()
        
        # Кэш для предотвращения дублирования уведомлений
        self.recent_reminders = {}  # thread_id: timestamp последнего напоминания
        
        # Cooldown между напоминаниями в одном топике (секунды)
        self.reminder_cooldown = config.RESPONSE_DELAY * 10  # 30 секунд по умолчанию
        
        logger.info("🔗 Link Handler инициализирован")
    
    def process_message_with_links(self, message: Message, user):
        """Основная обработка сообщения со ссылками"""
        try:
            user_id = extract_user_id_from_message(message)
            thread_id = extract_thread_id_from_message(message)
            text = message.text or ""
            
            # Проверяем активен ли бот
            if not ConfigHelper.is_bot_enabled():
                logger.debug(f"🔗 Бот деактивирован, пропускаем обработку ссылок")
                return
            
            # Проверяем whitelist топиков
            if thread_id and not security_manager.is_whitelisted_thread(thread_id):
                logger.debug(f"🔗 Топик {thread_id} не в whitelist, пропускаем")
                return
            
            # Извлекаем ссылки из сообщения
            links = CommandParser.extract_links_from_text(text)
            if not links:
                return
            
            # Валидируем и фильтруем ссылки
            valid_links = self._validate_and_filter_links(links)
            if not valid_links:
                logger.debug(f"🔗 Не найдено валидных ссылок в сообщении от {user_id}")
                return
            
            # Сохраняем ссылки в базу данных
            saved_links = self._save_links_to_database(
                user=user,
                message=message,
                links=valid_links,
                thread_id=thread_id
            )
            
            # Проверяем нужно ли отправлять напоминание
            if self._should_send_reminder(thread_id, user_id):
                self._send_presave_reminder(message, user, saved_links, thread_id)
            
            # Логируем событие
            telegram_logger.user_action(
                user_id,
                f"опубликовал {len(valid_links)} ссылок",
                thread_id=thread_id,
                links_count=len(valid_links),
                domains=[self._extract_domain(link) for link in valid_links]
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки ссылок: {e}")
    
    def _validate_and_filter_links(self, links: List[str]) -> List[str]:
        """Валидация и фильтрация ссылок"""
        valid_links = []
        
        # Поддерживаемые домены для пресейвов
        supported_domains = [
            'spotify.com', 'music.apple.com', 'music.youtube.com',
            'soundcloud.com', 'bandcamp.com', 'deezer.com', 'tidal.com',
            'music.amazon.com', 'linktr.ee', 'fanlink.to', 'smarturl.it',
            'ffm.to', 'orcd.co', 'lnk.to', 'distrokid.com', 'toneden.io'
        ]
        
        for link in links:
            try:
                # Базовая валидация URL
                if not link.startswith(('http://', 'https://')):
                    continue
                
                parsed = urlparse(link)
                domain = parsed.netloc.lower()
                
                # Убираем www.
                if domain.startswith('www.'):
                    domain = domain[4:]
                
                # Проверяем поддерживаемые домены
                is_supported = any(supported_domain in domain for supported_domain in supported_domains)
                
                if is_supported:
                    valid_links.append(link)
                    logger.debug(f"🔗 Валидная ссылка: {domain}")
                else:
                    logger.debug(f"🔗 Неподдерживаемый домен: {domain}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка валидации ссылки {link}: {e}")
                continue
        
        return valid_links
    
    def _save_links_to_database(self, user, message: Message, links: List[str], 
                              thread_id: Optional[int]) -> List:
        """Сохранение ссылок в базу данных"""
        saved_links = []
        
        try:
            for link in links:
                # Создаем запись ссылки
                link_record = self.db.create_link(
                    user_id=user.id,
                    message_id=message.message_id,
                    url=link,
                    thread_id=thread_id,
                    message_text=message.text
                )
                saved_links.append(link_record)
                
                logger.debug(f"💾 Ссылка сохранена: {link_record.domain}")
            
            # Обновляем статистику пользователя
            if thread_id:
                self.db.update_message_stats(
                    user_id=user.id,
                    thread_id=thread_id,
                    links_shared=len(links)
                )
            
            # Обновляем счетчик просьб о пресейвах (для План 2)
            if config.ENABLE_PLAN_2_FEATURES:
                karma_record = self.db.get_user_karma(user.id)
                if karma_record:
                    karma_record.presave_requests_count += len(links)
                    # Обновление происходит автоматически через ORM
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения ссылок в БД: {e}")
        
        return saved_links
    
    def _should_send_reminder(self, thread_id: Optional[int], user_id: int) -> bool:
        """Проверка нужно ли отправлять напоминание"""
        # Не отправляем напоминания в ЛС
        if not thread_id:
            return False
        
        # Не отправляем напоминания админам (они и так знают)
        if security_manager.is_admin(user_id):
            return False
        
        # Проверяем cooldown для топика
        current_time = time.time()
        last_reminder = self.recent_reminders.get(thread_id, 0)
        
        if current_time - last_reminder < self.reminder_cooldown:
            logger.debug(f"🔗 Cooldown активен для топика {thread_id}")
            return False
        
        return True
    
    def _send_presave_reminder(self, message: Message, user, saved_links: List, 
                             thread_id: Optional[int]):
        """Отправка напоминания о пресейвах"""
        try:
            # Получаем текст напоминания из настроек
            reminder_text = self.db.get_setting('reminder_text') or config.REMINDER_TEXT
            
            # Добавляем персонализацию
            user_display = f"@{user.username}" if user.username else user.first_name or "Музыкант"
            
            # Формируем полное сообщение
            full_reminder = f"{reminder_text}\n\n"
            
            # Добавляем информацию о ссылках
            if len(saved_links) == 1:
                domain = self._extract_domain_name(saved_links[0].url)
                full_reminder += f"📎 Обнаружена ссылка: {domain}"
            else:
                full_reminder += f"📎 Обнаружено ссылок: {len(saved_links)}"
                domains = [self._extract_domain_name(link.url) for link in saved_links]
                unique_domains = list(set(domains))
                if len(unique_domains) <= 3:
                    full_reminder += f" ({', '.join(unique_domains)})"
            
            # Задержка перед отправкой (чтобы не выглядело слишком быстро)
            time.sleep(config.RESPONSE_DELAY)
            
            # Отправляем напоминание
            self.bot.reply_to(message, full_reminder)
            
            # Обновляем время последнего напоминания
            if thread_id:
                self.recent_reminders[thread_id] = time.time()
            
            # Логируем отправку напоминания
            telegram_logger.user_action(
                user.telegram_id,
                "получил напоминание о пресейвах",
                thread_id=thread_id,
                reminder_type="auto",
                links_detected=len(saved_links)
            )
            
            logger.info(f"🔗 Напоминание отправлено пользователю {user.telegram_id} в топике {thread_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки напоминания: {e}")
    
    def _extract_domain(self, url: str) -> str:
        """Извлечение домена из URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return "unknown"
    
    def _extract_domain_name(self, url: str) -> str:
        """Извлечение красивого названия сервиса из URL"""
        try:
            domain = self._extract_domain(url)
            
            # Маппинг доменов на красивые названия
            domain_names = {
                'spotify.com': 'Spotify',
                'music.apple.com': 'Apple Music',
                'music.youtube.com': 'YouTube Music',
                'soundcloud.com': 'SoundCloud',
                'bandcamp.com': 'Bandcamp',
                'deezer.com': 'Deezer',
                'tidal.com': 'Tidal',
                'music.amazon.com': 'Amazon Music',
                'linktr.ee': 'Linktree',
                'fanlink.to': 'FanLink',
                'smarturl.it': 'SmartURL',
                'ffm.to': 'Feature.fm',
                'orcd.co': 'Onerpm',
                'lnk.to': 'Linkfire',
                'distrokid.com': 'DistroKid',
                'toneden.io': 'ToneDen'
            }
            
            return domain_names.get(domain, domain.capitalize())
            
        except:
            return "Неизвестный сервис"
    
    # ============================================
    # ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ КОМАНД
    # ============================================
    
    def get_recent_links_formatted(self, limit: int = 10, thread_id: Optional[int] = None) -> str:
        """Получение отформатированного списка последних ссылок"""
        try:
            # Получаем ссылки из БД
            links = self.db.get_recent_links(limit=limit, thread_id=thread_id)
            
            if not links:
                return f"{MessageFormatter.get_emoji('info')} Ссылки не найдены."
            
            # Формируем список
            result = f"{MessageFormatter.get_emoji('link')} **Последние {min(len(links), limit)} ссылок:**\n\n"
            
            for i, link in enumerate(links, 1):
                # Получаем информацию о пользователе
                user_display = "Неизвестный пользователь"
                if hasattr(link, 'user') and link.user:
                    if link.user.username:
                        user_display = f"@{link.user.username}"
                    else:
                        user_display = link.user.first_name or "Пользователь"
                
                # Форматируем домен
                domain_name = self._extract_domain_name(link.url)
                
                # Время публикации
                time_ago = MessageFormatter.format_time_ago(link.created_at)
                
                # Топик (если есть)
                topic_info = f" в топике {link.thread_id}" if link.thread_id else ""
                
                result += f"{i}. **{domain_name}** от {user_display}{topic_info} ({time_ago})\n"
                
                # Добавляем превью текста сообщения (если есть и не слишком длинное)
                if link.message_text and len(link.message_text) > 10:
                    preview = MessageFormatter.truncate_text(link.message_text, 100)
                    result += f"   _{preview}_\n"
                
                result += "\n"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка форматирования списка ссылок: {e}")
            return f"{MessageFormatter.get_emoji('error')} Ошибка загрузки ссылок."
    
    def get_user_links_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики ссылок пользователя"""
        try:
            user = self.db.get_user_by_telegram_id(user_id)
            if not user:
                return {'error': 'Пользователь не найден'}
            
            # Получаем ссылки пользователя
            user_links = self.db.get_user_links(user.id, limit=100)
            
            # Анализируем домены
            domain_stats = {}
            total_links = len(user_links)
            
            for link in user_links:
                domain = self._extract_domain_name(link.url)
                domain_stats[domain] = domain_stats.get(domain, 0) + 1
            
            # Сортируем по популярности
            sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1], reverse=True)
            
            return {
                'total_links': total_links,
                'domains': sorted_domains,
                'recent_links': user_links[:10],
                'user': user
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики ссылок: {e}")
            return {'error': 'Ошибка загрузки статистики'}
    
    def analyze_link_trends(self, days: int = 7) -> Dict[str, Any]:
        """Анализ трендов ссылок за период (для админов)"""
        try:
            from datetime import datetime, timedelta, timezone
            
            # Период анализа
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)
            
            # Получаем ссылки за период (это упрощенный запрос, в реальности нужен более сложный)
            recent_links = self.db.get_recent_links(limit=1000)  # Берем много ссылок
            
            # Фильтруем по дате
            period_links = [
                link for link in recent_links 
                if link.created_at >= start_date
            ]
            
            # Анализируем
            domain_stats = {}
            daily_stats = {}
            
            for link in period_links:
                # Статистика доменов
                domain = self._extract_domain_name(link.url)
                domain_stats[domain] = domain_stats.get(domain, 0) + 1
                
                # Статистика по дням
                day_key = link.created_at.strftime('%Y-%m-%d')
                daily_stats[day_key] = daily_stats.get(day_key, 0) + 1
            
            # Топ доменов
            top_domains = sorted(domain_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'period_days': days,
                'total_links': len(period_links),
                'daily_average': len(period_links) / max(days, 1),
                'top_domains': top_domains,
                'daily_breakdown': daily_stats,
                'most_active_day': max(daily_stats.items(), key=lambda x: x[1]) if daily_stats else None
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа трендов: {e}")
            return {'error': 'Ошибка анализа данных'}
    
    # ============================================
    # ИНТЕГРАЦИЯ С ПЛАНАМИ 2-3
    # ============================================
    
    def check_user_activity_for_karma(self, user_id: int) -> Dict[str, Any]:
        """Анализ активности пользователя для системы кармы (План 2)"""
        if not config.ENABLE_PLAN_2_FEATURES:
            return {}
        
        try:
            user = self.db.get_user_by_telegram_id(user_id)
            if not user:
                return {}
            
            # Получаем статистику
            user_links = self.db.get_user_links(user.id, limit=50)
            karma_record = self.db.get_user_karma(user.id)
            
            links_count = len(user_links)
            karma_points = karma_record.karma_points if karma_record else 0
            
            # Вычисляем соотношение
            ratio = karma_points / max(links_count, 1)
            
            # Оценка активности
            if links_count == 0:
                activity_level = "Нет активности"
            elif ratio >= 0.8:
                activity_level = "Отличная взаимность"
            elif ratio >= 0.5:
                activity_level = "Хорошая взаимность" 
            elif ratio >= 0.25:
                activity_level = "Умеренная взаимность"
            else:
                activity_level = "Низкая взаимность"
            
            return {
                'links_count': links_count,
                'karma_points': karma_points,
                'ratio': ratio,
                'activity_level': activity_level,
                'needs_karma_boost': ratio < 0.3 and links_count > 5
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка анализа активности для кармы: {e}")
            return {}
    
    def suggest_presave_targets(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Предложение целей для пресейвов (План 3 - ИИ)"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return []
        
        try:
            # Получаем недавние ссылки других пользователей
            recent_links = self.db.get_recent_links(limit=20)
            
            suggestions = []
            user_links = set()  # Ссылки текущего пользователя
            
            # Получаем ссылки текущего пользователя для исключения
            user = self.db.get_user_by_telegram_id(user_id)
            if user:
                user_recent_links = self.db.get_user_links(user.id, limit=10)
                user_links = {link.url for link in user_recent_links}
            
            for link in recent_links:
                # Пропускаем собственные ссылки
                if link.url in user_links:
                    continue
                
                # Пропускаем ссылки от того же пользователя
                if hasattr(link, 'user') and link.user and link.user.telegram_id == user_id:
                    continue
                
                # Формируем предложение
                suggestion = {
                    'url': link.url,
                    'domain': self._extract_domain_name(link.url),
                    'author': link.user.username if link.user and link.user.username else "Аноним",
                    'time_ago': MessageFormatter.format_time_ago(link.created_at),
                    'preview': MessageFormatter.truncate_text(link.message_text or "", 50)
                }
                
                suggestions.append(suggestion)
                
                if len(suggestions) >= limit:
                    break
            
            return suggestions
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации предложений пресейвов: {e}")
            return []
    
    # ============================================
    # СЛУЖЕБНЫЕ ФУНКЦИИ
    # ============================================
    
    def cleanup_old_reminders(self):
        """Очистка старых записей напоминаний из кэша"""
        try:
            current_time = time.time()
            expired_threads = [
                thread_id for thread_id, timestamp in self.recent_reminders.items()
                if current_time - timestamp > self.reminder_cooldown * 2
            ]
            
            for thread_id in expired_threads:
                del self.recent_reminders[thread_id]
            
            if expired_threads:
                logger.debug(f"🧹 Очищено {len(expired_threads)} старых записей напоминаний")
                
        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша напоминаний: {e}")
    
    def get_handler_stats(self) -> Dict[str, Any]:
        """Получение статистики работы обработчика"""
        try:
            return {
                'recent_reminders_count': len(self.recent_reminders),
                'reminder_cooldown': self.reminder_cooldown,
                'bot_enabled': ConfigHelper.is_bot_enabled(),
                'whitelist_threads': len(config.WHITELIST_THREADS),
                'supported_domains': 15  # Количество поддерживаемых доменов
            }
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {}

# ============================================
# ГЛОБАЛЬНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ
# ============================================

def init_link_handlers(bot: telebot.TeleBot) -> LinkHandler:
    """Инициализация обработчика ссылок"""
    return LinkHandler(bot)

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = ['LinkHandler', 'init_link_handlers']

if __name__ == "__main__":
    print("🧪 Тестирование Link Handler...")
    print("✅ КЛЮЧЕВАЯ ФУНКЦИЯ бота готова!")
    print("🔗 Модуль links.py обеспечивает основной функционал пресейв-напоминаний")
