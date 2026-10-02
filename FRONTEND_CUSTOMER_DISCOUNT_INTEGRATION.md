# Frontend Customer and Discount Integration Specification

This document describes the frontend contract exposed by the DOPSY proxy
backend for customer registration, discounts, bookings, contacts, and history.

The frontend must call the proxy backend only. It must not call the bot service
directly and must never send or store the bot service API key.

## 1. Base URL and authentication

All paths below are relative to the proxy backend base URL and begin with
`/api`.

Authenticated requests use the existing user JWT:

```http
Authorization: Bearer <user-jwt>
```

The proxy determines the current actor from this JWT. Fields such as `source`,
`created_by`, `approved_by`, and `approved_at` must not be collected from the
user or supplied by the frontend. The proxy injects the authenticated user's
email as the trusted actor identity.

Bot responses generally use this success envelope:

```json
{
  "ok": true,
  "data": {}
}
```

Errors generally use:

```json
{
  "ok": false,
  "code": "ERROR_CODE",
  "message": "Human-readable message"
}
```

The frontend must use the machine-readable `code` when one is present. It
must not infer the error solely from the HTTP status because multiple discount
errors may use HTTP `409`.

## 2. Roles and UI permissions

The API remains the final authorization authority. The UI should also hide or
disable actions that the current user cannot perform.

| Operation | Manager / arena manager | Admin | Super admin |
|---|---:|---:|---:|
| View customers | Yes | Yes | Yes |
| Create customers | Yes | Yes | Yes |
| Edit customer name or phone | Yes | Yes | Yes |
| Change regular-customer status | No | Yes | Yes |
| Delete customers | No | No | Yes |
| View discounts | Yes | Yes | Yes |
| Assign an available discount to a booking | Yes | Yes | Yes |
| Create a discount request | No | Yes | Yes |
| Create an already-approved discount | No | No | Yes |
| Approve or reject discounts | No | No | Yes |
| Edit, activate, deactivate, or delete discounts | No | No | Yes |

Role-related failures return HTTP `403`.

## 3. Shared data types

### 3.1 Customer

```ts
interface Customer {
  id: number;
  name: string | null;
  phone: string;                 // digits only
  is_registered: boolean;
  is_regular_customer: boolean;
  created_at: string;            // ISO 8601
  updated_at: string;            // ISO 8601
}
```

Phone numbers returned by customer and booking APIs are normalized by removing
all non-digit characters:

```text
+7 (707) 111-22-33 -> 77071112233
```

The proxy converts common Kazakhstan forms to one international representation:

```text
8 (707) 111-22-33 -> 77071112233
707 111-22-33     -> 77071112233
```

`is_registered` is response-only state. The frontend must never include it in
customer create or update requests. In the unified contacts response it means
that the normalized phone has a corresponding PostgreSQL customer record; a
conversation or booking alone does not make the contact registered.

`is_regular_customer` is meaningful only for registered customers. When
`is_registered=false`, the UI must treat `is_regular_customer` as `false` and
must not show its editing control.

### 3.2 Discount

```ts
type DiscountStatus = "pending" | "approved" | "rejected";

interface Discount {
  id: number;
  customer_id: number;
  customer_name: string | null;
  customer_phone: string;
  discount_amount: number;
  condition: string | null;
  status: DiscountStatus;
  usage_limit: number;
  usages_left: number;
  usages_count: number;
  is_active: boolean;
  created_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}
```

`discount_amount` is a fixed nominal amount in tenge, not a percentage.

```text
usages_count = usage_limit - usages_left
```

A discount is assignable only when all of these are true:

```text
status = approved
is_active = true
usages_left > 0
discount customer phone = booking phone
```

The bot backend performs the authoritative validation and decrements usage
atomically.

### 3.3 Booking discount fields

Booking detail and listing responses may contain:

```ts
interface BookingDiscountFields {
  customer_id: number;
  discount_id: number | null;
  discount_amount: number;
  price_before_discount: number | null;
  price_total: number;
}
```

