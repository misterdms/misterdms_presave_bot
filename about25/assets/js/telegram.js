/**
 * Интеграция с Telegram WebApp API
 * Do Presave Reminder Bot by Mister DMS
 */

class TelegramWebApp {
    constructor() {
        this.tg = window.Telegram?.WebApp;
        this.isReady = false;
        this.user = null;
        this.startParam = null;
        this.isDebug = false;
        
        this.init();
    }

    /**
     * Инициализация WebApp
     */
    init() {
        if (!this.tg) {
            console.warn('❌ Telegram WebApp API недоступен');
            this.initBrowserMode();
            return;
        }

        try {
            console.log('🚀 Инициализация Telegram WebApp...');
            
            // Инициализация WebApp
            this.tg.ready();
            this.tg.expand();
            
            // Получаем данные пользователя
            this.user = this.tg.initDataUnsafe?.user;
            this.startParam = this.tg.initDataUnsafe?.start_param;
            
            // Настройка темы и интерфейса
            this.setupTheme();
            this.setupMainButton();
            this.setupBackButton();
            this.setupEventHandlers();
            
            // Настройка viewport
            this.setupViewport();
            
            // Разрешение закрытия подтверждением
            this.tg.enableClosingConfirmation();
            
            this.isReady = true;
            console.log('✅ Telegram WebApp инициализирован успешно');
            console.log('👤 Пользователь:', this.user);
            
            // Отправляем событие готовности
            this.dispatchEvent('webapp:ready', { user: this.user });
            
        } catch (error) {
            console.error('❌ Ошибка инициализации Telegram WebApp:', error);
            this.initBrowserMode();
        }
    }

    /**
     * Настройка темы
     */
    setupTheme() {
        // Применяем тему Telegram к нашему WebApp
        if (this.tg.colorScheme === 'dark') {
            document.body.classList.add('dark-theme');
        }
        
        // Настройка цвета заголовка
        if (this.tg.setHeaderColor) {
            this.tg.setHeaderColor('#667eea');
        }
        
        // Настройка цвета фона
        if (this.tg.setBackgroundColor) {
            this.tg.setBackgroundColor('#667eea');
        }
        
        console.log('🎨 Тема настроена:', this.tg.colorScheme);
    }

    /**
     * Настройка главной кнопки
     */
    setupMainButton() {
        this.tg.MainButton.setText('🤖 Открыть бота');
        this.tg.MainButton.color = '#4CAF50';
        this.tg.MainButton.textColor = '#ffffff';
        this.tg.MainButton.show();

        // Обработчик клика по главной кнопке
        this.tg.MainButton.onClick(() => {
            this.openBot();
        });
        
        console.log('🔘 Главная кнопка настроена');
    }

    /**
     * Настройка кнопки "Назад"
     */
    setupBackButton() {
        // Кнопка назад скрыта по умолчанию
        this.tg.BackButton.hide();
        
        this.tg.BackButton.onClick(() => {
            this.close();
        });
    }

    /**
     * Настройка viewport
     */
    setupViewport() {
        if (this.tg.setViewportHeight) {
            this.tg.setViewportHeight('100vh');
        }
    }

    /**
     * Настройка обработчиков событий
     */
    setupEventHandlers() {
        // Обработчик получения данных от бота
        this.tg.onEvent('mainButtonClicked', () => {
            console.log('🔘 Главная кнопка нажата');
        });

        // Обработчик изменения темы
        this.tg.onEvent('themeChanged', () => {
            console.log('🎨 Тема изменена');
            this.setupTheme();
        });

        // Обработчик изменения viewport
        this.tg.onEvent('viewportChanged', (data) => {
            console.log('📱 Viewport изменен:', data);
        });

        // Обработчик события закрытия
        this.tg.onEvent('popupClosed', (data) => {
            console.log('❌ Popup закрыт:', data);
        });

        console.log('📡 Обработчики событий настроены');
    }

    /**
     * Режим браузера (fallback)
     */
    initBrowserMode() {
        console.log('🌐 Инициализация режима браузера');
        this.isReady = true;
        
        // Симулируем готовность WebApp
        setTimeout(() => {
            this.dispatchEvent('webapp:ready', { 
                user: null, 
                mode: 'browser' 
            });
        }, 100);
    }

