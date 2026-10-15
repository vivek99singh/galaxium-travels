import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Booking, Flight, Notification, User, WaitlistEntry
from schemas import ErrorResponse
from services import booking, flight, user, waitlist


class TestFlightService:
    """Test flight service functions."""

    def test_list_flights_empty(self, db_session):
        """Test listing flights when database is empty."""
        result = flight.list_flights(db_session)
        assert result == []

    def test_list_flights_with_data(self, db_session):
        """Test listing flights with data in database."""
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000,
            economy_seats_available=5,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(db_session)
        assert len(result) == 1
        assert result[0].origin == "Earth"
        assert result[0].destination == "Mars"

    def test_list_flights_sort_by_price_asc(self, db_session):
        """Test sorting flights by price ascending."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=2000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Venus",
            departure_time="2099-01-02 09:00", arrival_time="2099-01-02 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(db_session, sort_by="base_price", sort_order="asc")
        assert len(result) == 2
        assert result[0].base_price == 1000
        assert result[1].base_price == 2000

    def test_list_flights_sort_by_price_desc(self, db_session):
        """Test sorting flights by price descending."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Venus",
            departure_time="2099-01-02 09:00", arrival_time="2099-01-02 17:00",
            base_price=2000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(db_session, sort_by="base_price", sort_order="desc")
        assert len(result) == 2
        assert result[0].base_price == 2000
        assert result[1].base_price == 1000

    def test_list_flights_filter_by_date_range(self, db_session):
        """Test filtering flights by date range."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Venus",
            departure_time="2099-01-15 09:00", arrival_time="2099-01-15 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(db_session, departure_date_from="2099-01-10", departure_date_to="2099-01-20")
        assert len(result) == 1
        assert result[0].destination == "Venus"

    def test_list_flights_filter_by_price_range(self, db_session):
        """Test filtering flights by price range."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=500, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Venus",
            departure_time="2099-01-02 09:00", arrival_time="2099-01-02 17:00",
            base_price=1500, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Jupiter",
            departure_time="2099-01-03 09:00", arrival_time="2099-01-03 17:00",
            base_price=2500, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(db_session, min_price=1000, max_price=2000)
        assert len(result) == 1
        assert result[0].base_price == 1500

    def test_list_flights_filter_by_seat_class(self, db_session):
        """Test filtering flights by seat class availability."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000, economy_seats_available=0, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Venus",
            departure_time="2099-01-02 09:00", arrival_time="2099-01-02 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=0, galaxium_seats_available=0
        ))
        db_session.commit()

        result = flight.list_flights(db_session, seat_class="economy")
        assert len(result) == 1
        assert result[0].destination == "Venus"

    def test_list_flights_filter_by_time_period(self, db_session):
        """Test filtering flights by time of day."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 08:00", arrival_time="2099-01-01 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Venus",
            departure_time="2099-01-01 14:00", arrival_time="2099-01-01 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(db_session, departure_time_period="morning")
        assert len(result) == 1
        assert result[0].destination == "Mars"

    def test_list_flights_filter_by_duration(self, db_session):
        """Test filtering flights by duration."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 13:00",  # 4 hours
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Jupiter",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 21:00",  # 12 hours
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(db_session, min_duration=5, max_duration=15)
        assert len(result) == 1
        assert result[0].destination == "Jupiter"

    def test_list_flights_filter_by_min_seats(self, db_session):
        """Test filtering flights by minimum seats available."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000, economy_seats_available=1, business_seats_available=1, galaxium_seats_available=0
        ))
        db_session.add(Flight(
            origin="Earth", destination="Venus",
            departure_time="2099-01-02 09:00", arrival_time="2099-01-02 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=2
        ))
        db_session.commit()

        result = flight.list_flights(db_session, min_seats_available=5)
        assert len(result) == 1
        assert result[0].destination == "Venus"

    def test_list_flights_filter_by_route_category(self, db_session):
        """Test filtering flights by route category."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Jupiter",
            departure_time="2099-01-02 09:00", arrival_time="2099-01-02 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(db_session, route_category="inner_planets")
        assert len(result) == 1
        assert result[0].destination == "Mars"

    def test_list_flights_combined_filters(self, db_session):
        """Test combining multiple filters."""
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.add(Flight(
            origin="Earth", destination="Venus",
            departure_time="2099-01-02 09:00", arrival_time="2099-01-02 17:00",
            base_price=2000, economy_seats_available=5, business_seats_available=3, galaxium_seats_available=1
        ))
        db_session.commit()

        result = flight.list_flights(
            db_session,
            sort_by="base_price",
            sort_order="asc",
            min_price=500,
            max_price=1500,
            seat_class="economy"
        )
        assert len(result) == 1
        assert result[0].destination == "Mars"


class TestUserService:
    """Test user service functions."""

    def test_register_user_success(self, db_session):
        """Test successful user registration."""
        result = user.register_user(db_session, "Test User", "test@example.com")
        assert result.name == "Test User"
        assert result.email == "test@example.com"
        assert result.user_id > 0

    def test_register_user_duplicate_email(self, db_session):
        """Test registration with duplicate email."""
        user.register_user(db_session, "User 1", "test@example.com")
        result = user.register_user(db_session, "User 2", "test@example.com")

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "EMAIL_EXISTS"

    def test_get_user_success(self, db_session):
        """Test successful user retrieval."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()

        result = user.get_user(db_session, "Test User", "test@example.com")
        assert result.name == "Test User"
        assert result.email == "test@example.com"

    def test_get_user_not_found(self, db_session):
        """Test user retrieval when not found."""
        result = user.get_user(db_session, "NonExistent", "none@example.com")
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "USER_NOT_FOUND"


