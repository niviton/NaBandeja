from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurante', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='appsettings',
            name='is_store_open',
            field=models.BooleanField(default=True, verbose_name='Loja Aberta'),
        ),
    ]
