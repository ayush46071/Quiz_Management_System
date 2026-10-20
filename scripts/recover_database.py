"""Offline restore when a damaged live database prevents normal startup."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import argparse,json,sqlite3,shutil,time
from quizcore.config import Config
from quizcore.backups import Backups
from quizcore.db import SCHEMA

def recover(config,filename,confirmation):
    if confirmation!="STOPPED AND RESTORE":raise ValueError("Close the app and provide the exact confirmation.")
    if Path(filename).name!=filename or not filename.endswith(".sqlite3"):raise ValueError("Use a backup filename, not a path.")
    source_path=config.backups/filename
    metadata=json.loads(source_path.with_suffix(".json").read_text(encoding="utf-8"))
    if Backups.checksum(source_path)!=metadata.get("sha256"):raise ValueError("Backup checksum mismatch.")
    source=sqlite3.connect(source_path.as_uri()+"?mode=ro",uri=True)
    expected=sqlite3.connect(":memory:");expected.executescript(SCHEMA)
    temp=config.data_dir/"recovered.tmp"
    try:
        query="SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        if source.execute("PRAGMA quick_check").fetchone()[0]!="ok" or source.execute(query).fetchall()!=expected.execute(query).fetchall():raise ValueError("Backup structure or integrity failed.")
        if source.execute("PRAGMA foreign_key_check").fetchall():raise ValueError("Invalid database relationships.")
        if not source.execute("SELECT id FROM users WHERE role='admin' AND active=1").fetchone():raise ValueError("Backup has no active administrator.")
        target=sqlite3.connect(temp)
        try:
            source.backup(target);target.execute("DELETE FROM sessions")
            target.execute("INSERT INTO audit(occurred_at,actor,action,entity,detail) VALUES(?,'local operator','OFFLINE_RESTORE',?,'Original files retained in quarantine')",(int(time.time()),filename));target.commit()
        finally:target.close()
    finally:source.close();expected.close()
    quarantine=config.data_dir/("quarantine_"+str(time.time_ns()));quarantine.mkdir()
    # Copy the original files first. Nothing is overwritten until the new database is verified.
    for suffix in ("","-wal","-shm"):
        old=Path(str(config.database)+suffix)
        if old.exists():shutil.copy2(old,quarantine/old.name)
    for suffix in ("-wal","-shm"):Path(str(config.database)+suffix).unlink(missing_ok=True)
    temp.replace(config.database)
    return quarantine

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--data-dir",type=Path,default=ROOT/"data");p.add_argument("--file",required=True);a=p.parse_args()
    print("Close every quiz app using this data folder. Current files will be preserved in quarantine.")
    confirmation=input("Type STOPPED AND RESTORE: ")
    try:result=recover(Config(a.data_dir),a.file,confirmation)
    except (ValueError,OSError,sqlite3.Error) as error:raise SystemExit(f"Recovery cancelled: {error}")
    print(f"Recovered. Original files are in {result}. Restart QuizSure and sign in with the backup's credentials.")

if __name__=="__main__":main()
