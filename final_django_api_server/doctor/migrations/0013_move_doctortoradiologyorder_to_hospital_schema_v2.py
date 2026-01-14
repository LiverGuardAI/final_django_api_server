from django.db import migrations


FORWARD_SQL = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'hospital') THEN
        IF to_regclass('hospital.doctor_to_radiology_orders') IS NOT NULL THEN
            -- Already in the correct schema and name.
        ELSIF to_regclass('public.doctor_to_radiology_orders') IS NOT NULL THEN
            EXECUTE 'ALTER TABLE public.doctor_to_radiology_orders SET SCHEMA hospital';
        ELSIF to_regclass('public.doctor_doctortoradiologyorder') IS NOT NULL THEN
            EXECUTE 'ALTER TABLE public.doctor_doctortoradiologyorder SET SCHEMA hospital';
            EXECUTE 'ALTER TABLE hospital.doctor_doctortoradiologyorder RENAME TO doctor_to_radiology_orders';
        END IF;
    END IF;
END$$;
"""

REVERSE_SQL = """
DO $$
BEGIN
    IF to_regclass('hospital.doctor_to_radiology_orders') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE hospital.doctor_to_radiology_orders SET SCHEMA public';
    END IF;
END$$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ('doctor', '0012_move_doctortoradiologyorder_to_hospital_schema'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]
