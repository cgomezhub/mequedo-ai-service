# Mequedo AI Service (Django)

This project is a Django-based AI service for **Mequedo**, an accommodation platform in Venezuela. It provides a chatbot (Karen) for searching listings and integrates with WhatsApp for notifications and interactions.

## Tech Stack
- **Framework:** Django with Django Rest Framework (DRF)
- **AI Orchestration:** CrewAI (Multi-Agent System)
- **Database:** MongoDB (Listings, Locations, Scheduled Tasks)
- **LLMs:** OpenAI and NVIDIA AI Endpoints (Llama 3)
- **Integrations:** WhatsApp Cloud API

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
Copy `.env.template` to `.env` and fill in the required variables:
- `DATABASE_URL`: MongoDB connection string.
- `MONGODB_DB_NAME`: MongoDB database name.
- `MEQUEDO_SECRET_TOKEN`: Shared secret for Next.js callbacks.
- `NVIDIA_API_KEY`: API key for LLM agents.
- `WHATSAPP_ACCESS_TOKEN`: Meta WhatsApp API token.

### 3. Running the API (Web Process)
To start the main API server for the chatbot and WhatsApp webhooks:
```bash
python manage.py runserver
```

---

## Reservation Scheduler (Worker)

The project includes a background worker responsible for handling reservation expirations. It polls MongoDB for tasks that are due and notifies the Next.js frontend to release the properties.

### How it works:
1. **Polling:** The worker checks the `ScheduledTask` collection in MongoDB every 60 seconds.
2. **Identification:** It looks for tasks with `status: "pending"` where `executeAt <= now`.
3. **Callback:** For each due task, it sends a POST request to the `callbackUrl` (Next.js endpoint) with the `reservationId` and `MEQUEDO_SECRET_TOKEN`.
4. **Completion:** It updates the task status in MongoDB based on the response.

### Running the Worker in Development:
Open a **separate terminal**, activate your venv, and run:
```bash
python manage.py run_reservation_scheduler
```

### Running in Production:
In production (e.g., Railway/Heroku), the worker is managed by the `Procfile`:
```yaml
worker: python manage.py run_reservation_scheduler
```

---

## Testing
- **Chatbot API:** POST to `http://127.0.0.1:8000/api/chatbot/` with a JSON body: `{"message": "Busco casa en Lechería"}`.
- **WhatsApp Webhook:** Use the `test_whatsapp_webhook.sh` script to simulate incoming messages.
