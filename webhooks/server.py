"""
🌐 Webhook Server - Do Presave Reminder Bot v25+
HTTP сервер для webhook от Telegram и keep-alive для Render.com
"""

import json
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify, abort
import telebot
from telebot.types import Update

from config import config
from utils.security import security_manager
from utils.logger import get_logger, telegram_logger, performance_logger
from webhooks.keepalive import KeepAliveManager

logger = get_logger(__name__)

class WebhookServer:
    """HTTP сервер для webhook и API endpoints"""
    
    def __init__(self, bot: telebot.TeleBot):
        self.bot = bot
        self.app = Flask(__name__)
        self.keep_alive_manager = None
        
        # Статистика сервера
        self.server_stats = {
            'start_time': datetime.now(timezone.utc),
            'webhook_requests': 0,
            'health_checks': 0,
            'last_update': None,
            'errors': 0
        }
        
        # Настраиваем маршруты
        self._setup_routes()
        
        logger.info("🌐 Webhook Server инициализирован")
    
    def _setup_routes(self):
        """Настройка всех маршрутов Flask"""
        
        # Основной webhook endpoint
        @self.app.route(config.WEBHOOK_PATH, methods=['POST'])
        def webhook():
            return self._handle_webhook()
        
        # Health check endpoint
        @self.app.route(config.HEALTH_CHECK_PATH, methods=['GET'])
        def health_check():
            return self._handle_health_check()
        
        # Статистика сервера (только для админов)
        @self.app.route('/stats', methods=['GET'])
        def server_stats():
            return self._handle_stats_request()
        
        # Информация о боте
        @self.app.route('/info', methods=['GET'])
        def bot_info():
            return self._handle_info_request()
        
        # API для проверки статуса планов
        @self.app.route('/api/plans', methods=['GET'])
        def plans_status():
            return self._handle_plans_status()
        
        # Корневой маршрут
        @self.app.route('/', methods=['GET'])
        def root():
            return self._handle_root_request()
        
        # Обработчик ошибок
        @self.app.errorhandler(404)
        def not_found(error):
            return jsonify({
                'error': 'Not Found',
                'message': 'Endpoint not found',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 404
        
        @self.app.errorhandler(500)
        def internal_error(error):
            self.server_stats['errors'] += 1
            logger.error(f"❌ Internal server error: {error}")
            return jsonify({
                'error': 'Internal Server Error',
                'message': 'Something went wrong',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 500
    
    def _handle_webhook(self):
        """Обработка webhook от Telegram"""
        try:
            start_time = time.time()
            
            # Проверяем Content-Type
            if request.content_type != 'application/json':
                logger.warning("⚠️ Неверный Content-Type для webhook")
                abort(400)
            
            # Получаем данные
            json_data = request.get_json()
            if not json_data:
                logger.warning("⚠️ Пустые данные в webhook")
                abort(400)
            
            # Проверяем подпись (опционально)
            if hasattr(request, 'headers') and 'X-Telegram-Bot-Api-Secret-Token' in request.headers:
                secret_token = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
                if secret_token != config.WEBHOOK_SECRET:
                    logger.warning("⚠️ Неверный secret token в webhook")
                    abort(403)
            
            # Создаем объект Update
            update = Update.de_json(json_data)
            if not update:
                logger.warning("⚠️ Не удалось декодировать Update")
                abort(400)
            
            # Обрабатываем update
            self._process_update(update)
            
            # Обновляем статистику
            processing_time = (time.time() - start_time) * 1000
            self.server_stats['webhook_requests'] += 1
            self.server_stats['last_update'] = datetime.now(timezone.utc)
            
            # Логируем производительность
            performance_logger.log_execution_time('webhook_processing', processing_time)
            
            # Возвращаем успешный ответ
            return jsonify({'status': 'ok'}), 200
            
        except Exception as e:
            self.server_stats['errors'] += 1
            logger.error(f"❌ Ошибка обработки webhook: {e}")
            return jsonify({'error': 'Webhook processing failed'}), 500
    
    def _process_update(self, update: Update):
        """Обработка Update от Telegram"""
        try:
            # Извлекаем информацию о пользователе и типе update
            user_id = None
            update_type = None
            
            if update.message:
                user_id = update.message.from_user.id
                update_type = 'message'
            elif update.callback_query:
                user_id = update.callback_query.from_user.id
                update_type = 'callback_query'
            elif update.inline_query:
                user_id = update.inline_query.from_user.id
                update_type = 'inline_query'
            
            # Логируем получение update
            telegram_logger.webhook_received(
                update_type=update_type or 'unknown',
                user_id=user_id,
                update_id=update.update_id
            )
            
            # Передаем update боту для обработки
            self.bot.process_new_updates([update])
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки Update: {e}")
            raise
    
    def _handle_health_check(self):
        """Обработка health check запросов"""
        try:
            self.server_stats['health_checks'] += 1
            
            # Проверяем состояние компонентов
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'uptime_seconds': (datetime.now(timezone.utc) - self.server_stats['start_time']).total_seconds(),
                'components': {
                    'webhook_server': True,
                    'telegram_bot': True,
                    'database': False,
                    'keep_alive': False
                }
            }
            
            # Проверяем базу данных
            try:
                from database.manager import get_database_manager
                db = get_database_manager()
                db_health = db.health_check()
                health_status['components']['database'] = db_health['database_connection'] == 'ok'
            except Exception as e:
                logger.warning(f"⚠️ Ошибка проверки БД в health check: {e}")
            
            # Проверяем keep-alive
            if self.keep_alive_manager:
                health_status['components']['keep_alive'] = self.keep_alive_manager.is_running()
            
            # Определяем общий статус
            all_components_healthy = all(health_status['components'].values())
            if not all_components_healthy:
                health_status['status'] = 'degraded'
            
            # Добавляем статистику
            health_status['stats'] = {
                'webhook_requests': self.server_stats['webhook_requests'],
                'health_checks': self.server_stats['health_checks'],
                'errors': self.server_stats['errors'],
                'last_update': self.server_stats['last_update'].isoformat() if self.server_stats['last_update'] else None
            }
            
            status_code = 200 if all_components_healthy else 503
            return jsonify(health_status), status_code
            
        except Exception as e:
            logger.error(f"❌ Ошибка health check: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }), 500
    
    def _handle_stats_request(self):
        """Обработка запросов статистики (только для админов)"""
        try:
            # Простая проверка прав (в production можно добавить токен)
            auth_header = request.headers.get('Authorization')
            if not auth_header or auth_header != f"Bearer {config.WEBHOOK_SECRET}":
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Получаем расширенную статистику
            stats = {
                'server': self.server_stats.copy(),
                'bot': {
                    'enabled': self._is_bot_enabled(),
                    'limit_mode': self._get_current_limit_mode(),
                    'whitelist_threads': len(config.WHITELIST_THREADS),
                    'admin_count': len(config.ADMIN_IDS)
                },
                'plans': {
                    'plan_1': True,
                    'plan_2': config.ENABLE_PLAN_2_FEATURES,
                    'plan_3': config.ENABLE_PLAN_3_FEATURES,
                    'plan_4': config.ENABLE_PLAN_4_FEATURES
                }
            }
            
            # Добавляем статистику БД
            try:
                from database.manager import get_database_manager
                db = get_database_manager()
                db_stats = db.get_database_stats()
                stats['database'] = db_stats
            except Exception as e:
                stats['database'] = {'error': str(e)}
            
            # Конвертируем datetime объекты
            if stats['server']['start_time']:
                stats['server']['start_time'] = stats['server']['start_time'].isoformat()
            if stats['server']['last_update']:
                stats['server']['last_update'] = stats['server']['last_update'].isoformat()
            
            return jsonify(stats), 200
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return jsonify({'error': 'Stats unavailable'}), 500
    
    def _handle_info_request(self):
        """Обработка запросов информации о боте"""
        try:
            bot_info = {
                'name': 'Do Presave Reminder Bot',
                'version': 'v25+ (Поэтапная разработка)',
                'description': 'Автоматизация взаимных пресейвов в музыкальном сообществе',
                'developer': '@Mister_DMS',
                'features': {
                    'presave_reminders': True,
                    'karma_system': config.ENABLE_PLAN_2_FEATURES,
                    'ai_integration': config.ENABLE_PLAN_3_FEATURES,
                    'backup_system': config.ENABLE_PLAN_4_FEATURES
                },
                'supported_platforms': [
                    'Spotify', 'Apple Music', 'YouTube Music', 'SoundCloud',
                    'Bandcamp', 'Deezer', 'Tidal', 'Amazon Music',
                    'Linktree', 'FanLink', 'SmartURL', 'Feature.fm'
                ],
                'deployment': {
                    'platform': 'Render.com',
                    'database': 'PostgreSQL',
                    'monitoring': 'UptimeRobot'
                }
            }
            
            return jsonify(bot_info), 200
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения информации: {e}")
            return jsonify({'error': 'Info unavailable'}), 500
    
    def _handle_plans_status(self):
        """API для проверки статуса планов развития"""
        try:
            plans_status = {
                'plan_1': {
                    'name': 'Базовый функционал',
                    'version': 'v25',
                    'status': 'active',
                    'features': [
                        'Реакция на ссылки',
                        'Система меню',
                        'Управление лимитами',
                        'Статистика'
                    ]
                },
                'plan_2': {
                    'name': 'Система кармы',
                    'version': 'v26',
                    'status': 'active' if config.ENABLE_PLAN_2_FEATURES else 'development',
                    'features': [
                        'Система званий',
                        'Лидерборды',
                        'Управление кармой',
                        'Соотношения'
                    ]
                },
                'plan_3': {
                    'name': 'ИИ и интерактивные формы',
                    'version': 'v27',
                    'status': 'active' if config.ENABLE_PLAN_3_FEATURES else 'development',
                    'features': [
                        'ИИ-помощник',
                        'Автоматическая карма',
                        'Интерактивные формы',
                        'Распознавание благодарностей'
                    ]
                },
                'plan_4': {
                    'name': 'Backup система',
                    'version': 'v27.1',
                    'status': 'active' if config.ENABLE_PLAN_4_FEATURES else 'development',
                    'features': [
                        'Автоматический backup',
                        'Циклические миграции',
                        'Уведомления о лимитах',
                        'Восстановление данных'
                    ]
                }
            }
            
            return jsonify(plans_status), 200
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статуса планов: {e}")
            return jsonify({'error': 'Plans status unavailable'}), 500
    
    def _handle_root_request(self):
        """Обработка корневого запроса"""
        try:
            welcome_info = {
                'message': 'Do Presave Reminder Bot API',
                'version': 'v25+',
                'status': 'running',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'endpoints': {
                    '/health': 'Health check',
                    '/info': 'Bot information',
                    '/api/plans': 'Development plans status',
                    '/stats': 'Server statistics (auth required)'
                },
                'documentation': 'https://github.com/MisterDMS/presave-bot',
                'support': '@Mister_DMS'
            }
            
            return jsonify(welcome_info), 200
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки корневого запроса: {e}")
            return jsonify({'error': 'Service unavailable'}), 500
    
    # ============================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ============================================
    
    def _is_bot_enabled(self) -> bool:
        """Проверка включен ли бот"""
        try:
            from database.manager import get_database_manager
            db = get_database_manager()
            enabled = db.get_setting('bot_enabled')
            return enabled == 'true' if enabled else True
        except:
            return True
    
    def _get_current_limit_mode(self) -> str:
        """Получение текущего режима лимитов"""
        try:
            from database.manager import get_database_manager
            db = get_database_manager()
            mode = db.get_setting('current_limit_mode')
            return mode or config.DEFAULT_LIMIT_MODE
        except:
            return config.DEFAULT_LIMIT_MODE
    
    def start_server(self, debug: bool = False, use_reloader: bool = False):
        """Запуск Flask сервера"""
        try:
            logger.info(f"🌐 Запуск webhook сервера на порту {config.PORT}")
            logger.info(f"🔗 Webhook URL: {config.get_webhook_url()}")
            
            # Запускаем keep-alive менеджер
            if not debug:  # Не запускаем keep-alive в debug режиме
                self.keep_alive_manager = KeepAliveManager()
                self.keep_alive_manager.start()
            
            # Настраиваем Flask
            self.app.config['SECRET_KEY'] = config.WEBHOOK_SECRET
            
            # Запускаем сервер
            self.app.run(
                host='0.0.0.0',
                port=config.PORT,
                debug=debug,
                use_reloader=use_reloader,
                threaded=True
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска сервера: {e}")
            raise
    
    def start_server_threaded(self):
        """Запуск сервера в отдельном потоке"""
        try:
            server_thread = threading.Thread(
                target=self.start_server,
                kwargs={'debug': False, 'use_reloader': False},
                daemon=True
            )
            server_thread.start()
            
            logger.info("🌐 Webhook сервер запущен в отдельном потоке")
            return server_thread
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска сервера в потоке: {e}")
            raise
    
    def setup_webhook(self):
        """Установка webhook в Telegram"""
        try:
            webhook_url = config.get_webhook_url()
            
            if not webhook_url:
                logger.warning("⚠️ RENDER_EXTERNAL_URL не настроен, webhook не установлен")
                return False
            
            # Удаляем существующий webhook
            self.bot.remove_webhook()
            time.sleep(1)
            
            # Устанавливаем новый webhook
            result = self.bot.set_webhook(
                url=webhook_url,
                certificate=None,  # Используем Let's Encrypt сертификат Render.com
                max_connections=40,
                allowed_updates=['message', 'callback_query', 'inline_query']
            )
            
            if result:
                logger.info(f"✅ Webhook установлен: {webhook_url}")
                
                # Проверяем информацию о webhook
                webhook_info = self.bot.get_webhook_info()
                logger.info(f"📋 Webhook info: URL={webhook_info.url}, pending={webhook_info.pending_update_count}")
                
                return True
            else:
                logger.error("❌ Не удалось установить webhook")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка установки webhook: {e}")
            return False
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Получение статистики сервера"""
        try:
            current_time = datetime.now(timezone.utc)
            uptime = current_time - self.server_stats['start_time']
            
            stats = self.server_stats.copy()
            stats['uptime_seconds'] = uptime.total_seconds()
            stats['uptime_formatted'] = str(uptime).split('.')[0]  # Убираем микросекунды
            stats['requests_per_minute'] = self.server_stats['webhook_requests'] / max(uptime.total_seconds() / 60, 1)
            
            # Конвертируем datetime в строки
            stats['start_time'] = stats['start_time'].isoformat()
            if stats['last_update']:
                stats['last_update'] = stats['last_update'].isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики сервера: {e}")
            return {}
    
    def stop_server(self):
        """Остановка сервера и очистка ресурсов"""
        try:
            # Останавливаем keep-alive
            if self.keep_alive_manager:
                self.keep_alive_manager.stop()
            
            # Удаляем webhook
            try:
                self.bot.remove_webhook()
                logger.info("✅ Webhook удален")
            except:
                pass
            
            logger.info("🌐 Webhook сервер остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка остановки сервера: {e}")

# ============================================
# ГЛОБАЛЬНАЯ ФУНКЦИЯ ИНИЦИАЛИЗАЦИИ
# ============================================

def create_webhook_server(bot: telebot.TeleBot) -> WebhookServer:
    """Создание webhook сервера"""
    return WebhookServer(bot)

# ============================================
# ЭКСПОРТ
# ============================================

__all__ = ['WebhookServer', 'create_webhook_server']

if __name__ == "__main__":
    print("🧪 Тестирование Webhook Server...")
    print("✅ Модуль server.py готов к запуску")
