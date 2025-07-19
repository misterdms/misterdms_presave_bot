/**
 * Основная логика WebApp
 * Do Presave Reminder Bot by Mister DMS
 */

class PresaveWebApp {
    constructor() {
        this.isInitialized = false;
        this.user = null;
        this.stats = {
            users: 247,
            support: 1842,
            karma: 3156
        };
        
        this.init();
    }

    /**
     * Инициализация приложения
     */
    async init() {
        console.log('🎵 Инициализация Do Presave Reminder Bot WebApp...');
        
        try {
            // Показываем лоадер
            this.showLoader();
            
            // Инициализируем различные режимы
            await this.initializeMode();
            
            // Общая инициализация
            await this.initializeCommonFeatures();
            
            // Скрываем лоадер
            this.hideLoader();
            
            this.isInitialized = true;
            console.log('✅ WebApp инициализирован успешно');
            
        } catch (error) {
            console.error('❌ Ошибка инициализации WebApp:', error);
            this.handleInitializationError(error);
        }
    }

    /**
     * Определение режима работы и инициализация
     */
    async initializeMode() {
        const isInTelegram = window.telegramWebApp && window.telegramWebApp.isTelegram();
        
        if (isInTelegram) {
            console.log('✅ Запущено в Telegram WebApp');
            await this.initializeTelegramMode();
        } else {
            console.log('⚠️ Запущено в браузере (режим предпросмотра)');
            await this.initializeBrowserMode();
        }
    }

    /**
     * Инициализация режима Telegram
     */
    async initializeTelegramMode() {
        // Ждем готовности Telegram WebApp
        if (window.telegramWebApp.isReady) {
            await this.setupTelegramFeatures();
        } else {
            // Ждем событие готовности
            document.addEventListener('webapp:ready', () => {
                this.setupTelegramFeatures();
            });
        }
    }

    /**
     * Настройка функций Telegram
     */
    async setupTelegramFeatures() {
        console.log('⚙️ Настройка функций Telegram...');
        
        // Получаем информацию о пользователе
        this.user = window.telegramWebApp.getUserInfo();
        if (this.user) {
            console.log('👤 Пользователь:', this.user);
            this.personalizeInterface(this.user);
        }
        
        // Загружаем статистику от бота
        this.startStatsUpdater();
        
        // Настраиваем обработчики событий Telegram
        this.setupTelegramEventHandlers();
    }

    /**
     * Инициализация режима браузера
     */
    async initializeBrowserMode() {
        console.log('🌐 Настройка режима браузера...');
        
        // Показываем уведомление о режиме браузера
        setTimeout(() => {
            this.showBrowserModeNotice();
        }, 2000);
        
        // Загружаем демонстрационные данные
        setTimeout(() => {
            window.loadStats();
        }, 1000);
    }

    /**
     * Общая инициализация функций
     */
    async initializeCommonFeatures() {
        console.log('⚙️ Инициализация общих функций...');
        
        // Инициализация анимаций
        this.initializeAnimations();
        
        // Добавление обработчиков событий
        this.addEventListeners();
        
        // Оптимизация производительности
        this.optimizePerformance();
        
        // Настройка клавиатурных сочетаний
        this.setupKeyboardShortcuts();
        
        // Проверка доступности функций
        this.checkFeatureSupport();
    }

    /**
     * Персонализация интерфейса
     */
    personalizeInterface(userInfo) {
        console.log('👤 Персонализация интерфейса для:', userInfo.first_name);
        
        // Можно добавить приветствие или другую персонализацию
        if (userInfo.first_name) {
            const welcomeMessage = `👋 Привет, ${userInfo.first_name}! Добро пожаловать в музыкальное сообщество!`;
            setTimeout(() => {
                window.showNotification(welcomeMessage, 'info');
            }, 1500);
        }
        
        // Если есть стартовый параметр, обрабатываем его
        const startParam = window.telegramWebApp.getStartParam();
        if (startParam) {
            this.handleStartParam(startParam);
        }
    }

