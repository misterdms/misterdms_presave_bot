"""
Менеджер базы данных Do Presave Reminder Bot v25+
CRUD операции и управление соединениями для всех планов
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager

from sqlalchemy import create_engine, desc, func, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from database.models import Base, User, Link, Settings
# ПЛАН 2: Импорты кармы (ЗАГЛУШКИ)
# from database.models import UserKarma, KarmaHistory
# ПЛАН 3: Импорты ИИ и форм (ЗАГЛУШКИ)  
# from database.models import PresaveRequest, ApprovalClaim, ClaimScreenshot, AIInteraction, AutoKarmaLog, MessageStats
# ПЛАН 4: Импорты backup (ЗАГЛУШКИ)
# from database.models import BackupHistory

from utils.logger import get_logger, log_database_operation, PerformanceLogger

logger = get_logger(__name__)

class DatabaseManager:
    """Менеджер базы данных с поддержкой всех планов развития"""
    
    def __init__(self, database_url: str = None):
        """Инициализация менеджера БД"""
        
        # Получаем URL БД из параметра или переменной окружения
        self.database_url = database_url or os.getenv('DATABASE_URL')
        
        if not self.database_url:
            raise ValueError("DATABASE_URL не указан!")
        
        # Настройка пула соединений
        pool_size = int(os.getenv('DB_POOL_SIZE', '5'))
        
        # Создание движка БД
        self.engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=pool_size * 2,
            pool_pre_ping=True,  # Проверка соединений
            echo=False  # Отключаем SQL логи для production
        )
        
        # Создание фабрики сессий
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        logger.info(f"DatabaseManager инициализирован: {self.database_url.split('@')[-1]}")
    
    @contextmanager
    def get_session(self):
        """Контекстный менеджер для получения сессии БД"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Ошибка БД сессии: {e}")
            raise
        finally:
            session.close()
    
    def create_tables(self):
        """Создание всех таблиц БД"""
        try:
            with PerformanceLogger(logger, "создание таблиц БД"):
                Base.metadata.create_all(self.engine)
            
            logger.info("✅ Все таблицы БД созданы/проверены")
            
            # Инициализация базовых настроек
            self._init_default_settings()
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания таблиц: {e}")
            raise
    
    def _init_default_settings(self):
        """Инициализация настроек по умолчанию"""
        default_settings = [
            ('bot_enabled', 'true', 'bool', 'Включен ли бот'),
            ('current_limit_mode', 'BURST', 'string', 'Текущий режим лимитов API'),
            ('reminder_count', '0', 'int', 'Счетчик отправленных напоминаний'),
            ('last_reset_date', datetime.now().isoformat(), 'string', 'Дата последнего сброса статистики'),
            
            # ПЛАН 2: Настройки кармы (ЗАГЛУШКИ)
            # ('karma_enabled', 'false', 'bool', 'Включена ли система кармы'),
            # ('auto_karma_enabled', 'false', 'bool', 'Включено ли автоматическое начисление кармы'),
            
            # ПЛАН 3: Настройки ИИ и форм (ЗАГЛУШКИ)
            # ('ai_enabled', 'false', 'bool', 'Включен ли ИИ'),
            # ('forms_enabled', 'false', 'bool', 'Включены ли интерактивные формы'),
            # ('gratitude_detection_enabled', 'false', 'bool', 'Включено ли распознавание благодарностей'),
            
            # ПЛАН 4: Настройки backup (ЗАГЛУШКИ)
            # ('last_backup_date', '', 'string', 'Дата последнего backup'),
            # ('backup_notifications_enabled', 'true', 'bool', 'Включены ли уведомления о backup'),
        ]
        
        try:
            with self.get_session() as session:
                for key, value, value_type, description in default_settings:
                    existing = session.query(Settings).filter(Settings.key == key).first()
                    if not existing:
                        setting = Settings(
                            key=key,
                            value=value,
                            value_type=value_type,
                            description=description
                        )
                        session.add(setting)
                
                session.commit()
                log_database_operation(logger, "INIT", "settings", len(default_settings))
                
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации настроек: {e}")
    
    def close(self):
        """Закрытие соединений с БД"""
        try:
            self.engine.dispose()
            logger.info("✅ Соединения с БД закрыты")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия БД: {e}")
    
    # ============================================
    # ПЛАН 1: CRUD ОПЕРАЦИИ ДЛЯ БАЗОВЫХ МОДЕЛЕЙ
    # ============================================
    
    # --- Управление пользователями ---
    
    def get_or_create_user(self, user_id: int, username: str = None, 
                          first_name: str = None, last_name: str = None) -> User:
        """Получение или создание пользователя"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                
                if not user:
                    # Создаем нового пользователя
                    is_admin = user_id in self._get_admin_ids()
                    
                    user = User(
                        user_id=user_id,
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        is_admin=is_admin
                    )
                    session.add(user)
                    session.commit()
                    
                    log_database_operation(logger, "CREATE", "users", 1, user_id=user_id)
                else:
                    # Обновляем данные существующего пользователя
                    updated = False
                    if username and user.username != username:
                        user.username = username
                        updated = True
                    if first_name and user.first_name != first_name:
                        user.first_name = first_name
                        updated = True
                    if last_name and user.last_name != last_name:
                        user.last_name = last_name
                        updated = True
                    
                    user.last_seen_at = datetime.now()
                    
                    if updated:
                        session.commit()
                        log_database_operation(logger, "UPDATE", "users", 1, user_id=user_id)
                
                return user
                
        except Exception as e:
            logger.error(f"❌ Ошибка get_or_create_user: {e}")
            raise
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                return user
        except Exception as e:
            logger.error(f"❌ Ошибка get_user_by_id: {e}")
            return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Получение пользователя по username"""
        try:
            # Убираем @ если есть
            username = username.lstrip('@')
            
            with self.get_session() as session:
                user = session.query(User).filter(User.username == username).first()
                return user
        except Exception as e:
            logger.error(f"❌ Ошибка get_user_by_username: {e}")
            return None
    
    def get_all_admins(self) -> List[User]:
        """Получение всех администраторов"""
        try:
            with self.get_session() as session:
                admins = session.query(User).filter(User.is_admin == True).all()
                return admins
        except Exception as e:
            logger.error(f"❌ Ошибка get_all_admins: {e}")
            return []
    
    def _get_admin_ids(self) -> List[int]:
        """Получение списка ID админов из конфигурации"""
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        try:
            return [int(x.strip()) for x in admin_ids_str.split(',') if x.strip()]
        except ValueError:
            return []
    
    # --- Управление ссылками ---
    
    def add_link(self, user_id: int, url: str, message_text: str = None, 
                 message_id: int = None, thread_id: int = None) -> Link:
        """Добавление новой ссылки"""
        try:
            with self.get_session() as session:
                # Получаем или создаем пользователя
                user = self.get_or_create_user(user_id)
                
                # Создаем ссылку
                link = Link(
                    user_id=user_id,
                    url=url,
                    message_text=message_text,
                    message_id=message_id,
                    thread_id=thread_id
                )
                
                session.add(link)
                session.commit()
                
                log_database_operation(logger, "CREATE", "links", 1, 
                                     user_id=user_id, url=url[:50] + "...")
                
                return link
                
        except Exception as e:
            logger.error(f"❌ Ошибка add_link: {e}")
            raise
    
    def get_recent_links(self, limit: int = 10, thread_id: int = None) -> List[Link]:
        """Получение последних ссылок"""
        try:
            with self.get_session() as session:
                query = session.query(Link).filter(Link.is_active == True)
                
                if thread_id:
                    query = query.filter(Link.thread_id == thread_id)
                
                links = query.order_by(desc(Link.created_at)).limit(limit).all()
                
                log_database_operation(logger, "SELECT", "links", len(links), limit=limit)
                
                return links
                
        except Exception as e:
            logger.error(f"❌ Ошибка get_recent_links: {e}")
            return []
    
    def get_user_links(self, user_id: int, limit: int = 50) -> List[Link]:
        """Получение ссылок пользователя"""
        try:
            with self.get_session() as session:
                links = session.query(Link).filter(
                    and_(Link.user_id == user_id, Link.is_active == True)
                ).order_by(desc(Link.created_at)).limit(limit).all()
                
                return links
                
        except Exception as e:
            logger.error(f"❌ Ошибка get_user_links: {e}")
            return []
    
    def get_links_by_username(self, username: str, limit: int = 50) -> List[Link]:
        """Получение ссылок по username"""
        try:
            user = self.get_user_by_username(username)
            if not user:
                return []
            
            return self.get_user_links(user.user_id, limit)
            
        except Exception as e:
            logger.error(f"❌ Ошибка get_links_by_username: {e}")
            return []
    
    def clear_all_links(self) -> int:
        """Очистка всех ссылок (помечаем как неактивные)"""
        try:
            with self.get_session() as session:
                count = session.query(Link).filter(Link.is_active == True).count()
                
                session.query(Link).filter(Link.is_active == True).update(
                    {Link.is_active: False}
                )
                session.commit()
                
                log_database_operation(logger, "UPDATE", "links", count, action="clear_all")
                
                return count
                
        except Exception as e:
            logger.error(f"❌ Ошибка clear_all_links: {e}")
            return 0
    
    # --- Управление настройками ---
    
    def get_setting(self, key: str, default_value: Any = None) -> Any:
        """Получение настройки"""
        try:
            with self.get_session() as session:
                setting = session.query(Settings).filter(Settings.key == key).first()
                
                if not setting:
                    return default_value
                
                # Преобразуем значение в нужный тип
                if setting.value_type == 'bool':
                    return setting.value.lower() == 'true'
                elif setting.value_type == 'int':
                    return int(setting.value)
                elif setting.value_type == 'float':
                    return float(setting.value)
                elif setting.value_type == 'json':
                    import ujson
                    return ujson.loads(setting.value)
                else:
                    return setting.value
                    
        except Exception as e:
            logger.error(f"❌ Ошибка get_setting: {e}")
            return default_value
    
    def set_setting(self, key: str, value: Any, value_type: str = 'string', 
                   description: str = None, updated_by: int = None):
        """Установка настройки"""
        try:
            with self.get_session() as session:
                setting = session.query(Settings).filter(Settings.key == key).first()
                
                # Преобразуем значение в строку
                if value_type == 'json':
                    import ujson
                    str_value = ujson.dumps(value)
                else:
                    str_value = str(value)
                
                if setting:
                    # Обновляем существующую настройку
                    setting.value = str_value
                    setting.value_type = value_type
                    setting.updated_by = updated_by
                    if description:
                        setting.description = description
                else:
                    # Создаем новую настройку
                    setting = Settings(
                        key=key,
                        value=str_value,
                        value_type=value_type,
                        description=description,
                        updated_by=updated_by
                    )
                    session.add(setting)
                
                session.commit()
                
                log_database_operation(logger, "UPSERT", "settings", 1, 
                                     key=key, value=str_value[:50])
                
        except Exception as e:
            logger.error(f"❌ Ошибка set_setting: {e}")
            raise
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Получение всех настроек"""
        try:
            with self.get_session() as session:
                settings = session.query(Settings).all()
                
                result = {}
                for setting in settings:
                    if setting.value_type == 'bool':
                        result[setting.key] = setting.value.lower() == 'true'
                    elif setting.value_type == 'int':
                        result[setting.key] = int(setting.value)
                    elif setting.value_type == 'float':
                        result[setting.key] = float(setting.value)
                    elif setting.value_type == 'json':
                        import ujson
                        result[setting.key] = ujson.loads(setting.value)
                    else:
                        result[setting.key] = setting.value
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Ошибка get_all_settings: {e}")
            return {}
    
    # --- Статистика ПЛАН 1 ---
    
    def get_basic_stats(self) -> Dict[str, Any]:
        """Получение базовой статистики"""
        try:
            with self.get_session() as session:
                stats = {
                    'total_users': session.query(User).count(),
                    'total_admins': session.query(User).filter(User.is_admin == True).count(),
                    'total_links': session.query(Link).filter(Link.is_active == True).count(),
                    'links_today': session.query(Link).filter(
                        and_(
                            Link.is_active == True,
                            Link.created_at >= datetime.now().replace(hour=0, minute=0, second=0)
                        )
                    ).count(),
                    'active_users_week': session.query(User).filter(
                        User.last_seen_at >= datetime.now() - timedelta(days=7)
                    ).count()
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Ошибка get_basic_stats: {e}")
            return {}
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики пользователя"""
        try:
            with self.get_session() as session:
                user = session.query(User).filter(User.user_id == user_id).first()
                
                if not user:
                    return {}
                
                # Базовая статистика
                total_links = session.query(Link).filter(
                    and_(Link.user_id == user_id, Link.is_active == True)
                ).count()
                
                links_this_month = session.query(Link).filter(
                    and_(
                        Link.user_id == user_id,
                        Link.is_active == True,
                        Link.created_at >= datetime.now().replace(day=1, hour=0, minute=0, second=0)
                    )
                ).count()
                
                stats = {
                    'user_id': user_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'is_admin': user.is_admin,
                    'total_links': total_links,
                    'links_this_month': links_this_month,
                    'member_since': user.created_at,
                    'last_seen': user.last_seen_at,
                    
                    # ПЛАН 2: Статистика кармы (ЗАГЛУШКИ)
                    # 'karma_points': 0,
                    # 'rank': 'Новенький',
                    # 'total_approvals': 0,
                    
                    # ПЛАН 3: Статистика ИИ и форм (ЗАГЛУШКИ)
                    # 'ai_interactions': 0,
                    # 'presave_requests': 0,
                    # 'approval_claims': 0,
                    # 'messages_count': 0,
                }
                
                return stats
                
        except Exception as e:
            logger.error(f"❌ Ошибка get_user_stats: {e}")
            return {}
    
    # ============================================
    # ПЛАН 2: CRUD ДЛЯ СИСТЕМЫ КАРМЫ (ЗАГЛУШКИ)
    # ============================================
    
    # def get_or_create_karma(self, user_id: int) -> UserKarma:
    #     """Получение или создание записи кармы пользователя"""
    #     try:
    #         with self.get_session() as session:
    #             karma = session.query(UserKarma).filter(UserKarma.user_id == user_id).first()
    #             
    #             if not karma:
    #                 # Проверяем админа
    #                 is_admin = user_id in self._get_admin_ids()
    #                 initial_karma = int(os.getenv('ADMIN_KARMA', '100500')) if is_admin else 0
    #                 
    #                 karma = UserKarma(
    #                     user_id=user_id,
    #                     karma_points=initial_karma,
    #                     rank=self._calculate_rank(initial_karma)
    #                 )
    #                 session.add(karma)
    #                 session.commit()
    #                 
    #                 log_database_operation(logger, "CREATE", "user_karma", 1, user_id=user_id)
    #             
    #             return karma
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка get_or_create_karma: {e}")
    #         raise
    
    # def update_karma(self, user_id: int, new_karma: int, admin_id: int, reason: str = None) -> bool:
    #     """Обновление кармы пользователя"""
    #     try:
    #         with self.get_session() as session:
    #             karma = session.query(UserKarma).filter(UserKarma.user_id == user_id).first()
    #             
    #             if not karma:
    #                 karma = self.get_or_create_karma(user_id)
    #             
    #             old_karma = karma.karma_points
    #             karma.karma_points = new_karma
    #             karma.rank = self._calculate_rank(new_karma)
    #             
    #             # Записываем в историю
    #             history = KarmaHistory(
    #                 user_id=user_id,
    #                 admin_id=admin_id,
    #                 change_amount=new_karma - old_karma,
    #                 old_karma=old_karma,
    #                 new_karma=new_karma,
    #                 reason=reason
    #             )
    #             session.add(history)
    #             
    #             session.commit()
    #             
    #             log_database_operation(logger, "UPDATE", "user_karma", 1, 
    #                                  user_id=user_id, old_karma=old_karma, new_karma=new_karma)
    #             
    #             return True
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка update_karma: {e}")
    #         return False
    
    # def _calculate_rank(self, karma_points: int) -> str:
    #     """Расчет звания по карме"""
    #     if karma_points >= int(os.getenv('RANK_AMBASSADOR_MIN', '31')):
    #         return '💎 Амбассадорище'
    #     elif karma_points >= int(os.getenv('RANK_MEGA_MIN', '16')):
    #         return '🥇 Мега-человечище'
    #     elif karma_points >= int(os.getenv('RANK_HOPE_MIN', '6')):
    #         return '🥈 Надежда сообщества'
    #     else:
    #         return '🥉 Новенький'
    
    # ============================================
    # ПЛАН 3: CRUD ДЛЯ ИИ И ФОРМ (ЗАГЛУШКИ)
    # ============================================
    
    # def create_presave_request(self, user_id: int, description: str, 
    #                           links: List[str], message_id: int = None, 
    #                           thread_id: int = None) -> PresaveRequest:
    #     """Создание заявки на пресейв"""
    #     # Реализация в ПЛАНЕ 3
    #     pass
    
    # def create_approval_claim(self, user_id: int, comment: str = None, 
    #                          screenshots: List[str] = None) -> ApprovalClaim:
    #     """Создание заявки о совершенном пресейве"""
    #     # Реализация в ПЛАНЕ 3
    #     pass
    
    # def log_ai_interaction(self, user_id: int, prompt: str, response: str, 
    #                       model: str, tokens_used: int) -> AIInteraction:
    #     """Логирование взаимодействия с ИИ"""
    #     # Реализация в ПЛАНЕ 3
    #     pass
    
    # ============================================
    # ПЛАН 4: CRUD ДЛЯ BACKUP (ЗАГЛУШКИ)
    # ============================================
    
    # def create_backup_record(self, filename: str, file_size_mb: float, 
    #                         backup_type: str = 'manual', created_by: int = None) -> BackupHistory:
    #     """Создание записи о backup"""
    #     # Реализация в ПЛАНЕ 4
    #     pass
    
    # def get_backup_history(self, limit: int = 50) -> List[BackupHistory]:
    #     """Получение истории backup операций"""
    #     # Реализация в ПЛАНЕ 4
    #     pass


