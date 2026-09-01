import time

from app import SESSION_TIMEOUT_SECONDS, clear_session_payload, is_session_valid, make_session_payload


def test_session_is_valid_within_timeout():
    payload = make_session_payload("Payel", now=time.time())
    assert payload["logged_in"] is True
    assert payload["username"] == "Payel"
    assert payload["expires_at"] > time.time()
    assert is_session_valid(payload) is True


def test_session_is_invalid_after_timeout():
    payload = {
        "logged_in": True,
        "username": "Payel",
        "expires_at": time.time() - 1,
    }
    assert is_session_valid(payload) is False


def test_clear_session_payload_resets_values():
    payload = clear_session_payload()
    assert payload == {"logged_in": False, "username": "", "expires_at": 0}
    assert is_session_valid(payload) is False


def test_session_timeout_matches_requirement():
    assert SESSION_TIMEOUT_SECONDS == 30 * 60
