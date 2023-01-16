# Generated by Django 3.2.13 on 2022-12-24 12:46

from django.db import migrations, models
import userdetails.models


class Migration(migrations.Migration):

    dependencies = [
        ('userdetails', '0020_auto_20210319_2310'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='association',
            managers=[
                ('objects', userdetails.models.AssociationManager()),
            ],
        ),
        migrations.AlterModelManagers(
            name='user',
            managers=[
                ('objects', userdetails.models.UserManager()),
            ],
        ),
        migrations.AddField(
            model_name='user',
            name='allergies',
            field=models.CharField(blank=True, help_text='E.g. gluten or vegetarian. Leave empty if not applicable.', max_length=100, verbose_name='food allergies or preferences'),
        ),
    ]
