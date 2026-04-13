from django.urls import path
from .views import ChatbotView, ChatbotAsyncView, ChatbotStatusView


urlpatterns = [
    path('query/', ChatbotView.as_view(), name='chatbot-query'),
    # Async polling endpoints — no HTTP timeouts, background AI processing
    path('query/async/', ChatbotAsyncView.as_view(), name='chatbot-query-async'),
    path('query/status/', ChatbotStatusView.as_view(),
         name='chatbot-query-status'),
]
