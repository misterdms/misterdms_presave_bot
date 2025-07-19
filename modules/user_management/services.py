"""
Modules/user_management/services.py - Бизнес-логика модуля
Do Presave Reminder Bot v29.07

Сервисы для управления пользователями, кармой и статистикой
"""

import asyncio
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import selectinload

from .models import MusicUser, KarmaHistory, UserStatistics, UserSession
from .models import get_rank_title_by_karma, calculate_presave_ratio, calculate_karma_links_ratio
from core.exceptions import UserError, UserNotFoundError, KarmaError, ValidationError
from utils.logger import get_module_logger, log_user_action


class UserService:
    """Сервис управления пользователями"""
    
    def __init__(self, database, settings):
        """
        Инициализация сервиса
        
        Args:
            database: Ядро базы данных
            settings: Настройки системы
        """
        self.database = database
        self.settings = settings
        self.logger = get_module_logger("user_service")
        
        # Настройки кармы
        self.karma_settings = {
            'max_karma': 100500,
            'min_karma': 0,
            'admin_karma': 100500,
            'newbie_karma': 0
        }
    
    # === УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ===
    
    async def get_user(self, user_id: int) -> Optional[MusicUser]:
        """Получение пользователя по ID"""
        try:
            async with self.database.get_async_session() as session:
                user = await session.get(MusicUser, user_id)
                return user
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения пользователя {user_id}: {e}")
            return None
    
    async def get_user_by_username(self, username: str, group_id: int = None) -> Optional[MusicUser]:
        """Получение пользователя по username"""
        try:
            async with self.database.get_async_session() as session:
                query = session.query(MusicUser).filter(MusicUser.username == username)
                
                if group_id:
                    query = query.filter(MusicUser.group_id == group_id)
                
                user = await query.first()
                return user
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения пользователя @{username}: {e}")
            return None
    
    async def create_user(self, user_data: Dict[str, Any]) -> MusicUser:
        """Создание нового пользователя"""
        try:
            # Валидация данных
            required_fields = ['user_id', 'group_id']
            for field in required_fields:
                if field not in user_data:
                    raise ValidationError(f"Отсутствует обязательное поле: {field}")
            
            # Проверяем, не существует ли уже пользователь
            existing_user = await self.get_user(user_data['user_id'])
            if existing_user:
                raise UserError(f"Пользователь {user_data['user_id']} уже существует")
            
            async with self.database.get_async_session() as session:
                # Создаем пользователя
                user = MusicUser(
                    user_id=user_data['user_id'],
                    group_id=user_data['group_id'],
                    username=user_data.get('username'),
                    first_name=user_data.get('first_name'),
                    last_name=user_data.get('last_name'),
                    music_genre=user_data.get('music_genre'),
                    karma_points=self.karma_settings['newbie_karma'],
                    rank_title=get_rank_title_by_karma(self.karma_settings['newbie_karma']),
                    is_admin=self._is_admin(user_data['user_id'])
                )
                
                session.add(user)
                await session.commit()
                await session.refresh(user)
                
                # Если админ, устанавливаем админскую карму
                if user.is_admin:
                    await self.set_karma(
                        user.user_id,
                        self.karma_settings['admin_karma'],
                        "Админские права",
                        change_type="admin_adjustment"
                    )
                    await session.refresh(user)
                
                log_user_action(user.user_id, "user_created", {
                    'username': user.username,
                    'genre': user.music_genre,
                    'is_admin': user.is_admin
                })
                
                self.logger.info(f"✅ Создан пользователь: {user.user_id} (@{user.username})")
                return user
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка создания пользователя: {e}")
            raise UserError(f"Не удалось создать пользователя: {e}")
    
    async def update_user(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Обновление данных пользователя"""
        try:
            async with self.database.get_async_session() as session:
                user = await session.get(MusicUser, user_id)
                if not user:
                    raise UserNotFoundError(f"Пользователь {user_id} не найден")
                
                # Обновляем поля
                for field, value in updates.items():
                    if hasattr(user, field) and field not in ['id', 'user_id']:
                        setattr(user, field, value)
                
                # Обновляем время активности
                user.update_activity()
                
                await session.commit()
                
                log_user_action(user_id, "user_updated", updates)
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка обновления пользователя {user_id}: {e}")
            raise UserError(f"Не удалось обновить пользователя: {e}")
    
    async def update_last_activity(self, user_id: int):
        """Обновление времени последней активности"""
        try:
            async with self.database.get_async_session() as session:
                user = await session.get(MusicUser, user_id)
                if user:
                    user.update_activity()
                    await session.commit()
        except Exception as e:
            self.logger.error(f"❌ Ошибка обновления активности {user_id}: {e}")
    
    async def get_users_by_group(self, group_id: int, limit: int = 100, offset: int = 0) -> List[MusicUser]:
        """Получение пользователей группы"""
        try:
            async with self.database.get_async_session() as session:
                query = (
                    session.query(MusicUser)
                    .filter(MusicUser.group_id == group_id)
                    .filter(MusicUser.is_active == True)
                    .order_by(desc(MusicUser.karma_points))
                    .limit(limit)
                    .offset(offset)
                )
                
                users = await query.all()
                return users
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения пользователей группы {group_id}: {e}")
            return []
    
    # === УПРАВЛЕНИЕ КАРМОЙ ===
    
    async def get_karma(self, user_id: int) -> Optional[int]:
        """Получение кармы пользователя"""
        user = await self.get_user(user_id)
        return user.karma_points if user else None
    
    async def change_karma(self, user_id: int, change_amount: int, reason: str, 
                          changed_by: int = None, change_type: str = "manual") -> bool:
        """Изменение кармы пользователя"""
        try:
            async with self.database.get_async_session() as session:
                user = await session.get(MusicUser, user_id)
                if not user:
                    raise UserNotFoundError(f"Пользователь {user_id} не найден")
                
                # Проверяем возможность изменения
                can_change, error_msg = user.can_change_karma(change_amount, self.karma_settings['max_karma'])
                if not can_change:
                    raise KarmaError(error_msg)
                
                # Сохраняем старое значение
                karma_before = user.karma_points
                new_karma = karma_before + change_amount
                
                # Обновляем карму
                user.karma_points = new_karma
                user.rank_title = get_rank_title_by_karma(new_karma)
                user.update_activity()
                
                # Записываем в историю
                history_entry = KarmaHistory(
                    user_id=user_id,
                    group_id=user.group_id,
                    karma_change=change_amount,
                    karma_before=karma_before,
                    karma_after=new_karma,
                    reason=reason,
                    change_type=change_type,
                    changed_by_user_id=changed_by
                )
                
                session.add(history_entry)
                await session.commit()
                
                log_user_action(user_id, "karma_changed", {
                    'old_karma': karma_before,
                    'new_karma': new_karma,
                    'change': change_amount,
                    'reason': reason,
                    'changed_by': changed_by
                })
                
                self.logger.info(f"✅ Карма изменена: {user_id} {karma_before}→{new_karma} ({change_amount:+d})")
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка изменения кармы {user_id}: {e}")
            raise KarmaError(f"Не удалось изменить карму: {e}")
    
    async def set_karma(self, user_id: int, karma_value: int, reason: str, 
                       changed_by: int = None, change_type: str = "manual") -> bool:
        """Установка точного значения кармы"""
        try:
            user = await self.get_user(user_id)
            if not user:
                raise UserNotFoundError(f"Пользователь {user_id} не найден")
            
            change_amount = karma_value - user.karma_points
            
            if change_amount == 0:
                return True  # Карма уже имеет нужное значение
            
            return await self.change_karma(user_id, change_amount, reason, changed_by, change_type)
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка установки кармы {user_id}: {e}")
            raise KarmaError(f"Не удалось установить карму: {e}")
    
    async def give_gratitude_karma(self, giver_id: int, receiver_username: str, context: str = "") -> bool:
        """Начисление кармы за благодарность"""
        try:
            # Находим получателя по username
            receiver = await self.get_user_by_username(receiver_username)
            if not receiver:
                self.logger.warning(f"⚠️ Пользователь @{receiver_username} не найден для благодарности")
                return False
            
            # Проверяем, что не благодарят самого себя
            if giver_id == receiver.user_id:
                return False
            
            # Начисляем 1 карму
            reason = f"Благодарность от пользователя {giver_id}"
            if context:
                reason += f" | {context[:100]}"
            
            await self.change_karma(
                receiver.user_id,
                1,  # +1 карма за благодарность
                reason,
                changed_by=giver_id,
                change_type="gratitude"
            )
            
            log_user_action(giver_id, "gratitude_given", {
                'receiver_id': receiver.user_id,
                'receiver_username': receiver_username
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка начисления кармы за благодарность: {e}")
            return False
    
    async def get_karma_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение истории изменений кармы"""
        try:
            async with self.database.get_async_session() as session:
                query = (
                    session.query(KarmaHistory)
                    .filter(KarmaHistory.user_id == user_id)
                    .order_by(desc(KarmaHistory.created_at))
                    .limit(limit)
                )
                
                history = await query.all()
                
                return [
                    {
                        'change': entry.karma_change,
                        'reason': entry.reason,
                        'date': entry.created_at.strftime('%d.%m.%Y %H:%M'),
                        'type': entry.change_type,
                        'karma_before': entry.karma_before,
                        'karma_after': entry.karma_after
                    }
                    for entry in history
                ]
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения истории кармы {user_id}: {e}")
            return []
    
    # === СТАТИСТИКА И РЕЙТИНГИ ===
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Получение статистики пользователя"""
        try:
            user = await self.get_user(user_id)
            if not user:
                raise UserNotFoundError(f"Пользователь {user_id} не найден")
            
            # Базовая статистика
            stats = {
                'user_info': {
                    'user_id': user.user_id,
                    'username': user.username,
                    'display_name': user.get_display_name(),
                    'first_name': user.first_name,
                    'music_genre': user.music_genre
                },
                'karma': {
                    'points': user.karma_points,
                    'rank': user.rank_title,
                    'rank_emoji': user.get_rank_emoji(),
                    'percentage': user.get_karma_percentage(),
                    'is_newbie': user.is_newbie()
                },
                'activity': {
                    'presaves_given': user.presaves_given,
                    'presaves_received': user.presaves_received,
                    'presave_ratio': float(user.presave_ratio),
                    'links_published': user.links_published,
                    'karma_to_links_ratio': float(user.karma_to_links_ratio)
                },
                'meta': {
                    'registration_date': user.registration_date.strftime('%d.%m.%Y'),
                    'last_activity': user.last_activity.strftime('%d.%m.%Y %H:%M'),
                    'is_admin': user.is_admin,
                    'webapp_visits': user.webapp_visit_count
                }
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения статистики {user_id}: {e}")
            raise UserError(f"Не удалось получить статистику: {e}")
    
    async def get_leaderboard(self, group_id: int, limit: int = 10, 
                             order_by: str = "karma") -> List[Dict[str, Any]]:
        """Получение лидерборда"""
        try:
            async with self.database.get_async_session() as session:
                # Определяем поле сортировки
                order_field = {
                    'karma': MusicUser.karma_points,
                    'presaves_given': MusicUser.presaves_given,
                    'presaves_received': MusicUser.presaves_received,
                    'links_published': MusicUser.links_published,
                    'activity': MusicUser.last_activity
                }.get(order_by, MusicUser.karma_points)
                
                query = (
                    session.query(MusicUser)
                    .filter(MusicUser.group_id == group_id)
                    .filter(MusicUser.is_active == True)
                    .order_by(desc(order_field))
                    .limit(limit)
                )
                
                users = await query.all()
                
                leaderboard = []
                for position, user in enumerate(users, 1):
                    leaderboard.append({
                        'position': position,
                        'user_id': user.user_id,
                        'display_name': user.get_display_name(),
                        'karma': user.karma_points,
                        'rank': user.rank_title,
                        'rank_emoji': user.get_rank_emoji(),
                        'presaves_given': user.presaves_given,
                        'presaves_received': user.presaves_received,
                        'links_published': user.links_published,
                        'music_genre': user.music_genre
                    })
                
                return leaderboard
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения лидерборда: {e}")
            return []
    
    async def get_group_statistics(self, group_id: int) -> Dict[str, Any]:
        """Получение общей статистики группы"""
        try:
            async with self.database.get_async_session() as session:
                # Общее количество пользователей
                total_users = await session.query(func.count(MusicUser.id)).filter(
                    MusicUser.group_id == group_id,
                    MusicUser.is_active == True
                ).scalar()
                
                # Статистика по рангам
                rank_stats = await session.query(
                    MusicUser.rank_title,
                    func.count(MusicUser.id)
                ).filter(
                    MusicUser.group_id == group_id,
                    MusicUser.is_active == True
                ).group_by(MusicUser.rank_title).all()
                
                # Общая статистика активности
                activity_stats = await session.query(
                    func.sum(MusicUser.presaves_given),
                    func.sum(MusicUser.presaves_received),
                    func.sum(MusicUser.links_published),
                    func.avg(MusicUser.karma_points)
                ).filter(
                    MusicUser.group_id == group_id,
                    MusicUser.is_active == True
                ).first()
                
                # Топ жанры
                genre_stats = await session.query(
                    MusicUser.music_genre,
                    func.count(MusicUser.id)
                ).filter(
                    MusicUser.group_id == group_id,
                    MusicUser.is_active == True,
                    MusicUser.music_genre.isnot(None)
                ).group_by(MusicUser.music_genre).order_by(
                    desc(func.count(MusicUser.id))
                ).limit(5).all()
                
                return {
                    'total_users': total_users or 0,
                    'rank_distribution': {rank: count for rank, count in rank_stats},
                    'activity': {
                        'total_presaves_given': activity_stats[0] or 0,
                        'total_presaves_received': activity_stats[1] or 0,
                        'total_links_published': activity_stats[2] or 0,
                        'average_karma': round(activity_stats[3] or 0, 1)
                    },
                    'top_genres': [{'genre': genre, 'count': count} for genre, count in genre_stats]
                }
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения статистики группы {group_id}: {e}")
            return {}
    
    # === СООТНОШЕНИЯ И МЕТРИКИ ===
    
    async def update_presave_stats(self, user_id: int, presaves_given: int = 0, 
                                  presaves_received: int = 0, links_published: int = 0):
        """Обновление статистики пресейвов"""
        try:
            async with self.database.get_async_session() as session:
                user = await session.get(MusicUser, user_id)
                if not user:
                    return False
                
                # Обновляем счетчики
                if presaves_given > 0:
                    user.presaves_given += presaves_given
                if presaves_received > 0:
                    user.presaves_received += presaves_received
                if links_published > 0:
                    user.links_published += links_published
                
                # Пересчитываем соотношения
                user.presave_ratio = calculate_presave_ratio(user.presaves_given, user.presaves_received)
                user.karma_to_links_ratio = calculate_karma_links_ratio(user.karma_points, user.links_published)
                
                user.update_activity()
                await session.commit()
                
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка обновления статистики пресейвов {user_id}: {e}")
            return False
    
    async def set_karma_ratio(self, user_id: int, links: int, karma: int) -> bool:
        """Установка соотношения карма:ссылки (админская функция)"""
        try:
            async with self.database.get_async_session() as session:
                user = await session.get(MusicUser, user_id)
                if not user:
                    raise UserNotFoundError(f"Пользователь {user_id} не найден")
                
                # Обновляем данные
                user.links_published = links
                user.karma_to_links_ratio = calculate_karma_links_ratio(karma, links)
                
                # Если карма отличается, записываем изменение
                if user.karma_points != karma:
                    await self.set_karma(user_id, karma, f"Корректировка соотношения {karma}:{links}")
                
                user.update_activity()
                await session.commit()
                
                log_user_action(user_id, "karma_ratio_updated", {
                    'links': links,
                    'karma': karma,
                    'ratio': float(user.karma_to_links_ratio)
                })
                
                return True
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка установки соотношения кармы {user_id}: {e}")
            raise UserError(f"Не удалось установить соотношение: {e}")
    
    # === ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===
    
    def _is_admin(self, user_id: int) -> bool:
        """Проверка, является ли пользователь админом"""
        admin_ids = getattr(self.settings, 'admin_ids', [])
        return user_id in admin_ids
    
    async def search_users(self, query: str, group_id: int = None, limit: int = 10) -> List[MusicUser]:
        """Поиск пользователей по имени/username"""
        try:
            async with self.database.get_async_session() as session:
                search_filter = f"%{query}%"
                
                db_query = session.query(MusicUser).filter(
                    and_(
                        MusicUser.is_active == True,
                        func.or_(
                            MusicUser.username.ilike(search_filter),
                            MusicUser.first_name.ilike(search_filter),
                            MusicUser.last_name.ilike(search_filter)
                        )
                    )
                )
                
                if group_id:
                    db_query = db_query.filter(MusicUser.group_id == group_id)
                
                users = await db_query.limit(limit).all()
                return users
                
        except Exception as e:
            self.logger.error(f"❌ Ошибка поиска пользователей: {e}")
            return []


if __name__ == "__main__":
    # Тестирование сервиса (требует настроенную БД)
    print("🧪 Модуль UserService готов к тестированию")
    print("📋 Доступные методы:")
    
    methods = [method for method in dir(UserService) if not method.startswith('_')]
    for method in methods:
        print(f"  • {method}")
    
    print("✅ Сервис управления пользователями инициализирован")