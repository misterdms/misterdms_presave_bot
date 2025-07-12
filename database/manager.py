"""
💾 Database Manager - Do Presave Reminder Bot v25+
Центральный менеджер базы данных с поддержкой всех планов развития
"""

import uuid
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Union, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text, func, and_, or_, desc, asc
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.pool import QueuePool
import time

from config import config
from database.models import Base, User, BotSettings, Link
from utils.logger import get_logger
from utils.security import security_manager, ValidationError

logger = get_logger(__name__)

# ИСПРАВЛЕНИЕ database/manager.py - ЗАГЛУШКИ КЛАССОВ И ДЕКОРАТОРА

## ДОБАВИТЬ В НАЧАЛО ФАЙЛА ПОСЛЕ ИМПОРТОВ

**НАЙТИ рядом с [строка ~25 после импортов]:**

```python
from utils.logger import get_logger

logger = get_logger(__name__)
```

# Заглушки классов Plan 2-4 для типизации
class UserKarma: pass
class KarmaHistory: pass
class PresaveRequest: pass
class ApprovalClaim: pass
class ClaimScreenshot: pass
class FormSession: pass
class AIConversation: pass
class AutoKarmaLog: pass
class BackupHistory: pass
class MessageStats: pass

# Заглушки Enums
class UserRank: pass
class PresaveRequestStatus: pass  
class ApprovalClaimStatus: pass
class FormState: pass

# Заглушки функций
def get_user_rank_by_karma(karma_points): 
    return None

def get_karma_threshold_for_next_rank(karma): 
    return None

# Заглушка декоратора для Plan 1
def log_database_operation(table_name: str, operation_type: str = "UNKNOWN"):
    """Заглушка декоратора логирования операций БД"""
    def decorator(func):
        return func  # Просто возвращаем функцию без изменений
    return decorator

# Заглушка декоратора для Plan 1
def log_database_operation(table_name: str, operation_type: str = "UNKNOWN"):
    """Заглушка декоратора логирования операций БД"""
    def decorator(func):
        return func  # Просто возвращаем функцию без изменений
    return decorator

class DatabaseError(Exception):
    """Базовое исключение для ошибок базы данных"""
    pass

