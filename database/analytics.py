"""
📊 Analytics Module - Do Presave Reminder Bot v25+
Функции аналитики и статистики (/mystat, рейтинги) для всех планов

ФУНКЦИОНАЛЬНОСТЬ:
- Статистика пользователей и активности
- Рейтинги и лидерборды  
- Аналитика ссылок и пресейвов
- Система кармы и званий (План 2)
- ИИ метрики (План 3)
- Backup аналитика (План 4)
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json

from sqlalchemy import text, func, and_, or_, desc, asc
from sqlalchemy.orm import Session

from config import config
from database.manager import get_database_manager
from database.models import User, Link, UserKarma, KarmaHistory
from utils.logger import get_logger
from utils.formatters import AnalyticsFormatter
from utils.helpers import DateHelper, MathHelper

logger = get_logger(__name__)

class AnalyticsPeriod(Enum):
    """Периоды для аналитики"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    ALL_TIME = "all_time"

class StatType(Enum):
    """Типы статистики"""
    USER_ACTIVITY = "user_activity"
    LINK_ACTIVITY = "link_activity"
    KARMA_ACTIVITY = "karma_activity"
    AI_ACTIVITY = "ai_activity"
    SYSTEM_HEALTH = "system_health"

@dataclass
class UserStats:
    """Статистика пользователя"""
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    
    # Основная активность
    total_links_posted: int = 0
    total_links_clicked: int = 0
    total_messages: int = 0
    registration_date: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    # Карма (План 2)
    current_karma: int = 0
    total_karma_given: int = 0
    total_karma_received: int = 0
    karma_rank: Optional[str] = None
    
    # ИИ взаимодействия (План 3)
    ai_requests: int = 0
    ai_responses_received: int = 0
    gratitude_auto_karma: int = 0
    
    # Активность по периодам
    activity_today: int = 0
    activity_week: int = 0
    activity_month: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return asdict(self)

@dataclass
class LinkStats:
    """Статистика ссылки"""
    link_id: int
    url: str
    platform: Optional[str]
    user_id: int
    username: Optional[str]
    
    posted_at: datetime
    total_views: int = 0
    unique_viewers: int = 0
    
    # Метрики эффективности
    click_through_rate: float = 0.0
    engagement_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return asdict(self)

@dataclass
class CommunityStats:
    """Общая статистика сообщества"""
    total_users: int = 0
    active_users_today: int = 0
    active_users_week: int = 0
    active_users_month: int = 0
    
    total_links: int = 0
    links_today: int = 0
    links_week: int = 0
    links_month: int = 0
    
    # План 2 - Карма
    total_karma_operations: int = 0
    average_karma: float = 0.0
    top_karma_user: Optional[str] = None
    
    # План 3 - ИИ
    total_ai_requests: int = 0
    ai_requests_today: int = 0
    average_response_time: float = 0.0
    
    # Платформы
    platform_distribution: Dict[str, int] = None
    
    def __post_init__(self):
        if self.platform_distribution is None:
            self.platform_distribution = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return asdict(self)

