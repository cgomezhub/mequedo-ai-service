from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class ChatbotView(APIView):
    def post(self, request, *args, **kwargs):
        user_message = request.data.get("message", "")
        if not user_message:
            return Response(
                {"error": "Message is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Here you would typically process the message and generate a response.
        # For demonstration purposes, we'll just echo the message back.
        bot_response = f"Echo: {user_message}"
 
        return Response({"response": bot_response}, status=status.HTTP_200_OK)
    
