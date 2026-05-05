"""Credit balance and call limit calculations.

Logic mirrors the [limite-saldo] dialplan gosub in extensions_fonotarot.conf.
Each entry is (threshold_seconds, audio_file). The rule is: find the smallest
threshold T where seconds <= T (ceiling to nearest bucket).
"""

# Derived directly from extensions_fonotarot.conf [limite-saldo].
# Note: 4800 maps to zvn/saldo/75 (same as 4500) — intentional replication of original dialplan.
_THRESHOLDS = [
    (60, "zvn/saldo/1"),
    (120, "zvn/saldo/2"),
    (180, "zvn/saldo/3"),
    (240, "zvn/saldo/4"),
    (300, "zvn/saldo/5"),
    (360, "zvn/saldo/6"),
    (420, "zvn/saldo/7"),
    (480, "zvn/saldo/8"),
    (540, "zvn/saldo/9"),
    (600, "zvn/saldo/10"),
    (660, "zvn/saldo/11"),
    (720, "zvn/saldo/12"),
    (780, "zvn/saldo/13"),
    (840, "zvn/saldo/14"),
    (900, "zvn/saldo/15"),
    (1080, "zvn/saldo/18"),
    (1200, "zvn/saldo/20"),
    (1500, "zvn/saldo/25"),
    (1800, "zvn/saldo/30"),
    (2100, "zvn/saldo/35"),
    (2400, "zvn/saldo/40"),
    (2700, "zvn/saldo/45"),
    (3000, "zvn/saldo/50"),
    (3300, "zvn/saldo/55"),
    (3600, "zvn/saldo/60"),
    (3900, "zvn/saldo/65"),
    (4200, "zvn/saldo/70"),
    (4500, "zvn/saldo/75"),
    (4800, "zvn/saldo/75"),  # dialplan plays /75 here too (bug in original, replicated)
    (5100, "zvn/saldo/85"),
    (5400, "zvn/saldo/90"),
    (5700, "zvn/saldo/95"),
    (6000, "zvn/saldo/100"),
    (6300, "zvn/saldo/105"),
    (6600, "zvn/saldo/110"),
    (7200, "zvn/saldo/120"),
]


def compute_call_limit(seconds: int) -> dict:
    """Return timeout, audio, and minutes for a given credit balance in seconds.

    Replicates [limite-saldo] in extensions_fonotarot.conf:
    - <= 0: immediate hangup (timeout=1)
    - <= each threshold: use that threshold (first bucket the balance fits into)
    - > 7200: cap at 7200s, play zvn/saldo/121
    """
    if seconds <= 0:
        return {"timeout": 1, "audio": "", "minutes": 0}

    for threshold, audio in _THRESHOLDS:
        if seconds <= threshold:
            return {"timeout": threshold, "audio": audio, "minutes": threshold // 60}

    # seconds > 7200
    return {"timeout": 7200, "audio": "zvn/saldo/121", "minutes": 121}
