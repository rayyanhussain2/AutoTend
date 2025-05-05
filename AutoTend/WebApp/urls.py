from django.contrib import admin
from django.urls import path
from django.urls import include
from . import views

urlpatterns = [
    path('',  views.default, name='default'),
    path('home/', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('lecture/', views.lecture, name='lecture') #redirect to class get essentially ()
    
]