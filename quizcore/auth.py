"""Salted password hashes, revocable sessions and bounded login retries."""
import hashlib
import hmac
import secrets
import time
from .validation import AppError, username, password, text, require_role
from .audit import record

def hash_password(value):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), 240_000).hex()
    return f"pbkdf2_sha256$240000${salt}${digest}"

def verify_password(value, stored):
    try:
        _, rounds, salt, expected = stored.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False

def digest_token(token):
    return hashlib.sha256(token.encode()).hexdigest()

class Auth:
    def __init__(self, db):
        self.db = db
        self.dummy_hash = hash_password("NotARealPassword123")

    def setup(self, data):
        name = text(data.get("name"), "Name", 2, 80)
        login = username(data.get("username"))
        secret = hash_password(password(data.get("password")))
        with self.db.transaction() as c:
            if c.execute("SELECT 1 FROM users").fetchone():
                raise AppError("Setup is already complete.", 409)
            uid = c.execute("INSERT INTO users(name,username,password_hash,role,created_at) VALUES(?,?,?,'admin',?)",
                            (name, login, secret, int(time.time()))).lastrowid
            record(c, {"id":uid,"username":login}, "SETUP", "users", "Initial administrator created")
        return {"message":"Administrator created. Please sign in."}

    def login(self, data):
        login = username(data.get("username"))
        supplied = data.get("password")
        if not isinstance(supplied,str) or len(supplied) > 128:
            raise AppError("Invalid username or password.", 401)
        now = int(time.time())
        error = None
        result = None
        with self.db.transaction() as c:
            row = c.execute("SELECT * FROM users WHERE username=?", (login,)).fetchone()
            user = dict(row) if row else None
            valid = verify_password(supplied, user["password_hash"] if user else self.dummy_hash)
            if user and user["locked_until"] > now:
                error = AppError("Too many attempts. Wait five minutes before trying again.", 429)
            elif not user or not user["active"] or not valid:
                if user:
                    count = user["failures"] + 1 if user["locked_until"] == 0 else 1
                    c.execute("UPDATE users SET failures=?,locked_until=? WHERE id=?", (count,now+300 if count>=5 else 0,user["id"]))
                record(c, user, "LOGIN_FAILED", "authentication", "Invalid credentials")
                error = AppError("Invalid username or password.", 401)
            else:
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
                c.execute("UPDATE users SET failures=0,locked_until=0 WHERE id=?", (user["id"],))
                c.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
                c.execute("INSERT INTO sessions VALUES(?,?,?,?)", (digest_token(token),user["id"],csrf,now+self.db.config.session_seconds))
                record(c, user, "LOGIN", "authentication")
                result = {"token":token,"csrf":csrf,"user":self.public(user)}
        if error:
            raise error
        return result

    @staticmethod
    def public(user):
        return {k:user[k] for k in ("id","name","username","role","active")}

    def session(self, token):
        if not token:
            return None
        return self.db.one("SELECT u.id,u.name,u.username,u.role,u.active,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1", (digest_token(token),int(time.time())))

    def logout(self, token, user):
        with self.db.transaction() as c:
            c.execute("DELETE FROM sessions WHERE token_hash=?", (digest_token(token),))
            record(c,user,"LOGOUT","authentication")

    def change_password(self, user, data):
        require_role(user,"admin","teacher","student")
        current = self.db.one("SELECT password_hash FROM users WHERE id=?",(user["id"],))
        if not verify_password(str(data.get("current","")), current["password_hash"]):
            raise AppError("Current password is incorrect.")
        new_hash = hash_password(password(data.get("password")))
        with self.db.transaction() as c:
            c.execute("UPDATE users SET password_hash=? WHERE id=?",(new_hash,user["id"]))
            c.execute("DELETE FROM sessions WHERE user_id=?",(user["id"],))
            record(c,user,"PASSWORD_CHANGED",f"user:{user['id']}")
        return {"message":"Password changed. Sign in again."}
