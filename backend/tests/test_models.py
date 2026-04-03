"""
Тесты моделей Django
"""
import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model

from backend.models import (
    User, Shop, Category, Product, ProductInfo,
    Parameter, ProductParameter, Order, OrderItem, Contact,
    ConfirmEmailToken, STATE_CHOICES, USER_TYPE_CHOICES
)

User = get_user_model()

@pytest.mark.django_db
class TestUserModel:
    """Тесты модели User"""

    def test_create_user(self):
        """Создаём обычного пользователя"""
        user = User.objects.create_user(
            email='test@test.com',
            password='TestPass123!',
            first_name='Тест',
            last_name='Тестов'
        )
        assert user.email == 'test@test.com'
        assert user.type == 'buyer'
        assert user.is_active is False
        assert user.is_staff is False
        assert user.is_superuser is False

    def test_create_superuser(self):
        """Создаём суперпользователя"""
        user = User.objects.create_superuser(
            email='admin@test.com',
            password='AdminPass123!'
        )
        assert user.is_active is True
        assert user.is_staff is True
        assert user.is_superuser is True

    def test_user_email_unique(self):
        """Email должен быть уникальным"""
        User.objects.create_user(
            email='unique@test.com',
            password='TestPass123!'
        )
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email='unique@test.com',
                password='TestPass123!'
            )

    def test_user_without_email(self):
        """Создаём пользователя без email, должно вызвать ошибку"""
        with pytest.raises(ValueError):
            User.objects.create_user(
                email='',
                password='TestPass123!'
            )

    def test_user_str(self):
        """Проверяем строкового представления"""
        user = User.objects.create_user(
            email='str@test.com',
            password='TestPass123!',
            first_name='Иван',
            last_name='Иванов'
        )
        assert str(user) == 'Иван Иванов'

    def test_user_type_choices(self):
        """Проверяем типы пользователей"""
        assert ('shop', 'Магазин') in USER_TYPE_CHOICES
        assert ('buyer', 'Покупатель') in USER_TYPE_CHOICES


@pytest.mark.django_db
class TestShopModel:
    """Тесты модели Shop"""

    def test_create_shop(self, user_shop):
        """Создаём магазин"""
        shop = Shop.objects.create(
            name='Тестовый магазин',
            user=user_shop,
            state=True
        )
        assert shop.name == 'Тестовый магазин'
        assert shop.state is True

    def test_shop_str(self, user_shop):
        """Строковое представление магазина"""
        shop = Shop.objects.create(
            name='Магазин Тест',
            user=user_shop
        )
        assert str(shop) == 'Магазин Тест'

    def test_shop_state_default(self, user_shop):
        """Значение state по умолчанию"""
        shop = Shop.objects.create(
            name='Магазин',
            user=user_shop
        )
        assert shop.state is True

@pytest.mark.django_db
class TestCategoryModel:
    """Тесты модели Category"""

    def test_create_category(self):
        """Создаём категории"""
        category = Category.objects.create(name='Электроника')
        assert category.name == 'Электроника'

    def test_category_str(self):
        """Строковое представление категории"""
        category = Category.objects.create(name='Телефоны')
        assert str(category) == 'Телефоны'

    def test_category_shops_m2m(self, shop):
        """Связь ManyToMany с магазинами"""
        category = Category.objects.create(name='Смартфоны')
        category.shops.add(shop)
        assert shop in category.shops.all()

@pytest.mark.django_db
class TestProductModel:
    """Тесты модели Product"""

    def test_create_product(self, category):
        """Создаем товар"""
        product = Product.objects.create(
            name='iPhone 15',
            category=category
        )
        assert product.name == 'iPhone 15'
        assert product.category == category

    def test_product_str(self, category):
        """Строковое представление товара"""
        product = Product.objects.create(
            name='Samsung Galaxy',
            category=category
        )
        assert str(product) == 'Samsung Galaxy'

@pytest.mark.django_db
class TestProductInfoModel:
    """Тесты модели ProductInfo"""

    def test_create_product_info(self, product, shop):
        """Создаём информацию о товаре"""
        product_info = ProductInfo.objects.create(
            product=product,
            shop=shop,
            external_id=12345,
            model='apple/iphone/15',
            price=100000,
            price_rrc=110000,
            quantity=10
        )
        assert product_info.price == 100000
        assert product_info.quantity == 10

    def test_product_info_str(self, product, shop):
        """Строковое представление ProductInfo"""
        product_info = ProductInfo.objects.create(
            product=product,
            shop=shop,
            external_id=12345,
            price=100000,
            price_rrc=110000,
            quantity=10
        )
        assert 'iPhone 15' in str(product_info)
        assert 'Тестовый магазин' in str(product_info)

    def test_product_info_unique_constraint(self, product, shop):
        """Проверка уникальности (product, shop, external_id)"""
        ProductInfo.objects.create(
            product=product,
            shop=shop,
            external_id=12345,
            price=100000,
            price_rrc=110000,
            quantity=10
        )
        with pytest.raises(IntegrityError):
            ProductInfo.objects.create(
                product=product,
                shop=shop,
                external_id=12345,
                price=90000,
                price_rrc=100000,
                quantity=5
            )

