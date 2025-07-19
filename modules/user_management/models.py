"""
Modules/user_management/models.py - Модели базы данных
Do Presave Reminder Bot v29.07

SQLAlchemy модели для управления пользователями и системы кармы
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, DECIMAL, BigInteger, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from core.database_core import Base


class MusicUser(Base):
    """Модель пользователя музыкального сообщества"""
    __tablename__ = 'music_users'
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Идентификаторы
    group_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    
    # Информация о пользователе
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    
    # Система кармы и званий
    karma_points = Column(Integer, default=0, nullable=False, index=True)
    rank_title = Column(String(50), default='🥉 Новенький', nullable=False)
    
    # Статистика пресейвов и поддержки
    presaves_given = Column(Integer, default=0, nullable=False)
    presaves_received = Column(Integer, default=0, nullable=False)
    presave_ratio = Column(DECIMAL(5,2), default=0.0, nullable=False)
    links_published = Column(Integer, default=0, nullable=False)
    karma_to_links_ratio = Column(DECIMAL(5,2), default=0.0, nullable=False)
    
    # Персонализация
    music_genre = Column(String(50), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False, index=True)
    
    # WebApp интеграция
    webapp_last_visit = Column(DateTime, nullable=True)
    webapp_visit_count = Column(Integer, default=0, nullable=False)
    preferred_interface = Column(String(20), default='bot', nullable=False)
    
    # Метаданные
    registration_date = Column(DateTime, default=func.now(), nullable=False)
    last_activity = Column(DateTime, default=func.now(), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    def __repr__(self):
        return f"<MusicUser(user_id={self.user_id}, username='{self.username}', karma={self.karma_points})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'group_id': self.group_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'karma_points': self.karma_points,
            'rank_title': self.rank_title,
            'presaves_given': self.presaves_given,
            'presaves_received': self.presaves_received,
            'presave_ratio': float(self.presave_ratio),
            'links_published': self.links_published,
            'karma_to_links_ratio': float(self.karma_to_links_ratio),
            'music_genre': self.music_genre,
            'is_admin': self.is_admin,
            'webapp_last_visit': self.webapp_last_visit.isoformat() if self.webapp_last_visit else None,
            'webapp_visit_count': self.webapp_visit_count,
            'preferred_interface': self.preferred_interface,
            'registration_date': self.registration_date.isoformat() if self.registration_date else None,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MusicUser':
        """Создание из словаря"""
        user = cls()
        for key, value in data.items():
            if hasattr(user, key) and key not in ['id']:  # id автогенерируется
                if key in ['registration_date', 'last_activity', 'webapp_last_visit'] and value:
                    if isinstance(value, str):
                        value = datetime.fromisoformat(value)
                setattr(user, key, value)
        return user
    
    def get_display_name(self) -> str:
        """Получение отображаемого имени"""
        if self.username:
            return f"@{self.username}"
        elif self.first_name:
            return self.first_name
        else:
            return f"User_{self.user_id}"
    
    def get_rank_emoji(self) -> str:
        """Получение эмодзи звания"""
        rank_emojis = {
            'Новенький': '🥉',
            'Надежда сообщества': '🥈',
            'Мега-помощничье': '🥇',
            'Амбассадорище': '💎'
        }
        
        for rank_name, emoji in rank_emojis.items():
            if rank_name in self.rank_title:
                return emoji
        
        return '🎵'  # По умолчанию
    
    def get_karma_percentage(self, max_karma: int = 100500) -> float:
        """Получение процента кармы от максимума"""
        return (self.karma_points / max_karma) * 100
    
    def is_newbie(self) -> bool:
        """Проверка, является ли пользователь новичком"""
        return self.karma_points <= 5
    
    def can_change_karma(self, change_amount: int, max_karma: int = 100500) -> tuple[bool, Optional[str]]:
        """Проверка возможности изменения кармы"""
        new_karma = self.karma_points + change_amount
        
        if new_karma < 0:
            return False, "Карма не может быть отрицательной"
        
        if new_karma > max_karma:
            return False, f"Карма не может превышать {max_karma}"
        
        return True, None
    
    def update_activity(self):
        """Обновление времени последней активности"""
        self.last_activity = datetime.now()
    
    def update_webapp_visit(self):
        """Обновление данных о посещении WebApp"""
        self.webapp_last_visit = datetime.now()
        self.webapp_visit_count += 1


class KarmaHistory(Base):
    """История изменений кармы пользователей"""
    __tablename__ = 'karma_history'
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Связь с пользователем
    group_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    
    # Изменение кармы
    karma_change = Column(Integer, nullable=False)
    karma_before = Column(Integer, nullable=False)
    karma_after = Column(Integer, nullable=False)
    
    # Информация об изменении
    reason = Column(String(500), nullable=False)
    change_type = Column(String(50), default='manual', nullable=False)  # 'manual', 'auto', 'gratitude', 'penalty'
    
    # Кто изменил (для админских команд)
    changed_by_user_id = Column(BigInteger, nullable=True)
    changed_by_username = Column(String(100), nullable=True)
    
    # Дополнительные данные
    metadata = Column(Text, nullable=True)  # JSON строка с дополнительной информацией
    
    # Временные метки
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<KarmaHistory(user_id={self.user_id}, change={self.karma_change}, reason='{self.reason}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'group_id': self.group_id,
            'karma_change': self.karma_change,
            'karma_before': self.karma_before,
            'karma_after': self.karma_after,
            'reason': self.reason,
            'change_type': self.change_type,
            'changed_by_user_id': self.changed_by_user_id,
            'changed_by_username': self.changed_by_username,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def get_change_icon(self) -> str:
        """Получение иконки изменения"""
        if self.karma_change > 0:
            return "📈"
        elif self.karma_change < 0:
            return "📉"
        else:
            return "📊"
    
    def get_change_text(self) -> str:
        """Получение текста изменения"""
        if self.karma_change > 0:
            return f"+{self.karma_change}"
        else:
            return str(self.karma_change)
    
    def is_recent(self, hours: int = 24) -> bool:
        """Проверка, является ли изменение недавним"""
        if not self.created_at:
            return False
        
        time_diff = datetime.now() - self.created_at
        return time_diff.total_seconds() < (hours * 3600)


class UserStatistics(Base):
    """Ежедневная статистика пользователей"""
    __tablename__ = 'user_statistics'
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Связь с пользователем
    user_id = Column(BigInteger, nullable=False, index=True)
    group_id = Column(BigInteger, nullable=False, index=True)
    
    # Дата статистики
    stat_date = Column(Date, nullable=False, index=True)
    
    # Статистика активности за день
    messages_sent = Column(Integer, default=0, nullable=False)
    commands_used = Column(Integer, default=0, nullable=False)
    links_shared = Column(Integer, default=0, nullable=False)
    presaves_made = Column(Integer, default=0, nullable=False)
    karma_received = Column(Integer, default=0, nullable=False)
    karma_given = Column(Integer, default=0, nullable=False)
    
    # WebApp активность
    webapp_sessions = Column(Integer, default=0, nullable=False)
    webapp_time_spent = Column(Integer, default=0, nullable=False)  # в секундах
    
    # Временные метки
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<UserStatistics(user_id={self.user_id}, date={self.stat_date}, messages={self.messages_sent})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'group_id': self.group_id,
            'stat_date': self.stat_date.isoformat() if self.stat_date else None,
            'messages_sent': self.messages_sent,
            'commands_used': self.commands_used,
            'links_shared': self.links_shared,
            'presaves_made': self.presaves_made,
            'karma_received': self.karma_received,
            'karma_given': self.karma_given,
            'webapp_sessions': self.webapp_sessions,
            'webapp_time_spent': self.webapp_time_spent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_activity_score(self) -> float:
        """Расчет общего балла активности"""
        score = (
            self.messages_sent * 1 +
            self.commands_used * 2 +
            self.links_shared * 5 +
            self.presaves_made * 3 +
            self.karma_received * 2 +
            self.karma_given * 1.5 +
            self.webapp_sessions * 1
        )
        return score


class UserSession(Base):
    """Пользовательские сессии (для WebApp и состояний)"""
    __tablename__ = 'user_sessions'
    
    # Первичный ключ
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Идентификаторы
    session_id = Column(String(100), nullable=False, unique=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    group_id = Column(BigInteger, nullable=False, index=True)
    
    # Тип сессии
    session_type = Column(String(50), default='webapp', nullable=False)  # 'webapp', 'onboarding', 'form'
    session_data = Column(Text, nullable=True)  # JSON данные сессии
    
    # Статус и активность
    is_active = Column(Boolean, default=True, nullable=False)
    last_activity = Column(DateTime, default=func.now(), nullable=False, index=True)
    
    # Метаданные
    ip_address = Column(String(45), nullable=True)  # IPv6 поддержка
    user_agent = Column(String(500), nullable=True)
    platform = Column(String(50), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    
    def __repr__(self):
        return f"<UserSession(session_id='{self.session_id}', user_id={self.user_id}, type='{self.session_type}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'group_id': self.group_id,
            'session_type': self.session_type,
            'session_data': self.session_data,
            'is_active': self.is_active,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'platform': self.platform,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    def is_expired(self) -> bool:
        """Проверка истечения сессии"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at
    
    def extend_session(self, hours: int = 24):
        """Продление сессии"""
        self.expires_at = datetime.now() + timedelta(hours=hours)
        self.last_activity = datetime.now()
    
    def get_session_duration(self) -> timedelta:
        """Получение продолжительности сессии"""
        if not self.created_at:
            return timedelta(0)
        
        end_time = self.last_activity or datetime.now()
        return end_time - self.created_at


