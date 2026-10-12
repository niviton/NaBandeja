from django import forms
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_slug
from django.contrib.auth.forms import AuthenticationForm
from .models import AppSettings, Category, Ingredient, Product, User
from .services.pix import PixError, build_payload as build_pix_payload


class LoginForm(AuthenticationForm):
    """Login com empresa + usuário + senha."""

    empresa = forms.CharField(label='Empresa', max_length=60)

    field_order = ['empresa', 'username', 'password']
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if settings.IS_MASTER:  # painel master: só e-mail e senha
            self.fields['empresa'].required = False


class CategoryForm(forms.ModelForm):
    """Formulário de categoria"""
    class Meta:
        model = Category
        fields = ['name', 'icon', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ProductForm(forms.ModelForm):
    """Formulário de produto"""
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'price', 'cost_price', 'stock', 'use_ingredient_stock', 'icon', 'image', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
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


# Configurações em abas: cada aba salva só os seus campos (checkbox de outra aba não é zerado).
SETTINGS_TABS = {
    'loja': ['store_name', 'slogan', 'logo', 'cnpj', 'phone', 'address', 'city',
             'primary_color', 'secondary_color', 'background_color', 'text_color'],
    'pagamento': ['pix_key', 'pix_key_type', 'pix_name', 'pix_city', 'show_pix_on_receipt'],
    'salao': ['quick_notes', 'kitchen_late_minutes', 'kitchen_auto_print'],
    'cardapio': ['public_menu_enabled', 'wifi_ssid', 'wifi_password'],
    'delivery': ['online_orders_enabled', 'whatsapp_number', 'min_delivery_order'],
}


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
            'pix_key_type',
            'pix_name',
            'pix_city',
            'show_pix_on_receipt',
            'quick_notes',
            'kitchen_late_minutes',
            'kitchen_auto_print',
            'public_menu_enabled',
            'online_orders_enabled',
            'whatsapp_number',
            'min_delivery_order',
            'wifi_ssid',
            'wifi_password',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'slogan' in self.fields:
            self.fields['slogan'].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('pix_key'):
            store = self.instance
            try:
                build_pix_payload(
                    key=cleaned['pix_key'],
                    key_type=cleaned.get('pix_key_type') or 'auto',
                    name=cleaned.get('pix_name') or cleaned.get('store_name', store.store_name) or '',
                    city=cleaned.get('pix_city') or cleaned.get('city', store.city) or '',
                    amount='1.00',
                )
            except PixError as exc:
                raise forms.ValidationError(f'PIX: {exc}')
        return cleaned


class TeamMemberForm(forms.ModelForm):
    """Cria ou edita um membro da equipe. Senha obrigatória só na criação."""

    password = forms.CharField(label='Senha', required=False, strip=False, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email', 'role']
        labels = {'username': 'Usuário', 'first_name': 'Nome', 'email': 'E-mail (login com Google)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = User.ROLE_CHOICES
        if self.instance.pk:
            self.fields['username'].disabled = True
            self.fields['password'].label = 'Nova senha (deixe em branco para manter)'

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        validate_slug(username)
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este usuário já existe.')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email and User.objects.filter(email__iexact=email, is_active=True).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este e-mail já está em uso por outro membro.')
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        if not self.instance.pk and not password:
            self.add_error('password', 'Informe a senha.')
        if password:
            user = self.instance if self.instance.pk else User(username=cleaned.get('username', ''))
            try:
                validate_password(password, user)
            except forms.ValidationError as exc:
                self.add_error('password', exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
