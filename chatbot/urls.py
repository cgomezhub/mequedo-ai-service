from django.urls import path
from .views import ChatbotView


urlpatterns = [
    path('query/', ChatbotView.as_view(), name='chatbot-query'),
]