class AnalyticsEngine:
    """Движок аналитики"""
    
    def __init__(self):
        """Инициализация движка аналитики"""
        self.db = get_database_manager()
        self.formatter = AnalyticsFormatter()
        
        # Кэш для оптимизации запросов
        self._cache = {}
        self._cache_ttl = 300  # 5 минут
        
        logger.info("📊 AnalyticsEngine инициализирован")
    
    def _get_cache_key(self, key: str, period: AnalyticsPeriod = None, user_id: int = None) -> str:
        """Генерация ключа кэша"""
        parts = [key]
        if period:
            parts.append(period.value)
        if user_id:
            parts.append(str(user_id))
        return "_".join(parts)
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Получение данных из кэша"""
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if (datetime.now(timezone.utc) - timestamp).total_seconds() < self._cache_ttl:
                return data
            else:
                del self._cache[cache_key]
        return None
    
    def _set_cache(self, cache_key: str, data: Any):
        """Сохранение данных в кэш"""
        self._cache[cache_key] = (data, datetime.now(timezone.utc))
    
    def _get_period_filter(self, period: AnalyticsPeriod, column) -> Any:
        """Получение фильтра для периода"""
        now = datetime.now(timezone.utc)
        
        if period == AnalyticsPeriod.HOUR:
            return column >= now - timedelta(hours=1)
        elif period == AnalyticsPeriod.DAY:
            return column >= now - timedelta(days=1)
        elif period == AnalyticsPeriod.WEEK:
            return column >= now - timedelta(weeks=1)
        elif period == AnalyticsPeriod.MONTH:
            return column >= now - timedelta(days=30)
        elif period == AnalyticsPeriod.YEAR:
            return column >= now - timedelta(days=365)
        else:  # ALL_TIME
            return True
    
    def get_user_stats(self, user_id: int, use_cache: bool = True) -> Optional[UserStats]:
        """
        Получение статистики пользователя
        
        Args:
            user_id: ID пользователя
            use_cache: Использовать кэш
            
        Returns:
            UserStats: Статистика пользователя или None если не найден
        """
        cache_key = self._get_cache_key("user_stats", user_id=user_id)
        
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                return cached_data
        
        try:
            with self.db.get_session() as session:
                # Получение основной информации о пользователе
                user = session.query(User).filter(User.user_id == user_id).first()
                
                if not user:
                    return None
                
                stats = UserStats(
                    user_id=user.user_id,
                    username=user.username,
                    first_name=user.first_name,
                    registration_date=user.created_at,
                    last_activity=user.last_activity
                )
                
                # Статистика ссылок
                links_query = session.query(Link).filter(Link.user_id == user_id)
                stats.total_links_posted = links_query.count()
                
                # Активность по периодам
                now = datetime.now(timezone.utc)
                
                # Активность сегодня
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                stats.activity_today = links_query.filter(Link.created_at >= today_start).count()
                
                # Активность за неделю
                week_start = now - timedelta(days=7)
                stats.activity_week = links_query.filter(Link.created_at >= week_start).count()
                
                # Активность за месяц
                month_start = now - timedelta(days=30)
                stats.activity_month = links_query.filter(Link.created_at >= month_start).count()
                
                # План 2 - Статистика кармы
                if config.ENABLE_PLAN_2_FEATURES:
                    self._add_karma_stats(session, stats, user_id)
                
                # План 3 - Статистика ИИ
                if config.ENABLE_PLAN_3_FEATURES:
                    self._add_ai_stats(session, stats, user_id)
                
                if use_cache:
                    self._set_cache(cache_key, stats)
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
            return None
    
    def _add_karma_stats(self, session: Session, stats: UserStats, user_id: int):
        """Добавление статистики кармы"""
        try:
            # Текущая карма
            karma_record = session.query(UserKarma).filter(UserKarma.user_id == user_id).first()
            if karma_record:
                stats.current_karma = karma_record.karma_points
                stats.karma_rank = karma_record.rank
            
            # История кармы
            karma_given = session.query(func.sum(KarmaHistory.change_amount)).filter(
                KarmaHistory.admin_id == user_id,
                KarmaHistory.change_amount > 0
            ).scalar() or 0
            
            karma_received = session.query(func.sum(KarmaHistory.change_amount)).filter(
                KarmaHistory.user_id == user_id,
                KarmaHistory.change_amount > 0
            ).scalar() or 0
            
            stats.total_karma_given = int(karma_given)
            stats.total_karma_received = int(karma_received)
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления статистики кармы: {e}")
    
    def _add_ai_stats(self, session: Session, stats: UserStats, user_id: int):
        """Добавление статистики ИИ"""
        try:
            # Здесь будет добавлена статистика ИИ когда будут созданы соответствующие таблицы
            # Пока заглушка
            stats.ai_requests = 0
            stats.ai_responses_received = 0
            stats.gratitude_auto_karma = 0
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления статистики ИИ: {e}")
    
    def get_community_stats(self, period: AnalyticsPeriod = AnalyticsPeriod.ALL_TIME, use_cache: bool = True) -> CommunityStats:
        """
        Получение общей статистики сообщества
        
        Args:
            period: Период для анализа
            use_cache: Использовать кэш
            
        Returns:
            CommunityStats: Статистика сообщества
        """
        cache_key = self._get_cache_key("community_stats", period)
        
        if use_cache:
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                return cached_data
        
        try:
            with self.db.get_session() as session:
                stats = CommunityStats()
                
                # Общее количество пользователей
                stats.total_users = session.query(User).count()
                
                # Активные пользователи
                now = datetime.now(timezone.utc)
                
                # Активные сегодня
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                stats.active_users_today = session.query(User).filter(
                    User.last_activity >= today_start
                ).count()
                
                # Активные за неделю
                week_start = now - timedelta(days=7)
                stats.active_users_week = session.query(User).filter(
                    User.last_activity >= week_start
                ).count()
                
                # Активные за месяц
                month_start = now - timedelta(days=30)
                stats.active_users_month = session.query(User).filter(
                    User.last_activity >= month_start
                ).count()
                
                # Статистика ссылок
                stats.total_links = session.query(Link).count()
                
                # Ссылки сегодня
                stats.links_today = session.query(Link).filter(
                    Link.created_at >= today_start
                ).count()
                
                # Ссылки за неделю
                stats.links_week = session.query(Link).filter(
                    Link.created_at >= week_start
                ).count()
                
                # Ссылки за месяц
                stats.links_month = session.query(Link).filter(
                    Link.created_at >= month_start
                ).count()
                
                # Распределение по платформам
                stats.platform_distribution = self._get_platform_distribution(session, period)
                
                # План 2 - Статистика кармы
                if config.ENABLE_PLAN_2_FEATURES:
                    self._add_community_karma_stats(session, stats)
                
                # План 3 - Статистика ИИ
                if config.ENABLE_PLAN_3_FEATURES:
                    self._add_community_ai_stats(session, stats)
                
                if use_cache:
                    self._set_cache(cache_key, stats)
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики сообщества: {e}")
            return CommunityStats()
    
    def _get_platform_distribution(self, session: Session, period: AnalyticsPeriod) -> Dict[str, int]:
        """Получение распределения по платформам"""
        try:
            query = session.query(Link.platform, func.count(Link.id)).group_by(Link.platform)
            
            if period != AnalyticsPeriod.ALL_TIME:
                period_filter = self._get_period_filter(period, Link.created_at)
                query = query.filter(period_filter)
            
            results = query.all()
            
            return {platform or 'Unknown': count for platform, count in results}
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения распределения платформ: {e}")
            return {}
    
    def _add_community_karma_stats(self, session: Session, stats: CommunityStats):
        """Добавление общей статистики кармы"""
        try:
            # Общее количество операций с кармой
            stats.total_karma_operations = session.query(KarmaHistory).count()
            
            # Средняя карма
            avg_karma = session.query(func.avg(UserKarma.karma_points)).scalar()
            stats.average_karma = float(avg_karma or 0)
            
            # Топ пользователь по карме
            top_user = session.query(UserKarma, User).join(User).order_by(
                desc(UserKarma.karma_points)
            ).first()
            
            if top_user:
                karma_record, user_record = top_user
                stats.top_karma_user = user_record.username or user_record.first_name
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления статистики кармы сообщества: {e}")
    
    def _add_community_ai_stats(self, session: Session, stats: CommunityStats):
        """Добавление общей статистики ИИ"""
        try:
            # Здесь будет добавлена статистика ИИ когда будут созданы соответствующие таблицы
            stats.total_ai_requests = 0
            stats.ai_requests_today = 0
            stats.average_response_time = 0.0
            
        except Exception as e:
            logger.error(f"❌ Ошибка добавления статистики ИИ сообщества: {e}")
    
    def get_top_users(self, metric: str = "links", period: AnalyticsPeriod = AnalyticsPeriod.ALL_TIME, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получение топа пользователей по метрике
        
        Args:
            metric: Метрика для ранжирования (links, karma, activity)
            period: Период для анализа
            limit: Количество пользователей в топе
            
        Returns:
            List[Dict]: Список пользователей с рейтингами
        """
        cache_key = self._get_cache_key(f"top_users_{metric}", period)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data[:limit]
        
        try:
            with self.db.get_session() as session:
                
                if metric == "links":
                    top_users = self._get_top_users_by_links(session, period, limit)
                elif metric == "karma" and config.ENABLE_PLAN_2_FEATURES:
                    top_users = self._get_top_users_by_karma(session, limit)
                elif metric == "activity":
                    top_users = self._get_top_users_by_activity(session, period, limit)
                else:
                    top_users = []
                
                self._set_cache(cache_key, top_users)
                return top_users
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения топа пользователей: {e}")
            return []
    
    def _get_top_users_by_links(self, session: Session, period: AnalyticsPeriod, limit: int) -> List[Dict[str, Any]]:
        """Топ пользователей по количеству ссылок"""
        
        base_query = session.query(
            User.user_id,
            User.username,
            User.first_name,
            func.count(Link.id).label('link_count')
        ).join(Link, User.user_id == Link.user_id)
        
        if period != AnalyticsPeriod.ALL_TIME:
            period_filter = self._get_period_filter(period, Link.created_at)
            base_query = base_query.filter(period_filter)
        
        results = base_query.group_by(
            User.user_id, User.username, User.first_name
        ).order_by(desc('link_count')).limit(limit).all()
        
        return [
            {
                'rank': idx + 1,
                'user_id': result.user_id,
                'username': result.username,
                'display_name': result.username or result.first_name or f"User{result.user_id}",
                'value': result.link_count,
                'metric': 'ссылок'
            }
            for idx, result in enumerate(results)
        ]
    
    def _get_top_users_by_karma(self, session: Session, limit: int) -> List[Dict[str, Any]]:
        """Топ пользователей по карме"""
        
        results = session.query(
            UserKarma.user_id,
            UserKarma.karma_points,
            UserKarma.rank,
            User.username,
            User.first_name
        ).join(User, UserKarma.user_id == User.user_id).order_by(
            desc(UserKarma.karma_points)
        ).limit(limit).all()
        
        return [
            {
                'rank': idx + 1,
                'user_id': result.user_id,
                'username': result.username,
                'display_name': result.username or result.first_name or f"User{result.user_id}",
                'value': result.karma_points,
                'karma_rank': result.rank,
                'metric': 'кармы'
            }
            for idx, result in enumerate(results)
        ]
    
    def _get_top_users_by_activity(self, session: Session, period: AnalyticsPeriod, limit: int) -> List[Dict[str, Any]]:
        """Топ пользователей по активности"""
        
        # Активность = количество ссылок + участие в карме (если включено)
        base_query = session.query(
            User.user_id,
            User.username,
            User.first_name,
            func.count(Link.id).label('activity_score')
        ).outerjoin(Link, User.user_id == Link.user_id)
        
        if period != AnalyticsPeriod.ALL_TIME:
            period_filter = self._get_period_filter(period, Link.created_at)
            base_query = base_query.filter(or_(Link.id.is_(None), period_filter))
        
        results = base_query.group_by(
            User.user_id, User.username, User.first_name
        ).order_by(desc('activity_score')).limit(limit).all()
        
        return [
            {
                'rank': idx + 1,
                'user_id': result.user_id,
                'username': result.username,
                'display_name': result.username or result.first_name or f"User{result.user_id}",
                'value': result.activity_score,
                'metric': 'активности'
            }
            for idx, result in enumerate(results)
        ]
    
    def get_link_stats(self, link_id: int = None, user_id: int = None, period: AnalyticsPeriod = AnalyticsPeriod.ALL_TIME) -> List[LinkStats]:
        """
        Получение статистики ссылок
        
        Args:
            link_id: ID конкретной ссылки (опционально)
            user_id: ID пользователя для фильтрации (опционально)
            period: Период для анализа
            
        Returns:
            List[LinkStats]: Список статистики ссылок
        """
        try:
            with self.db.get_session() as session:
                query = session.query(Link, User).join(User, Link.user_id == User.user_id)
                
                if link_id:
                    query = query.filter(Link.id == link_id)
                
                if user_id:
                    query = query.filter(Link.user_id == user_id)
                
                if period != AnalyticsPeriod.ALL_TIME:
                    period_filter = self._get_period_filter(period, Link.created_at)
                    query = query.filter(period_filter)
                
                results = query.order_by(desc(Link.created_at)).limit(100).all()
                
                link_stats = []
                for link, user in results:
                    stats = LinkStats(
                        link_id=link.id,
                        url=link.url,
                        platform=link.platform,
                        user_id=link.user_id,
                        username=user.username,
                        posted_at=link.created_at,
                        # TODO: Добавить реальные метрики просмотров когда будет реализовано
                        total_views=0,
                        unique_viewers=0,
                        click_through_rate=0.0,
                        engagement_score=0.0
                    )
                    link_stats.append(stats)
                
                return link_stats
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики ссылок: {e}")
            return []
    
    def get_growth_trends(self, period: AnalyticsPeriod = AnalyticsPeriod.MONTH) -> Dict[str, List[Dict[str, Any]]]:
        """
        Получение трендов роста
        
        Args:
            period: Период для анализа трендов
            
        Returns:
            Dict: Тренды по различным метрикам
        """
        try:
            with self.db.get_session() as session:
                
                # Определяем интервал группировки
                if period == AnalyticsPeriod.DAY:
                    date_trunc = func.date_trunc('hour', Link.created_at)
                    intervals = 24
                elif period == AnalyticsPeriod.WEEK:
                    date_trunc = func.date_trunc('day', Link.created_at)
                    intervals = 7
                elif period == AnalyticsPeriod.MONTH:
                    date_trunc = func.date_trunc('day', Link.created_at)
                    intervals = 30
                else:
                    date_trunc = func.date_trunc('week', Link.created_at)
                    intervals = 52
                
                # Тренд ссылок
                now = datetime.now(timezone.utc)
                start_time = now - timedelta(days=intervals if period != AnalyticsPeriod.DAY else 1)
                
                links_trend = session.query(
                    date_trunc.label('period'),
                    func.count(Link.id).label('count')
                ).filter(
                    Link.created_at >= start_time
                ).group_by('period').order_by('period').all()
                
                # Тренд пользователей
                users_trend = session.query(
                    date_trunc.label('period'),
                    func.count(func.distinct(Link.user_id)).label('count')
                ).filter(
                    Link.created_at >= start_time
                ).group_by('period').order_by('period').all()
                
                return {
                    'links': [
                        {
                            'period': trend.period.isoformat(),
                            'count': trend.count
                        }
                        for trend in links_trend
                    ],
                    'active_users': [
                        {
                            'period': trend.period.isoformat(),
                            'count': trend.count
                        }
                        for trend in users_trend
                    ]
                }
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения трендов роста: {e}")
            return {'links': [], 'active_users': []}
    
    def generate_report(self, user_id: int = None, period: AnalyticsPeriod = AnalyticsPeriod.WEEK) -> str:
        """
        Генерация аналитического отчета
        
        Args:
            user_id: ID пользователя для персонального отчета (опционально)
            period: Период для отчета
            
        Returns:
            str: Отформатированный отчет
        """
        try:
            if user_id:
                return self._generate_user_report(user_id, period)
            else:
                return self._generate_community_report(period)
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации отчета: {e}")
            return "❌ Ошибка генерации отчета"
    
    def _generate_user_report(self, user_id: int, period: AnalyticsPeriod) -> str:
        """Генерация персонального отчета пользователя"""
        
        stats = self.get_user_stats(user_id)
        if not stats:
            return "❌ Пользователь не найден"
        
        period_name = self._get_period_name(period)
        display_name = stats.username or stats.first_name or f"User{stats.user_id}"
        
        report = f"""📊 **ЛИЧНАЯ СТАТИСТИКА**
👤 **Пользователь:** {display_name}

📈 **Активность за {period_name}:**
• Ссылок опубликовано: {self._get_period_value(stats, period, 'links')}
• Сообщений отправлено: {stats.total_messages}
• Последняя активность: {self.formatter.format_datetime(stats.last_activity)}

📊 **Общая статистика:**
• Всего ссылок: {stats.total_links_posted}
• Дата регистрации: {self.formatter.format_date(stats.registration_date)}"""

        # Добавляем карму если включена
        if config.ENABLE_PLAN_2_FEATURES and stats.current_karma is not None:
            report += f"""

🏆 **Карма:**
• Текущая карма: {stats.current_karma}
• Звание: {stats.karma_rank or 'Новенький'}
• Кармы выдано: {stats.total_karma_given}
• Кармы получено: {stats.total_karma_received}"""

        # Добавляем ИИ статистику если включена
        if config.ENABLE_PLAN_3_FEATURES:
            report += f"""

🤖 **ИИ взаимодействия:**
• Запросов к ИИ: {stats.ai_requests}
• Ответов получено: {stats.ai_responses_received}
• Авто-карма за благодарности: {stats.gratitude_auto_karma}"""

        return report
    
    def _generate_community_report(self, period: AnalyticsPeriod) -> str:
        """Генерация отчета сообщества"""
        
        stats = self.get_community_stats(period)
        period_name = self._get_period_name(period)
        
        report = f"""📊 **СТАТИСТИКА СООБЩЕСТВА**
⏰ **Период:** {period_name}

👥 **Пользователи:**
• Всего: {stats.total_users}
• Активных сегодня: {stats.active_users_today}
• Активных за неделю: {stats.active_users_week}
• Активных за месяц: {stats.active_users_month}

🔗 **Ссылки:**
• Всего: {stats.total_links}
• Сегодня: {stats.links_today}
• За неделю: {stats.links_week}
• За месяц: {stats.links_month}"""

        # Топ платформы
        if stats.platform_distribution:
            top_platforms = sorted(stats.platform_distribution.items(), key=lambda x: x[1], reverse=True)[:3]
            report += f"""

🎵 **Популярные платформы:**"""
            for platform, count in top_platforms:
                report += f"\n• {platform}: {count} ссылок"

        # Карма статистика
        if config.ENABLE_PLAN_2_FEATURES:
            report += f"""

🏆 **Карма:**
• Операций с кармой: {stats.total_karma_operations}
• Средняя карма: {stats.average_karma:.1f}
• Лидер по карме: {stats.top_karma_user or 'Нет данных'}"""

        # ИИ статистика
        if config.ENABLE_PLAN_3_FEATURES:
            report += f"""

🤖 **ИИ активность:**
• Запросов всего: {stats.total_ai_requests}
• Запросов сегодня: {stats.ai_requests_today}
• Среднее время ответа: {stats.average_response_time:.1f}с"""

        return report
    
    def _get_period_name(self, period: AnalyticsPeriod) -> str:
        """Получение названия периода на русском"""
        names = {
            AnalyticsPeriod.HOUR: "последний час",
            AnalyticsPeriod.DAY: "последние 24 часа",
            AnalyticsPeriod.WEEK: "последние 7 дней",
            AnalyticsPeriod.MONTH: "последние 30 дней",
            AnalyticsPeriod.YEAR: "последний год",
            AnalyticsPeriod.ALL_TIME: "всё время"
        }
        return names.get(period, "неизвестный период")
    
    def _get_period_value(self, stats: UserStats, period: AnalyticsPeriod, metric: str) -> int:
        """Получение значения метрики за период"""
        if metric == 'links':
            if period == AnalyticsPeriod.DAY:
                return stats.activity_today
            elif period == AnalyticsPeriod.WEEK:
                return stats.activity_week
            elif period == AnalyticsPeriod.MONTH:
                return stats.activity_month
            else:
                return stats.total_links_posted
        
        return 0
    
    def clear_cache(self):
        """Очистка кэша аналитики"""
        self._cache.clear()
        logger.info("🧹 Кэш аналитики очищен")

