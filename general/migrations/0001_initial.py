# Generated by Django 2.1.5 on 2019-02-03 18:22

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SiteUpdate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(auto_now_add=True, unique=True)),
                ('version', models.CharField(help_text='The current version', max_length=16, unique=True)),
                ('title', models.CharField(max_length=140, unique=True)),
                ('message', models.TextField()),
            ],
        ),
    ]