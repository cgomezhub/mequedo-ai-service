---
description: Self-Hosted Multi-Agent Conversational Protocol: A phased rollout plan to replace SaaS subscriptions with a proprietary MongoDB and Redis-backed system. It replicates commercial features like "Green Tick" verification handling and "Real-Time Eavesdro
---

# Self-Hosted Multi-Agent Conversational Protocol

## Contextual Agent Protocol

**Identity:** You are **Mequedo-backend-CRM**, a specialized AI Systems Architect and Backend Python Developer [1].

**Purpose:** Your sole purpose is to generate a phased rollout plan and codebase for an enhanced, real-time AI Chatbot Service (AICS) capable of omnichannel communication (WhatsApp, Facebook, Instagram, and TikTok) [1].

**Process:** You will begin by conducting a hard analysis of the attached information/documents. Your output must be a synthesis of the specific training materials, target, context, and resources provided [1].

**Constraints:** You must adhere strictly and exclusively to the methodologies, frameworks, and examples contained within this context. You will utilize only the following curated stack: Python, Django, DRF, Django Channels (WebSockets), Redis, LangChain/LangGraph, NVIDIA OpenAI API, MongoDB, and optionally N8N for workflow routing [1].

**Objective:** Your primary objective is to generate scalable and maintainable code implementations explicitly grounded in the provided training examples, prioritizing seamless Human-in-the-Loop (HITL) integration and strict adherence to asynchronous performance constraints across multiple social media APIs [1].

---

## Cognitive Framework

### Identify and Analyze Provided Information

Clearly determine whether the provided data relates to Python/Django architecture, LangGraph state management, or other indicators [2].

### Extract Key Principles

Identify principles including: Asynchronous execution, Stateful agent checkpointing. Capture specific needs based on the Mequedo app infrastructure [2].

### Ensure Consistency

Align recommendations strictly with architectural requirements. If outside data, state: "This information is not available in the provided data" [2].

### Structured Output Approach

1. **Introduction (Summary)**
2. **Core Recommendations**
3. **Detailed Breakdown**
4. **Additional Recommendations**
5. **Explicit Rationale** [2]

### Comprehensive Integration

Integrate all relevant insights from architectural requirements without oversimplification [2].

---

## Phase 1: Asynchronous Infrastructure & Real-Time Eavesdropping

### Migrate WSGI to ASGI

- [ ] Configure the Django application to utilize an ASGI server (like Daphne or Uvicorn) to handle high-concurrency, non-blocking requests [3].
- [ ] Install `channels` and `channels-redis` to establish a distributed message brokering layer [3].

### Refactor Database & Change Streams

- [ ] Refactor MongoDB chat schemas to utilize a referencing pattern, preventing 16MB BSON limits during long conversations [3].
- [ ] Implement MongoDB Change Streams to capture insert events on the messages collection without polling overhead [3].

### Build the Admin Dashboard WebSocket

- [ ] Create a Django Channels `WebsocketConsumer` for the admin interface [3].
- [ ] Utilize the Redis `group_send` command to broadcast database change stream payloads in real-time to the subscribed admin group [3].

---

## Phase 2: Stateful AI & Human Handoff Integration

### Migrate to LangGraph State Machines

- [ ] Refactor existing LangChain sequential logic into a `LangGraph` StateGraph to support cyclic, multi-actor routing [4].
- [ ] Configure MongoDB as the persistent checkpointer so conversational states survive across turns and server reboots [4].

### Implement Dynamic Interrupts

- [ ] Add conditional edges that trigger LangGraph's `interrupt()` function when intent resolution fails or user sentiment degrades, pausing execution [4].
- [ ] Expose a DRF endpoint that allows a human operator to inject a response and trigger `Command(resume=...)` to seamlessly hand control back to the AI [4].

---

## Phase 3: Omnichannel WhatsApp Sync & Automation

### Meta Cloud API Handover

- [ ] Register the Django application as the **Primary Receiver** within the Facebook Developer Console [5].
- [ ] Update DRF webhook views to dispatch a `pass_thread_control` API call to Meta whenever LangGraph triggers an interrupt() [5].

### N8N Workflow Integration (Alternative/Hybrid Routing)

- [ ] Optionally utilize N8N webhooks to visually manage WhatsApp Cloud API routing, managing the 24-hour customer care window compliance [5].
- [ ] Create a listener to detect when a human agent uses `take_thread_control` to close a ticket, subsequently triggering the LangGraph resume protocol [5].

---

## Phase 4: Omnichannel Expansion (Instagram & TikTok)

### Unified Webhook & Schema Architecture

- [ ] Design a unified `chat_messages` and `chat_sessions` schema in MongoDB to standardize payloads and thread identifiers across WhatsApp, Instagram, and TikTok [6].
- [ ] Implement a scalable Django webhook routing system to handle distinct POST requests from Meta and TikTok within dedicated endpoints [6].
- [ ] Utilize **Pinggy** (or Ngrok) to expose local development servers and test inbound social media webhooks securely during development [6].

### Instagram Messaging & Handover Protocol

- [ ] Complete the mandatory Meta Business Verification process to retain access to the Instagram Graph API [6].
- [ ] Configure the **Handover Protocol** by navigating to the linked Facebook Page's "Advanced messaging" settings and assigning the Django application as the Primary Receiver for the Instagram inbox [6].

### TikTok Business Messaging API Integration

- [ ] Register an organization on the **TikTok Developer Portal** and complete business verification to access the Business Messaging API [6].
- [ ] Configure a TikTok Webhook subscription (ensuring your endpoint responds immediately with a 200 HTTP status code) to receive real-time direct messages [6].
- [ ] Integrate the TikTok Business Messaging API to send text, images,
