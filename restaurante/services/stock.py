"""
Baixa e devolução de estoque.

As atualizações usam expressões F() com condição no próprio UPDATE
("estoque >= quantidade"), então dois garçons vendendo o último item ao
mesmo tempo não conseguem deixar o estoque negativo nem perder uma baixa.
Deve ser chamado dentro de uma transação (ATOMIC_REQUESTS já garante isso).
"""

from decimal import Decimal

from django.db.models import F

from ..models import Ingredient, IngredientStockMovement, Product


class OutOfStock(Exception):
    pass


def _log_ingredient(ingredient_id, movement_type, quantity, user=None, reason=''):
    ingredient = Ingredient.objects.get(pk=ingredient_id)
    if movement_type == 'consumo':
        before = ingredient.stock_quantity + quantity
    else:
        before = ingredient.stock_quantity - quantity
    IngredientStockMovement.objects.create(
        ingredient=ingredient,
        movement_type=movement_type,
        quantity=quantity,
        quantity_before=before,
        quantity_after=ingredient.stock_quantity,
        reason=reason,
        created_by=user if user is not None and user.is_authenticated else None,
    )


def consume(product, quantity, user=None, reason=''):
    """Dá baixa de `quantity` unidades do produto (ou dos ingredientes da receita)."""
    if quantity <= 0:
        return
    if not product.use_ingredient_stock:
        updated = Product.objects.filter(pk=product.pk, stock__gte=quantity).update(
            stock=F('stock') - quantity
        )
        if not updated:
            raise OutOfStock(f'Estoque insuficiente para {product.name}.')
        return

    recipe = list(product.recipe_items.all())
    if not recipe:
        raise OutOfStock(f'Receita não definida para {product.name}.')

    for recipe_item in recipe:
        required = recipe_item.quantity * Decimal(quantity)
        updated = Ingredient.objects.filter(
            pk=recipe_item.ingredient_id, stock_quantity__gte=required
        ).update(stock_quantity=F('stock_quantity') - required)
        if not updated:
            # A transação desfaz as baixas dos ingredientes anteriores.
            raise OutOfStock(f'Estoque insuficiente para {product.name}.')
        _log_ingredient(recipe_item.ingredient_id, 'consumo', required, user, reason)


def restore(product, quantity, user=None, reason=''):
    """Devolve ao estoque unidades que não chegaram a ser produzidas."""
    if quantity <= 0:
        return
    if not product.use_ingredient_stock:
        Product.objects.filter(pk=product.pk).update(stock=F('stock') + quantity)
        return

    for recipe_item in product.recipe_items.all():
        required = recipe_item.quantity * Decimal(quantity)
        Ingredient.objects.filter(pk=recipe_item.ingredient_id).update(
            stock_quantity=F('stock_quantity') + required
        )
        _log_ingredient(recipe_item.ingredient_id, 'estorno', required, user, reason)
