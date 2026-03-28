"""
Тесты Celery задач
"""
import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from backend.tasks import send_email_task, do_import_task
from backend.models import User, Shop, Product, ProductInfo, Category

User = get_user_model()

@pytest.mark.django_db
class TestSendEmailTask:
    """Тесты задачи отправки email"""

    @patch('backend.tasks.EmailMultiAlternatives')
    def test_send_email_task(self, mock_email):
        """Отправка email задачи"""
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance

        result = send_email_task(
            subject='Тест',
            message='Тестовое сообщение',
            recipient_list=['test@test.com']
        )

        mock_email.assert_called_once()
        mock_instance.send.assert_called_once()

    @patch('backend.tasks.EmailMultiAlternatives')
    def test_send_email_task_with_html(self, mock_email):
        """Отправка email с HTML"""
        mock_instance = MagicMock()
        mock_email.return_value = mock_instance

        result = send_email_task(
            subject='Тест',
            message='Тестовое сообщение',
            recipient_list=['test@test.com'],
            html_message='<h1>Тест</h1>'
        )

        mock_instance.attach_alternative.assert_called_once()

@pytest.mark.django_db
class TestDoImportTask:
    """Тесты задачи импорта"""

    @patch('backend.tasks.get')
    @patch('backend.tasks.yaml.safe_load')
    def test_do_import_task_success(self, mock_yaml, mock_get, user_shop):
        """Успешный импорт"""
        mock_response = MagicMock()
        mock_response.content = b'shop: Test\ncategories: []\ngoods: []'
        mock_get.return_value = mock_response
        mock_yaml.return_value = {
            'shop': 'Test Shop',
            'categories': [{'id': 1, 'name': 'Test'}],
            'goods': []
        }

        result = do_import_task('https://example.com/shop.yaml', user_shop.id)

        assert result['status'] is True

    @patch('backend.tasks.get')
    def test_do_import_task_invalid_url(self, mock_get, user_shop):
        """Невалидный URL"""
        mock_get.side_effect = Exception('Connection error')

        result = do_import_task('https://invalid.invalid/shop.yaml', user_shop.id)

        assert result['status'] is False

    @patch('backend.tasks.get')
    @patch('backend.tasks.yaml.safe_load')
    def test_do_import_task_invalid_yaml(self, mock_yaml, mock_get, user_shop):
        """Невалидный YAML"""
        mock_response = MagicMock()
        mock_response.content = b'invalid yaml'
        mock_get.return_value = mock_response
        mock_yaml.side_effect = Exception('YAML error')

        result = do_import_task('https://example.com/shop.yaml', user_shop.id)

        assert result['status'] is False