class TestBookingService:
    """Test booking service functions."""

    def test_book_flight_success(self, db_session):
        """Test successful flight booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=5,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id)
        assert result.status == "booked"
        assert result.user_id == user_obj.user_id
        assert result.flight_id == flight_obj.flight_id

        # Verify seat was decremented
        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 4

    def test_book_flight_not_found(self, db_session):
        """Test booking non-existent flight."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()
        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", 999)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "FLIGHT_NOT_FOUND"

    def test_book_flight_no_seats(self, db_session):
        """Test booking when no seats available."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=0,
            business_seats_available=0,
            galaxium_seats_available=0
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NO_SEATS_AVAILABLE"

    def test_book_flight_user_not_found(self, db_session):
        """Test booking with non-existent user."""
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=5,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, 999, "Fake User", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "USER_NOT_FOUND"

    def test_book_flight_name_mismatch(self, db_session):
        """Test booking with wrong name for user ID."""
        db_session.add(User(name="Real Name", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=5,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Wrong Name", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NAME_MISMATCH"

    def test_book_flight_name_mismatch_does_not_leak_stored_name(self, db_session):
        """SR-1: NAME_MISMATCH details must not reveal the stored registered name."""
        db_session.add(User(name="Secret Name", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000,
            economy_seats_available=5,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()
        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Wrong Name", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NAME_MISMATCH"
        assert "Secret Name" not in result.details

    def test_cancel_booking_success(self, db_session):
        """Test successful booking cancellation."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=4,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="booked",
            booking_time="2099-01-01 10:00",
            seat_class="economy",
            price_paid=1000000
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert result.status == "cancelled"

        # Verify seat was restored
        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 5

    def test_cancel_booking_not_found(self, db_session):
        """Test cancelling non-existent booking."""
        result = booking.cancel_booking(db_session, 999)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "BOOKING_NOT_FOUND"

    def test_cancel_booking_already_cancelled(self, db_session):
        """Test cancelling already cancelled booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=5,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="cancelled",
            booking_time="2099-01-01 10:00",
            seat_class="economy",
            price_paid=1000000
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "ALREADY_CANCELLED"

    def test_get_bookings_success(self, db_session):
        """Test getting user bookings."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01 09:00",
            arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=5,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="booked",
            booking_time="2099-01-01 10:00",
            seat_class="economy",
            price_paid=1000000
        ))
        db_session.commit()

        result = booking.get_bookings(db_session, user_obj.user_id)
        assert len(result) == 1
        assert result[0].status == "booked"

    def test_get_bookings_empty(self, db_session):
        """Test getting bookings when user has none."""
        result = booking.get_bookings(db_session, 999)
        assert result == []

    def test_cancel_booking_offers_seat_to_waitlist(self, db_session):
        """Cancel with an active waitlist entry → seat is offered and held, no booking yet."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(User(name="Waiter User", email="waiter@example.com"))
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=0,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        user_obj = db_session.query(User).filter_by(email="test@example.com").first()
        waiter = db_session.query(User).filter_by(email="waiter@example.com").first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id, flight_id=flight_obj.flight_id,
            status="booked", booking_time="2099-01-01 10:00",
            seat_class="economy", price_paid=1000000
        ))
        db_session.add(WaitlistEntry(
            user_id=waiter.user_id, flight_id=flight_obj.flight_id,
            seat_class="economy", status="waiting", position=1,
            locked_price=1000000, created_at="2099-01-01 08:00"
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).filter_by(user_id=user_obj.user_id).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert result.status == "cancelled"
        # Seat restored then held for the offer → stays at 0
        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 0
        # No booking until the waiter accepts
        assert db_session.query(Booking).filter_by(user_id=waiter.user_id).first() is None
        entry = db_session.query(WaitlistEntry).filter_by(user_id=waiter.user_id).first()
        assert entry.status == "offered"
        notes = db_session.query(Notification).filter_by(user_id=waiter.user_id).all()
        assert [n.type for n in notes] == ["waitlist_offer"]

    def test_cancel_booking_no_waitlist_restores_seat(self, db_session):
        """Cancel with no waitlist entry → seat is simply restored (regression)."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=4,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id, flight_id=flight_obj.flight_id,
            status="booked", booking_time="2099-01-01 10:00",
            seat_class="economy", price_paid=1000000
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert result.status == "cancelled"
        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 5