    /**
     * Отправка команды боту
     */
    sendCommand(command, data = {}) {
        if (!this.isReady) {
            this.showNotification('WebApp не готов. Попробуйте позже.', 'error');
            return Promise.reject('WebApp not ready');
        }

        const commandData = {
            type: 'command',
            command: command,
            data: data,
            source: 'webapp',
            timestamp: Date.now(),
            user_id: this.user?.id || null,
            webapp_version: '1.0.0'
        };

        console.log('📤 Отправка команды:', command, data);

        if (this.tg && this.tg.sendData) {
            try {
                // Тактильная обратная связь
                this.hapticFeedback('medium');
                
                // Отправляем команду боту
                this.tg.sendData(JSON.stringify(commandData));
                
                // Показываем уведомление
                this.showNotification('Команда отправлена в бот! 🚀', 'success');
                
                // Закрываем WebApp для определенных команд
                if (this.shouldCloseAfterCommand(command)) {
                    setTimeout(() => {
                        this.close();
                    }, 1000);
                }
                
                return Promise.resolve();
                
            } catch (error) {
                console.error('❌ Ошибка отправки команды:', error);
                this.showNotification('Ошибка отправки команды', 'error');
                return Promise.reject(error);
            }
        } else {
            // Fallback для браузера
            this.showNotification('Откройте в Telegram: t.me/misterdms_presave_bot', 'info');
            setTimeout(() => {
                window.open('https://t.me/misterdms_presave_bot', '_blank');
            }, 1500);
            return Promise.resolve();
        }
    }

    /**
     * Определяет, нужно ли закрывать WebApp после команды
     */
    shouldCloseAfterCommand(command) {
        const closeCommands = [
            '/ask_support@misterdms_presave_bot',
            '/claim_support@misterdms_presave_bot',
            '/help@misterdms_presave_bot',
            '/last10links@misterdms_presave_bot'
        ];
        
        return closeCommands.includes(command);
    }

    /**
     * Запрос статистики у бота
     */
    requestStats() {
        if (!this.isReady) return Promise.reject('WebApp not ready');

        const statsRequest = {
            type: 'get_stats',
            webapp: true,
            timestamp: Date.now(),
            user_id: this.user?.id || null
        };

        console.log('📊 Запрос статистики...');

        if (this.tg && this.tg.sendData) {
            try {
                this.tg.sendData(JSON.stringify(statsRequest));
                return Promise.resolve();
            } catch (error) {
                console.error('❌ Ошибка запроса статистики:', error);
                return Promise.reject(error);
            }
        } else {
            console.log('📊 Используем статические данные');
            return Promise.resolve();
        }
    }

    /**
     * Обработка ответа от бота
     */
    handleBotResponse(data) {
        try {
            const response = JSON.parse(data);
            console.log('📨 Ответ от бота:', response);
            
            switch (response.type) {
                case 'stats':
                    this.handleStatsResponse(response.data);
                    break;
                case 'user_info':
                    this.handleUserInfoResponse(response.data);
                    break;
                case 'command_result':
                    this.handleCommandResult(response);
                    break;
                case 'error':
                    this.showNotification(response.message || 'Ошибка от бота', 'error');
                    break;
                default:
                    console.log('❓ Неизвестный тип ответа:', response.type);
            }
        } catch (error) {
            console.error('❌ Ошибка обработки ответа от бота:', error);
        }
    }

    /**
     * Обработка ответа статистики
     */
    handleStatsResponse(stats) {
        console.log('📊 Получена статистика:', stats);
        
        if (stats.users && window.animateCounter) {
            window.animateCounter('user-count', stats.users);
        }
        if (stats.support_requests && window.animateCounter) {
            window.animateCounter('support-count', stats.support_requests);
        }
        if (stats.karma_total && window.animateCounter) {
            window.animateCounter('karma-count', stats.karma_total);
        }
        
        // Отправляем событие обновления статистики
        this.dispatchEvent('stats:updated', stats);
    }

    /**
     * Обработка информации о пользователе
     */
    handleUserInfoResponse(userInfo) {
        console.log('👤 Получена информация о пользователе:', userInfo);
        
        // Обновляем интерфейс на основе данных пользователя
        if (window.personalizeInterface) {
            window.personalizeInterface(userInfo);
        }
        
        this.dispatchEvent('user:updated', userInfo);
    }

    /**
     * Обработка результата команды
     */
    handleCommandResult(result) {
        if (result.success) {
            this.showNotification(result.message || 'Команда выполнена успешно', 'success');
        } else {
            this.showNotification(result.message || 'Ошибка выполнения команды', 'error');
        }
    }

