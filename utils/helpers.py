"""
Вспомогательные функции Do Presave Reminder Bot v25+
Общие утилиты для всех планов развития
"""

import html
import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import telebot
from telebot.types import Message, User

from utils.logger import get_logger

logger = get_logger(__name__)

# ============================================
# ФОРМАТИРОВАНИЕ ПОЛЬЗОВАТЕЛЕЙ
# ============================================

def format_user_mention(user_id: int, username: str = None, first_name: str = None, 
                        last_name: str = None, use_html: bool = True) -> str:
    """Форматирование упоминания пользователя"""
    try:
        if username:
            return f"@{username}"
        
        display_name = first_name or "Пользователь"
        if last_name:
            display_name += f" {last_name}"
        
        # Экранируем HTML
        if use_html:
            display_name = html.escape(display_name)
            return f"<a href='tg://user?id={user_id}'>{display_name}</a>"
        else:
            return display_name
            
    except Exception as e:
        logger.error(f"❌ Ошибка format_user_mention: {e}")
        return f"ID{user_id}"

def get_user_display_name(user: Union[User, Dict], include_username: bool = True) -> str:
    """Получение отображаемого имени пользователя"""
    try:
        if isinstance(user, dict):
            username = user.get('username')
            first_name = user.get('first_name')
            last_name = user.get('last_name')
        else:
            username = getattr(user, 'username', None)
            first_name = getattr(user, 'first_name', None)
            last_name = getattr(user, 'last_name', None)
        
        if include_username and username:
            return f"@{username}"
        
        name_parts = []
        if first_name:
            name_parts.append(first_name)
        if last_name:
            name_parts.append(last_name)
        
        return " ".join(name_parts) if name_parts else "Безымянный пользователь"
        
    except Exception as e:
        logger.error(f"❌ Ошибка get_user_display_name: {e}")
        return "Неизвестный пользователь"

def sanitize_username(username: str) -> str:
    """Очистка username от лишних символов"""
    if not username:
        return ""
    
    # Убираем @ в начале
    username = username.lstrip('@')
    
    # Удаляем недопустимые символы
    username = re.sub(r'[^a-zA-Z0-9_]', '', username)
    
    return username[:32]  # Максимальная длина username в Telegram

# ============================================
# ФОРМАТИРОВАНИЕ ТЕКСТА И СООБЩЕНИЙ
# ============================================

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Обрезка текста с добавлением суффикса"""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def escape_markdown(text: str) -> str:
    """Экранирование символов для Markdown"""
    if not text:
        return ""
    
    # Символы которые нужно экранировать в Markdown
    escape_chars = ['*', '_', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def escape_html(text: str) -> str:
    """Экранирование HTML символов"""
    if not text:
        return ""
    
    return html.escape(text)

def clean_text(text: str, max_length: int = 1000) -> str:
    """Очистка и нормализация текста"""
    if not text:
        return ""
    
    # Убираем лишние пробелы и переносы
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Ограничиваем длину
    text = text[:max_length]
    
    # Экранируем HTML
    text = html.escape(text)
    
    return text

def format_file_size(size_bytes: int) -> str:
    """Форматирование размера файла"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    i = 0
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

# ============================================
# РАБОТА СО ВРЕМЕНЕМ И ДАТАМИ
# ============================================

def format_datetime(dt: datetime, format_type: str = 'full') -> str:
    """Форматирование даты и времени"""
    if not dt:
        return "Неизвестно"
    
    try:
        if format_type == 'date':
            return dt.strftime("%d.%m.%Y")
        elif format_type == 'time':
            return dt.strftime("%H:%M")
        elif format_type == 'short':
            return dt.strftime("%d.%m %H:%M")
        elif format_type == 'full':
            return dt.strftime("%d.%m.%Y %H:%M:%S")
        elif format_type == 'iso':
            return dt.isoformat()
        else:
            return dt.strftime("%d.%m.%Y %H:%M")
            
    except Exception as e:
        logger.error(f"❌ Ошибка format_datetime: {e}")
        return "Ошибка форматирования"

def time_ago(dt: datetime) -> str:
    """Человекочитаемое время назад"""
    if not dt:
        return "неизвестно когда"
    
    try:
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            if diff.days == 1:
                return "вчера"
            elif diff.days < 7:
                return f"{diff.days} дн. назад"
            elif diff.days < 30:
                weeks = diff.days // 7
                return f"{weeks} нед. назад"
            else:
                months = diff.days // 30
                return f"{months} мес. назад"
        
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours} ч. назад"
        
        minutes = diff.seconds // 60
        if minutes > 0:
            return f"{minutes} мин. назад"
        
        return "только что"
        
    except Exception as e:
        logger.error(f"❌ Ошибка time_ago: {e}")
        return "неизвестно"

