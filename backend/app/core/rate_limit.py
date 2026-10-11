"""Shared SlowAPI limiter. Login and OTP routes import this instance."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
