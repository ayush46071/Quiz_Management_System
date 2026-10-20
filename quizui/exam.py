"""Timed assessment, autosave feedback and restart recovery in native widgets."""
import time
import tkinter as tk
from tkinter import ttk, messagebox
from .model import ExamSession
from .widgets import ScrollFrame, label, BG, PANEL, INK, MUTED, TEAL, PALE, RED
from quizcore.validation import AppError, require_role


class ExamMixin:
    def stop_exam_clock(self):
        if self.exam_job is not None:
            self.root.after_cancel(self.exam_job);self.exam_job=None

    def open_exam(self,attempt_id):
        require_role(self.actor,'student')
        self.stop_exam_clock()
        self.exam=ExamSession(self.session,attempt_id)
        if self.exam.attempt['submitted_at'] is not None:
            attempt=self.exam.attempt;self.exam=None;self.show_result(attempt);return
        warning=''
        try:
            if self.exam.recover():warning='Recovered a pending local draft. Choose Retry save to confirm it.'
        except AppError as error:warning=error.message
        for child in self.content.winfo_children():child.destroy()
        self.route='attempt';self.question_index=0
        bar=self.heading(self.exam.attempt['title'],'Each answer is saved as you choose it. The deadline continues if you close the app.')
        self.action_button(bar,'Retry save',self.retry_answers)
        self.action_button(bar,'Reload saved answers',self.reload_answers)
        split=ttk.Frame(self.content);split.pack(fill='both',expand=True)
        split.columnconfigure(0,weight=1);split.columnconfigure(1,weight=0);split.rowconfigure(0,weight=1)
        left=ttk.Frame(split);left.grid(row=0,column=0,sticky='nsew',padx=(0,20))
        scroll=ScrollFrame(left);scroll.pack(fill='both',expand=True)
        self.question_body=scroll.body
        controls=ttk.Frame(left);controls.pack(fill='x',pady=12)
        self.previous=ttk.Button(controls,text='← Previous',command=self.guard(lambda:self.pick_question(self.question_index-1)))
        self.previous.pack(side='left')
        self.next_button=ttk.Button(controls,text='Next →',command=self.guard(lambda:self.pick_question(self.question_index+1)))
        self.next_button.pack(side='right')
        right=ttk.Frame(split,width=200);right.grid(row=0,column=1,sticky='nsew');right.grid_propagate(False)
        right.columnconfigure(0,weight=1);right.rowconfigure(4,weight=1)
        label(right,'TIME REMAINING',9,MUTED).grid(row=0,column=0,sticky='w')
        self.timer_var=tk.StringVar();label_timer=ttk.Label(right,textvariable=self.timer_var,font=('Segoe UI',29,'bold'))
        label_timer.grid(row=1,column=0,sticky='w',pady=(5,14));self.timer_label=label_timer
        self.save_var=tk.StringVar(value=warning or 'All answers saved')
        ttk.Label(right,textvariable=self.save_var,wraplength=190).grid(row=2,column=0,sticky='ew',pady=(0,12))
        self.progress=ttk.Progressbar(right,maximum=len(self.exam.attempt['questions']))
        self.progress.grid(row=3,column=0,sticky='ew',pady=(0,12))
        nav=ScrollFrame(right);nav.grid(row=4,column=0,sticky='nsew')
        self.question_buttons=[]
        for i in range(len(self.exam.attempt['questions'])):
            button=tk.Button(nav.body,text=str(i+1),width=3,relief='flat',bg=PANEL,fg=INK,
                command=self.guard(lambda n=i:self.pick_question(n)))
            button.grid(row=i//4,column=i%4,padx=2,pady=3,ipady=6);self.question_buttons.append(button)
        ttk.Button(right,text='Submit quiz',style='Primary.TButton',command=self.guard(self.submit_answers)).grid(row=5,column=0,sticky='ew',pady=(15,0))
        self.pick_question(0)
        self.exam_tick()

    def pick_question(self,index):
        if not self.exam:return
        questions=self.exam.attempt['questions']
        if not 0<=index<len(questions):return
        self.question_index=index;q=questions[index]
        for child in self.question_body.winfo_children():child.destroy()
        label(self.question_body,f"QUESTION {index+1} OF {len(questions)}  ·  {q['points']} POINT(S)",9,TEAL,bold=True).pack(anchor='w',pady=12)
        prompt=label(self.question_body,q['prompt'],17,bold=True,wraplength=500)
        prompt.pack(anchor='w',fill='x',pady=(6,22))
        self.answer_var=tk.IntVar(value=self.exam.attempt['answers'].get(str(q['id']),-1))
        options=[]
        for i,text in enumerate(q['options']):
            button=tk.Radiobutton(self.question_body,text=f"{'ABCD'[i]}.  {text}",variable=self.answer_var,value=i,
                command=lambda qid=q['id']:self.choose_answer(qid),bg=PANEL,fg=INK,activebackground=PALE,
                selectcolor=PALE,anchor='w',justify='left',wraplength=430,padx=13,pady=16,relief='groove',borderwidth=1,
                font=('Segoe UI',11),highlightcolor=TEAL)
            button.pack(fill='x',pady=7,padx=(0,8));options.append(button)
        def resize(event):
            if prompt.winfo_exists():prompt.configure(wraplength=max(220,event.width-20))
            for button in options:
                if button.winfo_exists():button.configure(wraplength=max(190,event.width-65))
        self.question_body.bind('<Configure>',resize)
        self.previous.configure(state='normal' if index else 'disabled')
        self.next_button.configure(state='normal' if index<len(questions)-1 else 'disabled')
        self.update_question_map()

    def update_question_map(self):
        if not self.exam:return
        answers=self.exam.attempt['answers'];self.progress['value']=len(answers)
        for i,(q,button) in enumerate(zip(self.exam.attempt['questions'],self.question_buttons)):
            current=i==self.question_index;answered=str(q['id']) in answers
            button.configure(bg=TEAL if current else PALE if answered else PANEL,fg='white' if current else INK)

    def choose_answer(self,qid):
        try:
            result=self.exam.choose(qid,self.answer_var.get())
            self.save_var.set(self.exam.draft_error or 'All answers saved')
            if result['submitted_at'] is not None:self.finish_exam(result);return
        except Exception as error:
            self.save_var.set('Not saved — choose Retry save.\n'+self.error_text(error))
        self.update_question_map()

    def retry_answers(self):
        result=self.exam.save()
        self.save_var.set(self.exam.draft_error or 'All answers saved')
        if result['submitted_at'] is not None:self.finish_exam(result)

    def reload_answers(self):
        if not messagebox.askyesno('Reload saved answers?','Discard pending local changes and load the database copy?',parent=self.root):return
        result=self.exam.reload()
        if result['submitted_at'] is not None:self.finish_exam(result);return
        self.save_var.set('Saved answers reloaded');self.pick_question(self.question_index)

    def submit_answers(self):
        attempt=self.exam.attempt;remaining=len(attempt['questions'])-len(attempt['answers'])
        if not messagebox.askyesno('Submit quiz?',f'{remaining} question(s) unanswered. Submit now? The submitted result is final.',parent=self.root):return
        self.finish_exam(self.exam.save(submit=True))

    def finish_exam(self,attempt):
        self.stop_exam_clock();self.exam=None
        self.navigate('results');self.show_result(attempt)

    def exam_tick(self):
        self.exam_job=None
        if self.exam is None:return
        remaining=max(0,self.exam.attempt['deadline']-int(time.time()))
        self.timer_var.set(f'{remaining//60:02d}:{remaining%60:02d}')
        self.timer_label.configure(foreground=RED if remaining<=60 else TEAL)
        if remaining==0:
            try:
                # get() grades only acknowledged answers when time has elapsed.
                result=self.service.attempts.get(self.actor,self.exam.attempt['id'])
                self.finish_exam(result);return
            except Exception as error:self.save_var.set(self.error_text(error))
        self.exam_job=self.root.after(1000,self.exam_tick)