Calculation:

```text
price_total = max(price_before_discount - discount_amount, 0)
```

`discount_amount` is the saved nominal snapshot. For example, applying a
20,000 ₸ discount to a 13,500 ₸ booking produces:

```json
{
  "discount_amount": 20000,
  "price_before_discount": 13500,
  "price_total": 0
}
```

## 4. Customer API

### 4.1 Find a customer by phone

Use this when the user finishes entering the phone in the booking form.

```http
GET /api/manager/customers?phone=%2B7%20707%20111%2022%2033
Authorization: Bearer <jwt>
```

Match:

```json
{
  "ok": true,
  "data": {
    "id": 1,
    "name": "Алия",
    "phone": "77071112233",
    "is_registered": true,
    "is_regular_customer": true,
    "created_at": "2026-09-19T10:00:00+00:00",
    "updated_at": "2026-09-19T10:00:00+00:00"
  }
}
```

No match is a successful response, not a 404:

```json
{
  "ok": true,
  "data": null
}
```

### 4.2 List or search customers

```http
GET /api/manager/customers
GET /api/manager/customers?search=Алия
GET /api/manager/customers?search=7707
```

```json
{
  "ok": true,
  "data": [
    {
      "id": 1,
      "name": "Алия",
      "phone": "77071112233",
      "is_regular_customer": true,
      "created_at": "2026-09-19T10:00:00+00:00",
      "updated_at": "2026-09-19T10:00:00+00:00"
    }
  ]
}
```

### 4.3 Get one customer

```http
GET /api/manager/customers/{customer_id}
```

Not found uses HTTP `404`:

```json
{
  "ok": false,
  "code": "NOT_FOUND",
  "message": "Клиент не найден."
}
```

### 4.4 Create or register a customer

```http
POST /api/manager/customers
Content-Type: application/json
```

```json
{
  "name": "Алия",
  "phone": "+7 (707) 111-22-33",
  "is_regular_customer": false
}
```

Only `phone` is required. Do not send `source`; the proxy supplies it. Success
uses HTTP `201` and returns the created customer in `data`. When an automatic
customer with this phone already exists, this operation promotes that same row
to `is_registered=true`; it does not create a duplicate.

Managers may register customers, but only admins and super admins may submit
`is_regular_customer=true`. A manager attempting to do so receives HTTP `403`.

A duplicate normalized phone uses HTTP `409`:

```json
{
  "ok": false,
  "code": "CONFLICT",
  "message": "Запись конфликтует с существующими данными.",
  "constraint": "customers_phone_key"
}
```

Recommended UI behavior: use the existing customer returned by a subsequent
phone lookup rather than offering to create another record.

### 4.5 Update a customer

```http
PATCH /api/manager/customers/{customer_id}
Content-Type: application/json
```

All fields are optional:

```json
{
  "name": "Новое имя",
  "phone": "+7 707 999 88 77",
  "is_regular_customer": true
}
```

Managers may change `name` and `phone`. Only admins and super admins may include
`is_regular_customer`; otherwise the proxy returns HTTP `403`.

### 4.6 Delete a customer

Super admin only:

```http
DELETE /api/manager/customers/{customer_id}
```

Customers referenced by bookings or discounts cannot be deleted. This returns
HTTP `409`:

```json
{
  "ok": false,
  "code": "CUSTOMER_IN_USE",
  "message": "Нельзя удалить клиента с бронями или скидками."
}
```

## 5. Unified contacts API

The existing frontend endpoint is:

```http
GET /api/bot-status/contacts?bot_type=arena
```

Optional pagination:

```http
GET /api/bot-status/contacts?bot_type=arena&page=1&page_size=20
```

An arena contact row includes:

```ts
interface ArenaContact {
  phone: string;
  name: string | null;
  texted: boolean;
  has_booking: boolean;
  is_registered: boolean;
  is_regular_customer: boolean;
  last_activity: string | null;
  paused: boolean;
  paused_reason: string | null;
}
```

