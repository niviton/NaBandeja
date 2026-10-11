from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User, Category, Product, Order, OrderItem, AppSettings, Ingredient


class LoginForm(AuthenticationForm):
    """Formulário de login personalizado"""
    username = forms.CharField(
        label='Usuário',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Usuário',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Senha'
        })
    )


class UserForm(UserCreationForm):
    """Formulário de criação de usuário"""
    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'role']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
        }


class CategoryForm(forms.ModelForm):
    """Formulário de categoria"""
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ProductForm(forms.ModelForm):
    """Formulário de produto"""
    class Meta:
        model = Product
        fields = ['name', 'category', 'price', 'stock', 'use_ingredient_stock', 'icon', 'image', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'use_ingredient_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class IngredientForm(forms.ModelForm):
    """Formulário de ingrediente"""
    class Meta:
        model = Ingredient
        fields = ['name', 'unit', 'stock_quantity', 'low_stock_alert', 'cost_price', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.Select(attrs={'class': 'form-control'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'low_stock_alert': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OrderForm(forms.ModelForm):
    """Formulário de pedido"""
    class Meta:
        model = Order
        fields = ['mesa', 'cliente', 'observacoes', 'order_type', 'address']
        widgets = {
            'mesa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número da Mesa'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Cliente'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observações...'}),
            'order_type': forms.Select(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Endereço de entrega...'}),
        }


class DeliveryOrderForm(forms.ModelForm):
    """Formulário de pedido delivery"""
    PLATFORM_CHOICES = [
        ('Whatsapp', 'WhatsApp'),
        ('iFood', 'iFood'),
        ('Rappi', 'Rappi'),
        ('Telefone', 'Telefone'),
        ('Outro', 'Outro'),
    ]
    platform = forms.ChoiceField(choices=PLATFORM_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))

    class Meta:
        model = Order
        fields = ['cliente', 'address', 'observacoes']
        widgets = {
            'cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do Cliente'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Endereço completo...'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observações...'}),
        }


class PaymentForm(forms.Form):
    """Formulário de pagamento"""
    PAYMENT_CHOICES = [
        ('dinheiro', '💵 Dinheiro'),
        ('pix', '📱 PIX'),
        ('credito', '💳 Cartão de Crédito'),
        ('debito', '💳 Cartão de Débito'),
    ]
    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )


class AppSettingsForm(forms.ModelForm):
    """Formulário de configurações"""
    class Meta:
        model = AppSettings
        fields = [
            'store_name',
            'slogan',
            'logo',
            'cnpj',
            'phone',
            'address',
            'city',
            'primary_color',
            'secondary_color',
            'background_color',
            'text_color',
            'pix_key',
            'pix_name',
            'pix_qrcode',
            'show_pix_on_receipt',
        ]
        widgets = {
            'store_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do estabelecimento'}),
            'slogan': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Slogan da loja'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Rua, número, bairro'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Cidade - UF'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'background_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'text_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'pix_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chave PIX (CPF, CNPJ, telefone ou e-mail)'}),
            'pix_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome do titular da conta'}),
            'show_pix_on_receipt': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
