"""
Modules/user_management/validators.py - Валидация данных пользователей
Do Presave Reminder Bot v29.07

Валидация входных данных для системы управления пользователями и кармы
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from core.exceptions import ValidationError


class UserDataValidator:
    """Валидатор данных пользователей"""
    
    # Регулярные выражения для валидации
    USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
    GENRE_PATTERN = re.compile(r'^[а-яёa-z\s\-,]+$', re.IGNORECASE)
    
    # Ограничения
    MAX_NAME_LENGTH = 100
    MIN_NAME_LENGTH = 1
    MAX_USERNAME_LENGTH = 32
    MIN_USERNAME_LENGTH = 3
    
    @staticmethod
    def validate_user_creation_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Валидация данных для создания пользователя
        
        Args:
            data: Словарь с данными пользователя
            
        Returns:
            Tuple[bool, List[str]]: (валидность, список ошибок)
        """
        errors = []
        
        # Обязательные поля
        required_fields = ['user_id', 'group_id']
        for field in required_fields:
            if field not in data or data[field] is None:
                errors.append(f"Отсутствует обязательное поле: {field}")
        
        # Валидация user_id
        if 'user_id' in data:
            if not isinstance(data['user_id'], int) or data['user_id'] <= 0:
                errors.append("user_id должен быть положительным числом")
        
        # Валидация group_id  
        if 'group_id' in data:
            if not isinstance(data['group_id'], int):
                errors.append("group_id должен быть числом")
        
        # Валидация username (необязательно)
        if 'username' in data and data['username']:
            username = data['username']
            if len(username) > UserDataValidator.MAX_USERNAME_LENGTH:
                errors.append(f"Username слишком длинный (максимум {UserDataValidator.MAX_USERNAME_LENGTH} символов)")
            elif len(username) < UserDataValidator.MIN_USERNAME_LENGTH:
                errors.append(f"Username слишком короткий (минимум {UserDataValidator.MIN_USERNAME_LENGTH} символов)")
            elif not UserDataValidator.USERNAME_PATTERN.match(username):
                errors.append("Username может содержать только буквы, цифры и подчеркивания")
        
        # Валидация имени
        if 'first_name' in data and data['first_name']:
            first_name = str(data['first_name']).strip()
            if len(first_name) > UserDataValidator.MAX_NAME_LENGTH:
                errors.append(f"Имя слишком длинное (максимум {UserDataValidator.MAX_NAME_LENGTH} символов)")
            elif len(first_name) < UserDataValidator.MIN_NAME_LENGTH:
                errors.append("Имя не может быть пустым")
        
        # Валидация фамилии
        if 'last_name' in data and data['last_name']:
            last_name = str(data['last_name']).strip()
            if len(last_name) > UserDataValidator.MAX_NAME_LENGTH:
                errors.append(f"Фамилия слишком длинная (максимум {UserDataValidator.MAX_NAME_LENGTH} символов)")
        
        # Валидация жанра музыки
        if 'music_genre' in data and data['music_genre']:
            genre = str(data['music_genre']).strip()
            if len(genre) > 50:
                errors.append("Жанр музыки слишком длинный (максимум 50 символов)")
            elif not UserDataValidator.GENRE_PATTERN.match(genre):
                errors.append("Жанр может содержать только буквы, пробелы, дефисы и запятые")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_karma_change(karma_change: int, current_karma: int = 0, 
                            min_karma: int = 0, max_karma: int = 100500) -> Tuple[bool, Optional[str]]:
        """
        Валидация изменения кармы
        
        Args:
            karma_change: Изменение кармы
            current_karma: Текущая карма
            min_karma: Минимальная карма
            max_karma: Максимальная карма
            
        Returns:
            Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
        """
        if not isinstance(karma_change, int):
            return False, "Изменение кармы должно быть целым числом"
        
        if karma_change == 0:
            return False, "Изменение кармы не может быть равно нулю"
        
        new_karma = current_karma + karma_change
        
        if new_karma < min_karma:
            return False, f"Карма не может быть меньше {min_karma}"
        
        if new_karma > max_karma:
            return False, f"Карма не может превышать {max_karma}"
        
        # Ограничение на размер изменения (защита от случайных больших изменений)
        if abs(karma_change) > 1000:
            return False, "Слишком большое изменение кармы (максимум ±1000 за раз)"
        
        return True, None
    
    @staticmethod
    def validate_karma_ratio_format(ratio_str: str) -> Tuple[bool, Optional[Tuple[int, int]], Optional[str]]:
        """
        Валидация формата соотношения карма:ссылки
        
        Args:
            ratio_str: Строка в формате "карма:ссылки" (например, "15:3")
            
        Returns:
            Tuple[bool, Optional[Tuple[int, int]], Optional[str]]: 
                (валидность, (карма, ссылки), сообщение об ошибке)
        """
        if not ratio_str or not isinstance(ratio_str, str):
            return False, None, "Соотношение должно быть строкой"
        
        # Убираем пробелы
        ratio_str = ratio_str.strip()
        
        # Проверяем формат "число:число"
        if ':' not in ratio_str:
            return False, None, "Используйте формат 'карма:ссылки' (например, 15:3)"
        
        parts = ratio_str.split(':')
        if len(parts) != 2:
            return False, None, "Используйте формат 'карма:ссылки' (например, 15:3)"
        
        try:
            karma = int(parts[0].strip())
            links = int(parts[1].strip())
        except ValueError:
            return False, None, "Карма и ссылки должны быть целыми числами"
        
        # Валидация значений
        if karma < 0 or karma > 100500:
            return False, None, "Карма должна быть от 0 до 100500"
        
        if links < 0 or links > 10000:
            return False, None, "Количество ссылок должно быть от 0 до 10000"
        
        return True, (karma, links), None


