# Generated by Django 2.2 on 2019-08-15 19:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('textassembler_web', '0014_admin_users'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='admin_users',
            new_name='administrative_users',
        ),
    ]
