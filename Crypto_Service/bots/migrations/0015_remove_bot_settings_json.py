# Generated by Django 4.2.21 on 2025-07-06 17:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bots', '0014_bot_settings_json'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='bot',
            name='settings_json',
        ),
    ]