# ============================================
# ГЛОБАЛЬНЫЕ ФУНКЦИИ
# ============================================

# Глобальный экземпляр движка аналитики
_analytics_engine: Optional[AnalyticsEngine] = None

def get_analytics_engine() -> AnalyticsEngine:
    """Получение глобального экземпляра движка аналитики"""
    global _analytics_engine
    
    if _analytics_engine is None:
        _analytics_engine = AnalyticsEngine()
    
    return _analytics_engine

def init_analytics_engine() -> AnalyticsEngine:
    """Инициализация глобального движка аналитики"""
    global _analytics_engine
    
    _analytics_engine = AnalyticsEngine()
    logger.info("✅ Глобальный AnalyticsEngine инициализирован")
    
    return _analytics_engine

# Удобные функции для быстрого доступа
def get_user_stats(user_id: int) -> Optional[UserStats]:
    """Быстрое получение статистики пользователя"""
    return get_analytics_engine().get_user_stats(user_id)

def get_community_stats(period: AnalyticsPeriod = AnalyticsPeriod.ALL_TIME) -> CommunityStats:
    """Быстрое получение статистики сообщества"""
    return get_analytics_engine().get_community_stats(period)

def get_top_users(metric: str = "links", limit: int = 10) -> List[Dict[str, Any]]:
    """Быстрое получение топа пользователей"""
    return get_analytics_engine().get_top_users(metric, limit=limit)

