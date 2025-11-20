import os
from dotenv import load_dotenv
from pymongo import MongoClient
from rest_framework.views import APIView
from bson.objectid import ObjectId
import certifi
from rest_framework.response import Response
from rest_framework import status
import openai

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
    )

    print("✅ LLM de NVIDIA inicializado.")
except Exception as e:
    print(f"❌ Error al inicializar el LLM de NVIDIA: {e}")
    llm = None

# 3. Plantilla de Prompt para LangChain
template = """
Eres un asistente de inteligencia artificial para "Mequedo", un marketplace de alquiler de alojamientos en Venezuela. Tu objetivo es ayudar a los usuarios a encontrar el mejor alojamiento según sus necesidades.

Usa solamente la siguiente lista de alojamientos disponibles como contexto para responder a la pregunta del usuario. Sé amable, conversacional y servicial. Cuando presentes una lista de varios alojamientos, formatea tu respuesta como una tabla usando Markdown.
Si la pregunta no se relaciona con la búsqueda de alojamientos o no existen datos en la lista, responde amablemente que solo puedes ayudar con temas de la plataforma Mequedo y que es necesario que indique al menos la ciudad para iniciar una la busqueda.
 
Contexto de Alojamientos:
{listings_context}

Pregunta del Usuario:
"{user_question}"

Respuesta del Asistente:
"""

prompt = PromptTemplate(template=template, input_variables=[
                        "listings_context", "user_question"])


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
            user_message_lower = user_message.lower()

            for loc in all_locations:
                # Si la ciudad de la BD está en el mensaje del usuario...
                if loc['city'].lower() in user_message_lower:
                    # ...la añadimos a nuestra lista de IDs.
                    found_location_ids.append(loc['_id'])
            
            # Paso 2: Construir el filtro de búsqueda dinámicamente
            listing_filter = {"isApproved": True}
            if found_location_ids:
                # Usamos el operador $in para buscar en todos los IDs encontrados
                listing_filter["locationId"] = {"$in": found_location_ids}
    
            # Paso 3: Realizar la consulta a la base de datos con el filtro
            listings_cursor = listings_collection.find(listing_filter, {
                "title": 1, "price": 1, "category": 1, "slug": 1, "locationId": 1, "_id": 0
            }).limit(5)
            
            listings_list = list(listings_cursor)
            
            # Paso 4: Construir el contexto para el LLM
            listings_context = "\n".join([
                f"- Título: {l.get('title', 'N/A')}, Categoría: {l.get('category', 'N/A')}, Precio: ${l.get('price', 0)}, Ubicación: {locations_map.get(l.get('locationId'), 'N/A')}" for l in listings_list
            ])

            # Paso 5: Crear y ejecutar la cadena de LangChain

            chain = prompt | llm

            # bot_response = llm_chain.run(listings_context=listings_context, user_question=user_message)
            bot_response = chain.invoke({
                "listings_context": listings_context,
                "user_question": user_message
            })

            print("bot_response:", bot_response.content)

            # Preparamos una lista segura para la serialización JSON
            serializable_listings = []
            for listing in listings_list:
                # Convertimos el ObjectId a string
                if 'locationId' in listing and isinstance(listing['locationId'], ObjectId):
                    listing['locationId'] = str(listing['locationId'])
                serializable_listings.append(listing)

            return Response({"response": bot_response.content, "listings": serializable_listings}, status=status.HTTP_200_OK)

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
