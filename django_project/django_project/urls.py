"""django_project URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
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

from operating_procedures import views


urlpatterns = [
    path('admin/', admin.site.urls),
    path('toc', views.toc),
    path('toc/<source>', views.toc, name='toc'),
    path('cite', views.cite, name='cite'),
    path('cite/<citation>', views.cite, name='cite'),
    path('search/<words>', views.search, name='search'),
    path('synonyms/<word>', views.synonyms, name='synonyms'),
    path('versions', views.versions, name='versions'),
    path('item_debug/<int:version_id>', views.item_debug, name='item_debug'),
    path('item_debug/<int:version_id>/<citation>', views.item_debug, name='item_debug'),
    path('paragraph_debug/<int:paragraph_id>', views.paragraph_debug, name='paragraph_debug'),
]
