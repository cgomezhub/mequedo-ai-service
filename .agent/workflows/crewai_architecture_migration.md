---
description: Migration of Mequedo AI Service to a genuine Multi-Agent CrewAI architecture with CRM capabilities
---

# CrewAI Multi-Agent Architecture Migration

> **Contextual Agent Protocol**
>
> - **Identity:** You are a Senior AI Agent Engineer specializing in CrewAI, LangChain, and Django.
> - **Purpose:** Your purpose is orchestrating a complete migration from a deterministic pipeline to an advanced CrewAI multi-agent application.
> - **Process:** You will define optimal, fault-tolerant tools, design cross-agent caching, configure synchronous and asynchronous tasks, and manage memory parameters to ensure high performance and CRM readiness.
> - **Objective:** Build a scalable CrewAI system consisting of Specialist, QA, and Support agents, generating highly structured and validated outputs suitable for WhatsApp and future integrations.

## Phase 1: Environment & Orchestration Setup

1. **LLM Configuration & Optimization**
   - [ ] Configure primary LangChain LLMs: Provide a "Fast" reasoning model for simple routing (e.g., `gpt-4o-mini` or Llama 3 8B) and a "Deep" reasoning model for the Specialist/QA Agents (e.g., `gpt-4o` or Llama 3 70B).
   - [ ] Enable CrewAI Memory Systems: Short-Term Memory, Long-Term Memory (SQLite/MongoDB), and Entity Memory for user tracking.
   - [ ] Enable CrewAI cross-agent caching to prevent duplicate database or web scraping queries during multi-agent discussions.

## Phase 2: Agent Design (The Crew)

1. **Accommodation Specialist Agent**
   - [ ] **Role:** Expert Database Researcher.
   - [ ] **Goal:** Retrieve exact Mequedo listings matching complex user criteria.
   - [ ] **Tools:** `SearchAccommodationTool`.
   - [ ] **Hyperparameters:** `max_iter=3` (fault tolerance), `allow_delegation=False`.

2. **Customer Support Agent (Laura)**
   - [ ] **Role:** Empathetic FAQ, Booking Assistant, and Brand Ambassador.
   - [ ] **Goal:** Resolve user inquiries based on Mequedo's knowledge base and format the final output.
   - [ ] **Tools:** `ScrapeWebsiteTool` (Mequedo FAQ), future `MequedoInternalCRMTool`.
   - [ ] **Hyperparameters:** `allow_delegation=True` (can delegate searches to the Specialist).

3. **Quality Assurance (QA) Agent**
   - [ ] **Role:** Content Validator & Hallucination Checker.
   - [ ] **Goal:** Ensure all generated responses strictly adhere to Mequedo's available context and pricing rules.
   - [ ] **Hyperparameters:** `allow_delegation=False`.

## Phase 3: Tool Engineering

1. **Custom & Built-in Tools Setup**
   - [ ] **`SearchAccommodationTool` (Custom):** Connects to PyMongo. Must enforce strict Pydantic schemas for arguments (`city`, `max_price`, `guests`).
   - [ ] **`MequedoFAQScraperTool` (Built-in `ScrapeWebsiteTool`):** Targets the Mequedo documentation / FAQ pages.
   - [ ] **Mequedo Internal Database Tool (CRM):** Tool to seamlessly fetch user reservation data, booking history, and profile status directly from Mequedo's internal MongoDB (Next.js Dashboard integration).
   - [ ] **`WhatsAppNotifierTool` (Custom):** Triggers proactive follow-ups out of band.

## Phase 4: Task Definition & Execution Strategy

1. **Task Instantiation**
   - [ ] **`IntentExtractionTask`:** Determines if the user wants an FAQ answer, a listing search, or CRM support. Outputs a structured JSON object (`output_json=IntentSchema`) using Pydantic.
   - [ ] **`DatabaseSearchTask`:** Assigned to Specialist. Receives `context` from `IntentExtractionTask`.
   - [ ] **`QAValidationTask`:** Assigned to QA Agent. Validates the search data. Uses `human_input=True` _only in development mode_ for manual approval before continuing.
   - [ ] **`FormatReplyTask`:** Assigned to Laura. Synthesizes inputs into a final conversational message.
2. **Advanced Task Execution Flow**
   - [ ] **Human Handoff Bypass:** Implement a DB check for `is_human_paused=True` _before_ calling `crew.kickoff()`. If true, bypass the AI execution completely so the admin can chat manually via the Next.js Dashboard.
   - [ ] **Conversational Logging:** Ensure the webhook logic saves _both_ the User's message and the CrewAI output to a MongoDB `Conversations` collection for rendering in the Next.js CRM UI.
   - [ ] Implement `async_execution=True` for background logging tasks so they execute in parallel without delaying the final user response.
   - [ ] Implement Task `callbacks` on the final output to decouple generation from the Django HTTP Webhook response (maintaining the 200 OK rule).

## Phase 5: Testing & Quality Assurance (MANDATORY)

1. **Test Environment Preparation**
   - [ ] Identify external dependencies (MongoDB, WhatsApp API, LLMs) and set up necessary test databases using established Django patterns.
   - [ ] Ensure co-location of tests (e.g., `tests/` directory).

2. **Automated Test Creation**
   - [ ] Create unit tests for custom Agentic Tools (ensuring Pydantic schemas validate correctly).
   - [ ] Create integration tests for Django API routes (Verify Webhook background threading handles CrewAI execution time gracefully).

3. **Verification & Validation**
   - [ ] Run `python manage.py test` or `pytest`.
   - [ ] Check logs for Agent execution transparency to verify cross-agent caching and Memory are working efficiently.
