"""Editable checksheet, risk analysis and improvement log; no invented metrics."""
import time
from .validation import require_role, text, integer, choice, exists
from .audit import record

CATEGORIES=("People","Process","Software Code","Infrastructure")

class Quality:
    def __init__(self,db): self.db=db

    def read(self,actor):
        require_role(actor,"admin","teacher")
        risks=self.db.rows("SELECT *, severity*occurrence*detection AS rpn, residual_s*residual_o*residual_d AS residual_rpn FROM fmea ORDER BY rpn DESC")
        return {"defects":self.db.rows("SELECT * FROM defects ORDER BY id DESC"),"fmea":risks,"pdca":self.db.rows("SELECT * FROM pdca ORDER BY id DESC")}

    def save(self,actor,kind,data,rid=None):
        require_role(actor,"admin","teacher")
        now=int(time.time())
        if kind=="defects":
            fields=["title","category","severity","occurrences","status","evidence","source","updated_at"]
            values=[text(data.get("title"),"Defect title",5,160),choice(data.get("category"),"category",CATEGORIES),integer(data.get("severity"),"Severity",1,10),integer(data.get("occurrences",1),"Occurrences",1,10000),choice(data.get("status","Open"),"status",("Open","In progress","Resolved")),text(data.get("evidence",""),"Reproduction steps and evidence",0,3000),choice(data.get("source","Observed"),"source",("Observed","Illustrative")),now]
            if not rid: fields.append("created_at"); values.append(now)
        elif kind=="fmea":
            fields=["failure","effect","cause","control","action","owner","severity","occurrence","detection","residual_s","residual_o","residual_d"]
            values=[text(data.get(k),k.replace("_"," ").title(),2,500) for k in fields[:6]]+[integer(data.get(k),k.replace("_"," ").title(),1,10) for k in fields[6:]]
        elif kind=="pdca":
            fields=["title","plan","do_text","check_text","act","status","owner","updated_at"]
            values=[text(data.get("title"),"Title",3,160)]+[text(data.get(k,""),k.replace("_text",""),0,3000) for k in fields[1:5]]+[choice(data.get("status","Plan"),"PDCA stage",("Plan","Do","Check","Act","Complete")),text(data.get("owner"),"Owner",2,80),now]
        else:
            from .validation import AppError
            raise AppError("Unknown quality record.",404)
        with self.db.transaction() as c:
            if rid:
                exists(c.execute(f"SELECT id FROM {kind} WHERE id=?",(rid,)).fetchone())
                c.execute(f"UPDATE {kind} SET "+",".join(f"{f}=?" for f in fields)+" WHERE id=?",values+[rid])
            else:
                rid=c.execute(f"INSERT INTO {kind} ("+",".join(fields)+") VALUES("+",".join("?" for _ in fields)+")",values).lastrowid
            record(c,actor,"QUALITY_SAVED",f"{kind}:{rid}")
        return {"id":rid}

    def delete(self,actor,kind,rid):
        require_role(actor,"admin","teacher")
        choice(kind,"record type",("defects","fmea","pdca"))
        with self.db.transaction() as c:
            exists(c.execute(f"SELECT id FROM {kind} WHERE id=?",(rid,)).fetchone())
            c.execute(f"DELETE FROM {kind} WHERE id=?",(rid,))
            record(c,actor,"QUALITY_DELETED",f"{kind}:{rid}")
        return {"message":"Quality record deleted."}
