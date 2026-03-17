"""Tests for firenze.services.credit_service — call limit calculations."""

import pytest

from firenze.services.credit_service import compute_call_limit


class TestComputeCallLimit:
    def test_zero_credits(self):
        result = compute_call_limit(0)
        assert result == {"timeout": 1, "audio": "", "minutes": 0}

    def test_negative_credits(self):
        result = compute_call_limit(-100)
        assert result == {"timeout": 1, "audio": "", "minutes": 0}

    def test_exact_threshold(self):
        result = compute_call_limit(60)
        assert result == {"timeout": 60, "audio": "zvn/saldo/1", "minutes": 1}

    def test_between_thresholds(self):
        # 90 seconds should round up to the 120 bucket
        result = compute_call_limit(90)
        assert result == {"timeout": 120, "audio": "zvn/saldo/2", "minutes": 2}

    def test_one_second(self):
        result = compute_call_limit(1)
        assert result == {"timeout": 60, "audio": "zvn/saldo/1", "minutes": 1}

    def test_max_threshold(self):
        result = compute_call_limit(7200)
        assert result == {"timeout": 7200, "audio": "zvn/saldo/120", "minutes": 120}

    def test_above_max(self):
        result = compute_call_limit(10000)
        assert result == {"timeout": 7200, "audio": "zvn/saldo/121", "minutes": 121}

    def test_30_minutes(self):
        result = compute_call_limit(1800)
        assert result == {"timeout": 1800, "audio": "zvn/saldo/30", "minutes": 30}

    def test_replicated_dialplan_bug_4800(self):
        """4800 maps to /75 (same as 4500) — intentional replication of original dialplan."""
        result = compute_call_limit(4800)
        assert result["audio"] == "zvn/saldo/75"

    @pytest.mark.parametrize("seconds", [60, 120, 300, 600, 900, 1800, 3600, 7200])
    def test_common_thresholds_return_exact(self, seconds):
        result = compute_call_limit(seconds)
        assert result["timeout"] == seconds
