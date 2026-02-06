"""Tests for Gemini rate limiting utilities."""

from services.gemini import RateLimiter


def test_rate_limiter_sleeps_after_limit(monkeypatch):
    """Exceeding the call limit should trigger a sleep."""
    limiter = RateLimiter(max_calls=2, period=10.0)
    sleep_calls = []

    def fake_time():
        return 1000.0

    def fake_sleep(duration):
        sleep_calls.append(duration)

    monkeypatch.setattr("services.gemini.time.time", fake_time)
    monkeypatch.setattr("services.gemini.time.sleep", fake_sleep)

    limiter.wait_if_needed()
    limiter.wait_if_needed()
    limiter.wait_if_needed()

    assert sleep_calls == [10.0]
