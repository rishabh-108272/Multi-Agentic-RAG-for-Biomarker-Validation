from django.urls import path
from .views import *

urlpatterns = [
    path('analyze/', analyze_csv),
    path('analysis/<uuid:analysis_id>/status/', analysis_status),
    path('analysis/<uuid:analysis_id>/', analysis_results),
    path('analyses/', list_analyses),
    path('analyses/summary/', analyses_summary),
    path('analyses/clear/', clear_analyses),
]
