"""
Script para criar dados iniciais do sistema.
Execute com: python manage.py shell < scripts/initial_data.py
Ou copie e cole no shell do Django.
"""

from restaurante.models import User, Category, Product, AppSettings
import os

# Criar configurações padrão
settings, _ = AppSettings.objects.get_or_create(pk=1)
settings.store_name = 'Meu Restaurante'
settings.slogan = 'Feito com carinho, servido NaBandeja.'
settings.primary_color = '#ef4444'
settings.secondary_color = '#fbbf24'
settings.save()
print('✓ Configurações criadas')

# Criar usuário gerente
if not User.objects.filter(username='gerente').exists():
    admin_password = os.getenv('NABANDEJA_INIT_ADMIN_PASSWORD') or os.getenv('BILLAR_INIT_ADMIN_PASSWORD', 'admin123')
    user = User.objects.create_user(
        username='gerente',
        password=admin_password,
        role='gerente',
        is_staff=True,
        is_superuser=True
    )
    print('✓ Usuário gerente criado')
    print(f'  Senha inicial: {admin_password}')

# Criar categorias
categories_data = [
    ('Hambúrgueres', '🍔', 1),
    ('Lanches', '🌭', 2),
    ('Porções', '🍟', 3),
    ('Bebidas', '🥤', 4),
    ('Sobremesas', '🍰', 5),
]

for name, icon, order in categories_data:
    Category.objects.get_or_create(name=name, defaults={'icon': icon, 'order': order})
print('✓ Categorias criadas')

# Criar produtos
products_data = [
    ('X-Burger Clássico', 'Hambúrgueres', 18.90, 50, '🍔'),
    ('X-Bacon Especial', 'Hambúrgueres', 22.90, 30, '🍔'),
    ('X-Tudo Supreme', 'Hambúrgueres', 28.90, 20, '🍔'),
    ('Hot Dog Completo', 'Lanches', 12.90, 40, '🌭'),
    ('Misto Quente', 'Lanches', 8.90, 60, '🥪'),
    ('Batata Frita Grande', 'Porções', 15.90, 100, '🍟'),
    ('Onion Rings', 'Porções', 14.90, 80, '🧅'),
    ('Refrigerante Lata', 'Bebidas', 5.90, 200, '🥤'),
    ('Suco Natural', 'Bebidas', 8.90, 50, '🧃'),
    ('Milkshake', 'Sobremesas', 12.90, 30, '🥤'),
]

for name, cat_name, price, stock, icon in products_data:
    category = Category.objects.get(name=cat_name)
    Product.objects.get_or_create(
        name=name,
        defaults={
            'category': category,
            'price': price,
            'stock': stock,
            'icon': icon
        }
    )
print('✓ Produtos criados')

print('\n🎉 Dados iniciais criados com sucesso!')
print('   Acesse o sistema com:')
print('   Usuário: gerente')
print('   Senha: variável NABANDEJA_INIT_ADMIN_PASSWORD ou admin123')
