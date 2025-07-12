"""
database/analytics.py - Аналитика и статистика
Функции для получения статистики пользователей и аналитики сообщества
ПЛАН 1: Базовые функции + заглушки для будущих планов
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from utils.logger import get_logger
from database.models import User, Link, Settings
# ПЛАН 2: from database.models import UserKarma, KarmaHistory  # ЗАГЛУШКА
# ПЛАН 3: from database.models import FormSubmission, AIInteraction  # ЗАГЛУШКА

logger = get_logger(__name__)

class AnalyticsManager:
    """Менеджер аналитики и статистики сообщества"""
    
    def __init__(self, db_manager):
        """Инициализация менеджера аналитики"""
        self.db_manager = db_manager
        logger.info("✅ AnalyticsManager инициализирован")
    
    # ============================================
    # ПЛАН 1: БАЗОВАЯ СТАТИСТИКА (АКТИВНО)
    # ============================================
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Получение статистики пользователя для команды /mystat"""
        try:
            with self.db_manager.get_session() as session:
                # Базовая информация о пользователе
                user = session.query(User).filter(User.telegram_id == user_id).first()
                if not user:
                    return {"error": "Пользователь не найден"}
                
                # Статистика ссылок пользователя
                links_count = session.query(Link).filter(Link.user_id == user_id).count()
                
                # Статистика за последние 30 дней
                month_ago = datetime.utcnow() - timedelta(days=30)
                recent_links = session.query(Link).filter(
                    Link.user_id == user_id,
                    Link.created_at >= month_ago
                ).count()
                
                stats = {
                    "user_id": user_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "registered_at": user.created_at,
                    "total_links": links_count,
                    "links_last_30_days": recent_links,
                    "last_activity": user.last_activity,
                    # ПЛАН 2: Карма (ЗАГЛУШКИ)
                    "karma_points": 0,  # TODO: Заменить на реальную карму в Плане 2
                    "rank": "🥉 Новенький",  # TODO: Заменить на реальное звание в Плане 2
                    "rank_progress": "0/5",  # TODO: Заменить на реальный прогресс в Плане 2
                    # ПЛАН 3: Расширенная статистика (ЗАГЛУШКИ)
                    "presave_requests": 0,  # TODO: Добавить в Плане 3
                    "approved_presaves": 0,  # TODO: Добавить в Плане 3
                    "ai_interactions": 0,  # TODO: Добавить в Плане 3
                }
                
                logger.info(f"📊 Статистика пользователя {user_id} получена", user_id=user_id)
                return stats
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
            return {"error": "Ошибка получения статистики"}
    
    def get_community_stats(self) -> Dict:
        """Получение общей статистики сообщества"""
        try:
            with self.db_manager.get_session() as session:
                # Общее количество пользователей
                total_users = session.query(User).count()
                
                # Активные пользователи за последние 30 дней
                month_ago = datetime.utcnow() - timedelta(days=30)
                active_users = session.query(User).filter(
                    User.last_activity >= month_ago
                ).count()
                
                # Общее количество ссылок
                total_links = session.query(Link).count()
                
                # Ссылки за последние 7 дней
                week_ago = datetime.utcnow() - timedelta(days=7)
                recent_links = session.query(Link).filter(
                    Link.created_at >= week_ago
                ).count()
                
                stats = {
                    "total_users": total_users,
                    "active_users_30d": active_users,
                    "total_links": total_links,
                    "links_last_7d": recent_links,
                    "updated_at": datetime.utcnow(),
                    # ПЛАН 2: Статистика кармы (ЗАГЛУШКИ)
                    "avg_karma": 0,  # TODO: Добавить в Плане 2
                    "top_karma_users": [],  # TODO: Добавить в Плане 2
                    # ПЛАН 3: Расширенная аналитика (ЗАГЛУШКИ)
                    "total_forms_submitted": 0,  # TODO: Добавить в Плане 3
                    "ai_interactions_today": 0,  # TODO: Добавить в Плане 3
                }
                
                logger.info("📊 Общая статистика сообщества получена")
                return stats
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики сообщества: {e}")
            return {"error": "Ошибка получения статистики"}
    
    def get_links_history(self, limit: int = 10) -> List[Dict]:
        """Получение истории ссылок для команд /last10links и /last30links"""
        try:
            with self.db_manager.get_session() as session:
                links = session.query(Link).join(User).order_by(
                    desc(Link.created_at)
                ).limit(limit).all()
                
                history = []
                for link in links:
                    history.append({
                        "id": link.id,
                        "url": link.url,
                        "user_id": link.user_id,
                        "username": link.user.username or "Unknown",
                        "first_name": link.user.first_name or "Unknown",
                        "created_at": link.created_at,
                        "message_id": link.message_id,
                        "thread_id": link.thread_id
                    })
                
                logger.info(f"📜 История ссылок получена: {len(history)} записей")
                return history
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения истории ссылок: {e}")
            return []
    
    # ============================================
    # ПЛАН 2: АНАЛИТИКА КАРМЫ (ЗАГЛУШКИ)
    # ============================================
    
    def get_karma_leaderboard(self, limit: int = 10) -> List[Dict]:
        """ЗАГЛУШКА: Получение топа пользователей по карме"""
        # TODO: Реализовать в Плане 2
        logger.debug("🔄 get_karma_leaderboard - в разработке (План 2)")
        return []
    
    def get_karma_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """ЗАГЛУШКА: Получение истории изменения кармы пользователя"""
        # TODO: Реализовать в Плане 2
        logger.debug(f"🔄 get_karma_history для {user_id} - в разработке (План 2)")
        return []
    
    def calculate_user_rank(self, karma_points: int) -> Dict:
        """ЗАГЛУШКА: Расчет звания пользователя по карме"""
        # TODO: Реализовать в Плане 2
        logger.debug("🔄 calculate_user_rank - в разработке (План 2)")
        return {
            "rank": "🥉 Новенький",
            "emoji": "🥉",
            "progress": "0/5",
            "next_rank": "🥈 Надежда сообщества"
        }
    
    # ============================================
    # ПЛАН 3: АНАЛИТИКА ФОРМ И ИИ (ЗАГЛУШКИ) 
    # ============================================
    
    def get_forms_stats(self) -> Dict:
        """ЗАГЛУШКА: Статистика подачи форм и заявок"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 get_forms_stats - в разработке (План 3)")
        return {
            "total_submissions": 0,
            "pending_approval": 0,
            "approved_today": 0,
            "rejection_rate": 0
        }
    
    def get_ai_usage_stats(self) -> Dict:
        """ЗАГЛУШКА: Статистика использования ИИ"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 get_ai_usage_stats - в разработке (План 3)")
        return {
            "interactions_today": 0,
            "total_tokens_used": 0,
            "avg_response_time": 0,
            "most_active_users": []
        }
    
    def get_gratitude_stats(self) -> Dict:
        """ЗАГЛУШКА: Статистика автоматического распознавания благодарностей"""
        # TODO: Реализовать в Плане 3
        logger.debug("🔄 get_gratitude_stats - в разработке (План 3)")
        return {
            "auto_karma_given": 0,
            "gratitude_detected": 0,
            "top_grateful_users": []
        }
    
    # ============================================
    # ПЛАН 4: АНАЛИТИКА BACKUP (ЗАГЛУШКИ)
    # ============================================
    
    def get_backup_stats(self) -> Dict:
        """ЗАГЛУШКА: Статистика системы backup"""
        # TODO: Реализовать в Плане 4
        logger.debug("🔄 get_backup_stats - в разработке (План 4)")
        return {
            "database_age_days": 0,
            "last_backup_date": None,
            "backup_size_mb": 0,
            "auto_backups_count": 0
        }


