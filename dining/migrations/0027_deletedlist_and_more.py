# Generated by Django 4.1.4 on 2023-03-07 21:50

import datetime

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dining", "0026_diningcomment_increase_length"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="dininglist",
            name="min_diners",
        ),
        migrations.AlterField(
            model_name="dininglist",
            name="adjustable_duration",
            field=models.DurationField(
                default=datetime.timedelta(days=2),
                help_text="How long the dining list can be adjusted after its date.",
            ),
        ),
        migrations.AlterField(
            model_name="dininglist",
            name="dish",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AlterField(
            model_name="dininglist",
            name="limit_signups_to_association_only",
            field=models.BooleanField(
                default=False,
                help_text="Whether only members of the given association can sign up.",
            ),
        ),
        migrations.CreateModel(
            name="DeletedList",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "date",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="deletion date"
                    ),
                ),
                ("reason", models.TextField()),
                ("json_list", models.TextField(verbose_name="JSON dining list")),
                ("json_diners", models.TextField(verbose_name="JSON dining entries")),
                (
                    "deleted_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
