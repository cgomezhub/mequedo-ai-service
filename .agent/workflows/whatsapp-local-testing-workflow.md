---
description: How to test WhatsApp webhook + outbound sends against a local Django server, without touching production
---

# WhatsApp Local Testing Workflow

> **Contextual Agent Protocol**
>
> - **Identity:** You are a WhatsApp Cloud API integration engineer working on the Mequedo AI service.
> - **Purpose:** Stand up a local, disposable path for Meta to deliver real webhook events to `manage.py runserver` on a developer machine, and to send real outbound template messages, without altering the production webhook (`ai-whatsapp.mequedo.app` / Railway) or the WABA config other environments rely on.
> - **Constraints:** Never disable `X-Hub-Signature-256` verification, never commit tokens, and always revert the per-number webhook override when done testing.
> - **Objective:** Reach a state where a real WhatsApp message sent from a phone produces visible logs in the local `runserver` process, and a local outbound send produces a real delivered message — using ephemeral infrastructure that requires no production redeploy.

---

## Why this exists

Meta's webhook can only point at ONE app-level URL (`ai-whatsapp.mequedo.app`, pointed at Railway). Testing webhook changes locally used to mean either faking payloads with `curl`/`test_whatsapp_webhook.sh` (fine for parsing logic, useless for real Graph API round-trips) or redeploying to Railway on every change. This workflow uses Meta's **per-phone-number webhook override** so a single WhatsApp number (ideally the Meta-provided test number) can be pointed at a local tunnel while production keeps working normally for every other number.

Known-bad approaches, ruled out during the original investigation — don't retry them:
- **ngrok:** blocked outright for agents connecting from Venezuela IPs (`ERR_NGROK_9040`), no documented bypass.
- **Sending the override via `access_token`/`override_callback_uri` as top-level form params:** Graph API returns `{"success": true}` but silently does nothing. Must be a JSON body nested under `webhook_configuration`, sent with `Authorization: Bearer`.

---

## Phase 1: Local environment sanity check

1. **Confirm `load_dotenv()` actually runs**
   - [ ] `mequedo_ai/settings.py` must call `load_dotenv()` before reading any `os.getenv(...)`. If it's missing, `DEBUG`, `LOG_LEVEL`, and every WhatsApp/Mongo/LLM key silently fall back to defaults regardless of `.env` contents — this looks like "the server is ignoring my .env" and is easy to lose an hour to.
