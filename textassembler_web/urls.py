from django.urls import path
from django.conf.urls import url
from . import views

urlpatterns = [
    path('', views.login, name='login'),
    path('login', views.login, name='login'),
    path('logout', views.logout, name='logout'),
    path('search', views.search, name='search'),
    path('about', views.about, name='about'),
    path('mysearches', views.mysearches, name='mysearches'),
    url(r'^ajax/filter_val_input/(?P<filter_type>.+)$', views.get_filter_val_input, name='filter_val_input'),
    url(r'^delete/(?P<search_id>[0-9]+)/$', views.delete_search, name='delete'),
    url(r'^download/(?P<search_id>[0-9]+)/$', views.download_search, name='download'),
]
