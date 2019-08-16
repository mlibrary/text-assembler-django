"""
URL patterns for the web application
"""
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
    path('admin/users', views.admin_users, name='admin_users'),
    path('admin/searches', views.admin_searches, name='admin_searches'),
    path('admin/statistics', views.admin_statistics, name='admin_statistics'),
    path('add/admin', views.add_admin_user, name='add'),
    url(r'^ajax/filter_val_input/(?P<filter_type>.+)$', views.get_filter_val_input, name='filter_val_input'),
    url(r'^delete/(?P<search_id>[0-9]+)/$', views.delete_search, name='delete'),
    url(r'^download/(?P<search_id>[0-9]+)/$', views.download_search, name='download'),
    url(r'^delete/admin/(?P<userid>[A-Za-z0-9]+)/$', views.delete_admin_user, name='delete_admin_user'),
]
