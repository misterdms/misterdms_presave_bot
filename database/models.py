"""
Модели базы данных Do Presave Reminder Bot v25+
SQLAlchemy модели для всех планов развития

ПЛАН 1: Базовые таблицы (АКТИВНЫЕ)
ПЛАН 2: Система кармы (ЗАГЛУШКИ)  
ПЛАН 3: ИИ и формы (ЗАГЛУШКИ)
ПЛАН 4: Backup система (ЗАГЛУШКИ)
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    ForeignKey, Index, JSON, Float, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Базовый класс для всех моделей
Base = declarative_base()

# ============================================
# ПЛАН 1: БАЗОВЫЕ МОДЕЛИ (АКТИВНЫЕ)
# ============================================

class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)  # Telegram user_id
    username = Column(String(32), nullable=True, index=True)
    first_name = Column(String(256), nullable=True)
    last_name = Column(String(256), nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Метаданные
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    
    # ПЛАН 1: Связи с таблицами ссылок
    links = relationship("Link", back_populates="user", cascade="all, delete-orphan")
    
    # ПЛАН 2: Связи с кармой (ЗАГЛУШКИ)
    # karma_record = relationship("UserKarma", back_populates="user", uselist=False)
    # karma_changes_given = relationship("KarmaHistory", foreign_keys="KarmaHistory.admin_id", back_populates="admin")
    # karma_changes_received = relationship("KarmaHistory", foreign_keys="KarmaHistory.user_id", back_populates="user")
    
    # ПЛАН 3: Связи с формами и ИИ (ЗАГЛУШКИ)
    # presave_requests = relationship("PresaveRequest", back_populates="user")
    # approval_claims = relationship("ApprovalClaim", back_populates="user")
    # ai_interactions = relationship("AIInteraction", back_populates="user")
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, username={self.username})>"


class Link(Base):
    """Модель ссылок пользователей"""
    __tablename__ = 'links'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    
    # Данные ссылки
    url = Column(Text, nullable=False)
    message_text = Column(Text, nullable=True)  # Полный текст сообщения
    message_id = Column(Integer, nullable=True)  # ID сообщения в Telegram
    thread_id = Column(Integer, nullable=True, index=True)  # ID топика
    
    # Метаданные
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Связи
    user = relationship("User", back_populates="links")
    
    def __repr__(self):
        return f"<Link(id={self.id}, user_id={self.user_id}, url={self.url[:50]}...)>"


class Settings(Base):
    """Настройки бота"""
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    value_type = Column(String(20), default='string', nullable=False)  # string, int, bool, json
    description = Column(Text, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(Integer, nullable=True)  # admin user_id
    
    def __repr__(self):
        return f"<Settings(key={self.key}, value={self.value})>"


# ============================================
# ПЛАН 2: СИСТЕМА КАРМЫ (ЗАГЛУШКИ)
# ============================================

# class UserKarma(Base):
#     """Карма пользователей"""
#     __tablename__ = 'user_karma'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, ForeignKey('users.user_id'), unique=True, nullable=False, index=True)
#     
#     # Карма и звание
#     karma_points = Column(Integer, default=0, nullable=False, index=True)
#     rank = Column(String(50), default='Новенький', nullable=False)
#     
#     # Статистика
#     total_requests = Column(Integer, default=0, nullable=False)  # Количество просьб о пресейвах
#     total_approvals = Column(Integer, default=0, nullable=False)  # Подтвержденные пресейвы
#     
#     # Метаданные
#     created_at = Column(DateTime, default=func.now(), nullable=False)
#     updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
#     
#     # Связи
#     user = relationship("User", back_populates="karma_record")
#     
#     def __repr__(self):
#         return f"<UserKarma(user_id={self.user_id}, karma={self.karma_points}, rank={self.rank})>"


# class KarmaHistory(Base):
#     """История изменений кармы"""
#     __tablename__ = 'karma_history'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
#     admin_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
#     
#     # Изменение кармы
#     change_amount = Column(Integer, nullable=False)  # Может быть отрицательным
#     old_karma = Column(Integer, nullable=False)
#     new_karma = Column(Integer, nullable=False)
#     reason = Column(Text, nullable=True)
#     
#     # Метаданные
#     timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
#     
#     # Связи
#     user = relationship("User", foreign_keys=[user_id], back_populates="karma_changes_received")
#     admin = relationship("User", foreign_keys=[admin_id], back_populates="karma_changes_given")
#     
#     def __repr__(self):
#         return f"<KarmaHistory(user_id={self.user_id}, change={self.change_amount}, admin={self.admin_id})>"


# ============================================
# ПЛАН 3: ИИ И ИНТЕРАКТИВНЫЕ ФОРМЫ (ЗАГЛУШКИ)
# ============================================

# class PresaveRequest(Base):
#     """Заявки на пресейвы"""
#     __tablename__ = 'presave_requests'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
#     
#     # Данные заявки
#     description = Column(Text, nullable=False)
#     links = Column(JSON, nullable=True)  # Список ссылок в JSON
#     status = Column(String(20), default='active', nullable=False, index=True)  # active, closed, spam
#     
#     # Telegram данные
#     message_id = Column(Integer, nullable=True)
#     thread_id = Column(Integer, nullable=True)
#     
#     # Метаданные
#     created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
#     updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
#     
#     # Связи
#     user = relationship("User", back_populates="presave_requests")
#     approval_claims = relationship("ApprovalClaim", back_populates="presave_request")
#     
#     def __repr__(self):
#         return f"<PresaveRequest(id={self.id}, user_id={self.user_id}, status={self.status})>"


# class ApprovalClaim(Base):
#     """Заявки о совершенных пресейвах"""
#     __tablename__ = 'approval_claims'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
#     presave_request_id = Column(Integer, ForeignKey('presave_requests.id'), nullable=True, index=True)
#     
#     # Данные заявки
#     comment = Column(Text, nullable=True)
#     screenshots_count = Column(Integer, default=0, nullable=False)
#     
#     # Статус модерации
#     status = Column(String(20), default='pending', nullable=False, index=True)  # pending, approved, rejected
#     admin_id = Column(Integer, ForeignKey('users.user_id'), nullable=True, index=True)
#     admin_comment = Column(Text, nullable=True)
#     
#     # Метаданные
#     created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
#     processed_at = Column(DateTime, nullable=True)
#     
#     # Связи
#     user = relationship("User", back_populates="approval_claims")
#     presave_request = relationship("PresaveRequest", back_populates="approval_claims")
#     admin = relationship("User", foreign_keys=[admin_id])
#     screenshots = relationship("ClaimScreenshot", back_populates="claim", cascade="all, delete-orphan")
#     
#     def __repr__(self):
#         return f"<ApprovalClaim(id={self.id}, user_id={self.user_id}, status={self.status})>"


# class ClaimScreenshot(Base):
#     """Скриншоты к заявкам о пресейвах"""
#     __tablename__ = 'claim_screenshots'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     claim_id = Column(Integer, ForeignKey('approval_claims.id'), nullable=False, index=True)
#     
#     # Telegram файл
#     file_id = Column(String(200), nullable=False)
#     file_path = Column(String(500), nullable=True)
#     file_size = Column(Integer, nullable=True)
#     
#     # Метаданные
#     uploaded_at = Column(DateTime, default=func.now(), nullable=False)
#     
#     # Связи
#     claim = relationship("ApprovalClaim", back_populates="screenshots")
#     
#     def __repr__(self):
#         return f"<ClaimScreenshot(id={self.id}, claim_id={self.claim_id}, file_id={self.file_id})>"


# class AIInteraction(Base):
#     """Взаимодействия с ИИ"""
#     __tablename__ = 'ai_interactions'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
#     
#     # Данные взаимодействия
#     prompt = Column(Text, nullable=False)
#     response = Column(Text, nullable=True)
#     model = Column(String(50), nullable=False)
#     
#     # Метрики токенов
#     prompt_tokens = Column(Integer, nullable=True)
#     completion_tokens = Column(Integer, nullable=True)
#     total_tokens = Column(Integer, nullable=True)
#     
#     # Контекст
#     context_type = Column(String(50), nullable=True)  # mention, reply, private
#     message_id = Column(Integer, nullable=True)
#     thread_id = Column(Integer, nullable=True)
#     
#     # Метаданные
#     created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
#     response_time_ms = Column(Integer, nullable=True)
#     
#     # Связи
#     user = relationship("User", back_populates="ai_interactions")
#     
#     def __repr__(self):
#         return f"<AIInteraction(id={self.id}, user_id={self.user_id}, model={self.model})>"


# class AutoKarmaLog(Base):
#     """Лог автоматических начислений кармы"""
#     __tablename__ = 'auto_karma_log'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     from_user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
#     to_user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
#     
#     # Данные о благодарности
#     trigger_word = Column(String(100), nullable=False)
#     context = Column(Text, nullable=True)  # Полный текст сообщения
#     karma_added = Column(Integer, default=1, nullable=False)
#     
#     # Telegram данные
#     message_id = Column(Integer, nullable=True)
#     thread_id = Column(Integer, nullable=True)
#     
#     # Метаданные
#     timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
#     
#     # Связи
#     from_user = relationship("User", foreign_keys=[from_user_id])
#     to_user = relationship("User", foreign_keys=[to_user_id])
#     
#     def __repr__(self):
#         return f"<AutoKarmaLog(from={self.from_user_id}, to={self.to_user_id}, word={self.trigger_word})>"


# class MessageStats(Base):
#     """Статистика сообщений по топикам"""
#     __tablename__ = 'message_stats'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
#     thread_id = Column(Integer, nullable=False, index=True)
#     
#     # Статистика
#     message_count = Column(Integer, default=0, nullable=False)
#     last_message_at = Column(DateTime, nullable=True)
#     
#     # Метаданные
#     created_at = Column(DateTime, default=func.now(), nullable=False)
#     updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
#     
#     # Связи
#     user = relationship("User")
#     
#     def __repr__(self):
#         return f"<MessageStats(user_id={self.user_id}, thread_id={self.thread_id}, count={self.message_count})>"


# ============================================
# ПЛАН 4: BACKUP СИСТЕМА (ЗАГЛУШКИ)
# ============================================

# class BackupHistory(Base):
#     """История backup операций"""
#     __tablename__ = 'backup_history'
#     
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     
#     # Данные backup
#     filename = Column(String(255), nullable=False)
#     file_size_mb = Column(Float, nullable=True)
#     backup_type = Column(String(20), default='manual', nullable=False)  # manual, auto
#     
#     # Метаданные
#     created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
#     created_by = Column(Integer, ForeignKey('users.user_id'), nullable=True)
#     
#     # Статистика
#     tables_count = Column(Integer, nullable=True)
#     records_count = Column(Integer, nullable=True)
#     compression_ratio = Column(Float, nullable=True)
#     
#     # Связи
#     creator = relationship("User")
#     
#     def __repr__(self):
#         return f"<BackupHistory(id={self.id}, filename={self.filename}, size={self.file_size_mb}MB)>"


# ============================================
# ИНДЕКСЫ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ
# ============================================

# Индексы для ПЛАН 1 (АКТИВНЫЕ)
Index('idx_users_user_id', User.user_id)
Index('idx_users_username', User.username)
Index('idx_links_user_id_created', Link.user_id, Link.created_at)
Index('idx_links_thread_id', Link.thread_id)
Index('idx_settings_key', Settings.key)

# ПЛАН 2: Индексы для кармы (ЗАГЛУШКИ)
# Index('idx_karma_user_id', UserKarma.user_id)
# Index('idx_karma_points', UserKarma.karma_points)
# Index('idx_karma_history_user_timestamp', KarmaHistory.user_id, KarmaHistory.timestamp)
# Index('idx_karma_history_admin', KarmaHistory.admin_id)

# ПЛАН 3: Индексы для ИИ и форм (ЗАГЛУШКИ)
# Index('idx_presave_requests_user_status', PresaveRequest.user_id, PresaveRequest.status)
# Index('idx_approval_claims_status_created', ApprovalClaim.status, ApprovalClaim.created_at)
# Index('idx_ai_interactions_user_created', AIInteraction.user_id, AIInteraction.created_at)
# Index('idx_auto_karma_to_user_timestamp', AutoKarmaLog.to_user_id, AutoKarmaLog.timestamp)

# ПЛАН 4: Индексы для backup (ЗАГЛУШКИ)
# Index('idx_backup_history_created', BackupHistory.created_at)


def init_database_models(engine):
    """Инициализация моделей базы данных"""
    try:
        # Создаем все таблицы с проверкой существования
        Base.metadata.create_all(engine, checkfirst=True)
        print("✅ Модели базы данных инициализированы")
        return True
    except Exception as e:
        print(f"❌ Ошибка инициализации моделей БД: {e}")
        return False


def get_table_info():
    """Получение информации о таблицах"""
    tables_info = {
        'active_tables': [],
        'plan2_tables': [],
        'plan3_tables': [],
        'plan4_tables': []
    }
    
    # ПЛАН 1: Активные таблицы
    tables_info['active_tables'] = [
        ('users', 'Пользователи бота'),
        ('links', 'Ссылки пользователей'), 
        ('settings', 'Настройки бота')
    ]
    
    # ПЛАН 2: Таблицы кармы (заглушки)
    tables_info['plan2_tables'] = [
        # ('user_karma', 'Карма пользователей'),
        # ('karma_history', 'История изменений кармы')
    ]
    
    # ПЛАН 3: Таблицы ИИ и форм (заглушки)
    tables_info['plan3_tables'] = [
        # ('presave_requests', 'Заявки на пресейвы'),
        # ('approval_claims', 'Заявки о совершенных пресейвах'),
        # ('claim_screenshots', 'Скриншоты заявок'),
        # ('ai_interactions', 'Взаимодействия с ИИ'),
        # ('auto_karma_log', 'Автоматические начисления кармы'),
        # ('message_stats', 'Статистика сообщений')
    ]
    
    # ПЛАН 4: Таблицы backup (заглушки)
    tables_info['plan4_tables'] = [
        # ('backup_history', 'История backup операций')
    ]
    
    return tables_info


if __name__ == "__main__":
    """Тестирование моделей"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Создание тестовой БД в памяти
    engine = create_engine('sqlite:///:memory:', echo=True)
    
    # Инициализация моделей
    success = init_database_models(engine)
    
    if success:
        # Получение информации о таблицах
        tables_info = get_table_info()
        
        print("\n📋 ИНФОРМАЦИЯ О ТАБЛИЦАХ:")
        print(f"🟢 ПЛАН 1 (активные): {len(tables_info['active_tables'])} таблиц")
        for table, desc in tables_info['active_tables']:
            print(f"  • {table}: {desc}")
        
        print(f"🟡 ПЛАН 2 (заглушки): {len(tables_info['plan2_tables'])} таблиц")
        print(f"🟡 ПЛАН 3 (заглушки): {len(tables_info['plan3_tables'])} таблиц") 
        print(f"🟡 ПЛАН 4 (заглушки): {len(tables_info['plan4_tables'])} таблиц")
        
        # Создание тестовой сессии
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Тестовое создание пользователя
        test_user = User(
            user_id=12345,
            username='testuser',
            first_name='Test',
            is_admin=True
        )
        
        session.add(test_user)
        session.commit()
        
        print(f"\n✅ Тестовый пользователь создан: {test_user}")
        
        session.close()
        print("✅ Тестирование моделей завершено")
    else:
        print("❌ Ошибка при тестировании моделей")