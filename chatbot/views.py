import os
from dotenv import load_dotenv
from pymongo import MongoClient
from rest_framework.views import APIView
import certifi
from rest_framework.response import Response
from rest_framework import status
import openai

# LangChain imports
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.prompts import PromptTemplate
# from langchain_classic.chains import LLMChain

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# --- Configuración de Conexiones (fuera de la vista para eficiencia) ---

# 1. Conexión a MongoDB
try:
    client = MongoClient(os.getenv("DATABASE_URL"), tlsCAFile=certifi.where())
    # Asegúrate de usar el nombre correcto de tu base de datos y colección
    db = client.get_database("test")
    listings_collection = db.get_collection("Listing")
    print("✅ Conexión a MongoDB exitosa.")
except Exception as e:
    print(f"❌ Error al conectar a MongoDB: {e}")
    listings_collection = None

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

Usa solamente la siguiente lista de alojamientos disponibles como contexto para responder a la pregunta del usuario. Sé amable, conversacional y servicial.
Si la pregunta no se relaciona con la búsqueda de alojamientos o no existen datos en la lista, responde amablemente que solo puedes ayudar con temas de la plataforma Mequedo puedes usar la direccion https://mequedo.app.

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

        if listings_collection is None or llm is None:
            return Response(
                {"error": "El servicio de IA no está configurado correctamente. Revisa las conexiones."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            # 1. Obtener alojamientos de MongoDB (limitado para no sobrecargar)
            listings_cursor = listings_collection.find({"isApproved": True}, {
                                                       "title":1, "price": 1, "category": 1, "slug":1, "locationId":1, "_id": 0}).limit(10)
            
            print("list-cursor:", type(listings_cursor), listings_cursor._data)
            
            listings_context = "\n".join(
                [f"- Título: {l.get('title', 'N/A')}, Categoría: {l.get('category', 'N/A')}, Precio: ${l.get('price', 0)}" for l in listings_cursor] )

            # 3. Crear y ejecutar la cadena de LangChain
            # llm_chain = LLMChain(prompt=prompt, llm=llm)
            print("listings_context:", listings_context)
            print("user_message:", user_message)

            chain = prompt | llm

            # bot_response = llm_chain.run(listings_context=listings_context, user_question=user_message)
            bot_response = chain.invoke({
                "listings_context": listings_context,
                "user_question": user_message
            })

            print("bot_response:", bot_response.content)

            return Response({"response": bot_response.content},status=status.HTTP_200_OK)

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
