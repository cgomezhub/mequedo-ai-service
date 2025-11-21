import os
from dotenv import load_dotenv
from pymongo import MongoClient
from rest_framework.views import APIView
from bson.objectid import ObjectId
import certifi
from rest_framework.response import Response
from rest_framework import status
import openai
import re
from bson import ObjectId

# LangChain imports
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import PromptTemplate

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# --- Configuración de Conexiones (fuera de la vista para eficiencia) ---

# 1. Conexión a MongoDB
try:
    client = MongoClient(os.getenv("DATABASE_URL"), tlsCAFile=certifi.where())
    # Asegúrate de usar el nombre correcto de tu base de datos y colección
    db = client.get_database("test")
    listings_collection = db.get_collection("Listing")
    # Añadimos la colección de ubicaciones
    locations_collection = db.get_collection("Location")
    print("✅ Conexión a MongoDB exitosa.")
except Exception as e:
    print(f"❌ Error al conectar a MongoDB: {e}")
    listings_collection = locations_collection = None

# 2. Inicialización del LLM (usando el modelo de NVIDIA)
try:
    llm = ChatNVIDIA(
        model="openai/gpt-oss-20b",
        nvidia_api_key=os.getenv("NVIDIA_API_KEY"),
        temperature=1,
        top_p=1,
        max_tokens=1000,
    ).with_config({
        "timeout": 20,  # Aumentamos el timeout a 20 segundos para dar más margen al LLM
        "max_retries": 2, # Reintenta la llamada hasta 2 veces en caso de fallo
    })

    print("✅ LLM de NVIDIA inicializado.")
except Exception as e:
    print(f"❌ Error al inicializar el LLM de NVIDIA: {e}")
    llm = None

# 3. Plantilla de Prompt para LangChain
template = """
Eres un asistente de inteligencia artificial para "Mequedo", un marketplace de alquiler de alojamientos en Venezuela. Tu objetivo es ayudar a los usuarios a encontrar el mejor alojamiento según sus necesidades. 

**Instrucciones:**
1.  **Si el "Contexto de Alojamientos" NO está vacío:** Usa la información de los alojamientos para responder la pregunta del usuario de forma amable y servicial. Menciona las opciones encontradas y sus características. insta al usuario a hacer click en las opciones que le brindas. No formatees la respuesta como una tabla.
2.  **Si el "Contexto de Alojamientos" ESTÁ VACÍO:** Esto significa que no se encontraron resultados. Tu respuesta debe variar según la situación:
    *   **Si parece que el usuario mencionó una ciudad:** Es probable que haya un error tipográfico o que no tengamos alojamientos en esa ciudad. Responde amablemente, informa que no encontraste resultados para la ubicación solicitada y sugiere ciudades disponibles. Puedes decir algo como: "No encontré alojamientos en la ciudad que mencionaste. Quizás fue un error al escribir. Tenemos opciones en estas ciudades: {available_cities}. ¿Te gustaría buscar en alguna de ellas?".
    *   **Si el usuario NO mencionó una ciudad o su pregunta es muy general:** Preséntate amablemente y haz preguntas para recopilar la información que necesitas. Responde exactamente con este texto: "¡Hola! Soy tu asistente de búsqueda de hopedajes en Mequedo. Para ayudarte a encontrar tu lugar ideal, por favor, indícame: ¿A qué ciudad deseas viajar? ¿Para cuántas personas? ¿Buscas una habitación o un alojamiento completo? ¿Y cuáles son tus fechas de entrada y salida?".
3. **Manejo de precios:**
    *   Si el usuario proporciona un rango de precios pero no una ciudad, pregunta en qué ciudad está interesado.
    *   Si el usuario proporciona una ciudad y un rango de precios, busca alojamientos que cumplan con ambos criterios.

Usa solamente la siguiente lista de alojamientos disponibles como contexto para responder a la pregunta del usuario. Sé amable, conversacional y servicial. Cuando presentes una lista de varios alojamientos, formatea tu respuesta como una tabla usando Markdown.
Si la pregunta no se relaciona con la búsqueda de alojamientos o no existen datos en la lista, responde amablemente que solo puedes ayudar con temas de la plataforma Mequedo y que es necesario que indique al menos la ciudad para iniciar una la busqueda.
 
Contexto de Alojamientos:
{listings_context}

Ciudades Disponibles:
{available_cities}


Pregunta del Usuario:
"{user_question}"

Respuesta del Asistente:
"""

prompt = PromptTemplate(template=template, input_variables=["listings_context", "user_question", "available_cities"])