class KarmaValidator:
    """Валидатор операций с кармой"""
    
    # Допустимые типы изменений кармы
    VALID_CHANGE_TYPES = {
        'manual', 'auto', 'gratitude', 'penalty', 
        'admin_adjustment', 'system_bonus', 'onboarding'
    }
    
    # Ограничения для разных типов изменений
    CHANGE_LIMITS = {
        'gratitude': (1, 1),        # +1 карма за благодарность
        'penalty': (-10, -1),       # штрафы от -1 до -10
        'manual': (-100, 100),      # ручные изменения
        'admin_adjustment': (-1000, 1000),  # админские корректировки
        'system_bonus': (1, 50),    # системные бонусы
        'onboarding': (0, 10)       # бонус за онбординг
    }
    
    @staticmethod
    def validate_karma_operation(user_id: int, karma_change: int, change_type: str, 
                                current_karma: int = 0, reason: str = "") -> Tuple[bool, Optional[str]]:
        """
        Валидация операции изменения кармы
        
        Args:
            user_id: ID пользователя
            karma_change: Изменение кармы
            change_type: Тип изменения
            current_karma: Текущая карма
            reason: Причина изменения
            
        Returns:
            Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
        """
        # Валидация user_id
        if not isinstance(user_id, int) or user_id <= 0:
            return False, "Некорректный ID пользователя"
        
        # Валидация типа изменения
        if change_type not in KarmaValidator.VALID_CHANGE_TYPES:
            return False, f"Недопустимый тип изменения: {change_type}"
        
        # Валидация размера изменения для типа
        if change_type in KarmaValidator.CHANGE_LIMITS:
            min_change, max_change = KarmaValidator.CHANGE_LIMITS[change_type]
            if not (min_change <= karma_change <= max_change):
                return False, f"Для типа '{change_type}' изменение должно быть от {min_change} до {max_change}"
        
        # Валидация причины
        if not reason or len(reason.strip()) < 3:
            return False, "Причина изменения кармы должна содержать минимум 3 символа"
        
        if len(reason) > 500:
            return False, "Причина слишком длинная (максимум 500 символов)"
        
        # Проверка результирующей кармы
        new_karma = current_karma + karma_change
        if new_karma < 0:
            return False, "Результирующая карма не может быть отрицательной"
        
        if new_karma > 100500:
            return False, "Результирующая карма не может превышать 100500"
        
        return True, None


