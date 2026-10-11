from django.db import migrations


def reactivate_products(apps, schema_editor):
    """
    Até a versão 2.0 a tela de produto não tinha o campo "ativo": todo produto
    salvo ficava is_active=False sem ninguém perceber, e o garçom ignorava o
    campo. A partir da 2.1 o campo vale de verdade, então todos voltam a ativos.
    """
    apps.get_model('restaurante', 'Product').objects.update(is_active=True)
    apps.get_model('restaurante', 'Category').objects.update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ('restaurante', '0014_protect_history_and_close_info'),
    ]

    operations = [
        migrations.RunPython(reactivate_products, migrations.RunPython.noop),
    ]
