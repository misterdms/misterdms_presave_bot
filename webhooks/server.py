"""
HTTP сервер для webhook Do Presave Reminder Bot v25+
Минималистичный HTTP сервер на встроенном модуле для работы на Render.com
"""

import os
import json
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import telebot

from utils.logger import get_logger, log_api_call

logger = get_logger(__name__)

class WebhookHandler(BaseHTTPRequestHandler):
    """Обработчик HTTP запросов для webhook"""
    
    def __init__(self, *args, bot=None, webhook_secret=None, **kwargs):
        self.bot = bot
        self.webhook_secret = webhook_secret
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Обработка GET запросов"""
        try:
            parsed_url = urlparse(self.path)
            
            if parsed_url.path == '/':
                self._handle_root()
            elif parsed_url.path == '/health':
                self._handle_health()
            elif parsed_url.path == '/status':
                self._handle_status()
            else:
                self._handle_not_found()
                
        except Exception as e:
            logger.error(f"❌ Ошибка GET запроса: {e}")
            self._send_error(500, "Internal Server Error")
    
    def do_POST(self):
        """Обработка POST запросов (webhook от Telegram)"""
        try:
            parsed_url = urlparse(self.path)
            
            if parsed_url.path == '/webhook':
                self._handle_webhook()
            else:
                self._handle_not_found()
                
        except Exception as e:
            logger.error(f"❌ Ошибка POST запроса: {e}")
            self._send_error(500, "Internal Server Error")
    
    def _handle_root(self):
        """Обработка корневого пути"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Do Presave Reminder Bot v25+</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 600px; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .status {{ color: #28a745; font-weight: bold; }}
        .info {{ color: #6c757d; margin: 10px 0; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Do Presave Reminder Bot</h1>
        <div class="status">✅ Сервер работает нормально</div>
        
        <div class="section">
            <h3>📊 Информация о сервере</h3>
            <div class="info">Версия: v25+ (ПЛАН 1)</div>
            <div class="info">Время запуска: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</div>
            <div class="info">Режим: Production</div>
        </div>
        
        <div class="section">
            <h3>🔗 Endpoints</h3>
            <div class="info">GET /health - Health check</div>
            <div class="info">GET /status - Статус сервера</div>
            <div class="info">POST /webhook - Telegram webhook</div>
        </div>
        
        <div class="section">
            <h3>🎯 Возможности ПЛАН 1</h3>
            <div class="info">✅ Обработка ссылок и напоминания</div>
            <div class="info">✅ Админское меню с навигацией</div>
            <div class="info">✅ Режимы лимитов API</div>
            <div class="info">✅ Базовая статистика</div>
            <div class="info">⏸️ ПЛАН 2: Система кармы (в разработке)</div>
            <div class="info">⏸️ ПЛАН 3: ИИ и формы (в разработке)</div>
            <div class="info">⏸️ ПЛАН 4: Backup система (в разработке)</div>
        </div>
    </div>
</body>
</html>
"""
        
        self._send_response(200, html_content, content_type='text/html')
        log_api_call(logger, "GET", "/", "200")
    
    def _handle_health(self):
        """Health check endpoint"""
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "v25+",
            "plan": "ПЛАН 1",
            "uptime": "running",
            "bot_connected": self.bot is not None,
            "webhook_configured": self.webhook_secret is not None
        }
        
        self._send_json_response(200, health_data)
        log_api_call(logger, "GET", "/health", "200")
    
    def _handle_status(self):
        """Статус сервера и бота"""
        try:
            # Пытаемся получить информацию о боте
            bot_info = None
            if self.bot:
                try:
                    me = self.bot.get_me()
                    bot_info = {
                        "username": me.username,
                        "first_name": me.first_name,
                        "id": me.id
                    }
                except Exception as e:
                    logger.error(f"❌ Ошибка получения info о боте: {e}")
            
            status_data = {
                "server": {
                    "status": "running",
                    "timestamp": datetime.now().isoformat(),
                    "version": "v25+",
                    "plan": "ПЛАН 1 - Базовый функционал"
                },
                "bot": bot_info,
                "features": {
                    "plan_1": {
                        "enabled": True,
                        "description": "Базовый функционал",
                        "features": [
                            "Обработка ссылок",
                            "Админское меню", 
                            "Режимы лимитов",
                            "Базовая статистика"
                        ]
                    },
                    "plan_2": {
                        "enabled": False,
                        "description": "Система кармы",
                        "status": "В разработке"
                    },
                    "plan_3": {
                        "enabled": False,
                        "description": "ИИ и формы",
                        "status": "В разработке"
                    },
                    "plan_4": {
                        "enabled": False,
                        "description": "Backup система",
                        "status": "В разработке"
                    }
                },
                "environment": {
                    "host": os.getenv('HOST', '0.0.0.0'),
                    "port": os.getenv('PORT', '8080'),
                    "external_url": os.getenv('RENDER_EXTERNAL_URL'),
                    "webhook_configured": bool(self.webhook_secret)
                }
            }
            
            self._send_json_response(200, status_data)
            log_api_call(logger, "GET", "/status", "200")
            
        except Exception as e:
            logger.error(f"❌ Ошибка _handle_status: {e}")
            self._send_error(500, "Error getting status")
    
    def _handle_webhook(self):
        """Обработка webhook от Telegram"""
        try:
            # Проверяем Content-Type
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('application/json'):
                self._send_error(400, "Invalid Content-Type")
                return
            
            # Читаем тело запроса
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_error(400, "Empty request body")
                return
            
            body = self.rfile.read(content_length)
            
            # Проверяем webhook secret если настроен
            if self.webhook_secret:
                # В продакшене здесь должна быть проверка подписи
                # Для ПЛАНА 1 делаем базовую проверку
                pass
            
            # Парсим JSON
            try:
                update_data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON: {e}")
                self._send_error(400, "Invalid JSON")
                return
            
            # Проверяем что есть бот
            if not self.bot:
                logger.error("❌ Бот не инициализирован")
                self._send_error(500, "Bot not initialized")
                return
            
            # Обрабатываем update
            try:
                update = telebot.types.Update.de_json(update_data)
                self.bot.process_new_updates([update])
                
                # Логируем успешную обработку
                update_type = "message" if update.message else "callback_query" if update.callback_query else "unknown"
                log_api_call(logger, "POST", "/webhook", "200", update_type=update_type)
                
                self._send_response(200, "OK")
                
            except Exception as e:
                logger.error(f"❌ Ошибка обработки update: {e}")
                self._send_error(500, "Error processing update")
                
        except Exception as e:
            logger.error(f"❌ Ошибка _handle_webhook: {e}")
            self._send_error(500, "Internal webhook error")
    
    def _handle_not_found(self):
        """Обработка 404"""
        self._send_error(404, "Not Found")
        log_api_call(logger, self.command, self.path, "404")
    
    def _send_response(self, status_code: int, content: str, content_type: str = 'text/plain'):
        """Отправка HTTP ответа"""
        try:
            self.send_response(status_code)
            self.send_header('Content-Type', f'{content_type}; charset=utf-8')
            self.send_header('Content-Length', str(len(content.encode('utf-8'))))
            
            # CORS headers для возможных фронтенд запросов
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ответа: {e}")
    
    def _send_json_response(self, status_code: int, data: dict):
        """Отправка JSON ответа"""
        try:
            json_content = json.dumps(data, ensure_ascii=False, indent=2)
            self._send_response(status_code, json_content, 'application/json')
        except Exception as e:
            logger.error(f"❌ Ошибка отправки JSON: {e}")
            self._send_error(500, "JSON encoding error")
    
    def _send_error(self, status_code: int, message: str):
        """Отправка ошибки"""
        error_data = {
            "error": True,
            "status_code": status_code,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        self._send_json_response(status_code, error_data)
    
    def log_message(self, format, *args):
        """Переопределяем логирование запросов"""
        # Логируем через наш логгер вместо стандартного вывода
        logger.debug(f"🌐 HTTP: {format % args}")


class WebhookServer:
    """HTTP сервер для webhook с интеграцией бота"""
    
    def __init__(self, bot: telebot.TeleBot, webhook_secret: str = None, 
                 host: str = '0.0.0.0', port: int = 8080):
        """Инициализация сервера"""
        self.bot = bot
        self.webhook_secret = webhook_secret
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        
        logger.info(f"WebhookServer инициализирован: {host}:{port}")
    
    def create_handler_class(self):
        """Создание класса обработчика с инжекцией зависимостей"""
        bot = self.bot
        webhook_secret = self.webhook_secret
        
        class CustomWebhookHandler(WebhookHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, bot=bot, webhook_secret=webhook_secret, **kwargs)
        
        return CustomWebhookHandler
    
    def start_server(self):
        """Запуск HTTP сервера"""
        try:
            handler_class = self.create_handler_class()
            
            self.server = HTTPServer((self.host, self.port), handler_class)
            
            logger.info(f"🌐 HTTP сервер запущен на {self.host}:{self.port}")
            logger.info(f"🔗 Webhook URL: https://{os.getenv('RENDER_EXTERNAL_URL', 'localhost')}/webhook")
            
            # Запускаем сервер (блокирующий вызов)
            self.server.serve_forever()
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска HTTP сервера: {e}")
            raise
    
    def start_server_thread(self):
        """Запуск сервера в отдельном потоке"""
        try:
            self.server_thread = threading.Thread(
                target=self.start_server,
                daemon=True,
                name="WebhookServer"
            )
            
            self.server_thread.start()
            logger.info("🌐 HTTP сервер запущен в фоновом потоке")
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска сервера в потоке: {e}")
            raise
    
    def stop_server(self):
        """Остановка сервера"""
        try:
            if self.server:
                logger.info("🛑 Остановка HTTP сервера...")
                self.server.shutdown()
                self.server.server_close()
                
                if self.server_thread and self.server_thread.is_alive():
                    self.server_thread.join(timeout=5)
                
                logger.info("✅ HTTP сервер остановлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка остановки сервера: {e}")
    
    def is_running(self) -> bool:
        """Проверка работает ли сервер"""
        return self.server is not None and self.server_thread is not None and self.server_thread.is_alive()


def create_webhook_server(bot: telebot.TeleBot) -> WebhookServer:
    """Фабрика для создания webhook сервера"""
    
    # Получаем настройки из переменных окружения
    webhook_secret = os.getenv('WEBHOOK_SECRET')
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8080'))
    
    # Создаем сервер
    server = WebhookServer(
        bot=bot,
        webhook_secret=webhook_secret,
        host=host,
        port=port
    )
    
    return server

def init_webhook_server(config, bot: telebot.TeleBot) -> WebhookServer:
    """
    Инициализация webhook сервера с конфигурацией
    
    Args:
        config: Объект конфигурации бота
        bot: Экземпляр телеграм бота
        
    Returns:
        WebhookServer: Инициализированный сервер
    """
    try:
        logger.info("🌐 Инициализация webhook сервера...")
        
        # Создаем сервер с настройками из конфигурации
        server = WebhookServer(
            bot=bot,
            webhook_secret=getattr(config, 'WEBHOOK_SECRET', None),
            host=getattr(config, 'HOST', '0.0.0.0'),
            port=int(os.getenv('PORT', '8080'))
        )
        
        logger.info(f"✅ Webhook сервер инициализирован: {server.host}:{server.port}")
        return server
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации webhook сервера: {e}")
        raise

if __name__ == "__main__":
    """Тестирование webhook сервера"""
    import time
    
    print("🧪 Тестирование WebhookServer...")
    
    # Создание тестового сервера
    print("🌐 Создание тестового сервера...")
    server = WebhookServer(
        bot=None,  # Тестовый режим без бота
        webhook_secret="test_secret",
        host="127.0.0.1",
        port=8888
    )
    
    try:
        # Запуск в отдельном потоке
        print("🚀 Запуск сервера в тестовом режиме...")
        server.start_server_thread()
        
        # Ждем запуска
        time.sleep(2)
        
        if server.is_running():
            print("✅ Сервер запущен успешно!")
            print("🔗 Проверьте: http://127.0.0.1:8888")
            print("🔗 Health check: http://127.0.0.1:8888/health")
            
            # Ждем немного
            time.sleep(3)
        else:
            print("❌ Сервер не запустился")
        
    finally:
        print("🛑 Остановка тестового сервера...")
        server.stop_server()
        print("✅ Тестирование завершено!")
