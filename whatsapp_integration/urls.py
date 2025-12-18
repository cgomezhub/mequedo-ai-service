from django.urls import path
from .views import WhatsAppWebhookView, SendReservationRequestView

urlpatterns = [
    path('webhook/', WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
    path('send-reservation-request/', SendReservationRequestView.as_view(),
         name='send-reservation-request'),
]
