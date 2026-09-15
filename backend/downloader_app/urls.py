from django.urls import path

from . import views

urlpatterns = [
    path("video-info/", views.video_info, name="video-info"),
    path("download/", views.download_video, name="download-video"),
]
