from django.urls import path
from .views import WhatsAppWebhookView, SendReservationRequestView, SendPaymentRequestView, SendPaymentSuccessView

urlpatterns = [
    path('webhook/', WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
    path('send-reservation-request/', SendReservationRequestView.as_view(),
         name='send-reservation-request'),
    path('send-payment-request/', SendPaymentRequestView.as_view(),
         name='send-payment-request'),
    path('send-payment-success/', SendPaymentSuccessView.as_view(),
         name='send-payment-success'),
]
