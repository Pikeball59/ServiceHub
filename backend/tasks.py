from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from requests import get
from requests.exceptions import RequestException
import yaml
from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter

@shared_task
def send_email_task(subject, message, recipient_list, html_message=None):
    """Асинхронная отправка email с поддержкой HTML"""
    msg = EmailMultiAlternatives(subject, message, settings.EMAIL_HOST_USER, recipient_list)
    if html_message:
        msg.attach_alternative(html_message, "text/html")
    msg.send()

@shared_task
def do_import_task(url, user_id):
    """Асинхронный импорт прайс-листа"""
    from django.core.validators import URLValidator
    from django.core.exceptions import ValidationError

    try:
        # Валидация URL
        validate_url = URLValidator()
        try:
            validate_url(url)
        except ValidationError as e:
            return {'status': False, 'error': str(e)}

        # Загрузка файла
        try:
            response = get(url)
            response.raise_for_status()
        except RequestException as e:
            return {'status': False, 'error': f'Failed to download file: {e}'}

        # Парсинг YAML
        try:
            data = yaml.safe_load(response.content)
        except yaml.YAMLError as e:
            return {'status': False, 'error': f'Invalid YAML: {e}'}

        # Обработка данных
        shop, _ = Shop.objects.get_or_create(name=data['shop'], user_id=user_id)
        for category in data['categories']:
            category_object, _ = Category.objects.get_or_create(id=category['id'], name=category['name'])
            category_object.shops.add(shop.id)
            category_object.save()
        ProductInfo.objects.filter(shop_id=shop.id).delete()
        for item in data['goods']:
            product, _ = Product.objects.get_or_create(name=item['name'], category_id=item['category'])
            product_info = ProductInfo.objects.create(
                product_id=product.id,
                external_id=item['id'],
                model=item['model'],
                price=item['price'],
                price_rrc=item['price_rrc'],
                quantity=item['quantity'],
                shop_id=shop.id
            )
            for name, value in item['parameters'].items():
                parameter_object, _ = Parameter.objects.get_or_create(name=name)
                ProductParameter.objects.create(
                    product_info_id=product_info.id,
                    parameter_id=parameter_object.id,
                    value=value
                )
        return {'status': True}

    except Exception as e:
        return {'status': False, 'error': str(e)}