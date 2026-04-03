import logging

import rollbar
from rest_framework.request import Request
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle
from rest_framework import status

import json

from drf_spectacular.utils import extend_schema, OpenApiParameter
from backend.models import Shop, Category, ProductInfo, Order, OrderItem, \
    Contact, ConfirmEmailToken, Image, ProductImage, UserAvatar
from backend.serializers import UserSerializer, CategorySerializer, ShopSerializer, ProductInfoSerializer, \
    OrderItemSerializer, OrderSerializer, ContactSerializer
from backend.signals import new_order
from backend.tasks import do_import_task

# Добавленные импорты для социальной авторизации
import requests
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

# Добавлю кастомный throttle
class BurstRateThrottle(UserRateThrottle):
    rate = '10/min'

class RegisterAccount(APIView):
    """
    Для регистрации покупателей
    """
    # Регистрация методом POST
    def post(self, request, *args, **kwargs):
        if {'first_name', 'last_name', 'email', 'password', 'company', 'position'}.issubset(request.data):

            # проверяет пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                # проверяет данные для уникальности имени пользователя
                user_serializer = UserSerializer(data=request.data)
                if user_serializer.is_valid():
                    # сохраняем пользователя
                    user = user_serializer.save()
                    user.set_password(request.data['password'])
                    user.save()
                    return JsonResponse({'Status': True})
                else:
                    return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    """
    # Регистрация методом POST
    def post(self, request, *args, **kwargs):

        if {'email', 'token'}.issubset(request.data):

            token = ConfirmEmailToken.objects.filter(user__email=request.data['email'],
                                                     key=request.data['token']).first()
            if token:
                token.user.is_active = True
                token.user.save()
                token.delete()
                return JsonResponse({'Status': True})
            else:
                return JsonResponse({'Status': False, 'Errors': 'Неправильно указан токен или email'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class AccountDetails(APIView):
    """
    Класс для управления данными учётной записи пользователя
    """
    # получает данные
    def get(self, request: Request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # Редактирование методом POST
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        # проверяет обязательные аргументы
        if 'password' in request.data:
            errors = {}
            # проверяет пароль на сложность
            try:
                validate_password(request.data['password'])
            except Exception as password_error:
                error_array = []
                # noinspection PyTypeChecker
                for item in password_error:
                    error_array.append(item)
                return JsonResponse({'Status': False, 'Errors': {'password': error_array}})
            else:
                request.user.set_password(request.data['password'])
        # проверяет остальные данные
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': user_serializer.errors})

class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """
    # Авторизация методом POST
    def post(self, request, *args, **kwargs):
        if {'email', 'password'}.issubset(request.data):
            user = authenticate(request, username=request.data['email'], password=request.data['password'])

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)

                    return JsonResponse({'Status': True, 'Token': token.key})

            return JsonResponse({'Status': False, 'Errors': 'Не удалось авторизовать'})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer

class ProductInfoView(APIView):
    """
        Класс для поиска товаров
    """
    throttle_classes = [BurstRateThrottle]   # <-- добавлено

    @extend_schema(
        parameters=[
            OpenApiParameter('shop_id', int, description='ID магазина'),
            OpenApiParameter('category_id', int, description='ID категории'),
            OpenApiParameter('search', str, description='Поиск по названию товара'),
        ],
        responses={200: ProductInfoSerializer(many=True)},
        description='Получить список товаров с фильтрацией и поиском'
    )
    def get(self, request: Request, *args, **kwargs):
        query = Q(shop__state=True)
        shop_id = request.query_params.get('shop_id')
        category_id = request.query_params.get('category_id')
        search = request.query_params.get('search')  # новый параметр для поиска

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        if search:
            query = query & Q(product__name__icontains=search)

        # фильтрует и отбрасывает дуликаты
        queryset = ProductInfo.objects.filter(
            query).select_related(
            'shop', 'product__category').prefetch_related(
            'product_parameters__parameter').distinct()

        serializer = ProductInfoSerializer(queryset, many=True)

        return Response(serializer.data)

# Класс для получения детальной информации о товаре по id
class ProductDetailView(RetrieveAPIView):
    """Получение детальной информации о товаре (ProductInfo) по id"""
    queryset = ProductInfo.objects.filter(shop__state=True).select_related(
        'shop', 'product__category'
    ).prefetch_related('product_parameters__parameter')
    serializer_class = ProductInfoSerializer

