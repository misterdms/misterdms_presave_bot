"""
💾 Database Models - Do Presave Reminder Bot v25+ (ПЛАН 1 ТОЛЬКО)
Простые модели БД без сложных зависимостей
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# ============================================
# БАЗОВАЯ МОДЕЛЬ
# ============================================

Base = declarative_base()

class TimestampMixin:
    """Миксин для автоматических временных меток"""
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

# ============================================
# МОДЕЛИ ПЛАН 1 - БАЗОВЫЙ ФУНКЦИОНАЛ
# ============================================

class User(Base, TimestampMixin):
    """Пользователь бота (базовая модель для всех планов)"""
    __tablename__ = 'users'
    
    # Основные поля
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)  # Telegram user ID
    username = Column(String(255), nullable=True, index=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    
    # Статистика активности
    is_bot = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Связи (простые для Plan 1)
    links = relationship("Link", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(user_id={self.user_id}, username='{self.username}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_active': self.is_active,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Link(Base, TimestampMixin):
    """Ссылка пользователя"""
    __tablename__ = 'links'
    
    # Основные поля
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False, index=True)
    
    # Данные ссылки
    url = Column(Text, nullable=False)
    platform = Column(String(50), nullable=True)  # spotify, apple_music, youtube, etc.
    title = Column(String(500), nullable=True)
    artist = Column(String(255), nullable=True)
    
    # Метаданные
    message_id = Column(BigInteger, nullable=True)  # ID сообщения в Telegram
    thread_id = Column(BigInteger, nullable=True)   # ID топика
    is_processed = Column(Boolean, default=False, nullable=False)
    
    # Связи
    user = relationship("User", back_populates="links")
    
    def __repr__(self):
        return f"<Link(id={self.id}, user_id={self.user_id}, platform='{self.platform}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'url': self.url,
            'platform': self.platform,
            'title': self.title,
            'artist': self.artist,
            'message_id': self.message_id,
            'thread_id': self.thread_id,
            'is_processed': self.is_processed,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class BotSettings(Base, TimestampMixin):
    """Настройки бота"""
    __tablename__ = 'bot_settings'
    
    # Основные поля
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    
    # Метаданные
    is_system = Column(Boolean, default=False, nullable=False)  # Системная настройка
    
    def __repr__(self):
        return f"<BotSettings(key='{self.key}', value='{self.value}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description,
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def get_all_table_names() -> List[str]:
    """Получение списка всех таблиц"""
    return [
        'users',
        'links', 
        'bot_settings'
    ]

def create_default_settings() -> List[Dict[str, Any]]:
    """Создание настроек по умолчанию"""
    return [
        {
            'key': 'bot_enabled',
            'value': 'true',
            'description': 'Включен ли бот',
            'is_system': True
        },
        {
            'key': 'current_limit_mode',
            'value': 'BURST',
            'description': 'Текущий режим лимитов API',
            'is_system': True
        },
        {
            'key': 'plan_1_enabled',
            'value': 'true', 
            'description': 'План 1: Базовый функционал',
            'is_system': True
        },
        {
            'key': 'plan_2_enabled',
            'value': 'false',
            'description': 'План 2: Система кармы',
            'is_system': True
        },
        {
            'key': 'plan_3_enabled',
            'value': 'false',
            'description': 'План 3: ИИ и формы',
            'is_system': True
        },
        {
            'key': 'plan_4_enabled',
            'value': 'false',
            'description': 'План 4: Backup система',
            'is_system': True
        }
    ]

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = [
    # Базовые классы
    'Base', 'TimestampMixin',
    
    # Модели Plan 1
    'User', 'Link', 'BotSettings',
    
    # Вспомогательные функции
    'get_all_table_names', 'create_default_settings'
]

# ============================================
# ПЛАН МИГРАЦИЙ ДЛЯ БУДУЩИХ ПЛАНОВ
# ============================================

"""
СТРАТЕГИЯ ДОБАВЛЕНИЯ МОДЕЛЕЙ ПО ПЛАНАМ:

📋 ПЛАН 2 (v26) - СИСТЕМА КАРМЫ:
- Добавим: UserKarma, KarmaHistory
- Через: Alembic migration 001_add_karma_system.py
- Связи: User.karma (one-to-one), User.karma_history (one-to-many)

🤖 ПЛАН 3 (v27) - ИИ И ФОРМЫ:  
- Добавим: PresaveRequest, ApprovalClaim, FormSession, AIConversation
- Через: Alembic migration 002_add_ai_and_forms.py
- Связи: User.presave_requests, User.ai_conversations

💾 ПЛАН 4 (v27.1) - BACKUP:
- Добавим: BackupHistory, MigrationLog
- Через: Alembic migration 003_add_backup_system.py
- Связи: Standalone таблицы без foreign keys

ПРИНЦИПЫ:
✅ Каждая миграция добавляет только новые таблицы
✅ Никогда не изменяем существующие таблицы Plan 1
✅ Обратная совместимость 100%
✅ Можно откатиться на любой план
"""
