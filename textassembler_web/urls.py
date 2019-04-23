from django.urls import path
from django.conf.urls import url
from . import views

urlpatterns = [
    path('', views.search, name='search'),
    url(r'^ajax/filter_val_input/(?P<filter_type>\w+)$', views.get_filter_val_input, name='filter_val_input'),
]
