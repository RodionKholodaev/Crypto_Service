# Generated by Django 4.2.21 on 2025-07-06 17:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bots', '0012_remove_bot_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='bot',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
