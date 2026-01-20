from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, LogoutView, DoctorLoginView, LisLoginView, AdministrationLoginView, RadiologyLoginView, StaffListView, PublicDutyScheduleView, BulkScheduleView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('doctor/login/', DoctorLoginView.as_view(), name='doctor_login'),
    path('administration/login/', AdministrationLoginView.as_view(), name='administration_login'),
    path('radiology/login/', RadiologyLoginView.as_view(), name='radiology_login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('staff/', StaffListView.as_view(), name='staff-list'),
    path('schedules/public/', PublicDutyScheduleView.as_view(), name='public-schedules'),
    path('schedules/bulk/', BulkScheduleView.as_view(), name='bulk-schedules'),
    path('lis/login/', LisLoginView.as_view(), name='lis_login'),
]

from rest_framework.routers import DefaultRouter
from .views import DutyScheduleViewSet, NotificationViewSet, UserScheduleViewSet

router = DefaultRouter()
router.register(r'schedules', DutyScheduleViewSet)
router.register(r'user-schedules', UserScheduleViewSet)
router.register(r'notifications', NotificationViewSet)

urlpatterns += router.urls
