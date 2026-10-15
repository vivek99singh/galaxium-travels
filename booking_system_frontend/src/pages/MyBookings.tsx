import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Booking, Flight, StoredHold, ErrorResponse, WaitlistEntry, AppNotification } from '../types';
import { LoadingSpinner, Modal, Button } from '../components/common';
import { BookingCard } from '../components/bookings/BookingCard';
import { HoldCard } from '../components/bookings/HoldCard';
import {
  getUserBookings,
  getFlights,
  cancelBooking,
  getHold,
  isErrorResponse,
  getUserWaitlist,
  getUserNotifications,
  acceptWaitlistOffer,
  declineWaitlistOffer,
  leaveWaitlist,
} from '../services/api';
import { getStoredHolds, removeHold } from '../utils/holdStorage';
import { useUser } from '../hooks/useUserContext';
import { AlertCircle, Bell, Clock, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';
import { formatCurrency, getRelativeTime } from '../utils/formatters';

const offerTimeLeft = (entry: WaitlistEntry, now: number): number => {
  if (!entry.offer_expires_at) return 0;
  const remaining = new Date(entry.offer_expires_at).getTime() - now;
  return isNaN(remaining) ? 0 : Math.max(0, remaining);
};

const formatTimer = (ms: number): string => {
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
};

export const MyBookings = () => {
  const { user } = useUser();
  const navigate = useNavigate();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [flights, setFlights] = useState<Flight[]>([]);
  const [activeHolds, setActiveHolds] = useState<StoredHold[]>([]);
  const [waitlistEntries, setWaitlistEntries] = useState<WaitlistEntry[]>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [busyWaitlistId, setBusyWaitlistId] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const expiryReloadPending = useRef(false);
  const [isLoading, setIsLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [bookingToCancel, setBookingToCancel] = useState<number | null>(null);

  const loadHolds = useCallback(async () => {
    if (!user) return;

    const stored = getStoredHolds(user.user_id);
    if (stored.length === 0) {
      setActiveHolds([]);
      return;
    }

    // Verify each hold's current status from the API, remove stale ones
    const stillActive: StoredHold[] = [];
    const isLocallyExpired = (sh: StoredHold) => {
      const expiryTime = new Date(sh.reservedUntil).getTime();
      return isNaN(expiryTime) || expiryTime < Date.now();
    };
    await Promise.all(
      stored.map(async (sh) => {
        try {
          const hold = await getHold(sh.holdId);
          if (hold.status === 'HELD' && !isLocallyExpired(sh)) {
            stillActive.push(sh);
          } else {
            // Hold is no longer active (confirmed, released, expired, or locally timed out)
            removeHold(user.user_id, sh.holdId);
          }
        } catch {
          // API unavailable — fall back to local expiry check
          if (!isLocallyExpired(sh)) {
            stillActive.push(sh);
          } else {
            removeHold(user.user_id, sh.holdId);
          }
        }
      })
    );

    setActiveHolds(stillActive);
  }, [user]);

  const loadData = useCallback(async () => {
    if (!user) return;

    setIsLoading(true);
    try {
      const [bookingsData, flightsData, waitlistData, notificationsData] = await Promise.all([
        getUserBookings(user.user_id),
        getFlights(),
        getUserWaitlist(user.user_id),
        getUserNotifications(user.user_id),
      ]);
      setBookings(bookingsData);
      setFlights(flightsData);
      setWaitlistEntries(waitlistData);
      setNotifications(notificationsData);
      await loadHolds();
    } catch (err) {
      toast.error('Failed to load bookings');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [user, loadHolds]);

  useEffect(() => {
    if (!user) {
      navigate('/flights');
      return;
    }
    loadData();
  }, [user, navigate, loadData]);

  // Tick once a second while an offer is open, and reload when one runs out
  // so the server can pass the seat to the next person
  const hasOpenOffer = waitlistEntries.some((w) => w.status === 'offered');
  useEffect(() => {
    if (!hasOpenOffer) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [hasOpenOffer]);

  useEffect(() => {
    const anyRunOut = waitlistEntries.some(
      (w) => w.status === 'offered' && offerTimeLeft(w, now) === 0
    );
    if (anyRunOut && !expiryReloadPending.current) {
      expiryReloadPending.current = true;
      toast.error('A waitlist offer expired');
      loadData().finally(() => {
        expiryReloadPending.current = false;
      });
    }
  }, [now, waitlistEntries, loadData]);

  const handleCancelClick = (bookingId: number) => {
    setBookingToCancel(bookingId);
    setShowCancelModal(true);
  };

  const handleConfirmCancel = async () => {
    if (!bookingToCancel) return;

    setCancellingId(bookingToCancel);
    setShowCancelModal(false);

    try {
      const result = await cancelBooking(bookingToCancel);

      if (isErrorResponse(result)) {
        toast.error(result.details || result.error);
        return;
      }

      toast.success('Booking cancelled successfully');
      loadData();
    } catch (err) {
      const error = err as ErrorResponse;
      toast.error(error.details || error.error || 'Failed to cancel booking');
    } finally {
      setCancellingId(null);
      setBookingToCancel(null);
    }
  };

  const handleWaitlistAction = async (
    entry: WaitlistEntry,
    action: 'accept' | 'decline' | 'leave'
  ) => {
    if (!user) return;

    const actions = {
      accept: { call: acceptWaitlistOffer, success: 'Booking confirmed from the waitlist' },
      decline: { call: declineWaitlistOffer, success: 'Offer declined' },
      leave: { call: leaveWaitlist, success: 'You left the waitlist' },
    };

    setBusyWaitlistId(entry.waitlist_id);
    try {
      const result = await actions[action].call(entry.waitlist_id, user.user_id);

      if (isErrorResponse(result)) {
        toast.error(result.details || result.error);
        return;
      }

      toast.success(actions[action].success);
      loadData();
    } catch (err) {
      const error = err as ErrorResponse;
      toast.error(error.details || error.error || 'Waitlist action failed');
    } finally {
      setBusyWaitlistId(null);
    }
  };

  const getFlightForBooking = (booking: Booking): Flight | undefined => {
    return flights.find((f) => f.flight_id === booking.flight_id);
  };

  const getFlightForHold = (hold: StoredHold): Flight | undefined => {
    return flights.find((f) => f.flight_id === hold.flightId);
  };

  const activeBookings = bookings.filter((b) => b.status === 'booked');
  const pastBookings = bookings.filter((b) => b.status !== 'booked');
  // Open offers first, then the entries still waiting in queue order
  const activeWaitlist = waitlistEntries
    .filter((w) => w.status === 'offered' || w.status === 'waiting')
    .sort((a, b) =>
      a.status === b.status ? a.position - b.position : a.status === 'offered' ? -1 : 1
    );
  const recentNotifications = notifications.slice(0, 5);

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center"
      >
        <h1 className="text-4xl md:text-5xl font-bold text-star-white mb-4">
          My <span className="bg-cosmic-gradient bg-clip-text text-transparent">Bookings</span>
        </h1>
        <p className="text-star-white/70 text-lg">
          Manage your space travel reservations
        </p>
      </motion.div>

      {isLoading ? (
        <LoadingSpinner size="lg" text="Loading your bookings..." />
      ) : (
        <div className="space-y-8">
          {/* Notifications */}
          {recentNotifications.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <div className="flex items-center gap-2 mb-4">
                <Bell size={20} className="text-cosmic-purple" />
                <h2 className="text-2xl font-bold text-star-white">Notifications</h2>
              </div>
              <div className="glass-card divide-y divide-white/10">
                {recentNotifications.map((n) => (
                  <div
                    key={n.notification_id}
                    className="flex items-start justify-between gap-4 p-4"
                  >
                    <p
                      className={
                        n.type === 'waitlist_offer'
                          ? 'text-alien-green font-medium'
                          : 'text-star-white/80'
                      }
                    >
                      {n.message}
                    </p>
                    <span className="text-xs text-star-white/50 whitespace-nowrap">
                      {getRelativeTime(n.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Pending Holds */}
          {activeHolds.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
            >
              <div className="flex items-center gap-3 mb-4">
                <h2 className="text-2xl font-bold text-solar-orange">
                  Pending Holds ({activeHolds.length})
                </h2>
                <span className="text-xs text-star-white/50 bg-solar-orange/10 border border-solar-orange/30 px-2 py-1 rounded-full">
                  Confirm before time runs out
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {activeHolds.map((hold) => (
                  <HoldCard
                    key={hold.holdId}
                    storedHold={hold}
                    flight={getFlightForHold(hold)}
                    onAction={loadData}
                  />
                ))}
              </div>
            </motion.div>
          )}

          {/* Waitlist */}
          {activeWaitlist.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 }}
            >
              <div className="flex items-center gap-3 mb-4">
                <h2 className="text-2xl font-bold text-cosmic-purple">
                  Waitlist ({activeWaitlist.length})
                </h2>
                <span className="text-xs text-star-white/50 bg-cosmic-purple/10 border border-cosmic-purple/30 px-2 py-1 rounded-full">
                  You'll be notified when a seat opens
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {activeWaitlist.map((entry) => {
                  const flight = flights.find((f) => f.flight_id === entry.flight_id);
                  const isOffered = entry.status === 'offered';
                  const isBusy = busyWaitlistId === entry.waitlist_id;
                  const timeLeft = isOffered ? offerTimeLeft(entry, now) : 0;
                  const isOfferExpired = isOffered && timeLeft === 0;
                  return (
                    <div
                      key={entry.waitlist_id}
                      className={
                        isOffered
                          ? 'glass-card p-5 border border-alien-green/50 bg-alien-green/5 space-y-3'
                          : 'glass-card p-5 border border-cosmic-purple/30 bg-cosmic-purple/5 space-y-3'
                      }
                    >
                      <div className="flex items-center justify-between">
                        {isOffered ? (
                          <div className="flex items-center gap-2">
                            <Sparkles size={16} className="text-alien-green" />
                            <span className="text-xs font-semibold text-alien-green uppercase tracking-wide">
                              Seat available for you
                            </span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <Clock size={16} className="text-cosmic-purple" />
                            <span className="text-xs font-semibold text-cosmic-purple uppercase tracking-wide">
                              Queue Position #{entry.position}
                            </span>
                          </div>
                        )}
                        <span className="text-xs text-star-white/50 bg-white/5 px-2 py-0.5 rounded-full capitalize">
                          {entry.seat_class}
                        </span>
                      </div>
                      {flight ? (
                        <div>
                          <p className="text-star-white font-semibold">
                            {flight.origin} → {flight.destination}
                          </p>
                          <p className="text-star-white/60 text-sm">
                            {flight.departure_time}
                          </p>
                        </div>
                      ) : (
                        <p className="text-star-white/60 text-sm">Flight #{entry.flight_id}</p>
                      )}
                      <div className="flex items-center justify-between border-t border-white/10 pt-3">
                        <span className="text-xs text-star-white/50">Locked price</span>
                        <span className="text-star-white font-semibold">
                          {formatCurrency(entry.locked_price)}
                        </span>
                      </div>
                      {isOffered && (
                        <div className="flex items-center justify-between border-t border-white/10 pt-3">
                          <span className="text-xs text-star-white/50">
                            {isOfferExpired ? 'Offer expired' : 'Offer expires in'}
                          </span>
                          <span
                            className={`font-mono font-bold ${
                              timeLeft < 60000 ? 'text-red-400' : 'text-alien-green'
                            }`}
                          >
                            {formatTimer(timeLeft)}
                          </span>
                        </div>
                      )}
                      {isOffered ? (
                        <div className="flex gap-3">
                          <Button
                            size="sm"
                            className="flex-1"
                            isLoading={isBusy}
                            disabled={isBusy || isOfferExpired}
                            onClick={() => handleWaitlistAction(entry, 'accept')}
                          >
                            Accept
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            className="flex-1"
                            disabled={isBusy || isOfferExpired}
                            onClick={() => handleWaitlistAction(entry, 'decline')}
                          >
                            Decline
                          </Button>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="secondary"
                          className="w-full"
                          isLoading={isBusy}
                          disabled={isBusy}
                          onClick={() => handleWaitlistAction(entry, 'leave')}
                        >
                          Leave waitlist
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            </motion.div>
          )}

          {/* No content at all */}
          {bookings.length === 0 && activeHolds.length === 0 && activeWaitlist.length === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="glass-card p-12 text-center"
            >
              <AlertCircle className="mx-auto mb-4 text-star-white/50" size={48} />
              <h3 className="text-xl font-semibold text-star-white mb-2">
                No bookings yet
              </h3>
              <p className="text-star-white/70 mb-6">
                Start your space adventure by booking your first flight!
              </p>
              <Button onClick={() => navigate('/flights')}>Browse Flights</Button>
            </motion.div>
          )}

          {/* Active Bookings */}
          {activeBookings.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <h2 className="text-2xl font-bold text-star-white mb-4">
                Active Bookings ({activeBookings.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {activeBookings.map((booking) => (
                  <BookingCard
                    key={booking.booking_id}
                    booking={booking}
                    flight={getFlightForBooking(booking)}
                    onCancel={handleCancelClick}
                    isCancelling={cancellingId === booking.booking_id}
                  />
                ))}
              </div>
            </motion.div>
          )}

          {/* Past Bookings */}
          {pastBookings.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <h2 className="text-2xl font-bold text-star-white mb-4">
                Past Bookings ({pastBookings.length})
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {pastBookings.map((booking) => (
                  <BookingCard
                    key={booking.booking_id}
                    booking={booking}
                    flight={getFlightForBooking(booking)}
                    onCancel={handleCancelClick}
                  />
                ))}
              </div>
            </motion.div>
          )}
        </div>
      )}

      {/* Cancel Confirmation Modal */}
      <Modal
        isOpen={showCancelModal}
        onClose={() => setShowCancelModal(false)}
        title="Cancel Booking"
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-star-white/70">
            Are you sure you want to cancel this booking? This action cannot be undone.
          </p>
          <div className="flex gap-3">
            <Button
              variant="secondary"
              onClick={() => setShowCancelModal(false)}
              className="flex-1"
            >
              Keep Booking
            </Button>
            <Button variant="danger" onClick={handleConfirmCancel} className="flex-1">
              Cancel Booking
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

// Made with Bob
