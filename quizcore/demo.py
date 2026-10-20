"""Optional demonstration dataset; never seeds a live database without --demo."""

def seed_demo(app):
    if app.db.one("SELECT id FROM users LIMIT 1"): return False
    app.auth.setup({"name":"Demo Administrator","username":"admin","password":"DemoAdmin123!"})
    admin=app.db.one("SELECT id,username,role FROM users WHERE username='admin'")
    app.users.save(admin,{"name":"Demo Teacher","username":"teacher","password":"DemoTeacher123!","role":"teacher"})
    app.users.save(admin,{"name":"Demo Student","username":"student","password":"DemoStudent123!","role":"student"})
    bank=[
      ("What is the main purpose of Total Quality Management?",["Improve customer satisfaction through continuous improvement","Inspect only the final product","Eliminate all documentation","Focus only on short-term cost"],0,"TQM involves everyone in improving processes and meeting customer needs.","TQM foundations"),
      ("Which sequence correctly represents the PDCA cycle?",["Plan, Do, Check, Act","Prepare, Deliver, Close, Audit","Plan, Design, Create, Assess","Perform, Detect, Correct, Approve"],0,"PDCA links planning and implementation to verification and standardization.","TQM foundations"),
      ("How is the Risk Priority Number calculated in FMEA?",["Severity plus occurrence","Severity × occurrence × detection","Occurrence divided by detection","Severity × cost"],1,"RPN multiplies the severity, occurrence and detection ratings.","Quality tools"),
      ("What does a Pareto chart help a team identify?",["The most frequent categories of problems","The exact future failure date","Every possible root cause","The identity of every user"],0,"Categories are ordered by frequency with a cumulative percentage line.","Quality tools"),
      ("Which control best prevents a student receiving two attempts for one quiz?",["A larger Submit button","A unique database constraint on student and quiz","A dark theme","A longer quiz title"],1,"A database uniqueness constraint protects the invariant even when requests race.","Software reliability"),
      ("What is the safest way to back up an active SQLite database here?",["Copy only the main file without considering active writes","Use the SQLite backup API and verify the copy","Rename the live database during an exam","Delete old answers first"],1,"The backup API creates a consistent database snapshot while the service is active.","Software reliability"),
      ("Which TQM principle does input validation demonstrate?",["Poka-yoke or error prevention","Ignoring process variation","Final inspection only","Increasing rework"],0,"Preventing invalid input stops avoidable errors before they enter the process.","TQM foundations"),
      ("Why is a question snapshot stored for each attempt?",["To make the page colourful","To keep the attempted content and answer key stable","To allow students to edit marks","To remove the need for backups"],1,"A snapshot makes historical scoring independent of later question-bank edits.","Software reliability"),
      ("What does the C in SIPOC stand for?",["Control","Cost","Customers","Correction"],2,"SIPOC means Suppliers, Inputs, Process, Outputs and Customers.","Quality tools"),
      ("Which measurement is an appropriate CTQ for answer saving?",["The developer’s favourite colour","Confirmed answers survive a restart","Number of icons on the page","Length of the welcome message"],1,"A CTQ translates a user need into a measurable acceptance requirement.","Software reliability"),
      ("Who should be allowed to restore the whole quiz database?",["Any visitor","A student","An authenticated administrator","Anyone who knows a quiz title"],2,"Database recovery affects the entire workspace and is restricted to administrators.","Software reliability"),
      ("What should the Check stage of PDCA contain?",["A claim without evidence","Measured results compared with the planned target","Only the next feature idea","Only a list of team names"],1,"The Check stage evaluates evidence against the planned objective.","TQM foundations"),
    ]
    ids=[]
    for prompt,options,correct,explanation,category in bank:
        ids.append(app.questions.save(admin,{"prompt":prompt,"options":options,"correct":correct,"explanation":explanation,"category":category,"points":2})["id"])
    for title,description,minutes,questions,status in [
       ("TQM essentials","Build confidence in customer focus, PDCA, and quality tools.",12,[ids[i] for i in (0,1,2,3,6,8)],"published"),
       ("Reliable software practices","Explore the controls behind dependable quiz delivery.",10,[ids[i] for i in (4,5,7,9,10)],"published"),
       ("Quality tools checkpoint","Connect the classroom concepts with practical decisions.",8,[ids[i] for i in (2,3,8,11)],"draft")]:
        app.quizzes.save(admin,{"title":title,"description":description,"duration":minutes,"pass_percent":60,"status":status,"question_ids":questions})
    for title,category,count,severity in [("Incomplete input accepted","Software Code",8,7),("Answer acknowledgement unclear","Process",5,6),("Network interruption","Infrastructure",3,8),("Repeated submit click","People",2,5),("Missing restore rehearsal","Process",1,8)]:
        app.quality.save(admin,"defects",{"title":title,"category":category,"occurrences":count,"severity":severity,"status":"Open","source":"Illustrative","evidence":"Teaching example only. This is not an observed defect or measured project baseline."})
    app.quality.save(admin,"pdca",{"title":"Verify recovery before a classroom assessment","plan":"Run one restart-resume test and one verified restore drill before using real records.","do_text":"Save an answer, restart the app and resume the quiz. Use administrator Backup & recovery to rehearse a verified restore.","check_text":"Pending the operator’s own restore drill on the target machine.","act":"Keep a dated off-device backup; repeat after changes.","status":"Plan","owner":"Classroom administrator"})
    app.backups.create("demo-seed",admin)
    return True
