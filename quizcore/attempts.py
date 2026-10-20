"""A single attempt, an immutable question snapshot and application-owned timing."""
import json
import time
from .validation import require_role, exists, AppError, integer
from .audit import record

class Attempts:
    def __init__(self, db): self.db=db

    def start(self, actor, quiz_id):
        require_role(actor,"student")
        with self.db.transaction() as c:
            quiz=exists(c.execute("SELECT * FROM quizzes WHERE id=?",(quiz_id,)).fetchone(),"Quiz")
            old=c.execute("SELECT id FROM attempts WHERE quiz_id=? AND user_id=?",(quiz_id,actor["id"])).fetchone()
            if old: aid=old["id"]
            else:
                if quiz["status"]!="published": raise AppError("This quiz is not available.",403)
                rows=[dict(q) for q in c.execute("SELECT q.* FROM questions q JOIN quiz_questions qq ON q.id=qq.question_id WHERE qq.quiz_id=? ORDER BY qq.position",(quiz_id,))]
                if not rows: raise AppError("This quiz does not have questions.")
                for q in rows: q["options"]=json.loads(q["options"])
                now=int(time.time())
                aid=c.execute("INSERT INTO attempts(quiz_id,user_id,title,pass_percent,snapshot,started_at,deadline,total) VALUES(?,?,?,?,?,?,?,?)",(quiz_id,actor["id"],quiz["title"],quiz["pass_percent"],json.dumps(rows),now,now+quiz["duration"]*60,sum(q["points"] for q in rows))).lastrowid
                record(c,actor,"ATTEMPT_STARTED",f"attempt:{aid}")
        return self.get(actor,aid)

    @staticmethod
    def authorize(actor, row):
        require_role(actor,"admin","teacher","student")
        if actor["role"]=="student" and row["user_id"]!=actor["id"]:
            raise AppError("This attempt belongs to another student.",403)

    def finish(self, c, row, actor, reason):
        if row["submitted_at"] is not None: return
        questions=json.loads(row["snapshot"])
        answers=json.loads(row["answers"])
        score=sum(q["points"] for q in questions if answers.get(str(q["id"]))==q["correct"])
        c.execute("UPDATE attempts SET score=?,submitted_at=?,version=version+1 WHERE id=? AND submitted_at IS NULL",(score,int(time.time()),row["id"]))
        record(c,actor,"ATTEMPT_SUBMITTED",f"attempt:{row['id']}",reason)

    def expire(self):
        with self.db.transaction() as c:
            for row in c.execute("SELECT * FROM attempts WHERE submitted_at IS NULL AND deadline<=?",(int(time.time()),)).fetchall():
                self.finish(c,row,None,"Deadline reached; saved answers graded")

    def get(self, actor, aid):
        with self.db.transaction() as c:
            row=exists(c.execute("SELECT * FROM attempts WHERE id=?",(aid,)).fetchone(),"Attempt")
            self.authorize(actor,row)
            if row["submitted_at"] is None and int(time.time()) >= row["deadline"]:
                self.finish(c,row,actor,"Deadline reached; saved answers graded")
                row=c.execute("SELECT * FROM attempts WHERE id=?",(aid,)).fetchone()
            result=dict(row)
        questions=json.loads(result.pop("snapshot"))
        if result["submitted_at"] is None:
            questions=[{k:v for k,v in q.items() if k not in ("correct","explanation","created_by")} for q in questions]
        result["questions"]=questions
        result["answers"]=json.loads(result["answers"])
        result["server_time"]=int(time.time())
        result["percent"]=round(result["score"]*100/result["total"],1) if result["score"] is not None else None
        result["passed"]=(result["score"]*100 >= result["pass_percent"]*result["total"]) if result["score"] is not None else None
        return result

    def list(self, actor):
        require_role(actor,"admin","teacher","student")
        self.expire()
        where,params=("WHERE a.user_id=?",(actor["id"],)) if actor["role"]=="student" else ("",())
        return self.db.rows(f"SELECT a.id,a.title,u.name,u.username,a.started_at,a.deadline,a.submitted_at,a.score,a.total,a.pass_percent FROM attempts a JOIN users u ON u.id=a.user_id {where} ORDER BY a.id DESC",params)

    def save(self, actor, aid, data, submit=False):
        require_role(actor,"student")
        with self.db.transaction() as c:
            row=exists(c.execute("SELECT * FROM attempts WHERE id=?",(aid,)).fetchone(),"Attempt")
            self.authorize(actor,row)
            if row["submitted_at"] is not None:
                pass  # Repeated submit is idempotent; it never regrades or overwrites.
            elif int(time.time()) >= row["deadline"]:
                self.finish(c,row,actor,"Deadline reached; late answers ignored")
            else:
                version=integer(data.get("version"),"Answer revision",0,2**31-1)
                if version!=row["version"]:
                    raise AppError("Answers changed in another app window. Reload this attempt before continuing.",409)
                answers=data.get("answers")
                if not isinstance(answers,dict): raise AppError("Answers must be an object.")
                allowed={str(q["id"]) for q in json.loads(row["snapshot"])}
                if any(k not in allowed for k in answers): raise AppError("An answer does not belong to this quiz.")
                answers={k:integer(v,"Answer choice",0,3) for k,v in answers.items()}
                c.execute("UPDATE attempts SET answers=?,version=version+1 WHERE id=?",(json.dumps(answers),aid))
                record(c,actor,"ANSWERS_SAVED",f"attempt:{aid}",f"Answered={len(answers)}")
                if submit:
                    fresh=c.execute("SELECT * FROM attempts WHERE id=?",(aid,)).fetchone()
                    self.finish(c,fresh,actor,"Student submitted")
        return self.get(actor,aid)
