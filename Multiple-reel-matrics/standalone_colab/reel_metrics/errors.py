"""Map instagrapi exceptions to human-readable messages."""

from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    ClientError,
    LoginRequired,
    PleaseWaitFewMinutes,
    PrivateAccount,
    TwoFactorRequired,
    UserNotFound,
)


def error_message_from_exception(e: Exception, what: str = "Reel") -> str:
    """Human-readable error string for scraping failures."""
    if isinstance(e, UserNotFound):
        return f"{what} not found."
    if isinstance(e, PrivateAccount):
        return f"{what} is private and the logged-in account does not follow it."
    if isinstance(e, BadPassword):
        return "Bad password."
    if isinstance(e, TwoFactorRequired):
        return "Two-factor authentication required."
    if isinstance(e, ChallengeRequired):
        return "Instagram security challenge required — confirm in the app, then retry."
    if isinstance(e, LoginRequired):
        return "Login required (session expired). Provide your password."
    if isinstance(e, PleaseWaitFewMinutes):
        return "Instagram rate-limited this account. Wait a few minutes."
    if isinstance(e, ClientError):
        return f"Instagram refused the request: {e}"
    return f"{type(e).__name__}: {e}"
