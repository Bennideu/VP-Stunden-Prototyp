"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from vp_stunden.views import melde_an_view, melde_ab_view, aendere_passwort_view

urlpatterns = [
    path('admin/', admin.site.urls),

    # Anfragen an anmelden/ an die Anmelde-View weiterleiten
    path('anmelden/', melde_an_view, name='melde_an'),
    # Anfragen an abmelden/ an die Abmelde-View weiterleiten
    path('abmelden/', melde_ab_view, name='melde_ab'),
    # Anfragen an passwort_aendern/ an die Passwortänderungs-View weiterleiten
    path('passwort_aendern/', aendere_passwort_view, name='aendere_passwort'),
]
