import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from backend.models import (
    User, Shop, Category, Product, ProductInfo, Contact,
    Image,
)
from backend.tasks import do_import_task, process_image
from backend.signals import new_order
from backend.views import OrderView

User = get_user_model()

# Тесты для исправленного OrderView.post
@pytest.mark.django_db
class TestOrderViewPostFix:
    def test_confirm_basket_success(self, authenticated_client, basket, contact):
        """Успешное подтверждение корзины (статус basket -> new)"""
        url = '/api/v1/order'
        data = {'id': basket.id, 'contact': contact.id}
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == 200
        assert response.json()['Status'] is True
        basket.refresh_from_db()
        assert basket.state == 'new'
        assert basket.contact == contact

    def test_confirm_non_basket_order_fails(self, authenticated_client, order, contact):
        """Попытка подтвердить заказ, который не является корзиной (state != basket)"""
        url = '/api/v1/order'
        original_state = order.state  # например 'new'
        data = {'id': order.id, 'contact': contact.id}
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert 'Корзина не найдена или уже оформлена' in response.json()['Errors']
        order.refresh_from_db()
        assert order.state == original_state

    def test_confirm_with_wrong_contact(self, authenticated_client, basket, user_buyer):
        """Подтверждение с контактом другого пользователя"""
        other_user = User.objects.create_user(email='other@test.com', password='123', is_active=True)
        other_contact = Contact.objects.create(user=other_user, type='phone', phone='+79991112233')
        url = '/api/v1/order'
        data = {'id': basket.id, 'contact': other_contact.id}
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == 200
        assert response.json()['Status'] is False
        assert 'Контакт не найден или не принадлежит вам' in response.json()['Errors']

    def test_confirm_already_confirmed_basket_fails(self, authenticated_client, basket, contact):
        """Повторное подтверждение той же корзины (уже переведена в new)"""
        url = '/api/v1/order'
        # Первое подтверждение
        response1 = authenticated_client.post(url, {'id': basket.id, 'contact': contact.id}, format='json')
        assert response1.json()['Status'] is True
        # Второе подтверждение
        response2 = authenticated_client.post(url, {'id': basket.id, 'contact': contact.id}, format='json')
        assert response2.json()['Status'] is False
        assert 'Корзина не найдена или уже оформлена' in response2.json()['Errors']

# Тесты для ограничений Contact
@pytest.mark.django_db
class TestContactConstraints:
    def test_only_one_phone_per_user(self, user_buyer):
        Contact.objects.create(user=user_buyer, type='phone', phone='+79123456789')
        with pytest.raises(ValidationError, match='только один телефонный контакт'):
            Contact.objects.create(user=user_buyer, type='phone', phone='+79876543210')

    def test_max_five_addresses_per_user(self, user_buyer):
        for i in range(5):
            Contact.objects.create(
                user=user_buyer, type='address',
                city='City', street='Street', house=str(i), phone='+7000000000{}'.format(i)
            )
        # Шестой адрес должен вызвать ошибку
        with pytest.raises(ValidationError, match='не более пяти адресов'):
            Contact.objects.create(
                user=user_buyer, type='address',
                city='Over', street='Limit', house='6', phone='+79999999999'
            )

    def test_phone_must_be_provided_for_phone_type(self, user_buyer):
        with pytest.raises(ValidationError, match='необходимо указать номер'):
            Contact.objects.create(user=user_buyer, type='phone', phone='')

    def test_address_requires_city_street_phone(self, user_buyer):
        with pytest.raises(ValidationError, match='указать город, улицу и телефон'):
            Contact.objects.create(user=user_buyer, type='address', city='Moscow', street='Tverskaya')

# Тесты для сигналов (отправка писем)
@pytest.mark.django_db
class TestSignals:
    @patch('backend.signals.send_email_task.delay')
    def test_new_user_registered_signal(self, mock_send_email, user_buyer):
        """При создании неактивного пользователя должен отправиться токен"""
        # user_buyer уже создан фикстурой, но там is_active=True. Создам нового
        new_user = User.objects.create_user(
            email='fresh@test.com', password='test123', is_active=False
        )
        mock_send_email.assert_called_once()
        args, _ = mock_send_email.call_args
        assert 'Password Reset Token' in args[0]
        assert args[2] == ['fresh@test.com']

    @patch('backend.signals.send_email_task.delay')
    def test_new_order_signal(self, mock_send_email, order):
        """При создании нового заказа (state='new') должны отправиться два письма"""
        # order из фикстуры уже создан со state='new', но сигнал new_order отправляется вручную
        # Вызову сигнал напрямую (должен сработать после подтверждения корзины)
        new_order.send(sender=OrderView, user_id=order.user.id, order_id=order.id)
        # Должно быть два вызова: покупателю и админу
        assert mock_send_email.call_count == 2

    @patch('backend.signals.send_email_task.delay')
    def test_order_status_changed_signal(self, mock_send_email, order):
        """Изменение статуса заказа (не при создании) отправляет два письма: покупателю и админу"""
        order.state = 'confirmed'
        order.save()
        assert mock_send_email.call_count == 2
        # Проверяю, что тема первого письма содержит правильный текст
        args, _ = mock_send_email.call_args_list[0]
        assert 'Изменение статуса заказа' in args[0] or 'Статус заказа' in args[0]

