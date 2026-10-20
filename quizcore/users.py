import time
from .validation import text, username, password, choice, integer, exists, require_role, AppError
from .auth import hash_password
from .audit import record

class Users:
    def __init__(self, db): self.db = db

    def list(self, actor):
        require_role(actor,"admin")
        return self.db.rows("SELECT id,name,username,role,active,created_at FROM users ORDER BY name")

    def save(self, actor, data, uid=None):
        require_role(actor,"admin")
        name = text(data.get("name"),"Name",2,80)
        login = username(data.get("username"))
        role = choice(data.get("role"),"role",("admin","teacher","student"))
        active = integer(data.get("active",1),"Account status",0,1)
        hashed = hash_password(password(data["password"])) if data.get("password") else None
        if not uid and not hashed: raise AppError("A password is required for a new account.")
        with self.db.transaction() as c:
            if uid:
                old = exists(c.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(),"User")
                if actor["id"] == uid and (role != "admin" or not active):
                    raise AppError("You cannot remove your own administrator access.")
                c.execute("UPDATE users SET name=?,username=?,role=?,active=? WHERE id=?",(name,login,role,active,uid))
                if hashed: c.execute("UPDATE users SET password_hash=?,failures=0,locked_until=0 WHERE id=?",(hashed,uid))
                if hashed or role != old["role"] or active != old["active"]:
                    c.execute("DELETE FROM sessions WHERE user_id=?",(uid,))
            else:
                uid = c.execute("INSERT INTO users(name,username,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?)",(name,login,hashed,role,active,int(time.time()))).lastrowid
            record(c,actor,"USER_SAVED",f"user:{uid}",f"Role={role}; active={active}")
        return {"id":uid}

    def delete(self, actor, uid):
        require_role(actor,"admin")
        if uid == actor["id"]: raise AppError("You cannot delete your own account.")
        with self.db.transaction() as c:
            exists(c.execute("SELECT id FROM users WHERE id=?",(uid,)).fetchone(),"User")
            if c.execute("SELECT 1 FROM attempts WHERE user_id=?",(uid,)).fetchone():
                raise AppError("This user has quiz history. Deactivate the account to preserve results.",409)
            c.execute("DELETE FROM users WHERE id=?",(uid,))
            record(c,actor,"USER_DELETED",f"user:{uid}")
        return {"message":"User deleted."}