    /**
     * Обработка стартового параметра
     */
    handleStartParam(startParam) {
        console.log('🚀 Обработка стартового параметра:', startParam);
        
        switch (startParam) {
            case 'help':
                setTimeout(() => window.sendCommand('/help@misterdms_presave_bot'), 1000);
                break;
            case 'stats':
                this.highlightStatsSection();
                break;
            case 'support':
                setTimeout(() => window.sendCommand('/ask_support@misterdms_presave_bot'), 1000);
                break;
            default:
                console.log('ℹ️ Неизвестный стартовый параметр:', startParam);
        }
    }

    /**
     * Подсветка секции статистики
     */
    highlightStatsSection() {
        const statsElement = document.querySelector('.stats-mini');
        if (statsElement) {
            statsElement.scrollIntoView({ behavior: 'smooth' });
            statsElement.style.animation = 'glow 2s ease-in-out';
            setTimeout(() => {
                statsElement.style.animation = '';
            }, 2000);
        }
    }

    /**
     * Инициализация анимаций
     */
    initializeAnimations() {
        console.log('✨ Инициализация анимаций...');
        
        // Запуск анимаций для элементов с задержкой
        const animatedElements = document.querySelectorAll('[class*="animation-delay"]');
        
        animatedElements.forEach((element) => {
            element.style.animationName = 'fadeInUp';
            element.style.animationDuration = '0.8s';
            element.style.animationFillMode = 'forwards';
        });
        
        // Добавляем анимацию появления для всех основных секций
        const sections = document.querySelectorAll('.header, .features, .karma-section, .action-buttons, .ai-section, .other-bots');
        sections.forEach((section, index) => {
            section.style.opacity = '0';
            section.style.animation = `fadeInUp 0.8s ease-out ${(index + 1) * 0.1}s forwards`;
        });
    }

    /**
     * Добавление обработчиков событий
     */
    addEventListeners() {
        console.log('📡 Добавление обработчиков событий...');
        
        // Обработчики для кнопок
        this.setupButtonHandlers();
        
        // Обработчики для карточек рангов
        this.setupRankCardHandlers();
        
        // Обработчик ошибок
        this.setupErrorHandlers();
        
        // Обработчики для статистики
        this.setupStatsHandlers();
        
        // Обработчики жестов (для мобильных)
        this.setupGestureHandlers();
    }

