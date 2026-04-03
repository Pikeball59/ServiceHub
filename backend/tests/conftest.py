"""
Фикстуры для тестов
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from backend.models import (
    User, Shop, Category, Product, ProductInfo,
    Parameter, ProductParameter, Order, OrderItem, Contact
)

User = get_user_model()


@pytest.fixture
def api_client():
    """Создаём API клиент"""
    return APIClient()

@pytest.fixture
def user_buyer():
    """Создаём пользователя-покупателя"""
    return User.objects.create_user(
        email='buyer@test.com',
        password='TestPassword123!',
        first_name='Иван',
        last_name='Петров',
        type='buyer',
        is_active=True
    )

@pytest.fixture
def user_shop():
    """Создаём пользователя-магазин"""
    return User.objects.create_user(
        email='shop@test.com',
        password='TestPassword123!',
        first_name='Магазин',
        last_name='Тестовый',
        type='shop',
        is_active=True
    )

@pytest.fixture
def user_admin():
    """Создаём суперпользователя"""
    return User.objects.create_superuser(
        email='admin@test.com',
        password='AdminPassword123!',
        first_name='Админ',
        last_name='Системы',
        is_active=True
    )


@pytest.fixture
def auth_token(user_buyer):
    """Создаём токен для пользователя"""
    token, _ = Token.objects.get_or_create(user=user_buyer)
    return token.key

@pytest.fixture
def authenticated_client(api_client, auth_token):
    """Создаём авторизованный API клиент"""
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token}')
    return api_client

@pytest.fixture
def shop(user_shop):
    """Создаём магазин"""
    return Shop.objects.create(
        name='Тестовый магазин',
        url='https://example.com/shop.yaml',
        user=user_shop,
        state=True
    )

@pytest.fixture
def category():
    """Создаём категорию"""
    return Category.objects.create(name='Смартфоны')

@pytest.fixture
def product(category):
    """Создаём товар"""
    return Product.objects.create(
        name='iPhone 15',
        category=category
    )

@pytest.fixture
def product_info(product, shop):
    """Создаём информацию о товаре"""
    return ProductInfo.objects.create(
        product=product,
        shop=shop,
        external_id=12345,
        model='apple/iphone/15',
        price=100000,
        price_rrc=110000,
        quantity=10
    )

@pytest.fixture
def parameter():
    """Создаём параметр"""
    return Parameter.objects.create(name='Цвет')

@pytest.fixture
def product_parameter(product_info, parameter):
    """Создаём параметр товара"""
    return ProductParameter.objects.create(
        product_info=product_info,
        parameter=parameter,
        value='Чёрный'
    )

@pytest.fixture
def contact(user_buyer):
    """Создаём контакт пользователя (адрес)"""
    return Contact.objects.create(
        user=user_buyer,
        type='address',
        city='Пермь',
        street='Монастырская',
        house='1',
        phone='+79239123455'
    )

@pytest.fixture
def order(user_buyer, contact):
    """Создаём заказ"""
    return Order.objects.create(
        user=user_buyer,
        state='new',
        contact=contact
    )

@pytest.fixture
def order_item(order, product_info):
    """Создаём позицию заказа"""
    return OrderItem.objects.create(
        order=order,
        product_info=product_info,
        quantity=2
    )

@pytest.fixture
def basket(user_buyer):
    """Создаём корзину"""
    return Order.objects.create(
        user=user_buyer,
        state='basket'
    )

@pytest.fixture
def phone_contact(user_buyer):
    """Создаём телефонный контакт"""
    return Contact.objects.create(
        user=user_buyer,
        type='phone',
        phone='+79239123455'
    )