def parse_datetime(date_str: str, format_str: str = "%Y-%m-%d") -> Optional[datetime]:
    """Парсинг строки в datetime"""
    try:
        return datetime.strptime(date_str, format_str)
    except (ValueError, TypeError):
        return None

# ============================================
# ПРОГРЕСС-БАРЫ И ВИЗУАЛИЗАЦИЯ
# ============================================

def create_progress_bar(current: int, total: int, length: int = 10, 
                       filled_char: str = "█", empty_char: str = "░") -> str:
    """Создание текстового прогресс-бара"""
    try:
        if total == 0:
            return empty_char * length
        
        filled_length = int(length * current / total)
        filled_length = max(0, min(filled_length, length))
        
        bar = filled_char * filled_length + empty_char * (length - filled_length)
        percentage = int(100 * current / total)
        
        return f"{bar} {percentage}%"
        
    except Exception as e:
        logger.error(f"❌ Ошибка create_progress_bar: {e}")
        return "❌ Ошибка"

def create_karma_progress_bar(current: int, next_threshold: int, length: int = 10) -> str:
    """Создание прогресс-бара для кармы"""
    try:
        if next_threshold <= current:
            return "█" * length + " MAX"
        
        progress = create_progress_bar(current, next_threshold, length)
        return f"{progress} ({current}/{next_threshold})"
        
    except Exception as e:
        logger.error(f"❌ Ошибка create_karma_progress_bar: {e}")
        return "❌ Ошибка"

# ============================================
# ВАЛИДАЦИЯ И ПРОВЕРКИ
# ============================================

def is_valid_url(url: str) -> bool:
    """Проверка валидности URL"""
    if not url:
        return False
    
    # Простая проверка на паттерн URL
    url_pattern = re.compile(
        r'^https?://(?:[-\w.])+(?::[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?$'
    )
    
    return bool(url_pattern.match(url))

def validate_user_input(text: str, min_length: int = 1, max_length: int = 1000) -> Dict[str, Any]:
    """Валидация пользовательского ввода"""
    result = {
        'valid': False,
        'error': None,
        'cleaned_text': ''
    }
    
    if not text:
        result['error'] = "Текст не может быть пустым"
        return result
    
    # Очищаем текст
    cleaned = clean_text(text, max_length)
    
    if len(cleaned) < min_length:
        result['error'] = f"Текст слишком короткий (минимум {min_length} символов)"
        return result
    
    if len(cleaned) > max_length:
        result['error'] = f"Текст слишком длинный (максимум {max_length} символов)"
        return result
    
    result['valid'] = True
    result['cleaned_text'] = cleaned
    return result

def extract_numbers(text: str) -> List[int]:
    """Извлечение чисел из текста"""
    try:
        numbers = re.findall(r'-?\d+', text)
        return [int(num) for num in numbers]
    except Exception as e:
        logger.error(f"❌ Ошибка extract_numbers: {e}")
        return []

# ============================================
# РАБОТА СО СПИСКАМИ И ДАННЫМИ
# ============================================

def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Разбиение списка на части"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def safe_get(dictionary: Dict, key: str, default=None):
    """Безопасное получение значения из словаря"""
    try:
        return dictionary.get(key, default)
    except (AttributeError, TypeError):
        return default

def merge_dicts(*dicts: Dict) -> Dict:
    """Объединение словарей"""
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result

# ============================================
# ГЕНЕРАЦИЯ ID И ХЕШИРОВАНИЕ
# ============================================

def generate_unique_id(prefix: str = "", length: int = 8) -> str:
    """Генерация уникального ID"""
    try:
        import uuid
        unique_part = str(uuid.uuid4()).replace('-', '')[:length]
        return f"{prefix}{unique_part}" if prefix else unique_part
    except Exception as e:
        logger.error(f"❌ Ошибка generate_unique_id: {e}")
        return f"{prefix}error"

def hash_text(text: str, algorithm: str = 'md5') -> str:
    """Хеширование текста"""
    try:
        if algorithm == 'md5':
            return hashlib.md5(text.encode()).hexdigest()
        elif algorithm == 'sha256':
            return hashlib.sha256(text.encode()).hexdigest()
        else:
            return hashlib.md5(text.encode()).hexdigest()
    except Exception as e:
        logger.error(f"❌ Ошибка hash_text: {e}")
        return "error"

