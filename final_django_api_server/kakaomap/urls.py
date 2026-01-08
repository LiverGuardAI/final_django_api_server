from django.urls import path
from . import views

urlpatterns = [
    path('native-app-key/', views.get_native_app_key, name='kakao_native_app_key'),
    path('rest-api-key/', views.get_rest_api_key, name='kakao_rest_api_key'),
    path('search/nearby/', views.search_nearby_pharmacies, name='search_nearby_pharmacies'),
    path('search/query/', views.search_pharmacies_by_query, name='search_pharmacies_by_query'),
    path('search/place/', views.search_place_by_query, name='search_place_by_query'),
    path('map/', views.get_map_html, name='kakao_map_html'),
]
