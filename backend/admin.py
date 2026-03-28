from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Sum, F
from backend.tasks import do_import_task
from backend.models import (
    User, Shop, Category, Product, ProductInfo,
    Parameter, ProductParameter, Order, OrderItem,
    Contact, ConfirmEmailToken
)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Панель управления пользователями"""
    model = User

    fieldsets = (
        (None, {'fields': ('email', 'password', 'type')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'company', 'position')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_staff')

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'state', 'url')
    actions = ['import_pricelist']

    def import_pricelist(self, request, queryset):
        for shop in queryset:
            if shop.url:
                do_import_task.delay(shop.url, shop.user.id)
                self.message_user(request, f'Запущен импорт для магазина {shop.name}')
            else:
                self.message_user(request, f'У магазина {shop.name} не указан URL', level='ERROR')
    import_pricelist.short_description = 'Импортировать прайс-лист (асинхронно)'

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass

@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    pass

@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    pass

@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    pass

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_info', 'quantity')
    can_delete = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'dt', 'state', 'contact', 'total_sum')
    list_filter = ('state', 'dt')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    inlines = [OrderItemInline]
    readonly_fields = ('id', 'dt', 'user')
    fieldsets = (
        (None, {'fields': ('id', 'user', 'dt', 'state', 'contact')}),
    )
    actions = ['mark_as_confirmed', 'mark_as_canceled']

    def total_sum(self, obj):
        total = obj.ordered_items.aggregate(total=Sum(F('quantity') * F('product_info__price')))['total']
        return total if total else 0
    total_sum.short_description = 'Сумма заказа'

    def mark_as_confirmed(self, request, queryset):
        for order in queryset:
            order.state = 'confirmed'
            order.save()  # сгенерирует сигнал post_save, который отправит письмо
        self.message_user(request, f'Подтверждено заказов: {queryset.count()}')
    mark_as_confirmed.short_description = 'Подтвердить выбранные заказы'

    def mark_as_canceled(self, request, queryset):
        for order in queryset:
            order.state = 'canceled'
            order.save()
        self.message_user(request, f'Отменено заказов: {queryset.count()}')
    mark_as_canceled.short_description = 'Отменить выбранные заказы'

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    pass

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    pass

@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'key', 'created_at')


