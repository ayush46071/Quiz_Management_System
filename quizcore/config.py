"""One explicit location for runtime data and recovery policy."""
from dataclasses import dataclass
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

ROOT = Path(__file__).resolve().parent.parent

@dataclass
class Config:
    data_dir: Path = ROOT / "data"
    backup_seconds: int = 300
    backup_keep: int = 20
    session_seconds: int = 8 * 3600
    secure_cookie: bool = False

    def __post_init__(self):
        self.data_dir = Path(self.data_dir).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(exist_ok=True)

    @property
    def database(self):
        return self.data_dir / "quizsure.sqlite3"

    @property
    def backups(self):
        return self.data_dir / "backups"

    def logger(self):
        logger = logging.getLogger("quizsure." + str(self.data_dir))
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            h = RotatingFileHandler(self.data_dir / "system.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
            h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(h)
        return logger