# ============================================
# ПЛАН 2: УТИЛИТЫ ДЛЯ КАРМЫ (ЗАГЛУШКИ)
# ============================================

# def format_karma_change(old_karma: int, new_karma: int) -> str:
#     """Форматирование изменения кармы"""
#     change = new_karma - old_karma
#     
#     if change > 0:
#         return f"📈 +{change} ({old_karma} → {new_karma})"
#     elif change < 0:
#         return f"📉 {change} ({old_karma} → {new_karma})"
#     else:
#         return f"➡️ {old_karma} (без изменений)"

# def get_rank_emoji(rank: str) -> str:
#     """Получение эмодзи для звания"""
#     rank_emojis = {
#         'Новенький': '🥉',
#         'Надежда сообщества': '🥈', 
#         'Мега-человечище': '🥇',
#         'Амбассадорище': '💎'
#     }
#     
#     return rank_emojis.get(rank, '❓')

# def calculate_karma_progress(current_karma: int, rank_thresholds: Dict[int, str]) -> Dict[str, Any]:
#     """Расчет прогресса кармы"""
#     # Находим текущее и следующее звание
#     current_rank = "🥉 Новенький"
#     next_threshold = None
#     
#     sorted_thresholds = sorted(rank_thresholds.keys())
#     
#     for threshold in sorted_thresholds:
#         if current_karma >= threshold:
#             current_rank = rank_thresholds[threshold]
#         else:
#             next_threshold = threshold
#             break
#     
#     return {
#         'current_rank': current_rank,
#         'current_karma': current_karma,
#         'next_threshold': next_threshold,
#         'progress_bar': create_karma_progress_bar(current_karma, next_threshold or current_karma)
#     }

# ============================================
# ПЛАН 3: УТИЛИТЫ ДЛЯ ИИ И ФОРМ (ЗАГЛУШКИ)
# ============================================

# def format_ai_response(text: str, max_length: int = 4000) -> str:
#     """Форматирование ответа ИИ для Telegram"""
#     if not text:
#         return "🤖 Извините, не смог сгенерировать ответ."
#     
#     # Обрезаем если слишком длинный
#     if len(text) > max_length:
#         text = text[:max_length - 20] + "\n\n...✂️ (обрезано)"
#     
#     # Добавляем эмодзи ИИ если его нет
#     if not text.startswith('🤖'):
#         text = f"🤖 {text}"
#     
#     return text

# def extract_form_data(message: Message) -> Dict[str, Any]:
#     """Извлечение данных из сообщения для форм"""
#     data = {
#         'text': message.text or '',
#         'has_photo': bool(message.photo),
#         'has_document': bool(message.document),
#         'user_id': message.from_user.id,
#         'message_id': message.message_id,
#         'timestamp': datetime.now()
#     }
#     
#     if message.photo:
#         photo = message.photo[-1]  # Максимальное разрешение
#         data['photo_file_id'] = photo.file_id
#         data['photo_size'] = photo.file_size
#     
#     if message.document:
#         data['document_file_id'] = message.document.file_id
#         data['document_name'] = message.document.file_name
#         data['document_size'] = message.document.file_size
#     
#     return data

# def validate_screenshot(file_info: Dict) -> Dict[str, Any]:
#     """Валидация скриншота"""
#     result = {
#         'valid': False,
#         'error': None
#     }
#     
#     # Проверка размера
#     max_size_mb = 10  # Из конфигурации
#     if file_info.get('file_size', 0) > max_size_mb * 1024 * 1024:
#         result['error'] = f"Файл слишком большой (максимум {max_size_mb}MB)"
#         return result
#     
#     # Проверка типа файла
#     file_name = file_info.get('file_name', '').lower()
#     allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp']
#     
#     if not any(file_name.endswith(ext) for ext in allowed_extensions):
#         result['error'] = "Неподдерживаемый формат файла (только JPG, PNG, WebP)"
#         return result
#     
#     result['valid'] = True
#     return result

# ============================================
# ПЛАН 4: УТИЛИТЫ ДЛЯ BACKUP (ЗАГЛУШКИ)
# ============================================

