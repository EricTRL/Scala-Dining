# Generated by Django 2.2 on 2019-05-08 00:30

from django.db import migrations


def move_added_by(apps, schema_editor):
    DiningEntryUser = apps.get_model('Dining', 'DiningEntryUser')
    DiningEntryExternal = apps.get_model('Dining', 'DiningEntryExternal')

    for entry in DiningEntryUser.objects.all():
        entry.created_by = entry.added_by if entry.added_by else entry.user
        entry.save()

    for entry in DiningEntryExternal.objects.all():
        entry.created_by = entry.user
        entry.save()


def reverse_added_by(apps, schema_editor):
    DiningEntryUser = apps.get_model('Dining', 'DiningEntryUser')

    for entry in DiningEntryUser.objects.all():
        entry.added_by = entry.created_by
        entry.save()


class Migration(migrations.Migration):
    dependencies = [
        ('Dining', '0009_auto_20190508_0230'),
        ('UserDetails', '0014_remove_user_external_link'),
    ]

    operations = [
        migrations.RunPython(move_added_by, reverse_added_by, elidable=True),
    ]
