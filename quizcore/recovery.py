"""A restore is guarded, validated and preceded by a preserved rollback copy."""
import sqlite3
from .validation import AppError, require_role
from .audit import record

def restore(backups, actor, data):
    require_role(actor,"admin")
    if data.get("confirmation") != "RESTORE":
        raise AppError("Type RESTORE to confirm replacing current data.")
    db=backups.db
    with db.gate:
        path=backups.verified_path(data.get("file"))
        source=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)
        try:
            if source.execute("PRAGMA quick_check").fetchone()[0]!="ok" or source.execute("PRAGMA user_version").fetchone()[0]!=1:
                raise AppError("Backup integrity or schema version is incompatible.",409)
            current=db.connect()
            try:
                sql="SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                if [tuple(r) for r in current.execute(sql)] != source.execute(sql).fetchall():
                    raise AppError("Backup structure does not match this version.",409)
            finally: current.close()
            if source.execute("PRAGMA foreign_key_check").fetchall():
                raise AppError("Backup relationships are invalid.",409)
            if not source.execute("SELECT 1 FROM users WHERE role='admin' AND active=1").fetchone():
                raise AppError("This backup has no active administrator. Choose a later backup.",409)
            rollback=backups.create("pre-restore",actor)
            target=db.connect()
            try: source.backup(target)
            finally: target.close()
            with db.transaction() as c:
                c.execute("DELETE FROM sessions")
                record(c,actor,"DATABASE_RESTORED",path.name,"Rollback copy: "+rollback["file"])
        finally: source.close()
    return {"message":"Restore completed. All sessions were signed out. Sign in using an account from that backup.","rollback":rollback["file"]}
