# Generated by Django 2.2.5 on 2019-10-04 18:56

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('textassembler_web', '0017_searches_last_save_dir'),
    ]

    operations = [
        migrations.CreateModel(
            name='available_sort_orders',
            fields=[
                ('sort_id', models.AutoField(primary_key=True, serialize=False)),
                ('sort_value', models.CharField(max_length=30)),
                ('sort_label', models.CharField(max_length=255)),
                ('removed', models.DateTimeField(null=True)),
            ],
        ),
        migrations.AddField(
            model_name='searches',
            name='sort_order',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='textassembler_web.available_sort_orders'),
        ),
        migrations.RunSQL('''INSERT INTO textassembler_web_available_sort_orders (sort_value, sort_label, removed) VALUES
            ("","Relavence",NOW()),
            ("Date","Date (Newest to Oldest)",NULL),
            ("Date desc","Date (Oldest to Newest)",NULL),
            ("Title","Title (A to Z)",NULL),
            ("Title desc","Title (Z to A)",NULL)'''
        ),
    ]