from django.urls import path

from .views import GenerateContentAsyncView, GenerateContentStatusView

urlpatterns = [
    # Async generation: returns 202 + contentId, processes the crew in the background.
    path('generate/async/', GenerateContentAsyncView.as_view(),
         name='marketing-generate-async'),
    path('generate/status/', GenerateContentStatusView.as_view(),
         name='marketing-generate-status'),
]
