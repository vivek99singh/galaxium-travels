import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from sqlalchemy.orm import Session

from db import get_db, init_db
from schemas import (
    BookingOut,
    BookingRequest,
    ErrorResponse,
    FlightOut,
    NotificationOut,
    UserOut,
    UserRegistration,
    WaitlistActionRequest,
    WaitlistOut,
    WaitlistRequest,
)
from seed import seed
from services import booking, flight, user, waitlist

# Load environment variables from .env file
load_dotenv()


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()

    should_seed = os.getenv("SEED_DEMO_DATA", "true").lower() in {"1", "true", "yes", "on"}
    if should_seed:
        seed()

    yield
    # Shutdown (nothing to do)


# ==================== FASTAPI APP (REST + Swagger UI) ====================

app = FastAPI(
    title="Galaxium Booking System",
    description="API for booking interplanetary flights. Swagger UI available at /docs",
    version="1.0.0",
    lifespan=lifespan,
    root_path="/api"  # Add this for ALB routing
)

# Get allowed origins from environment
allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_fresh(db: Session = Depends(get_db)):
    """A DB session with expired waitlist offers already handed on to the next person."""
    waitlist.expire_stale_offers(db)
    return db


@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "OK"}


@app.get("/flights", response_model=list[FlightOut], tags=["Flights"])
def get_flights(
    # Basic filters from main branch
    origin: str | None = None,
    destination: str | None = None,
    departure_date_from: str | None = None,
    departure_date_to: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    has_economy: bool | None = None,
    has_business: bool | None = None,
    has_galaxium: bool | None = None,
    sort: str | None = None,
    order: str | None = 'asc',
    # Phase 1: Core Filters from feature branch
    sort_by: str | None = None,
    sort_order: str | None = None,
    seat_class: str | None = None,
    # Phase 2: Additional Filters from feature branch
    departure_time_period: str | None = None,
    min_duration: int | None = None,
    max_duration: int | None = None,
    min_seats_available: int | None = None,
    # Phase 3: Popular Routes from feature branch
    route_category: str | None = None,
    db: Session = Depends(get_db_fresh)
):
    """List all available flights with optional filtering and sorting.
    
    All query parameters are optional for backward compatibility.
    
    **Basic Filters:**
    - origin: Filter by origin (case-insensitive partial match)
    - destination: Filter by destination (case-insensitive partial match)
    - departure_date_from: Filter flights departing on or after this date (ISO format)
    - departure_date_to: Filter flights departing on or before this date (ISO format)
    - min_price: Minimum price (checks economy price)
    - max_price: Maximum price (checks economy price)
    - has_economy: Only flights with economy seats available
    - has_business: Only flights with business seats available
    - has_galaxium: Only flights with galaxium seats available
    - sort: Sort by 'price', 'departure_time', or 'duration'
    - order: Sort order 'asc' or 'desc' (default: asc)
    
    **Phase 1 - Core Filters:**
    - sort_by: Field to sort by (departure_time, base_price, duration, seats_available)
    - sort_order: Sort direction (asc, desc)
    - seat_class: Filter by seat class availability (economy, business, galaxium)
    
    **Phase 2 - Additional Filters:**
    - departure_time_period: Time of day (morning, afternoon, evening, night)
    - min_duration: Minimum flight duration in hours
    - max_duration: Maximum flight duration in hours
    - min_seats_available: Minimum total seats available
    
    **Phase 3 - Popular Routes:**
    - route_category: Route category (inner_planets, outer_planets, moons)
    """
    return flight.list_flights(
        db=db,
        origin=origin,
        destination=destination,
        departure_date_from=departure_date_from,
        departure_date_to=departure_date_to,
        min_price=min_price,
        max_price=max_price,
        has_economy=has_economy,
        has_business=has_business,
        has_galaxium=has_galaxium,
        sort=sort,
        order=order,
        sort_by=sort_by,
        sort_order=sort_order,
        seat_class=seat_class,
        departure_time_period=departure_time_period,
        min_duration=min_duration,
        max_duration=max_duration,
        min_seats_available=min_seats_available,
        route_category=route_category
    )


