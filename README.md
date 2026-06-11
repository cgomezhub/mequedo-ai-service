# Mequedo AI Service (Django)

This project is a Django-based AI service for **Mequedo**, an accommodation platform in Venezuela. It provides a chatbot (Karen) for searching listings and integrates with WhatsApp for notifications, interactions, and background workflows.

## Table of Contents

- [Tech Stack](#tech-stack)
- [Architecture & Design](#architecture--design)
  - [CrewAI Multi-Agent System](#crewai-multi-agent-system)
  - [Async Chatbot Endpoint (Timeout Prevention)](#async-chatbot-endpoint-timeout-prevention)
  - [Intent Routing & LLM Fallbacks](#intent-routing--llm-fallbacks)
  - [WhatsApp Webhook & Message Handler](#whatsapp-webhook--message-handler)
  - [Guest Firewall & Response Caching](#guest-firewall--response-caching)
- [Getting Started](#getting-started)
  - [1. Environment Setup](#1-environment-setup)
  - [2. Configuration (.env)](#2-configuration-env)
  - [3. Running the API (Web Process)](#3-running-the-api-web-process)
- [Reservation Scheduler (Worker)](#reservation-scheduler-worker)
- [Testing](#testing)

---

## Tech Stack

- **Framework:** Django with Django Rest Framework (DRF)
- **AI Orchestration:** CrewAI (Multi-Agent System) with optional legacy LangChain fallback
- **Database:** MongoDB (Listings, Locations, Scheduled Tasks) & SQLite (Django default)
- **LLMs:** NVIDIA AI Endpoints (e.g. Llama 3), Google Gemini, and OpenAI
- **Integrations:** WhatsApp Cloud API

---

## Architecture & Design

### CrewAI Multi-Agent System
The core AI orchestration uses **CrewAI** (toggled via the `USE_CREWAI` env var). It features a multi-agent system designed to handle search and support flows:
- **AccommodationSpecialist:** Specialized in querying listings from MongoDB and formatting accommodation options matching the user's constraints (location, budget, amenities).
- **CustomerSupportAgent (Karen):** Standardized core persona providing helpful, concise, and professional accommodation search assistance in Spanish, restricted to the provided database context.

### Async Chatbot Endpoint (Timeout Prevention)
To prevent server and gateway (e.g., Vercel) timeouts during long-running LLM/CrewAI operations (which can exceed 30 seconds), the service uses asynchronous polling endpoints:
- `ChatbotAsyncView`: Initiates the chat processing task and immediately returns a job/task status ID.
- `ChatbotStatusView`: Clients poll this view to check execution status and retrieve the final response once complete.

### Intent Routing & LLM Fallbacks
Every incoming query passes through an **Intent Router** utilizing `IntentSchema` and direct LLM calls to determine whether to run search crews, trigger template replies, or handle off-topic chat.
- **Provider Fallback Chain:** If the primary LLM fails, the system cascades down the configured provider list: **NVIDIA NIM -> Gemini -> OpenAI**.
- **Retry Mechanism (`_kickoff_with_retry`):** Automatically handles rate limits and API errors using exponential backoff/retry.

### WhatsApp Webhook & Message Handler
Handles incoming WhatsApp messages asynchronously to ensure immediate acknowledgement (200 OK) to Meta:
- **Fast-Template Short-Circuit:** Automatically handles greeting menus, support requests, and gibberish/spam detection to reduce LLM costs.
- **Dynamic Interactive UI:** Supports interactive buttons. If interactive options exceed 3, the message handler automatically falls back to an Interactive List menu (adhering to Meta's 24-character label limit).
- **Notification Templates:** Sends multi-channel notification updates for:
  - `reservation_request_notice`
  - `reservation_payment_notice`
  - `host_payment_notice`
  - `guest_payment_notice`
  - `admin_payment_review`
  - Host/Guest payment rejection notifications.

### Guest Firewall & Response Caching
- **Guest Firewall:** Restricts CrewAI agent execution to registered/logged-in phone numbers to prevent token abuse, returning conversion prompts to non-registered guests.
- **Response Caching:** Caches chatbot responses for 60 seconds (`_RESPONSE_CACHE`) to avoid duplicate processing on network retries.

---

## Getting Started

### 1. Environment Setup

- **Create virtual environment:**
  ```bash
  python3 -m venv venv
  ```
- **Activate virtual environment:**
  ```bash
  source venv/bin/activate
  ```
- **Install dependencies:**
  ```bash
  pip install -r requirements.txt
  ```

### 2. Configuration (.env)

Ensure you populate your `.env` file with these configuration keys:

```bash
# Django Settings
DEBUG=True
SECRET_KEY=your_secret_key
LOG_LEVEL=INFO   # DEBUG, INFO, WARNING, ERROR

# MongoDB Configuration
DATABASE_URL=mongodb+srv://...
MONGODB_DB_NAME=mequedo

# Security & Verification
MEQUEDO_SECRET_TOKEN=your_shared_secret_token
ADMIN_WHATSAPP_NUMBERS=+58412XXXXXX,+58414XXXXXX

# AI Orchestration & Fallbacks
USE_CREWAI=True

# LLM Providers & Keys
NVIDIA_API_KEY=nvapi-...
GEMINI_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-proj-...

# Fast Model Schemas
NVIDIA_FAST_MODEL=meta/llama3-8b-instruct
GEMINI_FAST_MODEL=gemini-1.5-flash
OPENAI_FAST_MODEL=gpt-4o-mini

# WhatsApp Integration
WHATSAPP_ACCESS_TOKEN=your_meta_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=your_webhook_verification_token
```

### 3. Running the API (Web Process)

To start the main API server for the chatbot and WhatsApp webhooks:

```bash
python manage.py runserver
```

---

## Reservation Scheduler (Worker)

The background worker manages reservation expirations by polling the MongoDB database.

### How it works:
1. **Polling:** Every 60 seconds, the worker checks the `ScheduledTask` collection.
2. **Identification:** It queries pending tasks where `executeAt <= now`.
3. **Execution & Callback:** Sends a POST request to the Next.js backend with `reservationId` and `MEQUEDO_SECRET_TOKEN`.
4. **Logging & Security:** Masking is implemented to ensure database credentials containing passwords are never exposed in terminal console logs.

### Running the Worker in Development:

```bash
python manage.py run_reservation_scheduler
```

### Running in Production:
Managed via the `Procfile`:
```yaml
worker: python manage.py run_reservation_scheduler
```

---

## Testing

- **Chatbot API:** POST to `http://127.0.0.1:8000/api/chatbot/` with:
  ```json
  {
    "message": "Busco casa en Lechería"
  }
  ```
- **WhatsApp Webhook:** Use the `test_whatsapp_webhook.sh` script to simulate incoming webhook events.