Example:

```json
{
  "phone": "77071112233",
  "name": "Алия",
  "texted": true,
  "has_booking": true,
  "is_registered": true,
  "is_regular_customer": true,
  "last_activity": "2026-09-19T15:00:00+05:00",
  "paused": false,
  "paused_reason": null
}
```

Rules:

- Treat `phone` as the row identity. Do not deduplicate by name or raw phone
  formatting.
- Render the two flags exactly as returned. The proxy passes them through and
  the frontend must not derive registration from `texted` or `has_booking`.
- Hide the regular-customer switch when `is_registered` is false.
- When `is_registered=true`, display the returned `is_regular_customer` value.
- A SQLite-only contact has `is_registered=false` and
  `is_regular_customer=false`, regardless of conversation or booking activity.
- A booking without a matching customer record remains unregistered.
- A PostgreSQL customer without a SQLite contact is still returned with
  `is_registered=true`, its stored `is_regular_customer`, and `texted=false`.
- When both sources contain differently formatted versions of the same phone,
  the response contains one row with a normalized digits-only phone.

Source behavior summarized:

| Bot/SQLite contact | PostgreSQL customer | UI registration | UI regular-customer value |
|---|---|---|---|
| Yes | No | Unregistered | `false`; hide switch |
| No | Yes | Registered | Returned value; show switch |
| Yes | Yes | Registered | Returned value; show switch |

The source-presence markers used by the bot to perform this merge are private
and are not part of the frontend contract.

Without pagination parameters, this legacy endpoint may return a bare array.
With pagination it returns:

```json
{
  "ok": true,
  "data": [],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0
}
```

The frontend data loader should support both shapes.

## 6. Discount API

### 6.1 List and filter discounts

```http
GET /api/manager/discounts
GET /api/manager/discounts?customer_id=1
GET /api/manager/discounts?phone=77071112233
GET /api/manager/discounts?status=pending
GET /api/manager/discounts?available_only=true
GET /api/manager/discounts?phone=77071112233&available_only=true
```

Valid status filters are `pending`, `approved`, and `rejected`. The proxy also
accepts `canceled` and converts it to canonical `rejected`.

Example:

```json
{
  "ok": true,
  "data": [
    {
      "id": 10,
      "customer_id": 1,
      "customer_name": "Алия",
      "customer_phone": "77071112233",
      "discount_amount": 10000,
      "condition": "Для постоянного клиента",
      "status": "approved",
      "usage_limit": 5,
      "usages_left": 3,
      "usages_count": 2,
      "is_active": true,
      "created_by": "admin@example.com",
      "approved_by": "superadmin@example.com",
      "approved_at": "2026-09-19T11:00:00+00:00",
      "created_at": "2026-09-19T10:00:00+00:00",
      "updated_at": "2026-09-19T11:00:00+00:00"
    }
  ]
}
```

For booking forms always fetch choices with:

```http
GET /api/manager/discounts?phone={customer.phone}&available_only=true
```

### 6.2 Get one discount

```http
GET /api/manager/discounts/{discount_id}
```

### 6.3 Create a discount request

Admin and super admin:

```http
POST /api/manager/discounts
Content-Type: application/json
```

```json
{
  "customer_id": 1,
  "discount_amount": 10000,
  "condition": "Для постоянного клиента",
  "status": "pending",
  "usage_limit": 5
}
```

Required fields:

- `customer_id`
- `discount_amount`, greater than zero

Defaults:

- `status = pending`
- `usage_limit = 5`

For an ordinary admin the proxy always forwards `pending`, even if the client
sends `approved`. A super admin may create a discount directly as `approved`.
Do not send actor or approval metadata.

### 6.4 Approve a discount

Super admin only:

```http
PATCH /api/manager/discounts/{discount_id}
Content-Type: application/json
```

```json
{
  "status": "approved"
}
```

