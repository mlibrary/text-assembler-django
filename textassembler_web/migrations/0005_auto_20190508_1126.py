# Generated by Django 2.2 on 2019-05-08 15:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('textassembler_web', '0004_available_formats_help_text'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='searches',
            name='date_startd',
        ),
        migrations.AddField(
            model_name='searches',
            name='date_started',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='searches',
            name='date_completed',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='searches',
            name='date_completed_compression',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='searches',
            name='date_started_compression',
            field=models.DateTimeField(null=True),
        ),
        migrations.AlterField(
            model_name='searches',
            name='update_date',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]