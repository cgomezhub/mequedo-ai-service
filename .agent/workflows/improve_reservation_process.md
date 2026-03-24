---
description: Improve the guest-host reservation process by relocating coupon logic, automating BDV verification, adding manual validation, and enhancing dual-channel notifications.
---

# Improve Guest-Host Reservation Process

> **Contextual Agent Protocol**
>
> - **Identity:** You are a Senior Full-Stack Engineer, specialized in Next.js, Node.js, TypeScript, API integrations, and Test-Driven Development.
> - **Purpose:** Your purpose is to implement an enhanced reservation and payment tracking process. Currently, the automated BDV payment integration lacks API credentials, so you must establish a new Manual Payment Notification flow that coexists alongside the paused BDV flow. You must also implement server actions to bridge WhatsApp notification endpoints explicitly ensuring a seamless fallback.
> - **Process:** You will conduct a hard analysis of the existing reservation and checkout flow. You will implement surgical changes to `BolivarPayment.tsx`, establish the `ManualNotificationModal`, interconnect WhatsApp notifications (`djangoUrl/api/whatsapp/send-payment-review/`, `send-payment-success/`, `send-payment-rejected/`), and finalize with explicit testing coverage mandated by the Quality Assurance phase.
> - **Constraints:** You must keep the disabled BDV flow visually accessible but safely on hold. You must ensure that coupon discounts apply ONLY to the "servicio mequedo" (app commission). You must adhere strictly to Next.js App Router patterns, leveraging Server Actions (`change-order-paid.ts`, `send-payment-notification.ts`).
> - **Objective:** Your primary objective is to generate professional, robust Next.js UI flows and server actions explicitly grounded in the provided context, prioritizing security, intuitive dual-payment options, and strict adherence to testing constraints.
>
> **Cognitive Framework**
>
> 1. **Identify and Analyze Provided Information:** Analyze previously accomplished phases (Coupons, partial BDV integration, PayPal). Then, drill strictly into active Phase 5 and Phase 6 requirements.
> 2. **Extract Key Principles:** Targeted discounting, dual-payment UI coexistence, proactive WhatsApp validations, and strictly enforced Testing Coverage.
> 3. **Ensure Consistency:** Align changes with Prisma schema (`isPaymentInReview`, `isPaid`) and Next.js Form validation (`react-hook-form`, `zod`).
> 4. **Structured Output Approach:**
>    1. Introduction to the active Phase constraints
>    2. Implementation of Manual Validation and UI Refactor
>    3. Integration of WhatsApp Notification actions
>    4. Execution of mandatory QA verification (MANDATORY).

---

## Phase 1: Coupon Logic Relocation (COMPLETED)

1. **Move Input to Checkout**
   - [x] Remove coupon input and logic from `ListingReservation.tsx`.
   - [x] Implement coupon logic in `PlaceOrder.tsx`.
   - [x] Persist coupon code via `useReservationStore`.
2. **Update Discounting Logic**
   - [x] Modify `get-order-summary.ts` to apply `couponDiscount` solely to app commission.
   - [x] Update `place-order.ts` reflecting targeted discounting on DB reservation creation.

## Phase 2: Automated BDV Payment Base Integration (PAUSED/ON HOLD)

1. **Implement BDV UI Base**
   - [x] Establish `BolivarPayment.tsx` and base logic for `processBdvPayment`.
   - [x] Create the original `PaymentNotificationModal` designed for OTP verification.
   - [x] **CONSTRAINT:** Due to missing credentials (`BDV_API_KEY`, `BDV_ENVIRONMENT`, `BDV_PROD_URL`), this flow is fully authored but must remain completely passive/on hold. It operates securely under the "Procesar Pago Seguro BDV" umbrella without executing remote charges until enabled.

## Phase 3: Enhanced Notifications Backbone (COMPLETED)

1. **Dual-Channel Orchestration**
   - [x] Develop `notifyPaymentSuccessInternal.ts` mapping Email (Resend) and preliminary WhatsApp calls.
   - [x] Unify the notification approach.