Approval sets the approval actor and timestamp on the server and activates the
discount when it has remaining uses.

### 6.5 Reject a discount

Super admin only:

```json
{
  "status": "rejected"
}
```

Rejection deactivates the discount. The request alias `canceled` is accepted,
but frontend state and labels should use the canonical value `rejected`.

### 6.6 Edit or deactivate a discount

Super admin only. Supported fields are all optional:

```json
{
  "discount_amount": 15000,
  "condition": "Updated condition",
  "status": "approved",
  "is_active": true,
  "usage_limit": 10
}
```

Validation rules:

- `discount_amount` must be greater than zero.
- `usage_limit` must be greater than zero.
- `usage_limit` cannot be lower than `usages_count`.
- Increasing the limit preserves the number already used and increases
  `usages_left`.
- Only approved discounts may be active.
- An exhausted discount cannot be reactivated unless its limit is increased.
- Editing an amount does not change historical booking snapshots.

### 6.7 Delete a discount

Super admin only:

```http
DELETE /api/manager/discounts/{discount_id}
```

Only a never-used discount can be deleted. Otherwise HTTP `409` is returned:

```json
{
  "ok": false,
  "code": "DISCOUNT_IN_USE",
  "message": "Скидка не найдена или уже использовалась."
}
```

## 7. Single manager booking creation

Use the proxy manager route:

```http
POST /api/manager/bookings
Content-Type: application/json
Authorization: Bearer <jwt>
```

```json
{
  "field": 1,
  "date": "2026-10-01",
  "time_start": "10:00",
  "time_end": "11:00",
  "customer": "Алия",
  "customer_id": 1,
  "phone": "+7 707 111 22 33",
  "price_total": 13500,
  "discount_id": 10,
  "prepayment": 3500,
  "notes": "Optional note"
}
```

Required scheduling fields are `field`, `date`, `time_start`, `time_end`, and
`price_total`. Send both `customer_id` and `phone` whenever they are known. At
least one ownership field must reach the bot. If only `customer_id` is sent,
the bot fills the phone; if only `phone` is sent, it resolves or creates the
customer. The incoming `price_total` is the gross price before discount.

Example result:

```json
{
  "ok": true,
  "data": {
    "customer_id": 1,
    "phone": "77071112233",
    "discount_id": 10,
    "discount_amount": 10000,
    "price_before_discount": 13500,
    "price_total": 3500,
    "paid_avans": 3500
  }
}
```

Applying the discount and decrementing its remaining uses occur in the same
database transaction as booking creation.

## 8. Batch and recurring bookings

Use the existing route:

```http
POST /api/bookings/batch
```

### 8.1 One default discount for all slots

```json
{
  "customer": "Алия",
  "customer_id": 1,
  "phone": "77071112233",
  "discount_id": 10,
  "prepayment": 3500,
  "slots": [
    {
      "field": 1,
      "date": "2026-10-01",
      "time_start": "10:00",
      "time_end": "11:00"
    },
    {
      "field": 1,
      "date": "2026-10-03",
      "time_start": "12:00",
      "time_end": "13:00"
    }
  ]
}
```

### 8.2 Per-slot discounts

```json
{
  "customer": "Алия",
  "phone": "77071112233",
  "discount_id": 10,
  "slots": [
    {
      "field": 1,
      "date": "2026-10-01",
      "time_start": "10:00",
      "time_end": "11:00",
      "discount_id": 11
    },
    {
      "field": 2,
      "date": "2026-10-03",
      "time_start": "12:00",
      "time_end": "13:00"
    },
    {
      "field": 3,
      "date": "2026-10-05",
      "time_start": "16:00",
      "time_end": "17:00",
      "discount_id": null
    }
  ]
}
```

Precedence is:

```text
explicit slot.discount_id, including null
otherwise top-level discount_id
otherwise no discount
```

It is important to send `"discount_id": null` when a slot must explicitly opt
out of the top-level discount. Omitting the property causes that slot to inherit
the top-level discount.