def generate_user_report(user_id: int, period: AnalyticsPeriod = AnalyticsPeriod.WEEK) -> str:
    """Быстрая генерация отчета пользователя"""
    return get_analytics_engine().generate_report(user_id, period)

def generate_community_report(period: AnalyticsPeriod = AnalyticsPeriod.WEEK) -> str:
    """Быстрая генерация отчета сообщества"""
    return get_analytics_engine().generate_report(period=period)

# ============================================
# КОМАНДЫ ДЛЯ TELEGRAM БОТА
# ============================================

def handle_mystat_command(user_id: int) -> str:
    """
    Обработка команды /mystat
    
    Args:
        user_id: ID пользователя
        
    Returns:
        str: Отформатированная статистика
    """
    try:
        stats = get_user_stats(user_id)
        
        if not stats:
            return """❌ **Статистика недоступна**

Возможные причины:
• Вы еще не опубликовали ни одной ссылки
• Произошла ошибка при получении данных

💡 Опубликуйте ссылку на музыкальную платформу, чтобы начать накапливать статистику!"""
        
        return generate_user_report(user_id, AnalyticsPeriod.WEEK)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки команды /mystat: {e}")
        return "❌ Ошибка получения статистики. Попробуйте позже."

def handle_leaderboard_command(metric: str = "links") -> str:
    """
    Обработка команды рейтинга
    
    Args:
        metric: Метрика для рейтинга (links, karma, activity)
        
    Returns:
        str: Отформатированный рейтинг
    """
    try:
        top_users = get_top_users(metric, limit=10)
        
        if not top_users:
            return f"📊 **Рейтинг по {metric}**\n\nПока нет данных для отображения рейтинга."
        
        metric_names = {
            'links': 'ссылкам',
            'karma': 'карме',
            'activity': 'активности'
        }
        
        metric_name = metric_names.get(metric, metric)
        
        report = f"🏆 **ТОП-10 ПО {metric_name.upper()}**\n"
        
        for user in top_users:
            medal = "🥇" if user['rank'] == 1 else "🥈" if user['rank'] == 2 else "🥉" if user['rank'] == 3 else f"{user['rank']}."
            
            if metric == 'karma' and 'karma_rank' in user:
                report += f"\n{medal} **{user['display_name']}** — {user['value']} {user['metric']} ({user['karma_rank']})"
            else:
                report += f"\n{medal} **{user['display_name']}** — {user['value']} {user['metric']}"
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки команды рейтинга: {e}")
        return "❌ Ошибка получения рейтинга. Попробуйте позже."

# ============================================
# ТЕСТИРОВАНИЕ
# ============================================

if __name__ == "__main__":
    """Тестирование системы аналитики"""
    
    print("🧪 Тестирование AnalyticsEngine...")
    
    # Создание движка аналитики
    engine = AnalyticsEngine()
    
    # Тест получения статистики сообщества
    print("\n📊 Тест статистики сообщества:")
    community_stats = engine.get_community_stats()
    print(f"  Пользователей: {community_stats.total_users}")
    print(f"  Ссылок: {community_stats.total_links}")
    
    # Тест получения топа пользователей
    print("\n🏆 Тест топа пользователей:")
    top_users = engine.get_top_users("links", limit=5)
    for user in top_users[:3]:
        print(f"  {user['rank']}. {user['display_name']}: {user['value']} {user['metric']}")
    
    # Тест генерации отчета
    print("\n📋 Тест отчета сообщества:")
    report = engine.generate_report(period=AnalyticsPeriod.WEEK)
    print(report[:200] + "..." if len(report) > 200 else report)
    
    print("\n✅ Тестирование завершено")
