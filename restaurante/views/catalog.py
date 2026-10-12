"""Cardápio (categorias e produtos) e ingredientes."""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..modules import module_required
from ..forms import CategoryForm, IngredientForm, ProductForm
from ..models import Category, Ingredient, IngredientStockMovement, Product, ProductIngredient
from ..permissions import manager_required
from ..services.audit import audit


class RecipeError(ValueError):
    pass


def _save_recipe(product, request):
    """Grava a receita enviada pelo formulário (listas recipe_ingredient[] e recipe_quantity[])."""
    if not product.use_ingredient_stock:
        return
    rows = {}
    for ingredient_id, raw_qty in zip(request.POST.getlist('recipe_ingredient[]'), request.POST.getlist('recipe_quantity[]')):
        try:
            ingredient_id = int(ingredient_id)
            quantity = Decimal(str(raw_qty).replace(',', '.'))
        except (ValueError, InvalidOperation):
            continue
        if quantity > 0:
            rows.setdefault(ingredient_id, quantity)

    ingredients = Ingredient.objects.filter(pk__in=rows, is_active=True).in_bulk()
    if not ingredients:
        raise RecipeError('Defina ao menos 1 ingrediente na receita para usar estoque por ingredientes.')

    ProductIngredient.objects.filter(product=product).delete()
    ProductIngredient.objects.bulk_create([
        ProductIngredient(product=product, ingredient=ingredients[pk], quantity=rows[pk])
        for pk in rows if pk in ingredients
    ])


def _product_form_page(request, form, title, product=None):
    return render(request, 'restaurante/admin/product_form.html', {
        'form': form,
        'title': title,
        'product': product,
        'active_menu': 'menu',
        'categories': Category.objects.filter(is_active=True),
        'ingredients': Ingredient.objects.filter(is_active=True).order_by('name'),
        'recipe_items': product.recipe_items.select_related('ingredient').order_by('ingredient__name') if product else [],
    })


# ------------------------------------------------------------------ cardápio

@manager_required
def admin_menu(request):
    return render(request, 'restaurante/admin/menu.html', {
        'categories': Category.objects.prefetch_related('products__recipe_items__ingredient'),
        'active_menu': 'menu',
    })


@manager_required
def product_create(request):
    return _product_edit(request, None)


@manager_required
def product_edit(request, product_id):
    return _product_edit(request, get_object_or_404(Product, pk=product_id))


def _product_edit(request, product):
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save()
                _save_recipe(saved, request)
        except RecipeError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, 'Produto salvo!')
            return redirect('admin_menu')
    return _product_form_page(request, form, 'Editar Produto' if product else 'Novo Produto', product)


@manager_required
@require_POST
def product_delete(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if product.orderitem_set.exists():
        product.is_active = False
        product.save(update_fields=['is_active', 'updated_at'])
        messages.info(request, f'"{product.name}" já tem vendas: foi desativado para preservar o histórico.')
    else:
        product.delete()
        messages.success(request, 'Produto removido!')
    audit(request, 'product.delete', f'Produto "{product.name}" removido/desativado.', product)
    return redirect('admin_menu')


@manager_required
def category_create(request):
    return _category_edit(request, None)


@manager_required
def category_edit(request, category_id):
    return _category_edit(request, get_object_or_404(Category, pk=category_id))


def _category_edit(request, category):
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoria salva!')
            return redirect('admin_menu')
        messages.error(request, 'Não foi possível salvar a categoria. Verifique os dados.')
    return render(request, 'restaurante/admin/category_form.html', {
        'form': form,
        'title': 'Editar Categoria' if category else 'Nova Categoria',
        'category': category,
        'active_menu': 'menu',
    })


@manager_required
@require_POST
def category_delete(request, category_id):
    category = get_object_or_404(Category, pk=category_id)
    if category.products.exists():
        category.is_active = False
        category.save(update_fields=['is_active'])
        category.products.update(is_active=False)
        messages.info(request, f'"{category.name}" tem produtos: a categoria e seus produtos foram desativados.')
    else:
        category.delete()
        messages.success(request, 'Categoria removida!')
    audit(request, 'category.delete', f'Categoria "{category.name}" removida/desativada.', category)
    return redirect('admin_menu')


# ------------------------------------------------------------------ ingredientes

def _log_movement(request, ingredient, movement_type, before, after, reason):
    IngredientStockMovement.objects.create(
        ingredient=ingredient,
        movement_type=movement_type,
        quantity=abs(after - before),
        quantity_before=before,
        quantity_after=after,
        reason=reason,
        created_by=request.user,
    )


@manager_required
@module_required('ingredientes')
def admin_ingredients(request):
    return render(request, 'restaurante/admin/ingredients.html', {
        'ingredients': Ingredient.objects.order_by('-is_active', 'name'),
        'active_menu': 'ingredients',
    })


@manager_required
@module_required('ingredientes')
def ingredient_create(request):
    return _ingredient_edit(request, None)


@manager_required
@module_required('ingredientes')
def ingredient_edit(request, ingredient_id):
    return _ingredient_edit(request, get_object_or_404(Ingredient, pk=ingredient_id))


def _ingredient_edit(request, ingredient):
    previous_stock = ingredient.stock_quantity if ingredient else Decimal('0')
    form = IngredientForm(request.POST or None, instance=ingredient)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        if saved.stock_quantity != previous_stock:
            movement = 'entrada' if ingredient is None else 'ajuste'
            reason = 'Estoque inicial' if ingredient is None else 'Ajuste manual na edição do ingrediente'
            _log_movement(request, saved, movement, previous_stock, saved.stock_quantity, reason)
        audit(request, 'ingredient.save', f'Ingrediente "{saved.name}" salvo.', saved,
              previous_stock=previous_stock, new_stock=saved.stock_quantity)
        messages.success(request, 'Ingrediente salvo!')
        return redirect('admin_ingredients')
    return render(request, 'restaurante/admin/ingredient_form.html', {
        'form': form,
        'title': 'Editar Ingrediente' if ingredient else 'Novo Ingrediente',
        'ingredient': ingredient,
        'active_menu': 'ingredients',
    })


@manager_required
@require_POST
@module_required('ingredientes')
def ingredient_delete(request, ingredient_id):
    ingredient = get_object_or_404(Ingredient, pk=ingredient_id)
    if ingredient.recipe_products.exists() or ingredient.stock_movements.exists():
        ingredient.is_active = False
        ingredient.save(update_fields=['is_active', 'updated_at'])
        messages.info(request, f'"{ingredient.name}" tem receitas ou histórico: foi desativado.')
    else:
        ingredient.delete()
        messages.success(request, 'Ingrediente removido!')
    audit(request, 'ingredient.delete', f'Ingrediente "{ingredient.name}" removido/desativado.', ingredient)
    return redirect('admin_ingredients')
