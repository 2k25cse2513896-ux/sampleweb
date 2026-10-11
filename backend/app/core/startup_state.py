"""Small process-local state used by health and readiness probes."""

from threading import Lock
from typing import Dict

_lock = Lock()
_state: Dict[str, str] = {"status": "starting", "message": "Starting application."}


def set_startup_state(status: str, message: str) -> None:
    """Update readiness state without exposing secrets or connection details."""
    with _lock:
        _state["status"] = status
        _state["message"] = message


def get_startup_state() -> Dict[str, str]:
    """Return a copy so callers cannot mutate shared state."""
    with _lock:
        return dict(_state)
