# Generated by Django 2.1.5 on 2019-04-29 20:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('UserDetails', '0012_auto_20190429_1306'),
    ]

    operations = [
        migrations.AddField(
            model_name='association',
            name='icon_image',
            field=models.ImageField(blank=True, null=True, upload_to=''),
        ),
        migrations.AlterField(
            model_name='association',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=''),
        ),
    ]