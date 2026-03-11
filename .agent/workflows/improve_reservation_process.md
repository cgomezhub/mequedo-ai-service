---
description: Improve the guest-host reservation process by moving coupon logic, automating BDV payment verification, and enhancing notifications.
---

# Improve Guest-Host Reservation Process (BDV Integration)

> **Contextual Agent Protocol**
>
> - **Identity:** You are a Senior Full-Stack Engineer, specialized in Next.js, TypeScript, and Banco de Venezuela (BDV) API integrations.
> - **Purpose:** Your sole purpose is to improve the reservation process by relocating the coupon discount input, implementing automated BDV payment verification (B2P flow), and enhancing the notification system.
> - **Process:** You will conduct a hard analysis of the existing reservation and checkout flow, then implement surgical changes to move components, update server actions for targeted discounting, and integrate the BDV payment gateway.
> - **Constraints:** You must ensure that coupon discounts apply ONLY to the "servicio mequedo" (app commission). Payment verification must use the BDV B2P flow (ID, Phone, OTP). Notifications must reach both host and guest via WhatsApp and Email.
> - **Objective:** Your primary objective is to generate a professional, robust, and seamless reservation experience explicitly grounded in the provided project context and BDV technical guidelines.
>
> **Cognitive Framework**
>
> 1. **Identify and Analyze Provided Information:** Analyze `ListingReservation.tsx`, `PlaceOrder.tsx`, `get-order-summary.ts`, `notifyHostInternal.ts`, and `payment_search.md`.
> 2. **Extract Key Principles:** Targeted discounting (commission-only), automated BDV B2P verification (ID/Phone/OTP), and proactive dual-channel notifications.
> 3. **Ensure Consistency:** Align changes with existing Prisma models (`Reservation`, `Coupon`, `User`) and Next.js App Router patterns.
> 4. **Structured Output Approach:**
>    1. Introduction (Summary of changes)
>    2. Coupon Relocation & Targeted Discounting
>    3. Automated BDV Payment Integration (B2P)
>    4. Enhanced Notification System
>    5. Explicit Rationale (Security & UX)

---

## Phase 1: Coupon Logic Relocation

1. **Move Input to Checkout**
   - [x] Remove coupon input and logic from `app/components/listings/ListingReservation.tsx`.
   - [x] Implement coupon input and "Apply" logic in `app/(lodgement)/checkout/[listingId]/ui/PlaceOrder.tsx`.
   - [x] Ensure the coupon code is persisted in the `useReservationStore`.

2. **Update Discounting Logic**
   - [x] Modify `app/actions/order/get-order-summary.ts` to apply `couponDiscount` only to `appCommission`.
   - [x] Update `app/actions/order/place-order.ts` to reflect the same targeted discounting when creating the reservation record.

## Phase 2: Automated BDV Payment Integration

1. **Implement BDV Client & Action**
   - [x] Create `app/libs/payments/bdvClient.ts` to handle REST calls to BDV (`/api/Payments/{paidId}/process`).
   - [x] Implement `app/actions/payments/process-bdv-payment.ts` to handle the B2P flow (ID, Phone, OTP).

2. **Update Payment UI**
   - [x] Refactor `app/components/payments/BolivarPayment.tsx` to collect Payer ID and Phone Number.
   - [x] Update `PaymentNotificationModal` to include an OTP verification step for automated confirmation.
   - [x] Replace manual receipt upload with the automated BDV flow as the primary method.

## Phase 3: Enhanced Notifications

1. **Dual-Channel Notifications**
   - [x] Modify `app/libs/notifyHostInternal.ts` to trigger notifications on payment success. (Created `notifyPaymentSuccessInternal.ts`)
   - [x] Implement WhatsApp notification for Guest and Host (via Django service).
   - [x] Implement Email notification for Guest and Host (using Resend).

2. **Validation**
   - [x] Verify that both parties receive correct details about the confirmed reservation and payment.

## Phase 4: PayPal Notifications Consistency

1. **Unify Payment Logic**
   - [x] Delete deprecated routes: `/api/authorPaymentNotification` & `/api/userPaymentConfirmation`.
   - [x] Create centralized Action: `notify-paypal-success.ts` defaulting to `US$` and `PayPal`.
   - [x] Update `PaypalButton.tsx` to invoke the unified notification service.
