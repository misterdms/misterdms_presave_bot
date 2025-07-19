/**
 * Обработка команд и взаимодействие с ботом
 * Do Presave Reminder Bot by Mister DMS
 */

// Константы команд бота
const BotCommands = {
    // Основные команды пользователей
    START: '/start@misterdms_presave_bot',
    MENU: '/menu@misterdms_presave_bot',
    HELP: '/help@misterdms_presave_bot',
    MYSTAT: '/mystat@misterdms_presave_bot',
    LEADERBOARD: '/leaderboard@misterdms_presave_bot',
    NAVIGATION: '/navigation@misterdms_presave_bot',
    DONATE: '/donate@misterdms_presave_bot',
    
    // Команды поддержки треков
    ASK_SUPPORT: '/ask_support@misterdms_presave_bot',
    CLAIM_SUPPORT: '/claim_support@misterdms_presave_bot',
    LAST_10_LINKS: '/last10links@misterdms_presave_bot',
    MY_SUPPORT_REQUESTS: '/my_support_requests@misterdms_presave_bot',
    PRESAVE_REQUESTS: '/presave_requests@misterdms_presave_bot',
    BOOST_REQUESTS: '/boost_requests@misterdms_presave_bot',
    SUPPORT_STATS: '/support_stats@misterdms_presave_bot',
    MY_APPLICATIONS: '/my_applications@misterdms_presave_bot',
    
    // ИИ и события
    AI_SETTINGS: '/ai_settings@misterdms_presave_bot',
    CALENDAR: '/calendar@misterdms_presave_bot',
    PROFILE: '/profile@misterdms_presave_bot',
    
    // Админские команды (если пользователь админ)
    KARMA: '/karma@misterdms_presave_bot',
    KARMA_RATIO: '/karma_ratio@misterdms_presave_bot',
    APPROVAL_QUEUE: '/approval_queue@misterdms_presave_bot',
    PRESAVE_QUEUE: '/presave_queue@misterdms_presave_bot',
    BOOST_QUEUE: '/boost_queue@misterdms_presave_bot',
    SETTINGS: '/settings@misterdms_presave_bot'
};

// Описания команд для пользователя
const CommandDescriptions = {
    [BotCommands.ASK_SUPPORT]: 'Создать запрос на поддержку трека (пресейв или буст)',
    [BotCommands.CLAIM_SUPPORT]: 'Отчитаться о поддержке других треков',
    [BotCommands.MYSTAT]: 'Посмотреть свою карму и статистику',
    [BotCommands.LAST_10_LINKS]: 'Последние 5+5 запросов поддержки',
    [BotCommands.HELP]: 'Полный список команд с примерами',
    [BotCommands.AI_SETTINGS]: 'Настроить ИИ сервисы для сообщества'
};

/**
 * Функция для отправки команд боту
 */
function sendCommand(command, data = {}) {
    console.log('📤 Отправка команды:', command);
    
    if (!window.telegramWebApp) {
        console.error('❌ TelegramWebApp не инициализирован');
        showFallbackMessage(command);
        return Promise.reject('TelegramWebApp not initialized');
    }

    // Добавляем описание команды в уведомление
    const description = CommandDescriptions[command];
    if (description) {
        console.log('ℹ️ Описание команды:', description);
    }

    return window.telegramWebApp.sendCommand(command, data)
        .then(() => {
            console.log('✅ Команда отправлена успешно');
            
            // Логируем статистику использования
            logCommandUsage(command);
            
            // Добавляем визуальную обратную связь
            addVisualFeedback(command);
        })
        .catch((error) => {
            console.error('❌ Ошибка отправки команды:', error);
            showFallbackMessage(command);
        });
}

/**
 * Открыть бота
 */
function openBot() {
    console.log('🤖 Открытие бота...');
    
    if (window.telegramWebApp) {
        window.telegramWebApp.openBot();
    } else {
        window.open('https://t.me/misterdms_presave_bot', '_blank');
    }
    
    // Логируем действие
    logAction('open_bot');
}

/**
 * Задать вопрос ИИ
 */
function askAI() {
    console.log('🤖 Запуск диалога с ИИ...');
    
    if (window.telegramWebApp && window.telegramWebApp.isTelegram()) {
        // В Telegram показываем инструкцию
        window.telegramWebApp.showNotification(
            'Упомяните @misterdms_presave_bot в группе с вопросом!', 
            'info'
        );
        
        // Закрываем WebApp
        setTimeout(() => {
            window.telegramWebApp.close();
        }, 2000);
    } else {
        // В браузере открываем бота
        openBot();
    }
}