    /**
     * Настройка обработчиков кнопок
     */
    setupButtonHandlers() {
        const buttons = document.querySelectorAll('.feature-btn, .btn');
        
        buttons.forEach(button => {
            // Визуальная обратная связь при клике
            button.addEventListener('click', function(event) {
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    this.style.transform = '';
                }, 150);
                
                // Тактильная обратная связь
                if (window.telegramWebApp) {
                    window.telegramWebApp.hapticFeedback('medium');
                }
            });
            
            // Эффект наведения
            button.addEventListener('mouseenter', function() {
                if (window.telegramWebApp) {
                    window.telegramWebApp.hapticFeedback('light');
                }
            });
        });
    }

    /**
     * Настройка обработчиков карточек рангов
     */
    setupRankCardHandlers() {
        const rankCards = document.querySelectorAll('.rank-mini');
        
        rankCards.forEach(card => {
            card.addEventListener('click', function() {
                if (window.telegramWebApp) {
                    window.telegramWebApp.hapticFeedback('selection');
                }
                
                // Анимация клика
                this.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    this.style.transform = '';
                }, 150);
            });
        });
    }

    /**
     * Настройка обработчиков ошибок
     */
    setupErrorHandlers() {
        window.addEventListener('error', (event) => {
            console.error('❌ Ошибка WebApp:', event.error);
            this.handleGlobalError(event.error);
        });
        
        window.addEventListener('unhandledrejection', (event) => {
            console.error('❌ Необработанное отклонение промиса:', event.reason);
            this.handleGlobalError(event.reason);
        });
    }

    /**
     * Настройка обработчиков статистики
     */
    setupStatsHandlers() {
        document.addEventListener('stats:updated', (event) => {
            console.log('📊 Статистика обновлена:', event.detail);
            this.updateStatsDisplay(event.detail);
        });
    }

    /**
     * Настройка обработчиков жестов
     */
    setupGestureHandlers() {
        // Обработка свайпов (если понадобится)
        let startY = 0;
        let startX = 0;
        
        document.addEventListener('touchstart', (event) => {
            startY = event.touches[0].clientY;
            startX = event.touches[0].clientX;
        });
        
        document.addEventListener('touchend', (event) => {
            const endY = event.changedTouches[0].clientY;
            const endX = event.changedTouches[0].clientX;
            const diffY = startY - endY;
            const diffX = startX - endX;
            
            // Обработка свайпа вниз для обновления
            if (diffY < -100 && Math.abs(diffX) < 50) {
                console.log('🔄 Свайп вниз - обновление статистики');
                window.loadStats();
                
                if (window.telegramWebApp) {
                    window.telegramWebApp.hapticFeedback('light');
                }
            }
        });
    }

    /**
     * Настройка обработчиков событий Telegram
     */
    setupTelegramEventHandlers() {
        document.addEventListener('webapp:ready', (event) => {
            console.log('✅ WebApp готов:', event.detail);
        });
        
        document.addEventListener('user:updated', (event) => {
            console.log('👤 Пользователь обновлен:', event.detail);
            this.user = event.detail;
        });
    }

    /**
     * Настройка клавиатурных сочетаний
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (event) => {
            // Alt + S - статистика
            if (event.altKey && event.key === 's') {
                event.preventDefault();
                window.sendCommand('/mystat@misterdms_presave_bot');
            }
            
            // Alt + A - запросить поддержку
            if (event.altKey && event.key === 'a') {
                event.preventDefault();
                window.sendCommand('/ask_support@misterdms_presave_bot');
            }
            
            // Alt + R - обновить статистику
            if (event.altKey && event.key === 'r') {
                event.preventDefault();
                window.loadStats();
            }
        });
    }

    /**
     * Запуск системы обновления статистики
     */
    startStatsUpdater() {
        console.log('🔄 Запуск системы обновления статистики...');
        
        // Загружаем статистику сразу
        window.loadStats();
        
        // Обновляем каждые 30 секунд
        setInterval(() => {
            window.loadStats();
        }, 30000);
        
        // Обновляем при фокусе на странице
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                setTimeout(() => window.loadStats(), 1000);
            }
        });
    }

    /**
     * Обновление отображения статистики
     */
    updateStatsDisplay(stats) {
        if (stats.users) {
            window.animateCounter('user-count', stats.users);
        }
        if (stats.support_requests) {
            window.animateCounter('support-count', stats.support_requests);
        }
        if (stats.karma_total) {
            window.animateCounter('karma-count', stats.karma_total);
        }
        
        // Сохраняем статистику
        this.stats = { ...this.stats, ...stats };
    }

    /**
     * Оптимизация производительности
     */
    optimizePerformance() {
        console.log('⚡ Оптимизация производительности...');
        
        // Ленивая загрузка изображений
        if ('loading' in HTMLImageElement.prototype) {
            const images = document.querySelectorAll('img[data-src]');
            images.forEach(img => {
                img.src = img.dataset.src;
            });
        }
        
        // Оптимизация анимаций для слабых устройств
        const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (prefersReducedMotion) {
            document.body.classList.add('reduced-motion');
            console.log('♿ Включен режим сниженной анимации');
        }
        
        // Оптимизация для медленных соединений
        if (navigator.connection && navigator.connection.effectiveType === 'slow-2g') {
            document.body.classList.add('slow-connection');
            console.log('🐌 Обнаружено медленное соединение');
        }
    }

    /**
     * Проверка поддержки функций
     */
    checkFeatureSupport() {
        console.log('🔍 Проверка поддержки функций...');
        
        const support = {
            webp: this.supportsWebP(),
            localStorage: typeof Storage !== 'undefined',
            fetch: typeof fetch !== 'undefined',
            telegram: !!window.Telegram?.WebApp,
            hapticFeedback: !!(window.Telegram?.WebApp?.HapticFeedback),
            notifications: 'Notification' in window
        };
        
        console.log('📋 Поддержка функций:', support);
        
        // Добавляем классы для CSS
        Object.entries(support).forEach(([feature, supported]) => {
            document.body.classList.toggle(`supports-${feature}`, supported);
        });
        
        return support;
    }

    /**
     * Проверка поддержки WebP
     */
    supportsWebP() {
        const canvas = document.createElement('canvas');
        canvas.width = 1;
        canvas.height = 1;
        return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
    }

    /**
     * Показать лоадер
     */
    showLoader() {
        const loader = document.getElementById('loader');
        if (loader) {
            loader.classList.remove('hidden');
        }
    }

    /**
     * Скрыть лоадер
     */
    hideLoader() {
        const loader = document.getElementById('loader');
        if (loader) {
            setTimeout(() => {
                loader.classList.add('hidden');
            }, 1000);
        }
    }

    /**
     * Показать уведомление о режиме браузера
     */
    showBrowserModeNotice() {
        const notice = document.createElement('div');
        notice.className = 'browser-notice';
        notice.innerHTML = `
            <div class="notice-content">
                <div class="notice-icon">🔍</div>
                <div class="notice-title">Режим предпросмотра</div>
                <div class="notice-text">Для полной функциональности откройте в Telegram</div>
                <button onclick="window.open('https://t.me/misterdms_presave_bot', '_blank')" class="notice-btn">
                    Открыть в Telegram
                </button>
            </div>
        `;
        
        // Добавляем стили
        const style = document.createElement('style');
        style.textContent = `
            .browser-notice {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 16px;
                padding: 20px;
                color: white;
                z-index: 1000;
                max-width: 320px;
                text-align: center;
                animation: slideUp 0.3s ease-out reverse;
                box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            }
            .notice-content {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 12px;
            }
            .notice-icon {
                font-size: 32px;
            }
            .notice-title {
                font-weight: 600;
                font-size: 16px;
            }
            .notice-text {
                font-size: 14px;
                opacity: 0.9;
                line-height: 1.4;
            }
            .notice-btn {
                background: linear-gradient(45deg, #4CAF50, #45a049);
                border: none;
                border-radius: 12px;
                color: white;
                padding: 10px 20px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            .notice-btn:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            }
        `;
        
        document.head.appendChild(style);
        document.body.appendChild(notice);
        
        // Автоматически скрываем через 15 секунд
        setTimeout(() => {
            if (notice.parentNode) {
                notice.style.animation = 'slideUp 0.3s ease-in forwards';
                setTimeout(() => {
                    if (notice.parentNode) {
                        notice.parentNode.removeChild(notice);
                        document.head.removeChild(style);
                    }
                }, 300);
            }
        }, 15000);
    }

    /**
     * Обработка глобальных ошибок
     */
    handleGlobalError(error) {
        console.error('🚨 Глобальная ошибка:', error);
        
        // Не показываем уведомления для некритичных ошибок
        if (error.name === 'NetworkError' || error.message.includes('fetch')) {
            return;
        }
        
        window.showNotification('Произошла ошибка. Попробуйте обновить страницу.', 'error');
    }

    /**
     * Обработка ошибки инициализации
     */
    handleInitializationError(error) {
        console.error('🚨 Ошибка инициализации:', error);
        
        this.hideLoader();
        
        const errorMessage = document.createElement('div');
        errorMessage.className = 'error-message';
        errorMessage.innerHTML = `
            <div class="error-content">
                <div class="error-icon">⚠️</div>
                <div class="error-title">Ошибка загрузки</div>
                <div class="error-text">Попробуйте обновить страницу или открыть WebApp позже</div>
                <button onclick="window.location.reload()" class="error-btn">
                    Обновить страницу
                </button>
            </div>
        `;
        
        document.body.appendChild(errorMessage);
    }

    /**
     * Получение информации о WebApp
     */
    getAppInfo() {
        return {
            isInitialized: this.isInitialized,
            user: this.user,
            stats: this.stats,
            isTelegram: window.telegramWebApp?.isTelegram() || false,
            version: '1.0.0'
        };
    }
}

// Инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎵 Загрузка Do Presave Reminder Bot WebApp...');
    
    // Создаем экземпляр приложения
    window.presaveApp = new PresaveWebApp();
});

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PresaveWebApp;
}