import logging
from typing import Dict, Optional, List
from .services import WhatsAppService, MessageFormatter

logger = logging.getLogger(__name__)


class WhatsAppMessageHandler:
    """
    Maneja el procesamiento de mensajes entrantes de WhatsApp.
    Integra con la lógica existente del chatbot.
    """

    def __init__(self):
        self.whatsapp_service = WhatsAppService()
        self.message_formatter = MessageFormatter()

    def process_incoming_message(
        self, from_number: str, message_text: str, message_id: str
    ) -> bool:
        """
        Procesa un mensaje entrante de WhatsApp.

        Args:
            from_number: Número del remitente
            message_text: Texto del mensaje
            message_id: ID del mensaje de WhatsApp

        Returns:
            bool: True si se procesó exitosamente
        """
        try:
            # Marcar mensaje como leído
            self.whatsapp_service.mark_message_as_read(message_id)

            # Importar aquí para evitar importación circular
            from chatbot.views import process_chatbot_message

            # Procesar mensaje con la lógica del chatbot
            result = process_chatbot_message(message_text)

            if result.get("error"):
                # Enviar mensaje de error
                error_message = "Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo."
                self.whatsapp_service.send_text_message(
                    from_number, error_message)
                return False

            # Obtener respuesta y listados
            response_text = result.get("response", "")
            listings = result.get("listings", [])

            # Formatear y enviar respuesta
            if listings:
                # Si hay listados, enviar mensaje con formato especial
                formatted_message = self.message_formatter.format_listings_as_text(
                    listings, response_text
                )
                self.whatsapp_service.send_text_message(
                    from_number, formatted_message)
            else:
                # Solo texto
                formatted_message = self.message_formatter.format_text_message(
                    response_text
                )
                self.whatsapp_service.send_text_message(
                    from_number, formatted_message)

            logger.info(f"✅ Processed message from {from_number}")
            return True

        except Exception as e:
            logger.error(
                f"❌ Error processing message from {from_number}: {str(e)}")
            # Enviar mensaje de error genérico
            try:
                self.whatsapp_service.send_text_message(
                    from_number,
                    "Lo siento, no pude procesar tu mensaje. Por favor intenta más tarde.",
                )
            except:
                pass
            return False

    def extract_message_data(self, webhook_data: Dict) -> Optional[Dict]:
        """
        Extrae los datos del mensaje del payload del webhook de WhatsApp.

        Args:
            webhook_data: Datos del webhook

        Returns:
            Dict con from_number, message_text, message_id o None si no es válido
        """
        try:
            # Estructura del webhook de WhatsApp:
            # {
            #   "object": "whatsapp_business_account",
            #   "entry": [{
            #     "changes": [{
            #       "value": {
            #         "messages": [{
            #           "from": "1234567890",
            #           "id": "wamid.xxx",
            #           "text": {"body": "mensaje"},
            #           "type": "text"
            #         }]
            #       }
            #     }]
            #   }]
            # }

            entry = webhook_data.get("entry", [])
            if not entry:
                return None

            changes = entry[0].get("changes", [])
            if not changes:
                return None

            value = changes[0].get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None

            message = messages[0]
            message_type = message.get("type")

            # Solo procesar mensajes de texto por ahora
            if message_type != "text":
                logger.info(f"Ignoring message type: {message_type}")
                return None

            from_number = message.get("from")
            message_id = message.get("id")
            message_text = message.get("text", {}).get("body", "")

            if not from_number or not message_text or not message_id:
                return None

            return {
                "from_number": from_number,
                "message_text": message_text,
                "message_id": message_id,
            }

        except Exception as e:
            logger.error(f"❌ Error extracting message data: {str(e)}")
            return None
