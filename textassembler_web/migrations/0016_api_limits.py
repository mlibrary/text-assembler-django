# Generated by Django 2.2.5 on 2019-09-06 14:37

from django.db import migrations, models
import textassembler_web.models


class Migration(migrations.Migration):

    dependencies = [
        ('textassembler_web', '0015_auto_20190815_1547'),
    ]

    operations = [
        migrations.CreateModel(
            name='api_limits',
            fields=[
                ('limit_type', models.CharField(choices=[(textassembler_web.models.CallTypeChoice('Sources'), 'Sources'), (textassembler_web.models.CallTypeChoice('Search'), 'Search'), (textassembler_web.models.CallTypeChoice('Download'), 'Download')], max_length=20, primary_key=True, serialize=False)),
                ('per_minute', models.IntegerField(default=0)),
                ('per_hour', models.IntegerField(default=0)),
                ('per_day', models.IntegerField(default=0)),
                ('update_date', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
