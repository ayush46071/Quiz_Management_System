import time
from .validation import text, integer, choice, exists, require_role, AppError
from .audit import record

class Quizzes:
    def __init__(self, db): self.db = db

    def list(self, actor):
        require_role(actor,"admin","teacher","student")
        rows = self.db.rows("SELECT q.*, (SELECT COUNT(*) FROM quiz_questions WHERE quiz_id=q.id) AS question_count FROM quizzes q " + ("WHERE status='published' " if actor["role"]=="student" else "") + "ORDER BY id DESC")
        for row in rows:
            row["question_ids"] = [x["question_id"] for x in self.db.rows("SELECT question_id FROM quiz_questions WHERE quiz_id=? ORDER BY position",(row["id"],))]
            row["attempt"] = self.db.one("SELECT id,submitted_at,score,total,deadline FROM attempts WHERE quiz_id=? AND user_id=?",(row["id"],actor["id"]))
        return rows

    def save(self, actor, data, qid=None):
        require_role(actor,"admin","teacher")
        title = text(data.get("title"),"Quiz title",3,120)
        desc = text(data.get("description",""),"Description",0,1000)
        duration = integer(data.get("duration"),"Duration in minutes",1,180)
        threshold = integer(data.get("pass_percent",60),"Pass percentage",0,100)
        status = choice(data.get("status","draft"),"status",("draft","published","archived"))
        ids = data.get("question_ids",[])
        if not isinstance(ids,list) or len(ids)>100: raise AppError("Select up to 100 questions.")
        ids = [integer(x,"Question ID",1,2**31-1) for x in ids]
        if len(set(ids)) != len(ids): raise AppError("A question cannot be repeated in the same quiz.")
        if status=="published" and not ids: raise AppError("Add at least one question before publishing.")
        with self.db.transaction() as c:
            for i in ids: exists(c.execute("SELECT id FROM questions WHERE id=?",(i,)).fetchone(),"Selected question")
            if qid:
                old=exists(c.execute("SELECT * FROM quizzes WHERE id=?",(qid,)).fetchone(),"Quiz")
                old_ids=[r[0] for r in c.execute("SELECT question_id FROM quiz_questions WHERE quiz_id=? ORDER BY position",(qid,))]
                changed=(title,desc,duration,threshold,ids)!=(old["title"],old["description"],old["duration"],old["pass_percent"],old_ids)
                if changed and c.execute("SELECT 1 FROM attempts WHERE quiz_id=?",(qid,)).fetchone():
                    raise AppError("This quiz has attempts. Only its publication status can change; create a new quiz for revised content.",409)
                c.execute("UPDATE quizzes SET title=?,description=?,duration=?,pass_percent=?,status=? WHERE id=?",(title,desc,duration,threshold,status,qid))
                c.execute("DELETE FROM quiz_questions WHERE quiz_id=?",(qid,))
            else:
                qid=c.execute("INSERT INTO quizzes(title,description,duration,pass_percent,status,created_by,created_at) VALUES(?,?,?,?,?,?,?)",(title,desc,duration,threshold,status,actor["id"],int(time.time()))).lastrowid
            c.executemany("INSERT INTO quiz_questions VALUES(?,?,?)",[(qid,i,pos) for pos,i in enumerate(ids)])
            record(c,actor,"QUIZ_SAVED",f"quiz:{qid}",f"Status={status}; questions={len(ids)}")
        return {"id":qid}

    def delete(self, actor, qid):
        require_role(actor,"admin","teacher")
        with self.db.transaction() as c:
            exists(c.execute("SELECT id FROM quizzes WHERE id=?",(qid,)).fetchone(),"Quiz")
            if c.execute("SELECT 1 FROM attempts WHERE quiz_id=?",(qid,)).fetchone():
                raise AppError("This quiz has results. Archive it to retain assessment history.",409)
            c.execute("DELETE FROM quizzes WHERE id=?",(qid,))
            record(c,actor,"QUIZ_DELETED",f"quiz:{qid}")
        return {"message":"Quiz deleted."}