Only authenticated staff may submit a batch containing a non-null discount.
Unauthenticated or client-role requests with discounts return HTTP `403`.

The whole batch is atomic. If any discount cannot cover every assigned
occurrence, no booking or usage decrement is committed. Each generated
recurring occurrence consumes one use. A logical cross-midnight booking stored
as two backend rows consumes only one use.

### 8.3 Local batch availability counter

After fetching available discounts, track assignments in the current form:

```text
locally available = usages_left returned by API - assignments in this form
```

Disable further selection when the local value reaches zero. This is only a UX
guard; the backend remains authoritative because another user may consume a use
concurrently.

## 9. Booking editing

Use the existing booking update endpoint:

```http
PATCH /api/bookings/{booking_id}
Content-Type: application/json
```

### 9.1 Apply or replace a discount

```json
{
  "discount_id": 10
}
```

The backend atomically returns a use to the old discount, validates and consumes
the new discount, recalculates the price, and records history. If validation of
the replacement fails, the old assignment remains unchanged.

### 9.2 Remove a discount

```json
{
  "discount_id": null
}
```

The frontend must include the property with an explicit JSON `null`. Do not
omit it. Removal returns one use, clears the discount snapshot, and restores the
gross price.

### 9.3 Change the booking phone

```json
{
  "phone": "+7 707 111 22 33"
}
```

If the booking has a discount, the normalized new phone must still match the
discount owner.

When changing booking ownership, send both values together:

```json
{
  "customer_id": 2,
  "phone": "77079998877"
}
```

### 9.4 Reschedule a discounted booking

Date, time, duration, or field changes cause the backend to recalculate gross
price and reapply the stored discount snapshot. Rescheduling does not consume
another use.

Use `discount_id` returned by booking detail as the edit form's selected value.
Display `discount_amount` in booking tables where discount information is
required.

## 10. Prepayment behavior

The frontend should suggest:

```text
suggested prepayment = min(final price_total, 10000)
```

Examples:

| Gross | Discount | Final | Suggested prepayment |
|---:|---:|---:|---:|
| 13,500 | 10,000 | 3,500 | 3,500 |
| 31,000 | 10,000 | 21,000 | 10,000 |
| 13,500 | 20,000 | 0 | 0 |

Recalculate the suggestion whenever the price, schedule, field, or selected
discount changes. The field may remain editable. The backend stores submitted
`prepayment` as `paid_avans`. Existing ApiPay configuration may override the
manual value for chargeable slots.

## 11. Customer and discount errors during booking

Handle these codes explicitly:

| Code | Meaning | Recommended UI message/action |
|---|---|---|
| `DISCOUNT_NOT_FOUND` | The discount no longer exists | Clear selection and refresh discounts |
| `DISCOUNT_CUSTOMER_MISMATCH` | Discount belongs to another phone/customer | Clear selection and verify booking phone |
| `DISCOUNT_UNAVAILABLE` | Pending, rejected, inactive, or exhausted | Clear selection and refresh discounts |
| `INVALID_DISCOUNT` | Invalid discount identifier | Treat as form/integration error |
| `CUSTOMER_REQUIRED` | Neither customer ID nor phone was supplied | Return to customer step |
| `INVALID_CUSTOMER` | Customer ID is malformed | Treat as form/integration error |
| `CUSTOMER_NOT_FOUND` | Explicit customer no longer exists | Refresh customer selection |
| `CUSTOMER_PHONE_MISMATCH` | ID and phone identify different customers | Refresh customer data |

Example error:

```json
{
  "ok": false,
  "code": "DISCOUNT_UNAVAILABLE",
  "message": "Скидка недоступна или закончилась."
}
```

These may be returned with HTTP `409`. Show the backend `message` as the user
message when appropriate, but branch behavior using `code`.

## 12. History

Existing endpoint:

```http
GET /api/manager/history
```

