import os
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .message_handler import WhatsAppMessageHandler

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhookView(APIView):
    """
    Vista para manejar el webhook de WhatsApp Cloud API.

    GET: Verificación del webhook por parte de Meta
    POST: Recepción de mensajes entrantes
    """

    authentication_classes = []  # No requiere autenticación
    permission_classes = []  # No requiere permisos

    def get(self, request, *args, **kwargs):
        """
        Maneja la verificación del webhook por parte de Meta.

        Meta envía:
        - hub.mode: "subscribe"
        - hub.verify_token: El token que configuraste
        - hub.challenge: Un string que debes devolver

        Si el verify_token coincide, devuelves el challenge.
        """
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")

        # Validar que todos los parámetros estén presentes
        if not all([mode, token, challenge]):
            logger.warning(
                "⚠️ Webhook verification failed - missing parameters")
            return Response(
                {"error": "Missing required parameters"}, status=status.HTTP_400_BAD_REQUEST
            )

        if mode == "subscribe" and token == verify_token:
            logger.info("✅ Webhook verified successfully")
            # WhatsApp espera el challenge como respuesta de texto plano
            from django.http import HttpResponse
            return HttpResponse(challenge, content_type="text/plain", status=200)
        else:
            logger.warning(
                f"⚠️ Webhook verification failed - mode: {mode}, token match: {token == verify_token}")
            return Response(
                {"error": "Verification failed"}, status=status.HTTP_403_FORBIDDEN
            )

    def post(self, request, *args, **kwargs):
        """
        Maneja los mensajes entrantes de WhatsApp.
        """
        # Log del request para trazabilidad
        logger.info(
            f"🔔 WEBHOOK POST RECEIVED from {request.META.get('REMOTE_ADDR')}")
        # logger.debug(f"Headers: {request.headers}")
        # logger.debug(f"Body start: {request.body[:100]}")

        try:
            webhook_data = request.data

            # Log del webhook para debugging (solo en desarrollo)
            if os.getenv("DEBUG", "False") == "True":
                logger.debug(f"Webhook data: {webhook_data}")

            # Verificar que sea un evento de WhatsApp Business
            if webhook_data.get("object") != "whatsapp_business_account":
                logger.info("Ignoring non-WhatsApp webhook")
                return Response({"status": "ignored"}, status=status.HTTP_200_OK)

            # Procesar el mensaje
            handler = WhatsAppMessageHandler()
            message_data = handler.extract_message_data(webhook_data)

            if not message_data:
                # No hay mensaje para procesar (puede ser un status update u otro evento)
                logger.info("No message to process")
                return Response({"status": "no_message"}, status=status.HTTP_200_OK)

            # Procesar el mensaje de forma asíncrona (en producción considera usar Celery)
            from_number = message_data["from_number"]
            message_text = message_data["message_text"]
            message_id = message_data["message_id"]

            logger.info(
                f"📨 Received message from {from_number}: {message_text[:50]}")

            # Procesar mensaje de forma asíncrona con threading para evitar timeout de Meta
            import threading

            # Función wrapper para el thread
            def process_async():
                try:
                    logger.info(
                        f"🧵 Starting async processing for {from_number}")
                    handler.process_incoming_message(
                        from_number, message_text, message_id)
                    logger.info(
                        f"✅ Async processing complete for {from_number}")
                except Exception as e:
                    logger.error(f"❌ Error in async processing: {str(e)}")

            # Iniciar thread
            thread = threading.Thread(target=process_async)
            thread.daemon = True
            thread.start()

            logger.info(
                f"🚀 Message handed off to background thread for {from_number}")

            # Siempre devolver 200 OK a Meta para confirmar recepción INMEDIATAMENTE
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"❌ Error processing webhook: {str(e)}")
            # Aún así devolver 200 OK para evitar reintentos de Meta
            return Response({"status": "error"}, status=status.HTTP_200_OK)