@app.post("/book", response_model=BookingOut, tags=["Bookings"])
def book_flight_endpoint(request: BookingRequest, db: Session = Depends(get_db_fresh)):
    """Book a seat on a specific flight for a user in the specified seat class.

    Requires user_id, name, and flight_id.
    Optional seat_class: 'economy' (default), 'business', or 'galaxium'.
    Decrements available seats for the selected class if successful.
    Returns booking details. Raises 404 if the flight or user is not found,
    409 if there is a name mismatch or no seats available.
    """
    result = booking.book_flight(db, request.user_id, request.name, request.flight_id, request.seat_class)
    if isinstance(result, ErrorResponse):
        status = 404 if result.error_code in ("FLIGHT_NOT_FOUND", "USER_NOT_FOUND") else 409
        raise HTTPException(status_code=status, detail=result.model_dump())
    return result


@app.get("/bookings/{user_id}", response_model=list[BookingOut], tags=["Bookings"])
def get_user_bookings(user_id: int, db: Session = Depends(get_db_fresh)):
    """Retrieve all bookings for a specific user by user_id."""
    return booking.get_bookings(db, user_id)


@app.post("/waitlist", response_model=WaitlistOut, status_code=201, tags=["Waitlist"])
def join_waitlist_endpoint(request: WaitlistRequest, db: Session = Depends(get_db_fresh)):
    """Join the waitlist for a sold-out seat class on a flight.

    Returns 404 for unknown flight or user, 409 if seats are still available,
    name mismatches, or the user is already waitlisted.
    """
    result = waitlist.join_waitlist(db, request.user_id, request.name, request.flight_id, request.seat_class)
    if isinstance(result, ErrorResponse):
        status = 404 if result.error_code in ("FLIGHT_NOT_FOUND", "USER_NOT_FOUND") else 409
        raise HTTPException(status_code=status, detail=result.model_dump())
    return result


@app.get("/waitlist/{user_id}", response_model=list[WaitlistOut], tags=["Waitlist"])
def get_user_waitlist(user_id: int, db: Session = Depends(get_db_fresh)):
    """Retrieve all waitlist entries for a specific user by user_id."""
    return waitlist.get_waitlist(db, user_id)


WAITLIST_ERROR_STATUS = {
    "WAITLIST_NOT_FOUND": 404, "NOT_OWNER": 403, "INVALID_WAITLIST_STATUS": 409, "OFFER_EXPIRED": 409,
}


def _raise_waitlist_error(result: ErrorResponse):
    raise HTTPException(status_code=WAITLIST_ERROR_STATUS.get(result.error_code, 400), detail=result.model_dump())


@app.post("/waitlist/{waitlist_id}/accept", response_model=BookingOut, tags=["Waitlist"])
def accept_waitlist_offer(waitlist_id: int, request: WaitlistActionRequest, db: Session = Depends(get_db_fresh)):
    """Accept a seat offer from the waitlist. Creates a booking at the locked price.

    Returns 404 if the entry is unknown, 403 if it belongs to another user,
    409 if the entry has no open offer.
    """
    result = waitlist.accept_offer(db, waitlist_id, request.user_id)
    if isinstance(result, ErrorResponse):
        _raise_waitlist_error(result)
    return result


@app.post("/waitlist/{waitlist_id}/decline", response_model=WaitlistOut, tags=["Waitlist"])
def decline_waitlist_offer(waitlist_id: int, request: WaitlistActionRequest, db: Session = Depends(get_db_fresh)):
    """Decline a seat offer. The seat is offered to the next person waiting."""
    result = waitlist.decline_offer(db, waitlist_id, request.user_id)
    if isinstance(result, ErrorResponse):
        _raise_waitlist_error(result)
    return result


@app.post("/waitlist/{waitlist_id}/leave", response_model=WaitlistOut, tags=["Waitlist"])
def leave_waitlist_endpoint(waitlist_id: int, request: WaitlistActionRequest, db: Session = Depends(get_db_fresh)):
    """Leave the waitlist. Works while waiting or while holding an offer."""
    result = waitlist.leave_waitlist(db, waitlist_id, request.user_id)
    if isinstance(result, ErrorResponse):
        _raise_waitlist_error(result)
    return result


@app.get("/notifications/{user_id}", response_model=list[NotificationOut], tags=["Notifications"])
def get_user_notifications(user_id: int, db: Session = Depends(get_db_fresh)):
    """Retrieve all notifications for a specific user by user_id, newest first."""
    from models import Notification
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.notification_id.desc())
        .all()
    )
    return [NotificationOut.model_validate(n) for n in notifications]


