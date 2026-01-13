from rest_framework import serializers
from .models import DutySchedule, CustomUser

class DutyScheduleSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = DutySchedule
        fields = ['schedule_id', 'user', 'user_name', 'work_role', 'start_time', 'end_time', 'shift_type', 'schedule_status', 'created_at', 'updated_at']
        read_only_fields = ['schedule_id', 'created_at', 'updated_at']
