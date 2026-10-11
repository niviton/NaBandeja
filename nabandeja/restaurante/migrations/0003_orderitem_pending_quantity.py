from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurante', '0002_appsettings_is_store_open'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='pending_quantity',
            field=models.IntegerField(default=0, verbose_name='Qtd. Pendente Cozinha'),
        ),
    ]