2. **Check for a stray process already bound to port 8000**
   - [ ] `lsof -i :8000` — kill anything that isn't the `runserver` you're about to start (a leftover `python -m http.server 8000` will make Django's own webhook return a confusing `501 Unsupported method`).
3. **Verify `ALLOWED_HOSTS`**
   - [ ] Your tunnel's public hostname must be in `ALLOWED_HOSTS` (see `mequedo_ai/settings.py`) or Django 400s every request before it reaches the view. Watch for accidental Python string concatenation if you add a host on the line above/below another literal without a trailing comma — two adjacent string literals silently merge into one invalid host and there's no syntax error to warn you.
4. **Set `LOG_LEVEL=INFO` in `.env`**
   - [ ] Once `load_dotenv()` is actually wired up, `DEBUG=True` defaults `LOG_LEVEL` to `DEBUG`, which floods the console with pymongo/litellm internals and makes it look like the server hung. Set `LOG_LEVEL=INFO` explicitly for testing sessions; only drop to `DEBUG` when you need those internals.

## Phase 2: Expose local Django to the internet

Use the pre-existing named Cloudflare Tunnel, not ngrok.

1. **Confirm the tunnel exists and where it points**
   - [ ] `cloudflared tunnel list`
   - [ ] `cat ~/.cloudflared/config.yml` — ingress should map a fixed hostname (e.g. `whatsapp-test.mequedo.app`) to `http://localhost:8000`.
2. **Start it alongside `runserver`**
   - [ ] `python manage.py runserver 8000`
   - [ ] `cloudflared tunnel run whatsapp-test` (separate terminal)
3. **Add the tunnel hostname to `ALLOWED_HOSTS`** in `mequedo_ai/settings.py` if it isn't already there (see Phase 1, step 3).

## Phase 3: Point ONE WhatsApp number at the local tunnel

Do this against Meta's free test number (`WHATSAPP_PHONE_NUMBER_ID` in `.env`), never the production number, unless explicitly testing production-only behavior.

1. **Register the override** — must be JSON body + Bearer header, not form params:
   ```bash
   curl -X POST "https://graph.facebook.com/v24.0/${WHATSAPP_PHONE_NUMBER_ID}" \
     -H "Authorization: Bearer ${WHATSAPP_ACCESS_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "webhook_configuration": {
         "override_callback_uri": "https://whatsapp-test.mequedo.app/api/whatsapp/webhook/",
         "verify_token": "'"${WHATSAPP_VERIFY_TOKEN}"'"
       }
     }'
   ```
2. **Verify it actually took** (the call above can return `{"success": true}` even when nothing changed if the format was wrong):
   ```bash
   curl -s -G "https://graph.facebook.com/v24.0/${WHATSAPP_PHONE_NUMBER_ID}" \
     --data-urlencode "access_token=${WHATSAPP_ACCESS_TOKEN}" \
     --data-urlencode "fields=webhook_configuration"
   ```
   - [ ] Look for a `"phone_number"` key in the response alongside the existing `"application"` fallback key. If only `"application"` (pointing at Railway) is present, the override did not take — redo step 1.
   - [ ] Re-check this periodically during a long session; the override has been observed to silently revert to the `"application"` default between test attempts.
3. **Add your test recipient number** in Meta's WhatsApp Manager → "Paso 1: Pruébalo" → "Para:" list. Test numbers can **only** exchange messages with numbers explicitly OTP-verified there — a message sent from any other number produces no webhook traffic at all, with no error shown anywhere.

## Phase 4: Send a real test message and confirm receipt

1. **From the verified phone, send a WhatsApp message** to the Meta test number.
2. **Watch logs live** instead of polling manually:
   ```bash
   tail -F <django log file> | grep -i whatsapp
   ```
   or poll the local `cloudflared`/ngrok-equivalent inspector if available.
3. **Confirm in Django logs:** webhook POST received → signature verified → `WhatsAppMessageHandler` spawned on a background thread → 200 OK returned to Meta immediately (per the async webhook pattern in `CLAUDE.md`).

## Phase 5: Outbound sends (System User token required)

Real outbound sends (`send_template_message`) need a **System User** access token, not a personal User token — even with correct OAuth scopes granted, Meta additionally requires the token's identity to hold an explicit role on the WABA in Business Manager.

1. **Check token type before debugging anything else:**
   ```bash
   curl -s -G "https://graph.facebook.com/v24.0/debug_token" \
     --data-urlencode "input_token=${WHATSAPP_ACCESS_TOKEN}" \
     --data-urlencode "access_token=${WHATSAPP_ACCESS_TOKEN}" | python3 -m json.tool
   ```
   - [ ] `"type"` must be `"SYSTEM_USER"`. `"type": "USER"` reliably produces `(#131005) Access denied` on send, even when `debug_token` shows all the right scopes.
   - [ ] Generate one at `https://business.facebook.com/latest/settings/system_users` if missing, assign it a role on the WABA, restart `runserver` to pick up the new `.env` value.
2. **Match template placeholder count exactly.** Query the approved template before wiring up `components`:
   ```bash
   curl -s -G "https://graph.facebook.com/v24.0/${WHATSAPP_BUSINESS_ACCOUNT_ID}/message_templates" \
     --data-urlencode "access_token=${WHATSAPP_ACCESS_TOKEN}" | python3 -m json.tool
   ```
   - [ ] Count the `{{n}}` placeholders in the approved body text and send exactly that many `body` parameters, in that order. Sending an extra/missing parameter produces `(#132000) Number of parameters does not match the expected number of params` — this is a data-shape mismatch, not an auth problem.
   - [ ] If the template your code references isn't in this list at all (`(#132001) Template name does not exist in the translation`), it very likely belongs to a **different WABA** than `WHATSAPP_BUSINESS_ACCOUNT_ID` in `.env` — check the `business_id` in the template's Meta WhatsApp Manager URL against the WABA ID you're querying before assuming the template needs to be recreated.

## Phase 6: Tear down (always do this)

1. **Revert the webhook override** so the test number falls back to the app-level (production) webhook:
   ```bash
   curl -X POST "https://graph.facebook.com/v24.0/${WHATSAPP_PHONE_NUMBER_ID}" \
     -H "Authorization: Bearer ${WHATSAPP_ACCESS_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"webhook_configuration": {"override_callback_uri": ""}}'
   ```
   - [ ] Re-run the Phase 3 step 2 verification GET to confirm only `"application"` remains.
2. **Stop `cloudflared` and `runserver`.**
3. **Never leave a test-number override pointed at a laptop tunnel between sessions** — if the machine goes to sleep or the tunnel drops, that number's webhook traffic silently goes nowhere until you notice.

---

## Phase 7: Testing & Quality Assurance (MANDATORY)

1. **Fake-payload smoke test (fast, no real Meta round-trip)**
   - [ ] `./test_whatsapp_webhook.sh` — exercises webhook GET verification + a synthetic POST payload against local `runserver`. Good for parser/handler logic changes; does **not** validate real template sends or real Graph API auth.
2. **Real end-to-end test (required before shipping WhatsApp-facing changes)**
   - [ ] Run Phases 1–5 above with a real verified phone number.
   - [ ] Confirm the specific code path changed (e.g., a new template, a new button flow) end-to-end: inbound webhook → handler → any outbound reply/template send → delivered message on the phone.
3. **Verification & Validation**
   - [ ] Check Django logs for the async ack pattern (200 OK returned before background processing completes).
   - [ ] Confirm Phase 6 teardown was actually done — check `webhook_configuration` one last time.
