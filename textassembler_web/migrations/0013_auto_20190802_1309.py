# Generated by Django 2.2 on 2019-08-02 17:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('textassembler_web', '0012_auto_20190802_1139'),
    ]

    operations = [
        migrations.RenameField(
            model_name='historical_searches',
            old_name='delete',
            new_name='deleted',
        ),
        migrations.RenameField(
            model_name='searches',
            old_name='delete',
            new_name='deleted',
        ),
    ]