if __name__ == "__main__":
    """Тестирование менеджера БД"""
    import os
    from datetime import datetime
    
    # Тестовая база в памяти
    test_db_url = "sqlite:///:memory:"
    
    print("🧪 Тестирование DatabaseManager...")
    
    try:
        # Создание менеджера
        db = DatabaseManager(test_db_url)
        
        # Создание таблиц
        db.create_tables()
        
        # Тестирование пользователей
        print("\n👤 Тестирование пользователей:")
        user1 = db.get_or_create_user(12345, "testuser", "Test", "User")
        print(f"Создан пользователь: {user1}")
        
        user2 = db.get_or_create_user(12345, "testuser_updated", "Test Updated")
        print(f"Обновлен пользователь: {user2}")
        
        # Тестирование ссылок
        print("\n🔗 Тестирование ссылок:")
        link1 = db.add_link(12345, "https://example.com", "Тестовая ссылка", 1001, 2)
        print(f"Добавлена ссылка: {link1}")
        
        link2 = db.add_link(12345, "https://test.org", "Еще одна ссылка", 1002, 3)
        print(f"Добавлена ссылка: {link2}")
        
        # Получение последних ссылок
        recent_links = db.get_recent_links(10)
        print(f"Последние ссылки: {len(recent_links)} шт.")
        
        # Тестирование настроек
        print("\n⚙️ Тестирование настроек:")
        db.set_setting("test_setting", "test_value", "string", "Тестовая настройка")
        value = db.get_setting("test_setting")
        print(f"Настройка test_setting: {value}")
        
        db.set_setting("bot_enabled", True, "bool", "Статус бота")
        enabled = db.get_setting("bot_enabled")
        print(f"Бот включен: {enabled}")
        
        # Тестирование статистики
        print("\n📊 Тестирование статистики:")
        basic_stats = db.get_basic_stats()
        print(f"Базовая статистика: {basic_stats}")
        
        user_stats = db.get_user_stats(12345)
        print(f"Статистика пользователя: {user_stats}")
        
        # Очистка ссылок
        print("\n🗑️ Тестирование очистки:")
        cleared = db.clear_all_links()
        print(f"Очищено ссылок: {cleared}")
        
        db.close()
        print("\n✅ Тестирование завершено успешно!")
        
    except Exception as e:
        print(f"\n❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()