def extract_price_filters(text):
    """
    Extrae filtros de precio de un texto usando expresiones regulares.
    Devuelve un diccionario para un filtro de MongoDB.
    """
    price_filter = {}
    text_lower = text.lower()

    # 1. Rango de precios (ej: "entre 20 y 50", "de 20 a 50")
    range_match = re.search(r'(?:entre|de)\s+\$?(\d+)\$?\s*(?:y|a)\s+\$?(\d+)\$?', text_lower)
    if range_match:
        min_price = int(range_match.group(1))
        max_price = int(range_match.group(2))
        price_filter['$gte'] = min(min_price, max_price)
        price_filter['$lte'] = max(max_price, min_price)
        return price_filter

    # 2. Precio máximo (ej: "menos de 50", "hasta 50", "no más de 50")
    max_match = re.search(r'(?:menos de|menor a|hasta|no más de|no mas de|maximo|máximo)\s+\$?(\d+)\$?', text_lower)
    if max_match:
        price_filter['$lte'] = int(max_match.group(1))

    # Se podrían añadir más condiciones como precio mínimo si fuera necesario.
    return price_filter


class ChatbotView(APIView):
    def post(self, request, *args, **kwargs):
        user_message = request.data.get("message", "")
        if not user_message:
            return Response(
                {"error": "Message is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if listings_collection is None or locations_collection is None or llm is None:
            return Response(
                {"error": "El servicio de IA no está configurado correctamente. Revisa las conexiones."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            # --- Paso 1: Extraer información de la pregunta del usuario ---

            # Crear un mapa de todas las ubicaciones disponibles para búsquedas eficientes
            all_locations = list(locations_collection.find({}, {"_id": 1, "city": 1}))
            locations_map = {loc['_id']: loc['city'] for loc in all_locations}
            available_cities_str = ", ".join(sorted(list(set(locations_map.values()))))

            # Buscar IDs de ubicación que coincidan con el mensaje del usuario
            found_location_ids = []
            user_message_lower = user_message.lower()
            for loc in all_locations:
                if loc['city'].lower() in user_message_lower:
                    found_location_ids.append(loc['_id'])
            
            # Extraer filtros de precio del mensaje del usuario
            price_query = extract_price_filters(user_message)
           

            # --- Paso 2: Lógica de respuesta temprana si no se encuentra una ciudad ---

            # Si no se especifica una ciudad, no podemos buscar. Devolvemos una respuesta guiada.
            if not found_location_ids:
                bot_response_content = f"No he podido identificar una ciudad en tu búsqueda. Tenemos opciones en estas ciudades: {available_cities_str}. ¿En cuál de ellas te gustaría buscar?"
                return Response({"response": bot_response_content, "listings": []}, status=status.HTTP_200_OK)

            # --- Paso 3: Búsqueda en la Base de Datos ---

            # Construir el filtro de búsqueda dinámicamente
            listing_filter = {"isApproved": True}
            listing_filter["locationId"] = {"$in": found_location_ids}
            if price_query:
                listing_filter["price"] = price_query

            listings_cursor = listings_collection.find(listing_filter, {
                "title": 1, "price": 1, "category": 1, "slug": 1, "locationId": 1, "_id": 0
            }).limit(10)
            listings_list = list(listings_cursor)
            
            # --- Paso 4: Preparar datos para el LLM y el Frontend ---

            # Enriquecer los resultados con el nombre de la ciudad y prepararlos para la serialización JSON
            serializable_enriched_listings = []
            for listing in listings_list:
                enriched_listing = listing.copy()
                enriched_listing['city'] = locations_map.get(listing.get('locationId'), 'N/A')
                if isinstance(enriched_listing.get('locationId'), ObjectId):
                    enriched_listing['locationId'] = str(enriched_listing['locationId'])
                serializable_enriched_listings.append(enriched_listing)

            # Construir el contexto de texto para el LLM
            listings_context = "\n".join([
                f"- Título: {l.get('title', 'N/A')}, Categoría: {l.get('category', 'N/A')}, Precio: ${l.get('price', 0)}, Ubicación: {l.get('city', 'N/A')}" for l in serializable_enriched_listings
            ])
            # --- Paso 5: Ejecutar el LLM y validar la respuesta ---
            chain = prompt | llm
            bot_response = chain.invoke({
                "available_cities": available_cities_str,
                "listings_context": listings_context,
                "user_question": user_message
            })

            # **VALIDACIÓN CRÍTICA DE LA RESPUESTA DEL LLM**
            # Si la respuesta está vacía o solo contiene espacios, es un fallo.
            if not bot_response.content or not bot_response.content.strip():
                return Response(
                    {"error": "El asistente de IA no pudo generar una respuesta en este momento. Por favor, inténtalo de nuevo."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            # Devolver la respuesta del LLM y la lista de alojamientos enriquecida
            return Response({"response": bot_response.content, "listings": serializable_enriched_listings}, status=status.HTTP_200_OK)

        except openai.NotFoundError: # Específico para errores de modelo no encontrado
            return Response(
                {"error": "El modelo de IA configurado no está disponible. Contacta al administrador."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            return Response(
                {"error": "Ocurrió un error al generar la respuesta."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