class BasketView(APIView):
    """
    Класс для управления корзиной пользователя
    """
    # получает корзину
    @extend_schema(auth=['tokenAuth'], description='Получить содержимое корзины')
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        basket = Order.objects.filter(
            user_id=request.user.id, state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    # редактирует корзину
    @extend_schema(auth=['tokenAuth'], description='Добавить товары в корзину')
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = json.loads(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_created = 0
                for order_item in items_dict:
                    order_item.update({'order': basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({'Status': False, 'Errors': str(error)})
                        else:
                            objects_created += 1

                    else:

                        return JsonResponse({'Status': False, 'Errors': serializer.errors})

                return JsonResponse({'Status': True, 'Создано объектов': objects_created})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удаляет товары из корзины
    @extend_schema(auth=['tokenAuth'], description='Удалить товары из корзины')
    def delete(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            try:
                basket = Order.objects.get(user_id=request.user.id, state='basket')
            except Order.DoesNotExist:
                return JsonResponse({'Status': False, 'Errors': 'Корзина пуста'})

            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # добавляет позиции в корзину
    @extend_schema(auth=['tokenAuth'], description='Обновить количество товаров в корзине')
    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            try:
                items_dict = json.loads(items_sting)
            except ValueError:
                return JsonResponse({'Status': False, 'Errors': 'Неверный формат запроса'})
            else:
                basket, _ = Order.objects.get_or_create(user_id=request.user.id, state='basket')
                objects_updated = 0
                for order_item in items_dict:
                    if type(order_item['id']) == int and type(order_item['quantity']) == int:
                        objects_updated += OrderItem.objects.filter(order_id=basket.id, id=order_item['id']).update(
                            quantity=order_item['quantity'])

                return JsonResponse({'Status': True, 'Обновлено объектов': objects_updated})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class PartnerUpdate(APIView):
    """
    Класс для обновления информации магазина (прайс-листа)
    """
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        url = request.data.get('url')
        if url:
            validate_url = URLValidator()
            try:
                validate_url(url)
            except ValidationError as e:
                return JsonResponse({'Status': False, 'Error': str(e)})
            else:
                # Запускаем асинхронную задачу импорта
                do_import_task.delay(url, request.user.id)
                return JsonResponse({'Status': True, 'Message': 'Импорт запущен в фоне'})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class PartnerState(APIView):
    """
       Класс для управления статусом магазина (приём заказов)
    """
    # получает текущий статус
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    # изменяет текущий статус
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        state = request.data.get('state')
        if state:
            # Преобразует строку в булево значение
            is_active = state.lower() in ('true', '1', 't', 'yes', 'on')
            Shop.objects.filter(user_id=request.user.id).update(state=is_active)
            return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class PartnerOrders(APIView):
    """
    Класс для получения заказов поставщиками
    """
    def get(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if request.user.type != 'shop':
            return JsonResponse({'Status': False, 'Error': 'Только для магазинов'}, status=403)

        order = Order.objects.filter(
            ordered_items__product_info__shop__user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

class ContactView(APIView):
    """
       Класс для управления контактной информацией.
    """
    # получаю мои контакты
    def get(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        contact = Contact.objects.filter(
            user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    # добавляю новый контакт
    def post(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'type', 'phone'}.issubset(request.data) or (
            request.data.get('type') == 'address' and {'city', 'street', 'phone'}.issubset(request.data)
        ):
            data = request.data.copy()
            data['user'] = request.user.id
            serializer = ContactSerializer(data=data)

            if serializer.is_valid():
                try:
                    serializer.save()
                    return JsonResponse({'Status': True})
                except ValidationError as e:
                    return JsonResponse({'Status': False, 'Errors': str(e)})
            else:
                return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # удаляю контакт
    def delete(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        items_sting = request.data.get('items')
        if items_sting:
            items_list = items_sting.split(',')
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({'Status': True, 'Удалено объектов': deleted_count})
        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # редактирую контакт
    def put(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if 'id' in request.data:
            if isinstance(request.data['id'], int) or str(request.data['id']).isdigit():
                contact = Contact.objects.filter(id=request.data['id'], user_id=request.user.id).first()
                if contact:
                    serializer = ContactSerializer(contact, data=request.data, partial=True)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                            return JsonResponse({'Status': True})
                        except ValidationError as e:
                            return JsonResponse({'Status': False, 'Errors': str(e)})
                    else:
                        return JsonResponse({'Status': False, 'Errors': serializer.errors})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

class OrderView(APIView):
    """
    Класс для получения и размещения заказов пользователями
    """
    # получаю мои заказы
    @extend_schema(auth=['tokenAuth'], description='Получить список заказов пользователя')
    def get(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)
        order = Order.objects.filter(
            user_id=request.user.id).exclude(state='basket').prefetch_related(
            'ordered_items__product_info__product__category',
            'ordered_items__product_info__product_parameters__parameter').select_related('contact').annotate(
            total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))).distinct()

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    # размещаю заказ из корзины
    @extend_schema(auth=['tokenAuth'], description='Подтвердить корзину и создать заказ')
    def post(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        if {'id', 'contact'}.issubset(request.data):
            if isinstance(request.data['id'], int) or str(request.data['id']).isdigit():
                contact_id = request.data['contact']
                # Проверяю, что контакт принадлежит пользователю
                if not Contact.objects.filter(id=contact_id, user_id=request.user.id).exists():
                    return JsonResponse({'Status': False, 'Errors': 'Контакт не найден или не принадлежит вам'})

                # Исправление: обновляем только корзину (state='basket')
                updated = Order.objects.filter(
                    user_id=request.user.id,
                    id=request.data['id'],
                    state='basket'
                ).update(contact_id=contact_id, state='new')

                if not updated:
                    return JsonResponse({'Status': False, 'Errors': 'Корзина не найдена или уже оформлена'})

                new_order.send(sender=self.__class__, user_id=request.user.id, order_id=request.data['id'])
                return JsonResponse({'Status': True})

        return JsonResponse({'Status': False, 'Errors': 'Не указаны все необходимые аргументы'})

    # отмена заказа
    @extend_schema(auth=['tokenAuth'], description='Отменить заказ')
    def patch(self, request, *args, **kwargs):
        """Изменение статуса заказа (только отмена для покупателя)"""
        if not request.user.is_authenticated:
            return JsonResponse({'Status': False, 'Error': 'Log in required'}, status=403)

        order_id = request.data.get('id')
        new_status = request.data.get('state')
        if not order_id or not new_status:
            return JsonResponse({'Status': False, 'Errors': 'Не указаны id заказа или новый статус'})

        try:
            order = Order.objects.get(id=order_id, user_id=request.user.id)
        except Order.DoesNotExist:
            return JsonResponse({'Status': False, 'Errors': 'Заказ не найден'})

        # Разрешаю только отмену (для покупателя) и только если заказ ещё не отправлен
        if new_status == 'canceled' and order.state in ['new', 'confirmed', 'assembled']:
            order.state = 'canceled'
            order.save()
            return JsonResponse({'Status': True})
        else:
            return JsonResponse({'Status': False, 'Errors': 'Недопустимое изменение статуса'})

class AvatarUploadView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required'}, status=status.HTTP_403_FORBIDDEN)
        if 'image' not in request.FILES:
            return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)

        image = Image.objects.create(original=request.FILES['image'])
        avatar, created = UserAvatar.objects.get_or_create(user=request.user, defaults={'image': image})
        if not created:
            avatar.image = image
            avatar.save()
        return Response({'status': 'ok', 'image_id': image.id})

class ProductImageView(APIView):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return Response({'error': 'Login required'}, status=status.HTTP_403_FORBIDDEN)
        # Проверяет, что пользователь — владелец магазина этого товара
        try:
            product_info = ProductInfo.objects.get(id=pk, shop__user=request.user)
        except ProductInfo.DoesNotExist:
            return Response({'error': 'Product not found or access denied'}, status=status.HTTP_404_NOT_FOUND)

        if 'image' not in request.FILES:
            return Response({'error': 'No image provided'}, status=status.HTTP_400_BAD_REQUEST)

        image = Image.objects.create(original=request.FILES['image'])
        ProductImage.objects.create(product_info=product_info, image=image)
        return Response({'status': 'ok', 'image_id': image.id})

class TestRollbarView(APIView):
    def get(self, request):
        try:
            raise Exception("This is a test exception for Rollbar")
        except Exception as e:
            rollbar.report_exc_info()
            return Response({'error': str(e), 'reported_to_rollbar': True}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Социальная авторизация
User = get_user_model()

class SocialAuthView(APIView):
    provider = None

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token missing'}, status=status.HTTP_400_BAD_REQUEST)

        if self.provider == 'google':
            url = 'https://www.googleapis.com/oauth2/v3/userinfo'
            headers = {'Authorization': f'Bearer {token}'}
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
            data = resp.json()
            email = data.get('email')
            first_name = data.get('given_name', '')
            last_name = data.get('family_name', '')
            provider_user_id = data.get('sub')
        elif self.provider == 'github':
            resp = requests.get('https://api.github.com/user', headers={'Authorization': f'token {token}'})
            if resp.status_code != 200:
                return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
            data = resp.json()
            # Get email
            email_resp = requests.get('https://api.github.com/user/emails', headers={'Authorization': f'token {token}'})
            if email_resp.status_code == 200:
                emails = email_resp.json()
                email = next((e['email'] for e in emails if e['primary']), None)
            else:
                email = None
            first_name = data.get('name', '').split()[0] if data.get('name') else ''
            last_name = ' '.join(data.get('name', '').split()[1:]) if data.get('name') else ''
            provider_user_id = str(data.get('id'))
        else:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)

        if not email:
            return Response({'error': 'Email not provided'}, status=status.HTTP_400_BAD_REQUEST)

        user, created = User.objects.get_or_create(email=email, defaults={
            'first_name': first_name,
            'last_name': last_name,
            'is_active': True,
            'username': email.split('@')[0],
        })
        if created:
            user.set_unusable_password()
            user.save()

        SocialAccount.objects.get_or_create(
            user=user,
            provider=self.provider,
            uid=provider_user_id,
            defaults={'extra_data': data}
        )

        token_obj, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token_obj.key})

class GoogleAuthView(SocialAuthView):
    provider = 'google'

class GitHubAuthView(SocialAuthView):
    provider = 'github'


