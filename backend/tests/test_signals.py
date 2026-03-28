"""
Тесты сигналов Django
"""
import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from backend.models import User, Order, Contact, ConfirmEmailToken

User = get_user_model()

@pytest.mark.django_db
class TestUserSignals:
    """Тесты сигналов пользователя"""

    @patch('backend.signals.send_email_task.delay')
    def test_new_user_registered_signal(self, mock_send_email):
        """Сигнал при регистрации нового пользователя"""
        user = User.objects.create_user(
            email='new_signal@test.com',
            password='TestPass123!',
            first_name='Тест',
            last_name='Тестов'
        )
        token = ConfirmEmailToken.objects.filter(user=user).first()
        assert token is not None
        mock_send_email.assert_called_once()

    @patch('backend.signals.send_email_task.delay')
    def test_password_reset_signal(self, mock_send_email, user_buyer):
        """Сигнал сброса пароля"""
        from django_rest_passwordreset.models import ResetPasswordToken

        token = ResetPasswordToken.objects.create(user=user_buyer)
        assert token is not None
        mock_send_email.assert_called_once()

@pytest.mark.django_db
class TestOrderSignals:
    """Тесты сигналов заказа"""

    @patch('backend.signals.send_email_task.delay')
    def test_new_order_signal(self, mock_send_email, user_buyer, contact, basket, product_info):
        """Сигнал при создании нового заказа"""
        from backend.signals import new_order

        # Создаём позицию в корзине
        from backend.models import OrderItem
        OrderItem.objects.create(
            order=basket,
            product_info=product_info,
            quantity=2
        )

        # Отправляем сигнал
        new_order.send(sender=None, user_id=user_buyer.id, order_id=basket.id)

        # Email задачи должны быть вызваны (покупателю и администратору)
        assert mock_send_email.call_count >= 2

    @patch('backend.signals.send_email_task.delay')
    def test_order_status_changed_signal(self, mock_send_email, order):
        """Сигнал при изменении статуса заказа"""
        order.state = 'confirmed'
        order.save()

        # При изменении статуса отправляются два письма (покупателю и администратору)
        assert mock_send_email.call_count == 2

    @patch('backend.signals.send_email_task.delay')
    def test_order_status_not_changed_on_create(self, mock_send_email, user_buyer, contact):
        """Сигнал не срабатывает при создании заказа"""
        order = Order.objects.create(
            user=user_buyer,
            state='new',
            contact=contact
        )
        # При создании created=True, сигнал не должен отправлять уведомления о статусе
        # (только new_order сигнал)
        mock_send_email.assert_not_called()


