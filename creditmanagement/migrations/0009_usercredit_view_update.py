from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from general.db_view_migration import CreateView


class Migration(migrations.Migration):


    dependencies = [
        ('userdetails', '0017_association_balance_update_instructions'),
        ('creditmanagement', '0008_pendingdiningtransaction'),
    ]

    operations = [
        CreateView(
            name='UserCredit',
            fields=[
                ('user', models.OneToOneField(db_column='id', on_delete=django.db.models.deletion.DO_NOTHING, primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('balance', models.DecimalField(blank=True, db_column='balance', decimal_places=2, max_digits=6, null=True)),
                ('balance_fixed', models.DecimalField(blank=True, db_column='balance_fixed', decimal_places=2, max_digits=6, null=True)),
            ],
        ),
    ]
