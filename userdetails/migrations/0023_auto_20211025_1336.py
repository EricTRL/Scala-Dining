# Generated by Django 3.2.8 on 2021-10-25 11:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userdetails', '0022_move_allergies'),
    ]

    operations = [
        migrations.RenameField(
            model_name='association',
            old_name='has_min_exception',
            new_name='allow_direct_debit',
        ),
        migrations.AddField(
            model_name='association',
            name='direct_debit_name',
            field=models.CharField(blank=True, help_text='For instance Q-rekening in the case of Quadrivium.', max_length=100),
        ),
    ]
