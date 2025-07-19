"""
Core/database_core.py - Ядро работы с базой данных
Do Presave Reminder Bot v29.07

Управление PostgreSQL базой данных с поддержкой всех модулей системы
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Type
from contextlib import asynccontextmanager
import traceback

try:
    from sqlalchemy import create_engine, text, MetaData, Table
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import QueuePool
    from sqlalchemy.exc import SQLAlchemyError, OperationalError
    import asyncpg
except ImportError as e:
    raise ImportError(f"SQLAlchemy или asyncpg не установлены: {e}")

from config.settings import Settings
from utils.logger import get_logger
from core.exceptions import DatabaseConnectionError, DatabaseOperationError


# Базовый класс для всех моделей
Base = declarative_base()


class DatabaseCore:
    """Ядро работы с базой данных PostgreSQL"""
    
    def __init__(self, settings: Settings):
        """
        Инициализация ядра БД
        
        Args:
            settings: Настройки системы
        """
        self.settings = settings
        self.logger = get_logger(__name__)
        
        # Движки SQLAlchemy
        self.sync_engine = None
        self.async_engine = None
        self.async_session_maker = None
        self.sync_session_maker = None
        
        # Метаданные
        self.metadata = MetaData()
        
        # Статистика
        self.connection_pool_stats = {}
        self.query_count = 0
        self.error_count = 0
        self.last_health_check = None
        
        # Состояние
        self.is_connected = False
        self.is_initialized = False
        
    async def initialize(self) -> bool:
        """Инициализация базы данных"""
        try:
            self.logger.info("🗃️ Инициализация базы данных PostgreSQL...")
            
            # Создание движков
            await self._create_engines()
            
            # Проверка подключения
            await self._test_connection()
            
            # Создание таблиц (если нужно)
            await self._setup_database_schema()
            
            # Создание сессий
            self._setup_sessions()
            
            self.is_initialized = True
            self.is_connected = True
            
            self.logger.info("✅ База данных успешно инициализирована")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации БД: {e}")
            self.logger.error(traceback.format_exc())
            raise DatabaseConnectionError(f"Не удалось инициализировать БД: {e}")
    
    async def _create_engines(self):
        """Создание движков SQLAlchemy"""
        db_url = self.settings.database.url
        
        if not db_url:
            raise ValueError("DATABASE_URL не установлен")
        
        # Преобразуем URL для async режима
        if db_url.startswith("postgresql://"):
            async_db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            async_db_url = db_url
        
        # Async движок
        self.async_engine = create_async_engine(
            async_db_url,
            poolclass=QueuePool,
            pool_size=self.settings.database.pool_size,
            max_overflow=10,
            pool_timeout=self.settings.database.pool_timeout,
            pool_recycle=3600,  # 1 час
            echo=self.settings.debug,  # SQL логи в debug режиме
            echo_pool=self.settings.debug
        )
        
        # Sync движок (для миграций и синхронных операций)
        self.sync_engine = create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=self.settings.database.pool_size,
            max_overflow=10,
            pool_timeout=self.settings.database.pool_timeout,
            pool_recycle=3600,
            echo=self.settings.debug
        )
        
        self.logger.info("🔧 Движки SQLAlchemy созданы")
    
    async def _test_connection(self):
        """Тестирование подключения к БД"""
        try:
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                
                if test_value != 1:
                    raise DatabaseConnectionError("Тестовый запрос вернул неверный результат")
            
            self.logger.info("🔗 Подключение к PostgreSQL успешно")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка подключения к БД: {e}")
            raise DatabaseConnectionError(f"Не удалось подключиться к БД: {e}")
    
    async def _setup_database_schema(self):
        """Настройка схемы базы данных"""
        try:
            # Если включен режим пересоздания таблиц
            if self.settings.database.force_recreate_tables:
                self.logger.warning("⚠️ FORCE_RECREATE_TABLES включен! Пересоздаем таблицы...")
                async with self.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
                    await conn.run_sync(Base.metadata.create_all)
                self.logger.info("🔄 Таблицы пересозданы")
            else:
                # Создаем только отсутствующие таблицы
                async with self.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                self.logger.info("📋 Схема БД проверена/создана")
            
            # Создание индексов и триггеров (если нужно)
            await self._create_additional_database_objects()
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка настройки схемы БД: {e}")
            raise
    
    async def _create_additional_database_objects(self):
        """Создание дополнительных объектов БД (индексы, триггеры, функции)"""
        try:
            # SQL для создания дополнительных объектов
            additional_sql = [
                # Функция обновления last_activity
                """
                CREATE OR REPLACE FUNCTION update_last_activity()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.last_activity = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """,
                
                # Функция автоматической установки кармы для админов
                """
                CREATE OR REPLACE FUNCTION set_admin_karma()
                RETURNS TRIGGER AS $$
                BEGIN
                    IF NEW.is_admin = TRUE AND (OLD IS NULL OR OLD.is_admin = FALSE) THEN
                        NEW.karma_points = 100500;
                        NEW.rank_title = 'Амбассадорище';
                    END IF;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """,
                
                # Функция для расчета соотношений кармы
                """
                CREATE OR REPLACE FUNCTION calculate_karma_ratios()
                RETURNS TRIGGER AS $$
                BEGIN
                    -- Расчет presave_ratio
                    IF NEW.presaves_received > 0 THEN
                        NEW.presave_ratio = ROUND(NEW.presaves_given::decimal / NEW.presaves_received::decimal, 2);
                    ELSE
                        NEW.presave_ratio = NEW.presaves_given::decimal;
                    END IF;
                    
                    -- Расчет karma_to_links_ratio
                    IF NEW.links_published > 0 THEN
                        NEW.karma_to_links_ratio = ROUND(NEW.karma_points::decimal / NEW.links_published::decimal, 2);
                    ELSE
                        NEW.karma_to_links_ratio = NEW.karma_points::decimal;
                    END IF;
                    
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            ]
            
            async with self.async_engine.begin() as conn:
                for sql in additional_sql:
                    try:
                        await conn.execute(text(sql))
                        self.logger.debug("✅ Выполнен SQL объект")
                    except Exception as e:
                        # Игнорируем ошибки "уже существует"
                        if "already exists" not in str(e).lower():
                            self.logger.warning(f"⚠️ Ошибка создания SQL объекта: {e}")
            
            self.logger.info("🔧 Дополнительные объекты БД созданы")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Ошибка создания дополнительных объектов: {e}")
            # Не критично для работы системы
    
    def _setup_sessions(self):
        """Настройка фабрик сессий"""
        # Async сессии
        self.async_session_maker = async_sessionmaker(
            bind=self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Sync сессии
        self.sync_session_maker = sessionmaker(
            bind=self.sync_engine,
            expire_on_commit=False
        )
        
        self.logger.info("🎭 Фабрики сессий настроены")
    
    # === МЕТОДЫ РАБОТЫ С СЕССИЯМИ ===
    
    @asynccontextmanager
    async def get_async_session(self):
        """Получение async сессии с автоматическим управлением"""
        if not self.async_session_maker:
            raise DatabaseOperationError("Async сессии не инициализированы")
        
        session = self.async_session_maker()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            self.error_count += 1
            self.logger.error(f"❌ Ошибка в async сессии: {e}")
            raise DatabaseOperationError(f"Ошибка БД операции: {e}")
        finally:
            await session.close()
            self.query_count += 1
    
    @asynccontextmanager
    async def get_sync_session(self):
        """Получение sync сессии с автоматическим управлением"""
        if not self.sync_session_maker:
            raise DatabaseOperationError("Sync сессии не инициализированы")
        
        session = self.sync_session_maker()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.error_count += 1
            self.logger.error(f"❌ Ошибка в sync сессии: {e}")
            raise DatabaseOperationError(f"Ошибка БД операции: {e}")
        finally:
            session.close()
            self.query_count += 1
    
    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    
    async def execute_raw_sql(self, sql: str, params: Optional[Dict] = None) -> Any:
        """Выполнение сырого SQL запроса"""
        try:
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text(sql), params or {})
                return result
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"❌ Ошибка выполнения SQL: {e}")
            raise DatabaseOperationError(f"Ошибка SQL запроса: {e}")
    
    async def check_table_exists(self, table_name: str, schema: str = "public") -> bool:
        """Проверка существования таблицы"""
        try:
            sql = """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = :schema 
                    AND table_name = :table_name
                );
            """
            result = await self.execute_raw_sql(sql, {
                "schema": schema,
                "table_name": table_name
            })
            return result.scalar()
        except Exception as e:
            self.logger.error(f"❌ Ошибка проверки таблицы {table_name}: {e}")
            return False
    
    async def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Получение статистики таблицы"""
        try:
            sql = """
                SELECT 
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_rows,
                    n_dead_tup as dead_rows,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                FROM pg_stat_user_tables 
                WHERE tablename = :table_name;
            """
            result = await self.execute_raw_sql(sql, {"table_name": table_name})
            row = result.fetchone()
            
            if row:
                return {
                    "inserts": row.inserts or 0,
                    "updates": row.updates or 0,
                    "deletes": row.deletes or 0,
                    "live_rows": row.live_rows or 0,
                    "dead_rows": row.dead_rows or 0,
                    "size": row.size or "0 bytes"
                }
            else:
                return {"error": "Table not found"}
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения статистики {table_name}: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья базы данных"""
        try:
            start_time = time.time()
            
            # Простой запрос для проверки
            async with self.async_engine.begin() as conn:
                result = await conn.execute(text("SELECT version()"))
                db_version = result.scalar()
                
                # Проверка подключений
                pool_status = self.async_engine.pool.status()
                
            response_time = time.time() - start_time
            self.last_health_check = time.time()
            
            return {
                "healthy": True,
                "database_version": db_version,
                "response_time_ms": round(response_time * 1000, 2),
                "pool_status": pool_status,
                "query_count": self.query_count,
                "error_count": self.error_count,
                "is_connected": self.is_connected,
                "is_initialized": self.is_initialized
            }
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"❌ Ошибка health check БД: {e}")
            return {
                "healthy": False,
                "error": str(e),
                "query_count": self.query_count,
                "error_count": self.error_count,
                "is_connected": False
            }
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Получение общей статистики базы данных"""
        try:
            # Размер БД
            db_name = self.async_engine.url.database
            size_sql = "SELECT pg_size_pretty(pg_database_size(:db_name)) as size"
            size_result = await self.execute_raw_sql(size_sql, {"db_name": db_name})
            db_size = size_result.scalar()
            
            # Количество подключений
            connections_sql = """
                SELECT count(*) as active_connections
                FROM pg_stat_activity 
                WHERE datname = :db_name AND state = 'active'
            """
            conn_result = await self.execute_raw_sql(connections_sql, {"db_name": db_name})
            active_connections = conn_result.scalar()
            
            # Статистика таблиц
            tables_sql = """
                SELECT 
                    COUNT(*) as table_count,
                    SUM(n_live_tup) as total_rows
                FROM pg_stat_user_tables
            """
            tables_result = await self.execute_raw_sql(tables_sql)
            tables_row = tables_result.fetchone()
            
            return {
                "database_size": db_size,
                "active_connections": active_connections,
                "table_count": tables_row.table_count or 0,
                "total_rows": tables_row.total_rows or 0,
                "pool_size": self.async_engine.pool.size(),
                "pool_checked_in": self.async_engine.pool.checkedin(),
                "pool_checked_out": self.async_engine.pool.checkedout(),
                "pool_overflow": self.async_engine.pool.overflow(),
                "query_count": self.query_count,
                "error_count": self.error_count
            }
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения статистики БД: {e}")
            return {"error": str(e)}
    
    async def backup_schema(self) -> str:
        """Создание backup схемы БД (только структура)"""
        try:
            # Получаем DDL всех таблиц
            ddl_sql = """
                SELECT 
                    'CREATE TABLE ' || schemaname || '.' || tablename || ' (' ||
                    array_to_string(
                        array_agg(
                            column_name || ' ' || data_type ||
                            CASE 
                                WHEN character_maximum_length IS NOT NULL 
                                THEN '(' || character_maximum_length || ')' 
                                ELSE '' 
                            END ||
                            CASE 
                                WHEN is_nullable = 'NO' THEN ' NOT NULL' 
                                ELSE '' 
                            END
                        ), 
                        ', '
                    ) || ');' as ddl
                FROM information_schema.columns 
                JOIN pg_stat_user_tables ON tablename = table_name
                WHERE table_schema = 'public'
                GROUP BY schemaname, tablename
                ORDER BY tablename;
            """
            
            result = await self.execute_raw_sql(ddl_sql)
            ddl_statements = [row.ddl for row in result.fetchall()]
            
            schema_backup = f"""
