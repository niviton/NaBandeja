from django.db import models

from restaurante.services.company import normalize


class Loja(models.Model):
    """Uma loja hospedada no servidor. Os dados dela ficam em lojas/<code>.sqlite3."""

    code = models.SlugField('Código', max_length=40, unique=True,
                            help_text='Vai no endereço (/l/<código>/) e no campo Empresa do login.')
    code_key = models.CharField(max_length=40, unique=True, editable=False)
    name = models.CharField('Nome', max_length=120)
    is_active = models.BooleanField('Ativa', default=True)
    notes = models.TextField('Anotações', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Loja'
        verbose_name_plural = 'Lojas'

    def __str__(self):
        return f'{self.name} ({self.code})'

    def save(self, *args, **kwargs):
        self.code_key = normalize(self.code)
        super().save(*args, **kwargs)

    def url(self, path='/'):
        return f'/l/{self.code}{path}'
