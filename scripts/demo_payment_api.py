"""Hardcoded smoke test for the payment API.

Walks through the full storefront -> Firenze contract end to end against a
running Firenze instance, using fixed sample data. No assertions - it prints
each request/response so you can read what happened.

Run:
    python scripts/demo_payment_api.py

Override target / service via environment:
    FIRENZE_API_BASE=http://localhost:9002 \\
    FIRENZE_DEMO_SERVICE=fonotarot-cl \\
    python scripts/demo_payment_api.py

Steps:
    1. search by email   -> expect NOT FOUND on a fresh run
    2. POST purchase     -> creates a new client, returns its client_id
    3. search by email   -> expect FOUND, returns the same client_id
    4. POST purchase     -> top-up using the returned client_id
    5. PATCH client      -> set full_name, add a phone
    6. PATCH client      -> sentinel '::EMPTY::' to erase all phones
    7. final search      -> show end state
"""

import json
import os
import sys
import time

import requests

API_BASE = os.environ.get("FIRENZE_API_BASE", "http://localhost:9002")
SERVICE = os.environ.get("FIRENZE_DEMO_SERVICE", "fonotarot-cl")

# A unique-ish email so re-runs do not collide with prior demo state.
RUN_TAG = int(time.time())
DEMO_EMAIL = f"demo+{RUN_TAG}@example.com"
DEMO_NAME = "Demo Buyer"
DEMO_PHONE = f"56900{RUN_TAG % 1000000:06d}"
DEMO_PHONE_2 = f"56911{RUN_TAG % 1000000:06d}"
INITIAL_CREDITS = 600
TOPUP_CREDITS = 1800


def _show(label: str, resp: requests.Response) -> dict:
    print(f"\n--- {label} ---")
    print(f"  {resp.request.method} {resp.request.url}")
    if resp.request.body:
        body = resp.request.body
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
        print(f"  body: {body}")
    print(f"  -> {resp.status_code}")
    try:
        data = resp.json()
        print(f"  json: {json.dumps(data, indent=2, ensure_ascii=False)}")
        return data
    except ValueError:
        print(f"  text: {resp.text}")
        return {}


def run_demo() -> None:
    print(f"target : {API_BASE}")
    print(f"service: {SERVICE}")
    print(f"email  : {DEMO_EMAIL}")
    print(f"phones : {DEMO_PHONE}, {DEMO_PHONE_2}")

    # 1. search before purchase - expect NOT FOUND
    resp = requests.get(
        f"{API_BASE}/api/v1/clients/search",
        params={"service": SERVICE, "email": DEMO_EMAIL},
        timeout=10,
    )
    pre = _show("1. search (pre-purchase)", resp)
    if pre.get("found"):
        print("  WARNING: client already exists - the rest of the run will top up an existing record")

    # 2. purchase that creates a new client
    resp = requests.post(
        f"{API_BASE}/api/v1/payments/complete",
        json={
            "service": SERVICE,
            "credits": INITIAL_CREDITS,
            "email": DEMO_EMAIL,
            "full_name": DEMO_NAME,
            "phone_number": DEMO_PHONE,
            "ani": DEMO_PHONE,
            "transaction_id": f"demo-create-{RUN_TAG}",
        },
        timeout=10,
    )
    purchase1 = _show("2. payments/complete (create)", resp)
    if not purchase1.get("ok"):
        print("  aborting - first purchase did not succeed")
        return
    client_id = purchase1["client_id"]

    # 3. search after purchase - expect FOUND with the same client_id
    resp = requests.get(
        f"{API_BASE}/api/v1/clients/search",
        params={"service": SERVICE, "email": DEMO_EMAIL},
        timeout=10,
    )
    post = _show("3. search (post-purchase)", resp)
    if post.get("client_id") != client_id:
        print(f"  WARNING: search returned client_id={post.get('client_id')} but purchase returned {client_id}")

    # 4. top-up the existing client by client_id
    resp = requests.post(
        f"{API_BASE}/api/v1/payments/complete",
        json={
            "service": SERVICE,
            "client_id": client_id,
            "credits": TOPUP_CREDITS,
            "transaction_id": f"demo-topup-{RUN_TAG}",
        },
        timeout=10,
    )
    _show("4. payments/complete (top-up)", resp)

    # 5. PATCH: set full_name + add a second phone
    resp = requests.patch(
        f"{API_BASE}/api/v1/clients/{SERVICE}/{client_id}",
        json={
            "full_name": "Demo Buyer (renamed)",
            "phone": DEMO_PHONE_2,
        },
        timeout=10,
    )
    _show("5. PATCH client (rename + add phone)", resp)

    # 6. PATCH: sentinel to erase all phones
    resp = requests.patch(
        f"{API_BASE}/api/v1/clients/{SERVICE}/{client_id}",
        json={"phone": "::EMPTY::"},
        timeout=10,
    )
    _show("6. PATCH client (erase phones)", resp)

    # 7. final search to show end state
    resp = requests.get(
        f"{API_BASE}/api/v1/clients/search",
        params={"service": SERVICE, "email": DEMO_EMAIL},
        timeout=10,
    )
    _show("7. search (final)", resp)


if __name__ == "__main__":
    try:
        run_demo()
    except requests.RequestException as e:
        print(f"\nrequest error: {e}", file=sys.stderr)
        sys.exit(1)
