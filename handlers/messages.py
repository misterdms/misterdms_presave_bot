"""
📝 Messages Handler - Do Presave Reminder Bot v25+
Обработчик текстовых сообщений с интеграцией ИИ и распознавания благодарностей
"""

import re
from typing import Optional, List, Dict, Any
import telebot
from telebot.types import Message

from config import config
from database.manager import get_database_manager
from utils.security import (
    security_manager, user_rate_limit, whitelisted_thread_required,
    extract_user_id_from_message, extract_thread_id_from_message
)
from utils.logger import get_logger, telegram_logger, ai_logger, karma_logger
from utils.helpers import MessageFormatter, CommandParser, UserHelper, ConfigHelper

logger = get_logger(__name__)

class MessageHandler:
    """Обработчик текстовых сообщений"""
    
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot
        self.db = get_database_manager()
        
        # Кэш для обработки сообщений
        self.recent_messages = {}  # user_id: последнее сообщение
        
        # Регистрируем обработчики
        self._register_handlers()
        
        logger.info("📝 Message Handler инициализирован")
    
    def _register_handlers(self):
        """Регистрация обработчиков сообщений"""
        
        # Основной обработчик текстовых сообщений
        @self.bot.message_handler(content_types=['text'])
        def handle_text_message(message: Message):
            self.process_text_message(message)
        
        # Обработчик голосовых сообщений (для будущего)
        @self.bot.message_handler(content_types=['voice'])
        def handle_voice_message(message: Message):
            self.process_voice_message(message)
        
        # Обработчик изображений (для План 3 - скриншоты)
        @self.bot.message_handler(content_types=['photo'])
        def handle_photo_message(message: Message):
            self.process_photo_message(message)
        
        # Обработчик документов (для План 4 - backup файлы)
        @self.bot.message_handler(content_types=['document'])
        def handle_document_message(message: Message):
            self.process_document_message(message)
    
    def process_text_message(self, message: Message):
        """Основная обработка текстовых сообщений"""
        try:
            user_id = extract_user_id_from_message(message)
            thread_id = extract_thread_id_from_message(message)
            text = message.text or ""
            
            # Проверяем активен ли бот
            if not ConfigHelper.is_bot_enabled():
                # Бот деактивирован, игнорируем сообщения пользователей
                if not security_manager.is_admin(user_id):
                    return
            
            # Создаем или обновляем пользователя
            user = self.db.create_or_update_user(
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            
            # Обновляем статистику сообщений (если топик из whitelist)
            if thread_id and security_manager.is_whitelisted_thread(thread_id):
                self.db.update_message_stats(user.id, thread_id)
            
            # Логируем сообщение
            telegram_logger.user_action(
                user_id,
                "отправил сообщение",
                thread_id=thread_id,
                message_length=len(text),
                has_links=bool(CommandParser.extract_links_from_text(text))
            )
            
            # Проверяем различные типы сообщений
            
            # 1. Команды уже обрабатываются отдельными handlers
            if text.startswith('/'):
                return
            
            # 2. Проверяем упоминание бота (План 3 - ИИ)
            if self._is_bot_mentioned(text):
                self._handle_bot_mention(message, user)
                return
            
            # 3. Проверяем reply на сообщение бота (План 3 - ИИ)
            if self._is_reply_to_bot(message):
                self._handle_reply_to_bot(message, user)
                return
            
            # 4. Проверяем благодарности с reply (План 3 - авто-карма)
            if self._is_gratitude_message(message):
                self._handle_gratitude_message(message, user)
                return
            
            # 5. Проверяем ссылки (План 1 - основная функция)
            if self._has_links(text):
                # Переадресуем в handlers/links.py
                from handlers.links import LinkHandler
                link_handler = LinkHandler(self.bot)
                link_handler.process_message_with_links(message, user)
                return
            
            # 6. Обработка в контексте интерактивных форм (План 3)
            if config.ENABLE_PLAN_3_FEATURES:
                form_handled = self._handle_form_input(message, user)
                if form_handled:
                    return
            
            # 7. Обычное сообщение - просто логируем
            logger.debug(f"📝 Обычное сообщение от {user_id}: {text[:50]}...")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}")
    
    # ============================================
    # ПЛАН 3 - ИИ ИНТЕГРАЦИЯ
    # ============================================
    
    def _is_bot_mentioned(self, text: str) -> bool:
        """Проверка упоминания бота в сообщении"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return False
        
        bot_username = self.bot.get_me().username
        return CommandParser.is_mention_bot(text, bot_username)
    
    def _is_reply_to_bot(self, message: Message) -> bool:
        """Проверка что сообщение является ответом на сообщение бота"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return False
        
        if not message.reply_to_message:
            return False
        
        bot_id = self.bot.get_me().id
        return message.reply_to_message.from_user.id == bot_id
    
    @user_rate_limit('ai_requests')
    def _handle_bot_mention(self, message: Message, user):
        """Обработка упоминания бота (План 3 - ИИ)"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return
        
        try:
            user_id = user.telegram_id
            text = message.text or ""
            
            # Убираем упоминание бота из текста
            bot_username = self.bot.get_me().username
            clean_text = re.sub(rf'@{re.escape(bot_username)}', '', text).strip()
            
            if not clean_text:
                # Если только упоминание без текста
                response = f"{MessageFormatter.get_emoji('ai')} Привет! Чем могу помочь?\n\n"
                response += f"Можете задать вопрос или попросить совет по музыкальным темам."
                
                self.bot.reply_to(message, response)
                return
            
            # Логируем AI запрос
            ai_logger.ai_request(
                user_id=user_id,
                model="mention_detected",
                tokens_used=0,
                response_time_ms=0,
                success=True,
                request_type="mention"
            )
            
            # В Плане 3 здесь будет интеграция с реальным ИИ
            # Пока отправляем заглушку
            response = f"{MessageFormatter.get_emoji('ai')} **ИИ-помощник (в разработке)**\n\n"
            response += f"Получен запрос: _{clean_text}_\n\n"
            response += f"Функции ИИ будут доступны в Плане 3:\n"
            response += f"• Умные ответы на вопросы\n"
            response += f"• Поиск информации в интернете\n"
            response += f"• Советы по музыкальной индустрии\n"
            response += f"• Помощь с продвижением треков"
            
            self.bot.reply_to(message, response, parse_mode='Markdown')
            
            telegram_logger.user_action(
                user_id,
                "упомянул бота в сообщении",
                request_text=clean_text[:100]
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки упоминания бота: {e}")
    
    @user_rate_limit('ai_requests')
    def _handle_reply_to_bot(self, message: Message, user):
        """Обработка reply на сообщение бота (План 3 - ИИ)"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return
        
        try:
            user_id = user.telegram_id
            text = message.text or ""
            
            # Логируем AI запрос
            ai_logger.ai_request(
                user_id=user_id,
                model="reply_detected",
                tokens_used=0,
                response_time_ms=0,
                success=True,
                request_type="reply"
            )
            
            # В Плане 3 здесь будет контекстуальный ответ ИИ
            response = f"{MessageFormatter.get_emoji('ai')} **Контекстуальный ответ (в разработке)**\n\n"
            response += f"Ваш запрос: _{text}_\n\n"
            response += f"В готовой версии бот сможет:\n"
            response += f"• Продолжить диалог с учетом контекста\n"
            response += f"• Дать персональные рекомендации\n"
            response += f"• Помочь с решением музыкальных задач"
            
            self.bot.reply_to(message, response, parse_mode='Markdown')
            
            telegram_logger.user_action(
                user_id,
                "ответил на сообщение бота",
                reply_text=text[:100]
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки reply боту: {e}")
    
    # ============================================
    # ПЛАН 3 - АВТОМАТИЧЕСКОЕ РАСПОЗНАВАНИЕ БЛАГОДАРНОСТЕЙ
    # ============================================
    
    def _is_gratitude_message(self, message: Message) -> bool:
        """Проверка содержит ли сообщение благодарность с reply"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return False
        
        if not message.reply_to_message:
            return False
        
        # Проверяем что reply не на сообщение бота
        bot_id = self.bot.get_me().id
        if message.reply_to_message.from_user.id == bot_id:
            return False
        
        text = (message.text or "").lower()
        
        # Проверяем наличие слов благодарности
        gratitude_words = config.GRATITUDE_WORDS.get('ru', []) + config.GRATITUDE_WORDS.get('en', [])
        
        for word in gratitude_words:
            if word in text:
                return True
        
        return False
    
    def _handle_gratitude_message(self, message: Message, user):
        """Обработка сообщения с благодарностью (План 3 - авто-карма)"""
        if not config.ENABLE_PLAN_3_FEATURES or not config.ENABLE_PLAN_2_FEATURES:
            return
        
        try:
            from_user_id = user.telegram_id
            reply_message = message.reply_to_message
            to_user_id = reply_message.from_user.id
            text = (message.text or "").lower()
            
            # Проверяем что пользователь не благодарит сам себя
            if from_user_id == to_user_id:
                return
            
            # Ищем слово-триггер
            trigger_word = None
            gratitude_words = config.GRATITUDE_WORDS.get('ru', []) + config.GRATITUDE_WORDS.get('en', [])
            
            for word in gratitude_words:
                if word in text:
                    trigger_word = word
                    break
            
            if not trigger_word:
                return
            
            # Проверяем cooldown (не более 1 кармы от одного пользователя в час)
            cooldown_minutes = config.GRATITUDE_COOLDOWN_MINUTES
            recent_auto_karma = self.db.db.execute(
                """SELECT created_at FROM auto_karma_log 
                   WHERE from_user_id = %s AND to_user_id = %s 
                   AND created_at > NOW() - INTERVAL '%s minutes'""",
                (from_user_id, to_user_id, cooldown_minutes)
            ).fetchone()
            
            if recent_auto_karma:
                logger.debug(f"🙏 Cooldown активен для благодарности {from_user_id} -> {to_user_id}")
                return
            
            # Проверяем минимальную длину сообщения
            if len(text) < config.MIN_MESSAGE_LENGTH_FOR_KARMA:
                return
            
            # Получаем или создаем пользователя получателя
            to_user = self.db.create_or_update_user(
                telegram_id=to_user_id,
                username=reply_message.from_user.username,
                first_name=reply_message.from_user.first_name,
                last_name=reply_message.from_user.last_name
            )
            
            # Начисляем карму автоматически
            karma_record = self.db.change_karma(
                user_id=to_user.id,
                change=1,
                admin_id=None,  # Автоматическое начисление
                reason=f"Автоматическое начисление за благодарность: '{trigger_word}'",
                is_automatic=True
            )
            
            # Логируем автоматическое начисление
            self.db.log_auto_karma(
                from_user_id=user.id,
                to_user_id=to_user.id,
                trigger_word=trigger_word,
                message_text=text[:500],
                karma_added=1
            )
            
            # Отправляем уведомление
            to_user_display = UserHelper.get_user_display_name(to_user)
            notification = f"{MessageFormatter.get_emoji('thank_you')} {to_user_display} твоя карма повышена на +1, продолжай быть примером для остальных! {MessageFormatter.get_emoji('success')}"
            
            self.bot.reply_to(reply_message, notification)
            
            # Логируем событие
            karma_logger.auto_karma_detected(
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                trigger_word=trigger_word,
                message_text=text[:100]
            )
            
            telegram_logger.user_action(
                from_user_id,
                f"автоматически начислил карму пользователю {to_user_id}",
                trigger_word=trigger_word,
                karma_added=1
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки благодарности: {e}")
    
    # ============================================
    # ПЛАН 3 - ИНТЕРАКТИВНЫЕ ФОРМЫ
    # ============================================
    
    def _handle_form_input(self, message: Message, user) -> bool:
        """Обработка ввода в интерактивных формах (План 3)"""
        if not config.ENABLE_PLAN_3_FEATURES:
            return False
        
        try:
            # Получаем сессию формы пользователя
            form_session = self.db.db.query(FormSession)\
                .filter(FormSession.user_id == user.id)\
                .first()
            
            if not form_session or form_session.current_state == FormState.IDLE:
                return False
            
            # В Плане 3 здесь будет полная реализация форм
            # Пока просто логируем
            logger.debug(f"📝 Ввод в форме от {user.telegram_id}: состояние {form_session.current_state.value}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки ввода формы: {e}")
            return False
    
    # ============================================
    # ОБРАБОТКА ДРУГИХ ТИПОВ СООБЩЕНИЙ
    # ============================================
    
    def process_voice_message(self, message: Message):
        """Обработка голосовых сообщений (будущее расширение)"""
        try:
            user_id = extract_user_id_from_message(message)
            
            if not security_manager.is_admin(user_id):
                # Голосовые сообщения пока только для админов
                return
            
            response = f"{MessageFormatter.get_emoji('ai')} **Голосовые сообщения**\n\n"
            response += f"Функция распознавания речи будет добавлена в будущих планах."
            
            self.bot.reply_to(message, response, parse_mode='Markdown')
            
            telegram_logger.user_action(user_id, "отправил голосовое сообщение")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки голосового сообщения: {e}")
    
    def process_photo_message(self, message: Message):
        """Обработка изображений (План 3 - скриншоты пресейвов)"""
        try:
            user_id = extract_user_id_from_message(message)
            
            # Создаем пользователя
            user = self.db.create_or_update_user(
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            
            if config.ENABLE_PLAN_3_FEATURES:
                # В Плане 3 здесь будет обработка скриншотов для заявок
                response = f"{MessageFormatter.get_emoji('screenshot')} **Скриншот получен**\n\n"
                response += f"Система обработки скриншотов будет доступна в Плане 3.\n"
                response += f"Планируется:\n"
                response += f"• Автоматическое добавление к заявкам\n"
                response += f"• Распознавание текста на изображениях\n"
                response += f"• Валидация скриншотов пресейвов"
            else:
                response = f"{MessageFormatter.get_emoji('loading')} **Обработка изображений**\n\n"
                response += f"Функция будет доступна в Плане 3."
            
            self.bot.reply_to(message, response, parse_mode='Markdown')
            
            telegram_logger.user_action(user_id, "отправил изображение")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки изображения: {e}")
    
    def process_document_message(self, message: Message):
        """Обработка документов (План 4 - backup файлы)"""
        try:
            user_id = extract_user_id_from_message(message)
            
            # Проверяем права админа для backup файлов
            if not security_manager.is_admin(user_id):
                return
            
            document = message.document
            filename = document.file_name or "unknown"
            
            # Проверяем это backup файл
            if filename.startswith('presave_bot_backup_') and filename.endswith('.zip'):
                if config.ENABLE_PLAN_4_FEATURES:
                    # В Плане 4 здесь будет автоматическое восстановление
                    response = f"{MessageFormatter.get_emoji('backup')} **Backup файл обнаружен**\n\n"
                    response += f"**Файл:** `{filename}`\n"
                    response += f"**Размер:** {MessageFormatter.format_file_size(document.file_size)}\n\n"
                    response += f"Система автоматического восстановления будет доступна в Плане 4."
                else:
                    response = f"{MessageFormatter.get_emoji('loading')} **Backup система в разработке**"
            else:
                response = f"{MessageFormatter.get_emoji('info')} **Документ получен**\n\n"
                response += f"**Файл:** `{filename}`\n"
                response += f"**Размер:** {MessageFormatter.format_file_size(document.file_size)}"
            
            self.bot.reply_to(message, response, parse_mode='Markdown')
            
            telegram_logger.admin_action(
                user_id, 
                "отправил документ",
                filename=filename,
                file_size=document.file_size
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки документа: {e}")
    
    # ============================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================
    
    def _has_links(self, text: str) -> bool:
        """Проверка содержит ли текст ссылки"""
        links = CommandParser.extract_links_from_text(text)
        return len(links) > 0
    
    def _is_private_chat(self, message: Message) -> bool:
        """Проверка что это личное сообщение"""
        return message.chat.type == 'private'
    
    def _should_ignore_message(self, message: Message) -> bool:
        """Проверка нужно ли игнорировать сообщение"""
        # Игнорируем сообщения от ботов
        if message.from_user.is_bot:
            return True
        
        # Игнорируем системные сообщения
        if message.content_type not in ['text', 'voice', 'photo', 'document']:
            return True
        
        return False
    
    def get_message_context(self, message: Message) -> Dict[str, Any]:
        """Получение контекста сообщения для ИИ"""
        return {
            'user_id': message.from_user.id,
            'username': message.from_user.username,
            'chat_type': message.chat.type,
            'thread_id': extract_thread_id_from_message(message),
            'is_reply': bool(message.reply_to_message),
            'message_length': len(message.text or ""),
            'timestamp': message.date
        }

# ============================================
# ГЛОБАЛЬНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ
# ============================================

def init_message_handlers(bot: telebot.TeleBot) -> MessageHandler:
    """Инициализация обработчиков сообщений"""
    return MessageHandler(bot)

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = ['MessageHandler', 'init_message_handlers']

if __name__ == "__main__":
    print("🧪 Тестирование Message Handlers...")
    print("✅ Модуль messages.py готов к интеграции")
