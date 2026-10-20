"""Append-only from the application; never record secrets or answer payloads."""
import time

def record(conn, actor, action, entity, detail=""):
    conn.execute("INSERT INTO audit(occurred_at,actor_id,actor,action,entity,detail) VALUES(?,?,?,?,?,?)",
                 (int(time.time()), actor.get("id") if actor else None,
                  actor.get("username", "system") if actor else "system",
                  action, str(entity), str(detail)[:500]))