# Глобальный менеджер аналитики
analytics_manager = None

def init_analytics_manager(db_manager):
    """Инициализация менеджера аналитики"""
    global analytics_manager
    analytics_manager = AnalyticsManager(db_manager)
    logger.info("✅ AnalyticsManager инициализирован глобально")

def get_analytics_manager() -> AnalyticsManager:
    """Получение менеджера аналитики"""
    if analytics_manager is None:
        raise RuntimeError("AnalyticsManager не инициализирован")
    return analytics_manager


# ============================================
# БЫСТРЫЕ ФУНКЦИИ ДЛЯ ИСПОЛЬЗОВАНИЯ В ХЕНДЛЕРАХ
# ============================================

def get_user_quick_stats(user_id: int) -> str:
    """Быстрое получение статистики пользователя в виде форматированной строки"""
    try:
        manager = get_analytics_manager()
        stats = manager.get_user_stats(user_id)
        
        if "error" in stats:
            return f"❌ {stats['error']}"
        
        # Форматируем статистику
        result = f"""
📊 **Твоя статистика** @{stats.get('username', 'unknown')}

🔗 **Ссылки:** {stats['total_links']} всего / {stats['links_last_30_days']} за месяц
🏆 **Звание:** {stats['rank']} ({stats['rank_progress']})
💎 **Карма:** {stats['karma_points']} баллов

📅 **Регистрация:** {stats['registered_at'].strftime('%d.%m.%Y') if stats['registered_at'] else 'Неизвестно'}
🕒 **Последняя активность:** {stats['last_activity'].strftime('%d.%m.%Y %H:%M') if stats['last_activity'] else 'Давно'}
"""
        
        # ПЛАН 3: Добавим расширенную статистику
        if stats['presave_requests'] > 0 or stats['approved_presaves'] > 0:
            result += f"""
🎵 **Пресейвы:** {stats['presave_requests']} запросов / {stats['approved_presaves']} одобрено
🤖 **ИИ:** {stats['ai_interactions']} взаимодействий
"""
        
        return result.strip()
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения быстрой статистики для {user_id}: {e}")
        return "❌ Ошибка получения статистики"