History entries may now include customer and discount associations:

```ts
interface HistoryEntry {
  booking_id: number | null;
  customer_id: number | null;
  discount_id: number | null;
  source: string;
  description: string;
  created_at: string;
}
```

Example:

```json
{
  "booking_id": null,
  "customer_id": 1,
  "discount_id": 10,
  "source": "admin@example.com",
  "description": "Создана скидка 10000 тг со статусом pending.",
  "created_at": "2026-09-19T10:00:00+00:00"
}
```

The proxy normalizes empty identifier strings returned by the bot into JSON
`null` for `booking_id`, `customer_id`, and `discount_id`.

## 13. Recommended booking-form workflow

### Step 1: identify or register the customer

1. Collect a phone number in consistent Kazakhstan country-code format.
2. Call `GET /api/manager/customers?phone={encodedPhone}`.
3. If `data` contains a customer, populate the customer name and retain its ID
   and normalized phone.
4. If `data` is `null`, show a registration action. Do not use a booking-only
   row from the contacts endpoint as proof that the customer is registered.
5. Register the customer with `POST /api/manager/customers`.
6. Store the returned customer ID and normalized phone.

### Step 2: load discount choices

Call:

```http
GET /api/manager/discounts?phone={normalizedPhone}&available_only=true
```

For every option display:

- formatted `discount_amount` in tenge;
- `usages_left`;
- `condition` when present.

Include a clear "No discount" option whose value is `null`.

### Step 3: calculate preview values

```ts
const finalPrice = Math.max(grossPrice - selectedDiscountAmount, 0);
const suggestedPrepayment = Math.min(finalPrice, 10_000);
```

Use the preview only for UI feedback. Send the gross `price_total` during
single booking creation and let the backend apply the authoritative discount.

### Step 4: submit and reconcile

1. Submit `customer_id`, normalized `phone`, the selected `discount_id`, and
   calculated/editable `prepayment`.
2. On success, use returned booking values rather than retaining local preview
   values.
3. On a discount error, refresh the available discount list and preserve the
   rest of the booking form.

## 14. Suggested frontend validation

- Customer phone: required and must contain at least one digit.
- Discount amount: numeric and greater than zero.
- Usage limit: integer and greater than zero.
- Gross booking price: numeric and zero or greater.
- Prepayment: numeric and zero or greater.
- Do not allow prepayment to become negative when a discount exceeds gross
  price.
- Never derive availability only from cached `usages_left`; refresh when opening
  a booking form and after successful booking creation/editing.
- Never expose controls based solely on UI role checks; retain normal handling
  for backend HTTP `401` and `403` responses.

## 15. Endpoint summary

| Method | Public proxy path | Purpose |
|---|---|---|
| GET | `/api/manager/customers` | Find, list, or search customers |
| POST | `/api/manager/customers` | Create customer |
| GET | `/api/manager/customers/{id}` | Get customer |
| PATCH | `/api/manager/customers/{id}` | Update customer |
| DELETE | `/api/manager/customers/{id}` | Delete customer |
| GET | `/api/manager/discounts` | List/filter discounts |
| POST | `/api/manager/discounts` | Create discount request |
| GET | `/api/manager/discounts/{id}` | Get discount |
| PATCH | `/api/manager/discounts/{id}` | Approve, reject, or edit discount |
| DELETE | `/api/manager/discounts/{id}` | Delete unused discount |
| POST | `/api/manager/bookings` | Create one manager booking |
| POST | `/api/bookings/batch` | Create batch/recurring bookings |
| PATCH | `/api/bookings/{id}` | Edit booking or replace/remove discount |
| GET | `/api/bookings` | List bookings with discount fields |
| GET | `/api/bookings/{id}` | Get booking with discount fields |
| GET | `/api/bookings/range/{start}/{end}` | List range with discount fields |
| GET | `/api/bot-status/contacts` | Unified customer/contact list |
| GET | `/api/manager/history` | Audit history |
