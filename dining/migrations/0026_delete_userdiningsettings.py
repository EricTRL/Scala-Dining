# Generated by Django 3.2.8 on 2021-10-23 14:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dining', '0025_auto_20211023_0053'),
    ]

    operations = [
        migrations.DeleteModel(
            name='UserDiningSettings',
        ),
    ]