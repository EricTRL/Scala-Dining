# Generated by Django 3.2.8 on 2021-10-25 13:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('creditmanagement', '0014_auto_20210320_0015'),
    ]

    operations = [
        migrations.CreateModel(
            name='InvoiceReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.CreateModel(
            name='InvoicedTransaction',
            fields=[
                ('transaction_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='creditmanagement.transaction')),
                ('report', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='invoicing.invoicereport')),
            ],
            bases=('creditmanagement.transaction',),
        ),
    ]