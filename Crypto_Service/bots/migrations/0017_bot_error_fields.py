# Generated manually for adding error fields to Bot model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bots', '0016_deal_exit_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='bot',
            name='last_error',
            field=models.TextField(blank=True, help_text='Последняя ошибка, возникшая в работе бота', null=True),
        ),
        migrations.AddField(
            model_name='bot',
            name='error_timestamp',
            field=models.DateTimeField(blank=True, help_text='Время возникновения ошибки', null=True),
        ),
    ]
