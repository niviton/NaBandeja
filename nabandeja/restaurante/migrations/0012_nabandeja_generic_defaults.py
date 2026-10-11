from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('restaurante', '0011_additional_productadditional_orderitemadditional'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appsettings',
            name='store_name',
            field=models.CharField(default='Meu Restaurante', max_length=200, verbose_name='Nome da Loja'),
        ),
        migrations.AlterField(
            model_name='appsettings',
            name='slogan',
            field=models.CharField(default='Feito com carinho, servido NaBandeja.', max_length=500, verbose_name='Slogan'),
        ),
    ]
