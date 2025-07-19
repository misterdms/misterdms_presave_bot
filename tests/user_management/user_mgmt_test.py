"""
Tests/test_user_management.py - Тесты модуля управления пользователями
Do Presave Reminder Bot v29.07

Модульные тесты для МОДУЛЯ 1: user_management
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any

# Импорты модуля
from modules.user_management import (
    UserManagementModule,
    UserManagementConfig,
    UserService,
    MusicUser,
    KarmaHistory,
    UserDataValidator,
    KarmaValidator,
    OnboardingValidator,
    sanitize_username,
    sanitize_name,
    sanitize_genre
)


class TestUserDataValidator:
    """Тесты валидатора данных пользователей"""
    
    def test_validate_user_creation_data_valid(self):
        """Тест валидации корректных данных пользователя"""
        data = {
            'user_id': 12345,
            'group_id': -1001234567890,
            'username': 'test_user',
            'first_name': 'Тест',
            'last_name': 'Пользователь',
            'music_genre': 'Рок'
        }
        
        is_valid, errors = UserDataValidator.validate_user_creation_data(data)
        assert is_valid == True
        assert len(errors) == 0
    
    def test_validate_user_creation_data_missing_required(self):
        """Тест валидации с пропущенными обязательными полями"""
        data = {
            'username': 'test_user'
        }
        
        is_valid, errors = UserDataValidator.validate_user_creation_data(data)
        assert is_valid == False
        assert 'user_id' in str(errors)
        assert 'group_id' in str(errors)
    
    def test_validate_user_creation_data_invalid_username(self):
        """Тест валидации некорректного username"""
        data = {
            'user_id': 12345,
            'group_id': -1001234567890,
            'username': 'invalid-user@name!'
        }
        
        is_valid, errors = UserDataValidator.validate_user_creation_data(data)
        assert is_valid == False
        assert any('Username' in error for error in errors)
    
    def test_validate_karma_change_valid(self):
        """Тест валидации корректного изменения кармы"""
        is_valid, error = UserDataValidator.validate_karma_change(
            karma_change=5,
            current_karma=10,
            min_karma=0,
            max_karma=100500
        )
        assert is_valid == True
        assert error is None
    
    def test_validate_karma_change_exceeds_max(self):
        """Тест валидации изменения кармы, превышающего максимум"""
        is_valid, error = UserDataValidator.validate_karma_change(
            karma_change=100,
            current_karma=100450,
            min_karma=0,
            max_karma=100500
        )
        assert is_valid == False
        assert "превышать" in error
    
    def test_validate_karma_ratio_format_valid(self):
        """Тест валидации корректного формата соотношения"""
        is_valid, ratio, error = UserDataValidator.validate_karma_ratio_format("15:3")
        assert is_valid == True
        assert ratio == (15, 3)
        assert error is None
    
    def test_validate_karma_ratio_format_invalid(self):
        """Тест валидации некорректного формата соотношения"""
        is_valid, ratio, error = UserDataValidator.validate_karma_ratio_format("invalid")
        assert is_valid == False
        assert ratio is None
        assert "формат" in error


class TestKarmaValidator:
    """Тесты валидатора операций с кармой"""
    
    def test_validate_karma_operation_valid_gratitude(self):
        """Тест валидации корректной операции благодарности"""
        is_valid, error = KarmaValidator.validate_karma_operation(
            user_id=12345,
            karma_change=1,
            change_type='gratitude',
            current_karma=10,
            reason='Помощь новичку'
        )
        assert is_valid == True
        assert error is None
    
    def test_validate_karma_operation_invalid_change_type(self):
        """Тест валидации некорректного типа изменения"""
        is_valid, error = KarmaValidator.validate_karma_operation(
            user_id=12345,
            karma_change=5,
            change_type='invalid_type',
            current_karma=10,
            reason='Тест'
        )
        assert is_valid == False
        assert "Недопустимый тип" in error
    
    def test_validate_karma_operation_invalid_reason_length(self):
        """Тест валидации слишком короткой причины"""
        is_valid, error = KarmaValidator.validate_karma_operation(
            user_id=12345,
            karma_change=1,
            change_type='gratitude',
            current_karma=10,
            reason='OK'  # Слишком короткая
        )
        assert is_valid == False
        assert "минимум 3 символа" in error


class TestOnboardingValidator:
    """Тесты валидатора онбординга"""
    
    def test_validate_onboarding_data_valid(self):
        """Тест валидации корректных данных онбординга"""
        data = {
            'user_id': 12345,
            'group_id': -1001234567890,
            'music_genre': 'Рок',
            'first_name': 'Тест'
        }
        
        is_valid, errors = OnboardingValidator.validate_onboarding_data(data)
        assert is_valid == True
        assert len(errors) == 0
    
    def test_validate_onboarding_data_invalid_genre(self):
        """Тест валидации некорректного жанра"""
        data = {
            'user_id': 12345,
            'group_id': -1001234567890,
            'music_genre': 'НесуществующийЖанр',
            'first_name': 'Тест'
        }
        
        is_valid, errors = OnboardingValidator.validate_onboarding_data(data)
        assert is_valid == False
        assert any('жанр' in error.lower() for error in errors)
    
    def test_validate_onboarding_step_valid(self):
        """Тест валидации корректного шага онбординга"""
        is_valid, error = OnboardingValidator.validate_onboarding_step(2, 3)
        assert is_valid == True
        assert error is None
    
    def test_validate_onboarding_step_invalid(self):
        """Тест валидации некорректного шага онбординга"""
        is_valid, error = OnboardingValidator.validate_onboarding_step(5, 3)
        assert is_valid == False
        assert "от 1 до 3" in error


class TestSanitizers:
    """Тесты функций очистки данных"""
    
    def test_sanitize_username(self):
        """Тест очистки username"""
        assert sanitize_username('@test_user') == 'test_user'
        assert sanitize_username('user@with!special#chars') == 'userwithspecialchars'
        assert sanitize_username('') == ''
    
    def test_sanitize_name(self):
        """Тест очистки имени"""
        assert sanitize_name('  Тест  ') == 'Тест'
        assert sanitize_name('') == ''
        long_name = 'А' * 150  # Длиннее максимума
        assert len(sanitize_name(long_name)) <= 100
    
    def test_sanitize_genre(self):
        """Тест очистки жанра"""
        assert sanitize_genre('рок') == 'Рок'
        assert sanitize_genre('hip-hop') == 'Хип-хоп'
        assert sanitize_genre('неизвестный жанр') == 'Другое'
        assert sanitize_genre('') == ''


class TestUserManagementConfig:
    """Тесты конфигурации модуля"""
    
    def test_config_initialization(self):
        """Тест инициализации конфигурации"""
        config = UserManagementConfig()
        assert config.enabled == True
        assert config.karma.min_karma == 0
        assert config.karma.max_karma == 100500
        assert config.karma.admin_karma == 100500
    
    def test_config_validation_valid(self):
        """Тест валидации корректной конфигурации"""
        config = UserManagementConfig()
        is_valid, errors = config.validate_config()
        assert is_valid == True
        assert len(errors) == 0
    
    def test_get_rank_by_karma(self):
        """Тест получения звания по карме"""
        config = UserManagementConfig()
        
        assert '🥉 Новенький' in config.get_rank_by_karma(3)
        assert '🥈 Надежда сообщества' in config.get_rank_by_karma(10)
        assert '🥇 Мега-помощничье' in config.get_rank_by_karma(20)
        assert '💎 Амбассадорище' in config.get_rank_by_karma(50)
    
    def test_get_rank_info(self):
        """Тест получения детальной информации о звании"""
        config = UserManagementConfig()
        
        rank_info = config.get_rank_info(10)
        assert rank_info['level'] == 'hope'
        assert rank_info['next_rank'] is not None
        assert rank_info['karma_to_next'] > 0
        assert 0 <= rank_info['progress_percent'] <= 100
    
    def test_is_admin(self):
        """Тест проверки администратора"""
        config = UserManagementConfig({'ADMIN_IDS': '12345,67890'})
        assert config.is_admin(12345) == True
        assert config.is_admin(99999) == False


class TestMusicUserModel:
    """Тесты модели пользователя"""
    
    def test_music_user_creation(self):
        """Тест создания пользователя"""
        user = MusicUser(
            user_id=12345,
            group_id=-1001234567890,
            username='test_user',
            first_name='Тест',
            karma_points=10
        )
        
        assert user.user_id == 12345
        assert user.username == 'test_user'
        assert user.karma_points == 10
        assert user.is_active == True
    
    def test_music_user_to_dict(self):
        """Тест преобразования пользователя в словарь"""
        user = MusicUser(
            user_id=12345,
            group_id=-1001234567890,
            username='test_user',
            karma_points=10
        )
        
        user_dict = user.to_dict()
        assert isinstance(user_dict, dict)
        assert user_dict['user_id'] == 12345
        assert user_dict['username'] == 'test_user'
        assert user_dict['karma_points'] == 10
    
    def test_music_user_karma_percentage(self):
        """Тест расчета процента кармы"""
        user = MusicUser(user_id=12345, group_id=-1001, karma_points=50)
        percentage = user.get_karma_percentage()
        expected = (50 / 100500) * 100
        assert abs(percentage - expected) < 0.01
    
    def test_music_user_can_change_karma(self):
        """Тест проверки возможности изменения кармы"""
        user = MusicUser(user_id=12345, group_id=-1001, karma_points=10)
        
        can_add, msg = user.can_change_karma(5)
        assert can_add == True
        assert msg is None
        
        can_subtract, msg = user.can_change_karma(-15)
        assert can_subtract == False
        assert "отрицательной" in msg
    
    def test_music_user_is_newbie(self):
        """Тест проверки новичка"""
        newbie = MusicUser(user_id=12345, group_id=-1001, karma_points=3)
        experienced = MusicUser(user_id=67890, group_id=-1001, karma_points=10)
        
        assert newbie.is_newbie() == True
        assert experienced.is_newbie() == False


class TestKarmaHistoryModel:
    """Тесты модели истории кармы"""
    
    def test_karma_history_creation(self):
        """Тест создания записи истории кармы"""
        entry = KarmaHistory(
            user_id=12345,
            group_id=-1001234567890,
            karma_change=5,
            karma_before=10,
            karma_after=15,
            reason='Помощь новичку',
            change_type='gratitude'
        )
        
        assert entry.user_id == 12345
        assert entry.karma_change == 5
        assert entry.karma_before == 10
        assert entry.karma_after == 15
        assert entry.reason == 'Помощь новичку'
    
    def test_karma_history_to_dict(self):
        """Тест преобразования истории кармы в словарь"""
        entry = KarmaHistory(
            user_id=12345,
            group_id=-1001,
            karma_change=5,
            karma_before=10,
            karma_after=15,
            reason='Тест'
        )
        
        entry_dict = entry.to_dict()
        assert isinstance(entry_dict, dict)
        assert entry_dict['user_id'] == 12345
        assert entry_dict['karma_change'] == 5


@pytest.mark.asyncio
class TestUserService:
    """Тесты сервиса пользователей (асинхронные)"""
    
    async def test_user_service_initialization(self):
        """Тест инициализации сервиса пользователей"""
        # Мокаем зависимости
        mock_database = Mock()
        mock_config = UserManagementConfig()
        
        service = UserService(mock_database, mock_config)
        assert service.database == mock_database
        assert service.config == mock_config


# Интеграционные тесты

class TestUserManagementIntegration:
    """Интеграционные тесты модуля"""
    
    def test_module_imports(self):
        """Тест импорта всех компонентов модуля"""
        from modules.user_management import (
            UserManagementModule,
            MusicUser,
            KarmaHistory,
            UserService,
            UserManagementConfig,
            UserDataValidator
        )
        
        # Проверяем, что все классы импортируются без ошибок
        assert UserManagementModule is not None
        assert MusicUser is not None
        assert KarmaHistory is not None
        assert UserService is not None
        assert UserManagementConfig is not None
        assert UserDataValidator is not None
    
    def test_module_info_consistency(self):
        """Тест консистентности информации о модуле"""
        from modules.user_management import get_module_info, get_module_stats
        
        info = get_module_info()
        stats = get_module_stats()
        
        assert info['name'] == 'user_management'
        assert info['plan'] == 1
        assert info['priority'] == 1
        assert info['webapp_integration'] == True
        
        assert stats['plan'] == 1
        assert stats['priority'] == 1
        assert stats['has_webapp'] == True
        assert stats['commands_count'] > 0
        assert stats['events_count'] > 0


def run_tests():
    """Запуск всех тестов модуля"""
    print("🧪 Запуск тестов модуля user_management...")
    
    # Запускаем синхронные тесты
    test_classes = [
        TestUserDataValidator,
        TestKarmaValidator,
        TestOnboardingValidator,
        TestSanitizers,
        TestUserManagementConfig,
        TestMusicUserModel,
        TestKarmaHistoryModel,
        TestUserManagementIntegration
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n📋 Тестирование {test_class.__name__}...")
        
        instance = test_class()
        test_methods = [method for method in dir(instance) if method.startswith('test_')]
        
        for test_method_name in test_methods:
            total_tests += 1
            try:
                test_method = getattr(instance, test_method_name)
                test_method()
                print(f"  ✅ {test_method_name}")
                passed_tests += 1
            except Exception as e:
                print(f"  ❌ {test_method_name}: {e}")
    
    print(f"\n📊 Результаты тестирования:")
    print(f"  Всего тестов: {total_tests}")
    print(f"  Пройдено: {passed_tests}")
    print(f"  Не пройдено: {total_tests - passed_tests}")
    print(f"  Процент успеха: {(passed_tests / total_tests * 100):.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 Все тесты пройдены успешно!")
        return True
    else:
        print("⚠️ Некоторые тесты не прошли проверку")
        return False


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
