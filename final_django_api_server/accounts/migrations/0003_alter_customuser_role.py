# Generated manually on 2025-12-23 03:22

import accounts.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="role",
            field=accounts.fields.UserRoleField(blank=True, max_length=20, null=True),
        ),
    ]