class OnboardingValidator:
    """Валидатор данных онбординга"""
    
    # Допустимые жанры музыки
    VALID_GENRES = {
        'Рок', 'Поп', 'Хип-хоп', 'Рэп', 'Электронная', 'Джаз', 'Блюз', 
        'Кантри', 'Фолк', 'Классическая', 'Металл', 'Панк', 'Регги',
        'R&B', 'Соул', 'Фанк', 'Диско', 'Альтернатива', 'Инди', 'Гранж',
        'Тeхно', 'Хаус', 'Транс', 'Дабстеп', 'Драм-н-бэйс', 'Амбиент',
        'Другое'
    }
    
    @staticmethod
    def validate_onboarding_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Валидация данных онбординга нового пользователя
        
        Args:
            data: Данные онбординга
            
        Returns:
            Tuple[bool, List[str]]: (валидность, список ошибок)
        """
        errors = []
        
        # Валидация жанра музыки
        if 'music_genre' in data:
            genre = data['music_genre']
            if genre and genre not in OnboardingValidator.VALID_GENRES:
                errors.append(f"Неизвестный жанр музыки: {genre}")
        
        # Валидация базовых данных пользователя
        is_valid, user_errors = UserDataValidator.validate_user_creation_data(data)
        errors.extend(user_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_onboarding_step(step: int, max_steps: int = 3) -> Tuple[bool, Optional[str]]:
        """
        Валидация шага онбординга
        
        Args:
            step: Номер шага
            max_steps: Максимальное количество шагов
            
        Returns:
            Tuple[bool, Optional[str]]: (валидность, сообщение об ошибке)
        """
        if not isinstance(step, int):
            return False, "Номер шага должен быть целым числом"
        
        if step < 1 or step > max_steps:
            return False, f"Номер шага должен быть от 1 до {max_steps}"
        
        return True, None


def validate_user_input(func):
    """
    Декоратор для автоматической валидации пользовательского ввода
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Ошибка валидации: {e}")
    
    return wrapper


# Вспомогательные функции

def sanitize_username(username: str) -> str:
    """Очистка username от недопустимых символов"""
    if not username:
        return ""
    
    # Убираем символ @ если есть
    username = username.lstrip('@')
    
    # Убираем недопустимые символы
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', username)
    
    # Ограничиваем длину
    if len(sanitized) > UserDataValidator.MAX_USERNAME_LENGTH:
        sanitized = sanitized[:UserDataValidator.MAX_USERNAME_LENGTH]
    
    return sanitized


def sanitize_name(name: str) -> str:
    """Очистка имени от недопустимых символов"""
    if not name:
        return ""
    
    # Убираем лишние пробелы и ограничиваем длину
    sanitized = str(name).strip()
    if len(sanitized) > UserDataValidator.MAX_NAME_LENGTH:
        sanitized = sanitized[:UserDataValidator.MAX_NAME_LENGTH]
    
    return sanitized


def sanitize_genre(genre: str) -> str:
    """Очистка жанра музыки"""
    if not genre:
        return ""
    
    # Приводим к стандартному виду
    sanitized = str(genre).strip().title()
    
    # Проверяем на соответствие допустимым жанрам
    if sanitized in OnboardingValidator.VALID_GENRES:
        return sanitized
    
    # Если не найден точно, пытаемся найти частичное совпадение
    for valid_genre in OnboardingValidator.VALID_GENRES:
        if sanitized.lower() in valid_genre.lower() or valid_genre.lower() in sanitized.lower():
            return valid_genre
    
    return "Другое"


if __name__ == "__main__":
    # Тестирование валидаторов
    print("🧪 Тестирование валидаторов...")
    
    # Тест данных пользователя
    test_user_data = {
        'user_id': 12345,
        'group_id': -1001234567890,
        'username': 'test_user',
        'first_name': 'Тест',
        'music_genre': 'Рок'
    }
    
    is_valid, errors = UserDataValidator.validate_user_creation_data(test_user_data)
    print(f"👤 Валидация пользователя: {'✅' if is_valid else '❌'}")
    if errors:
        for error in errors:
            print(f"  - {error}")
    
    # Тест изменения кармы
    is_valid, error = KarmaValidator.validate_karma_operation(
        user_id=12345,
        karma_change=5,
        change_type='gratitude',
        current_karma=10,
        reason='Помощь новичку'
    )
    print(f"⭐ Валидация кармы: {'✅' if is_valid else '❌'}")
    if error:
        print(f"  - {error}")
    
    # Тест соотношения
    is_valid, ratio, error = UserDataValidator.validate_karma_ratio_format("15:3")
    print(f"📊 Валидация соотношения: {'✅' if is_valid else '❌'}")
    if error:
        print(f"  - {error}")
    elif ratio:
        print(f"  - Карма: {ratio[0]}, Ссылки: {ratio[1]}")
    
    print("✅ Тестирование валидаторов завершено")
