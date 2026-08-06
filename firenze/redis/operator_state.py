import json

def set_state(redis_conn, number, **kwargs):
    if not redis_conn: return
    key = f"operator:{number}:state"
    current = get_state(redis_conn, number) or {}
    current.update(kwargs)
    redis_conn.set(key, json.dumps(current))

def get_state(redis_conn, number):
    if not redis_conn: return None
    key = f"operator:{number}:state"
    data = redis_conn.get(key)
    if data:
        return json.loads(data)
    return None
