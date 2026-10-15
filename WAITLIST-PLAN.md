# Waitlist Feature Plan

## Overview

Add a waitlist system to Galaxium Travels so that when a flight's seat class is full, passengers can join a queue. When a booking is cancelled, the first passenger on the waitlist for that flight/seat-class is automatically promoted: a confirmed booking is created at the price locked in at join time, and a notification is logged to stdout and stored in the database.

**Scope:** Backend (Python/FastAPI), Frontend (React/TypeScript). No Java hold-service changes needed.

**Non-goals:** Real email sending, cross-seat-class promotion, admin UI for managing waitlists.

---

## Sub-Tasks

---

### Sub-Task 1 — Add `WaitlistEntry` and `Notification` DB models

**Status:** `[x] done`

**Intent**
Introduce two new SQLAlchemy ORM models. `WaitlistEntry` stores one row per waitlist slot; `Notification` stores simulated email records. Both must be created before any service or schema work.

**Expected Outcomes**
- `WaitlistEntry` table exists in SQLite with columns: `waitlist_id`, `user_id`, `flight_id`, `seat_class`, `status` (`waiting`/`promoted`/`expired`), `position`, `locked_price`, `created_at`.
- `Notification` table exists with columns: `notification_id`, `user_id`, `type`, `message`, `created_at`.
- `Base.metadata.create_all()` creates both tables (verified in the test suite).

**Todo List**
1. Open `booking_system_backend/models.py`.
2. Add a `WaitlistStatus` string enum: `waiting`, `promoted`, `expired`.
3. Add `WaitlistEntry` ORM model with the columns listed above. `position` is an integer (1-based) reflecting insertion order within the flight+seat_class group. `locked_price` is an integer (cents).
4. Add `Notification` ORM model with columns: `notification_id` (PK), `user_id` (FK → users), `type` (String), `message` (String), `created_at` (String, ISO timestamp).

**Relevant Context**
- Existing model pattern: `booking_system_backend/models.py` — `Booking` and `Flight` classes show the column style to follow.
- `Base` is imported from `db.py`; all models use `Base.metadata`.

---

### Sub-Task 2 — Add Pydantic schemas for waitlist

**Status:** `[x] done`

**Intent**
Define the request/response shapes for joining a waitlist and for the waitlist entry output. These are used by the REST endpoints and MCP tools.

**Expected Outcomes**
- `WaitlistRequest` schema: `user_id: int`, `name: str`, `flight_id: int`, `seat_class: SeatClass`.
- `WaitlistOut` schema: `waitlist_id`, `user_id`, `flight_id`, `seat_class`, `status`, `position`, `locked_price`, `created_at`.
- `NotificationOut` schema: `notification_id`, `user_id`, `type`, `message`, `created_at`.

**Todo List**
1. Open `booking_system_backend/schemas.py`.
2. Add `WaitlistRequest`, `WaitlistOut`, and `NotificationOut` Pydantic models with `model_config = ConfigDict(from_attributes=True)` so they work with `model_validate()`.

**Relevant Context**
- Pattern to follow: `BookingRequest` / `BookingOut` in `booking_system_backend/schemas.py`.

---

### Sub-Task 3 — Implement waitlist service logic

**Status:** `[x] done`

**Intent**
Add all business logic for joining a waitlist and for auto-promoting the next person in queue when a booking is cancelled. This is the core of the feature.

**Expected Outcomes**
- `join_waitlist(db, user_id, name, flight_id, seat_class)` → `WaitlistOut | ErrorResponse`
  - Returns `ErrorResponse` with `error_code="FLIGHT_NOT_FOUND"` if flight doesn't exist.
  - Returns `ErrorResponse` with `error_code="USER_NOT_FOUND"` or `"NAME_MISMATCH"` if user validation fails (same pattern as `book_flight`).
  - Returns `ErrorResponse` with `error_code="SEATS_AVAILABLE"` if seats are actually available (no need to waitlist).
  - Returns `ErrorResponse` with `error_code="ALREADY_WAITLISTED"` if user already has a `waiting` entry for this flight+seat_class.
  - Calculates `locked_price` using the same multipliers as `book_flight` (`economy=base_price`, `business=base_price*2.5`, `galaxium=base_price*5`).
  - Assigns `position` as `(count of existing waiting entries for this flight+seat_class) + 1`.
  - Creates and returns a `WaitlistEntry` with status `waiting`.
