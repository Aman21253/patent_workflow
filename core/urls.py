from django.urls import path
from .views import patents_list, patent_detail, patents_page, recommendation_view

urlpatterns = [
    path("", patents_page, name="home"),
    path("patents/", patents_list, name="patents"),
    path("patents/<str:application_id>/", patent_detail, name="patent-detail"),
    path("recommendations/", recommendation_view, name="recommendations"),
]
