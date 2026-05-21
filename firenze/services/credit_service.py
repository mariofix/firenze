"""Cálculos de saldo de crédito y límites de llamadas.

La lógica refleja el gosub [limite-saldo] del dialplan en extensions_fonotarot.conf.
Cada entrada es (threshold_seconds, audio_file). La regla es: encontrar el
umbral más pequeño T donde seconds <= T (redondeo al cubo más cercano).
"""

# Derivado directamente de [limite-saldo] en extensions_fonotarot.conf.
# Nota: 4800 mapea a zvn/saldo/75 (igual que 4500) — replicación intencional del dialplan original.
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
    (4800, "zvn/saldo/80"),
    (5100, "zvn/saldo/85"),
    (5400, "zvn/saldo/90"),
    (5700, "zvn/saldo/95"),
    (6000, "zvn/saldo/100"),
    (6300, "zvn/saldo/105"),
    (6600, "zvn/saldo/110"),
    (7200, "zvn/saldo/120"),
]


def compute_call_limit(seconds: int) -> dict:
    """Retorna timeout, audio y minutos para un saldo de crédito dado en segundos.

    Replica [limite-saldo] en extensions_fonotarot.conf:
    - <= 0: cuelgue inmediato (timeout=1)
    - <= cada umbral: usa ese umbral (primer cubo en el que cabe el saldo)
    - > 7200: tapa a 7200s, reproduce zvn/saldo/121
    """
    if seconds <= 0:
        return {"timeout": 1, "audio": "", "minutes": 0}

    for threshold, audio in _THRESHOLDS:
        if seconds <= threshold:
            return {"timeout": threshold, "audio": audio, "minutes": threshold // 60}

    # seconds > 7200
    return {"timeout": 7200, "audio": "zvn/saldo/121", "minutes": 121}
