# Generated by Django 2.2 on 2019-06-11 15:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('textassembler_web', '0007_auto_20190529_1208'),
    ]

    operations = [
        migrations.RenameField(
            model_name='searches',
            old_name='errror_message',
            new_name='error_message',
        ),
    ]
