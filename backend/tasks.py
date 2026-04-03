from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from requests import get
from requests.exceptions import RequestException
import yaml
from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter
import os
import logging
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

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

@shared_task
def process_image(image_id):
    from backend.models import Image as ImageModel
    try:
        img_obj = ImageModel.objects.get(id=image_id)
        img = PILImage.open(img_obj.original.path)
        # Создание миниатюры (100x100)
        thumb = img.copy()
        thumb.thumbnail((100, 100), PILImage.Resampling.LANCZOS)
        thumb_path = img_obj.original.path.replace('original', 'thumbnails')
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        thumb.save(thumb_path, optimize=True, quality=85)
        img_obj.thumbnail = thumb_path.replace(settings.MEDIA_ROOT, '')

        # Средний размер (300x300)
        medium = img.copy()
        medium.thumbnail((300, 300), PILImage.Resampling.LANCZOS)
        medium_path = img_obj.original.path.replace('original', 'medium')
        medium.save(medium_path, optimize=True, quality=85)
        img_obj.medium = medium_path.replace(settings.MEDIA_ROOT, '')

        # Большой размер (800x800)
        large = img.copy()
        large.thumbnail((800, 800), PILImage.Resampling.LANCZOS)
        large_path = img_obj.original.path.replace('original', 'large')
        large.save(large_path, optimize=True, quality=85)
        img_obj.large = large_path.replace(settings.MEDIA_ROOT, '')

        img_obj.save()
    except Exception as e:
        logger.error(f"Error processing image {image_id}: {e}")


