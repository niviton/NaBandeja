from decimal import Decimal

from django import template

from ..services.payments import split_evenly as _split_evenly

register = template.Library()


@register.filter
def split_evenly(amount, people):
    """{{ total|split_evenly:3 }} -> lista com o valor de cada pessoa."""
    return _split_evenly(Decimal(str(amount or 0)), people)


@register.filter
def brl(value):
    """12345.6 -> 'R$ 12.345,60'"""
    try:
        number = Decimal(str(value or 0)).quantize(Decimal('0.01'))
    except ArithmeticError:
        return value
    integer, _, cents = f'{number:,.2f}'.partition('.')
    return f"R$ {integer.replace(',', '.')},{cents}"
