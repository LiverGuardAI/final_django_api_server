from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('radiology', '0006_ctreport_tumor_analysis'),
    ]

    operations = [
        migrations.CreateModel(
            name='SegmentationMaskClass',
            fields=[
                ('class_id', models.AutoField(primary_key=True, serialize=False)),
                ('mask_series_id', models.CharField(db_index=True, max_length=64)),
                ('label_value', models.PositiveIntegerField()),
                ('label_name', models.CharField(max_length=64)),
                ('color', models.CharField(blank=True, max_length=16, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'hospital"."segmentation_mask_classes',
                'indexes': [
                    models.Index(fields=['mask_series_id'], name='segmentation_mask_classes_mask_series_id_idx'),
                ],
                'unique_together': {('mask_series_id', 'label_value')},
            },
        ),
    ]
