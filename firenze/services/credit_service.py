"""Credit balance and call limit calculations."""

# Sorted thresholds in seconds. Each maps to an audio file zvn/saldo/{minutes}.
# Derived from the legacy limite-saldo dialplan ladder.
_THRESHOLDS = [
    60, 120, 180, 240, 300, 360, 420, 480, 540, 600,
    660, 720, 780, 840, 900,
    1080, 1200, 1500, 1800, 2100, 2400, 2700,
    3000, 3300, 3600, 3900, 4200, 4500, 4800,
    5100, 5400, 5700, 6000, 6300, 6600, 7200,
]

_MAX_TIMEOUT = 7200  # 2 hours hard cap


def compute_call_limit(seconds: int) -> dict:
    """Given a credit balance in seconds, return the call timeout and audio file.

    Returns a dict with:
        timeout: int  — TIMEOUT(absolute) value for the dialplan
        audio: str    — Playback file path (e.g. "zvn/saldo/30")
        minutes: int  — human-readable minutes for the audio announcement
    """
    if seconds <= 0:
        return {"timeout": 1, "audio": "", "minutes": 0}

    # Find the highest threshold that doesn't exceed the balance
    chosen = _THRESHOLDS[0]
    for threshold in _THRESHOLDS:
        if seconds >= threshold:
            chosen = threshold
        else:
            break

    # Cap at max
    timeout = min(chosen, _MAX_TIMEOUT)
    minutes = timeout // 60

    # Over 2 hours: cap at 7200 but play the "more than 120 minutes" audio
    if seconds > _MAX_TIMEOUT:
        return {"timeout": _MAX_TIMEOUT, "audio": "zvn/saldo/121", "minutes": 121}

    return {"timeout": timeout, "audio": f"zvn/saldo/{minutes}", "minutes": minutes}
