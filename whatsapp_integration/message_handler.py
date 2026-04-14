import logging
from typing import Dict, Optional, List
from .services import WhatsAppService, MessageFormatter
from chatbot.crew.tools.search_accommodation import get_db

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

            import os

            # Evaluate if we should use Multi-Agent CrewAI dynamically
            use_crewai = os.getenv(
                "USE_CREWAI", "False").lower() in ("true", "1", "yes")
            if use_crewai:
                from chatbot.utils import sanitize_message, contains_suspicious_content, MAX_MESSAGE_LENGTH
                
                # 1. Sanitize & Length Check
                message_text = sanitize_message(message_text)
                if not message_text:
                    logger.info("Empty or invalid message after sanitization.")
                    return True
                
                # 2. Check for Prompt Injection / Suspicious patterns
                if contains_suspicious_content(message_text):
                    logger.warning(f"Suspicious content detected from WhatsApp user {from_number}")
                    self.whatsapp_service.send_text_message(
                        from_number, 
                        "¡Hola! Soy Laura. Mi sistema de seguridad ha detectado patrones inusuales en tu mensaje. Por favor, asegúrate de realizar consultas relacionadas con la búsqueda de alojamientos en Mequedo."
                    )
                    return True

                # 3. Generate or fetch session_id (using from_number as temporary session identifier)
                session_id = f"wa_{from_number}"

                # --- NUEVO: Smart Redirect para botones de navegación ---
                # Si el mensaje es exactamente un ID de acción, enviamos el link directamente
                # para ahorrar tiempo de procesamiento y ser más precisos.
                redirects = {
                    "GO_TO_TRIPS": "Aquí tienes el acceso directo a tus viajes y reservaciones:\n🔗 https://mequedo.app/trips",
                    "GO_TO_PROPERTIES": "Aquí tienes el acceso directo a tus anuncios y propiedades:\n🔗 https://mequedo.app/properties",
                    "START_REGISTRATION": "Puedes registrarte en Mequedo aquí:\n🔗 https://mequedo.app/",
                    "START_LOGIN": "Inicia sesión en Mequedo aquí:\n🔗 https://mequedo.app/",
                    "OPEN_SEARCH": "Realiza una búsqueda manual en Mequedo aquí:\n🔗 https://mequedo.app/",
                    "START_ID_VERIFICATION": "Para verificar tu identidad, por favor sube una foto de tu documento en tu perfil:\n🔗 https://mequedo.app/account-settings/personal-info",
                    "START_RENT_PROCESS": "Para publicar tu alojamiento, ve a tu panel de anfitrión:\n🔗 https://mequedo.app/",
                }

                # Listado de acciones que también disparan un trigger en la UI del frontend
                ui_triggers = ["START_REGISTRATION", "START_LOGIN",
                               "OPEN_SEARCH", "START_ID_VERIFICATION", "START_RENT_PROCESS"]

                if message_text in redirects or message_text.strip().upper() in redirects:
                    action_key = message_text if message_text in redirects else message_text.strip().upper()

                    logger.info(
                        f"⚡ Smart redirect triggered for action: {action_key}")

                    # 1. Enviar respuesta en WhatsApp
                    self.whatsapp_service.send_text_message(
                        from_number, redirects[action_key]
                    )

                    # 2. Si es una acción UI, actualizar la base de datos para el frontend (si aplica)
                    if action_key in ui_triggers:
                        try:
                            from .database import get_db  # Assuming get_db is available or handled further down
                            db = get_db()
                            if db is not None:
                                db.get_collection("ChatSessions").update_one(
                                    {"session_id": session_id},
                                    {"$set": {"ui_action": action_key}},
                                    upsert=True
                                )
                                logger.info(
                                    f"🎨 UI Trigger '{action_key}' logged in DB for session {session_id}")
                        except Exception as db_err:
                            logger.error(
                                f"Failed to log UI trigger in DB (ignored for WhatsApp): {db_err}")

                    return

                # --- STEP A: Fast Template Check (Short-Circuit) ---
                from chatbot.templates import get_short_circuit_response
                # We use "WEB_ANONYMOUS" or "wa_..." to indicate they aren't authenticated yet in context of CRM
                fast_response = get_short_circuit_response(
                    message_text, session_id)

                if fast_response:
                    logger.info(
                        f"⚡ Fast Template triggered for WhatsApp user {from_number}")
                    crew_output = fast_response
                else:
                    # --- STEP B: Heavy Logic (CrewAI) ---
                    # 2. Fetch conversation history from MongoDB to satisfy CrewAI template requirements
                    conversation_history = ""
                    try:
                        from pymongo import MongoClient
                        import certifi
                        client = MongoClient(os.getenv(
                            "DATABASE_URL"), tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2000)
                        db = client.get_database(
                            os.getenv("MONGODB_DB_NAME", "test"))
                        conversations_col = db.get_collection("Conversations")

                        # Get last 5 messages for context
                        history_docs = list(conversations_col.find(
                            {"user_id": from_number},
                            sort=[("_id", -1)],
                            limit=5
                        ))

                        # Format history: "User: msg \nAI: resp"
                        formatted_history = []
                        for doc in reversed(history_docs):
                            u_msg = doc.get("user_message", "")
                            a_resp = doc.get("ai_response", "")
                            if u_msg:
                                formatted_history.append(f"User: {u_msg}")
                            if a_resp:
                                formatted_history.append(f"AI: {a_resp}")

                        conversation_history = "\n".join(formatted_history)
                        if not conversation_history:
                            conversation_history = "No previous history."
                    except Exception as history_err:
                        logger.warning(
                            f"Failed to fetch conversation history: {history_err}")
                        conversation_history = "History unavailable."

                    from chatbot.crew.orchestrator import MequedoCrew
                    crew = MequedoCrew()

                    # Provide all required template variables: user_id, user_message, conversation_history, session_id
                    crew_output = crew.kickoff({
                        "user_id": from_number,
                        "user_message": message_text,
                        "conversation_history": conversation_history,
                        "session_id": session_id
                    })

                if crew_output == "HUMAN_PAUSED":
                    logger.info(
                        f"Skipping automated response for {from_number} due to human bypass.")
                    return True

                # --- STEP C: Response Cleaning & Parsing ---
                # Strip internal reasoning and extract LISTINGS_JSON if present
                clean_response, extracted_listings = self.message_formatter.clean_and_parse_response(
                    crew_output)

                # Conversational Logging: Ensure the webhook logic saves both User message and AI output
                try:
                    from pymongo import MongoClient
                    import certifi
                    client = MongoClient(os.getenv(
                        "DATABASE_URL"), tlsCAFile=certifi.where(), serverSelectionTimeoutMS=2000)
                    db = client.get_database(
                        os.getenv("MONGODB_DB_NAME", "test"))
                    conversations_col = db.get_collection("Conversations")
                    conversations_col.insert_one({
                        "user_id": from_number,
                        "user_message": message_text,
                        "ai_response": clean_response,
                        "status": "completed",
                        "source": "crewai_webhook"
                    })
                    logger.info(
                        "Successfully historically logged User message and CrewAI response to MongoDB in webhook logic.")
                except Exception as db_err:
                    logger.warning(
                        f"Failed to securely log conversation to CRM: {db_err}")

                result = {
                    "response": clean_response,
                    "listings": extracted_listings
                }
            else:
                # Importar aquí para evitar importación circular
                from chatbot.views import process_chatbot_message
                # Procesar mensaje con la lógica del chatbot legacy
                result = process_chatbot_message(message_text)

            if result and result.get("error"):
                # Enviar mensaje de error
                error_message = "Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo."
                self.whatsapp_service.send_text_message(
                    from_number, error_message)
                return False

            # Obtener respuesta y listados
            response_text = result.get("response", "")
            listings = result.get("listings", [])

            # --- NUEVO: Extraer botones interactivos ---
            extracted = self.message_formatter.extract_actions(response_text)
            clean_text = extracted["clean_text"]
            buttons = extracted["buttons"]

            # Formatear y enviar respuesta
            if listings:
                # Si hay listados, enviar mensaje con formato especial
                # Por ahora mantenemos el formato de texto para los listados
                formatted_message = self.message_formatter.format_listings_as_text(
                    listings, clean_text
                )
                self.whatsapp_service.send_text_message(
                    from_number, formatted_message)
            elif buttons and len(buttons) <= 3:
                # Si hay entre 1 y 3 botones, enviar como mensaje interactivo
                self.whatsapp_service.send_button_message(
                    from_number, clean_text, buttons
                )
            elif buttons and len(buttons) > 3:
                # Meta API max button limit is 3. For menus up to 10 options we safely fall back to an Interactive List
                sections = [{
                    "title": "Opciones válidas",
                    "rows": [
                        {
                            "id": btn.get("id", ""),
                            # Hard limit of 24 chars for Whatsapp list
                            "title": btn.get("title", "")[:24],
                        } for btn in buttons[:10]
                    ]
                }]
                self.whatsapp_service.send_interactive_list(
                    from_number, clean_text[:1024], "Seleccionar opción", sections
                )
            else:
                # Solo texto (o demasiados botones para el formato de botones)
                formatted_message = self.message_formatter.format_text_message(
                    clean_text if buttons else response_text
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

            from_number = message.get("from")
            message_id = message.get("id")
            message_text = ""

            # 1. Manejar mensajes de texto
            if message_type == "text":
                message_text = message.get("text", {}).get("body", "")

            # 2. Manejar respuestas a botones interactivos
            elif message_type == "interactive":
                interactive_data = message.get("interactive", {})
                itype = interactive_data.get("type")

                if itype == "button_reply":
                    # Usamos el ID del botón como el texto del mensaje para que el AI sepa la acción
                    message_text = interactive_data.get(
                        "button_reply", {}).get("id", "").strip()
                    logger.info(
                        f"🔘 INTERACTIVE BUTTON CLICKED: ID='{message_text}'")
                elif itype == "list_reply":
                    message_text = interactive_data.get(
                        "list_reply", {}).get("id", "").strip()

            else:
                logger.info(f"Ignoring message type: {message_type}")
                return None

            if not from_number or not message_text or not message_id:
                return None

            return {
                "from_number": from_number,
                "message_text": message_text.strip(),
                "message_id": message_id,
            }
        except Exception as e:
            logger.error(f"❌ Error extracting message data: {str(e)}")
            return None
