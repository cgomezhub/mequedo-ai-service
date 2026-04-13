# Gemini Project Context: Mequedo AI Service

This project is a Django-based AI service for **Mequedo**, an accommodation platform in Venezuela. It provides a chatbot (Laura) for searching listings and integrates with WhatsApp for notifications and interactions.

## Tech Stack

- **Framework:** Django with Django Rest Framework (DRF)
- **AI Orchestration:** CrewAI (Multi-Agent System), formerly LangChain
- **LLMs:** OpenAI and NVIDIA AI Endpoints (e.g., Llama 3)
- **Database:** MongoDB (Listings, Locations, Scheduled Tasks) and SQLite (Django default)
- **Integrations:** WhatsApp Cloud API (Using background threading)

## Core Persona: Laura

- **Name:** Laura
- **Role:** Accommodation search assistant for Mequedo in Venezuela.
- **Tone:** Professional, helpful, and concise.
- **Language:** Primarily Spanish for user interactions.
- **Constraint:** Only suggest accommodations found in the provided database context.

## Coding Standards & Guidelines

### 1. General Style

- Follow **PEP 8** for Python code.
- Use **Type Hints** for function signatures to improve clarity and maintainability.
- Provide **Docstrings** for classes and important functions.

### 2. Error Handling & Logging

- Use the `logging` module to log errors and important events.
- Implement robust `try-except` blocks, especially around external service calls (MongoDB, LLM, WhatsApp).
- Never expose sensitive system details or raw error messages to the end user in production.

### 3. Security

- **Sanitize Input:** Always sanitize user-provided strings to prevent injections or malicious content.
- **Prompt Injection:** Be vigilant about prompt injection patterns (see `chatbot/views.py` for existing regex patterns).
- **Rate Limiting:** Use DRF's throttling for public-facing endpoints.

### 4. Database Interactions

- This project heavily uses **MongoDB** via `pymongo` for dynamic data like listings and scheduled tasks.
- Ensure `ObjectId` validations are in place when querying by ID.
- Use `certifi` for SSL/TLS connections to MongoDB.

### 5. Asynchronous Processing

- WhatsApp webhooks should acknowledge Meta's request immediately (200 OK) and process the message logic in the background (currently using threading; consider Celery for more complex tasks).

## Key Files & Directories

- `chatbot/views.py`: Main AI logic and chatbot API.
- `whatsapp_integration/views.py`: Webhook handlers for WhatsApp.
- `whatsapp_integration/message_handler.py`: Logic for parsing and responding to WhatsApp messages.
- `whatsapp_integration/services.py`: External service integrations (e.g., WhatsApp Cloud API).
- `manage.py`: Django management script.

## Interaction with Gemini

When assisting with this codebase:

- Maintain the "Laura" persona logic when editing chatbot prompts.
- Prefer clear, modular code.
- Ensure any new endpoints follow the established DRF patterns used in the project.
- Respect the existing mixture of English (for code/logic) and Spanish (for user-facing content and some comments).
