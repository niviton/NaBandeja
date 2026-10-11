"""Dados de teste reutilizáveis."""

from decimal import Decimal

from restaurante.models import AppSettings, Category, Ingredient, Product, ProductIngredient, User


class FakeCart:
    """Carrinho em memória com a mesma interface usada por place_order."""

    def __init__(self, *lines):
        self.items = []
        for line in lines:
            item, qty = line[0], line[1]
            notes = line[2] if len(line) > 2 else ''
            self.items.append({
                'cart_key': str(item.id), 'id': item.id, 'name': item.name,
                'price': float(item.price), 'qty': qty, 'notes': notes,
            })

    def __bool__(self):
        return bool(self.items)


def user(username='gerente', role='gerente', **extra):
    return User.objects.create_user(username, password='senha-forte-123', role=role, **extra)


def product(name='X-Burger', price='25.90', stock=10, category=None, **extra):
    category = category or Category.objects.get_or_create(name='Lanches')[0]
    return Product.objects.create(name=name, category=category, price=Decimal(price), stock=stock, **extra)


def product_with_recipe(name='Suco', price='8.00', ingredient_stock='1000', per_unit='300'):
    item = product(name=name, price=price, stock=0, use_ingredient_stock=True)
    fruit = Ingredient.objects.create(name=f'Polpa {name}', unit='g', stock_quantity=Decimal(ingredient_stock))
    ProductIngredient.objects.create(product=item, ingredient=fruit, quantity=Decimal(per_unit))
    return item, fruit


def open_store():
    store = AppSettings.get_settings()
    store.is_store_open = True
    store.save()
    return store
