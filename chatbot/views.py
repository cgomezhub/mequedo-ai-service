import os
from dotenv import load_dotenv
from pymongo import MongoClient
from rest_framework.views import APIView
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
        "timeout": 10,  # Establece un timeout de 20 segundos para la llamada a la API
        "max_retries": 2, # Reintenta la llamada hasta 2 veces en caso de fallo
    })

    print("✅ LLM de NVIDIA inicializado.")
except Exception as e:
    print(f"❌ Error al inicializar el LLM de NVIDIA: {e}")
    llm = None

# 3. Plantilla de Prompt para LangChain
template = """
Eres un asistente de IA para "Mequedo", un marketplace de alquiler de alojamientos en Venezuela. Tu objetivo es ayudar a los usuarios a encontrar el alojamiento ideal.

**Instrucciones:**
1.  **Si el "Contexto de Alojamientos" NO está vacío:** Usa la información de los alojamientos para responder la pregunta del usuario de forma amable y servicial. Menciona las opciones encontradas y sus características. No formatees la respuesta como una tabla.
2.  **Si el "Contexto de Alojamientos" ESTÁ VACÍO:** Esto significa que no se encontraron resultados. Tu respuesta debe variar según la situación:
    *   **Si parece que el usuario mencionó una ciudad:** Es probable que haya un error tipográfico o que no tengamos alojamientos en esa ciudad. Responde amablemente, informa que no encontraste resultados para la ubicación solicitada y sugiere ciudades disponibles. Puedes decir algo como: "No encontré alojamientos en la ciudad que mencionaste. Quizás fue un error al escribir. Tenemos opciones en estas ciudades: {available_cities}. ¿Te gustaría buscar en alguna de ellas?".
    *   **Si el usuario NO mencionó una ciudad o su pregunta es muy general:** Preséntate amablemente y haz preguntas para recopilar la información que necesitas. Responde exactamente con este texto: "¡Hola! Soy tu asistente de búsqueda de hopedajes en Mequedo. Para ayudarte a encontrar tu lugar ideal, por favor, indícame: ¿A qué ciudad deseas viajar? ¿Para cuántas personas? ¿Buscas una habitación o un alojamiento completo? ¿Y cuáles son tus fechas de entrada y salida?".
3. **Manejo de precios:**
    *   Si el usuario proporciona un rango de precios pero no una ciudad, pregunta en qué ciudad está interesado.
    *   Si el usuario proporciona una ciudad y un rango de precios, busca alojamientos que cumplan con ambos criterios.

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
            # 1. Obtener alojamientos de MongoDB (limitado para no sobrecargar)
            # Paso 1: Buscar si el mensaje del usuario contiene una ciudad de nuestra BD
            # y crear un mapa de ubicaciones para enriquecer el contexto.
            found_location_ids = [] # Usaremos una lista para todas las coincidencias
            all_locations = list(locations_collection.find({}, {"_id": 1, "city": 1}))
            locations_map = {loc['_id']: loc['city'] for loc in all_locations}
            print(f"Ubicaciones disponibles en la BD: {locations_map}")
            user_message_lower = user_message.lower()

            for loc in all_locations:
                # Si la ciudad de la BD está en el mensaje del usuario...
                if loc['city'].lower() in user_message_lower:
                    # ...la añadimos a nuestra lista de IDs.
                    found_location_ids.append(loc['_id'])
            
            if found_location_ids:
                print(f"IDs de ubicación encontrados para la ciudad: {found_location_ids}")
            
            # Paso 2: Construir el filtro de búsqueda dinámicamente
            listing_filter = {"isApproved": True}
            if found_location_ids:
                # Usamos el operador $in para buscar en todos los IDs encontrados
                listing_filter["locationId"] = {"$in": found_location_ids}
            
            # Paso 2.5: Extraer y aplicar filtros de precio
            price_query = extract_price_filters(user_message)
            print(f"Filtro de precio extraído: {price_query}")
            if price_query:
                listing_filter["price"] = price_query

            print(f"Filtro de búsqueda final aplicado: {listing_filter}")

            # Paso 3: Realizar la consulta a la base de datos con el filtro construido
            if found_location_ids:
                listings_cursor = listings_collection.find(listing_filter, {
                    "title": 1, "price": 1, "category": 1, "slug": 1, "locationId": 1, "_id": 0
                }).limit(10)
            else:
                listings_cursor = []

            available_cities_str = ", ".join(sorted(list(set(locations_map.values()))))

            if (not found_location_ids and price_query) or (not found_location_ids and not price_query):
                bot_response_content = f"Tenemos opciones en estas ciudades: {available_cities_str}. ¿En cual de ellas te gustaría?"
                return Response({"response": bot_response_content, "listings": []}, status=status.HTTP_200_OK)

            # if not found_location_ids and not price_query:
            #     bot_response_content = f"Tenemos opciones en estas ciudades: {available_cities_str}. ¿Te gustaría buscar en alguna de ellas?"
            #     return Response({"response": bot_response_content, "listings": []}, status=status.HTTP_200_OK)
            
            listings_list = list(listings_cursor)
            print(f"Alojamientos encontrados tras el filtro: {len(listings_list)}, listings_list: {listings_list}")
            
            # Enriquecer listings_list con el nombre de la ciudad para el frontend
            enriched_listings_list = []
            for listing in listings_list:
                listing_with_city = listing.copy()
                listing_with_city['city'] = locations_map.get(listing.get('locationId'), 'N/A')
                enriched_listings_list.append(listing_with_city)
                
            serialable_enriched_listings_list = []
            for l in enriched_listings_list:
                serialable_listing = l.copy()
                if isinstance(serialable_listing.get('locationId'), ObjectId):
                    serialable_listing['locationId'] = str(serialable_listing['locationId'])
                serialable_enriched_listings_list.append(serialable_listing)

            # Paso 4: Construir el contexto para el LLM
            listings_context = "\n".join([
                f"- Título: {l.get('title', 'N/A')}, Categoría: {l.get('category', 'N/A')}, Precio: ${l.get('price', 0)}, Ubicación: {locations_map.get(l.get('locationId'), 'N/A')}" for l in listings_list
            ])
            # Paso 5: Crear y ejecutar la cadena de LangChain
            print("listings_context:", listings_context)
            
            # available_cities_str = ", ".join(locations_map.values())
            print("Ciudades disponibles:", available_cities_str)
            print("user_message:", user_message)

            chain = prompt | llm

            bot_response = chain.invoke({
                "available_cities": available_cities_str,
                "listings_context": listings_context,
                "user_question": user_message
            }) # Esta es la respuesta de texto del LLM

            print("bot_response:", bot_response.content)

            # Devolver tanto la respuesta de texto del LLM como los datos de los alojamientos enriquecidos
            return Response({"response": bot_response.content, "listings": serialable_enriched_listings_list}, status=status.HTTP_200_OK)

        except openai.NotFoundError:
            print(f"❌ Error: El modelo de IA no fue encontrado. Revisa el nombre del modelo o la URL base de la API.")
            return Response(
                {"error": "El modelo de IA configurado no está disponible. Contacta al administrador."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            print(type(e))
            print(f"❌ Error al procesar la solicitud del chatbot: {e}")
            return Response(
                {"error": "Ocurrió un error al generar la respuesta."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