/**
 * Показать информацию о ранге
 */
function showRankInfo(rankElement) {
    const rank = rankElement.dataset.rank;
    const karma = rankElement.dataset.karma;
    
    const message = `🏆 ${rank}\n💎 Карма: ${karma}\n\nПомогайте другим музыкантам, чтобы повысить свой ранг!`;
    
    if (window.telegramWebApp) {
        window.telegramWebApp.showNotification(message, 'info');
        window.telegramWebApp.hapticFeedback('selection');
    } else {
        alert(message);
    }
    
    // Добавляем анимацию
    rankElement.classList.add('success-animation');
    setTimeout(() => {
        rankElement.classList.remove('success-animation');
    }, 1000);
}

/**
 * Анимация счетчиков
 */
function animateCounter(elementId, targetValue, duration = 1500) {
    const element = document.getElementById(elementId);
    if (!element) {
        console.warn('⚠️ Элемент не найден:', elementId);
        return;
    }

    const startValue = parseInt(element.textContent.replace(/\D/g, '')) || 0;
    const increment = (targetValue - startValue) / (duration / 16);
    let currentValue = startValue;
    
    // Добавляем класс анимации
    element.classList.add('animate');
    
    const timer = setInterval(() => {
        currentValue += increment;
        if ((increment > 0 && currentValue >= targetValue) || 
            (increment < 0 && currentValue <= targetValue)) {
            currentValue = targetValue;
            clearInterval(timer);
            
            // Убираем класс анимации
            element.classList.remove('animate');
        }
        
        // Форматируем число с разделителями
        element.textContent = Math.round(currentValue).toLocaleString('ru-RU');
    }, 16);
    
    console.log(`📊 Анимация счетчика ${elementId}: ${startValue} → ${targetValue}`);
}

/**
 * Показать уведомление (fallback)
 */
function showNotification(message, type = 'info') {
    if (window.telegramWebApp) {
        window.telegramWebApp.showNotification(message, type);
    } else {
        // Создаем уведомление для браузера
        createBrowserNotification(message, type);
    }
}

/**
 * Создание уведомления для браузера
 */
function createBrowserNotification(message, type = 'info') {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    
    container.appendChild(notification);
    
    // Автоматическое удаление
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
 * Создание контейнера для уведомлений
 */
function createNotificationContainer() {
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        document.body.appendChild(container);
    }
    return container;
}

/**
 * Загрузка статистики
 */
function loadStats() {
    console.log('📊 Загрузка статистики...');
    
    if (window.telegramWebApp && window.telegramWebApp.isReady) {
        return window.telegramWebApp.requestStats()
            .catch(() => {
                // Если не удалось получить от бота, используем демонстрационные данные
                loadDemoStats();
            });
    } else {
        // Загружаем демонстрационные данные
        loadDemoStats();
        return Promise.resolve();
    }
}

/**
 * Загрузка демонстрационных данных
 */
function loadDemoStats() {
    console.log('📊 Загрузка демонстрационных данных...');
    
    // Генерируем случайные, но реалистичные данные
    const baseUsers = 247;
    const baseSupport = 1842;
    const baseKarma = 3156;
    
    const users = baseUsers + Math.floor(Math.random() * 20);
    const support = baseSupport + Math.floor(Math.random() * 100);
    const karma = baseKarma + Math.floor(Math.random() * 200);
    
    setTimeout(() => {
        animateCounter('user-count', users);
        setTimeout(() => animateCounter('support-count', support), 200);
        setTimeout(() => animateCounter('karma-count', karma), 400);
    }, 500);
}

/**
 * Запуск обновления статистики
 */
function startStatsUpdater() {
    console.log('🔄 Запуск системы обновления статистики...');
    
    // Загружаем статистику сразу
    loadStats();
    
    // Обновляем каждые 30 секунд
    setInterval(() => {
        loadStats();
    }, 30000);
    
    // Обновляем при фокусе на странице
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            setTimeout(loadStats, 1000);
        }
    });
}

/**
 * Fallback сообщение при ошибке отправки команды
 */
function showFallbackMessage(command) {
    const message = `Команда: ${command}\n\nОткройте бота в Telegram для выполнения команды`;
    
    if (window.telegramWebApp) {
        window.telegramWebApp.showNotification(
            'Откройте бота для выполнения команды', 
            'info'
        );
    } else {
        showNotification('Откройте в Telegram: t.me/misterdms_presave_bot', 'info');
    }
    
    setTimeout(() => {
        openBot();
    }, 1500);
}

