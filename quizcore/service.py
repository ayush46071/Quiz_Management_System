"""Composition root and scheduled reliability work."""
import threading
import time
from .db import Database
from .auth import Auth
from .users import Users
from .questions import Questions
from .quizzes import Quizzes
from .attempts import Attempts
from .backups import Backups
from .quality import Quality
from .risk_seed import seed_risks

class Service:
    def __init__(self,config):
        self.config=config
        self.db=Database(config)
        self.auth=Auth(self.db)
        self.users=Users(self.db)
        self.questions=Questions(self.db)
        self.quizzes=Quizzes(self.db)
        self.attempts=Attempts(self.db)
        self.backups=Backups(self.db)
        self.quality=Quality(self.db)
        seed_risks(self.db)
        self.stop_event=threading.Event()
        self.worker=None

    def maintenance(self):
        last=0
        while not self.stop_event.is_set():
            try:
                self.attempts.expire()
                if time.monotonic()-last>=self.config.backup_seconds and self.db.one("SELECT id FROM users LIMIT 1"):
                    self.backups.create("automatic")
                    last=time.monotonic()
            except Exception:
                self.config.logger().exception("Scheduled maintenance failed; next cycle will retry")
                last=time.monotonic()  # Avoid flooding on a persistent disk failure.
            self.stop_event.wait(5)

    def start_worker(self):
        self.worker=threading.Thread(target=self.maintenance,daemon=True,name="quizsure-maintenance")
        self.worker.start()

    def close(self):
        self.stop_event.set()
        if self.worker: self.worker.join(timeout=12)
        if self.db.one("SELECT id FROM users LIMIT 1"):
            try: self.backups.create("shutdown")
            except Exception: self.config.logger().exception("Shutdown backup failed")
