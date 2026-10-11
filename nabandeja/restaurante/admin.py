from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    Category,
    Product,
    Order,
    OrderItem,
    AppSettings,
    Ingredient,
    ProductIngredient,
    AuditLog,
    IngredientStockMovement,
    CashSession,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Função', {'fields': ('role',)}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'order']
    list_editable = ['order']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock', 'use_ingredient_stock', 'available_stock', 'is_active']
    list_filter = ['category', 'is_active']
    list_editable = ['price', 'stock', 'use_ingredient_stock', 'is_active']
    search_fields = ['name']


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ['name', 'unit', 'stock_quantity', 'cost_price', 'is_active']
    list_filter = ['unit', 'is_active']
    search_fields = ['name']
    list_editable = ['stock_quantity', 'cost_price', 'is_active']


@admin.register(ProductIngredient)
class ProductIngredientAdmin(admin.ModelAdmin):
    list_display = ['product', 'ingredient', 'quantity']
    list_filter = ['ingredient']
    search_fields = ['product__name', 'ingredient__name']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['subtotal']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'mesa', 'cliente', 'total', 'status', 'order_type', 'created_at']
    list_filter = ['status', 'order_type', 'created_at']
    search_fields = ['mesa', 'cliente']
    inlines = [OrderItemInline]


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ['store_name', 'slogan']

    def has_add_permission(self, request):
        # Só permite uma instância
        return not AppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'action', 'user', 'model_name', 'object_id']
    list_filter = ['action', 'model_name', 'created_at']
    search_fields = ['description', 'user__username', 'object_id']
    readonly_fields = ['created_at']


@admin.register(IngredientStockMovement)
class IngredientStockMovementAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'ingredient', 'movement_type', 'quantity', 'quantity_before', 'quantity_after', 'created_by']
    list_filter = ['movement_type', 'created_at']
    search_fields = ['ingredient__name', 'reason', 'created_by__username']
    readonly_fields = ['created_at']


@admin.register(CashSession)
class CashSessionAdmin(admin.ModelAdmin):
    list_display = ['opened_at', 'status', 'opening_amount', 'closing_amount', 'expected_amount', 'difference_amount', 'opened_by', 'closed_by']
    list_filter = ['status', 'opened_at']
    search_fields = ['opened_by__username', 'closed_by__username', 'notes']
    readonly_fields = ['opened_at', 'closed_at']
