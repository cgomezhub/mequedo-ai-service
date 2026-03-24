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

    def post(self, request, *args, **kwargs):
        # Validate Internal Secret
        secret_key = os.getenv("DJANGO_SERVICE_SECRET")
        if secret_key and request.headers.get("X-Internal-Secret") != secret_key:
            logger.warning(
                f"⛔ Unauthorized access attempt to SendReservationRequestView from {request.META.get('REMOTE_ADDR')}")
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            data = request.data
            print("Data", data)

            # 1. Validar datos requeridos
            required_fields = ["hostPhoneNumber", "guestName", "hostName",
                               "listingTitle", "dates", "reservationId", "callbackUrl"]

            missing_or_invalid = [
                field for field in required_fields
                if field not in data or data[field] in [None, "", "null", "undefined"]
            ]

            if missing_or_invalid:
                logger.warning(
                    f"⚠️ Missing or invalid fields in SendReservationRequestView: {missing_or_invalid}")
                return Response(
                    {"error": f"Missing or invalid fields: {', '.join(missing_or_invalid)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            to_number = data.get("hostPhoneNumber")
            guest_name = data.get("guestName")
            host_name = data.get("hostName")
            listing_title = data.get("listingTitle")
            dates = data.get("dates")
            reservation_id = data.get("reservationId")
            callback_url = data.get("callbackUrl")
            listing_image = data.get(
                "listingMainImage") or "https://res.cloudinary.com/carlosgomez/image/upload/v1773242952/jm9zmpz79bcf9sj5gqb9.png"

            # 2. Instanciar servicio
            from .services import WhatsAppService
            whatsapp_service = WhatsAppService()

            # 3. Construir componentes de la plantilla
            components = []
            # Add Header Image if present
            if listing_image:
                components.append({
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"link": listing_image}
                        }
                    ]
                })

            # Add Body parameters
            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": host_name},
                    {"type": "text", "text": listing_title},
                    {"type": "text", "text": dates},
                    {"type": "text", "text": guest_name},
                ]
            })

            # 4. send  WhatsApp message
            print("Sending reservation request to", to_number)
            print("Reservation request components", components)
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
                try:
                    expiration_hours = float(
                        os.getenv("RESERVATION_EXPIRATION_HOURS", "1"))
                    expiration_time = datetime.utcnow() + timedelta(hours=expiration_hours)

                    task_doc = {
                        "type": "reservation_expiration",
                        "reservationId": reservation_id,
                        "callbackUrl": callback_url,
                        "executeAt": expiration_time,
                        "status": "pending",
                        "createdAt": datetime.utcnow()
                    }
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
            print("Payment request data", data)
            # 1. Validar datos requeridos
            required_fields = ["guestPhoneNumber", "guestName", "hostName",
                               "listingTitle", "dates", "reservationId", "callbackUrl"]

            missing_or_invalid = [
                field for field in required_fields
                if field not in data or data[field] in [None, "", "null", "undefined"]
            ]

            if missing_or_invalid:
                logger.warning(
                    f"⚠️ Missing or invalid fields in SendPaymentRequestView: {missing_or_invalid}")
                return Response(
                    {"error": f"Missing or invalid fields: {', '.join(missing_or_invalid)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            to_number = data.get("guestPhoneNumber")
            guest_name = data.get("guestName")
            host_name = data.get("hostName")
            listing_title = data.get("listingTitle")
            listing_image = data.get(
                "listingMainImage") or "https://res.cloudinary.com/carlosgomez/image/upload/v1773242952/jm9zmpz79bcf9sj5gqb9.png"
            dates = data.get("dates")
            reservation_id = data.get("reservationId")
            callback_url = data.get("callbackUrl")

            # 2. Instanciar servicio
            from .services import WhatsAppService
            whatsapp_service = WhatsAppService()

            # 3. Construir componentes de la plantilla
            components = []
            # Add Header Image if present
            if listing_image:
                components.append({
                    "type": "header",
                    "parameters": [
                        {
                            "type": "image",
                            "image": {"link": listing_image}
                        }
                    ]
                })
            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": guest_name},
                    {"type": "text", "text": listing_title},
                    {"type": "text", "text": dates},
                    {"type": "text", "text": host_name},

                ]
            })
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
                try:
                    expiration_hours = float(
                        os.getenv("RESERVATION_EXPIRATION_HOURS", "1"))
                    expiration_time = datetime.utcnow() + timedelta(hours=expiration_hours)

                    task_doc = {
                        "type": "reservation_expiration",
                        "reservationId": reservation_id,
                        "callbackUrl": callback_url,
                        "executeAt": expiration_time,
                        "status": "pending",
                        "createdAt": datetime.utcnow()
                    }
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
            logger.error(f"❌ Error in SendPaymentRequestView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendPaymentSuccessView(APIView):
    """
    Vista para enviar notificaciones de pago exitoso vía WhatsApp a host y guest.
    Es llamada por el backend de Next.js.
    """

    def post(self, request, *args, **kwargs):
        # Validate Internal Secret
        secret_key = os.getenv("DJANGO_SERVICE_SECRET")
        if secret_key and request.headers.get("X-Internal-Secret") != secret_key:
            logger.warning(
                f"⛔ Unauthorized access attempt to SendPaymentSuccessView from {request.META.get('REMOTE_ADDR')}")
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            data = request.data

            # 1. Validar datos requeridos básicos
            host_phone = data.get("hostPhoneNumber")
            guest_phone = data.get("guestPhoneNumber")

            if not host_phone and not guest_phone:
                return Response({"error": "Missing at least one phone number (hostPhoneNumber or guestPhoneNumber)"}, status=400)

            guest_name = data.get("guestName", "Guest")
            host_name = data.get("hostName", "Host")
            listing_title = data.get("listingTitle", "Alojamiento")
            listing_image = data.get(
                "listingMainImage") or "https://res.cloudinary.com/carlosgomez/image/upload/v1773242952/jm9zmpz79bcf9sj5gqb9.png"
            dates = data.get("dates", "")
            amount = str(data.get("amount", ""))
            currency = data.get("currency", "USD")

            # 2. Instanciar servicio
            from .services import WhatsAppService
            whatsapp_service = WhatsAppService()

            responses = {}

            # 3. Enviar a Host si el número está presente
            if host_phone:
                # Variables del host:
                # {{1}}: host name, {{2}}: guest name, {{3}}: currency, {{4}}: amount, {{5}}: listing name, {{6}}: dates
                host_components = [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "image",
                                "image": {"link": listing_image}
                            }
                        ]
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": host_name},
                            {"type": "text", "text": guest_name},
                            {"type": "text", "text": currency},
                            {"type": "text", "text": amount},
                            {"type": "text", "text": listing_title},
                            {"type": "text", "text": dates},
                        ]
                    }
                ]
                success_host = whatsapp_service.send_template_message(
                    to=host_phone,
                    template_name="host_payment_notice",
                    language_code="es",
                    components=host_components
                )
                responses["host_notified"] = success_host
                if success_host:
                    logger.info(
                        f"✅ Payment success notification sent to HOST {host_phone}")

            # 4. Enviar a Guest si el número está presente
            if guest_phone:
                # Variables del guest:
                # {{1}}: guest name, {{2}}: currency, {{3}}: amount, {{4}}: listing name, {{5}}: dates, {{6}}: host name
                guest_components = [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "image",
                                "image": {"link": listing_image}
                            }
                        ]
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": guest_name},
                            {"type": "text", "text": currency},
                            {"type": "text", "text": amount},
                            {"type": "text", "text": listing_title},
                            {"type": "text", "text": dates},
                            {"type": "text", "text": host_name},
                        ]
                    }
                ]
                success_guest = whatsapp_service.send_template_message(
                    to=guest_phone,
                    template_name="guest_payment_notice",
                    language_code="es",
                    components=guest_components
                )
                responses["guest_notified"] = success_guest
                if success_guest:
                    logger.info(
                        f"✅ Payment success notification sent to GUEST {guest_phone}")

            return Response({"status": "success", "details": responses}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"❌ Error in SendPaymentSuccessView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendPaymentReviewView(APIView):
    """
    Vista para enviar notificaciones a los administradores de que un recibo de pago 
    manual está en cola de revisión.
    Es llamada por el backend de Next.js.
    """

    def post(self, request, *args, **kwargs):
        # Validate Internal Secret
        secret_key = os.getenv("DJANGO_SERVICE_SECRET")
        if secret_key and request.headers.get("X-Internal-Secret") != secret_key:
            logger.warning(
                f"⛔ Unauthorized access attempt to SendPaymentReviewView from {request.META.get('REMOTE_ADDR')}")
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            data = request.data

            order_id = data.get("orderId")
            sender_name = data.get("senderName", "Guest")
            transaction_id = data.get("transactionId", "N/A")
            amount = str(data.get("amount", ""))
            currency = data.get("currency", "Bs.")
            receipt_url = data.get("receiptUrl")

            if not order_id:
                return Response({"error": "Missing orderId"}, status=status.HTTP_400_BAD_REQUEST)

            # Get admin numbers from environment (comma-separated)
            admin_numbers_env = os.getenv("ADMIN_WHATSAPP_NUMBERS", "")
            admin_numbers = [num.strip() for num in admin_numbers_env.split(",") if num.strip()]

            if not admin_numbers:
                logger.warning("⚠️ No ADMIN_WHATSAPP_NUMBERS configured. Cannot send payment review notification.")
                return Response({"error": "No admin numbers configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            from .services import WhatsAppService
            whatsapp_service = WhatsAppService()

            # Format components
            components = []
            if receipt_url:
                components.append({
                    "type": "header",
                    "parameters": [
                        {
                            "type": "document", # Can be image or document, relying on standard format
                            "document": {"link": receipt_url}
                        }
                    ]
                })

            components.append({
                "type": "body",
                "parameters": [
                    {"type": "text", "text": sender_name},
                    {"type": "text", "text": amount},
                    {"type": "text", "text": currency},
                    {"type": "text", "text": transaction_id},
                    {"type": "text", "text": order_id},
                ]
            })

            notified_admins = []
            for admin_phone in admin_numbers:
                success = whatsapp_service.send_template_message(
                    to=admin_phone,
                    template_name="admin_payment_review",
                    language_code="es",
                    components=components
                )
                if success:
                    notified_admins.append(admin_phone)

            logger.info(f"✅ Payment review notification sent to {len(notified_admins)} admin(s)")
            return Response({"status": "success", "notified_admins": notified_admins}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"❌ Error in SendPaymentReviewView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SendPaymentRejectedView(APIView):
    """
    Vista para enviar notificaciones de rechazo de pago manual vía WhatsApp a host y guest.
    Es llamada por el backend de Next.js.
    """

    def post(self, request, *args, **kwargs):
        # Validate Internal Secret
        secret_key = os.getenv("DJANGO_SERVICE_SECRET")
        if secret_key and request.headers.get("X-Internal-Secret") != secret_key:
            logger.warning(
                f"⛔ Unauthorized access attempt to SendPaymentRejectedView from {request.META.get('REMOTE_ADDR')}")
            return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)

        try:
            data = request.data

            host_phone = data.get("hostPhoneNumber")
            guest_phone = data.get("guestPhoneNumber")
            amount = str(data.get("amount", ""))
            currency = data.get("currency", "Bs.")

            if not host_phone and not guest_phone:
                return Response({"error": "Missing at least one phone number (hostPhoneNumber or guestPhoneNumber)"}, status=status.HTTP_400_BAD_REQUEST)

            guest_name = data.get("guestName", "Guest")
            host_name = data.get("hostName", "Host")
            listing_title = data.get("listingTitle", "Alojamiento")
            listing_image = data.get(
                "listingMainImage") or "https://res.cloudinary.com/carlosgomez/image/upload/v1773242952/jm9zmpz79bcf9sj5gqb9.png"
            dates = data.get("dates", "")

            from .services import WhatsAppService
            whatsapp_service = WhatsAppService()

            responses = {}

            # 1. Enviar a Guest
            if guest_phone:
                guest_components = [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "image",
                                "image": {"link": listing_image}
                            }
                        ]
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": guest_name},
                            {"type": "text", "text": amount},
                            {"type": "text", "text": currency},
                            {"type": "text", "text": listing_title},
                            {"type": "text", "text": host_name},
                        ]
                    }
                ]
                success_guest = whatsapp_service.send_template_message(
                    to=guest_phone,
                    template_name="guest_payment_rejected",
                    language_code="es",
                    components=guest_components
                )
                responses["guest_notified"] = success_guest
                if success_guest:
                    logger.info(
                        f"✅ Payment rejection notification sent to GUEST {guest_phone}")

            # 2. Enviar a Host
            if host_phone:
                host_components = [
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "image",
                                "image": {"link": listing_image}
                            }
                        ]
                    },
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": host_name},
                            {"type": "text", "text": guest_name},
                            {"type": "text", "text": amount},
                            {"type": "text", "text": currency},
                            {"type": "text", "text": listing_title},
                        ]
                    }
                ]
                success_host = whatsapp_service.send_template_message(
                    to=host_phone,
                    template_name="host_payment_rejected",
                    language_code="es",
                    components=host_components
                )
                responses["host_notified"] = success_host
                if success_host:
                    logger.info(
                        f"✅ Payment rejection notification sent to HOST {host_phone}")

            return Response({"status": "success", "details": responses}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"❌ Error in SendPaymentRejectedView: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
