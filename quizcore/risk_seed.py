"""Initial FMEA engineering estimates, to be reassessed with operational data."""

RISKS=[
 ("Saved answers lost after interruption","Student must repeat work","App interruption before database acknowledgement",8,5,6,"Immediate answer save and retry indicator","Test failed save and restart recovery",8,2,2),
 ("Duplicate submissions change grade","Inconsistent assessment result","Repeated clicks or request retries",8,4,7,"Unique attempt and idempotent submission transaction","Run parallel submit regression test",8,1,2),
 ("Backup cannot be restored","Extended loss of service","Damaged or incompatible backup",9,3,8,"Online SQLite backup, checksum and schema verification","Perform restore drill and keep off-device copies",9,2,3),
 ("Unauthorized question modification","Assessment integrity compromised","Missing service role checks",9,4,6,"Role checks on every protected service operation","Run role and revoked-session tests on each release",9,1,2),
 ("Invalid quiz or answer saved","Incorrect scores or application error","Unbounded or malformed input",7,5,5,"Validation plus SQLite check and foreign-key constraints","Run input-boundary regression suite",7,2,2),
 ("Timer bypass accepts late answers","Unfair assessment timing","Untrusted system clock or timer-only UI validation",8,4,6,"Deadline stored and checked by Python services","Test late saves with a forced expired deadline",8,1,2),
 ("Question edits change historical result","Result cannot be explained","Grading against live mutable questions",8,3,7,"Immutable question and answer-key snapshots","Verify history after question bank edit",8,1,2),
 ("Local disk loss destroys all copies","All records unavailable","Same-device database and backups",10,3,8,"Verified backup and manifest export","Copy backups to a separate drive after each session",10,2,4),
]

def seed_risks(db):
    with db.transaction() as c:
        if c.execute("SELECT 1 FROM fmea").fetchone(): return
        for failure,effect,cause,s,o,d,control,action,rs,ro,rd in RISKS:
            c.execute("INSERT INTO fmea(failure,effect,cause,severity,occurrence,detection,control,action,owner,residual_s,residual_o,residual_d) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(failure,effect,cause,s,o,d,control,action,"Project maintainer",rs,ro,rd))
