import logging
import unicodedata

logger = logging.getLogger(__name__)


def get_short_circuit_response(user_message: str, user_id: str = "WEB_ANONYMOUS") -> str | None:
    """
    Checks if the user message matches any predefined "Fast response" templates.
    Returns the response string if a match is found, otherwise None.
    """
    normalized_msg = user_message.strip().lower()

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
            "¡Hola! Soy Karen. No he podido comprender tu mensaje, ya que parece contener caracteres aleatorios o repetidos.\n\n"
            "Mequedo es una plataforma profesional para la renta de alojamientos. Por favor, escribe una pregunta clara "
            "en español o utiliza nuestro [Menú de Ayuda](action:menu) para guiarte."
        )

    crm_keywords = ["mis reservaciones", "mis reservas", "mis alojamientos",
                    "mis listados", "mis propiedades", "mis compras", "mis viajes", "mi cuenta", "mis arriendos", "mis publicaciones"]

    # Case 1: Anonymous user trying to access private data
    if (user_id in ["WEB_ANONYMOUS", "ANONYMOUS"] or user_id.startswith("wa_")) and any(keyword in clean_msg for keyword in crm_keywords):
        # Note: For WhatsApp, we might need a different check for auth, but the keyword trigger is enough to prompt login
        return (
            "¡Hola! Veo que deseas consultar información personal sobre tus propiedades o reservaciones. "
            "Para proteger tu privacidad y poder acceder a estos datos, necesitas iniciar sesión en la plataforma Mequedo primero.\n\n"
            "Selecciona [Iniciar Sesión](action:START_LOGIN) o, si aún no tienes una cuenta, [Registrarme](action:START_REGISTRATION)."
        )

    # Case 2: Basic greetings
    if clean_msg in ["hola", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hey", "saludos", "hola Karen"]:
        return (
            "¡Hola! Soy Karen, la asistente virtual de Mequedo. Estoy aquí para ayudarte a encontrar el alojamiento perfecto "
            "en Venezuela, o responder cualquier duda que tengas sobre nuestra plataforma. ¿En qué ciudad te gustaría buscar hospedaje?"
        )

    # Case 3: Platform Help / Menu
    if clean_msg in ["que hace esta plataforma", "para que es esta plataforma", "que ofrecen", "que es mequedo", "menu", "opciones", "ayuda", "que puedes hacer"]:
        return (
            "Mequedo es la plataforma líder en renta y reserva de alojamientos en Venezuela, ofreciendo un entorno seguro y verificado.\n\n"
            "¡Estoy aquí para guiarte! Puedes pedirme que busque hospedajes en cualquier ciudad, o consultar estas opciones:\n\n"
            "[🏠 Publicar mi alojamiento](action:START_RENT_PROCESS)\n"
            "[🤝 ¿Quiénes somos?](action:START_ABOUT_US)\n"
            "[👤 Crear mi cuenta](action:START_REGISTRATION)\n"
            "[❓ Preguntas frecuentes](action:START_FAQ)\n"
            "[📋 Términos y Reglas](action:START_TERMS)"
        )

    is_wa = user_id.startswith("wa_")

    # Case 4: About us
    if clean_msg in ["quienes son ustedes y por que confiar en mequedo", "quienes son ustedes", "por que confiar", "start_about_us"]:
        video_element = (
            "▶️ Mira este video sobre nosotros: https://www.youtube.com/watch?v=5r9x0GuHd_U"
            if is_wa else
            "<iframe width=\"100%\" height=\"350\" src=\"https://www.youtube.com/embed/5r9x0GuHd_U\" frameborder=\"0\" allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen style=\"border-radius: 12px; margin-top: 10px;\"></iframe>"
        )
        return (
            "¡Hola! Mequedo es la plataforma líder en renta y reserva de alojamientos en Venezuela. "
            "Nuestro objetivo es transformar la forma de hospedarse en el país, ofreciendo un entorno seguro, profesional y verificado.\n\n"
            "Para empezar a disfrutar de nuestras opciones, [Registrarme](action:START_REGISTRATION) es el primer paso. "
            "Si ya tienes una cuenta, pero no has verificado tu identidad, por favor selecciona [Verificar Identidad](action:START_ID_VERIFICATION) para continuar.\n\n"
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
        # tudren_link = (
        #     "*TuDrenViajes* (https://www.tudrenviajes.com/)" # Single asterisk for WhatsApp bold
        #     if is_wa else
        #     "🔗 [TuDrenViajes](https://www.tudrenviajes.com/)"
        # )
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

    return None


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
