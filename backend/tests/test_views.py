"""
Тесты API Views
"""
import json
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from backend.models import User, Shop, Order, Contact

@pytest.mark.django_db
class TestRegisterAccount:
    """Тесты регистрации пользователя"""

    def test_register_success(self, api_client):
        """Успешная регистрация"""
        url = reverse('backend:user-register')
        data = {
            'first_name': 'Иван',
            'last_name': 'Петров',
            'email': 'newuser@test.com',
            'password': 'TestPassword123!',
            'company': 'ООО Тест',
            'position': 'Менеджер'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True
        assert User.objects.filter(email='newuser@test.com').exists()

    def test_register_missing_fields(self, api_client):
        """Регистрация без обязательных полей"""
        url = reverse('backend:user-register')
        data = {
            'first_name': 'Иван',
            'email': 'newuser@test.com'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False
        assert 'Errors' in response.json()

    def test_register_weak_password(self, api_client):
        """Регистрация со слабым паролем"""
        url = reverse('backend:user-register')
        data = {
            'first_name': 'Иван',
            'last_name': 'Петров',
            'email': 'newuser2@test.com',
            'password': '123',
            'company': '',
            'position': ''
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False
        assert 'password' in response.json()['Errors']

    def test_register_duplicate_email(self, api_client, user_buyer):
        """Регистрация с существующим email"""
        url = reverse('backend:user-register')
        data = {
            'first_name': 'Иван',
            'last_name': 'Петров',
            'email': user_buyer.email,
            'password': 'TestPassword123!',
            'company': '',
            'position': ''
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

@pytest.mark.django_db
class TestLoginAccount:
    """Тесты авторизации"""

    def test_login_success(self, api_client, user_buyer):
        """Успешная авторизация"""
        url = reverse('backend:user-login')
        data = {
            'email': 'buyer@test.com',
            'password': 'TestPassword123!'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True
        assert 'Token' in response.json()

    def test_login_wrong_password(self, api_client, user_buyer):
        """Неверный пароль"""
        url = reverse('backend:user-login')
        data = {
            'email': 'buyer@test.com',
            'password': 'WrongPassword'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

    def test_login_missing_fields(self, api_client):
        """Отсутствие обязательных полей"""
        url = reverse('backend:user-login')
        data = {
            'email': 'buyer@test.com'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

    def test_login_inactive_user(self, api_client):
        """Авторизация неактивного пользователя"""
        user = User.objects.create_user(
            email='inactive@test.com',
            password='TestPassword123!',
            is_active=False
        )
        url = reverse('backend:user-login')
        data = {
            'email': 'inactive@test.com',
            'password': 'TestPassword123!'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

@pytest.mark.django_db
class TestConfirmAccount:
    """Тесты подтверждения email"""

    def test_confirm_success(self, api_client, user_buyer):
        """Успешное подтверждение email"""
        from backend.models import ConfirmEmailToken
        token = ConfirmEmailToken.objects.create(user=user_buyer)

        url = reverse('backend:user-register-confirm')
        data = {
            'email': 'buyer@test.com',
            'token': token.key
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

        user_buyer.refresh_from_db()
        assert user_buyer.is_active is True

    def test_confirm_wrong_token(self, api_client, user_buyer):
        """Неверный токен"""
        url = reverse('backend:user-register-confirm')
        data = {
            'email': 'buyer@test.com',
            'token': 'wrong_token'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

    def test_confirm_missing_fields(self, api_client):
        """Отсутствие обязательных полей"""
        url = reverse('backend:user-register-confirm')
        data = {
            'email': 'buyer@test.com'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

@pytest.mark.django_db
class TestProductInfoView:
    """Тесты просмотра товаров"""

    def test_get_products_list(self, api_client, product_info):
        """Получение списка товаров"""
        url = reverse('backend:products')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)
        assert len(response.json()) >= 1

    def test_get_products_filter_by_shop(self, api_client, product_info, shop):
        """Фильтрация товаров по магазину"""
        url = f"{reverse('backend:products')}?shop_id={shop.id}"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        for item in response.json():
            assert item['shop'] == shop.id

    def test_get_products_filter_by_category(self, api_client, product_info, category):
        """Фильтрация товаров по категории"""
        url = f"{reverse('backend:products')}?category_id={category.id}"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_get_products_search(self, api_client, product_info):
        """Поиск товаров"""
        url = f"{reverse('backend:products')}?search=iPhone"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_get_products_inactive_shop(self, api_client, shop):
        """Товары неактивного магазина не показываются"""
        shop.state = False
        shop.save()
        url = reverse('backend:products')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

@pytest.mark.django_db
class TestBasketView:
    """Тесты корзины"""

    def test_get_basket_authenticated(self, authenticated_client, basket):
        """Получение корзины авторизованным пользователем"""
        url = reverse('backend:basket')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_get_basket_unauthenticated(self, api_client):
        """Получение корзины неавторизованным пользователем"""
        url = reverse('backend:basket')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_add_to_basket(self, authenticated_client, product_info):
        """Добавление товара в корзину"""
        url = reverse('backend:basket')
        data = {
            'items': json.dumps([{"product_info": product_info.id, "quantity": 2}])
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

    def test_add_to_basket_invalid_json(self, authenticated_client):
        """Добавление с неверным JSON"""
        url = reverse('backend:basket')
        data = {
            'items': 'invalid_json'
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

    def test_delete_from_basket(self, authenticated_client, basket, order_item):
        """Удаление товара из корзины"""
        order_item.order = basket
        order_item.save()

        url = reverse('backend:basket')
        data = {
            'items': str(order_item.id)
        }
        response = authenticated_client.delete(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

    def test_update_basket_quantity(self, authenticated_client, basket, order_item):
        """Обновление количества товара в корзине"""
        order_item.order = basket
        order_item.save()

        url = reverse('backend:basket')
        data = {
            'items': json.dumps([{"id": order_item.id, "quantity": 5}])
        }
        response = authenticated_client.put(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

@pytest.mark.django_db
class TestContactView:
    """Тесты контактов"""

    def test_get_contacts(self, authenticated_client, contact):
        """Получение списка контактов"""
        url = reverse('backend:user-contact')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) >= 1

    def test_create_contact(self, authenticated_client):
        """Создание нового контакта"""
        url = reverse('backend:user-contact')
        data = {
            'city': 'Санкт-Петербург',
            'street': 'Невский',
            'house': '10',
            'phone': '+79991112233'
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

    def test_create_contact_missing_fields(self, authenticated_client):
        """Создание контакта без обязательных полей"""
        url = reverse('backend:user-contact')
        data = {
            'city': 'Пермь'
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

    def test_delete_contact(self, authenticated_client, contact):
        """Удаление контакта"""
        url = reverse('backend:user-contact')
        data = {
            'items': str(contact.id)
        }
        response = authenticated_client.delete(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

    def test_update_contact(self, authenticated_client, contact):
        """Обновление контакта"""
        url = reverse('backend:user-contact')
        data = {
            'id': contact.id,
            'city': 'Новый город'
        }
        response = authenticated_client.put(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

@pytest.mark.django_db
class TestOrderView:
    """Тесты заказов"""

    def test_get_orders(self, authenticated_client, order):
        """Получение списка заказов"""
        url = reverse('backend:order')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) >= 1

    def test_confirm_order(self, authenticated_client, basket, contact):
        """Подтверждение заказа"""
        url = reverse('backend:order')
        data = {
            'id': basket.id,
            'contact': contact.id
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

        basket.refresh_from_db()
        assert basket.state == 'new'

    def test_confirm_order_wrong_contact(self, authenticated_client, basket):
        """Подтверждение с чужим контактом"""
        from backend.models import User, Contact
        other_user = User.objects.create_user(
            email='other@test.com',
            password='TestPass123!',
            is_active=True
        )
        other_contact = Contact.objects.create(
            user=other_user,
            city='Пермь',
            street='Монастырская',
            house='1',
            phone='+79239123455'
        )

        url = reverse('backend:order')
        data = {
            'id': basket.id,
            'contact': other_contact.id
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is False

    def test_cancel_order(self, authenticated_client, order):
        """Отмена заказа"""
        url = reverse('backend:order')
        data = {
            'id': order.id,
            'state': 'canceled'
        }
        response = authenticated_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

        order.refresh_from_db()
        assert order.state == 'canceled'

@pytest.mark.django_db
class TestPartnerViews:
    """Тесты для партнёров (магазинов)"""

    def test_partner_update(self, api_client, user_shop, shop):
        """Обновление прайс-листа партнёром"""
        from rest_framework.authtoken.models import Token
        auth_token = Token.objects.create(user=user_shop)

        api_client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token.key}')

        url = reverse('backend:partner-update')
        data = {
            'url': 'https://example.com/shop.yaml'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

    def test_partner_update_not_shop(self, api_client, user_buyer):
        """Обновление прайс-листа покупателем (запрещено)"""
        from rest_framework.authtoken.models import Token
        auth_token = Token.objects.create(user=user_buyer)

        api_client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token.key}')

        url = reverse('backend:partner-update')
        data = {
            'url': 'https://example.com/shop.yaml'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_partner_state_get(self, api_client, user_shop, shop):
        """Получение статуса магазина"""
        from rest_framework.authtoken.models import Token
        auth_token = Token.objects.create(user=user_shop)

        api_client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token.key}')

        url = reverse('backend:partner-state')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_partner_state_update(self, api_client, user_shop, shop):
        """Изменение статуса магазина"""
        from rest_framework.authtoken.models import Token
        auth_token = Token.objects.create(user=user_shop)

        api_client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token.key}')

        url = reverse('backend:partner-state')
        data = {
            'state': 'false'
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

        shop.refresh_from_db()
        assert shop.state is False

    def test_partner_orders(self, api_client, user_shop, shop, order, order_item):
        """Получение заказов партнёра"""
        from rest_framework.authtoken.models import Token
        auth_token = Token.objects.create(user=user_shop)

        api_client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token.key}')

        order_item.product_info.shop = shop
        order_item.product_info.save()

        url = reverse('backend:partner-orders')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK

@pytest.mark.django_db
class TestCategoryView:
    """Тесты категорий"""

    def test_get_categories(self, api_client, category):
        """Получение списка категорий"""
        url = reverse('backend:categories')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) >= 1


@pytest.mark.django_db
class TestShopView:
    """Тесты магазинов"""

    def test_get_shops(self, api_client, shop):
        """Получение списка магазинов"""
        url = reverse('backend:shops')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) >= 1

    def test_get_shops_inactive_not_shown(self, api_client):
        """Неактивные магазины не показываются"""
        from backend.models import User
        user = User.objects.create_user(
            email='shop2@test.com',
            password='TestPass123!',
            type='shop',
            is_active=True
        )
        Shop.objects.create(
            name='Inactive Shop',
            user=user,
            state=False
        )

        url = reverse('backend:shops')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for shop in data:
            assert shop['state'] is True

@pytest.mark.django_db
class TestProductDetailView:
    """Тесты детальной информации о товаре"""

    def test_get_product_detail(self, api_client, product_info):
        """Получение детальной информации о товаре"""
        url = reverse('backend:product-detail', kwargs={'pk': product_info.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['id'] == product_info.id

    def test_get_product_detail_not_found(self, api_client):
        """Товар не найден"""
        url = reverse('backend:product-detail', kwargs={'pk': 99999})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.django_db
class TestAccountDetails:
    """Тесты данных пользователя"""

    def test_get_account_details(self, authenticated_client):
        """Получение данных аккаунта"""
        url = reverse('backend:user-details')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'email' in response.json()

    def test_update_account_details(self, authenticated_client):
        """Обновление данных аккаунта"""
        url = reverse('backend:user-details')
        data = {
            'first_name': 'Новое имя'
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

    def test_update_password(self, authenticated_client):
        """Обновление пароля"""
        url = reverse('backend:user-details')
        data = {
            'password': 'NewPassword123!'
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        assert response.json()['Status'] is True

# Добавлю тест для throttling
@pytest.mark.django_db
class TestThrottling:
    def test_anon_throttle(self, api_client):
        """Проверка, что анонимный пользователь получает 429 после превышения лимита (100 запросов в день)"""
        url = reverse('backend:products')
        # Делаем 101 запрос
        for _ in range(101):
            response = api_client.get(url)
        # Последний (101-й) должен вернуть 429
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS