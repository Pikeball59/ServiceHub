from typing import Type
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver, Signal
from django.template.loader import render_to_string
from django_rest_passwordreset.signals import reset_password_token_created
from backend.models import ConfirmEmailToken, User, Order, Image
from backend.tasks import send_email_task, process_image

new_user_registered = Signal()
new_order = Signal()

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, **kwargs):
    """Отправляет письмо с токеном для сброса пароля"""
    send_email_task.delay(
        f"Password Reset Token for {reset_password_token.user}",
        reset_password_token.key,
        [reset_password_token.user.email]
    )

@receiver(post_save, sender=User)
def new_user_registered_signal(sender: Type[User], instance: User, created: bool, **kwargs):
    """Отправляет письмо с подтверждением почты"""
    if created and not instance.is_active:
        token, _ = ConfirmEmailToken.objects.get_or_create(user_id=instance.pk)
        send_email_task.delay(
            f"Password Reset Token for {instance.email}",
            token.key,
            [instance.email]
        )

@receiver(new_order)
def new_order_signal(sender, user_id, order_id, **kwargs):
    """Отправляет письма при создании заказа: покупателю и администратору"""
    try:
        order = Order.objects.select_related('user', 'contact').prefetch_related(
            'ordered_items__product_info__product'
        ).get(id=order_id)
    except Order.DoesNotExist:
        return

    # Формирую накладную
    items = []
    for item in order.ordered_items.all():
        items.append({
            'name': item.product_info.product.name,
            'model': item.product_info.model,
            'quantity': item.quantity,
            'price': item.product_info.price,
            'total': item.quantity * item.product_info.price,
        })

    context = {
        'order_id': order.id,
        'user': order.user,
        'contact': order.contact,
        'items': items,
        'total_sum': sum(i['total'] for i in items),
    }

    # Письмо покупателю
    html_buyer = render_to_string('email/order_confirmation.html', context)
    send_email_task.delay(
        f'Подтверждение заказа №{order.id}',
        'Ваш заказ принят',
        [order.user.email],
        html_buyer
    )

    # Письмо администратору (накладная)
    html_admin = render_to_string('email/order_invoice.html', context)
    send_email_task.delay(
        f'Новый заказ №{order.id}',
        'Поступил новый заказ',
        [settings.ADMIN_EMAIL],
        html_admin
    )

@receiver(post_save, sender=Order)
def order_status_changed(sender, instance, created, **kwargs):
    """Отправляет письма при изменении статуса заказа (не при создании)"""
    if not created and instance.state != 'basket':
        status_display = instance.get_state_display()
        # Письмо покупателю об изменении статуса
        subject = f'Статус заказа №{instance.id} изменён'
        message = f'Ваш заказ №{instance.id} переведён в статус "{status_display}".'
        send_email_task.delay(subject, message, [instance.user.email])

        # Письмо администратору об изменении статуса
        admin_subject = f'Изменение статуса заказа №{instance.id}'
        admin_message = f'Заказ №{instance.id} изменён на статус "{status_display}".'
        send_email_task.delay(admin_subject, admin_message, [settings.ADMIN_EMAIL])

@receiver(post_save, sender=Image)
def image_post_save(sender, instance, created, **kwargs):
    if created:
        process_image.delay(instance.id)