@app.post("/cancel/{booking_id}", response_model=BookingOut, tags=["Bookings"])
def cancel_booking_endpoint(booking_id: int, db: Session = Depends(get_db_fresh)):
    """Cancel an existing booking by its booking_id.

    Increments available seats for the flight if successful.
    Raises 404 if the booking is not found, 409 if already cancelled.
    """
    result = booking.cancel_booking(db, booking_id)
    if isinstance(result, ErrorResponse):
        status = 404 if result.error_code == "BOOKING_NOT_FOUND" else 409
        raise HTTPException(status_code=status, detail=result.model_dump())
    return result


@app.post("/register", response_model=UserOut, tags=["Users"])
def register_user_endpoint(request: UserRegistration, db: Session = Depends(get_db)):
    """Register a new user with a name and unique email.

    Raises 409 if the email is already registered, 422 if the email format is invalid.
    """
    result = user.register_user(db, request.name, request.email)
    if isinstance(result, ErrorResponse):
        status = 409 if result.error_code == "EMAIL_EXISTS" else 422
        raise HTTPException(status_code=status, detail=result.model_dump())
    return result


@app.get("/user", response_model=UserOut, tags=["Users"])
def get_user_endpoint(name: str, email: str, db: Session = Depends(get_db)):
    """Get user by name and email.

    Raises 404 if no user matches the provided name and email,
    422 if the email format is invalid.
    """
    result = user.get_user(db, name, email)
    if isinstance(result, ErrorResponse):
        status = 404 if result.error_code == "USER_NOT_FOUND" else 422
        raise HTTPException(status_code=status, detail=result.model_dump())
    return result


# ==================== JAVA SERVICE INTEGRATION ====================

JAVA_SERVICE_URL = os.getenv("JAVA_SERVICE_URL", "http://localhost:8080")


@app.post("/internal/bookings/from-hold", response_model=BookingOut, tags=["Internal"])
def create_booking_from_hold(hold_data: dict, db: Session = Depends(get_db_fresh)):
    """Internal endpoint for Java hold service to create bookings.

    This endpoint is called by the Java inventory hold service when confirming a hold.
    Returns HTTP 400 on booking failure so the Java service can detect and propagate the error.
    """
    result = booking.book_flight(
        db,
        user_id=hold_data["travelerId"],
        name=hold_data["travelerName"],
        flight_id=hold_data["flightId"],
        seat_class=hold_data["seatClass"]
    )
    if isinstance(result, ErrorResponse):
        raise HTTPException(status_code=400, detail=result.model_dump())
    return result


# ==================== JAVA SERVICE PROXY ENDPOINTS ====================

@app.post("/quotes", tags=["Quotes"])
async def create_quote(quote_data: dict):
    """Proxy endpoint to create a quote in the Java hold service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{JAVA_SERVICE_URL}/api/v1/quotes",
                json=quote_data,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to create quote: {e!s}"}


@app.get("/quotes/{quote_id}", tags=["Quotes"])
async def get_quote(quote_id: str):
    """Proxy endpoint to get a quote from the Java hold service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{JAVA_SERVICE_URL}/api/v1/quotes/{quote_id}",
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to get quote: {e!s}"}


@app.post("/quotes/{quote_id}/holds", tags=["Holds"])
async def create_hold(quote_id: str):
    """Proxy endpoint to create a hold from a quote in the Java hold service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{JAVA_SERVICE_URL}/api/v1/quotes/{quote_id}/holds",
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to create hold: {e!s}"}


@app.get("/holds/{hold_id}", tags=["Holds"])
async def get_hold(hold_id: str):
    """Proxy endpoint to get a hold from the Java hold service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{JAVA_SERVICE_URL}/api/v1/holds/{hold_id}",
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to get hold: {e!s}"}


@app.post("/holds/{hold_id}/confirm", tags=["Holds"])
async def confirm_hold(hold_id: str):
    """Proxy endpoint to confirm a hold in the Java hold service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{JAVA_SERVICE_URL}/api/v1/holds/{hold_id}/confirm",
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to confirm hold: {e!s}"}


@app.post("/holds/{hold_id}/release", tags=["Holds"])
async def release_hold(hold_id: str):
    """Proxy endpoint to release a hold in the Java hold service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{JAVA_SERVICE_URL}/api/v1/holds/{hold_id}/release",
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"Failed to release hold: {e!s}"}


# ==================== MCP SERVER (for AI agents) ====================
# Auto-generates MCP tools from all FastAPI routes above — no duplication needed.

mcp = FastApiMCP(app)
mcp.mount_http()


# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
