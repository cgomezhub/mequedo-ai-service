from __future__ import annotations
import logging
import os
import unicodedata

logger = logging.getLogger(__name__)


def get_short_circuit_response(user_message: str, user_id: str = "WEB_ANONYMOUS") -> str | None:
    """
    Checks if the user message matches any predefined "Fast response" templates.
    Returns the response string if a match is found, otherwise None.
    """
    BASE_URL = os.getenv("MEQUEDO_BASE_URL", "https://mequedo.app").rstrip("/")
    normalized_msg = user_message.strip().lower()
    is_wa = user_id.startswith("wa_")

    # Strip common punctuation and accents BEFORE checking for gibberish/matching
    clean_msg = normalized_msg.replace("¿", "").replace(
        "?", "").replace("¡", "").replace("!", "").strip()
    clean_msg = ''.join(c for c in unicodedata.normalize(
        'NFD', clean_msg) if unicodedata.category(c) != 'Mn')

    # Case 0: Gibberish / Nonsense / Spam detection (Highest Priority)
    # Using clean_msg ensures accents are removed before [^a-z] regex checks
    if _is_nonsense_or_spam(clean_msg):
        logger.info(f"🚫 Gibberish/Spam detected: '{clean_msg}'")
        return (
            "No he podido comprender tu mensaje, ya que parece contener caracteres aleatorios o repetidos.\n\n"
            "Mequedo es una plataforma profesional para la renta de alojamientos. Por favor, escribe una pregunta clara "
            "en español o utiliza el [Menú de Ayuda](action:menu) para guiarte."
        )

    crm_keywords = ["mis reservaciones", "mis reservas", "mis alojamientos",
                    "mis listados", "mis propiedades", "mis compras", "mis viajes", "mi cuenta", "mis arriendos", "mis publicaciones", "mis mensajes", "mis notificaciones"]

    # Case 1: Anonymous user trying to access private data
    if (user_id in ["WEB_ANONYMOUS", "ANONYMOUS"] or user_id.startswith("wa_")) and any(keyword in clean_msg for keyword in crm_keywords):
        # Note: For WhatsApp, we might need a different check for auth, but the keyword trigger is enough to prompt login
        return (
            "Si deseas consultar información personal sobre tus propiedades, reservaciones o mensajes, "
            "para proteger tu privacidad y poder acceder a tus datos, necesitas iniciar sesión en Mequedo.\n\n"
            "Selecciona: [Iniciar Sesión](action:START_LOGIN) o, si aún no tienes una cuenta, [Registrarme](action:START_REGISTRATION)."
        )
    # Case 2: Basic greetings
    if clean_msg in ["hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hey", "saludos", "hola Karen"]:
        return (
            "¡Hola! Soy Karen, tu asistente en Mequedo. ¿En qué ciudad buscas hospedaje hoy?"
        )

    # Case 3: Platform Help / Menu
    if clean_msg in ["que hace esta plataforma", "para que es esta plataforma", "que ofrecen", "que es mequedo", "menu", "opciones", "ayuda", "que puedes hacer", "como funciona la plataforma", "como funciona mequedo", "que puedo hacer aqui", "que es esto", "para que sirve esto", "no entiendo"]:
        return (
            "Mequedo es la plataforma líder en renta y reserva de alojamientos en Venezuela, ofreciendo un entorno seguro y verificado.\n\n"
            "¡Estoy aquí para guiarte! Puedes pedirme que busque hospedajes en cualquier ciudad, o consultar estas opciones:\n\n"
            "[🏠 Publicar mi alojamiento](action:START_RENT_PROCESS)\n"
            "[🤝 ¿Quiénes somos?](action:START_ABOUT_US)\n"
            "[👤 Crear mi cuenta](action:START_REGISTRATION)\n"
            "[❓ Preguntas frecuentes](action:START_FAQ)\n"
            "[📋 Términos y Reglas](action:START_TERMS)"
        )

    # Case 4: Basic goodbyes
    if clean_msg in ["gracias", "muchas gracias", "te lo agradezco", "gracias Karen", "agradecido", "agradecida", "gracias por tu ayuda", "gracias por la ayuda", "gracias por la información"]:
        return (
            "¡De nada! Estoy aquí para ayudarte. ¿En qué más puedo asistirte hoy?"
        )
    # Case 5: Basic goodbyes
    if clean_msg in ["adios", "hasta luego", "nos vemos", "chao", "chao Karen", "gracias, chao", "gracias, chao Karen"]:
        return (
            "¡Hasta luego! Que tengas un excelente día, si necesitas algo mas no dudes en escribirme"
        )

    # Case 8: Guest Search Detection - MOVED TO BOTTOM

    # Case 6: How to register
    if clean_msg in ["como me registro", "como me inscribo", "como me registro en mequedo", "como me registro en la plataforma"]:
        return (
            "Para registrarte en Mequedo, por favor selecciona [Registrarme](action:START_REGISTRATION)."
        )
    if clean_msg in ["como publico mi alojamiento", "como publico mi alojamiento en mequedo", "como publico mi alojamiento en la plataforma"]:
        return (
            "Para publicar tu alojamiento en Mequedo, por favor selecciona [Publicar mi alojamiento](action:START_RENT_PROCESS)."
        )
    if clean_msg in ["como verifico mi identidad", "como verifico mi identidad en mequedo", "como verifico mi identidad en la plataforma"]:
        return (
            "Para verificar tu identidad en Mequedo, por favor selecciona [Verificar Identidad](action:START_ID_VERIFICATION)."
        )
    if clean_msg in ["como inicio sesion", "como inicio sesion en mequedo", "como inicio sesion en la plataforma"]:
        return (
            "Para iniciar sesión en Mequedo, por favor selecciona [Iniciar Sesión](action:START_LOGIN)."
        )
    # Case 9: Dashboard Redirections (Gated for Auth)
    if any(keyword in clean_msg for keyword in ["mis mensajes", "ver mensajes", "mensajes", "mensaje"]):
        text = "💬 Puedes ver tus mensajes y solicitudes en Mequedo aquí:"
        link = f"{BASE_URL}/guest/messages"
        return f"{text}\n\n" + (f"{link}" if is_wa else f"> 🔗 [Ver Mis Mensajes]({link})")

    if any(keyword in clean_msg for keyword in ["mi perfil", "mi cuenta", "configuracion", "ajustes"]):
        text = "⚙️ Accede a tu configuración de perfil y datos personales aquí:"
        link = f"{BASE_URL}/account-settings"
        return f"{text}\n\n" + (f"{link}" if is_wa else f"> 🔗 [Gestionar Mi Perfil]({link})")

    if any(keyword in clean_msg for keyword in ["mis favoritos", "favoritos", "guardados"]):
        text = "❤️ Mira tus alojamientos guardados y favoritos aquí:"
        link = f"{BASE_URL}/favorites"
        return f"{text}\n\n" + (f"{link}" if is_wa else f"> 🔗 [Ver Mis Favoritos]({link})")

    if any(keyword in clean_msg for keyword in ["solicitudes", "reservas de mis casas", "solicitudes a mis alojamientos"]):
        text = "📅 Gestiona las solicitudes y reservas de tus huéspedes aquí:"
        link = f"{BASE_URL}/reservations"
        return f"{text}\n\n" + (f"{link}" if is_wa else f"> 🔗 [Gestionar Reservas]({link})")

    if any(keyword in clean_msg for keyword in ["noticias", "promociones", "experiencias"]):
        text = "🆕 Descubre las últimas novedades, noticias y experiencias en Mequedo:"
        link = f"{BASE_URL}/experiences"
        return f"{text}\n\n" + (f"{link}" if is_wa else f"> 🔗 [Ver Experiencias]({link})")

    if any(keyword in clean_msg for keyword in ["soporte", "contacto", "ayuda humana", "atencion"]):
        text = "💁 Nuestro equipo de soporte está listo para ayudarte directamente:"
        link = f"{BASE_URL}/contact"
        return f"{text}\n\n" + (f"{link}" if is_wa else f"> 🔗 [Contactar Soporte]({link})")

    if any(keyword in clean_msg for keyword in ["como publico mi casa", "como publico mi alojamiento", "publicar alojamiento", "rentar mi casa"]):
        return (
            "Publicar tu alojamiento en Mequedo es muy sencillo y seguro. Solo sigue este enlace para completar tu registro y subir tus fotos:\n\n"
            "[🏠 Publicar mi alojamiento](action:START_RENT_PROCESS)"
        )

    if any(keyword in clean_msg for keyword in ["propiedades", "anuncios", "publicaciones", "casas"]):
        text = "🏠 Revisa y edita tus anuncios publicados en Mequedo aquí:"
        link = f"{BASE_URL}/properties"
        return f"{text}\n\n" + (f"{link}" if is_wa else f"> 🔗 [Ver Mis Anuncios]({link})")

    if clean_msg in ["como veo mis reservas", "como veo mis reservas en mequedo", "como veo mis reservas en la plataforma", "mis reservas", "mis viajes"]:
        # We leave the "How to see" link here, but the actual "data query" will fall through to Crew if not matched here
        text = "🔗 Puedes ver tus viajes y reservas en Mequedo aquí:"
        link = f"{BASE_URL}/trips"
        return f"{text}\n\n" + (f"{link}" if is_wa else f"> 🔗 [Ver Mis Viajes]({link})")

    # Case 4: About us
    if clean_msg in ["quienes son ustedes y por que confiar en mequedo", "quienes son ustedes", "por que confiar", "start_about_us"]:
        video_element = (
            "▶️ Mira este video sobre nosotros: https://www.youtube.com/watch?v=5r9x0GuHd_U"
            if is_wa else
            "<iframe width=\"100%\" height=\"350\" src=\"https://www.youtube.com/embed/5r9x0GuHd_U\" frameborder=\"0\" allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen style=\"border-radius: 12px; margin-top: 10px;\"></iframe>"
        )
        return (
            "Mequedo es la plataforma líder en renta y reserva de alojamientos en Venezuela. "
            "Nuestro objetivo es transformar la forma de hospedarse en el país, ofreciendo un entorno seguro, profesional y verificado.\n\n"
            "Para empezar a disfrutar de nuestras opciones, [Registrarme](action:START_REGISTRATION) es el primer paso. "
            "Si ya tienes una cuenta y deseas iniciar sesión, por favor selecciona [Iniciar Sesión](action:START_LOGIN)."
            "Si ya tienes una cuenta, pero no has verificado tu identidad, por favor selecciona [Verificar Identidad](action:START_ID_VERIFICATION) para poder publicar y reservar, es muy fácil, rápido y seguro.\n\n"
            f"Conoce más sobre nosotros aquí:\n\n{video_element}"
        )

    # Case 5: FAQ
    if clean_msg in ["preguntas frecuentes sobre la plataforma", "preguntas frecuentes", "faq", "start_faq"]:
        video_element = (
            "▶️ Mira este video sobre nosotros: https://www.youtube.com/watch?v=5r9x0GuHd_U"
            if is_wa else
            "<iframe width=\"100%\" height=\"350\" src=\"https://www.youtube.com/embed/5r9x0GuHd_U\" frameborder=\"0\" allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen style=\"border-radius: 12px; margin-top: 10px;\"></iframe>"
        )
        return (
            "¡Claro! Estas son algunas de las dudas más comunes sobre Mequedo:\n\n"
            "**1. ¿Es seguro alquilar por aquí?**\n\n"
            "100%. Utilizamos integración con Didit para validar la identidad de todos nuestros usuarios y anfitriones.\n\n"
            "**2. ¿Cómo publico mi alojamiento?**\n\n"
            "Debes tener tu cuenta registrada y verificada. Luego, utiliza la opción [Publicar mi alojamiento](action:START_RENT_PROCESS)\n\n"
            "**3. ¿Cómo me registro?**\n\n"
            "Solo haz clic aquí: [Crear mi cuenta](action:START_REGISTRATION)\n\n"
            "**4. ¿Cuentan con respaldo legal en Venezuela?**\n\n"
            "Sí, estamos legalmente constituidos en Venezuela y tenemos fuertes alianzas con *12 Tablas* y los Abogados de *Doctores Condominio* para ofrecer seguridad jurídica en ambas direcciones. "
            f"Puedes conocer un poco de nosotros a continuación:\n\n{video_element}"
        )

    # Case 6: Terms
    if clean_msg in ["terminos y condiciones de servicio", "terminos y reglas", "reglas", "start_terms"]:
        web_link = (
            "🔗 Puedes leer el documento legal completo aquí:\nhttps://mequedo.app/terms-conditions"
            if is_wa else
            "> 🔗 Puedes leer el documento legal completo aquí: [Términos y Condiciones de Mequedo](https://mequedo.app/terms-conditions)"
        )
        response_text = (
            "Para mantener nuestro Ecosistema Mequedo seguro y proteger tanto a Anfitriones como a Viajeros, aquí te presento **las 5 reglas de oro**:\n\n"
            "**1. Edades y Verificación:** \n\n"
            "Solo mayores de 18 años pueden rentar. La validación de identidad con Didit es estrictamente obligatoria.\n\n"
            "**2. Tarifas Transparentes:** \n\n"
            "La plataforma cobra hasta un 5% de comisión al Anfitrión y hasta un 15% al Viajero para mantener el servicio activo, ciertas promociones y condiciones aplican.\n\n"
            "**3. Pagos y Transacciones:** \n\n"
            "Está *estrictamente prohibido* pagar en efectivo o contactar directamente cuentas bancarias externas. Todo se procesa en las cuentas bancarias de Mequedo.\n\n"
            "**4. Comunicaciones:** \n\n"
            "Por tu seguridad, no compartas números de teléfono ni correos personales. Usa siempre el chat interno entre usuarios.\n\n"
            "**5. Seguros (Alojamiento y Viajero):** \n\n"
            "   - *Anfitriones:* Recomendamos adquirir un seguro de alojamiento (opcional), siendo tú el responsable directo.\n\n"
            f"   - *Viajeros:* Tienen la opción de contratar un seguro de viaje con nuestro aliado estratégico, TuDrenViajes, durante el proceso de reserva.\n\n"
            f"{web_link}"
        )
        # WhatsApp uses * for bold, while conventional Markdown uses **
        if is_wa:
            response_text = response_text.replace("**", "*")
        return response_text

    # Case 7: Human Handoff / Scam / Toxicity / Support
    escalation_keywords = ["estafa", "robo", "fraude", "humano", "asesor", "persona real", "soporte", "contacto", "reclamo", "fake",
                           "mentira", "ayuda", "ayuda humana", "mierda", "cagada", "jodiendo", "jodete", "jodanse", "carajo", "coño", "coño e", "coño e madre"]
    if any(keyword in clean_msg for keyword in escalation_keywords):
        ig_link = (
            "@mequedo.app (https://instagram.com/mequedo.app)"
            if is_wa else
            "nuestro Instagram **[@mequedo.app](https://instagram.com/mequedo.app)**"
        )
        return (
            "Para brindarte la mejor asistencia y aclarar tus inquietudes de seguridad o soporte técnico, "
            f"por favor comunícate directamente con nuestro equipo de atención humana a través de {ig_link}. "
            "Ellos están listos para ayudarte con tu caso específico."
        )

    # Case 8: Guest Search Detection (Catch common Search patterns for Guests)
    # Refined triggers to avoid false positives with general sentences
    search_triggers = ["busca en", "alojamiento en", "hospedaje en", "apartamento en",
                       "casa en", "habitacion en", "alquiler en", "renta en"]
    if (user_id in ["WEB_ANONYMOUS", "ANONYMOUS"] or is_wa) and any(trigger in clean_msg for trigger in search_triggers):
        logger.info(f"🚀 Guest Search Short-Circuit: '{clean_msg}'")
        if is_wa:
            return (
                "¡Veo que estás buscando alojamiento! 🏠\n\n"
                "Para poder procesar tu búsqueda con Inteligencia Artificial y mostrarte nuestras mejores opciones, "
                "por nuestra política de seguridad necesitas estar registrado en nuestra comunidad Mequedo.\n\n"
                "Crear tu cuenta es totalmente gratis. Te invito a registrarte y ver nuestros listados aquí:\n\n"
                f"🔗 {BASE_URL}/\n\n"
                "¡Estaré aquí esperándote cuando termines!"
            )
        return (
            "Veo que estás buscando alojamiento.\n\n"
            "En nuestra plataforma estamos para ayudarte a encontrar el alojamiento ideal.\n\n"
            "Para que pueda ayudarte a encontrar la mejor opción con nuestra búsqueda personalizada por IA, **necesitas iniciar sesión o registrarte**.\n\n"
            "Si prefieres explorar por tu cuenta, puedes usar nuestro buscador manual:\n\n"
            "[Iniciar Sesión](action:START_LOGIN)\n"
            "[Registrarme](action:START_REGISTRATION)\n"
            "[Búsqueda Manual](action:OPEN_SEARCH)"
        )

    return None