# def format_backup_info(backup_data: Dict) -> str:
#     """Форматирование информации о backup"""
#     created_date = backup_data.get('created_date')
#     file_size = backup_data.get('file_size_mb', 0)
#     tables_count = backup_data.get('tables_count', 0)
#     records_count = backup_data.get('records_count', 0)
#     
#     return f"""
# 💾 <b>Информация о backup</b>
# 
# 📅 <b>Создан:</b> {format_datetime(created_date)}
# 📊 <b>Размер:</b> {file_size:.1f} MB
# 🗃️ <b>Таблиц:</b> {tables_count}
# 📝 <b>Записей:</b> {records_count:,}
# """

# def calculate_database_age(created_date: str) -> Dict[str, Any]:
#     """Расчет возраста базы данных"""
#     try:
#         created = datetime.strptime(created_date, '%Y-%m-%d')
#         now = datetime.now()
#         age_days = (now - created).days
#         
#         days_until_expiry = max(0, 30 - age_days)
#         
#         if days_until_expiry == 0:
#             status = "🚨 ИСТЕКЛА"
#         elif days_until_expiry <= 5:
#             status = "🚨 КРИТИЧНО"
#         elif days_until_expiry <= 10:
#             status = "⚠️ ВНИМАНИЕ"
#         else:
#             status = "✅ В НОРМЕ"
#         
#         return {
#             'age_days': age_days,
#             'days_until_expiry': days_until_expiry,
#             'status': status,
#             'status_emoji': status.split()[0]
#         }
#         
#     except Exception as e:
#         logger.error(f"❌ Ошибка calculate_database_age: {e}")
#         return {
#             'age_days': 0,
#             'days_until_expiry': 30,
#             'status': "❓ НЕИЗВЕСТНО",
#             'status_emoji': "❓"
#         }

# ============================================
# ОБЩИЕ УТИЛИТЫ
# ============================================

def log_function_call(func_name: str, args: tuple = (), kwargs: dict = None):
    """Логирование вызова функции"""
    try:
        args_str = ", ".join(str(arg) for arg in args)
        kwargs_str = ", ".join(f"{k}={v}" for k, v in (kwargs or {}).items())
        
        params = ", ".join(filter(None, [args_str, kwargs_str]))
        logger.debug(f"🔧 Вызов функции {func_name}({params})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка log_function_call: {e}")

def safe_int(value: Any, default: int = 0) -> int:
    """Безопасное преобразование в int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """Безопасное преобразование в float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def format_number(number: Union[int, float], precision: int = 1) -> str:
    """Форматирование числа с разделителями тысяч"""
    try:
        if isinstance(number, float):
            return f"{number:,.{precision}f}"
        else:
            return f"{number:,}"
    except Exception as e:
        logger.error(f"❌ Ошибка format_number: {e}")
        return str(number)


if __name__ == "__main__":
    """Тестирование вспомогательных функций"""
    
    print("🧪 Тестирование utils/helpers.py...")
    
    # Тестирование форматирования пользователей
    print("\n👤 Тестирование форматирования пользователей:")
    print(f"С username: {format_user_mention(12345, 'testuser')}")
    print(f"Без username: {format_user_mention(12345, None, 'Тест', 'Пользователь')}")
    
    # Тестирование работы с текстом
    print("\n📝 Тестирование работы с текстом:")
    long_text = "Это очень длинный текст" * 10
    print(f"Обрезка: {truncate_text(long_text, 50)}")
    print(f"Очистка: {clean_text('  Текст   с   пробелами  ')}")
    
    # Тестирование времени
    print("\n🕐 Тестирование времени:")
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    print(f"Сейчас: {format_datetime(now, 'short')}")
    print(f"Вчера было: {time_ago(yesterday)}")
    
    # Тестирование прогресс-баров
    print("\n📊 Тестирование прогресс-баров:")
    print(f"50%: {create_progress_bar(50, 100)}")
    print(f"25%: {create_progress_bar(25, 100)}")
    print(f"Карма: {create_karma_progress_bar(15, 31)}")
    
    # Тестирование валидации
    print("\n✅ Тестирование валидации:")
    print(f"Валидный URL: {is_valid_url('https://example.com')}")
    print(f"Невалидный URL: {is_valid_url('not-a-url')}")
    
    validation = validate_user_input("Тестовый текст", 5, 100)
    print(f"Валидация текста: {validation}")
    
    # Тестирование утилит
    print("\n🔧 Тестирование утилит:")
    print(f"Размер файла: {format_file_size(1536000)}")
    print(f"Числа из текста: {extract_numbers('У меня 5 яблок и 10 груш')}")
    print(f"Уникальный ID: {generate_unique_id('test_', 6)}")
    
    print("\n✅ Тестирование helpers завершено!")