import os
import logging
from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .message_handler import WhatsAppMessageHandler
from pymongo import MongoClient
import certifi

logger = logging.getLogger(__name__)

# --- MongoDB Connection ---
try:
    client = MongoClient(os.getenv("DATABASE_URL"), tlsCAFile=certifi.where())
    db = client.get_database(os.getenv("MONGODB_DB_NAME", "test"))
    scheduled_tasks_collection = db.get_collection("ScheduledTask")
    logger.info("✅ Connected to MongoDB (ScheduledTask)")
except Exception as e:
    logger.error(f"❌ Error connecting to MongoDB: {e}")
    scheduled_tasks_collection = None


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


class SendReservationRequestView(APIView):
    """
    Vista para enviar notificaciones de solicitud de reserva vía WhatsApp.
    Es llamada por el backend de Next.js cuando se crea una reserva.
    """
    # Se debe asegurar autenticación en producción (ej: API Key o JWT)
    # Por ahora dejamos abierto o asumimos que se configura a nivel global/servidor

    def post(self, request, *args, **kwargs):
        try:
            data = request.data

            # 1. Validar datos requeridos
            required_fields = ["hostPhoneNumber", "guestName", "hostName",
                               "listingTitle", "dates", "reservationId", "callbackUrl"]
            # Note: reservationId and callbackUrl are needed for scheduling

            if not all(field in data for field in required_fields):
                # Try to proceed even if specific new fields absent for backward compatibility if needed,
                # but better to enforce key fields.
                # Strict check for now:
                if "hostPhoneNumber" not in data:
                    return Response({"error": "Missing hostPhoneNumber"}, status=400)

            to_number = data.get("hostPhoneNumber")
            guest_name = data.get("guestName")
            host_name = data.get("hostName")
            listing_title = data.get("listingTitle")
            dates = data.get("dates")
            reservation_id = data.get("reservationId")
            callback_url = data.get("callbackUrl")

            # 2. Instanciar servicio
            from .services import WhatsAppService
            whatsapp_service = WhatsAppService()

            # 3. Construir componentes de la plantilla
            components = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": host_name},
                        {"type": "text", "text": listing_title},
                        {"type": "text", "text": dates},
                        {"type": "text", "text": guest_name},
                    ]
                }
            ]
            # TODO!: Implementar envío de mensaje texto con Twilio

            # 4. send  WhatsApp message
            success = whatsapp_service.send_template_message(
                to=to_number,
                template_name="reservation_request_notice",
                language_code="es",
                components=components
            )

            if success:
                logger.info(f"✅ Reservation notification sent to {to_number}")

            # 5. Schedule Expiration Task (MongoDB)
            if scheduled_tasks_collection is not None and reservation_id and callback_url:
                expiration_time = datetime.utcnow() + timedelta(hours=1)
                # expiration_time = datetime.utcnow() + timedelta(hours=0.05)
                task_doc = {
                    "type": "reservation_expiration",
                    "reservationId": reservation_id,
                    "callbackUrl": callback_url,
                    "executeAt": expiration_time,
                    "status": "pending",
                    "createdAt": datetime.utcnow()
                }
                try:
                    scheduled_tasks_collection.insert_one(task_doc)
                    logger.info(
                        f"⏰ Scheduled expiration task for reservation {reservation_id} at {expiration_time}")
                except Exception as db_err:
                    logger.error(f"❌ Failed to schedule task: {db_err}")

            return Response({"status": "success", "message": "Notification sent and task scheduled"}, status=status.HTTP_200_OK)
            # else:
            #     return Response(
            #         {"error": "Failed to send WhatsApp message"},
            #         status=status.HTTP_500_INTERNAL_SERVER_ERROR
            #     )

        except Exception as e:
            logger.error(f"❌ Error in SendReservationRequestView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendPaymentRequestView(APIView):
    """
    Vista para enviar notificaciones de solicitud de pago vía WhatsApp.
    Es llamada por el backend de Next.js cuando se APRUEBA una reserva.
    """
    # Se debe asegurar autenticación en producción (ej: API Key o JWT)
    # Por ahora dejamos abierto o asumimos que se configura a nivel global/servidor

    def post(self, request, *args, **kwargs):
        # Validate Internal Secret
        secret_key = os.getenv("DJANGO_SERVICE_SECRET")
        if secret_key and request.headers.get("X-Internal-Secret") != secret_key:
            logger.warning(
                f"⛔ Unauthorized access attempt to SendPaymentRequestView from {request.META.get('REMOTE_ADDR')}")
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            data = request.data
            # 1. Validar datos requeridoswa
            required_fields = ["guestPhoneNumber", "guestName", "hostName",
                               "listingTitle", "dates", "reservationId", "callbackUrl"]
            # Note: reservationId and callbackUrl are needed for scheduling

            if not all(field in data for field in required_fields):
                # Try to proceed even if specific new fields absent for backward compatibility if needed,
                # but better to enforce key fields.
                # Strict check for now:
                if "guestPhoneNumber" not in data:
                    return Response({"error": "Missing guestPhoneNumber"}, status=400)

            to_number = data.get("guestPhoneNumber")
            guest_name = data.get("guestName")
            host_name = data.get("hostName")
            listing_title = data.get("listingTitle")
            dates = data.get("dates")
            reservation_id = data.get("reservationId")
            callback_url = data.get("callbackUrl")

            # 2. Instanciar servicio
            from .services import WhatsAppService
            whatsapp_service = WhatsAppService()

            # 3. Construir componentes de la plantilla
            components = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": guest_name},
                        {"type": "text", "text": listing_title},
                        {"type": "text", "text": dates},
                        {"type": "text", "text": host_name},

                    ]
                }
            ]

            # 4. send WhatsApp message
            success = whatsapp_service.send_template_message(
                to=to_number,
                template_name="reservation_payment_notice",
                language_code="es",
                components=components
            )

            if success:
                logger.info(f"✅ Reservation notification sent to {to_number}")

            # 5. Schedule Expiration Task (MongoDB)
            if scheduled_tasks_collection is not None and reservation_id and callback_url:
                expiration_time = datetime.utcnow() + timedelta(hours=1)
                # expiration_time = datetime.utcnow() + timedelta(hours=0.05)
                task_doc = {
                    "type": "reservation_expiration",
                    "reservationId": reservation_id,
                    "callbackUrl": callback_url,
                    "executeAt": expiration_time,
                    "status": "pending",
                    "createdAt": datetime.utcnow()
                }
                try:
                    scheduled_tasks_collection.insert_one(task_doc)
                    logger.info(
                        f"⏰ Scheduled expiration task for reservation {reservation_id} at {expiration_time}")
                except Exception as db_err:
                    logger.error(f"❌ Failed to schedule task: {db_err}")

            return Response({"status": "success", "message": "Notification sent and task scheduled"}, status=status.HTTP_200_OK)
            # else:
            #     return Response(
            #         {"error": "Failed to send WhatsApp message"},
            #         status=status.HTTP_500_INTERNAL_SERVER_ERROR
            #     )

        except Exception as e:
            logger.error(f"❌ Error in SendReservationRequestView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