def get_default_guest_fallback(user_id: str = "WEB_ANONYMOUS") -> str:
    """
    Standard response for unauthenticated users who ask something 
    that doesn't match a specific template, preventing CrewAI execution.
    """
    is_wa = user_id.startswith("wa_")
    BASE_URL = os.getenv("MEQUEDO_BASE_URL", "https://mequedo.app").rstrip("/")

    if is_wa:
        return (
            "¡Bienvenido a Mequedo! 🏠\n\n"
            "He notado que estás escribiendo desde un número no registrado o sin sesión activa.\n"
            "Para garantizar una comunidad segura y poder ofrecerte búsquedas impulsadas por nuestra Inteligencia Artificial, "
            "necesitas tener una cuenta verificada y tu número celular asociado.\n\n"
            "Te invito a registrarte, iniciar sesión, o asegurarte de agregar tu número telefónico en tu perfil para continuar tu búsqueda de forma rápida y segura:\n\n"
            f"🔗 {BASE_URL}/\n\n"
            "Una vez iniciada tu sesión y validado tu número, serás libre de usar este chat para todas tus reservaciones. ¡Te esperamos!"
        )

    return (
        "¡Bienvenido a Mequedo! 🏠\n\n"
        "He notado que aún no has ingresado a tu cuenta.\n"
        "Para garantizar una comunidad segura, las funciones de búsqueda inteligente, publicación, reserva y verificación de identidad son exclusivas para **nuestros miembros**.\n\n"
        "¿Cómo prefieres continuar?\n\n"
        "[Iniciar Sesión](action:START_LOGIN)\n"
        "[Registrarme](action:START_REGISTRATION)\n"
        "[Verificar Identidad](action:START_ID_VERIFICATION)\n"
        "[¿Quiénes somos?](action:START_ABOUT_US)\n"
        "[Búsqueda Manual](action:OPEN_SEARCH)"
    )


