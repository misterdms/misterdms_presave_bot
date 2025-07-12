"""
Обработчик сообщений Do Presave Reminder Bot v25+
Обработка всех текстовых сообщений с интеграцией ссылок

ПЛАН 1: Базовая обработка сообщений (АКТИВНАЯ)
ПЛАН 2: Интеграция с кармой (ЗАГЛУШКИ)
ПЛАН 3: Интеграция с ИИ и формами (ЗАГЛУШКИ)
ПЛАН 4: Логирование для backup (ЗАГЛУШКИ)
"""

import re
from typing import List, Optional
import telebot
from telebot.types import Message

from database.manager import DatabaseManager
from utils.security import SecurityManager, whitelist_required
from utils.logger import get_logger, log_user_action
from handlers.links import LinkHandler

logger = get_logger(__name__)

class MessageHandler:
    """Обработчик всех текстовых сообщений"""
    
    def __init__(self, bot: telebot.TeleBot, db_manager: DatabaseManager, security_manager: SecurityManager):
        """Инициализация обработчика сообщений"""
        self.bot = bot
        self.db = db_manager
        self.security = security_manager
        
        # Интеграция с обработчиком ссылок
        self.link_handler = None  # Будет инициализирован в main.py
        
        # Паттерны для обработки
        self.url_pattern = re.compile(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        )
        
        # ПЛАН 3: Паттерны для ИИ (ЗАГЛУШКИ)
        # self.mention_pattern = re.compile(r'@\w+')
        # self.gratitude_patterns = self._compile_gratitude_patterns()
        
        logger.info("MessageHandler инициализирован")
    
    def set_link_handler(self, link_handler):
        """Установка обработчика ссылок (вызывается из main.py)"""
        self.link_handler = link_handler
        logger.info("LinkHandler интегрирован в MessageHandler")
    
    def register_handlers(self):
        """Регистрация обработчиков сообщений"""
        
        # Обработчик всех текстовых сообщений (кроме команд)
        @self.bot.message_handler(content_types=['text'])
        def handle_text_message(message: Message):
            """Обработка текстовых сообщений"""
            try:
                self._process_text_message(message)
            except Exception as e:
                logger.error(f"❌ Критическая ошибка message handler: {e}")
        
        # ПЛАН 3: Обработчик файлов для форм (ЗАГЛУШКИ)
        # @self.bot.message_handler(content_types=['photo', 'document'])
        # def handle_file_message(message: Message):
        #     """Обработка файлов (скриншоты для заявок)"""
        #     try:
        #         self._process_file_message(message)
        #     except Exception as e:
        #         logger.error(f"❌ Ошибка обработки файла: {e}")
        
        logger.info("Message handlers зарегистрированы")
    
    def _process_text_message(self, message: Message):
        """Основная обработка текстового сообщения"""
        try:
            # Получаем информацию о сообщении
            user_id = message.from_user.id
            chat_type = message.chat.type
            thread_id = getattr(message, 'message_thread_id', None)
            text = message.text or ""
            
            # Пропускаем команды (они обрабатываются отдельно)
            if text.startswith('/'):
                return
            
            # Регистрируем пользователя
            self.db.get_or_create_user(
                user_id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            
            # Логируем активность
            log_user_action(logger, user_id, f"отправил сообщение в {chat_type}")
            
            # Обработка в зависимости от типа чата
            if chat_type == 'private':
                self._handle_private_message(message)
            elif chat_type in ['group', 'supergroup']:
                self._handle_group_message(message)
            else:
                logger.info(f"Неподдерживаемый тип чата: {chat_type}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка _process_text_message: {e}")
    
    def _handle_private_message(self, message: Message):
        """Обработка сообщения в личке"""
        try:
            user_id = message.from_user.id
            text = message.text
            
            # ПЛАН 3: Проверка состояния интерактивных форм (ЗАГЛУШКА)
            # if self._is_user_in_form(user_id):
            #     self._handle_form_input(message)
            #     return
            
            # ПЛАН 3: Проверка на аналитические запросы админов (ЗАГЛУШКА)
            # if self.security.is_admin(user_id) and self._is_analytics_request(text):
            #     self._handle_analytics_request(message)
            #     return
            
            # ПЛАН 3: ИИ обработка в личке (ЗАГЛУШКА)
            # if self.db.get_setting('ai_enabled', False):
            #     self._handle_ai_conversation(message)
            #     return
            
            # Стандартная обработка - направляем к меню или командам
            if self.security.is_admin(user_id):
                self.bot.send_message(
                    message.chat.id,
                    "👋 Привет! Используйте /menu для доступа к панели управления или /help для списка команд."
                )
            else:
                self.bot.send_message(
                    message.chat.id,
                    "👋 Привет! Я бот для управления пресейвами в музыкальном сообществе.\n\n"
                    "Используйте /help для получения информации о доступных функциях."
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка _handle_private_message: {e}")
    
    @whitelist_required
    def _handle_group_message(self, message: Message):
        """Обработка сообщения в группе"""
        try:
            user_id = message.from_user.id
            text = message.text
            thread_id = getattr(message, 'message_thread_id', None)
            
            # Проверяем включен ли бот
            if not self.db.get_setting('bot_enabled', True):
                return  # Бот отключен, игнорируем сообщения
            
            # ПЛАН 3: Проверка на упоминание бота (ЗАГЛУШКА)
            # if self._is_bot_mentioned(text):
            #     self._handle_bot_mention(message)
            #     return
            
            # ПЛАН 3: Проверка на reply к боту (ЗАГЛУШКА)  
            # if message.reply_to_message and message.reply_to_message.from_user.is_bot:
            #     self._handle_reply_to_bot(message)
            #     return
            
            # ПЛАН 3: Обработка благодарностей (ЗАГЛУШКА)
            # if self._contains_gratitude(text) and message.reply_to_message:
            #     self._handle_gratitude_message(message)
            
            # ПЛАН 1: Обработка ссылок (АКТИВНАЯ)
            if self._contains_urls(text):
                self._handle_message_with_links(message)
                return
            
            # ПЛАН 1: Обновление статистики сообщений
            self._update_message_stats(user_id, thread_id)
            
        except Exception as e:
            logger.error(f"❌ Ошибка _handle_group_message: {e}")
    
    def _contains_urls(self, text: str) -> bool:
        """Проверка содержит ли текст URLs"""
        return bool(self.url_pattern.search(text))
    
    def _handle_message_with_links(self, message: Message):
        """Обработка сообщения со ссылками"""
        try:
            if self.link_handler:
                # Делегируем обработку ссылок в LinkHandler
                self.link_handler.handle_link_message(message)
            else:
                logger.warning("LinkHandler не инициализирован!")
                
        except Exception as e:
            logger.error(f"❌ Ошибка _handle_message_with_links: {e}")
    
    def _update_message_stats(self, user_id: int, thread_id: int):
        """Обновление статистики сообщений пользователя"""
        try:
            # ПЛАН 3: Полная статистика сообщений (ЗАГЛУШКА)
            # В ПЛАНЕ 1 просто логируем активность
            log_user_action(logger, user_id, f"активен в топике {thread_id}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка _update_message_stats: {e}")
    
    # ============================================
    # ПЛАН 3: ИИ И ФОРМЫ (ЗАГЛУШКИ)
    # ============================================
    
    # def _is_user_in_form(self, user_id: int) -> bool:
    #     """Проверка находится ли пользователь в интерактивной форме"""
    #     try:
    #         # Проверяем состояние формы в БД или кэше
    #         from services.forms import FormManager
    #         form_manager = FormManager(self.db, None)
    #         return form_manager.is_user_in_form(user_id)
    #     except:
    #         return False
    
    # def _handle_form_input(self, message: Message):
    #     """Обработка ввода в интерактивной форме"""
    #     try:
    #         user_id = message.from_user.id
    #         
    #         from services.forms import FormManager
    #         form_manager = FormManager(self.db, None)
    #         
    #         # Обрабатываем ввод в зависимости от текущего состояния формы
    #         result = form_manager.process_form_input(user_id, message)
    #         
    #         if result['status'] == 'completed':
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 "✅ <b>Форма заполнена!</b>\n\nДанные отправлены на обработку.",
    #                 parse_mode='HTML'
    #             )
    #         elif result['status'] == 'error':
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 f"❌ Ошибка: {result['message']}",
    #                 parse_mode='HTML'
    #             )
    #         elif result['status'] == 'next_step':
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 result['message'],
    #                 parse_mode='HTML',
    #                 reply_markup=result.get('keyboard')
    #             )
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _handle_form_input: {e}")
    #         self.bot.send_message(
    #             message.chat.id,
    #             "❌ Ошибка обработки формы. Попробуйте начать заново."
    #         )
    
    # def _is_analytics_request(self, text: str) -> bool:
    #     """Проверка является ли сообщение аналитическим запросом"""
    #     analytics_keywords = [
    #         '@', 'статистика', 'ссылки', 'карма', 'пользователь'
    #     ]
    #     
    #     text_lower = text.lower()
    #     return any(keyword in text_lower for keyword in analytics_keywords)
    
    # def _handle_analytics_request(self, message: Message):
    #     """Обработка аналитического запроса"""
    #     try:
    #         text = message.text.lower()
    #         
    #         # Ищем username в сообщении
    #         username_match = re.search(r'@(\w+)', message.text)
    #         if not username_match:
    #             self.bot.send_message(
    #                 message.chat.id,
    #                 "❌ Не найден username в запросе. Используйте формат: @username"
    #             )
    #             return
    #         
    #         username = username_match.group(1)
    #         
    #         # Определяем тип аналитики
    #         if 'ссылк' in text:
    #             self._send_user_links_analytics(message, username)
    #         elif 'карм' in text:
    #             self._send_user_karma_analytics(message, username)
    #         elif 'соотношен' in text:
    #             self._send_user_ratio_analytics(message, username)
    #         else:
    #             self._send_full_user_analytics(message, username)
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _handle_analytics_request: {e}")
    #         self.bot.send_message(
    #             message.chat.id,
    #             "❌ Ошибка обработки аналитического запроса"
    #         )
    
    # def _is_bot_mentioned(self, text: str) -> bool:
    #     """Проверка упоминания бота в сообщении"""
    #     bot_username = self.bot.get_me().username
    #     
    #     mention_patterns = [
    #         f'@{bot_username}',
    #         bot_username.lower(),
    #         'бот',
    #         'bot'
    #     ]
    #     
    #     text_lower = text.lower()
    #     return any(pattern in text_lower for pattern in mention_patterns)
    
    # def _handle_bot_mention(self, message: Message):
    #     """Обработка упоминания бота"""
    #     try:
    #         if not self.db.get_setting('ai_enabled', False):
    #             # ИИ отключен, отправляем стандартный ответ
    #             self.bot.reply_to(
    #                 message,
    #                 "👋 Привет! Я помогаю с пресейвами в сообществе.\n"
    #                 "Используйте /help для списка команд."
    #             )
    #             return
    #         
    #         # Передаем в ИИ обработчик
    #         self._handle_ai_conversation(message)
    #         
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _handle_bot_mention: {e}")
    
    # def _handle_reply_to_bot(self, message: Message):
    #     """Обработка reply на сообщение бота"""
    #     try:
    #         if self.db.get_setting('ai_enabled', False):
    #             self._handle_ai_conversation(message)
    #         else:
    #             # Стандартная обработка
    #             self.bot.reply_to(
    #                 message,
    #                 "Спасибо за ответ! Используйте /help для списка команд."
    #             )
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _handle_reply_to_bot: {e}")
    
    # def _handle_ai_conversation(self, message: Message):
    #     """Обработка разговора с ИИ"""
    #     try:
    #         user_id = message.from_user.id
    #         text = message.text
    #         
    #         # Удаляем упоминание бота из текста
    #         bot_username = self.bot.get_me().username
    #         clean_text = re.sub(f'@{bot_username}', '', text).strip()
    #         
    #         if not clean_text:
    #             self.bot.reply_to(
    #                 message,
    #                 "🤔 Что именно вас интересует? Задайте конкретный вопрос!"
    #             )
    #             return
    #         
    #         # Отправляем в ИИ
    #         from services.ai import AIManager
    #         ai_manager = AIManager(None)  # Передаем config
    #         
    #         # Генерируем ответ
    #         response = ai_manager.generate_response(
    #             prompt=clean_text,
    #             user_id=user_id,
    #             context_type='mention' if self._is_bot_mentioned(text) else 'reply'
    #         )
    #         
    #         if response:
    #             self.bot.reply_to(message, response, parse_mode='HTML')
    #         else:
    #             self.bot.reply_to(
    #                 message,
    #                 "😅 Извините, не смог обработать ваш запрос. Попробуйте переформулировать."
    #             )
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _handle_ai_conversation: {e}")
    #         self.bot.reply_to(
    #             message,
    #             "❌ Ошибка при обработке запроса. Обратитесь к администраторам."
    #         )
    
    # def _contains_gratitude(self, text: str) -> bool:
    #     """Проверка содержит ли текст благодарности"""
    #     if not self.db.get_setting('auto_karma_enabled', False):
    #         return False
    #     
    #     gratitude_words = [
    #         # Русские
    #         'спасибо', 'спс', 'благодарю', 'огонь', 'полезно', 'помогло',
    #         'выручил', 'выручила', 'плюс в карму', 'респект', 'крутяк',
    #         'классно', 'топ', 'красава',
    #         
    #         # Английские
    #         'thanks', 'thx', 'thank you', 'awesome', 'cool', 'nice',
    #         'great', 'helpful', 'amazing'
    #     ]
    #     
    #     text_lower = text.lower()
    #     return any(word in text_lower for word in gratitude_words)
    
    # def _handle_gratitude_message(self, message: Message):
    #     """Обработка сообщения с благодарностью"""
    #     try:
    #         from_user_id = message.from_user.id
    #         to_user_id = message.reply_to_message.from_user.id
    #         
    #         # Проверяем что это не автоблагодарность
    #         if from_user_id == to_user_id:
    #             return
    #         
    #         # Проверяем cooldown
    #         cooldown_minutes = int(os.getenv('GRATITUDE_COOLDOWN_MINUTES', '60'))
    #         if not self._check_gratitude_cooldown(from_user_id, to_user_id, cooldown_minutes):
    #             return
    #         
    #         # Проверяем минимальную длину сообщения
    #         min_length = int(os.getenv('MIN_MESSAGE_LENGTH_FOR_KARMA', '10'))
    #         if len(message.text) < min_length:
    #             return
    #         
    #         # Определяем ключевое слово благодарности
    #         trigger_word = self._extract_gratitude_word(message.text)
    #         
    #         # Начисляем карму
    #         from services.karma import KarmaManager
    #         karma_manager = KarmaManager(self.db, None)
    #         
    #         success = karma_manager.add_auto_karma(
    #             to_user_id=to_user_id,
    #             from_user_id=from_user_id,
    #             trigger_word=trigger_word,
    #             context=message.text,
    #             message_id=message.message_id
    #         )
    #         
    #         if success:
    #             # Получаем информацию о получателе
    #             to_user = self.db.get_user_by_id(to_user_id)
    #             to_username = f"@{to_user.username}" if to_user and to_user.username else f"ID{to_user_id}"
    #             
    #             self.bot.reply_to(
    #                 message,
    #                 f"{to_username} твоя карма повышена на +1, продолжай быть примером для остальных! 😀"
    #             )
    #             
    #             logger.info(f"Автокарма: {from_user_id}→{to_user_id} +1 за '{trigger_word}'")
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _handle_gratitude_message: {e}")
    
    # def _check_gratitude_cooldown(self, from_user_id: int, to_user_id: int, cooldown_minutes: int) -> bool:
    #     """Проверка cooldown для благодарностей"""
    #     # Проверяем последнее начисление кармы этой паре пользователей
    #     # Возвращаем True если можно начислять, False если еще рано
    #     return True  # Заглушка
    
    # def _extract_gratitude_word(self, text: str) -> str:
    #     """Извлечение ключевого слова благодарности"""
    #     gratitude_words = [
    #         'спасибо', 'спс', 'благодарю', 'огонь', 'полезно',
    #         'thanks', 'thx', 'awesome', 'cool', 'nice'
    #     ]
    #     
    #     text_lower = text.lower()
    #     for word in gratitude_words:
    #         if word in text_lower:
    #             return word
    #     
    #     return 'благодарность'
    
    # def _process_file_message(self, message: Message):
    #     """Обработка файлов (ПЛАН 3)"""
    #     try:
    #         user_id = message.from_user.id
    #         
    #         # Проверяем находится ли пользователь в форме
    #         if not self._is_user_in_form(user_id):
    #             return  # Игнорируем файлы вне контекста форм
    #         
    #         # Обрабатываем в зависимости от типа файла
    #         if message.photo:
    #             self._handle_photo_upload(message)
    #         elif message.document:
    #             self._handle_document_upload(message)
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _process_file_message: {e}")
    
    # def _handle_photo_upload(self, message: Message):
    #     """Обработка загрузки фото"""
    #     try:
    #         user_id = message.from_user.id
    #         
    #         # Получаем информацию о фото
    #         photo = message.photo[-1]  # Берем максимальное разрешение
    #         file_id = photo.file_id
    #         file_size = photo.file_size
    #         
    #         # Проверяем размер файла
    #         max_size_mb = int(os.getenv('SCREENSHOT_MAX_SIZE_MB', '10'))
    #         if file_size > max_size_mb * 1024 * 1024:
    #             self.bot.reply_to(
    #                 message,
    #                 f"❌ Файл слишком большой! Максимальный размер: {max_size_mb}MB"
    #             )
    #             return
    #         
    #         # Сохраняем в контексте формы
    #         from services.forms import FormManager
    #         form_manager = FormManager(self.db, None)
    #         
    #         result = form_manager.add_screenshot(user_id, file_id, file_size)
    #         
    #         if result['success']:
    #             self.bot.reply_to(
    #                 message,
    #                 f"✅ Скриншот добавлен! ({result['count']}/{result['max_count']})"
    #             )
    #         else:
    #             self.bot.reply_to(
    #                 message,
    #                 f"❌ {result['message']}"
    #             )
    #             
    #     except Exception as e:
    #         logger.error(f"❌ Ошибка _handle_photo_upload: {e}")
    #         self.bot.reply_to(
    #             message,
    #             "❌ Ошибка при загрузке скриншота"
    #         )


if __name__ == "__main__":
    """Тестирование MessageHandler"""
    from database.manager import DatabaseManager
    from utils.security import SecurityManager
    
    print("🧪 Тестирование MessageHandler...")
    
    # Создание тестовых компонентов
    db = DatabaseManager("sqlite:///:memory:")
    db.create_tables()
    
    security = SecurityManager([12345], [2, 3])
    
    # Тестирование message handler
    message_handler = MessageHandler(None, db, security)
    
    # Тестирование обнаружения URL
    print("\n🔗 Тестирование обнаружения URL:")
    test_texts = [
        "Привет! Вот ссылка: https://example.com",
        "Нет ссылок в этом сообщении",
        "Множество ссылок: http://test.org и https://another.com",
        "Просто текст без ссылок"
    ]
    
    for text in test_texts:
        has_urls = message_handler._contains_urls(text)
        status = "✅ Есть URL" if has_urls else "❌ Нет URL"
        print(f"• '{text[:30]}...': {status}")
    
    print("\n✅ Тестирование MessageHandler завершено!")