from django.db import migrations
from django.contrib.postgres.operations import TrigramExtension

class Migration(migrations.Migration):

    dependencies = [
        ('doctor', '0003_remove_doctortoradiologyorder_medical_record_and_more'),
    ]

    operations = [
        TrigramExtension(),
    ]
