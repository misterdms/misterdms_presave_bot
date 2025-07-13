"""
Обработчик ссылок Do Presave Reminder Bot v25+
Обработка ссылок и отправка напоминаний о пресейвах

ПЛАН 1: Базовая обработка ссылок (АКТИВНАЯ)
ПЛАН 2: Интеграция с кармой (ЗАГЛУШКИ)
ПЛАН 3: Интеграция с формами (ЗАГЛУШКИ)
ПЛАН 4: Логирование для backup (ЗАГЛУШКИ)
"""

import re
import time
from datetime import datetime
from typing import List, Optional
import telebot
from telebot.types import Message

from database.manager import DatabaseManager
from utils.security import SecurityManager
from utils.logger import get_logger, log_user_action
from config import Config

logger = get_logger(__name__)

class LinkHandler:
    """Обработчик ссылок и автоматических напоминаний"""
    
    def __init__(self, bot: telebot.TeleBot, db_manager: DatabaseManager, 
                 security_manager: SecurityManager, config: Config):
        """Инициализация обработчика ссылок"""
        self.bot = bot
        self.db = db_manager
        self.security = security_manager
        self.config = config
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: инициализация WHITELIST
        if not hasattr(self.security, 'whitelist_threads'):
            logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: SecurityManager.whitelist_threads не инициализирован!")
            self.security.whitelist_threads = self.config.WHITELIST if hasattr(self.config, 'WHITELIST') else []
            logger.info(f"✅ Принудительно установлен WHITELIST: {self.security.whitelist_threads}")
        
        # Паттерны для обнаружения ссылок (улучшенный регекс)
        self.url_pattern = re.compile(
            r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?',
            re.IGNORECASE
        )
        
        # Специальные паттерны для пресейв ссылок
        self.presave_patterns = [
            re.compile(r'presave', re.IGNORECASE),
            re.compile(r'pre-save', re.IGNORECASE),
            re.compile(r'linktr\.ee', re.IGNORECASE),
            re.compile(r'smarturl', re.IGNORECASE),
            re.compile(r'distrokid', re.IGNORECASE),
            re.compile(r'ampl\.ink', re.IGNORECASE),
        ]
        
        logger.info("LinkHandler инициализирован")
    
    def handle_link_message(self, message: Message):
        """Основная обработка сообщения со ссылками"""
        try:
            user_id = message.from_user.id
            text = message.text or ""
            thread_id = getattr(message, 'message_thread_id', None)
            message_id = message.message_id
            
            # ДИАГНОСТИЧЕСКИЙ ЛОГ
            logger.info(f"🔗 ВЫЗВАН handle_link_message: user_id={user_id}, thread_id={thread_id}, text='{text[:100]}...'")
            
            # Проверяем включен ли бот
            if not self.db.get_setting('bot_enabled', True):
                logger.info("Бот отключен, игнорируем ссылки")
                return
            
            # Проверяем разрешенные топики
            whitelist_threads = getattr(self.security, 'whitelist_threads', [])
            if not whitelist_threads:
                # Если whitelist пустой, берем из config
                whitelist_threads = getattr(self.config, 'WHITELIST', [])
                logger.warning(f"⚠️ WHITELIST взят из config: {whitelist_threads}")

            if thread_id and thread_id not in whitelist_threads:
                logger.info(f"Ссылка в неразрешенном топике {thread_id} проигнорирована (WHITELIST: {whitelist_threads})")
                return

            logger.info(f"✅ Ссылка в разрешенном топике {thread_id} (WHITELIST: {whitelist_threads})")
            
            # Извлекаем ссылки из сообщения
            urls = self._extract_urls(text)
            
            if not urls:
                logger.info(f"🔍 В сообщении не найдено валидных URL")
                return
            
            log_user_action(logger, user_id, f"опубликовал {len(urls)} ссылок в топике {thread_id}")
            
            # Сохраняем ссылки в БД
            self._save_links_to_database(user_id, urls, text, message_id, thread_id)
            
            # ПЛАН 2: Обновление счетчика просьб (ЗАГЛУШКА)
            # self._update_request_count(user_id, len(urls))
            
            # Отправляем напоминание о взаимности
            self._send_reminder_message(message, len(urls))
            
            # ПЛАН 3: Уведомление о новой заявке админам (ЗАГЛУШКА)
            # if self._is_presave_link(urls):
            #     self._notify_admins_new_request(user_id, urls, text)
            
        except Exception as e:
            logger.error(f"❌ Ошибка handle_link_message: {e}")
    
    def _extract_urls(self, text: str) -> List[str]:
        """Извлечение URL из текста"""
        try:
            urls = self.url_pattern.findall(text)
            
            # Очистка и валидация URL
            cleaned_urls = []
            for url in urls:
                # Убираем лишние символы в конце
                url = url.rstrip('.,!?;)')
                
                # Проверяем что URL валидный
                if self._is_valid_url(url):
                    cleaned_urls.append(url)
            
            logger.info(f"🔍 Извлечено {len(cleaned_urls)} валидных URL из {len(urls)} найденных")
            return cleaned_urls
            
        except Exception as e:
            logger.error(f"❌ Ошибка _extract_urls: {e}")
            return []
    
    def _is_valid_url(self, url: str) -> bool:
        """Проверка валидности URL"""
        try:
            # Базовые проверки
            if len(url) < 10 or len(url) > 2000:
                return False
            
            if not (url.startswith('http://') or url.startswith('https://')):
                return False
            
            # Проверяем что есть домен
            if '//' not in url or '.' not in url:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка _is_valid_url: {e}")
            return False
    
    def _save_links_to_database(self, user_id: int, urls: List[str], 
                               message_text: str, message_id: int, thread_id: int):
        """Сохранение ссылок в базу данных"""
        try:
            for url in urls:
                self.db.add_link(
                    user_id=user_id,
                    url=url,
                    message_text=message_text,
                    message_id=message_id,
                    thread_id=thread_id
                )
            
            logger.info(f"✅ Сохранено {len(urls)} ссылок от пользователя {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка _save_links_to_database: {e}")
    
    def _send_reminder_message(self, original_message: Message, links_count: int):
        """Отправка напоминания о взаимности"""
        try:
            # Проверяем лимиты API и delay
            if not self._check_rate_limits(original_message.from_user.id):
                logger.info("Rate limit достигнут, напоминание пропущено")
                return
            
            # Добавляем задержку
            delay = self.config.RESPONSE_DELAY
            if delay > 0:
                logger.info(f"⏳ Задержка перед отправкой напоминания: {delay} сек")
                time.sleep(delay)
            
            # Получаем текст напоминания
            reminder_text = self.config.REMINDER_TEXT
            
            # Дополняем текст информацией о количестве ссылок
            if links_count > 1:
                reminder_text += f"\n\n📊 Обнаружено ссылок: {links_count}"
            
            # Отправляем напоминание
            self.bot.reply_to(original_message, reminder_text)
            
            log_user_action(logger, original_message.from_user.id, 
                           f"получил напоминание о {links_count} ссылках")
            
            # Обновляем счетчик напоминаний
            current_count = self.db.get_setting('reminder_count', 0)
            self.db.set_setting('reminder_count', current_count + 1, 'int', 
                               'Количество отправленных напоминаний')
            
        except Exception as e:
            logger.error(f"❌ Ошибка _send_reminder_message: {e}")
    
    def _check_rate_limits(self, user_id: int) -> bool:
        """Проверка лимитов частоты напоминаний"""
        try:
            # Получаем текущий режим лимитов
            current_mode = self.db.get_setting('current_limit_mode', 'BURST')
            limit_config = self.config.get_limit_config(current_mode)
            
            # Для админов применяем особые правила
            if self.security.is_admin(user_id):
                return True  # Админы не ограничены
            
            # ПЛАН 1: Простая проверка - всегда разрешаем
            # В продакшене здесь будет полноценная система лимитов
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка _check_rate_limits: {e}")
            return True
    
    def _is_presave_link(self, urls: List[str]) -> bool:
        """Проверка является ли ссылка пресейвом"""
        try:
            for url in urls:
                url_lower = url.lower()
                
                # Проверяем по паттернам
                for pattern in self.presave_patterns:
                    if pattern.search(url_lower):
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка _is_presave_link: {e}")
            return False
    
    # ============================================
    # ПЛАН 2: ИНТЕГРАЦИЯ С КАРМОЙ (ЗАГЛУШКИ)
    # ============================================
    
    # def _update_request_count(self, user_id: int, links_count: int):
    #     """Обновление счетчика просьб о пресейвах"""
    #     try:
    #         # Обновляем статистику просьб в таблице кармы
    #         karma = self.db.get_or_create_karma(user_id)
    #         karma.total_requests += links_count
    #         
    #         self.db.session.commit()
    #         
    #         logger.info(f"Обновлен счетчик просьб для {user_id}: +{links_count}")
    #         
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _update_request_count: {e}")
    
    # def _check_ratio_warning(self, user_id: int):
    #     """Проверка соотношения просьб к карме"""
    #     try:
    #         karma = self.db.get_or_create_karma(user_id)
    #         
    #         # Если много просьб, но мало кармы - предупреждение
    #         if karma.total_requests > 10 and karma.karma_points < 5:
    #             ratio = karma.total_requests / max(karma.karma_points, 1)
    #             
    #             if ratio > 3:  # Более 3 просьб на 1 карму
    #                 self._send_ratio_warning(user_id, karma.total_requests, karma.karma_points)
    #                 
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _check_ratio_warning: {e}")
    
    # def _send_ratio_warning(self, user_id: int, requests: int, karma: int):
    #     """Отправка предупреждения о плохом соотношении"""
    #     try:
    #         user = self.db.get_user_by_id(user_id)
    #         if not user:
    #             return
    #         
    #         warning_text = f"""
    # ⚠️ <b>Внимание!</b>
    # 
    # 📊 <b>Ваша статистика:</b>
    # • Просьб о пресейвах: {requests}
    # • Карма за помощь: {karma}
    # 
    # 🎯 <b>Рекомендация:</b>
    # Помогайте другим участникам сообщества делать пресейвы, чтобы улучшить соотношение!
    # 
    # 💡 Карма начисляется за реальную помощь и благодарности от других участников.
    # """
    #         
    #         self.bot.send_message(user_id, warning_text, parse_mode='HTML')
    #         
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _send_ratio_warning: {e}")
    
    # ============================================
    # ПЛАН 3: ИНТЕГРАЦИЯ С ФОРМАМИ (ЗАГЛУШКИ)
    # ============================================
    
    # def _notify_admins_new_request(self, user_id: int, urls: List[str], text: str):
    #     """Уведомление админов о новой заявке на пресейв"""
    #     try:
    #         if not self.db.get_setting('forms_enabled', False):
    #             return
    #         
    #         user = self.db.get_user_by_id(user_id)
    #         if not user:
    #             return
    #         
    #         # Создаем заявку в БД
    #         from services.forms import FormManager
    #         form_manager = FormManager(self.db, self.config)
    #         
    #         request_id = form_manager.create_presave_request(
    #             user_id=user_id,
    #             description=text,
    #             links=urls
    #         )
    #         
    #         # Уведомляем админов
    #         notification_text = f"""
    # 🎵 <b>Новая заявка на пресейв</b>
    # 
    # 👤 <b>От:</b> {format_user_mention(user_id, user.username, user.first_name)}
    # 🔗 <b>Ссылок:</b> {len(urls)}
    # 📝 <b>ID заявки:</b> {request_id}
    # 
    # 📋 <b>Описание:</b>
    # {text[:200]}{'...' if len(text) > 200 else ''}
    # 
    # 💡 Используйте /checkapprovals для модерации.
    # """
    #         
    #         # Отправляем всем админам
    #         admins = self.db.get_all_admins()
    #         for admin in admins:
    #             try:
    #                 self.bot.send_message(admin.user_id, notification_text, parse_mode='HTML')
    #             except Exception as e:
    #                 logger.error(f"❌ Не удалось уведомить админа {admin.user_id}: {e}")
    #                 
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _notify_admins_new_request: {e}")
    
    # def _create_presave_request(self, user_id: int, urls: List[str], description: str) -> int:
    #     """Создание заявки на пресейв в БД"""
    #     try:
    #         from database.models import PresaveRequest
    #         
    #         request = PresaveRequest(
    #             user_id=user_id,
    #             description=description,
    #             links=urls,
    #             status='active'
    #         )
    #         
    #         with self.db.get_session() as session:
    #             session.add(request)
    #             session.commit()
    #             return request.id
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _create_presave_request: {e}")
    #         return 0
    
    # ============================================
    # УТИЛИТЫ
    # ============================================
    
    def get_recent_links_formatted(self, count: int = 10, thread_id: int = None) -> str:
        """Получение отформатированного списка последних ссылок"""
        try:
            links = self.db.get_recent_links(count, thread_id)
            
            if not links:
                return f"📎 <b>Последние {count} ссылок</b>\n\n🤷 Ссылок пока нет."
            
            text_parts = [f"📎 <b>Последние {count} ссылок</b>\n"]
            
            for i, link in enumerate(links, 1):
                user = self.db.get_user_by_id(link.user_id)
                username = f"@{user.username}" if user and user.username else f"ID{link.user_id}"
                date_str = link.created_at.strftime("%d.%m %H:%M")
                
                # Обрезаем URL если слишком длинный
                display_url = link.url if len(link.url) <= 50 else link.url[:47] + "..."
                
                text_parts.append(f"{i}. <b>{username}</b> ({date_str})")
                text_parts.append(f"   🔗 {display_url}")
                
                if i < len(links):
                    text_parts.append("")
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"❌ Ошибка get_recent_links_formatted: {e}")
            return "❌ Ошибка при получении ссылок"
    
    def get_user_links_formatted(self, username: str, limit: int = 20) -> str:
        """Получение отформатированного списка ссылок пользователя"""
        try:
            links = self.db.get_links_by_username(username)
            
            if not links:
                return f"🔍 <b>Ссылки пользователя @{username}</b>\n\n🤷 Пользователь не найден или у него нет ссылок."
            
            # Ограничиваем количество для показа
            display_links = links[:limit]
            
            text_parts = [
                f"🔍 <b>Ссылки пользователя @{username}</b>",
                f"📊 <b>Всего найдено:</b> {len(links)} ссылок\n"
            ]
            
            for i, link in enumerate(display_links, 1):
                date_str = link.created_at.strftime("%d.%m.%Y %H:%M")
                display_url = link.url if len(link.url) <= 50 else link.url[:47] + "..."
                
                text_parts.append(f"{i}. {date_str}")
                text_parts.append(f"   🔗 {display_url}")
                
                if i < len(display_links):
                    text_parts.append("")
            
            if len(links) > limit:
                text_parts.append(f"\n... и еще {len(links) - limit} ссылок")
            
            return "\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"❌ Ошибка get_user_links_formatted: {e}")
            return "❌ Ошибка при получении ссылок пользователя"
    
    def get_links_statistics(self) -> dict:
        """Получение статистики ссылок"""
        try:
            stats = self.db.get_basic_stats()
            
            # Дополняем статистику ссылок
            with self.db.get_session() as session:
                from database.models import Link
                
                # Ссылки за сегодня
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_links = session.query(Link).filter(
                    Link.created_at >= today_start,
                    Link.is_active == True
                ).count()
                
                # Уникальные пользователи с ссылками
                unique_users = session.query(Link.user_id).filter(
                    Link.is_active == True
                ).distinct().count()
                
                # Топ пользователей по ссылкам
                from sqlalchemy import func
                top_users = session.query(
                    Link.user_id,
                    func.count(Link.id).label('link_count')
                ).filter(
                    Link.is_active == True
                ).group_by(Link.user_id).order_by(
                    func.count(Link.id).desc()
                ).limit(5).all()
                
                stats.update({
                    'links_today': today_links,
                    'unique_users_with_links': unique_users,
                    'top_users': top_users,
                    'reminder_count': self.db.get_setting('reminder_count', 0)
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка get_links_statistics: {e}")
            return {}


if __name__ == "__main__":
    """Тестирование LinkHandler"""
    from database.manager import DatabaseManager
    from utils.security import SecurityManager
    from config import Config
    
    print("🧪 Тестирование LinkHandler...")
    
    # Создание тестовых компонентов
    db = DatabaseManager("sqlite:///:memory:")
    db.create_tables()
    
    security = SecurityManager([12345], [2, 3])
    config = Config()
    
    # Тестирование link handler
    link_handler = LinkHandler(None, db, security, config)
    
    # Тестирование извлечения URL
    print("\n🔗 Тестирование извлечения URL:")
    test_texts = [
        "Привет! Вот ссылка: https://example.com",
        "Множественные ссылки: http://test.org и https://another.com/path?param=value",
        "Плохая ссылка: ht://invalid.url",
        "Пресейв: https://linktr.ee/artist_name"
    ]
    
    for text in test_texts:
        urls = link_handler._extract_urls(text)
        print(f"• '{text[:40]}...': {len(urls)} URL(s)")
        for url in urls:
            print(f"    - {url}")
    
    # Тестирование проверки пресейв ссылок
    print("\n🎵 Тестирование проверки пресейв ссылок:")
    test_urls = [
        ["https://linktr.ee/artist"],
        ["https://example.com/presave"],
        ["https://distrokid.com/hyperfollow/artist/song"],
        ["https://regular-website.com"]
    ]
    
    for urls in test_urls:
        is_presave = link_handler._is_presave_link(urls)
        status = "✅ Пресейв" if is_presave else "❌ Обычная ссылка"
        print(f"• {urls[0]}: {status}")
    
    print("\n✅ Тестирование LinkHandler завершено!")