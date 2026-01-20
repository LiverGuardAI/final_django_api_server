from rest_framework import serializers
from .models import DutySchedule, CustomUser, Notification, UserSchedule

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['notification_id', 'user', 'message_type', 'message', 'is_read', 'created_at']
        read_only_fields = ['notification_id', 'created_at']


class UserScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSchedule
        fields = ['schedule_id', 'user', 'schedule_date', 'schedule_type', 'start_time', 'end_time', 'notes', 'created_at']
        read_only_fields = ['created_at', 'user']


class DutyScheduleSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    employee_no = serializers.SerializerMethodField()

    class Meta:
        model = DutySchedule
        fields = ['schedule_id', 'user', 'user_name', 'employee_no', 'work_role', 'start_time', 'end_time', 'shift_type', 'schedule_status', 'rejection_reason', 'created_at', 'updated_at']
        read_only_fields = ['schedule_id', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        user = obj.user
        # Try to find name in related role models
        if hasattr(user, 'doctor'):
            return user.doctor.name
        if hasattr(user, 'radiology'):
            return user.radiology.name
        if hasattr(user, 'administration'):
            return user.administration.name
            
        # Fallback to User name
        return f"{user.last_name}{user.first_name}"

    def get_employee_no(self, obj):
        user = obj.user
        if hasattr(user, 'doctor'):
            return user.doctor.employee_no
        if hasattr(user, 'radiology'):
            return user.radiology.employee_no
        if hasattr(user, 'administration'):
            return user.administration.employee_no
        return ''