/**
 * Логирование использования команд
 */
function logCommandUsage(command) {
    try {
        const usage = JSON.parse(localStorage.getItem('command_usage') || '{}');
        usage[command] = (usage[command] || 0) + 1;
        localStorage.setItem('command_usage', JSON.stringify(usage));
    } catch (error) {
        // Игнорируем ошибки localStorage
    }
}

/**
 * Логирование действий пользователя
 */
function logAction(action) {
    try {
        const actions = JSON.parse(localStorage.getItem('user_actions') || '[]');
        actions.push({
            action: action,
            timestamp: Date.now(),
            url: window.location.href
        });
        
        // Оставляем только последние 50 действий
        if (actions.length > 50) {
            actions.splice(0, actions.length - 50);
        }
        
        localStorage.setItem('user_actions', JSON.stringify(actions));
    } catch (error) {
        // Игнорируем ошибки localStorage
    }
}

/**
 * Добавление визуальной обратной связи
 */
function addVisualFeedback(command) {
    // Находим кнопку, которая отправила команду
    const buttons = document.querySelectorAll(`[onclick*="${command}"]`);
    
    buttons.forEach(button => {
        button.classList.add('success-animation');
        setTimeout(() => {
            button.classList.remove('success-animation');
        }, 1000);
    });
}

/**
 * Получение статистики использования
 */
function getUsageStats() {
    try {
        return {
            commands: JSON.parse(localStorage.getItem('command_usage') || '{}'),
            actions: JSON.parse(localStorage.getItem('user_actions') || '[]')
        };
    } catch (error) {
        return { commands: {}, actions: [] };
    }
}

/**
 * Инициализация обработчиков команд
 */
function initializeCommandHandlers() {
    console.log('⚙️ Инициализация обработчиков команд...');
    
    // Добавляем глобальные обработчики
    document.addEventListener('command:sent', (event) => {
        console.log('📤 Команда отправлена:', event.detail);
    });
    
    document.addEventListener('stats:updated', (event) => {
        console.log('📊 Статистика обновлена:', event.detail);
    });
    
    // Обработка сочетаний клавиш
    document.addEventListener('keydown', (event) => {
        // Ctrl/Cmd + H - помощь
        if ((event.ctrlKey || event.metaKey) && event.key === 'h') {
            event.preventDefault();
            sendCommand(BotCommands.HELP);
        }
        
        // Ctrl/Cmd + M - меню
        if ((event.ctrlKey || event.metaKey) && event.key === 'm') {
            event.preventDefault();
            sendCommand(BotCommands.MENU);
        }
        
        // Escape - закрыть WebApp
        if (event.key === 'Escape') {
            if (window.telegramWebApp) {
                window.telegramWebApp.close();
            }
        }
    });
}

/**
 * Проверка доступности команд для пользователя
 */
function checkCommandAvailability(command) {
    // Админские команды требуют особых прав
    const adminCommands = [
        BotCommands.KARMA,
        BotCommands.KARMA_RATIO,
        BotCommands.APPROVAL_QUEUE,
        BotCommands.SETTINGS
    ];
    
    if (adminCommands.includes(command)) {
        // Здесь можно добавить проверку прав пользователя
        console.log('⚠️ Команда требует права администратора:', command);
    }
    
    return true;
}

/**
 * Форматирование команды для отображения
 */
function formatCommand(command) {
    return command.replace('@misterdms_presave_bot', '').replace('/', '');
}

/**
 * Получение списка доступных команд
 */
function getAvailableCommands() {
    return Object.entries(BotCommands).map(([key, command]) => ({
        key: key,
        command: command,
        formatted: formatCommand(command),
        description: CommandDescriptions[command] || 'Описание недоступно'
    }));
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    initializeCommandHandlers();
});

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { 
        BotCommands, 
        sendCommand, 
        openBot, 
        loadStats, 
        animateCounter,
        showNotification,
        askAI,
        showRankInfo
    };
}

// Глобальные функции для использования в HTML
window.sendCommand = sendCommand;
window.openBot = openBot;
window.loadStats = loadStats;
window.animateCounter = animateCounter;
window.showNotification = showNotification;
window.askAI = askAI;
window.showRankInfo = showRankInfo;