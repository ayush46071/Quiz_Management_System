import json
from .validation import text, integer, exists, require_role, AppError
from .audit import record

class Questions:
    def __init__(self, db): self.db = db

    def list(self, actor):
        require_role(actor,"admin","teacher")
        rows = self.db.rows("SELECT * FROM questions ORDER BY id DESC")
        for row in rows: row["options"] = json.loads(row["options"])
        return rows

    def save(self, actor, data, qid=None):
        require_role(actor,"admin","teacher")
        prompt = text(data.get("prompt"),"Question",5,1500)
        options = data.get("options")
        if not isinstance(options,list) or len(options)!=4: raise AppError("Provide exactly four answer options.")
        options = [text(x,"Option",1,300) for x in options]
        if len({x.casefold() for x in options}) != 4: raise AppError("Answer options must be different.")
        values = (prompt,json.dumps(options),integer(data.get("correct"),"Correct option",0,3),
                  text(data.get("explanation",""),"Explanation",0,1500),
                  text(data.get("category"),"Category",2,60),integer(data.get("points",1),"Points",1,100))
        with self.db.transaction() as c:
            if qid:
                exists(c.execute("SELECT id FROM questions WHERE id=?",(qid,)).fetchone(),"Question")
                if c.execute("SELECT 1 FROM quiz_questions qq JOIN quizzes q ON q.id=qq.quiz_id WHERE qq.question_id=? AND q.status='published'",(qid,)).fetchone():
                    raise AppError("Unpublish quizzes using this question before editing it.",409)
                c.execute("UPDATE questions SET prompt=?,options=?,correct=?,explanation=?,category=?,points=? WHERE id=?",values+(qid,))
            else:
                qid = c.execute("INSERT INTO questions(prompt,options,correct,explanation,category,points,created_by) VALUES(?,?,?,?,?,?,?)",values+(actor["id"],)).lastrowid
            record(c,actor,"QUESTION_SAVED",f"question:{qid}")
        return {"id":qid}

    def delete(self, actor, qid):
        require_role(actor,"admin","teacher")
        with self.db.transaction() as c:
            exists(c.execute("SELECT id FROM questions WHERE id=?",(qid,)).fetchone(),"Question")
            if c.execute("SELECT 1 FROM quiz_questions WHERE question_id=?",(qid,)).fetchone():
                raise AppError("Remove this question from its quizzes before deleting it.",409)
            c.execute("DELETE FROM questions WHERE id=?",(qid,))
            record(c,actor,"QUESTION_DELETED",f"question:{qid}")
        return {"message":"Question deleted."}
