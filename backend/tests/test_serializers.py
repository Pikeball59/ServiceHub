"""
Тесты сериализаторов
"""
import pytest
from django.contrib.auth import get_user_model

from backend.serializers import (
    UserSerializer, ContactSerializer, CategorySerializer,
    ShopSerializer, ProductInfoSerializer, OrderSerializer,
    OrderItemSerializer
)
from backend.models import User, Contact, Category, Shop, Product, ProductInfo, Order

User = get_user_model()

@pytest.mark.django_db
class TestUserSerializer:
    """Тесты UserSerializer"""

    def test_user_serializer_valid(self, user_buyer):
        """Валидная сериализация пользователя"""
        serializer = UserSerializer(user_buyer)
        assert 'email' in serializer.data
        assert 'first_name' in serializer.data
        assert 'last_name' in serializer.data

    def test_user_serializer_create(self):
        """Создаём пользователя через сериализатор"""
        data = {
            'email': 'new@test.com',
            'first_name': 'Тест',
            'last_name': 'Тестов',
            'company': 'ООО',
            'position': 'Менеджер'
        }
        serializer = UserSerializer(data=data)
        assert serializer.is_valid()

@pytest.mark.django_db
class TestContactSerializer:
    """Тесты ContactSerializer"""

    def test_contact_serializer_valid(self, user_buyer):
        """Валидная сериализация контакта (адрес)"""
        contact = Contact.objects.create(
            user=user_buyer,
            type='address',
            city='Пермь',
            street='Монастырская',
            house='1',
            phone='+79239123455'
        )
        serializer = ContactSerializer(contact)
        assert 'type' in serializer.data
        assert serializer.data['type'] == 'address'
        assert 'city' in serializer.data
        assert 'street' in serializer.data
        assert 'phone' in serializer.data

    def test_contact_serializer_valid_phone(self, user_buyer):
        """Валидная сериализация контакта (телефон)"""
        contact = Contact.objects.create(
            user=user_buyer,
            type='phone',
            phone='+79239123455'
        )
        serializer = ContactSerializer(contact)
        assert 'type' in serializer.data
        assert serializer.data['type'] == 'phone'
        assert 'phone' in serializer.data
        # поля адреса должны быть пустыми
        assert serializer.data['city'] == ''
        assert serializer.data['street'] == ''

    def test_contact_serializer_create_address(self, user_buyer):
        """Создаём адрес через сериализатор"""
        data = {
            'user': user_buyer.id,
            'type': 'address',
            'city': 'Пермь',
            'street': 'Монастырская',
            'house': '1',
            'phone': '+79239123455'
        }
        serializer = ContactSerializer(data=data)
        assert serializer.is_valid()
        contact = serializer.save()
        assert contact.type == 'address'
        assert contact.city == 'Пермь'

    def test_contact_serializer_create_phone(self, user_buyer):
        """Создаём телефон через сериализатор"""
        data = {
            'user': user_buyer.id,
            'type': 'phone',
            'phone': '+79239123455'
        }
        serializer = ContactSerializer(data=data)
        assert serializer.is_valid()
        contact = serializer.save()
        assert contact.type == 'phone'
        assert contact.phone == '+79239123455'

    # Тест удалён, так как валидация обязательных полей перенесена в модель Contact.
    # Сериализатор допускает пустые поля, ошибки возникают только при вызове save().

    def test_contact_serializer_invalid_type(self, user_buyer):
        """Неверный тип контакта"""
        data = {
            'user': user_buyer.id,
            'type': 'invalid_type',
            'phone': '+79239123455'
        }
        serializer = ContactSerializer(data=data)
        assert not serializer.is_valid()
        assert 'type' in serializer.errors

@pytest.mark.django_db
class TestCategorySerializer:
    """Тесты CategorySerializer"""

    def test_category_serializer_valid(self, category):
        """Валидная сериализация категории"""
        serializer = CategorySerializer(category)
        assert 'name' in serializer.data


@pytest.mark.django_db
class TestShopSerializer:
    """Тесты ShopSerializer"""

    def test_shop_serializer_valid(self, shop):
        """Валидная сериализация магазина"""
        serializer = ShopSerializer(shop)
        assert 'name' in serializer.data
        assert 'state' in serializer.data

@pytest.mark.django_db
class TestProductInfoSerializer:
    """Тесты ProductInfoSerializer"""

    def test_product_info_serializer_valid(self, product_info):
        """Валидная сериализация информации о товаре"""
        serializer = ProductInfoSerializer(product_info)
        assert 'price' in serializer.data
        assert 'quantity' in serializer.data
        assert 'product' in serializer.data

@pytest.mark.django_db
class TestOrderSerializer:
    """Тесты OrderSerializer"""

    def test_order_serializer_valid(self, order):
        """Валидная сериализация заказа"""
        serializer = OrderSerializer(order)
        assert 'state' in serializer.data
        assert 'dt' in serializer.data

@pytest.mark.django_db
class TestOrderItemSerializer:
    """Тесты OrderItemSerializer"""

    def test_order_item_serializer_valid(self, order_item):
        """Валидная сериализация позиции заказа"""
        serializer = OrderItemSerializer(order_item)
        assert 'quantity' in serializer.data
        assert 'product_info' in serializer.data