class DatabaseManager:
    """Центральный менеджер базы данных для всех планов"""
    
    def __init__(self):
        """Инициализация менеджера базы данных"""
        self.engine = None
        self.SessionLocal = None
        self.session_factory = None
        
        # Статистика подключений
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'total_queries': 0,
            'average_query_time': 0.0
        }
        
        self._setup_database_connection()
        logger.info("💾 Database Manager инициализирован")
    
    def _setup_database_connection(self):
        """Настройка подключения к базе данных"""
        try:
            # Создаем engine с настройками пула соединений
            self.engine = create_engine(
                config.DATABASE_URL,
                poolclass=QueuePool,
                pool_size=config.DB_POOL_SIZE,
                max_overflow=10,
                pool_timeout=config.DB_POOL_TIMEOUT,
                pool_recycle=config.DB_POOL_RECYCLE,
                pool_pre_ping=True,  # Проверка соединений
                echo=False,  # Логирование SQL запросов (отключено для production)
                future=True
            )
            
            # Создаем фабрику сессий
            self.SessionLocal = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False
            )
            
            # Scoped session для thread-safety
            self.session_factory = scoped_session(self.SessionLocal)
            
            logger.info("✅ Подключение к PostgreSQL установлено")
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к БД: {e}")
            raise DatabaseError(f"Не удалось подключиться к базе данных: {e}")
    
    @contextmanager
    def get_session(self):
        """Context manager для получения сессии БД"""
        session = self.session_factory()
        transaction_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        try:
            database_logger.transaction_started(transaction_id)
            self.connection_stats['active_connections'] += 1
            yield session
            
            session.commit()
            execution_time = (time.time() - start_time) * 1000
            database_logger.transaction_committed(transaction_id, execution_time)
            
        except Exception as e:
            session.rollback()
            database_logger.transaction_rolled_back(transaction_id, str(e))
            logger.error(f"❌ Ошибка транзакции {transaction_id}: {e}")
            raise
            
        finally:
            session.close()
            self.connection_stats['active_connections'] -= 1
            self.connection_stats['total_connections'] += 1
    
    def init_database(self):
        """Инициализация базы данных - создание таблиц"""
        try:
            logger.info("🔄 Инициализация схемы базы данных...")
            
            # Создаем все таблицы
            Base.metadata.create_all(bind=self.engine)
            
            # Инициализируем базовые настройки
            self._init_default_settings()
            
            logger.info("✅ База данных инициализирована успешно")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            raise DatabaseError(f"Не удалось инициализировать базу данных: {e}")
    
    def _init_default_settings(self):
        """Инициализация настроек по умолчанию"""
        with self.get_session() as session:
            # Проверяем есть ли настройки
            existing_settings = session.query(BotSettings).first()
            
            if not existing_settings:
                default_settings = [
                    BotSettings(
                        key='bot_enabled',
                        value='true',
                        value_type='bool',
                        description='Включен ли бот'
                    ),
                    BotSettings(
                        key='current_limit_mode',
                        value=config.DEFAULT_LIMIT_MODE,
                        value_type='string',
                        description='Текущий режим лимитов API'
                    ),
                    BotSettings(
                        key='reminder_text',
                        value=config.REMINDER_TEXT,
                        value_type='string',
                        description='Текст напоминания о пресейвах'
                    )
                ]
                
                for setting in default_settings:
                    session.add(setting)
                
                logger.info("✅ Настройки по умолчанию созданы")

    # ============================================
    # ПЛАН 1 - БАЗОВЫЕ CRUD ОПЕРАЦИИ
    # ============================================
    
    @log_database_operation('users', 'CREATE')
    def create_or_update_user(self, telegram_id: int, username: Optional[str] = None,
                             first_name: Optional[str] = None, last_name: Optional[str] = None) -> User:
        """Создание или обновление пользователя"""
        with self.get_session() as session:
            # Проверяем существует ли пользователь
            user = session.query(User).filter(User.telegram_id == telegram_id).first()
            
            if user:
                # Обновляем существующего
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.last_activity = func.now()
                user.is_admin = security_manager.is_admin(telegram_id)
                
                logger.debug(f"👤 Пользователь обновлен: {telegram_id}")
            else:
                # Создаем нового
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=security_manager.is_admin(telegram_id)
                )
                session.add(user)
                
                # Если включен План 2, создаем запись кармы
                if config.ENABLE_PLAN_2_FEATURES:
                    karma_record = UserKarma(
                        user_id=user.id,
                        karma_points=config.ADMIN_KARMA if user.is_admin else 0,
                        rank=UserRank.AMBASSADOR if user.is_admin else UserRank.NEWBIE
                    )
                    session.add(karma_record)
                
                logger.info(f"👤 Новый пользователь создан: {telegram_id}")
            
            session.flush()  # Получаем ID
            return user
    
    @log_database_operation('users', 'SELECT')
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя по Telegram ID"""
        with self.get_session() as session:
            return session.query(User).filter(User.telegram_id == telegram_id).first()
    
    @log_database_operation('users', 'SELECT')
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Получение пользователя по username"""
        username = username.lstrip('@').lower()
        with self.get_session() as session:
            return session.query(User).filter(
                func.lower(User.username) == username
            ).first()
    
    @log_database_operation('links', 'CREATE')
    def create_link(self, user_id: int, message_id: int, url: str, 
                   thread_id: Optional[int] = None, message_text: Optional[str] = None) -> Link:
        """Создание записи ссылки"""
        with self.get_session() as session:
            # Извлекаем домен для аналитики
            from urllib.parse import urlparse
            try:
                domain = urlparse(url).netloc.lower()
            except:
                domain = None
            
            link = Link(
                user_id=user_id,
                message_id=message_id,
                thread_id=thread_id,
                url=url,
                message_text=message_text,
                domain=domain
            )
            session.add(link)
            session.flush()
            
            logger.debug(f"🔗 Ссылка создана: {user_id} -> {domain}")
            return link
    
    @log_database_operation('links', 'SELECT')
    def get_recent_links(self, limit: int = 10, thread_id: Optional[int] = None) -> List[Link]:
        """Получение последних ссылок"""
        with self.get_session() as session:
            query = session.query(Link).order_by(desc(Link.created_at))
            
            if thread_id:
                query = query.filter(Link.thread_id == thread_id)
            
            return query.limit(limit).all()
    
    @log_database_operation('links', 'SELECT')
    def get_user_links(self, user_id: int, limit: int = 50) -> List[Link]:
        """Получение ссылок пользователя"""
        with self.get_session() as session:
            return session.query(Link)\
                .filter(Link.user_id == user_id)\
                .order_by(desc(Link.created_at))\
                .limit(limit).all()
    
    @log_database_operation('bot_settings', 'SELECT')
    def get_setting(self, key: str) -> Optional[str]:
        """Получение настройки бота"""
        with self.get_session() as session:
            setting = session.query(BotSettings).filter(BotSettings.key == key).first()
            return setting.value if setting else None
    
    @log_database_operation('bot_settings', 'UPDATE')
    def set_setting(self, key: str, value: str, value_type: str = 'string', 
                   description: Optional[str] = None):
        """Установка настройки бота"""
        with self.get_session() as session:
            setting = session.query(BotSettings).filter(BotSettings.key == key).first()
            
            if setting:
                setting.value = value
                setting.value_type = value_type
                if description:
                    setting.description = description
            else:
                setting = BotSettings(
                    key=key,
                    value=value,
                    value_type=value_type,
                    description=description
                )
                session.add(setting)
            
            logger.debug(f"⚙️ Настройка обновлена: {key} = {value}")
    
    @log_database_operation('links', 'DELETE')
    def clear_links(self, older_than_days: Optional[int] = None):
        """Очистка ссылок"""
        with self.get_session() as session:
            query = session.query(Link)
            
            if older_than_days:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                query = query.filter(Link.created_at < cutoff_date)
            
            deleted_count = query.count()
            query.delete()
            
            logger.info(f"🗑️ Удалено ссылок: {deleted_count}")
            return deleted_count

    # ============================================
    # ПЛАН 2 - СИСТЕМА КАРМЫ
    # ============================================
    
    @log_database_operation('user_karma', 'SELECT')
    def get_user_karma(self, user_id: int) -> Optional[UserKarma]:
        """Получение кармы пользователя"""
        if not config.ENABLE_PLAN_2_FEATURES:
            return None
            
        with self.get_session() as session:
            return session.query(UserKarma).filter(UserKarma.user_id == user_id).first()
    
    @log_database_operation('user_karma', 'UPDATE')
    def change_karma(self, user_id: int, change: int, admin_id: Optional[int] = None,
                    reason: Optional[str] = None, is_automatic: bool = False) -> UserKarma:
        """Изменение кармы пользователя"""
        if not config.ENABLE_PLAN_2_FEATURES:
            raise DatabaseError("План 2 (система кармы) не включен")
            
        with self.get_session() as session:
            # Получаем или создаем запись кармы
            karma_record = session.query(UserKarma).filter(UserKarma.user_id == user_id).first()
            
            if not karma_record:
                karma_record = UserKarma(user_id=user_id)
                session.add(karma_record)
                session.flush()
            
            # Сохраняем состояние до изменения
            karma_before = karma_record.karma_points
            rank_before = karma_record.rank
            
            # Применяем изменение
            new_karma = max(0, min(karma_record.karma_points + change, config.MAX_KARMA))
            karma_record.karma_points = new_karma
            karma_record.last_karma_change = func.now()
            
            # Обновляем звание
            old_rank = karma_record.rank
            new_rank = get_user_rank_by_karma(new_karma)
            karma_record.rank = new_rank
            
            # Создаем запись в истории
            history_record = KarmaHistory(
                user_id=user_id,
                admin_id=admin_id,
                change_amount=change,
                reason=reason,
                karma_before=karma_before,
                karma_after=new_karma,
                rank_before=rank_before,
                rank_after=new_rank,
                is_automatic=is_automatic,
                is_manual=not is_automatic
            )
            session.add(history_record)
            
            # Логируем изменение
            from utils.logger import karma_logger
            karma_logger.karma_changed(
                user_id, change, new_karma, admin_id, is_automatic
            )
            
            if old_rank != new_rank:
                karma_logger.rank_changed(user_id, old_rank.value, new_rank.value, new_karma)
            
            return karma_record
    
    @log_database_operation('user_karma', 'SELECT')
    def get_karma_leaderboard(self, limit: int = 10) -> List[Tuple[User, UserKarma]]:
        """Получение топа по карме"""
        if not config.ENABLE_PLAN_2_FEATURES:
            return []
            
        with self.get_session() as session:
            return session.query(User, UserKarma)\
                .join(UserKarma, User.id == UserKarma.user_id)\
                .order_by(desc(UserKarma.karma_points))\
                .limit(limit).all()
    
    @log_database_operation('user_karma', 'SELECT')
    def get_requests_leaderboard(self, limit: int = 10) -> List[Tuple[User, int]]:
        """Получение топа по количеству просьб о пресейвах"""
        with self.get_session() as session:
            # Подсчитываем ссылки каждого пользователя
            subquery = session.query(
                Link.user_id,
                func.count(Link.id).label('link_count')
            ).filter(Link.is_presave_request == True)\
             .group_by(Link.user_id)\
             .subquery()
            
            return session.query(User, subquery.c.link_count)\
                .join(subquery, User.id == subquery.c.user_id)\
                .order_by(desc(subquery.c.link_count))\
                .limit(limit).all()
    
    @log_database_operation('karma_history', 'SELECT')
    def get_karma_history(self, user_id: int, limit: int = 20) -> List[KarmaHistory]:
        """Получение истории изменений кармы"""
        if not config.ENABLE_PLAN_2_FEATURES:
            return []
            
        with self.get_session() as session:
            return session.query(KarmaHistory)\
                .filter(KarmaHistory.user_id == user_id)\
                .order_by(desc(KarmaHistory.created_at))\
                .limit(limit).all()
    
    @log_database_operation('user_karma', 'UPDATE')
    def update_user_ratio(self, user_id: int, requests_count: int, karma_count: int) -> bool:
        """Обновление соотношения просьбы:карма пользователя"""
        if not config.ENABLE_PLAN_2_FEATURES:
            return False
            
        with self.get_session() as session:
            # Обновляем количество просьб в UserKarma
            karma_record = session.query(UserKarma).filter(UserKarma.user_id == user_id).first()
            if karma_record:
                karma_record.presave_requests_count = requests_count
                karma_record.karma_points = karma_count
                karma_record.rank = get_user_rank_by_karma(karma_count)
                
                logger.info(f"📊 Соотношение обновлено: пользователь {user_id} - {requests_count}:{karma_count}")
                return True
                
        return False

    # ============================================
    # ПЛАН 3 - ИНТЕРАКТИВНЫЕ ФОРМЫ И ИИ
    # ============================================
    
    @log_database_operation('presave_requests', 'CREATE')
    def create_presave_request(self, user_id: int, title: Optional[str], 
                              description: Optional[str], links: List[str],
                              thread_id: Optional[int] = None) -> PresaveRequest:
        """Создание заявки на пресейв"""
        if not config.ENABLE_PLAN_3_FEATURES:
            raise DatabaseError("План 3 (интерактивные формы) не включен")
            
        with self.get_session() as session:
            request = PresaveRequest(
                user_id=user_id,
                title=title,
                description=description,
                links=links,
                thread_id=thread_id,
                status=PresaveRequestStatus.PENDING
            )
            session.add(request)
            session.flush()
            
            logger.info(f"📝 Заявка на пресейв создана: пользователь {user_id}")
            return request
    
    @log_database_operation('approval_claims', 'CREATE')
    def create_approval_claim(self, user_id: int, comment: Optional[str],
                             presave_link: Optional[str] = None) -> ApprovalClaim:
        """Создание заявки на аппрув"""
        if not config.ENABLE_PLAN_3_FEATURES:
            raise DatabaseError("План 3 (интерактивные формы) не включен")
            
        with self.get_session() as session:
            claim = ApprovalClaim(
                user_id=user_id,
                comment=comment,
                presave_link=presave_link,
                status=ApprovalClaimStatus.SUBMITTED
            )
            session.add(claim)
            session.flush()
            
            logger.info(f"✅ Заявка на аппрув создана: пользователь {user_id}")
            return claim
    
    @log_database_operation('claim_screenshots', 'CREATE')
    def add_claim_screenshot(self, claim_id: int, file_id: str, file_size: Optional[int] = None,
                            caption: Optional[str] = None) -> ClaimScreenshot:
        """Добавление скриншота к заявке"""
        if not config.ENABLE_PLAN_3_FEATURES:
            raise DatabaseError("План 3 (интерактивные формы) не включен")
            
        with self.get_session() as session:
            screenshot = ClaimScreenshot(
                claim_id=claim_id,
                file_id=file_id,
                file_size=file_size,
                caption=caption
            )
            session.add(screenshot)
            session.flush()
            
            logger.debug(f"📸 Скриншот добавлен к заявке {claim_id}")
            return screenshot
    
    @log_database_operation('approval_claims', 'SELECT')
    def get_pending_claims(self, limit: int = 20) -> List[ApprovalClaim]:
        """Получение заявок ожидающих рассмотрения"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return []
            
        with self.get_session() as session:
            return session.query(ApprovalClaim)\
                .filter(ApprovalClaim.status == ApprovalClaimStatus.SUBMITTED)\
                .order_by(asc(ApprovalClaim.created_at))\
                .limit(limit).all()
    
    @log_database_operation('approval_claims', 'UPDATE')
    def approve_claim(self, claim_id: int, admin_id: int, karma_awarded: int = 1,
                     admin_comment: Optional[str] = None) -> bool:
        """Одобрение заявки на аппрув"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return False
            
        with self.get_session() as session:
            claim = session.query(ApprovalClaim).filter(ApprovalClaim.id == claim_id).first()
            
            if not claim:
                return False
            
            # Обновляем статус заявки
            claim.status = ApprovalClaimStatus.APPROVED
            claim.admin_id = admin_id
            claim.karma_awarded = karma_awarded
            claim.admin_comment = admin_comment
            claim.processed_at = func.now()
            
            # Начисляем карму если План 2 включен
            if config.ENABLE_PLAN_2_FEATURES:
                self.change_karma(
                    claim.user_id, 
                    karma_awarded, 
                    admin_id, 
                    f"Одобрена заявка на аппрув #{claim_id}"
                )
            
            logger.info(f"✅ Заявка одобрена: #{claim_id}, карма +{karma_awarded}")
            return True
    
    @log_database_operation('form_sessions', 'UPDATE')
    def update_form_session(self, user_id: int, state: FormState, 
                           form_type: Optional[str] = None, 
                           session_data: Optional[Dict] = None) -> FormSession:
        """Обновление состояния формы пользователя"""
        if not config.ENABLE_PLAN_3_FEATURES:
            raise DatabaseError("План 3 (интерактивные формы) не включен")
            
        with self.get_session() as session:
            form_session = session.query(FormSession)\
                .filter(FormSession.user_id == user_id).first()
            
            if not form_session:
                form_session = FormSession(user_id=user_id)
                session.add(form_session)
            
            form_session.current_state = state
            if form_type:
                form_session.form_type = form_type
            if session_data:
                form_session.session_data = session_data
            
            # Устанавливаем время истечения (30 минут)
            form_session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
            
            session.flush()
            return form_session
    
    @log_database_operation('ai_conversations', 'CREATE')
    def log_ai_conversation(self, user_id: int, user_message: str, ai_response: str,
                           ai_model: str, tokens_used: int, response_time_ms: float,
                           context_data: Optional[Dict] = None) -> AIConversation:
        """Логирование беседы с ИИ"""
        if not config.ENABLE_PLAN_3_FEATURES:
            raise DatabaseError("План 3 (ИИ функции) не включен")
            
        with self.get_session() as session:
            conversation = AIConversation(
                user_id=user_id,
                user_message=user_message,
                ai_response=ai_response,
                ai_model=ai_model,
                tokens_used=tokens_used,
                response_time_ms=int(response_time_ms),
                context_data=context_data
            )
            session.add(conversation)
            session.flush()
            
            return conversation
    
    @log_database_operation('auto_karma_log', 'CREATE')
    def log_auto_karma(self, from_user_id: int, to_user_id: int, trigger_word: str,
                      message_text: str, karma_added: int = 1) -> AutoKarmaLog:
        """Логирование автоматического начисления кармы"""
        if not config.ENABLE_PLAN_3_FEATURES:
            raise DatabaseError("План 3 (автоматическая карма) не включен")
            
        with self.get_session() as session:
            log_entry = AutoKarmaLog(
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                trigger_word=trigger_word,
                message_text=message_text,
                karma_added=karma_added,
                processed=True
            )
            session.add(log_entry)
            session.flush()
            
            return log_entry

    # ============================================
    # ПЛАН 4 - BACKUP СИСТЕМА
    # ============================================
    
    @log_database_operation('backup_history', 'CREATE')
    def log_backup_operation(self, filename: str, file_size_bytes: int,
                            backup_type: str = 'manual', tables_included: List[str] = None,
                            rows_exported: Optional[int] = None, status: str = 'completed',
                            error_message: Optional[str] = None) -> BackupHistory:
        """Логирование операции backup"""
        if not config.ENABLE_PLAN_4_FEATURES:
            raise DatabaseError("План 4 (backup система) не включен")
            
        with self.get_session() as session:
            backup_record = BackupHistory(
                filename=filename,
                file_size_bytes=file_size_bytes,
                backup_type=backup_type,
                tables_included=tables_included or [],
                rows_exported=rows_exported,
                status=status,
                error_message=error_message,
                completed_at=func.now() if status == 'completed' else None
            )
            session.add(backup_record)
            session.flush()
            
            logger.info(f"💾 Backup операция залогирована: {filename} ({status})")
            return backup_record
    
    @log_database_operation('message_stats', 'UPDATE')
    def update_message_stats(self, user_id: int, thread_id: int, 
                           links_shared: int = 0, gratitude_received: int = 0,
                           gratitude_given: int = 0) -> MessageStats:
        """Обновление статистики сообщений"""
        with self.get_session() as session:
            stats = session.query(MessageStats)\
                .filter(and_(MessageStats.user_id == user_id, MessageStats.thread_id == thread_id))\
                .first()
            
            if not stats:
                stats = MessageStats(
                    user_id=user_id,
                    thread_id=thread_id,
                    message_count=1,
                    first_message_at=func.now()
                )
                session.add(stats)
            else:
                stats.message_count += 1
                stats.links_shared += links_shared
                stats.gratitude_received += gratitude_received
                stats.gratitude_given += gratitude_given
            
            stats.last_message_at = func.now()
            session.flush()
            
            return stats
    
    @log_database_operation('backup_history', 'SELECT')
    def get_backup_history(self, limit: int = 10) -> List[BackupHistory]:
        """Получение истории backup операций"""
        if not config.ENABLE_PLAN_4_FEATURES:
            return []
            
        with self.get_session() as session:
            return session.query(BackupHistory)\
                .order_by(desc(BackupHistory.started_at))\
                .limit(limit).all()

    # ============================================
    # АНАЛИТИКА И СТАТИСТИКА
    # ============================================
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение полной статистики пользователя"""
        with self.get_session() as session:
            stats = {
                'user_info': None,
                'links_count': 0,
                'karma_info': None,
                'message_stats': {},
                'ai_interactions': 0,
                'form_submissions': 0
            }
            
            # Основная информация о пользователе
            user = session.query(User).filter(User.telegram_id == user_id).first()
            if user:
                stats['user_info'] = {
                    'username': user.username,
                    'first_name': user.first_name,
                    'is_admin': user.is_admin,
                    'created_at': user.created_at,
                    'last_activity': user.last_activity
                }
                
                # Количество ссылок
                stats['links_count'] = session.query(Link)\
                    .filter(Link.user_id == user.id).count()
                
                # Информация о карме (План 2)
                if config.ENABLE_PLAN_2_FEATURES:
                    karma_record = session.query(UserKarma)\
                        .filter(UserKarma.user_id == user.id).first()
                    
                    if karma_record:
                        next_threshold = get_karma_threshold_for_next_rank(karma_record.karma_points)
                        stats['karma_info'] = {
                            'karma_points': karma_record.karma_points,
                            'rank': karma_record.rank.value,
                            'next_rank_threshold': next_threshold,
                            'progress_to_next': None
                        }
                        
                        if next_threshold:
                            progress = (karma_record.karma_points * 100) // next_threshold
                            stats['karma_info']['progress_to_next'] = min(progress, 100)
                
                # Статистика сообщений по топикам
                message_stats = session.query(MessageStats)\
                    .filter(MessageStats.user_id == user.id).all()
                
                stats['message_stats'] = {
                    stat.thread_id: {
                        'message_count': stat.message_count,
                        'links_shared': stat.links_shared,
                        'gratitude_received': stat.gratitude_received,
                        'gratitude_given': stat.gratitude_given
                    } for stat in message_stats
                }
                
                # ИИ взаимодействия (План 3)
                if config.ENABLE_PLAN_3_FEATURES:
                    stats['ai_interactions'] = session.query(AIConversation)\
                        .filter(AIConversation.user_id == user.id).count()
                    
                    stats['form_submissions'] = session.query(PresaveRequest)\
                        .filter(PresaveRequest.user_id == user.id).count()
            
            return stats
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Получение общей статистики базы данных"""
        with self.get_session() as session:
            stats = {
                'total_users': session.query(User).count(),
                'active_users_week': session.query(User).filter(
                    User.last_activity >= datetime.now(timezone.utc) - timedelta(days=7)
                ).count(),
                'total_links': session.query(Link).count(),
                'total_karma_points': 0,
                'total_ai_conversations': 0,
                'total_backups': 0,
                'database_size_info': self.connection_stats
            }
            
            # Статистика кармы (План 2)
            if config.ENABLE_PLAN_2_FEATURES:
                karma_sum = session.query(func.sum(UserKarma.karma_points)).scalar()
                stats['total_karma_points'] = karma_sum or 0
            
            # Статистика ИИ (План 3)
            if config.ENABLE_PLAN_3_FEATURES:
                stats['total_ai_conversations'] = session.query(AIConversation).count()
            
            # Статистика backup (План 4)
            if config.ENABLE_PLAN_4_FEATURES:
                stats['total_backups'] = session.query(BackupHistory).count()
            
            return stats
    
    def cleanup_expired_sessions(self):
        """Очистка истекших сессий форм"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return 0
            
        with self.get_session() as session:
            expired_count = session.query(FormSession)\
                .filter(FormSession.expires_at < func.now())\
                .count()
            
            session.query(FormSession)\
                .filter(FormSession.expires_at < func.now())\
                .delete()
            
            if expired_count > 0:
                logger.info(f"🧹 Очищено истекших сессий форм: {expired_count}")
            
            return expired_count
    
    def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья базы данных"""
        try:
            with self.get_session() as session:
                # Простой запрос для проверки соединения
                session.execute(text("SELECT 1")).fetchone()
                
                # Проверяем основные таблицы
                tables_status = {}
                for table_name in ['users', 'bot_settings', 'links']:
                    try:
                        count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                        tables_status[table_name] = {'status': 'ok', 'count': count}
                    except Exception as e:
                        tables_status[table_name] = {'status': 'error', 'error': str(e)}
                
                return {
                    'database_connection': 'ok',
                    'tables': tables_status,
                    'connection_stats': self.connection_stats,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Health check БД провален: {e}")
            return {
                'database_connection': 'error',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

# ============================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР
# ============================================

# Глобальный экземпляр менеджера БД
database_manager: Optional[DatabaseManager] = None

def get_database_manager() -> DatabaseManager:
    """Получение глобального экземпляра менеджера БД"""
    global database_manager
    if database_manager is None:
        database_manager = DatabaseManager()
    return database_manager

def init_database_manager() -> DatabaseManager:
    """Инициализация глобального менеджера БД"""
    global database_manager
    database_manager = DatabaseManager()
    database_manager.init_database()
    return database_manager

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = [
    'DatabaseManager', 'DatabaseError',
    'get_database_manager', 'init_database_manager'
]

if __name__ == "__main__":
    # Тестирование менеджера базы данных
    print("🧪 Тестирование Database Manager...")
    
    try:
        # Инициализация
        db = init_database_manager()
        print("✅ Database Manager инициализирован")
        
        # Health check
        health = db.health_check()
        print(f"✅ Health check: {health['database_connection']}")
        
        # Тест создания пользователя
        user = db.create_or_update_user(
            telegram_id=12345,
            username="test_user",
            first_name="Test"
        )
        print(f"✅ Пользователь создан: {user.telegram_id}")
        
        # Тест настроек
        db.set_setting("test_key", "test_value", "string", "Тестовая настройка")
        value = db.get_setting("test_key")
        print(f"✅ Настройки работают: {value}")
        
        # Статистика БД
        stats = db.get_database_stats()
        print(f"✅ Статистика БД: {stats['total_users']} пользователей")
        
        print("✅ Все тесты пройдены!")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
