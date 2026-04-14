import os
import requests
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    Servicio para interactuar con WhatsApp Cloud API.
    """

    def __init__(self):
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        self.api_version = "v24.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"

        if not self.phone_number_id or not self.access_token:
            logger.error("❌ WhatsApp credentials not configured")

    def _get_headers(self) -> Dict[str, str]:
        """Retorna los headers necesarios para las peticiones a la API."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _sanitize_number(self, phone: str) -> str:
        """Limpia el número de teléfono para que solo contenga dígitos."""
        if not phone:
            return ""
        return "".join(filter(str.isdigit, phone))

    def send_text_message(self, to: str, message: str) -> bool:
        """
        Envía un mensaje de texto a un número de WhatsApp.

        Args:
            to: Número de teléfono del destinatario (con código de país, sin +)
            message: Texto del mensaje a enviar

        Returns:
            bool: True si el mensaje se envió exitosamente, False en caso contrario
        """
        if not self.phone_number_id or not self.access_token:
            logger.error("❌ WhatsApp not configured")
            return False

        url = f"{self.base_url}/messages"
        to_clean = self._sanitize_number(to)
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "text",
            "text": {"preview_url": True, "body": message},
        }

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=10
            )
            response.raise_for_status()
            logger.info(f"✅ Message sent to {to}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error sending message to {to}: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False

    def send_interactive_list(
        self, to: str, body_text: str, button_text: str, sections: List[Dict]
    ) -> bool:
        """
        Envía un mensaje interactivo con lista de opciones.

        Args:
            to: Número de teléfono del destinatario
            body_text: Texto principal del mensaje
            button_text: Texto del botón para abrir la lista
            sections: Lista de secciones con opciones

        Returns:
            bool: True si se envió exitosamente
        """
        if not self.phone_number_id or not self.access_token:
            logger.error("❌ WhatsApp not configured")
            return False

        url = f"{self.base_url}/messages"
        to_clean = self._sanitize_number(to)
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body_text},
                "action": {"button": button_text, "sections": sections},
            },
        }

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=10
            )
            response.raise_for_status()
            logger.info(f"✅ Interactive list sent to {to}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error sending interactive list to {to}: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False

    def send_button_message(self, to: str, body_text: str, buttons: List[Dict]) -> bool:
        """
        Envía un mensaje interactivo con botones de respuesta (máximo 3).
        Args:
            to: Número del destinatario
            body_text: Texto del cuerpo del mensaje
            buttons: Lista de dicts [{'id': 'id1', 'title': 'Título'}]
        """
        if not self.phone_number_id or not self.access_token:
            logger.error("❌ WhatsApp not configured")
            return False

        url = f"{self.base_url}/messages"
        to_clean = self._sanitize_number(to)
        
        # WhatsApp supports up to 3 buttons for interactive type 'button'
        formatted_buttons = []
        for btn in buttons[:3]:
            formatted_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn.get("id"),
                    "title": btn.get("title")[:20] # Limit to 20 chars
                }
            })

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text[:1024]},
                "action": {"buttons": formatted_buttons},
            },
        }

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=10
            )
            response.raise_for_status()
            logger.info(f"✅ Button message sent to {to_clean}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error sending button message to {to_clean}: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False

    def mark_message_as_read(self, message_id: str) -> bool:
        """
        Marca un mensaje como leído.

        Args:
            message_id: ID del mensaje a marcar como leído

        Returns:
            bool: True si se marcó exitosamente
        """
        if not self.phone_number_id or not self.access_token:
            return False

        url = f"{self.base_url}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=10
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error marking message as read: {str(e)}")

    def send_template_message(
        self, to: str, template_name: str, language_code: str = "es", components: List[Dict] = None
    ) -> bool:
        """
        Envía un mensaje de plantilla (Template Message) a un número.
        Requerido para iniciar conversaciones fuera de la ventana de 24h.
        Args:
            to: Número del destinatario
            template_name: Nombre de la plantilla en Meta Business Manager
            language_code: Código de idioma (ej: "es", "en_US")
            components: Lista de componentes (variables {{1}}, botones, etc.)

        Returns:
            bool: True si se envió exitosamente
        """
        if not self.phone_number_id or not self.access_token:
            logger.error("❌ WhatsApp not configured")
            return False

        # Sanitizar número (eliminar '+' y espacios)
        to_clean = self._sanitize_number(to)

        url = f"{self.base_url}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_clean,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }

        if components:
            payload["template"]["components"] = components

        try:
            response = requests.post(
                url, headers=self._get_headers(), json=payload, timeout=10
            )
            response.raise_for_status()

            # Loguear respuesta para debugging
            # response_data = response.json()
            logger.info(
                f"✅ Template message '{template_name}' sent to {to_clean}")

            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error sending template to {to_clean}: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False


class MessageFormatter:
    """
    Formateador de mensajes para WhatsApp.
    Convierte respuestas del chatbot y listados a formato compatible con WhatsApp.
    """

    MAX_MESSAGE_LENGTH = 4096  # Límite de WhatsApp
    MAX_LIST_ITEMS = 10  # Límite de items en lista interactiva

    @staticmethod
    def clean_and_parse_response(text: str) -> tuple[str, list[dict]]:
        """
        Strips internal reasoning (Thoughts, etc.) and extracts LISTINGS_JSON.
        Returns (clean_text, listings_list).
        """
        import re
        import json
        import logging
        logger = logging.getLogger(__name__)

        clean_text = str(text)

        # 1. Strip CrewAI internal reasoning leaks
        if "Thought:" in clean_text:
            clean_text = re.sub(r"^\s*Thought:.*?\n\s*\n", "",
                                    clean_text, flags=re.DOTALL | re.IGNORECASE).strip()

        # 2. Strip common English reasoning preambles
        reasoning_patterns = [
            r"^Since\s.*?\n\n",
            r"^Based\son\s.*?\n\n",
            r"^I\swill\s.*?\n\n",
            r"^I've\schecked\s.*?\n\n",
            r"^To\sanswer\s.*?\n\n"
        ]
        for pattern in reasoning_patterns:
            clean_text = re.sub(
                pattern, "", clean_text, flags=re.IGNORECASE | re.DOTALL).strip()

        # 3. Extract LISTINGS_JSON
        listings_data = []
        try:
            tag_match = re.search(r"LISTINGS_JSON:(\[.*?\])", clean_text, re.DOTALL)
            if tag_match:
                json_str = tag_match.group(1).strip()
                listings_data = json.loads(json_str)
                # Remove the tag from final response shown to user
                clean_text = clean_text.replace(tag_match.group(0), "").strip()
        except Exception as e:
            logger.warning(f"Failed to parse LISTINGS_JSON in WhatsApp formatter: {e}")

        return clean_text, listings_data

    @staticmethod
    def extract_actions(text: str) -> Dict:
        """
        Extrae patrones de botones [Título](action:ID) del texto.
        Retorna el texto limpio y una lista de botones.
        """
        import re
        # Pattern: [Title](action:ID)
        pattern = r"\[(.*?)\]\(action:(.*?)\)"
        matches = re.findall(pattern, text)
        
        buttons = []
        for match in matches:
            buttons.append({
                "title": match[0].strip(),
                "id": match[1].strip()
            })
            
        # Reemplazar los patrones [Label](action:ID) por solo Label en el texto
        # Esto evita dejar "huecos" en la oración.
        clean_text = re.sub(r"\[(.*?)\]\(action:.*?\)", r"\1", text).strip()
        # Colapsar múltiples newlines resultantes
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
        
        return {
            "clean_text": clean_text,
            "buttons": buttons
        }

    @staticmethod
    def format_text_message(text: str) -> str:
        """
        Formatea un mensaje de texto para WhatsApp.
        Limita la longitud y ajusta el formato.
        Args:
            text: Texto a formatear

        Returns:
            str: Texto formateado
        """
        # Limitar longitud
        if len(text) > MessageFormatter.MAX_MESSAGE_LENGTH:
            text = text[: MessageFormatter.MAX_MESSAGE_LENGTH - 3] + "..."

        return text

    @staticmethod
    def format_listings_as_text(listings: List[Dict], response_text: str) -> str:
        """
        Formatea los listados como texto simple para WhatsApp.

        Args:
            listings: Lista de hospedajes
            response_text: Texto de respuesta del chatbot

        Returns:
            str: Mensaje formateado con listados
        """
        if not listings:
            return MessageFormatter.format_text_message(response_text)

        # Construir mensaje con listados
        message = f"{response_text}\n\n"

        for idx, listing in enumerate(listings[:MessageFormatter.MAX_LIST_ITEMS], 1):
            title = listing.get("title", "Sin título")
            price = listing.get("price", 0)
            city = listing.get("city", "N/A")
            category = listing.get("category", "N/A")
            slug = listing.get("slug", "")

            message += f"\n*{idx}. {title}*\n"
            message += f"💰 Precio: ${price}\n"
            message += f"📍 Ciudad: {city}\n"
            message += f"🏠 Categoría: {category}\n"

            # Agregar link si existe slug
            if slug:
                message += f"🔗 Ver más: https://mequedo.app/listings/{slug}\n"

        if len(listings) > MessageFormatter.MAX_LIST_ITEMS:
            message += f"\n_...y {len(listings) - MessageFormatter.MAX_LIST_ITEMS} más opciones_"

        return MessageFormatter.format_text_message(message)

    @staticmethod
    def create_listings_interactive_sections(listings: List[Dict]) -> List[Dict]:
        """
        Crea secciones para mensaje interactivo con listados.

        Args:
            listings: Lista de hospedajes

        Returns:
            List[Dict]: Secciones formateadas para WhatsApp
        """
        if not listings:
            return []

        rows = []
        for idx, listing in enumerate(listings[:MessageFormatter.MAX_LIST_ITEMS]):
            title = listing.get("title", "Sin título")
            price = listing.get("price", 0)
            city = listing.get("city", "N/A")
            slug = listing.get("slug", "")

            # Crear ID único para la opción
            option_id = f"listing_{idx}_{slug[:20]}" if slug else f"listing_{idx}"

            # Descripción limitada a 72 caracteres
            description = f"${price} - {city}"[:72]

            rows.append(
                {
                    "id": option_id,
                    "title": title[:24],  # Máximo 24 caracteres
                    "description": description,
                }
            )

        # Crear sección
        sections = [{"title": "Opciones disponibles", "rows": rows}]

        return sections
