"""
🗃️ Database Models - Do Presave Reminder Bot v25+
Модели данных для всех 4 планов развития с использованием SQLAlchemy ORM
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, JSON, BigInteger, Float, Enum as SQLEnum,
    Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
import enum

# Базовый класс для всех моделей
Base = declarative_base()

# ============================================
# ENUMS ДЛЯ ТИПИЗАЦИИ
# ============================================

class UserRank(enum.Enum):
    """Звания пользователей для системы кармы (План 2)"""
    NEWBIE = "🥉 Новенький"           # 0-5 кармы
    HOPE = "🥈 Надежда сообщества"    # 6-15 кармы
    MEGA = "🥇 Мега-человечище"       # 16-30 кармы
    AMBASSADOR = "💎 Амбассадорище"   # 31+ кармы

class PresaveRequestStatus(enum.Enum):
    """Статусы заявок на пресейвы (План 3)"""
    PENDING = "pending"      # Ожидает обработки
    APPROVED = "approved"    # Одобрена
    REJECTED = "rejected"    # Отклонена
    EXPIRED = "expired"      # Истекла

class ApprovalClaimStatus(enum.Enum):
    """Статусы заявок на аппрувы (План 3)"""
    SUBMITTED = "submitted"   # Подана
    REVIEWING = "reviewing"   # На рассмотрении
    APPROVED = "approved"     # Одобрена (+карма)
    REJECTED = "rejected"     # Отклонена
    EXPIRED = "expired"       # Истекла

class FormState(enum.Enum):
    """Состояния интерактивных форм (План 3)"""
    IDLE = "idle"                              # Неактивен
    ASKING_PRESAVE_DESCRIPTION = "asking_description"  # Запрос описания пресейва
    ASKING_PRESAVE_LINKS = "asking_links"              # Запрос ссылок
    ASKING_CLAIM_SCREENSHOTS = "asking_screenshots"    # Запрос скриншотов
    ASKING_CLAIM_COMMENT = "asking_comment"            # Запрос комментария

# ============================================
# ПЛАН 1 - БАЗОВЫЕ МОДЕЛИ
# ============================================

class User(Base):
    """Пользователи бота - центральная таблица для всех планов"""
    __tablename__ = 'users'
    
    # Основные поля
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Метаданные
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    language_code = Column(String(10), default='ru')
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    last_activity = Column(DateTime(timezone=True), default=func.now())
    
    # Связи с другими таблицами (будут активны при включении соответствующих планов)
    # План 1: Ссылки пользователя
    links = relationship("Link", back_populates="user", lazy="dynamic")
    
    # План 2: Карма пользователя  
    karma_record = relationship("UserKarma", back_populates="user", uselist=False)
    karma_changes_given = relationship("KarmaHistory", foreign_keys="KarmaHistory.admin_id", back_populates="admin")
    karma_changes_received = relationship("KarmaHistory", foreign_keys="KarmaHistory.user_id", back_populates="user")
    
    # План 3: Формы и ИИ
    presave_requests = relationship("PresaveRequest", back_populates="user", lazy="dynamic")
    approval_claims = relationship("ApprovalClaim", back_populates="user", lazy="dynamic")
    form_sessions = relationship("FormSession", back_populates="user", lazy="dynamic")
    ai_conversations = relationship("AIConversation", back_populates="user", lazy="dynamic")
    
    # Индексы для производительности
    __table_args__ = (
        Index('idx_users_telegram_id', 'telegram_id'),
        Index('idx_users_username', 'username'),
        Index('idx_users_active', 'is_active'),
        Index('idx_users_admin', 'is_admin'),
    )
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}')>"

class BotSettings(Base):
    """Настройки бота - глобальные состояния"""
    __tablename__ = 'bot_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    value_type = Column(String(20), default='string')  # string, int, bool, json
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_settings_key', 'key'),
    )
    
    def __repr__(self):
        return f"<BotSettings(key='{self.key}', value='{self.value}')>"

class Link(Base):
    """Ссылки пользователей - основа для отслеживания пресейвов"""
    __tablename__ = 'links'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Данные сообщения
    message_id = Column(BigInteger, nullable=False)
    thread_id = Column(Integer, nullable=True)  # ID топика для супергрупп
    url = Column(Text, nullable=False)
    message_text = Column(Text, nullable=True)
    
    # Метаданные
    domain = Column(String(255), nullable=True, index=True)  # Извлеченный домен для аналитики
    is_presave_request = Column(Boolean, default=True)  # Является ли это просьбой о пресейве
    
    # Временные метки  
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Связи
    user = relationship("User", back_populates="links")
    
    # Индексы для производительности
    __table_args__ = (
        Index('idx_links_user_id', 'user_id'),
        Index('idx_links_created_at', 'created_at'),
        Index('idx_links_thread_id', 'thread_id'),
        Index('idx_links_domain', 'domain'),
        Index('idx_links_is_presave_request', 'is_presave_request'),
    )
    
    def __repr__(self):
        return f"<Link(user_id={self.user_id}, url='{self.url[:50]}...')>"

# ============================================
# ПЛАН 2 - МОДЕЛИ СИСТЕМЫ КАРМЫ
# ============================================

class UserKarma(Base):
    """Карма пользователей - система мотивации и репутации"""
    __tablename__ = 'user_karma'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    
    # Основные метрики кармы
    karma_points = Column(Integer, default=0, nullable=False)
    rank = Column(SQLEnum(UserRank), default=UserRank.NEWBIE, nullable=False)
    
    # Дополнительная статистика
    total_karma_received = Column(Integer, default=0)  # Всего получено кармы
    total_karma_given = Column(Integer, default=0)     # Всего роздано кармы (для админов)
    presave_requests_count = Column(Integer, default=0) # Количество просьб о пресейвах
    approved_presaves_count = Column(Integer, default=0) # Подтвержденных пресейвов
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    last_karma_change = Column(DateTime(timezone=True), default=func.now())
    
    # Связи
    user = relationship("User", back_populates="karma_record")
    
    # Ограничения
    __table_args__ = (
        CheckConstraint('karma_points >= 0', name='check_karma_non_negative'),
        CheckConstraint('karma_points <= 100500', name='check_karma_max_limit'),
        Index('idx_user_karma_user_id', 'user_id'),
        Index('idx_user_karma_points', 'karma_points'),
        Index('idx_user_karma_rank', 'rank'),
    )
    
    def __repr__(self):
        return f"<UserKarma(user_id={self.user_id}, karma={self.karma_points}, rank={self.rank.value})>"

class KarmaHistory(Base):
    """История изменений кармы - аудит всех операций"""
    __tablename__ = 'karma_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # NULL для автоматических начислений
    
    # Детали изменения
    change_amount = Column(Integer, nullable=False)  # Может быть отрицательным
    reason = Column(String(500), nullable=True)      # Причина изменения
    context_data = Column(JSON, nullable=True)       # Дополнительные данные (message_id, etc.)
    
    # Состояние до и после
    karma_before = Column(Integer, nullable=False)
    karma_after = Column(Integer, nullable=False)
    rank_before = Column(SQLEnum(UserRank), nullable=True)
    rank_after = Column(SQLEnum(UserRank), nullable=True)
    
    # Тип операции
    is_automatic = Column(Boolean, default=False)  # Автоматическое начисление (благодарности)
    is_manual = Column(Boolean, default=True)      # Ручное начисление админом
    
    # Временная метка
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="karma_changes_received")
    admin = relationship("User", foreign_keys=[admin_id], back_populates="karma_changes_given")
    
    # Индексы
    __table_args__ = (
        Index('idx_karma_history_user_id', 'user_id'),
        Index('idx_karma_history_admin_id', 'admin_id'),
        Index('idx_karma_history_created_at', 'created_at'),
        Index('idx_karma_history_automatic', 'is_automatic'),
    )
    
    def __repr__(self):
        return f"<KarmaHistory(user_id={self.user_id}, change={self.change_amount}, admin_id={self.admin_id})>"

# ============================================
# ПЛАН 3 - МОДЕЛИ ИНТЕРАКТИВНЫХ ФОРМ И ИИ
# ============================================

class PresaveRequest(Base):
    """Заявки на пресейвы - интерактивные формы подачи"""
    __tablename__ = 'presave_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Содержимое заявки
    title = Column(String(500), nullable=True)        # Название релиза
    description = Column(Text, nullable=True)         # Описание
    links = Column(JSON, nullable=False)              # Список ссылок
    additional_info = Column(Text, nullable=True)     # Дополнительная информация
    
    # Метаданные обработки
    status = Column(SQLEnum(PresaveRequestStatus), default=PresaveRequestStatus.PENDING)
    message_id = Column(BigInteger, nullable=True)    # ID сообщения в топике
    thread_id = Column(Integer, nullable=True)        # ID топика
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    user = relationship("User", back_populates="presave_requests")
    
    # Индексы
    __table_args__ = (
        Index('idx_presave_requests_user_id', 'user_id'),
        Index('idx_presave_requests_status', 'status'),
        Index('idx_presave_requests_created_at', 'created_at'),
        Index('idx_presave_requests_thread_id', 'thread_id'),
    )
    
    def __repr__(self):
        return f"<PresaveRequest(user_id={self.user_id}, status={self.status.value})>"

class ApprovalClaim(Base):
    """Заявки на аппрувы - подтверждения сделанных пресейвов"""
    __tablename__ = 'approval_claims'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # Кто обрабатывал
    
    # Данные заявки
    comment = Column(Text, nullable=True)             # Комментарий пользователя
    presave_link = Column(Text, nullable=True)        # Ссылка на пресейв (опционально)
    
    # Метаданные обработки
    status = Column(SQLEnum(ApprovalClaimStatus), default=ApprovalClaimStatus.SUBMITTED)
    karma_awarded = Column(Integer, default=0)        # Сколько кармы было начислено
    admin_comment = Column(Text, nullable=True)       # Комментарий админа
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    user = relationship("User", back_populates="approval_claims")
    admin = relationship("User", foreign_keys=[admin_id])
    screenshots = relationship("ClaimScreenshot", back_populates="claim", lazy="dynamic")
    
    # Индексы
    __table_args__ = (
        Index('idx_approval_claims_user_id', 'user_id'),
        Index('idx_approval_claims_admin_id', 'admin_id'),
        Index('idx_approval_claims_status', 'status'),
        Index('idx_approval_claims_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<ApprovalClaim(user_id={self.user_id}, status={self.status.value})>"

class ClaimScreenshot(Base):
    """Скриншоты к заявкам на аппрувы"""
    __tablename__ = 'claim_screenshots'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey('approval_claims.id'), nullable=False)
    
    # Данные файла
    file_id = Column(String(255), nullable=False)     # Telegram file_id
    file_unique_id = Column(String(255), nullable=True) # Telegram file_unique_id
    file_size = Column(Integer, nullable=True)        # Размер файла в байтах
    file_path = Column(String(500), nullable=True)    # Путь к загруженному файлу
    
    # Метаданные
    caption = Column(Text, nullable=True)             # Подпись к скриншоту
    is_verified = Column(Boolean, default=False)     # Проверен админом
    
    # Временная метка
    uploaded_at = Column(DateTime(timezone=True), default=func.now())
    
    # Связи
    claim = relationship("ApprovalClaim", back_populates="screenshots")
    
    # Индексы
    __table_args__ = (
        Index('idx_claim_screenshots_claim_id', 'claim_id'),
        Index('idx_claim_screenshots_file_id', 'file_id'),
    )
    
    def __repr__(self):
        return f"<ClaimScreenshot(claim_id={self.claim_id}, file_id='{self.file_id}')>"

class FormSession(Base):
    """Сессии интерактивных форм - управление состояниями"""
    __tablename__ = 'form_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Состояние формы
    current_state = Column(SQLEnum(FormState), default=FormState.IDLE, nullable=False)
    form_type = Column(String(50), nullable=True)     # 'presave_request', 'approval_claim'
    
    # Данные сессии
    session_data = Column(JSON, default=dict)         # Временные данные формы
    last_message_id = Column(BigInteger, nullable=True) # ID последнего сообщения
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связи
    user = relationship("User", back_populates="form_sessions")
    
    # Ограничения: один активный сеанс на пользователя
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_form_sessions_user_id'),
        Index('idx_form_sessions_user_id', 'user_id'),
        Index('idx_form_sessions_state', 'current_state'),
        Index('idx_form_sessions_expires_at', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<FormSession(user_id={self.user_id}, state={self.current_state.value})>"

class AIConversation(Base):
    """Беседы с ИИ - история взаимодействий"""
    __tablename__ = 'ai_conversations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Данные беседы
    message_id = Column(BigInteger, nullable=True)     # ID сообщения Telegram
    user_message = Column(Text, nullable=False)       # Сообщение пользователя
    ai_response = Column(Text, nullable=True)         # Ответ ИИ
    
    # Метаданные ИИ
    ai_model = Column(String(100), nullable=True)     # Использованная модель
    tokens_used = Column(Integer, default=0)          # Потрачено токенов
    response_time_ms = Column(Integer, nullable=True) # Время ответа в мс
    
    # Контекст
    context_data = Column(JSON, nullable=True)        # Дополнительный контекст
    is_mention = Column(Boolean, default=False)       # Было ли упоминание бота
    is_reply = Column(Boolean, default=False)         # Был ли это reply
    is_private = Column(Boolean, default=False)       # Личное сообщение
    
    # Временная метка
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Связи
    user = relationship("User", back_populates="ai_conversations")
    
    # Индексы
    __table_args__ = (
        Index('idx_ai_conversations_user_id', 'user_id'),
        Index('idx_ai_conversations_created_at', 'created_at'),
        Index('idx_ai_conversations_ai_model', 'ai_model'),
        Index('idx_ai_conversations_is_mention', 'is_mention'),
    )
    
    def __repr__(self):
        return f"<AIConversation(user_id={self.user_id}, model='{self.ai_model}')>"

class AutoKarmaLog(Base):
    """Лог автоматических начислений кармы за благодарности"""
    __tablename__ = 'auto_karma_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # Кто поблагодарил
    to_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)    # Кому начислили карму
    
    # Детали благодарности
    trigger_word = Column(String(100), nullable=False)    # Слово-триггер
    message_text = Column(Text, nullable=True)            # Полный текст сообщения
    reply_message_id = Column(BigInteger, nullable=True)  # ID исходного сообщения
    
    # Результат
    karma_added = Column(Integer, default=1)              # Сколько кармы начислено
    processed = Column(Boolean, default=True)             # Обработано ли успешно
    
    # Временная метка
    timestamp = Column(DateTime(timezone=True), default=func.now())
    
    # Связи
    from_user = relationship("User", foreign_keys=[from_user_id])
    to_user = relationship("User", foreign_keys=[to_user_id])
    
    # Индексы
    __table_args__ = (
        Index('idx_auto_karma_log_from_user', 'from_user_id'),
        Index('idx_auto_karma_log_to_user', 'to_user_id'),
        Index('idx_auto_karma_log_timestamp', 'timestamp'),
        Index('idx_auto_karma_log_trigger_word', 'trigger_word'),
    )
    
    def __repr__(self):
        return f"<AutoKarmaLog(from={self.from_user_id}, to={self.to_user_id}, word='{self.trigger_word}')>"

# ============================================
# ПЛАН 4 - МОДЕЛИ BACKUP СИСТЕМЫ
# ============================================

class BackupHistory(Base):
    """История backup операций"""
    __tablename__ = 'backup_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Данные backup
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=True)
    compression_ratio = Column(Float, nullable=True)
    
    # Метаданные
    backup_type = Column(String(50), default='manual')   # manual, automatic
    tables_included = Column(JSON, nullable=True)        # Список таблиц
    rows_exported = Column(Integer, nullable=True)       # Всего записей
    
    # Статус
    status = Column(String(20), default='completed')     # completed, failed, in_progress
    error_message = Column(Text, nullable=True)          # Ошибка, если была
    
    # Временные метки
    started_at = Column(DateTime(timezone=True), default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Индексы
    __table_args__ = (
        Index('idx_backup_history_started_at', 'started_at'),
        Index('idx_backup_history_status', 'status'),
        Index('idx_backup_history_backup_type', 'backup_type'),
    )
    
    def __repr__(self):
        return f"<BackupHistory(filename='{self.filename}', status='{self.status}')>"

class MessageStats(Base):
    """Статистика сообщений пользователей по топикам"""
    __tablename__ = 'message_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    thread_id = Column(Integer, nullable=False)
    
    # Статистика
    message_count = Column(Integer, default=0)
    last_message_at = Column(DateTime(timezone=True), default=func.now())
    first_message_at = Column(DateTime(timezone=True), default=func.now())
    
    # Дополнительные метрики
    links_shared = Column(Integer, default=0)
    gratitude_received = Column(Integer, default=0)  # Получено благодарностей
    gratitude_given = Column(Integer, default=0)     # Дано благодарностей
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Связи
    user = relationship("User")
    
    # Ограничения
    __table_args__ = (
        UniqueConstraint('user_id', 'thread_id', name='uq_message_stats_user_thread'),
        Index('idx_message_stats_user_id', 'user_id'),
        Index('idx_message_stats_thread_id', 'thread_id'),
        Index('idx_message_stats_message_count', 'message_count'),
        Index('idx_message_stats_last_message_at', 'last_message_at'),
    )
    
    def __repr__(self):
        return f"<MessageStats(user_id={self.user_id}, thread_id={self.thread_id}, count={self.message_count})>"

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def get_all_tables():
    """Получение списка всех таблиц для миграций"""
    return [
        # План 1 - Базовые таблицы
        User.__tablename__,
        BotSettings.__tablename__,
        Link.__tablename__,
        
        # План 2 - Система кармы
        UserKarma.__tablename__,
        KarmaHistory.__tablename__,
        
        # План 3 - Интерактивные формы и ИИ
        PresaveRequest.__tablename__,
        ApprovalClaim.__tablename__,
        ClaimScreenshot.__tablename__,
        FormSession.__tablename__,
        AIConversation.__tablename__,
        AutoKarmaLog.__tablename__,
        
        # План 4 - Backup система
        BackupHistory.__tablename__,
        MessageStats.__tablename__,
    ]

def get_plan_tables(plan_number: int):
    """Получение таблиц для конкретного плана"""
    plan_tables = {
        1: [User.__tablename__, BotSettings.__tablename__, Link.__tablename__],
        2: [UserKarma.__tablename__, KarmaHistory.__tablename__],
        3: [PresaveRequest.__tablename__, ApprovalClaim.__tablename__, 
            ClaimScreenshot.__tablename__, FormSession.__tablename__, 
            AIConversation.__tablename__, AutoKarmaLog.__tablename__],
        4: [BackupHistory.__tablename__, MessageStats.__tablename__]
    }
    return plan_tables.get(plan_number, [])

def get_user_rank_by_karma(karma_points: int) -> UserRank:
    """Определение звания по количеству кармы"""
    if karma_points >= 31:
        return UserRank.AMBASSADOR
    elif karma_points >= 16:
        return UserRank.MEGA
    elif karma_points >= 6:
        return UserRank.HOPE
    else:
        return UserRank.NEWBIE

def get_karma_threshold_for_next_rank(current_karma: int) -> Optional[int]:
    """Получение порога для следующего звания"""
    thresholds = [6, 16, 31]
    for threshold in thresholds:
        if current_karma < threshold:
            return threshold
    return None  # Уже максимальное звание

# Экспорт всех моделей
__all__ = [
    'Base',
    # Enums
    'UserRank', 'PresaveRequestStatus', 'ApprovalClaimStatus', 'FormState',
    # План 1
    'User', 'BotSettings', 'Link',
    # План 2
    'UserKarma', 'KarmaHistory',
    # План 3
    'PresaveRequest', 'ApprovalClaim', 'ClaimScreenshot', 'FormSession', 
    'AIConversation', 'AutoKarmaLog',
    # План 4
    'BackupHistory', 'MessageStats',
    # Утилиты
    'get_all_tables', 'get_plan_tables', 'get_user_rank_by_karma', 'get_karma_threshold_for_next_rank'
]
