# Generated by Django 4.2.7 on 2023-11-30 01:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_alter_user_password_alter_user_username'),
    ]

    operations = [
        migrations.RenameField(
            model_name='follow',
            old_name='subscribed_to',
            new_name='author',
        ),
    ]
