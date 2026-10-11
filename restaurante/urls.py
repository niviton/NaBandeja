from django.urls import path
from django.views.generic import RedirectView

from .views import auth, cart, catalog, manager, orders, pwa, reports

urlpatterns = [
    # PWA
    path('manifest.webmanifest', pwa.pwa_manifest, name='pwa_manifest'),
    path('sw.js', pwa.pwa_service_worker, name='pwa_service_worker'),
    path('download-ca-cert', pwa.download_ca_cert, name='download_ca_cert'),

    # Acesso
    path('', auth.login_view, name='login'),
    path('login/', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('logout/', auth.logout_view, name='logout'),
    path('dashboard/', auth.dashboard, name='dashboard'),

    # Garçom
    path('garcom/', orders.waiter_view, name='waiter_view'),
    path('order/submit/', orders.submit_order, name='submit_order'),

    # Pedidos
    path('order/<int:order_id>/manage/', orders.manage_order, name='manage_order'),
    path('order/<int:order_id>/update/', orders.update_order_info, name='update_order_info'),
    path('order/<int:order_id>/item/add/<int:product_id>/', orders.add_product_to_order, name='add_product_to_order'),
    path('order/<int:order_id>/item/<int:item_id>/change/', orders.change_order_item_qty, name='change_order_item_qty'),
    path('order/<int:order_id>/close/', orders.close_order, name='close_order'),
    path('order/<int:order_id>/cancel/', orders.cancel_order, name='cancel_order'),
    path('order/<int:order_id>/print/', orders.print_order, name='print_order'),

    # Cozinha
    path('cozinha/', orders.kitchen_view, name='kitchen_view'),
    path('order/ready/<int:order_id>/', orders.mark_order_ready, name='mark_order_ready'),

    # Gerente
    path('admin-panel/', manager.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/cash/open/', manager.open_cash_session, name='open_cash_session'),
    path('admin-panel/cash/close/', manager.close_cash_session, name='close_cash_session'),
    path('admin-panel/store/toggle/', manager.toggle_store_status, name='toggle_store_status'),
    path('admin-panel/online/', manager.admin_online_orders, name='admin_online_orders'),
    path('admin-panel/settings/', manager.admin_settings, name='admin_settings'),
    path('admin-panel/users/', manager.admin_users, name='admin_users'),
    path('admin-panel/user/new/', manager.user_create, name='user_create'),
    path('admin-panel/user/<int:user_id>/delete/', manager.user_delete, name='user_delete'),
    path('admin-panel/reports/', reports.admin_reports, name='admin_reports'),

    # Cardápio e estoque
    path('admin-panel/menu/', catalog.admin_menu, name='admin_menu'),
    path('admin-panel/product/new/', catalog.product_create, name='product_create'),
    path('admin-panel/product/<int:product_id>/edit/', catalog.product_edit, name='product_edit'),
    path('admin-panel/product/<int:product_id>/delete/', catalog.product_delete, name='product_delete'),
    path('admin-panel/category/new/', catalog.category_create, name='category_create'),
    path('admin-panel/category/<int:category_id>/edit/', catalog.category_edit, name='category_edit'),
    path('admin-panel/category/<int:category_id>/delete/', catalog.category_delete, name='category_delete'),
    path('admin-panel/ingredients/', catalog.admin_ingredients, name='admin_ingredients'),
    path('admin-panel/ingredient/new/', catalog.ingredient_create, name='ingredient_create'),
    path('admin-panel/ingredient/<int:ingredient_id>/edit/', catalog.ingredient_edit, name='ingredient_edit'),
    path('admin-panel/ingredient/<int:ingredient_id>/delete/', catalog.ingredient_delete, name='ingredient_delete'),

    # API do carrinho (AJAX)
    path('api/cart/', cart.api_get_cart, name='api_get_cart'),
    path('api/cart/add/<int:product_id>/', cart.api_add_to_cart, name='api_add_to_cart'),
    path('api/cart/remove/<int:product_id>/', cart.api_remove_from_cart, name='api_remove_from_cart'),
    path('api/cart/change/', cart.api_change_cart_item, name='api_change_cart_item'),
    path('api/cart/clear/', cart.api_clear_cart, name='api_clear_cart'),
]
