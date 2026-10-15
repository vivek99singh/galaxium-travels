from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import Booking, Flight, Notification, User, WaitlistEntry
from schemas import BookingOut, ErrorResponse, SeatClass, WaitlistOut
from services.booking import SEAT_CLASS_MULTIPLIERS

# How long a waitlist offer holds the seat, matching the 15-minute seat hold
OFFER_MINUTES = 15


def join_waitlist(
    db: Session, user_id: int, name: str, flight_id: int, seat_class: SeatClass = 'economy'
) -> WaitlistOut | ErrorResponse:
    """Join the waitlist for a sold-out seat class on a flight."""
    # Check flight exists
    flight = db.query(Flight).filter(Flight.flight_id == flight_id).first()
    if not flight:
        return ErrorResponse(
            error="Flight not found",
            error_code="FLIGHT_NOT_FOUND",
            details=f"The specified flight_id {flight_id} does not exist in our system."
        )

    # Check user exists and name matches
    user = db.query(User).filter(User.user_id == user_id, User.name == name).first()
    if not user:
        existing_user = db.query(User).filter(User.user_id == user_id).first()
        if existing_user:
            return ErrorResponse(
                error="Name mismatch",
                error_code="NAME_MISMATCH",
                details=f"User ID {user_id} exists but the name provided does not match our records. Please verify the name for this user ID."
            )
        return ErrorResponse(
            error="User not found",
            error_code="USER_NOT_FOUND",
            details=f"User with ID {user_id} is not registered in our system."
        )

    # Seats still available — no need to waitlist
    seats_available = getattr(flight, f"{seat_class}_seats_available")
    if seats_available > 0:
        return ErrorResponse(
            error="Seats are available",
            error_code="SEATS_AVAILABLE",
            details=f"Flight {flight_id} still has {seats_available} {seat_class} seat(s) available. Please book directly."
        )

    # Already on waitlist for this flight+seat_class
    existing = db.query(WaitlistEntry).filter(
        WaitlistEntry.flight_id == flight_id,
        WaitlistEntry.user_id == user_id,
        WaitlistEntry.seat_class == seat_class,
        WaitlistEntry.status.in_(('waiting', 'offered')),
    ).first()
    if existing:
        return ErrorResponse(
            error="Already waitlisted",
            error_code="ALREADY_WAITLISTED",
            details=f"User {user_id} is already on the waitlist for flight {flight_id} ({seat_class} class)."
        )

    locked_price = int(flight.base_price * SEAT_CLASS_MULTIPLIERS[seat_class])
    position = db.query(WaitlistEntry).filter(
        WaitlistEntry.flight_id == flight_id,
        WaitlistEntry.seat_class == seat_class,
        WaitlistEntry.status == 'waiting',
    ).count() + 1

    entry = WaitlistEntry(
        user_id=user_id,
        flight_id=flight_id,
        seat_class=seat_class,
        status='waiting',
        position=position,
        locked_price=locked_price,
        created_at=datetime.now(tz=timezone.utc).isoformat(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return WaitlistOut.model_validate(entry)


def get_waitlist(db: Session, user_id: int) -> list[WaitlistOut]:
    """Retrieve all waitlist entries for a specific user."""
    entries = db.query(WaitlistEntry).filter(WaitlistEntry.user_id == user_id).all()
    return [WaitlistOut.model_validate(e) for e in entries]


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _notify(db: Session, user_id: int, type_: str, message: str) -> None:
    db.add(Notification(user_id=user_id, type=type_, message=message, created_at=_now()))


def _adjust_seat(db: Session, flight_id: int, seat_class: str, delta: int) -> None:
    flight = db.query(Flight).filter(Flight.flight_id == flight_id).first()
    if flight:
        column = f"{seat_class}_seats_available"
        setattr(flight, column, getattr(flight, column) + delta)


def _close_gap(db: Session, entry: WaitlistEntry) -> None:
    """Move everyone waiting behind this entry up one place in the queue."""
    behind = db.query(WaitlistEntry).filter(
        WaitlistEntry.flight_id == entry.flight_id,
        WaitlistEntry.seat_class == entry.seat_class,
        WaitlistEntry.status == 'waiting',
        WaitlistEntry.position > entry.position,
    ).all()
    for other in behind:
        other.position -= 1


def _offer_next_seat(db: Session, flight_id: int, seat_class: str) -> bool:
    """Offer a freed seat to the first waiting entry for a flight+seat_class.

    The caller must have already made the seat available. The seat is held for
    the offered user (taken off sale) until they accept or decline. Returns
    False if nobody is waiting, in which case the seat stays on sale.
    """
    entry = (
        db.query(WaitlistEntry)
        .filter(
            WaitlistEntry.flight_id == flight_id,
            WaitlistEntry.seat_class == seat_class,
            WaitlistEntry.status == 'waiting',
        )
        .order_by(WaitlistEntry.position.asc())
        .first()
    )
    if not entry:
        return False

    _adjust_seat(db, flight_id, seat_class, -1)
    entry.status = 'offered'
    entry.offer_expires_at = (datetime.now(tz=timezone.utc) + timedelta(minutes=OFFER_MINUTES)).isoformat()
    _close_gap(db, entry)
    _notify(
        db, entry.user_id, 'waitlist_offer',
        f"A {seat_class} seat on flight {flight_id} is now available for you at "
        f"{entry.locked_price} credits. Accept or decline within {OFFER_MINUTES} minutes in My Bookings.",
    )
    print(f"[WAITLIST] User {entry.user_id} offered a seat on flight {flight_id} ({seat_class})")
    return True


def expire_stale_offers(db: Session) -> int:
    """Expire offers past their deadline and pass each seat to the next person.

    Called before any request that reads or changes seats or the waitlist, so
    no background job is needed. Returns how many offers expired.
    """
    now = datetime.now(tz=timezone.utc)
    offered = db.query(WaitlistEntry).filter(WaitlistEntry.status == 'offered').all()
    expired = [
        e for e in offered
        if e.offer_expires_at and datetime.fromisoformat(e.offer_expires_at) <= now
    ]
    for entry in expired:
        entry.status = 'expired'
        _notify(
            db, entry.user_id, 'waitlist_expired',
            f"Your offer for the {entry.seat_class} seat on flight {entry.flight_id} expired "
            f"after {OFFER_MINUTES} minutes.",
        )
        print(f"[WAITLIST] Offer to user {entry.user_id} expired for flight {entry.flight_id} ({entry.seat_class})")
        _release_offered_seat(db, entry)
    if expired:
        db.commit()
    return len(expired)


def _get_own_entry(
    db: Session, waitlist_id: int, user_id: int, allowed: tuple[str, ...]
) -> WaitlistEntry | ErrorResponse:
    entry = db.query(WaitlistEntry).filter(WaitlistEntry.waitlist_id == waitlist_id).first()
    if not entry:
        return ErrorResponse(
            error="Waitlist entry not found",
            error_code="WAITLIST_NOT_FOUND",
            details=f"Waitlist entry {waitlist_id} does not exist.",
        )
    if entry.user_id != user_id:
        return ErrorResponse(
            error="Not your waitlist entry",
            error_code="NOT_OWNER",
            details=f"Waitlist entry {waitlist_id} does not belong to user {user_id}.",
        )
    if entry.status == 'expired' and 'offered' in allowed:
        return ErrorResponse(
            error="Offer expired",
            error_code="OFFER_EXPIRED",
            details=f"The offer for waitlist entry {waitlist_id} expired after {OFFER_MINUTES} minutes.",
        )
    if entry.status not in allowed:
        return ErrorResponse(
            error="Invalid waitlist status",
            error_code="INVALID_WAITLIST_STATUS",
            details=f"Waitlist entry {waitlist_id} is '{entry.status}'; this action needs {' or '.join(allowed)}.",
        )
    return entry


def accept_offer(db: Session, waitlist_id: int, user_id: int) -> BookingOut | ErrorResponse:
    """Accept a seat offer: create a confirmed booking at the locked price."""
    expire_stale_offers(db)
    entry = _get_own_entry(db, waitlist_id, user_id, ('offered',))
    if isinstance(entry, ErrorResponse):
        return entry

    # The seat was already taken off sale when the offer was made
    new_booking = Booking(
        user_id=entry.user_id,
        flight_id=entry.flight_id,
        status='booked',
        booking_time=_now(),
        seat_class=entry.seat_class,
        price_paid=entry.locked_price,
    )
    db.add(new_booking)
    db.flush()  # populate booking_id before building the notification message
    entry.status = 'promoted'
    entry.offer_expires_at = None
    _notify(
        db, entry.user_id, 'waitlist_confirmed',
        f"Your booking #{new_booking.booking_id} on flight {entry.flight_id} "
        f"({entry.seat_class} class) is confirmed at {entry.locked_price} credits.",
    )
    print(
        f"[WAITLIST] User {entry.user_id} accepted offer, booking "
        f"{new_booking.booking_id} for flight {entry.flight_id} ({entry.seat_class})"
    )
    db.commit()
    db.refresh(new_booking)
    return BookingOut.model_validate(new_booking)


def decline_offer(db: Session, waitlist_id: int, user_id: int) -> WaitlistOut | ErrorResponse:
    """Decline a seat offer: release the seat and offer it to the next in line."""
    expire_stale_offers(db)
    entry = _get_own_entry(db, waitlist_id, user_id, ('offered',))
    if isinstance(entry, ErrorResponse):
        return entry

    entry.status = 'declined'
    _release_offered_seat(db, entry)
    _notify(
        db, entry.user_id, 'waitlist_declined',
        f"You declined the {entry.seat_class} seat on flight {entry.flight_id}.",
    )
    db.commit()
    db.refresh(entry)
    return WaitlistOut.model_validate(entry)


def leave_waitlist(db: Session, waitlist_id: int, user_id: int) -> WaitlistOut | ErrorResponse:
    """Leave the waitlist, either while waiting or while holding an offer."""
    expire_stale_offers(db)
    entry = _get_own_entry(db, waitlist_id, user_id, ('waiting', 'offered'))
    if isinstance(entry, ErrorResponse):
        return entry

    was_offered = entry.status == 'offered'
    entry.status = 'left'
    if was_offered:
        _release_offered_seat(db, entry)
    else:
        _close_gap(db, entry)
    _notify(
        db, entry.user_id, 'waitlist_left',
        f"You left the waitlist for flight {entry.flight_id} ({entry.seat_class} class).",
    )
    db.commit()
    db.refresh(entry)
    return WaitlistOut.model_validate(entry)


def _release_offered_seat(db: Session, entry: WaitlistEntry) -> None:
    """Put a held seat back on sale, then offer it to the next person waiting."""
    _adjust_seat(db, entry.flight_id, entry.seat_class, +1)
    _offer_next_seat(db, entry.flight_id, entry.seat_class)
