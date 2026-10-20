import csv
import io
from .validation import require_role, choice

def safe_cell(value):
    if value is None: return ""
    if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")):
        return "'"+value
    return value

def export_csv(service,user,kind):
    choice(kind,"export",("results","defects","fmea","pdca","audit"))
    if kind=="results":
        rows=service.attempts.list(user)
    elif kind=="audit":
        require_role(user,"admin")
        rows=service.db.rows("SELECT * FROM audit ORDER BY id DESC")
    else:
        require_role(user,"admin","teacher")
        rows=service.quality.read(user)[kind]
    output=io.StringIO(newline="")
    writer=csv.writer(output)
    if rows:
        writer.writerow(rows[0].keys())
        for row in rows: writer.writerow([safe_cell(v) for v in row.values()])
    else: writer.writerow(["No records"])
    return output.getvalue().encode("utf-8-sig")
