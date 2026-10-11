"""Carrinho do garçom/gerente, guardado na sessão até o pedido ser enviado."""

from ..models import Product

SESSION_KEY = 'cart'


class CartError(Exception):
    pass


class SessionCart:
    def __init__(self, session):
        self.session = session
        self.items = list(session.get(SESSION_KEY, []))
        # Carrinhos antigos não tinham cart_key/notes.
        for item in self.items:
            item.setdefault('cart_key', str(item['id']))
            item.setdefault('notes', '')

    def _save(self):
        self.session[SESSION_KEY] = self.items
        self.session.modified = True

    def _find(self, cart_key):
        return next((item for item in self.items if item['cart_key'] == str(cart_key)), None)

    @staticmethod
    def make_key(product_id, notes=''):
        notes = (notes or '').strip().lower()
        return f'{product_id}:{notes}' if notes else str(product_id)

    def add(self, product, quantity=1, notes=''):
        if not product.is_active:
            raise CartError(f'{product.name} não está disponível.')
        notes = (notes or '').strip()[:200]
        cart_key = self.make_key(product.id, notes)
        in_cart = sum(i['qty'] for i in self.items if i['id'] == product.id)
        if in_cart + quantity > product.available_stock:
            raise CartError('Produto sem estoque' if in_cart == 0 else 'Limite de estoque atingido')

        item = self._find(cart_key)
        if item:
            item['qty'] += quantity
        else:
            self.items.append({
                'cart_key': cart_key,
                'id': product.id,
                'name': product.name,
                'price': float(product.price),
                'qty': quantity,
                'icon': product.icon,
                'image': product.image.url if product.image else None,
                'notes': notes,
            })
        self._save()

    def change(self, cart_key, delta):
        item = self._find(cart_key)
        if not item:
            return
        if delta > 0:
            product = Product.objects.filter(pk=item['id'], is_active=True).first()
            if not product:
                raise CartError('Produto indisponível')
            self.add(product, delta, item.get('notes', ''))
            return
        item['qty'] += delta
        if item['qty'] <= 0:
            self.items.remove(item)
        self._save()

    def set_notes(self, cart_key, notes):
        item = self._find(cart_key)
        if not item:
            return
        notes = (notes or '').strip()[:200]
        new_key = self.make_key(item['id'], notes)
        existing = self._find(new_key)
        if existing and existing is not item:
            existing['qty'] += item['qty']
            self.items.remove(item)
        else:
            item['notes'] = notes
            item['cart_key'] = new_key
        self._save()

    def clear(self):
        self.items = []
        self._save()

    @property
    def total(self):
        return round(sum(item['price'] * item['qty'] for item in self.items), 2)

    def as_json(self):
        return {'success': True, 'cart': self.items, 'total': self.total}

    def __bool__(self):
        return bool(self.items)
