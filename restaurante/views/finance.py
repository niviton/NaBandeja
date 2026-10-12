"""Gerente: contas a pagar e fluxo de caixa do mês."""

from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..modules import module_required
from ..models import Expense, Payment
from ..permissions import manager_required
from ..services.audit import audit


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['description', 'category', 'amount', 'due_date', 'paid_at', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'paid_at': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


def add_months(first_day, months):
    index = first_day.year * 12 + first_day.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _month(request):
    today = timezone.localdate()
    try:
        year, month = (int(part) for part in request.GET.get('mes', '').split('-'))
        return date(year, month, 1)
    except ValueError:
        return today.replace(day=1)


@manager_required
@module_required('financeiro')
def expenses(request):
    month_start = _month(request)
    next_month = add_months(month_start, 1)
    today = timezone.localdate()
    status = request.GET.get('status', 'abertas')

    qs = Expense.objects.all()
    if status == 'abertas':
        qs = qs.filter(paid_at__isnull=True).order_by('due_date')
    elif status == 'pagas':
        qs = qs.filter(paid_at__gte=month_start, paid_at__lt=next_month).order_by('-paid_at')
    else:
        qs = qs.filter(due_date__gte=month_start, due_date__lt=next_month).order_by('due_date')

    revenue = Payment.objects.filter(
        order__status='finalizado', order__closed_at__date__gte=month_start, order__closed_at__date__lt=next_month,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    paid = Expense.objects.filter(paid_at__gte=month_start, paid_at__lt=next_month).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    open_total = Expense.objects.filter(paid_at__isnull=True).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    overdue = Expense.objects.filter(paid_at__isnull=True, due_date__lt=today)

    return render(request, 'restaurante/admin/expenses.html', {
        'expenses': qs,
        'status': status,
        'month': month_start,
        'prev_month': add_months(month_start, -1),
        'next_month': next_month,
        'revenue': revenue,
        'paid': paid,
        'balance': revenue - paid,
        'open_total': open_total,
        'overdue_count': overdue.count(),
        'overdue_total': overdue.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        'form': ExpenseForm(initial={'due_date': today}),
        'status_tabs': [('abertas', 'Em aberto'), ('mes', 'Vencem no mês'), ('pagas', 'Pagas no mês')],
        'active_menu': 'expenses',
    })


@manager_required
@module_required('financeiro')
def expense_edit(request, expense_id=None):
    expense = get_object_or_404(Expense, pk=expense_id) if expense_id else None
    form = ExpenseForm(request.POST or None, instance=expense)
    if request.method == 'POST' and form.is_valid():
        saved = form.save(commit=False)
        if expense is None:
            saved.created_by = request.user
        saved.save()
        audit(request, 'expense.save', f'Conta "{saved.description}" salva.', saved, amount=saved.amount)
        messages.success(request, 'Conta salva!')
        return redirect('expenses')
    return render(request, 'restaurante/admin/expense_form.html', {
        'form': form, 'expense': expense, 'active_menu': 'expenses',
    })


@manager_required
@require_POST
@module_required('financeiro')
def expense_pay(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id)
    expense.paid_at = None if expense.paid_at else timezone.localdate()
    expense.save(update_fields=['paid_at'])
    messages.success(request, f'"{expense.description}" marcada como {"paga" if expense.paid_at else "em aberto"}.')
    return redirect(request.POST.get('next') or 'expenses')


@manager_required
@require_POST
@module_required('financeiro')
def expense_delete(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id)
    audit(request, 'expense.delete', f'Conta "{expense.description}" excluída.', expense, amount=expense.amount)
    expense.delete()
    messages.success(request, 'Conta excluída.')
    return redirect('expenses')
