"""Native create/read/update/delete workflows."""
import tkinter as tk
from tkinter import ttk, messagebox
from .widgets import FormDialog, label, MUTED
from quizcore.validation import require_role, AppError


class EditorsMixin:
    def questions_view(self):
        require_role(self.actor,'admin','teacher')
        bar=self.heading('Question bank','Write four clear options, choose one correct answer and add an explanation.')
        self.action_button(bar,'Add question',lambda:self.question_editor(),True)
        self.action_button(bar,'Edit selected',lambda:self.question_editor(self.table.selected()))
        self.action_button(bar,'Delete',lambda:self.delete_record('questions'))
        rows=self.service.questions.list(self.actor)
        for q in rows:q['summary']=q['prompt'].replace('\n',' ')[:160]
        self.search_table(bar,[('id','ID',55),('summary','Question',440),('category','Category',150),('points','Points',65)],rows,lambda:self.question_editor(self.table.selected()))

    def question_editor(self,row=None):
        require_role(self.actor,'admin','teacher')
        initial=dict(row or {'category':'General','points':1,'correct':0})
        for i,value in enumerate(initial.get('options',['','','',''])):initial[f'option{i}']=value
        initial['correct_label']='ABCD'[initial['correct']]
        fields=[('prompt','Question','text')]+[(f'option{i}',f'Option {c}','entry') for i,c in enumerate('ABCD')]+[
            ('correct_label','Correct answer',list('ABCD')),('category','Category','entry'),('points','Points (1–100)','entry'),('explanation','Explanation','text')]
        def save(data):
            data['options']=[data.pop(f'option{i}') for i in range(4)]
            data['correct']='ABCD'.index(data.pop('correct_label'))
            self.service.questions.save(self.actor,data,row['id'] if row else None)
            self.navigate('questions')
        FormDialog(self,'Edit question' if row else 'Add question',fields,initial,save)

    def quizzes_view(self):
        actor=self.actor;student=actor['role']=='student'
        bar=self.heading('Quiz library','Select a quiz to begin, resume, or review your result.' if student else 'Build assessments from your question bank and publish when ready.')
        if student:self.action_button(bar,'Start / resume / review',self.start_selected_quiz,True)
        else:
            self.action_button(bar,'Create quiz',lambda:self.quiz_editor(),True)
            self.action_button(bar,'Edit selected',lambda:self.quiz_editor(self.table.selected()))
            self.action_button(bar,'Delete',lambda:self.delete_record('quizzes'))
        self.action_button(bar,'Refresh',lambda:self.navigate('quizzes'))
        rows=self.service.quizzes.list(actor)
        for q in rows:
            q['progress']='Completed' if q['attempt'] and q['attempt']['submitted_at'] is not None else ('In progress' if q['attempt'] else 'Not started')
        columns=[('id','ID',55),('title','Quiz',300),('question_count','Questions',90),('duration','Minutes',80),('pass_percent','Pass %',75)]
        columns += [('progress','Your progress',130)] if student else [('status','Status',100)]
        self.search_table(bar,columns,rows,self.start_selected_quiz if student else lambda:self.quiz_editor(self.table.selected()))

    def quiz_editor(self,row=None):
        require_role(self.actor,'admin','teacher')
        questions=self.service.questions.list(self.actor)
        if not questions:raise AppError('Add questions to the question bank first.')
        initial=dict(row or {'duration':10,'pass_percent':60,'status':'draft'})
        original=list(initial.get('question_ids',[]))
        fields=[('title','Quiz title','entry'),('description','Instructions','text'),('duration','Duration in minutes (1–180)','entry'),
                ('pass_percent','Pass percentage (0–100)','entry'),('status','Publication status',('draft','published','archived'))]
        def extra(parent):
            label(parent,'Select up to 100 questions',12,bold=True).pack(anchor='w',pady=(18,6))
            label(parent,'Quizzes with attempts allow only a status change.',9,MUTED,wraplength=610).pack(anchor='w',pady=(0,8))
            selected={}
            for q in questions:
                variable=tk.BooleanVar(value=q['id'] in original);selected[q['id']]=variable
                ttk.Checkbutton(parent,text=f"#{q['id']} · {q['prompt'].replace(chr(10),' ')[:85]} ({q['points']} pt)",variable=variable).pack(anchor='w',fill='x')
            def read():
                # Preserve existing order when changing status on a used quiz.
                ids=[qid for qid in original if qid in selected and selected[qid].get()]
                ids += [qid for qid,var in selected.items() if var.get() and qid not in ids]
                return {'question_ids':ids}
            return read
        def save(data):
            self.service.quizzes.save(self.actor,data,row['id'] if row else None)
            self.navigate('quizzes')
        FormDialog(self,'Edit quiz' if row else 'Create quiz',fields,initial,save,extra)

    def users_view(self):
        require_role(self.actor,'admin')
        bar=self.heading('User management','Create accounts, assign roles, reset passwords or deactivate access.')
        self.action_button(bar,'Add user',lambda:self.user_editor(),True)
        self.action_button(bar,'Edit selected',lambda:self.user_editor(self.table.selected()))
        self.action_button(bar,'Delete',lambda:self.delete_record('users'))
        rows=self.service.users.list(self.actor)
        for row in rows:row['state']='Active' if row['active'] else 'Inactive'
        self.search_table(bar,[('id','ID',55),('name','Full name',250),('username','Username',180),('role','Role',100),('state','Status',100)],rows,lambda:self.user_editor(self.table.selected()))

    def user_editor(self,row=None):
        require_role(self.actor,'admin')
        initial=dict(row or {'role':'student','active':1})
        initial['state']='Active' if initial['active'] else 'Inactive'
        fields=[('name','Full name','entry'),('username','Username (3–40 characters)','entry'),
                ('role','Role',('student','teacher','admin')),('state','Status',('Active','Inactive')),
                ('password','New password (leave blank to keep existing)' if row else 'Password (10+ characters, letter and number)','password')]
        def save(data):
            data['active']=1 if data.pop('state')=='Active' else 0
            self.service.users.save(self.actor,data,row['id'] if row else None)
            if self.service.auth.session(self.session.token) is None:
                self.session.token=None;self.root.after_idle(self.login_screen)
            else:self.navigate('users')
        FormDialog(self,'Edit user' if row else 'Add user',fields,initial,save)

    def delete_record(self,kind):
        row=self.table.selected()
        if messagebox.askyesno('Delete record?',f"Delete selected {kind.rstrip('s')} #{row['id']}? This cannot be undone from this screen.",parent=self.root):
            getattr(self.service,kind).delete(self.actor,row['id']);self.navigate(kind)

    def start_selected_quiz(self):
        row=self.table.selected();require_role(self.actor,'student')
        if not row['attempt']:
            if not messagebox.askyesno('Start quiz?',f"{row['title']}\n\nThe {row['duration']}-minute timer starts now. One attempt is allowed.",parent=self.root):return
        attempt=self.service.attempts.start(self.actor,row['id'])
        if attempt['submitted_at'] is None:self.open_exam(attempt['id'])
        else:self.show_result(attempt)
