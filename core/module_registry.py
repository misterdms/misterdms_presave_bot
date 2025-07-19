"""
Core/module_registry.py - Реестр и загрузчик модулей
Do Presave Reminder Bot v29.07

Управление загрузкой, регистрацией и жизненным циклом модулей
"""

import asyncio
import importlib
import inspect
import traceback
import time
from typing import Dict, List, Optional, Type, Any
from pathlib import Path

from core.interfaces import BaseModule, ModuleStatus, ModuleInfo, ModulePriorities, EventTypes
from core.exceptions import ModuleLoadError, ModuleNotFoundError, ModuleDependencyError
from utils.logger import get_logger, log_module_activity, LogExecutionTime


class ModuleRegistry:
    """Реестр модулей с автоматической загрузкой и управлением жизненным циклом"""
    
    def __init__(self, bot, database, event_dispatcher, settings):
        """
        Инициализация реестра модулей
        
        Args:
            bot: Экземпляр Telegram бота
            database: Ядро базы данных
            event_dispatcher: Диспетчер событий
            settings: Настройки системы
        """
        self.bot = bot
        self.database = database
        self.event_dispatcher = event_dispatcher
        self.settings = settings
        self.logger = get_logger(__name__)
        
        # Хранилища модулей
        self.modules: Dict[str, BaseModule] = {}
        self.module_classes: Dict[str, Type[BaseModule]] = {}
        self.load_order: List[str] = []
        self.dependency_graph: Dict[str, List[str]] = {}
        
        # Статистика
        self.load_stats = {
            'total_modules': 0,
            'loaded_modules': 0,
            'running_modules': 0,
            'failed_modules': 0,
            'load_time': 0
        }
        
        # Состояние
        self.is_loading = False
        self.is_starting = False
        
    async def register_module(self, module_name: str, module_instance: BaseModule, priority: int = ModulePriorities.NORMAL) -> bool:
        """
        Регистрация экземпляра модуля
        
        Args:
            module_name: Имя модуля
            module_instance: Экземпляр модуля
            priority: Приоритет загрузки
            
        Returns:
            bool: Успешность регистрации
        """
        try:
            self.logger.info(f"📦 Регистрация модуля: {module_name}")
            
            # Проверяем, что модуль не зарегистрирован
            if module_name in self.modules:
                self.logger.warning(f"⚠️ Модуль {module_name} уже зарегистрирован")
                return True
            
            # Проверяем интерфейс
            if not isinstance(module_instance, BaseModule):
                raise ModuleLoadError(f"Модуль {module_name} не наследует BaseModule")
            
            # Получаем информацию о модуле
            module_info = module_instance.get_info()
            
            # Проверяем план разработки
            if not self._is_plan_enabled(module_info.plan):
                self.logger.info(f"⏭️ Модуль {module_name} отключен (план {module_info.plan} неактивен)")
                return True
            
            # Проверяем, включен ли модуль в настройках
            if not self.settings.is_module_enabled(module_name):
                self.logger.info(f"⏸️ Модуль {module_name} отключен в настройках")
                return True
            
            # Сохраняем модуль
            self.modules[module_name] = module_instance
            self.module_classes[module_name] = type(module_instance)
            
            # Добавляем в граф зависимостей
            self.dependency_graph[module_name] = module_info.dependencies
            
            # Вычисляем порядок загрузки
            self._update_load_order()
            
            module_instance.status = ModuleStatus.LOADED
            self.load_stats['loaded_modules'] += 1
            
            # Генерируем событие
            await self.event_dispatcher.emit(EventTypes.MODULE_LOADED, {
                'module_name': module_name,
                'module_info': module_info.__dict__,
                'priority': priority
            })
            
            log_module_activity(module_name, "registered", {
                'priority': priority,
                'dependencies': module_info.dependencies
            })
            
            self.logger.info(f"✅ Модуль {module_name} зарегистрирован")
            return True
            
        except Exception as e:
            self.load_stats['failed_modules'] += 1
            self.logger.error(f"❌ Ошибка регистрации модуля {module_name}: {e}")
            raise ModuleLoadError(f"Не удалось зарегистрировать модуль {module_name}: {e}")
    
    async def load_module_from_path(self, module_path: str, module_name: str = None) -> bool:
        """
        Загрузка модуля из файловой системы
        
        Args:
            module_path: Путь к модулю (modules.user_management.module)
            module_name: Имя модуля (опционально, извлекается из пути)
            
        Returns:
            bool: Успешность загрузки
        """
        try:
            if module_name is None:
                module_name = module_path.split('.')[-2]  # modules.user_management.module -> user_management
            
            with LogExecutionTime(f"Loading module {module_name}"):
                # Импортируем модуль
                module = importlib.import_module(module_path)
                
                # Ищем класс модуля
                module_class = None
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BaseModule) and 
                        obj != BaseModule and 
                        name.endswith('Module')):
                        module_class = obj
                        break
                
                if not module_class:
                    raise ModuleLoadError(f"Не найден класс модуля в {module_path}")
                
                # Создаем экземпляр
                module_instance = module_class(
                    bot=self.bot,
                    database=self.database,
                    config=self.settings.get_module_config(module_name),
                    event_dispatcher=self.event_dispatcher
                )
                
                # Регистрируем модуль
                module_info = module_instance.get_info()
                await self.register_module(module_name, module_instance, module_info.priority)
                
                return True
                
        except ImportError as e:
            self.logger.error(f"❌ Не удалось импортировать модуль {module_path}: {e}")
            raise ModuleNotFoundError(f"Модуль {module_path} не найден")
        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки модуля {module_path}: {e}")
            raise ModuleLoadError(f"Не удалось загрузить модуль {module_path}: {e}")
    
    async def load_all_modules(self) -> bool:
        """Загрузка всех модулей согласно планам разработки"""
        if self.is_loading:
            self.logger.warning("⚠️ Загрузка модулей уже выполняется")
            return False
        
        try:
            self.is_loading = True
            load_start_time = time.time()
            
            self.logger.info("🚀 Начинаем загрузку модулей...")
            
            # Модули по планам
            modules_to_load = []
            
            # ПЛАН 1 - базовый функционал (всегда загружается)
            plan1_modules = [
                ('modules.user_management.module', 'user_management'),
                ('modules.track_support_system.module', 'track_support_system'),
                ('modules.karma_system.module', 'karma_system'),
                ('modules.navigation_system.module', 'navigation_system'),
                ('modules.module_settings.module', 'module_settings')
            ]
            modules_to_load.extend(plan1_modules)
            
            # ПЛАН 2 - интерактивные формы
            if self.settings.plan2_enabled:
                plan2_modules = [
                    ('modules.interactive_forms.module', 'interactive_forms'),
                    ('modules.leaderboards.module', 'leaderboards')
                ]
                modules_to_load.extend(plan2_modules)
            
            # ПЛАН 3 - модерация и backup
            if self.settings.plan3_enabled:
                plan3_modules = [
                    ('modules.approval_system.module', 'approval_system'),
                    ('modules.database_management.module', 'database_management')
                ]
                modules_to_load.extend(plan3_modules)
            
            # ПЛАН 4 - ИИ и расширения
            if self.settings.plan4_enabled:
                plan4_modules = [
                    ('modules.ai_assistant.module', 'ai_assistant'),
                    ('modules.ai_settings.module', 'ai_settings'),
                    ('modules.calendar_system.module', 'calendar_system'),
                    ('modules.canva_integration.module', 'canva_integration')
                ]
                modules_to_load.extend(plan4_modules)
            
            # Загружаем модули
            self.load_stats['total_modules'] = len(modules_to_load)
            
            for module_path, module_name in modules_to_load:
                try:
                    await self.load_module_from_path(module_path, module_name)
                except (ModuleNotFoundError, ImportError):
                    # Модуль еще не создан - это нормально
                    self.logger.info(f"⏭️ Модуль {module_name} пропущен (не создан)")
                except Exception as e:
                    self.logger.error(f"❌ Критическая ошибка загрузки {module_name}: {e}")
                    self.load_stats['failed_modules'] += 1
            
            # Инициализация всех загруженных модулей
            await self._initialize_all_modules()
            
            self.load_stats['load_time'] = time.time() - load_start_time
            
            self.logger.info(f"✅ Загрузка модулей завершена за {self.load_stats['load_time']:.2f}s")
            self.logger.info(f"📊 Загружено: {self.load_stats['loaded_modules']}/{self.load_stats['total_modules']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Критическая ошибка загрузки модулей: {e}")
            return False
        finally:
            self.is_loading = False
    
    async def _initialize_all_modules(self):
        """Инициализация всех загруженных модулей в правильном порядке"""
        self.logger.info("🔧 Инициализация модулей...")
        
        for module_name in self.load_order:
            if module_name not in self.modules:
                continue
            
            module = self.modules[module_name]
            try:
                self.logger.info(f"🔧 Инициализация модуля: {module_name}")
                module.status = ModuleStatus.LOADING
                
                success = await module.initialize()
                if success:
                    module.status = ModuleStatus.LOADED
                    log_module_activity(module_name, "initialized")
                else:
                    module.status = ModuleStatus.ERROR
                    self.logger.error(f"❌ Модуль {module_name} не инициализировался")
                    
            except Exception as e:
                module.status = ModuleStatus.ERROR
                self.load_stats['failed_modules'] += 1
                self.logger.error(f"❌ Ошибка инициализации модуля {module_name}: {e}")
                self.logger.error(traceback.format_exc())
    
    async def start_all_modules(self) -> bool:
        """Запуск всех инициализированных модулей"""
        if self.is_starting:
            self.logger.warning("⚠️ Запуск модулей уже выполняется")
            return False
        
        try:
            self.is_starting = True
            self.logger.info("🚀 Запуск модулей...")
            
            for module_name in self.load_order:
                if module_name not in self.modules:
                    continue
                
                module = self.modules[module_name]
                if module.status != ModuleStatus.LOADED:
                    continue
                
                try:
                    self.logger.info(f"▶️ Запуск модуля: {module_name}")
                    module.status = ModuleStatus.STARTING
                    
                    # Регистрируем обработчики
                    module.register_handlers()
                    
                    # Запускаем модуль
                    success = await module.start()
                    if success:
                        module.status = ModuleStatus.RUNNING
                        self.load_stats['running_modules'] += 1
                        
                        # Генерируем событие
                        await self.event_dispatcher.emit(EventTypes.MODULE_STARTED, {
                            'module_name': module_name
                        })
                        
                        log_module_activity(module_name, "started")
                    else:
                        module.status = ModuleStatus.ERROR
                        self.logger.error(f"❌ Модуль {module_name} не запустился")
                        
                except Exception as e:
                    module.status = ModuleStatus.ERROR
                    self.logger.error(f"❌ Ошибка запуска модуля {module_name}: {e}")
                    
                    # Генерируем событие об ошибке
                    await self.event_dispatcher.emit(EventTypes.MODULE_ERROR, {
                        'module_name': module_name,
                        'error': str(e)
                    })
            
            self.logger.info(f"✅ Запущено модулей: {self.load_stats['running_modules']}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Критическая ошибка запуска модулей: {e}")
            return False
        finally:
            self.is_starting = False
    
    async def stop_all_modules(self):
        """Остановка всех модулей"""
        self.logger.info("🔄 Остановка модулей...")
        
        # Останавливаем в обратном порядке
        for module_name in reversed(self.load_order):
            if module_name not in self.modules:
                continue
            
            module = self.modules[module_name]
            if module.status != ModuleStatus.RUNNING:
                continue
            
            try:
                self.logger.info(f"⏹️ Остановка модуля: {module_name}")
                module.status = ModuleStatus.STOPPING
                
                await module.stop()
                await module.cleanup()
                
                module.status = ModuleStatus.STOPPED
                self.load_stats['running_modules'] -= 1
                
                # Генерируем событие
                await self.event_dispatcher.emit(EventTypes.MODULE_STOPPED, {
                    'module_name': module_name
                })
                
                log_module_activity(module_name, "stopped")
                
            except Exception as e:
                self.logger.error(f"❌ Ошибка остановки модуля {module_name}: {e}")
    
    def get_module(self, module_name: str) -> Optional[BaseModule]:
        """Получение экземпляра модуля по имени"""
        return self.modules.get(module_name)
    
    def is_module_running(self, module_name: str) -> bool:
        """Проверка, запущен ли модуль"""
        module = self.get_module(module_name)
        return module is not None and module.status == ModuleStatus.RUNNING
    
    def get_module_status(self, module_name: str) -> Optional[ModuleStatus]:
        """Получение статуса модуля"""
        module = self.get_module(module_name)
        return module.status if module else None
    
    def get_running_modules(self) -> List[str]:
        """Получение списка запущенных модулей"""
        return [
            name for name, module in self.modules.items()
            if module.status == ModuleStatus.RUNNING
        ]
    
    def get_all_commands(self) -> Dict[str, str]:
        """Получение всех команд от всех модулей"""
        all_commands = {}
        for module_name, module in self.modules.items():
            if module.status == ModuleStatus.RUNNING:
                commands = module.get_commands()
                for command in commands:
                    all_commands[command] = module_name
        return all_commands
    
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья всех модулей"""
        health_data = {
            "healthy": True,
            "modules_count": len(self.modules),
            "running_modules": self.load_stats['running_modules'],
            "failed_modules": self.load_stats['failed_modules'],
            "load_time": self.load_stats['load_time'],
            "modules": {}
        }
        
        for module_name, module in self.modules.items():
            try:
                module_health = await module.health_check()
                health_data["modules"][module_name] = module_health
                
                if not module_health.get("healthy", False):
                    health_data["healthy"] = False
                    
            except Exception as e:
                health_data["modules"][module_name] = {
                    "healthy": False,
                    "error": str(e)
                }
                health_data["healthy"] = False
        
        return health_data
    
    def _is_plan_enabled(self, plan: int) -> bool:
        """Проверка, включен ли план разработки"""
        if plan == 1:
            return True  # План 1 всегда включен
        elif plan == 2:
            return self.settings.plan2_enabled
        elif plan == 3:
            return self.settings.plan3_enabled
        elif plan == 4:
            return self.settings.plan4_enabled
        else:
            return False
    
    def _check_dependencies(self, dependencies: List[str]) -> bool:
        """Проверка выполнения зависимостей модуля"""
        for dependency in dependencies:
            if dependency not in self.modules:
                self.logger.error(f"❌ Зависимость {dependency} не найдена")
                return False
            
            dep_module = self.modules[dependency]
            if dep_module.status not in [ModuleStatus.LOADED, ModuleStatus.RUNNING]:
                self.logger.error(f"❌ Зависимость {dependency} не готова")
                return False
        
        return True
    
    def _update_load_order(self):
        """Обновление порядка загрузки модулей с учетом зависимостей"""
        # Топологическая сортировка для разрешения зависимостей
        visited = set()
        temp_visited = set()
        load_order = []
        
        def visit(module_name):
            if module_name in temp_visited:
                raise ModuleDependencyError(f"Циклическая зависимость обнаружена: {module_name}")
            
            if module_name not in visited:
                temp_visited.add(module_name)
                
                # Посещаем зависимости
                dependencies = self.dependency_graph.get(module_name, [])
                for dependency in dependencies:
                    if dependency in self.dependency_graph:
                        visit(dependency)
                
                temp_visited.remove(module_name)
                visited.add(module_name)
                load_order.append(module_name)
        
        # Обходим все модули
        for module_name in self.dependency_graph:
            if module_name not in visited:
                visit(module_name)
        
        self.load_order = load_order
        self.logger.debug(f"📋 Порядок загрузки модулей: {self.load_order}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики реестра модулей"""
        return {
            "load_stats": self.load_stats.copy(),
            "modules_count": len(self.modules),
            "running_modules": [name for name, module in self.modules.items() 
                              if module.status == ModuleStatus.RUNNING],
            "failed_modules": [name for name, module in self.modules.items() 
                             if module.status == ModuleStatus.ERROR],
            "load_order": self.load_order.copy(),
            "dependency_graph": self.dependency_graph.copy()
        }