-- Do Presave Reminder Bot Database Schema Backup
-- Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
-- Database: {self.async_engine.url.database}

{chr(10).join(ddl_statements)}
"""
            
            self.logger.info("💾 Backup схемы БД создан")
            return schema_backup
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка backup схемы: {e}")
            raise DatabaseOperationError(f"Не удалось создать backup схемы: {e}")
    
    async def close(self):
        """Закрытие всех подключений"""
        self.logger.info("🔄 Закрытие подключений к БД...")
        
        self.is_connected = False
        
        try:
            if self.async_engine:
                await self.async_engine.dispose()
            
            if self.sync_engine:
                self.sync_engine.dispose()
            
            self.logger.info("✅ Все подключения к БД закрыты")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка закрытия подключений: {e}")


# === УТИЛИТЫ ===

async def test_database_connection(database_url: str) -> bool:
    """Тестирование подключения к БД"""
    try:
        if database_url.startswith("postgresql://"):
            async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            async_url = database_url
        
        engine = create_async_engine(async_url)
        
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            test_result = result.scalar()
        
        await engine.dispose()
        
        return test_result == 1
        
    except Exception as e:
        logging.error(f"❌ Ошибка тестирования БД: {e}")
        return False


if __name__ == "__main__":
    # Тестирование ядра БД
    import os
    from config.env_loader import load_environment
    
    print("🧪 Тестирование ядра базы данных...")
    
    # Загружаем переменные окружения
    load_environment()
    
    # Создаем настройки
    from config.settings import Settings
    settings = Settings()
    
    async def test():
        # Создаем ядро БД
        db_core = DatabaseCore(settings)
        
        # Инициализируем
        success = await db_core.initialize()
        
        if success:
            print("✅ БД инициализирована успешно")
            
            # Проверяем здоровье
            health = await db_core.health_check()
            print(f"📊 Health check: {health}")
            
            # Получаем статистику
            stats = await db_core.get_database_stats()
            print(f"📈 Статистика: {stats}")
            
            # Закрываем
            await db_core.close()
        else:
            print("❌ Ошибка инициализации БД")
    
    asyncio.run(test())