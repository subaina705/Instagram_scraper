"""Instagram session management with disk persistence."""

import os
import threading
from typing import Optional

from instagrapi import Client

_clients: dict[str, Client] = {}
_clients_lock = threading.Lock()


def default_session_dir() -> str:
    """Directory for cached instagrapi session files."""
    base = os.environ.get("IG_SESSION_DIR")
    if base:
        return base
    return os.path.join(os.getcwd(), ".ig_sessions")


def session_path(username: str, session_dir: Optional[str] = None) -> str:
    """Path to the saved session file for ``username``."""
    directory = session_dir or default_session_dir()
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, f"instagrapi-{username}.json")


def new_client() -> Client:
    """Create a fresh instagrapi Client with sensible defaults."""
    cl = Client()
    cl.delay_range = [1, 3]
    return cl


def get_client(
    username: str,
    password: Optional[str] = None,
    session_dir: Optional[str] = None,
) -> Client:
    """
    Return a logged-in Client for ``username``.

    Reuses in-memory cache, then disk session, then password login.
    """
    with _clients_lock:
        cached = _clients.get(username)
        if cached is not None:
            return cached

        sess_file = session_path(username, session_dir)
        cl = new_client()

        if os.path.exists(sess_file):
            try:
                cl.load_settings(sess_file)
                cl.get_timeline_feed()
                _clients[username] = cl
                return cl
            except Exception:
                cl = new_client()
                try:
                    cl.load_settings(sess_file)
                except Exception:
                    pass

        if not password:
            raise RuntimeError(
                "No valid cached session for this username. Provide a password to log in."
            )

        cl.login(username, password)
        try:
            cl.dump_settings(sess_file)
        except Exception:
            pass

        _clients[username] = cl
        return cl
