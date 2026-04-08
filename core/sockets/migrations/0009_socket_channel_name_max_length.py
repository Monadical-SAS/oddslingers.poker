from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sockets", "0008_auto_20180730_2303"),
    ]

    operations = [
        migrations.AlterField(
            model_name="socket",
            name="channel_name",
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