    /**
     * Показать уведомление
     */
    showNotification(message, type = 'info') {
        console.log(`📢 Уведомление (${type}):`, message);
        
        const container = document.getElementById('notification-container');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        container.appendChild(notification);
        
        // Автоматическое удаление через 3 секунды
        setTimeout(() => {
            notification.classList.add('hide');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    /**
     * Показать popup
     */
    showPopup(title, message, buttons = []) {
        if (this.tg && this.tg.showPopup) {
            this.tg.showPopup({
                title: title,
                message: message,
                buttons: buttons
            });
        } else {
            // Fallback для браузера
            alert(`${title}\n\n${message}`);
        }
    }

    /**
     * Показать подтверждение
     */
    showConfirm(message) {
        return new Promise((resolve) => {
            if (this.tg && this.tg.showConfirm) {
                this.tg.showConfirm(message, resolve);
            } else {
                // Fallback для браузера
                resolve(confirm(message));
            }
        });
    }

    /**
     * Тактильная обратная связь
     */
    hapticFeedback(type = 'light') {
        if (this.tg && this.tg.HapticFeedback) {
            switch (type) {
                case 'light':
                    this.tg.HapticFeedback.impactOccurred('light');
                    break;
                case 'medium':
                    this.tg.HapticFeedback.impactOccurred('medium');
                    break;
                case 'heavy':
                    this.tg.HapticFeedback.impactOccurred('heavy');
                    break;
                case 'selection':
                    this.tg.HapticFeedback.selectionChanged();
                    break;
                case 'success':
                    this.tg.HapticFeedback.notificationOccurred('success');
                    break;
                case 'warning':
                    this.tg.HapticFeedback.notificationOccurred('warning');
                    break;
                case 'error':
                    this.tg.HapticFeedback.notificationOccurred('error');
                    break;
            }
        }
    }

    /**
     * Открыть бота
     */
    openBot() {
        console.log('🤖 Открытие бота...');
        
        try {
            if (this.tg && this.tg.openTelegramLink) {
                this.tg.openTelegramLink('https://t.me/misterdms_presave_bot');
            } else {
                window.open('https://t.me/misterdms_presave_bot', '_blank');
            }
        } catch (error) {
            console.error('❌ Ошибка открытия бота:', error);
            window.open('https://t.me/misterdms_presave_bot', '_blank');
        }
    }

    /**
     * Открыть внешнюю ссылку
     */
    openLink(url) {
        console.log('🔗 Открытие ссылки:', url);
        
        try {
            if (this.tg && this.tg.openLink) {
                this.tg.openLink(url);
            } else {
                window.open(url, '_blank');
            }
        } catch (error) {
            console.error('❌ Ошибка открытия ссылки:', error);
            window.open(url, '_blank');
        }
    }

    /**
     * Закрыть WebApp
     */
    close() {
        console.log('❌ Закрытие WebApp...');
        
        if (this.tg && this.tg.close) {
            this.tg.close();
        } else {
            // Fallback для браузера
            if (window.history.length > 1) {
                window.history.back();
            } else {
                window.close();
            }
        }
    }

    /**
     * Получение информации о пользователе
     */
    getUserInfo() {
        return this.user;
    }

    /**
     * Получение стартового параметра
     */
    getStartParam() {
        return this.startParam;
    }

    /**
     * Проверка, запущен ли WebApp в Telegram
     */
    isTelegram() {
        return !!this.tg;
    }

    /**
     * Получение версии Telegram
     */
    getTelegramVersion() {
        return this.tg?.version || null;
    }

    /**
     * Получение платформы
     */
    getPlatform() {
        return this.tg?.platform || 'unknown';
    }

    /**
     * Отправка кастомного события
     */
    dispatchEvent(eventName, data = {}) {
        const event = new CustomEvent(eventName, { 
            detail: data 
        });
        document.dispatchEvent(event);
    }

    /**
     * Включение режима отладки
     */
    enableDebug() {
        this.isDebug = true;
        console.log('🐛 Режим отладки включен');
    }

    /**
     * Логирование отладочной информации
     */
    debug(...args) {
        if (this.isDebug) {
            console.log('🐛 [DEBUG]', ...args);
        }
    }

    /**
     * Получение информации о WebApp
     */
    getWebAppInfo() {
        return {
            isReady: this.isReady,
            isTelegram: this.isTelegram(),
            user: this.user,
            startParam: this.startParam,
            version: this.getTelegramVersion(),
            platform: this.getPlatform(),
            colorScheme: this.tg?.colorScheme || 'light'
        };
    }
}

// Создаем глобальный экземпляр
console.log('🎵 Инициализация Telegram WebApp для Do Presave Reminder Bot...');
window.telegramWebApp = new TelegramWebApp();

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TelegramWebApp;
}