- `get_waitlist(db, user_id)` → `list[WaitlistOut]` — returns all waitlist entries for a user.
- `_promote_from_waitlist(db, flight_id, seat_class)` — internal helper called by `cancel_booking`:
  - Queries for the first `WaitlistEntry` with status `waiting` for the given flight+seat_class, ordered by `position` ascending.
  - If none found, returns without action.
  - Creates a real `Booking` using the locked price (bypass the seat-availability check — the cancelled seat is already restored at this point).
  - Decrements the appropriate seat counter back by 1.
  - Sets the waitlist entry status to `promoted`.
  - Creates a `Notification` record with `type="waitlist_promotion"` and a human-readable message.
  - Logs to stdout: `[WAITLIST] User {user_id} promoted to booking {booking_id} for flight {flight_id} ({seat_class})`.
- Modify `cancel_booking` in `booking_system_backend/services/booking.py` to call `_promote_from_waitlist` after restoring the seat counter and before committing.

**Relevant Context**
- `cancel_booking`: `booking_system_backend/services/booking.py` lines 93–123.
- `book_flight` multiplier logic: same file, lines 16–90. Re-use `SEAT_CLASS_MULTIPLIERS`.
- The `_promote_from_waitlist` helper should live in a new file `booking_system_backend/services/waitlist.py`. Import it into `booking_system_backend/services/booking.py` to avoid a circular import.
- User validation pattern (name match): `book_flight` — replicate for `join_waitlist`.

---

### Sub-Task 4 — Add REST endpoints and MCP tools

**Status:** `[x] done`

**Intent**
Expose the waitlist service via HTTP and make it accessible to agents through the auto-generated MCP tools.

**Expected Outcomes**
- `POST /waitlist` — join waitlist; returns `WaitlistOut` (201) or raises `HTTPException` on error.
- `GET /waitlist/{user_id}` — list a user's waitlist entries; returns `list[WaitlistOut]`.
- `GET /notifications/{user_id}` — list a user's notifications; returns `list[NotificationOut]`.
- All three endpoints appear as MCP tools automatically (FastApiMCP auto-generates from all FastAPI routes).

**Todo List**
1. Open `booking_system_backend/server.py`.
2. Import `WaitlistRequest`, `WaitlistOut`, `NotificationOut` from `schemas`.
3. Import the waitlist service module.
4. Add `POST /waitlist` endpoint following the `POST /book` error-handling pattern.
5. Add `GET /waitlist/{user_id}` endpoint.
6. Add `GET /notifications/{user_id}` endpoint — queries `Notification` records filtered by `user_id`.

**Relevant Context**
- Endpoint pattern: `POST /book` at `booking_system_backend/server.py:152–166`.
- MCP auto-generation: `FastApiMCP(app)` at `booking_system_backend/server.py:333–337` — no extra MCP registration needed.
- Error code → HTTP status mapping to follow: 404 for `FLIGHT_NOT_FOUND`/`USER_NOT_FOUND`, 409 for `SEATS_AVAILABLE`/`ALREADY_WAITLISTED`/`NAME_MISMATCH`.

---

### Sub-Task 5 — Backend tests

**Status:** `[x] done`

**Intent**
Ensure the waitlist service and endpoints are covered by unit tests, and that the modified `cancel_booking` path is regression-tested.

**Expected Outcomes**
- Service tests in `booking_system_backend/tests/test_services.py` cover:
  - Successful `join_waitlist`.
  - `join_waitlist` when seats are still available (error).
  - `join_waitlist` for unknown flight (error).
  - `join_waitlist` duplicate (error).
  - `cancel_booking` with an active waitlist entry → promotion happens, booking is created, seat count unchanged after cancel+promote.
  - `cancel_booking` with no waitlist entry → seat restored normally (regression).
- REST tests in `booking_system_backend/tests/test_rest.py` cover:
  - `POST /waitlist` happy path (201).
  - `POST /waitlist` when seats are available (409).
  - `GET /waitlist/{user_id}` returns entries.
  - `GET /notifications/{user_id}` returns notifications after promotion.

**Todo List**
1. Add a `TestWaitlistService` class to `test_services.py`.
2. Add a `TestWaitlistEndpoint` class to `test_rest.py`.
3. Extend `TestBookingService` with a cancellation+promotion test.
4. Use the existing `db_session` and `client` fixtures from `conftest.py`; no new fixtures needed.
5. Run `pytest booking_system_backend/tests/` and confirm all tests pass.

**Relevant Context**
- Test fixtures: `booking_system_backend/tests/conftest.py` — `db_session`, `client`, `sample_user_data`, `sample_flight_data`.
- Existing cancellation test pattern: `TestBookingService` in `test_services.py`.
- Footgun: `conftest.py` patches `SessionLocal` in two places (lines 49–50); waitlist tests that go through the REST client are already covered by the existing `client` fixture.

---

### Sub-Task 6 — Frontend: join waitlist flow

**Status:** `[x] done`

**Intent**
When a seat class is sold out, the passenger can join the waitlist straight from the flight card, and from the booking modal. On confirmation, call the backend and show the user their queue position.

