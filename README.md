# Django Rest Framework Project

## GOAL
This project is used to make API for a AI Chatbot to search and make suggestions using LnagChain and MongoDB

## SPTEPS
1. Seting the project:
    - set virtual enviroment: ```python3 -m venv venv```  venv at the end is the folder name (if use .env it will be hidden)
    - got to venv: ```source venv/bin/activate``` now you are in virtual envieroment
        - Check the dependencies: ```pip list ```
        - intall: ```pip install django djangorestframework pymongo langchain openai python-dotenv ```
    - create and  name the general project: ```django-admin startproject mequedo_ai .``` // the point(.) at the end isß neccesary to create the folder inside the general project.
    - creates the apps for the project: ej ```python3 manage.py startapp chatbot``` and apply migtations: ej: ```python3 manage.py migrate``` then, it does all migrations for dafaul.  a db.sqlite that can be changed to postgeSQL or mongoDB
    - in setting of the project, register the apps created before: ej: ```chatbot``` and ``` rest-framework``.
    - inside chatbot, create urls.py with a list urlpatterns= []
    -inside mequedo_ai register the ```route: path("api/", ("chatbot.urls"))```
    - watch the server with ```python3 manage.py runserver ```

2. API views:
    - create  APIview in chatbot/views.py,could be  a Post method ChatbotView.
    - create a path (ej. path('query/', ChatbotView.as_view())). in chatbot/urls.py
3. Test views:
    - in your browser go to http://127.0.0.1:8000/api/query/ and create the request, filling the body with the JSON for the message.
    - you can also test the API from Postman filling the body with the JSON for the message.
==================================== commit

## General Steps:

1. Create a new Django project.
2. set  Django Rest Framework.
3. Create  a basic  endpointusing  DRF.
4. Conect your route API  API from Next.js.
5. Integrate  LangChain y MongoDB:




    