@pytest.mark.django_db
class TestParameterModel:
    """Тесты модели Parameter"""

    def test_create_parameter(self):
        """Создаём параметр"""
        parameter = Parameter.objects.create(name='Цвет')
        assert parameter.name == 'Цвет'

    def test_parameter_str(self):
        """Строковое представление параметра"""
        parameter = Parameter.objects.create(name='Размер')
        assert str(parameter) == 'Размер'

@pytest.mark.django_db
class TestProductParameterModel:
    """Тесты модели ProductParameter"""

    def test_create_product_parameter(self, product_info, parameter):
        """Создаём параметр товара"""
        pp = ProductParameter.objects.create(
            product_info=product_info,
            parameter=parameter,
            value='Чёрный'
        )
        assert pp.value == 'Чёрный'

    def test_product_parameter_unique_constraint(self, product_info, parameter):
        """Проверка уникальности (product_info, parameter)"""
        ProductParameter.objects.create(
            product_info=product_info,
            parameter=parameter,
            value='Чёрный'
        )
        with pytest.raises(IntegrityError):
            ProductParameter.objects.create(
                product_info=product_info,
                parameter=parameter,
                value='Белый'
            )

@pytest.mark.django_db
class TestContactModel:
    """Тесты модели Contact"""

    def test_create_contact(self, user_buyer):
        """Создаём контакт (адрес)"""
        contact = Contact.objects.create(
            user=user_buyer,
            type='address',
            city='Пермь',
            street='Монастырская',
            house='1',
            phone='+79239123455'
        )
        assert contact.city == 'Пермь'
        assert contact.phone == '+79239123455'

    def test_contact_str(self, user_buyer):
        """Строковое представление контакта (адрес)"""
        contact = Contact.objects.create(
            user=user_buyer,
            type='address',
            city='Пермь',
            street='Монастырская',
            house='1',
            phone='+79239123455'
        )
        assert str(contact) == 'Пермь Монастырская 1'

@pytest.mark.django_db
class TestOrderModel:
    """Тесты модели Order"""

    def test_create_order(self, user_buyer, contact):
        """Создаём заказ"""
        order = Order.objects.create(
            user=user_buyer,
            state='new',
            contact=contact
        )
        assert order.user == user_buyer
        assert order.state == 'new'

    def test_order_str(self, user_buyer, contact):
        """Строковое представление заказа"""
        order = Order.objects.create(
            user=user_buyer,
            state='new',
            contact=contact
        )
        assert str(order) is not None  # Дата создания

    def test_order_state_choices(self, user_buyer, contact):
        """Проверка статусов заказа"""
        for state, _ in STATE_CHOICES:
            order = Order.objects.create(
                user=user_buyer,
                state=state,
                contact=contact
            )
            assert order.state == state

@pytest.mark.django_db
class TestOrderItemModel:
    """Тесты модели OrderItem"""

    def test_create_order_item(self, order, product_info):
        """Создаём позиции заказа"""
        item = OrderItem.objects.create(
            order=order,
            product_info=product_info,
            quantity=2
        )
        assert item.quantity == 2
        assert item.order == order

    def test_order_item_unique_constraint(self, order, product_info):
        """Проверка уникальности (order_id, product_info)"""
        OrderItem.objects.create(
            order=order,
            product_info=product_info,
            quantity=2
        )
        with pytest.raises(IntegrityError):
            OrderItem.objects.create(
                order=order,
                product_info=product_info,
                quantity=5
            )

@pytest.mark.django_db
class TestConfirmEmailTokenModel:
    """Тесты модели ConfirmEmailToken"""

    def test_create_token(self, user_buyer):
        """Создаём токен подтверждения"""
        token = ConfirmEmailToken.objects.create(user=user_buyer)
        assert token.key is not None
        assert len(token.key) > 0

    def test_token_key_unique(self, user_buyer):
        """Уникальность ключа токена"""
        token1 = ConfirmEmailToken.objects.create(user=user_buyer)
        user2 = User.objects.create_user(
            email='user2@test.com',
            password='TestPass123!'
        )
        token2 = ConfirmEmailToken.objects.create(user=user2)
        assert token1.key != token2.key

    def test_token_auto_generate_key(self, user_buyer):
        """Автоматическая генерация ключа при save"""
        token = ConfirmEmailToken(user=user_buyer)
        token.save()
        assert token.key is not None

