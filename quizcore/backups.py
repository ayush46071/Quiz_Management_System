"""Online SQLite snapshots, SHA-256 manifests and verified restore points."""
from pathlib import Path
import hashlib
import json
import sqlite3
import time
import uuid
from .validation import AppError, require_role
from .audit import record

class Backups:
    def __init__(self, db):
        self.db=db
        self.last_error=None

    @staticmethod
    def checksum(path):
        with open(path,"rb") as stream:
            h=hashlib.sha256()
            for chunk in iter(lambda:stream.read(1_048_576),b""): h.update(chunk)
        return h.hexdigest()

    def create(self, reason="manual", actor=None):
        if actor: require_role(actor,"admin")
        filename=time.strftime("quizsure_%Y%m%d_%H%M%S",time.gmtime())+"_"+uuid.uuid4().hex[:6]+".sqlite3"
        final=self.db.config.backups / filename
        temporary=final.with_suffix(".tmp")
        with self.db.gate:
            try:
                source=self.db.connect()
                target=sqlite3.connect(temporary)
                try:
                    source.backup(target)
                    target.execute("DELETE FROM sessions")
                    target.commit()
                    if target.execute("PRAGMA quick_check").fetchone()[0]!="ok":
                        raise AppError("Backup verification failed.",500)
                finally:
                    source.close(); target.close()
                temporary.replace(final)
                manifest={"file":filename,"sha256":self.checksum(final),"created_at":int(time.time()),"reason":reason,"bytes":final.stat().st_size}
                final.with_suffix(".json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
                with self.db.transaction() as c: record(c,actor,"BACKUP_CREATED",filename,reason)
                self.last_error=None
                regular=[p for p in sorted(self.db.config.backups.glob("*.sqlite3"),reverse=True) if self._manifest(p).get("reason")!="pre-restore"]
                for old in regular[self.db.config.backup_keep:]:
                    old.unlink(missing_ok=True); old.with_suffix(".json").unlink(missing_ok=True)
                return manifest
            except Exception:
                temporary.unlink(missing_ok=True)
                self.last_error="Backup failed. Check disk space and data folder permissions, then retry."
                self.db.config.logger().exception("Backup operation failed")
                raise

    def _manifest(self,path):
        try: return json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError,ValueError): return {}

    def list(self,actor):
        require_role(actor,"admin")
        result=[]
        for path in sorted(self.db.config.backups.glob("*.sqlite3"),reverse=True):
            info=self._manifest(path)
            result.append({**info,"file":path.name,"bytes":path.stat().st_size,"verified":bool(info.get("sha256")) and self.checksum(path)==info["sha256"]})
        return {"items":result,"last_error":self.last_error,"interval_seconds":self.db.config.backup_seconds,"retention":self.db.config.backup_keep}

    def verified_path(self,filename):
        if not isinstance(filename,str) or Path(filename).name!=filename or not filename.endswith(".sqlite3"):
            raise AppError("Select a valid backup filename.")
        path=self.db.config.backups / filename
        if not path.is_file(): raise AppError("Backup not found.",404)
        info=self._manifest(path)
        if not info.get("sha256") or self.checksum(path)!=info["sha256"]:
            raise AppError("Backup checksum does not match. Restore was cancelled.",409)
        return path