## Phase 4: PayPal Notifications Consistency (COMPLETED)

1. **Unify Payment Logic**
   - [x] Delete `/api/authorPaymentNotification` and unify via `notify-paypal-success.ts`.

---

## Phase 5: Manual Payment Integration & Dual Flow UI (ACTIVE)

1. **Modify `BolivarPayment.tsx` Configuration & Dual UI**
   - [ ] Replace static bank defaults with strict lookups for `NEXT_PUBLIC_BANK_NAME`, `NEXT_PUBLIC_BANK_ACCOUNT_NUMBER`, `NEXT_PUBLIC_BANK_RIF`, `NEXT_PUBLIC_COMPANY_NAME`, and `NEXT_PUBLIC_COMPANY_EMAIL`.
   - [ ] Implement a highly visible "Reportar Pago Manual" button as the primary fallback action.
   - [ ] Ensure the existing "Procesar Pago Seguro BDV" button remains visually present but clearly secondary so both options coexist for a future switch.

2. **Establish `ManualNotificationModal.tsx`**
   - [ ] Construct the custom modal implementing Cloudinary Image Upload (Receipt File).
   - [ ] Capture user input using Zod constraints: Sender Name, Transaction ID.
   - [ ] Bind submission explicitly to the `sendPaymentNotification()` server action.

## Phase 6: WhatsApp Notifications API Interconnectivity (ACTIVE)

1. **Update `send-payment-notification.ts` (Under Review Trigger)**
   - [ ] Upon resolving Cloudinary file upload and persisting `isPaymentInReview: true` to Prisma, instantiate a secondary notification payload.
   - [ ] Dispatch a POST fetch to `${process.env.DJANGO_AI_SERVICE_URL}/api/whatsapp/send-payment-review/` to alert proper parties the payment has been initialized but awaits manual review.

2. **Update `change-order-paid.ts` (Status Dispatcher Trigger)**
   - [ ] Inside the admin panel operation, conditionally assess the updated boolean status.
   - [ ] If `isPaid === true`, dispatch a POST fetch to `${process.env.DJANGO_AI_SERVICE_URL}/api/whatsapp/send-payment-success/` containing dynamic reservation strings.
   - [ ] If `isPaid === false`, dispatch a POST fetch to `${process.env.DJANGO_AI_SERVICE_URL}/api/whatsapp/send-payment-rejected/` to flag the failure back to the host/user.

---

## Phase 7: Testing & Quality Assurance (MANDATORY)

1. **Test Environment Preparation**
   - [ ] Identify external dependencies globally (Prisma DB operations, Cloudinary upload_stream interfaces, external Django Service API Fetch calls).
   - [ ] Initialize robust mocks inside `jest.mock()` blocks.
   - [ ] Co-locate generated unit tests within standard testing directories (e.g., `__tests__` or adjacent `.test.ts`).

2. **Automated Test Creation**
   - [ ] **`send-payment-notification.test.ts` (Unit Test):**
     - [ ] _Success Path:_ Mock Cloudinary response explicitly, ensure the Prisma DB update executes, and verify the `/send-payment-review/` fetch function triggered correctly with appropriate args.
     - [ ] _Validation Error:_ Guarantee incorrect file buffers reject via Zod mapping safely without throwing uncaught promises.
   - [ ] **`change-order-paid.test.ts` (Unit Test):**
     - [ ] _Authorization Filter:_ Prove that accessing the action without matching the role `"admin"` gracefully halts operation with an unauthorized flag.
     - [ ] _Boolean Toggling Routing:_ Send mock arguments routing the backend to trigger the `/success/` vs `/rejected/` Django endpoints purely dependent on the boolean condition.

3. **Verification & Validation**
   - [ ] Execute `npm test -- [path]` evaluating the fresh suite cleanly against existing Next.js architecture logic.
   - [ ] Run `npm run type-check` to analyze all TS payload mappings for the Modals and Actions.