def _is_nonsense_or_spam(text: str) -> bool:
    """
    Heuristic to detect gibberish, keyboard pounding, or repetitive spam.
    """
    import re

    clean = text.strip().lower()
    if not clean:
        return False

    # 1. Excessive simple character repetition (e.g., "aaaaaaa", "!!!!!!!")
    if re.search(r'(.)\1{4,}', clean):
        return True

    # 2. Pattern repetition (e.g., "abcabcabc", "weiweiwei")
    # Matches a pattern of 2-4 characters that repeats 3 or more times
    if re.search(r'(.{2,4})\1{2,}', clean):
        return True

    # 3. Word analysis (keyboard smash detection)
    words = clean.split()
    for word in words:
        # Extremely long words are suspicious
        if len(word) > 12:
            # Check vowel variety in long words
            vowels = set(re.findall(r'[aeiouáéíóúü]', word))
            # If a word is >12 chars and has only 1 type of vowel or no vowels
            if len(vowels) < 2:
                return True
            # Hard limit for 20+ char words (exceeds typical long Spanish words)
            if len(word) > 20:
                return True
            # Check for high character repetition density
            if len(set(word)) < len(word) / 2:
                return True

        # Words without vowels (excluding very short ones)
        if len(word) > 6:
            if not re.findall(r'[aeiouáéíóúü]', word):
                return True

    # 5. Overwhelming lack of vowels across multiple short words
    if len(words) > 4:
        # Note: 'y' is treated as a vowel here to avoid flagging valid Spanish conjunctions as gibberish
        vowelless_words = [w for w in words if not re.search(
            r'[aeiouáéíóúüiy]', w) and re.search(r'[a-z]', w)]
        if len(vowelless_words) > len(words) / 2:
            return True

    # 4. Nonsense non-alphanumeric density
    # If more than 35% of the string is symbols/garbage
    if len(clean) > 8:
        symbols = re.findall(r'[^a-z0-9\sáéíóúüñ]', clean)
        if len(symbols) / len(clean) > 0.35:
            return True

    # 6. Low unique character density (spamming a few keys repeatedly like "us fs asf fas")
    letters_only = re.sub(r'[^a-z]', '', clean)
    if len(letters_only) > 12:
        unique_letters = len(set(letters_only))
        if unique_letters / len(letters_only) < 0.3:
            return True

    # 7. Average word length check (keyboard smashing with spaces)
    if len(words) > 4:
        avg_word_length = len(letters_only) / len(words)
        if avg_word_length < 2.5:
            return True

    return False