def get_community_quick_stats() -> str:
    """Быстрое получение статистики сообщества в виде форматированной строки"""
    try:
        manager = get_analytics_manager()
        stats = manager.get_community_stats()
        
        if "error" in stats:
            return f"❌ {stats['error']}"
        
        result = f"""
📊 **Статистика сообщества**

👥 **Пользователи:** {stats['total_users']} всего / {stats['active_users_30d']} активных
🔗 **Ссылки:** {stats['total_links']} всего / {stats['links_last_7d']} за неделю
💎 **Средняя карма:** {stats['avg_karma']} баллов

🕒 **Обновлено:** {stats['updated_at'].strftime('%d.%m.%Y %H:%M')}
"""
        
        return result.strip()
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения быстрой статистики сообщества: {e}")
        return "❌ Ошибка получения статистики"

def format_links_history(links: List[Dict], limit_name: str) -> str:
    """Форматирование истории ссылок для команд /last10links и /last30links"""
    try:
        if not links:
            return f"📭 История ссылок пуста"
        
        result = f"🔗 **Последние {limit_name} ссылок:**\n\n"
        
        for i, link in enumerate(links, 1):
            username = link.get('username', 'Unknown')
            first_name = link.get('first_name', 'Unknown')
            date = link['created_at'].strftime('%d.%m %H:%M') if link['created_at'] else 'Unknown'
            
            # Укорачиваем URL если слишком длинный
            url = link['url']
            if len(url) > 50:
                url = url[:47] + "..."
            
            result += f"{i}. **@{username}** ({first_name})\n"
            result += f"   🔗 {url}\n"
            result += f"   📅 {date}\n\n"
        
        result += f"💡 Всего показано: {len(links)} ссылок"
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка форматирования истории ссылок: {e}")
        return "❌ Ошибка форматирования истории"