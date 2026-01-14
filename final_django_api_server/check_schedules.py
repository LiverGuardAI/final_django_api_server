import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liverguard_api_server.settings')
django.setup()

from accounts.models import DutySchedule, CustomUser

print("--- Checking Duty Schedules ---")
schedules = DutySchedule.objects.all()
if not schedules.exists():
    print("No DutySchedule found.")
else:
    for s in schedules:
        print(f"ID: {s.schedule_id}, User: {s.user.username} ({s.user.first_name}), Status: {s.schedule_status}")
        print(f"  Start: {s.start_time}")
        print(f"  End:   {s.end_time}")
        print(f"  Role: {s.work_role}, Shift: {s.shift_type}")
        print("-" * 30)
