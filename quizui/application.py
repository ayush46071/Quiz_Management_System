"""The complete native desktop workspace."""
import datetime
import shutil
import sqlite3
import tkinter as tk
import uuid
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from quizcore.validation import AppError, require_role
from quizcore.exports import export_csv
from quizcore.recovery import restore
from .model import DesktopSession
from .widgets import BG, PANEL, INK, MUTED, TEAL, DEEP, PALE, RED, apply_theme, label, DataTable, FormDialog, ScrollFrame
from .editors import EditorsMixin
from .exam import ExamMixin
from .quality import QualityMixin


def date(value):
    return datetime.datetime.fromtimestamp(value).strftime('%d %b %Y, %H:%M') if value else '—'


class QuizApplication(EditorsMixin, ExamMixin, QualityMixin):
    def __init__(self, root, service, demo=False):
        self.root, self.service, self.demo = root, service, demo
        self.session = DesktopSession(service)
        self.exam = None; self.exam_job = None; self.route = 'overview'
        self.status = tk.StringVar(value='Ready')
        root.title('Assessment workspace'); root.geometry('1200x800'); root.minsize(900, 640)
        apply_theme(root)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.report_callback_exception = lambda typ, value, tb: self.show_error(value)
        self.login_screen()

    @property
    def actor(self):
        return self.session.actor

    def error_text(self, error):
        if isinstance(error, AppError): return error.message
        if isinstance(error, sqlite3.IntegrityError):
            return 'This conflicts with existing data. Check the username and linked records.'
        if isinstance(error, sqlite3.OperationalError):
            return 'The database is busy or unavailable. Your changes were not confirmed. Retry after checking disk space and permissions.'
        if isinstance(error, PermissionError): return 'Access was denied. Choose a writable folder and retry.'
        if isinstance(error, OSError): return f'The file operation could not finish: {error}'
        reference = uuid.uuid4().hex[:8]
        self.service.config.logger().error('Desktop error %s', reference, exc_info=(type(error), error, error.__traceback__))
        return f'The action could not finish. Retry; if it continues, use error reference {reference} in system.log.'

    def show_error(self, error):
        text = self.error_text(error)
        if isinstance(error, AppError) and error.status == 401 and self.session.token is None:
            self.login_screen()
        messagebox.showerror('Please check', text, parent=self.root)

    def guard(self, action):
        def run(*args):
            try: return action()
            except Exception as error: self.show_error(error)
        return run

    def clear_root(self):
        self.stop_exam_clock()
        for child in self.root.winfo_children(): child.destroy()

    def login_screen(self):
        self.clear_root(); self.exam = None
        self.root.title('Sign in')
        self.root.columnconfigure(0, weight=1); self.root.rowconfigure(0, weight=1)
        page = ttk.Frame(self.root); page.pack(fill='both', expand=True)
        page.columnconfigure(0, weight=1); page.columnconfigure(1, weight=1); page.rowconfigure(0, weight=1)
        art = tk.Frame(page, bg=DEEP, padx=42, pady=38); art.grid(row=0, column=0, sticky='nsew')
        inner = tk.Frame(art, bg=DEEP); inner.place(relx=.5, rely=.5, anchor='center', relwidth=1)
        label(inner, 'A BETTER WAY TO ASSESS', 10, '#b8d5ad', DEEP, True).pack(anchor='w', pady=15)
        label(inner, 'Focus on learning.\nMake every\nanswer count.', 32, 'white', DEEP, True).pack(anchor='w')
        label(inner, 'A clear space for questions,\npractice and progress.', 13, '#c7d9cf', DEEP).pack(anchor='w', pady=24)
        drawing = tk.Canvas(inner, width=300, height=150, bg=DEEP, highlightthickness=0)
        drawing.pack(anchor='w', pady=12)
        for x, y, caption, color in ((2,45,'A','#326557'),(101,10,'✓','#d8e6c6'),(200,30,'B','#467661')):
            drawing.create_rectangle(x,y,x+85,145,fill=color,outline='')
            drawing.create_text(x+42,(y+145)/2,text=caption,font=('Segoe UI',32),fill=DEEP if caption=='✓' else '#dce8d4')
        form_outer = ttk.Frame(page, padding=35); form_outer.grid(row=0, column=1, sticky='nsew')
        form = ttk.Frame(form_outer); form.place(relx=.5,rely=.5,anchor='center',relwidth=1)
        setup = not self.service.db.one('SELECT id FROM users LIMIT 1')
        label(form, 'WELCOME TO YOUR WORKSPACE', 9, TEAL, bold=True).pack(anchor='w', pady=10)
        label(form, 'Create your administrator' if setup else 'Good to see you again', 22, bold=True, wraplength=410).pack(anchor='w')
        label(form, 'Set up the first account on this computer.' if setup else 'Sign in to manage assessments or continue learning.', 10, MUTED, wraplength=380).pack(anchor='w', pady=(12,25))
        entries = {}
        for key, caption in ([('name','Your full name')] if setup else []) + [('username','Username'),('password','Password')]:
            label(form, caption, bold=True).pack(anchor='w', pady=(8,5))
            field = ttk.Entry(form, show='*' if key=='password' else '')
            field.pack(fill='x'); entries[key] = field
        if setup: label(form, 'Use 10+ characters, including a letter and a number.', 9, MUTED, wraplength=380).pack(anchor='w', pady=10)
        self.login_error = tk.StringVar()
        ttk.Label(form,textvariable=self.login_error,style='Error.TLabel',wraplength=380).pack(fill='x',pady=12)
        def submit():
            try:
                values={k:w.get() for k,w in entries.items()}
                if setup:
                    self.service.auth.setup(values)
                    self.session.login(values['username'], values['password'])
                else: self.session.login(values['username'], values['password'])
                self.build_shell()
            except Exception as error:
                self.login_error.set(self.error_text(error))
        ttk.Button(form,text='Create administrator' if setup else 'Sign in',style='Primary.TButton',command=submit).pack(fill='x',pady=6)
        for w in entries.values(): w.bind('<Return>',lambda e:submit())
        if self.demo and not setup:
            label(form, 'DEMO ACCOUNTS', 9, MUTED).pack(anchor='w',pady=(25,8))
            buttons=ttk.Frame(form); buttons.pack(fill='x')
            def fill(role):
                for key,value in [('username',role),('password',{'admin':'DemoAdmin123!','teacher':'DemoTeacher123!','student':'DemoStudent123!'}[role])]:
                    entries[key].delete(0,'end');entries[key].insert(0,value)
            for role in ('admin','teacher','student'):
                ttk.Button(buttons,text=role.title(),command=lambda r=role:fill(r)).pack(side='left',padx=(0,5))
        entries['name' if setup else 'username'].focus_set()

    def build_shell(self):
        self.clear_root(); self.exam=None
        actor=self.actor
        self.root.title('Assessment workspace')
        self.shell=ttk.Frame(self.root); self.shell.pack(fill='both',expand=True)
        sidebar=tk.Frame(self.shell,bg=DEEP,width=210,padx=18,pady=26)
        sidebar.pack(side='left',fill='y');sidebar.pack_propagate(False)
        label(sidebar,'WORKSPACE',11,'#b9d5c6',DEEP,True).pack(anchor='w',pady=(8,30))
        pages=[('overview','Overview'),('quizzes','Quiz library'),('results','Results')]
        if actor['role']!='student':pages += [('questions','Question bank'),('quality','Quality lab')]
        if actor['role']=='admin':pages += [('users','User management'),('audit','Audit trail'),('backups','Backups & recovery')]
        pages += [('help','Help & guide')]
        self.nav_buttons={}
        for route,title in pages:
            button=tk.Button(sidebar,text=title,anchor='w',relief='flat',borderwidth=0,
                bg=DEEP,fg='white',activebackground=TEAL,activeforeground='white',padx=12,pady=11,
                cursor='hand2',command=self.guard(lambda r=route:self.navigate(r)))
            button.pack(fill='x',pady=2);self.nav_buttons[route]=button
        identity=tk.Frame(sidebar,bg=DEEP);identity.pack(side='bottom',fill='x',pady=12)
        label(identity,actor['name'],11,'white',DEEP,True,wraplength=170).pack(anchor='w')
        label(identity,actor['role'].title(),9,'#b9d5c6',DEEP).pack(anchor='w',pady=4)
        workspace=ttk.Frame(self.shell);workspace.pack(side='left',fill='both',expand=True)
        top=ttk.Frame(workspace,padding=(24,14));top.pack(fill='x')
        label(top,'Your assessment workspace',11,MUTED).pack(side='left')
        ttk.Button(top,text='Sign out',command=self.guard(self.logout)).pack(side='right',padx=(7,0))
        ttk.Button(top,text='Change password',command=self.guard(self.password_dialog)).pack(side='right')
        ttk.Separator(workspace).pack(fill='x')
        self.content=ttk.Frame(workspace,padding=24);self.content.pack(fill='both',expand=True)
        ttk.Label(workspace,textvariable=self.status,style='Muted.TLabel',padding=(24,10)).pack(fill='x',side='bottom')
        self.navigate('overview')

    def navigate(self, route):
        actor=self.actor
        if route in ('users','audit','backups'): require_role(actor,'admin')
        if route in ('questions','quality'): require_role(actor,'admin','teacher')
        if self.exam and self.exam.dirty:
            if not messagebox.askyesno('Unsaved answers','Some answers are not saved. Leave this screen? A local draft may be available to retry.',parent=self.root):return
        self.stop_exam_clock();self.exam=None;self.route=route
        for child in self.content.winfo_children():child.destroy()
        for key,button in self.nav_buttons.items():button.configure(bg=TEAL if key==route else DEEP)
        self.status.set('Ready')
        {'overview':self.overview,'quizzes':self.quizzes_view,'questions':self.questions_view,
         'results':self.results_view,'users':self.users_view,'audit':self.audit_view,
         'backups':self.backups_view,'quality':self.quality_view,'help':self.help_view}[route]()

    def heading(self,title,description):
        label(self.content,title,24,bold=True).pack(anchor='w')
        label(self.content,description,10,MUTED,wraplength=850).pack(anchor='w',pady=(8,18))
        bar=ttk.Frame(self.content);bar.pack(fill='x',pady=(0,14));return bar

    def action_button(self,bar,text,action,primary=False):
        button=ttk.Button(bar,text=text,style='Primary.TButton' if primary else 'TButton',command=self.guard(action))
        button.pack(side='left',padx=(0,7));return button

    def overview(self):
        actor=self.actor
        self.heading('Hello, '+actor['name'].split()[0]+'.','Your quizzes, progress and recent activity in one place.')
        quizzes=self.service.quizzes.list(actor);attempts=self.service.attempts.list(actor)
        complete=[a for a in attempts if a['submitted_at'] is not None]
        average=round(sum(a['score']*100/a['total'] for a in complete)/len(complete),1) if complete else None
        hero=tk.Frame(self.content,bg=PALE,padx=24,pady=22);hero.pack(fill='x',pady=(0,22))
        label(hero,'Make time for your next learning moment.',19,INK,PALE,True,wraplength=750).pack(anchor='w')
        label(hero,'Choose a quiz, follow your progress, and learn from every answer.',11,MUTED,PALE,wraplength=750).pack(anchor='w',pady=10)
        ttk.Button(hero,text='Open quiz library  →',style='Primary.TButton',command=self.guard(lambda:self.navigate('quizzes'))).pack(anchor='w')
        cards=ttk.Frame(self.content);cards.pack(fill='x',pady=(0,22))
        for i,(title,value) in enumerate([('Available quizzes',len(quizzes)),('Attempts',len(attempts)),('Completed',len(complete)),('Average score','—' if average is None else f'{average}%')]):
            cards.columnconfigure(i,weight=1)
            card=tk.Frame(cards,bg=PANEL,padx=16,pady=16);card.grid(row=0,column=i,sticky='nsew',padx=(0,10))
            label(card,title,9,MUTED,PANEL).pack(anchor='w');label(card,str(value),25,INK,PANEL,True).pack(anchor='w',pady=8)
        label(self.content,'Recent activity',13,bold=True).pack(anchor='w',pady=(0,10))
        rows=self.result_rows(attempts[:8])
        self.table=DataTable(self.content,self.result_columns(),rows,self.guard(self.open_result))
        self.table.pack(fill='both',expand=True)

    def search_table(self,bar,columns,rows,on_open=None):
        query=tk.StringVar();entry=ttk.Entry(bar,textvariable=query,width=22);entry.pack(side='right')
        label(bar,'Search ',9,MUTED).pack(side='right')
        holder=ttk.Frame(self.content);holder.pack(fill='both',expand=True)
        def refresh(*_):
            for child in holder.winfo_children():child.destroy()
            term=query.get().casefold()
            filtered=[r for r in rows if term in ' '.join(str(v) for v in r.values()).casefold()]
            self.table=DataTable(holder,columns,filtered,self.guard(on_open) if on_open else None)
            self.table.pack(fill='both',expand=True)
            self.status.set(f'{len(filtered)} record(s)')
        query.trace_add('write',refresh);refresh()

    @staticmethod
    def result_columns():
        return [('id','ID',55),('title','Quiz',240),('name','Student',140),('score_text','Score',100),('state','Status',100),('when','Started',155)]

    @staticmethod
    def result_rows(rows):
        return [dict(a,score_text=f"{a['score']} / {a['total']}" if a['submitted_at'] is not None else '—',
                     state='Completed' if a['submitted_at'] is not None else 'In progress',when=date(a['started_at'])) for a in rows]

    def results_view(self):
        bar=self.heading('Results & progress','Review scores, answer explanations and saved attempts.')
        self.action_button(bar,'Open / resume',self.open_result,True)
        self.action_button(bar,'Export CSV',lambda:self.export('results'))
        self.action_button(bar,'Refresh',lambda:self.navigate('results'))
        self.search_table(bar,self.result_columns(),self.result_rows(self.service.attempts.list(self.actor)),self.open_result)

    def open_result(self):
        record=self.table.selected()
        attempt=self.service.attempts.get(self.actor,record['id'])
        if attempt['submitted_at'] is None and self.actor['role']=='student':self.open_exam(attempt['id'])
        else:self.show_result(attempt)

    def show_result(self,attempt):
        window=tk.Toplevel(self.root);window.title('Attempt review');window.geometry('780x680');window.minsize(600,450)
        window.configure(bg=BG);window.transient(self.root)
        scroller=ScrollFrame(window);scroller.pack(fill='both',expand=True,padx=24,pady=24)
        body=scroller.body
        label(body,attempt['title'],22,bold=True,wraplength=680).pack(anchor='w')
        completed=attempt['submitted_at'] is not None
        summary=(f"{attempt['score']} / {attempt['total']}  ·  {attempt['percent']}%  ·  "+('Passed' if attempt['passed'] else 'Below pass mark')) if completed else 'Attempt in progress — answer key is hidden.'
        label(body,summary,16,TEAL,wraplength=680).pack(anchor='w',pady=15)
        for i,q in enumerate(attempt['questions'],1):
            card=tk.Frame(body,bg=PANEL,padx=16,pady=16);card.pack(fill='x',pady=8)
            label(card,f"{i}. {q['prompt']}",12,INK,PANEL,True,wraplength=650).pack(anchor='w')
            selected=attempt['answers'].get(str(q['id']))
            label(card,'Your answer: '+(q['options'][selected] if selected is not None else 'Unanswered'),10,MUTED,PANEL,wraplength=650).pack(anchor='w',pady=8)
            if completed:
                label(card,'Correct answer: '+q['options'][q['correct']],10,TEAL,PANEL,True,wraplength=650).pack(anchor='w')
                label(card,q.get('explanation','') or 'No additional explanation.',10,MUTED,PANEL,wraplength=650).pack(anchor='w',pady=8)
        ttk.Button(window,text='Close',command=window.destroy).pack(pady=(0,15))

    def export(self,kind):
        data=export_csv(self.service,self.actor,kind)
        path=filedialog.asksaveasfilename(parent=self.root,title='Save CSV',defaultextension='.csv',initialfile=f'{kind}.csv',filetypes=[('CSV files','*.csv')])
        if path:Path(path).write_bytes(data);self.status.set('CSV saved: '+path)

    def audit_view(self):
        require_role(self.actor,'admin')
        bar=self.heading('Audit trail','A read-only history of important actions. Most recent 1,000 events shown.')
        self.action_button(bar,'Export all events',lambda:self.export('audit'))
        self.action_button(bar,'Refresh',lambda:self.navigate('audit'))
        rows=self.service.db.rows('SELECT * FROM audit ORDER BY id DESC LIMIT 1000')
        for r in rows:r['when']=date(r.get('occurred_at'))
        self.search_table(bar,[('id','ID',60),('when','Time',155),('actor','User',120),('action','Action',170),('entity','Record',180),('detail','Details',400)],rows)

    def backups_view(self):
        require_role(self.actor,'admin');data=self.service.backups.list(self.actor)
        bar=self.heading('Backups & recovery','Automatic snapshots every five minutes while the app is running. Keep an external copy for device-loss protection.')
        self.action_button(bar,'Back up now',self.backup_now,True)
        self.action_button(bar,'Save copy',self.copy_backup)
        self.action_button(bar,'Restore selected',self.restore_backup)
        self.action_button(bar,'Refresh',lambda:self.navigate('backups'))
        if data['last_error']:label(self.content,data['last_error'],10,RED,wraplength=800).pack(anchor='w',pady=8)
        rows=[dict(x,when=date(x.get('created_at')),state='Verified' if x['verified'] else 'Invalid',size=f"{x['bytes']/1024:.1f} KB") for x in data['items']]
        self.table=DataTable(self.content,[('file','Backup file',340),('when','Created',160),('reason','Reason',130),('size','Size',100),('state','Status',100)],rows)
        self.table.pack(fill='both',expand=True)

    def backup_now(self):
        self.service.backups.create('manual',self.actor);self.navigate('backups');self.status.set('Verified backup created.')

    def copy_backup(self):
        require_role(self.actor,'admin')
        path=self.service.backups.verified_path(self.table.selected()['file'])
        directory=filedialog.askdirectory(parent=self.root,title='Choose an external backup folder')
        if directory:
            destination=Path(directory)/path.name
            if destination.resolve()==path.resolve():raise AppError('Choose a different folder for the backup copy.')
            if destination.exists() and not messagebox.askyesno('Replace copy?','This backup copy already exists. Replace it?',parent=self.root):return
            shutil.copy2(path,destination);shutil.copy2(path.with_suffix('.json'),destination.with_suffix('.json'))
            self.status.set('Backup and checksum manifest copied together.')

    def restore_backup(self):
        row=self.table.selected()
        confirmation=simpledialog.askstring('Restore backup','This replaces current records and signs everyone out.\nA rollback copy will be retained. Type RESTORE to continue.',parent=self.root)
        if confirmation is None:return
        result=restore(self.service.backups,self.actor,{'file':row['file'],'confirmation':confirmation})
        self.session.token=None;self.login_screen();messagebox.showinfo('Restore complete',result['message'],parent=self.root)

    def password_dialog(self):
        self.actor
        def save(data):
            self.service.auth.change_password(self.actor,data)
            self.session.token=None
            # Allow the dialog to destroy itself before rebuilding its parent.
            self.root.after_idle(self.login_screen)
        FormDialog(self,'Change password',[('current','Current password','password'),('password','New password (10+ characters, letter and number)','password')],{},save)

    def logout(self):
        if self.exam and self.exam.dirty:
            if not messagebox.askyesno('Unsaved answers','Some answers are not saved. Sign out anyway?',parent=self.root):return
        self.session.logout();self.login_screen()

    def help_view(self):
        self.heading('Help & guide','Practical steps for using the desktop application.')
        scroller=ScrollFrame(self.content);scroller.pack(fill='both',expand=True)
        topics=[('Run an assessment','Teacher: create questions, create a quiz, select its questions, then publish. Student: select the quiz and choose Start / resume. One attempt per student is allowed.'),
        ('Save and resume','Each answer is saved immediately. If saving fails, keep the app open and choose Retry save. A local draft can recover pending answers after restarting. The original deadline keeps running. Use one app window per attempt.'),
        ('Review results','Open Results to review submitted scores and explanations. Students see only their own results. Faculty can review all attempts. Export CSV opens in spreadsheet software.'),
        ('Edit or delete records','Unpublish quizzes before editing their linked questions. Once attempts exist, only the quiz status can change. Archive used quizzes and deactivate users with history.'),
        ('Recover data','Administrators can create, copy and restore backups. Save copy includes the SQLite file and checksum manifest. For a database that cannot start, stop the app and use scripts/recover_database.py as described in the manual.'),
        ('Quality tools','Record actual defects separately from illustrative demo examples. FMEA calculates S × O × D; residual values are estimates. Complete PDCA with real evidence. Pareto and fishbone diagrams are generated by Matplotlib.'),
        ('Account access','An administrator can set a new password in User management. If all administrators lose access, stop the app and run python scripts/reset_admin.py locally.'),
        ('Desktop scope','This edition runs directly in Python with Tkinter and SQLite on one computer. It does not expose an online service. For a classroom demonstration, sign out and switch roles on the same computer. Users with filesystem access can access the database; use a trusted computer.')]
        for title,text in topics:
            label(scroller.body,title,13,bold=True).pack(anchor='w',pady=(15,6))
            label(scroller.body,text,11,MUTED,wraplength=760).pack(anchor='w')

    def close(self):
        if self.exam and self.exam.dirty:
            if not messagebox.askyesno('Unsaved answers','Some answers are still pending. Close the app? A local draft may be available when you reopen.',parent=self.root):return
        self.stop_exam_clock()
        try:
            self.session.logout();self.service.close()
        except Exception as error:
            messagebox.showwarning('Shutdown notice',self.error_text(error),parent=self.root)
        finally:self.root.destroy()