**Expected Outcomes**
- `WaitlistEntry` and `WaitlistRequest` TypeScript types added to `booking_system_frontend/src/types/index.ts`.
- `joinWaitlist(data: WaitlistRequest)` API function added to `booking_system_frontend/src/services/api.ts`.
- `FlightCard` shows a "Join Waitlist" button on every seat class that is sold out (`seats === 0`). Clicking it opens `BookingModal` with that class already selected.
- If all classes on a flight are sold out, the card's main button stays enabled and reads "All Classes Sold Out: Join Waitlist".
- In `BookingModal`, sold-out classes stay selectable (shown as sold out, not disabled), so the passenger can pick one.
- `BookingModal` detects when `seats === 0` for the selected class and renders a "Join Waitlist" button instead of "Confirm Booking".
- On success, a confirmation message shows queue position (e.g. "You're #3 on the waitlist").
- On error (e.g. already waitlisted), an inline error message is shown.

**Todo List**
1. Add `WaitlistEntry`, `WaitlistRequest` interfaces to `booking_system_frontend/src/types/index.ts`.
2. Add `joinWaitlist()` function to `booking_system_frontend/src/services/api.ts` — `POST /waitlist`.
3. In `booking_system_frontend/src/components/flights/FlightCard.tsx`:
   - Change `onBook` to `onBook(flight, seatClass?)`.
   - For each sold-out class, render a "Join Waitlist" button that calls `onBook(flight, seatClass)`.
   - Keep the main button enabled when all classes are sold out; label it "All Classes Sold Out: Join Waitlist".
4. In `booking_system_frontend/src/pages/Flights.tsx`: keep the chosen class and pass it to `BookingModal` as `initialClass`.
5. In `booking_system_frontend/src/components/bookings/BookingModal.tsx`:
   - Accept an optional `initialClass` prop and select it when the modal opens (default `economy`).
   - Do not disable sold-out class buttons; show them as sold out but keep them selectable.
   - Detect sold-out state for the selected class (`seats === 0`).
   - Show "Join Waitlist" button and contextual copy when sold out.
   - Call `joinWaitlist` on submit; display position from response.
6. Run `npm run build` in `booking_system_frontend/` to confirm no TypeScript errors.

**Relevant Context**
- `FlightCard`: `booking_system_frontend/src/components/flights/FlightCard.tsx` — shows each class with seats left; the main button is currently disabled when all classes are sold out.
- `Flights` page: `booking_system_frontend/src/pages/Flights.tsx` — opens `BookingModal` via `onBook`.
- `BookingModal`: `booking_system_frontend/src/components/bookings/BookingModal.tsx` — `seats` is already read from `flight` per class.
- API pattern: `bookFlight` in `booking_system_frontend/src/services/api.ts:117–130`.
- Types file: `booking_system_frontend/src/types/index.ts`.

---

### Sub-Task 7 — Frontend: My Bookings waitlist section

**Status:** `[x] done`

**Intent**
Show the user's active waitlist entries on the My Bookings page so they can see their queue position and which flight they're waiting for.

**Expected Outcomes**
- `getUserWaitlist(userId)` API function added to `api.ts`.
- `MyBookings` page fetches and displays a "Waitlist" section listing each active (status=`waiting`) waitlist entry with flight details and queue position.
- The section is hidden when there are no waiting entries.

**Todo List**
1. Add `getUserWaitlist(userId: number)` to `booking_system_frontend/src/services/api.ts` — `GET /waitlist/{user_id}`.
2. In `booking_system_frontend/src/pages/MyBookings.tsx`:
   - Fetch waitlist entries alongside bookings.
   - Filter for `status === 'waiting'`.
   - Render a "Waitlist" section above or below active bookings, showing flight origin/destination, seat class, locked price, and queue position.
3. Run `npm run build` to confirm no TypeScript errors.

**Relevant Context**
- `MyBookings`: `booking_system_frontend/src/pages/MyBookings.tsx` — uses `Promise.all` to load bookings + flights; add waitlist to the same call.
- `HoldCard` component is a reference for a card-style display of a non-booking item.

---

## Architecture Notes

- The `WaitlistEntry` table is the source of truth for queue state. `position` is immutable after assignment; ordering by `position ASC` always gives correct FIFO.
- `_promote_from_waitlist` is called synchronously inside `cancel_booking` before the DB commit — no background jobs, no race conditions under SQLite's single-writer model.
- `locked_price` means the promoted booking's `price_paid` may differ from the current `base_price`. This is intentional.
- No seat counter is touched at join time — the waitlist entry is a reservation of intent, not a seat hold.
- The Java hold-service path (`/internal/bookings/from-hold`) calls `book_flight()` directly; if the flight is full at hold-confirm time, it returns an error normally. Waitlist joining is not triggered from that path (hold-confirmed bookings imply a seat was reserved).