# === ИНДЕКСЫ И ОГРАНИЧЕНИЯ ===

# Составные индексы для оптимизации запросов
from sqlalchemy import Index

# Индекс для поиска пользователей по группе и карме
Index('idx_music_users_group_karma', MusicUser.group_id, MusicUser.karma_points)

# Индекс для истории кармы по пользователю и дате
Index('idx_karma_history_user_date', KarmaHistory.user_id, KarmaHistory.created_at)

# Индекс для статистики по пользователю и дате
Index('idx_user_statistics_user_date', UserStatistics.user_id, UserStatistics.stat_date)

# Индекс для активных сессий
Index('idx_user_sessions_active', UserSession.user_id, UserSession.is_active, UserSession.last_activity)


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def get_rank_title_by_karma(karma: int) -> str:
    """Получение звания по количеству кармы"""
    if karma >= 31:
        return "💎 Амбассадорище"
    elif karma >= 16:
        return "🥇 Мега-помощничье"
    elif karma >= 6:
        return "🥈 Надежда сообщества"
    else:
        return "🥉 Новенький"


def calculate_presave_ratio(given: int, received: int) -> float:
    """Расчет соотношения пресейвов дал/получил"""
    if received == 0:
        return float(given)
    return round(given / received, 2)


def calculate_karma_links_ratio(karma: int, links: int) -> float:
    """Расчет соотношения карма/ссылки"""
    if links == 0:
        return float(karma)
    return round(karma / links, 2)


