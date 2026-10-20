"""Local-only recovery for an administrator who has forgotten the password."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import argparse
from getpass import getpass
from quizcore.config import Config,ROOT
from quizcore.db import Database
from quizcore.auth import hash_password
from quizcore.validation import password,username
from quizcore.audit import record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir",type=Path,default=ROOT/"data")
    args=parser.parse_args()
    print("Run on the app computer. Close the app first. This resets an existing administrator only.")
    db=Database(Config(args.data_dir))
    login=username(input("Administrator username: "))
    user=db.one("SELECT * FROM users WHERE username=? AND role='admin'",(login,))
    if not user:raise SystemExit("Administrator not found; no account was changed.")
    secret=password(getpass("New password (10+ characters, letter and number): "))
    if secret!=getpass("Repeat new password: "):raise SystemExit("Passwords did not match.")
    if input("Type RESET to continue: ")!="RESET":raise SystemExit("Cancelled.")
    with db.transaction() as c:
        c.execute("UPDATE users SET password_hash=?,active=1,failures=0,locked_until=0 WHERE id=?",(hash_password(secret),user["id"]))
        c.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
        record(c,None,"LOCAL_ADMIN_RESET",f"user:{user['id']}","Local operator reset; filesystem access required")
    print("Password reset. Restart the app and sign in.")

if __name__=="__main__":main()