# Тесты для импорта YAML (do_import_task)
@pytest.mark.django_db
class TestDoImportTask:
    @patch('backend.tasks.get')
    @patch('backend.tasks.yaml.safe_load')
    def test_import_creates_shop_categories_products(self, mock_yaml, mock_get, user_shop):
        mock_response = MagicMock()
        mock_response.content = b'dummy'
        mock_get.return_value = mock_response
        mock_yaml.return_value = {
            'shop': 'Test Shop',
            'categories': [{'id': 1, 'name': 'Electronics'}],
            'goods': [
                {
                    'id': 101,
                    'category': 1,
                    'model': 'abc',
                    'name': 'Phone',
                    'price': 500,
                    'price_rrc': 550,
                    'quantity': 10,
                    'parameters': {'Color': 'Black'}
                }
            ]
        }
        result = do_import_task('http://example.com/shop.yaml', user_shop.id)
        assert result['status'] is True
        shop = Shop.objects.get(user=user_shop)
        assert shop.name == 'Test Shop'
        category = Category.objects.get(id=1)
        assert category.name == 'Electronics'
        product = Product.objects.get(name='Phone')
        assert product.category == category
        product_info = ProductInfo.objects.get(product=product, shop=shop)
        assert product_info.price == 500
        param = product_info.product_parameters.first()
        assert param.parameter.name == 'Color'
        assert param.value == 'Black'

    @patch('backend.tasks.get')
    def test_import_invalid_url(self, mock_get, user_shop):
        mock_get.side_effect = Exception('Connection error')
        result = do_import_task('http://bad.url', user_shop.id)
        assert result['status'] is False
        assert 'error' in result

# Тесты для обработки изображений
@pytest.mark.django_db
class TestImageProcessing:
    @patch('backend.tasks.PILImage.open')
    def test_process_image_creates_thumbnails(self, mock_pil_open, tmpdir, settings):
        from django.core.files.base import ContentFile
        import os

        # Временно меняю MEDIA_ROOT на временную папку
        settings.MEDIA_ROOT = str(tmpdir)
        # Создаю структуру папок
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'images', 'original'), exist_ok=True)

        img = Image.objects.create(original=ContentFile(b'fake', name='test.jpg'))

        # Мокаю PIL
        mock_img = MagicMock()
        mock_pil_open.return_value = mock_img
        mock_img.copy.return_value = mock_img

        process_image(img.id)

        img.refresh_from_db()
        assert img.thumbnail is not None
        assert img.medium is not None
        assert img.large is not None

# Тесты для социальной авторизации (мокаю внешние запросы)
@pytest.mark.django_db
class TestSocialAuth:
    @patch('backend.views.requests.get')
    def test_google_auth_valid_token(self, mock_get, api_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'email': 'googleuser@example.com',
            'given_name': 'Google',
            'family_name': 'User',
            'sub': '12345'
        }
        mock_get.return_value = mock_resp
        url = '/api/v1/auth/google/'
        response = api_client.post(url, {'token': 'valid_token'}, format='json')
        assert response.status_code == 200
        assert 'token' in response.json()
        user = User.objects.get(email='googleuser@example.com')
        assert user.is_active is True

    @patch('backend.views.requests.get')
    def test_github_auth_valid_token(self, mock_get, api_client):
        # Мокаю запрос к /user
        mock_user_resp = MagicMock()
        mock_user_resp.status_code = 200
        mock_user_resp.json.return_value = {'id': 67890, 'name': 'Git Hub'}
        # Мокаю запрос к /user/emails
        mock_email_resp = MagicMock()
        mock_email_resp.status_code = 200
        mock_email_resp.json.return_value = [{'email': 'git@example.com', 'primary': True}]
        mock_get.side_effect = [mock_user_resp, mock_email_resp]
        url = '/api/v1/auth/github/'
        response = api_client.post(url, {'token': 'gh_token'}, format='json')
        assert response.status_code == 200
        assert 'token' in response.json()
        user = User.objects.get(email='git@example.com')
        assert user.first_name == 'Git'