def is_valid_karma_value(karma: int, min_karma: int = 0, max_karma: int = 100500) -> bool:
    """Проверка валидности значения кармы"""
    return min_karma <= karma <= max_karma


def get_karma_change_reason(change_type: str, change_amount: int, context: str = "") -> str:
    """Генерация причины изменения кармы"""
    reasons = {
        'manual': f"Ручное изменение на {change_amount:+d}",
        'auto': f"Автоматическое начисление {change_amount:+d}",
        'gratitude': f"Благодарность (+{change_amount})",
        'penalty': f"Штраф ({change_amount})",
        'admin_adjustment': f"Корректировка админа ({change_amount:+d})",
        'system_bonus': f"Системный бонус (+{change_amount})"
    }
    
    base_reason = reasons.get(change_type, f"Изменение на {change_amount:+d}")
    
    if context:
        base_reason += f" | {context}"
    
    return base_reason


if __name__ == "__main__":
    # Тестирование моделей
    print("🧪 Тестирование моделей пользователей...")
    
    # Создаем тестового пользователя
    user = MusicUser(
        user_id=12345,
        group_id=-1001234567890,
        username="test_user",
        first_name="Тест",
        last_name="Пользователь",
        music_genre="Рок",
        karma_points=10
    )
    
    print(f"👤 Пользователь: {user}")
    print(f"📊 Словарь: {user.to_dict()}")
    print(f"🏆 Звание: {get_rank_title_by_karma(user.karma_points)}")
    print(f"📈 Процент кармы: {user.get_karma_percentage():.1f}%")
    
    # Тестируем историю кармы
    karma_entry = KarmaHistory(
        user_id=12345,
        group_id=-1001234567890,
        karma_change=5,
        karma_before=10,
        karma_after=15,
        reason="Помощь новичку",
        change_type="gratitude"
    )
    
    print(f"📈 История кармы: {karma_entry}")
    print(f"🎯 Иконка изменения: {karma_entry.get_change_icon()}")
    
    print("✅ Тестирование моделей завершено")