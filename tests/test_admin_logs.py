import os

from firenze.admin import register_admin
from firenze.admin_logs import FirenzeApiLogViewer, collect_api_log_data


def test_collect_api_log_data_reads_rotations_and_multiline(monkeypatch, tmp_path):
    monkeypatch.setattr("firenze.admin_logs.LOGS_DIR", tmp_path)

    current_log = tmp_path / "firenze-api.log"
    rotated_log = tmp_path / "firenze-api.log.2026-05-25"

    current_log.write_text(
        "2026-05-26 10:00:00,000 firenze.WARNING client_service.py(83) deduct_credits called with no balance\n",
        encoding="utf-8",
    )
    rotated_log.write_text(
        "\n".join(
            [
                "2026-05-25 09:00:00,000 firenze.INFO payment_service.py(158) apply_purchase: ok",
                "2026-05-25 09:10:00,000 firenze.ERROR payment_service.py(166) apply_purchase failed",
                "Traceback (most recent call last):",
                '  File "payment_service.py", line 166, in apply_purchase',
                "ValueError: boom",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    os.utime(current_log, (2_000_000_000, 2_000_000_000))
    os.utime(rotated_log, (1_900_000_000, 1_900_000_000))

    data = collect_api_log_data(level="ALL", limit=10)

    assert data["selected_files"] == ["firenze-api.log", "firenze-api.log.2026-05-25"]
    assert data["total_records"] == 3
    assert [entry["level"] for entry in data["entries"]] == ["WARNING", "ERROR", "INFO"]
    assert "Traceback (most recent call last):" in data["entries"][1]["raw"]

    filtered = collect_api_log_data(
        selected_files=["firenze-api.log.2026-05-25"],
        level="ERROR",
        query="boom",
        limit=10,
    )

    assert filtered["total_records"] == 1
    assert filtered["entries"][0]["file_name"] == "firenze-api.log.2026-05-25"
    assert filtered["entries"][0]["level"] == "ERROR"


def test_register_admin_includes_log_view():
    added_views = []

    class FakeAdmin:
        def add_view(self, view):
            added_views.append(view)

    register_admin(FakeAdmin())

    assert FirenzeApiLogViewer in added_views
