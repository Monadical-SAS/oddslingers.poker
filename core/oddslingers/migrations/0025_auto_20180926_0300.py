# Generated by Django 2.0.8 on 2018-09-26 03:00

from django.db import migrations
import oddslingers.models


class Migration(migrations.Migration):

    dependencies = [
        ('oddslingers', '0024_auto_20180925_2322'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='user',
            managers=[
                ('objects', oddslingers.models.CaseInsensitiveUserManager()),
            ],
        ),
    ]