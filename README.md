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
    -inside mequedo_ai register the ```route: path("api/", ("nameoftheapp.urls))```
    - watch the server with ```python3 manage.py runserver ```