class TestWaitlistService:
    """Test waitlist service functions."""

    def _make_full_flight(self, db_session):
        """Helper: add a user and a sold-out economy flight, return (user, flight)."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=0,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()
        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()
        return user_obj, flight_obj

    def test_join_waitlist_success(self, db_session):
        """Successfully join waitlist for a sold-out class."""
        user_obj, flight_obj = self._make_full_flight(db_session)
        result = waitlist.join_waitlist(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "economy")
        assert not isinstance(result, ErrorResponse)
        assert result.position == 1
        assert result.status.value == "waiting"
        assert result.seat_class == "economy"
        assert result.locked_price == 1000000

    def test_join_waitlist_seats_available(self, db_session):
        """Returns SEATS_AVAILABLE when the class is not sold out."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=5,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()
        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()
        result = waitlist.join_waitlist(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "economy")
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "SEATS_AVAILABLE"

    def test_join_waitlist_flight_not_found(self, db_session):
        """Returns FLIGHT_NOT_FOUND for unknown flight."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()
        user_obj = db_session.query(User).first()
        result = waitlist.join_waitlist(db_session, user_obj.user_id, "Test User", 999, "economy")
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "FLIGHT_NOT_FOUND"

    def test_join_waitlist_name_mismatch_does_not_leak_stored_name(self, db_session):
        """SR-1: NAME_MISMATCH on join_waitlist must not reveal the stored registered name."""
        user_obj, flight_obj = self._make_full_flight(db_session)
        result = waitlist.join_waitlist(db_session, user_obj.user_id, "Wrong Name", flight_obj.flight_id, "economy")
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NAME_MISMATCH"
        assert "Test User" not in result.details

    def test_join_waitlist_duplicate(self, db_session):
        """Returns ALREADY_WAITLISTED on a second join attempt for same flight+class."""
        user_obj, flight_obj = self._make_full_flight(db_session)
        waitlist.join_waitlist(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "economy")
        result = waitlist.join_waitlist(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "economy")
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "ALREADY_WAITLISTED"

    def test_get_waitlist_returns_entries(self, db_session):
        """get_waitlist returns all entries for a user."""
        user_obj, flight_obj = self._make_full_flight(db_session)
        waitlist.join_waitlist(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "economy")
        results = waitlist.get_waitlist(db_session, user_obj.user_id)
        assert len(results) == 1
        assert results[0].user_id == user_obj.user_id

    def test_get_waitlist_empty(self, db_session):
        """get_waitlist returns empty list when user has no entries."""
        assert waitlist.get_waitlist(db_session, 999) == []


class TestWaitlistOfferFlow:
    """Test offer, accept, decline and leave on the waitlist."""

    def _setup(self, db_session, waiters=2):
        """A sold-out economy flight, one booked user, and `waiters` users queued in order."""
        db_session.add(User(name="Booker", email="booker@example.com"))
        for i in range(waiters):
            db_session.add(User(name=f"Waiter {i + 1}", email=f"waiter{i + 1}@example.com"))
        db_session.add(Flight(
            origin="Earth", destination="Mars",
            departure_time="2099-01-01 09:00", arrival_time="2099-01-01 17:00",
            base_price=1000000,
            economy_seats_available=0,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()
        booker = db_session.query(User).filter_by(email="booker@example.com").first()
        flight_obj = db_session.query(Flight).first()
        db_session.add(Booking(
            user_id=booker.user_id, flight_id=flight_obj.flight_id,
            status="booked", booking_time="2099-01-01 10:00",
            seat_class="economy", price_paid=1000000
        ))
        db_session.commit()
        entries = []
        for i in range(waiters):
            u = db_session.query(User).filter_by(email=f"waiter{i + 1}@example.com").first()
            entries.append(waitlist.join_waitlist(db_session, u.user_id, u.name, flight_obj.flight_id, "economy"))
        booking_obj = db_session.query(Booking).filter_by(user_id=booker.user_id).first()
        return flight_obj, booking_obj, entries

    def _entry(self, db_session, waitlist_id):
        return db_session.query(WaitlistEntry).filter_by(waitlist_id=waitlist_id).first()

    def test_accept_offer_creates_booking(self, db_session):
        """Accepting an offer books the held seat at the locked price."""
        flight_obj, booking_obj, (first, _) = self._setup(db_session)
        booking.cancel_booking(db_session, booking_obj.booking_id)

        result = waitlist.accept_offer(db_session, first.waitlist_id, first.user_id)

        assert not isinstance(result, ErrorResponse)
        assert result.status == "booked"
        assert result.price_paid == first.locked_price
        assert self._entry(db_session, first.waitlist_id).status == "promoted"
        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 0
        types = [n.type for n in db_session.query(Notification).filter_by(user_id=first.user_id)]
        assert types == ["waitlist_offer", "waitlist_confirmed"]

    def test_decline_offer_passes_seat_to_next(self, db_session):
        """Declining an offer moves the offer to the next person in the queue."""
        flight_obj, booking_obj, (first, second) = self._setup(db_session)
        booking.cancel_booking(db_session, booking_obj.booking_id)

        result = waitlist.decline_offer(db_session, first.waitlist_id, first.user_id)

        assert not isinstance(result, ErrorResponse)
        assert result.status.value == "declined"
        assert self._entry(db_session, second.waitlist_id).status == "offered"
        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 0

    def test_decline_offer_with_nobody_waiting_releases_seat(self, db_session):
        """Declining the last offer puts the seat back on sale."""
        flight_obj, booking_obj, (first,) = self._setup(db_session, waiters=1)
        booking.cancel_booking(db_session, booking_obj.booking_id)

        waitlist.decline_offer(db_session, first.waitlist_id, first.user_id)

        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 1

    def test_leave_waitlist_moves_queue_up(self, db_session):
        """Leaving while waiting moves everyone behind up one place."""
        _, _, (first, second) = self._setup(db_session)

        result = waitlist.leave_waitlist(db_session, first.waitlist_id, first.user_id)

        assert result.status.value == "left"
        assert self._entry(db_session, second.waitlist_id).position == 1

    def test_leave_while_offered_passes_seat_to_next(self, db_session):
        """Leaving while holding an offer passes the seat on."""
        _, booking_obj, (first, second) = self._setup(db_session)
        booking.cancel_booking(db_session, booking_obj.booking_id)

        waitlist.leave_waitlist(db_session, first.waitlist_id, first.user_id)

        assert self._entry(db_session, second.waitlist_id).status == "offered"

    def test_accept_without_offer_fails(self, db_session):
        """Accept is refused while the entry is still waiting."""
        _, _, (first, _) = self._setup(db_session)
        result = waitlist.accept_offer(db_session, first.waitlist_id, first.user_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "INVALID_WAITLIST_STATUS"

    def _expire(self, db_session, waitlist_id):
        """Move an offer's deadline into the past."""
        entry = self._entry(db_session, waitlist_id)
        entry.offer_expires_at = "2000-01-01T00:00:00+00:00"
        db_session.commit()

    def test_offer_has_15_minute_deadline(self, db_session):
        """An offer gets a deadline 15 minutes from now."""
        from datetime import datetime, timedelta, timezone
        _, booking_obj, (first, _) = self._setup(db_session)
        booking.cancel_booking(db_session, booking_obj.booking_id)

        deadline = datetime.fromisoformat(self._entry(db_session, first.waitlist_id).offer_expires_at)
        expected = datetime.now(tz=timezone.utc) + timedelta(minutes=waitlist.OFFER_MINUTES)
        assert abs((deadline - expected).total_seconds()) < 5

    def test_expired_offer_passes_seat_to_next(self, db_session):
        """An offer past its deadline expires and the next person gets the seat."""
        flight_obj, booking_obj, (first, second) = self._setup(db_session)
        booking.cancel_booking(db_session, booking_obj.booking_id)
        self._expire(db_session, first.waitlist_id)

        assert waitlist.expire_stale_offers(db_session) == 1

        assert self._entry(db_session, first.waitlist_id).status == "expired"
        assert self._entry(db_session, second.waitlist_id).status == "offered"
        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 0
        types = [n.type for n in db_session.query(Notification).filter_by(user_id=first.user_id)]
        assert types == ["waitlist_offer", "waitlist_expired"]

    def test_expired_offer_with_nobody_waiting_releases_seat(self, db_session):
        """The last expired offer puts the seat back on sale."""
        flight_obj, booking_obj, (first,) = self._setup(db_session, waiters=1)
        booking.cancel_booking(db_session, booking_obj.booking_id)
        self._expire(db_session, first.waitlist_id)

        waitlist.expire_stale_offers(db_session)

        db_session.refresh(flight_obj)
        assert flight_obj.economy_seats_available == 1

    def test_offer_within_deadline_is_kept(self, db_session):
        """An offer still inside its 15 minutes is not expired."""
        _, booking_obj, (first, _) = self._setup(db_session)
        booking.cancel_booking(db_session, booking_obj.booking_id)

        assert waitlist.expire_stale_offers(db_session) == 0
        assert self._entry(db_session, first.waitlist_id).status == "offered"

    def test_accept_after_deadline_fails(self, db_session):
        """Accepting an expired offer is refused and creates no booking."""
        _, booking_obj, (first, _) = self._setup(db_session)
        booking.cancel_booking(db_session, booking_obj.booking_id)
        self._expire(db_session, first.waitlist_id)

        result = waitlist.accept_offer(db_session, first.waitlist_id, first.user_id)

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "OFFER_EXPIRED"
        assert db_session.query(Booking).filter_by(user_id=first.user_id).first() is None

    def test_action_on_other_users_entry_fails(self, db_session):
        """A user cannot act on someone else's waitlist entry."""
        _, _, (first, second) = self._setup(db_session)
        result = waitlist.leave_waitlist(db_session, first.waitlist_id, second.user_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NOT_OWNER"


class TestFlightFiltering:
    """Test flight filtering and sorting functionality."""

    def setup_method(self):
        """Setup test flights with various attributes."""

    def test_filter_by_origin(self, db_session):
        """Test filtering flights by origin (case-insensitive partial match)."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Moon",
                destination="Mars",
                departure_time="2026-03-02 10:00",
                arrival_time="2026-03-02 18:00",
                base_price=800000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Venus",
                destination="Earth",
                departure_time="2026-03-03 11:00",
                arrival_time="2026-03-03 19:00",
                base_price=1200000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        # Test exact match
        results = flight.list_flights(db_session, origin="Earth")
        assert len(results) == 1
        assert results[0].origin == "Earth"

        # Test case-insensitive
        results = flight.list_flights(db_session, origin="earth")
        assert len(results) == 1
        assert results[0].origin == "Earth"

        # Test partial match
        results = flight.list_flights(db_session, origin="ar")
        assert len(results) == 1
        assert "ar" in results[0].origin.lower()

    def test_filter_by_destination(self, db_session):
        """Test filtering flights by destination."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Venus",
                departure_time="2026-03-02 10:00",
                arrival_time="2026-03-02 18:00",
                base_price=1100000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        results = flight.list_flights(db_session, destination="Mars")
        assert len(results) == 1
        assert results[0].destination == "Mars"

    def test_filter_by_date_range(self, db_session):
        """Test filtering flights by departure date range."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Venus",
                departure_time="2026-03-15 10:00",
                arrival_time="2026-03-15 18:00",
                base_price=1100000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Jupiter",
                departure_time="2026-04-01 11:00",
                arrival_time="2026-04-01 19:00",
                base_price=2000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        # Test from date
        results = flight.list_flights(db_session, departure_date_from="2026-03-15")
        assert len(results) == 2
        assert all(r.departure_time >= "2026-03-15" for r in results)

        # Test to date
        results = flight.list_flights(db_session, departure_date_to="2026-03-15")
        assert len(results) == 2
        assert all(r.departure_time <= "2026-03-15 23:59" for r in results)

        # Test date range
        results = flight.list_flights(
            db_session,
            departure_date_from="2026-03-10",
            departure_date_to="2026-03-20"
        )
        assert len(results) == 1
        assert results[0].departure_time.startswith("2026-03-15")

    def test_filter_by_price_range(self, db_session):
        """Test filtering flights by price range."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Moon",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",
                base_price=500000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-02 10:00",
                arrival_time="2026-03-02 18:00",
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Jupiter",
                departure_time="2026-03-03 11:00",
                arrival_time="2026-03-03 19:00",
                base_price=2000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        # Test min price
        results = flight.list_flights(db_session, min_price=1000000)
        assert len(results) == 2
        assert all(r.base_price >= 1000000 for r in results)

        # Test max price
        results = flight.list_flights(db_session, max_price=1000000)
        assert len(results) == 2
        assert all(r.base_price <= 1000000 for r in results)

        # Test price range
        results = flight.list_flights(db_session, min_price=800000, max_price=1500000)
        assert len(results) == 1
        assert results[0].base_price == 1000000

    def test_filter_by_seat_availability(self, db_session):
        """Test filtering flights by seat class availability."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",
                base_price=1000000,
                economy_seats_available=5,
                business_seats_available=0,
                galaxium_seats_available=0
            ),
            Flight(
                origin="Earth",
                destination="Venus",
                departure_time="2026-03-02 10:00",
                arrival_time="2026-03-02 18:00",
                base_price=1100000,
                economy_seats_available=0,
                business_seats_available=3,
                galaxium_seats_available=0
            ),
            Flight(
                origin="Earth",
                destination="Jupiter",
                departure_time="2026-03-03 11:00",
                arrival_time="2026-03-03 19:00",
                base_price=2000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        # Test economy seats
        results = flight.list_flights(db_session, has_economy=True)
        assert len(results) == 2
        assert all(r.economy_seats_available > 0 for r in results)

        # Test business seats
        results = flight.list_flights(db_session, has_business=True)
        assert len(results) == 2
        assert all(r.business_seats_available > 0 for r in results)

        # Test galaxium seats
        results = flight.list_flights(db_session, has_galaxium=True)
        assert len(results) == 1
        assert all(r.galaxium_seats_available > 0 for r in results)

        # Test multiple seat classes
        results = flight.list_flights(db_session, has_economy=True, has_business=True)
        assert len(results) == 1
        assert results[0].economy_seats_available > 0
        assert results[0].business_seats_available > 0

    def test_sort_by_price(self, db_session):
        """Test sorting flights by price."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Moon",
                departure_time="2026-03-02 10:00",
                arrival_time="2026-03-02 18:00",
                base_price=500000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Jupiter",
                departure_time="2026-03-03 11:00",
                arrival_time="2026-03-03 19:00",
                base_price=2000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        # Test ascending
        results = flight.list_flights(db_session, sort="price", order="asc")
        prices = [r.base_price for r in results]
        assert prices == sorted(prices)
        assert prices[0] == 500000

        # Test descending
        results = flight.list_flights(db_session, sort="price", order="desc")
        prices = [r.base_price for r in results]
        assert prices == sorted(prices, reverse=True)
        assert prices[0] == 2000000

    def test_sort_by_departure_time(self, db_session):
        """Test sorting flights by departure time."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-15 09:00",
                arrival_time="2026-03-15 17:00",
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Venus",
                departure_time="2026-03-01 10:00",
                arrival_time="2026-03-01 18:00",
                base_price=1100000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Jupiter",
                departure_time="2026-03-30 11:00",
                arrival_time="2026-03-30 19:00",
                base_price=2000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        # Test ascending
        results = flight.list_flights(db_session, sort="departure_time", order="asc")
        times = [r.departure_time for r in results]
        assert times == sorted(times)

        # Test descending
        results = flight.list_flights(db_session, sort="departure_time", order="desc")
        times = [r.departure_time for r in results]
        assert times == sorted(times, reverse=True)

    def test_sort_by_duration(self, db_session):
        """Test sorting flights by duration."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",  # 8 hours
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Moon",
                departure_time="2026-03-02 10:00",
                arrival_time="2026-03-02 14:00",  # 4 hours
                base_price=500000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Jupiter",
                departure_time="2026-03-03 11:00",
                arrival_time="2026-03-04 11:00",  # 24 hours
                base_price=2000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        # Test ascending
        results = flight.list_flights(db_session, sort="duration", order="asc")
        assert results[0].destination == "Moon"  # Shortest
        assert results[2].destination == "Jupiter"  # Longest

        # Test descending
        results = flight.list_flights(db_session, sort="duration", order="desc")
        assert results[0].destination == "Jupiter"  # Longest
        assert results[2].destination == "Moon"  # Shortest

    def test_combined_filters(self, db_session):
        """Test combining multiple filters."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Earth",
                destination="Venus",
                departure_time="2026-03-15 10:00",
                arrival_time="2026-03-15 18:00",
                base_price=1100000,
                economy_seats_available=6,
                business_seats_available=0,
                galaxium_seats_available=0
            ),
            Flight(
                origin="Moon",
                destination="Mars",
                departure_time="2026-03-20 11:00",
                arrival_time="2026-03-20 19:00",
                base_price=800000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        # Combine origin, destination, date range, and seat availability
        results = flight.list_flights(
            db_session,
            origin="Earth",
            destination="Mars",
            departure_date_from="2026-03-01",
            departure_date_to="2026-03-10",
            has_business=True
        )
        assert len(results) == 1
        assert results[0].origin == "Earth"
        assert results[0].destination == "Mars"
        assert results[0].business_seats_available > 0

    def test_no_filters_returns_all(self, db_session):
        """Test that no filters returns all flights."""
        db_session.add_all([
            Flight(
                origin="Earth",
                destination="Mars",
                departure_time="2026-03-01 09:00",
                arrival_time="2026-03-01 17:00",
                base_price=1000000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            ),
            Flight(
                origin="Moon",
                destination="Venus",
                departure_time="2026-03-02 10:00",
                arrival_time="2026-03-02 18:00",
                base_price=1100000,
                economy_seats_available=6,
                business_seats_available=3,
                galaxium_seats_available=1
            )
        ])
        db_session.commit()

        results = flight.list_flights(db_session)
        assert len(results) == 2

    def test_filters_return_empty_when_no_match(self, db_session):
        """Test that filters return empty list when no flights match."""
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2026-03-01 09:00",
            arrival_time="2026-03-01 17:00",
            base_price=1000000,
            economy_seats_available=6,
            business_seats_available=3,
            galaxium_seats_available=1
        ))
        db_session.commit()

        results = flight.list_flights(db_session, origin="Pluto")
        assert len(results) == 0

        results = flight.list_flights(db_session, min_price=10000000)
        assert len(results) == 0
