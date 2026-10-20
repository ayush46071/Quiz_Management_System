"""Native quality records, SQC charts and process reference diagrams."""
import base64
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from quizcore.config import ROOT
from quizcore.validation import require_role
from .widgets import BG, MUTED, label, DataTable, FormDialog, ScrollFrame


class QualityMixin:
    def quality_view(self):
        require_role(self.actor,'admin','teacher')
        self.quality_kind=getattr(self,'quality_kind','defects')
        bar=self.heading('Quality lab','Record evidence, prioritize risks and track improvements.')
        for kind,title in [('defects','Defects'),('fmea','FMEA'),('pdca','PDCA')]:
            self.action_button(bar,title,lambda k=kind:self.set_quality_tab(k),kind==self.quality_kind)
        chartbar=ttk.Frame(self.content);chartbar.pack(fill='x',pady=(0,12))
        self.chart_source=tk.StringVar(value='Observed')
        ttk.Combobox(chartbar,textvariable=self.chart_source,values=('Observed','Illustrative'),state='readonly',width=13).pack(side='left',padx=(0,7))
        self.action_button(chartbar,'Pareto',lambda:self.chart('pareto'))
        self.action_button(chartbar,'Fishbone',lambda:self.chart('fishbone'))
        self.action_button(chartbar,'SIPOC',lambda:self.diagram('sipoc.png'))
        self.action_button(chartbar,'CTQ',lambda:self.diagram('ctq.png'))
        buttons=ttk.Frame(self.content);buttons.pack(fill='x',pady=(0,12))
        self.action_button(buttons,'Add record',lambda:self.quality_editor(),True)
        self.action_button(buttons,'Edit selected',lambda:self.quality_editor(self.table.selected()))
        self.action_button(buttons,'Delete',self.delete_quality)
        self.action_button(buttons,'Export CSV',lambda:self.export(self.quality_kind))
        columns={
            'defects':[('id','ID',50),('title','Defect',280),('category','Category',140),('occurrences','Count',70),('severity','Severity',70),('status','Status',100),('source','Source',100)],
            'fmea':[('id','ID',50),('failure','Failure mode',280),('severity','S',50),('occurrence','O',50),('detection','D',50),('rpn','RPN',70),('residual_rpn','Target RPN',90),('owner','Owner',150)],
            'pdca':[('id','ID',50),('title','Improvement',370),('status','Stage',100),('owner','Owner',140)]}
        rows=self.service.quality.read(self.actor)[self.quality_kind]
        self.search_table(buttons,columns[self.quality_kind],rows,lambda:self.quality_editor(self.table.selected()))

    def set_quality_tab(self,kind):
        self.quality_kind=kind;self.navigate('quality')

    def quality_editor(self,row=None):
        require_role(self.actor,'admin','teacher');kind=self.quality_kind
        if kind=='defects':
            fields=[('title','Defect title','entry'),('category','Category',('People','Process','Software Code','Infrastructure')),
                ('severity','Severity (1–10)','entry'),('occurrences','Occurrence count','entry'),('status','Status',('Open','In progress','Resolved')),
                ('source','Evidence source',('Observed','Illustrative')),('evidence','Reproduction steps, expected/actual result and evidence','text')]
            initial={'severity':3,'occurrences':1,'status':'Open','source':'Observed','category':'Software Code'}
        elif kind=='fmea':
            fields=[(k,caption,'text' if k!='owner' else 'entry') for k,caption in [('failure','Failure mode'),('effect','Effect'),('cause','Cause'),('control','Current control'),('action','Recommended action'),('owner','Owner')]]
            fields += [(k,caption+' (1–10)','entry') for k,caption in [('severity','Severity'),('occurrence','Occurrence'),('detection','Detection difficulty'),('residual_s','Target severity'),('residual_o','Target occurrence'),('residual_d','Target detection')]]
            initial={k:3 for k in ('severity','occurrence','detection','residual_s','residual_o','residual_d')}
        else:
            fields=[('title','Improvement title','entry'),('owner','Owner','entry'),('status','Stage',('Plan','Do','Check','Act','Complete')),
                ('plan','Plan — target and proposed action','text'),('do_text','Do — changes actually made','text'),
                ('check_text','Check — measured evidence','text'),('act','Act — standardize or revise','text')]
            initial={'status':'Plan'}
        if row:initial.update(row)
        def save(data):
            self.service.quality.save(self.actor,kind,data,row['id'] if row else None);self.navigate('quality')
        FormDialog(self,('Edit ' if row else 'Add ')+{'defects':'defect','fmea':'FMEA record','pdca':'PDCA cycle'}[kind],fields,initial,save)

    def delete_quality(self):
        row=self.table.selected()
        if messagebox.askyesno('Delete quality record?',f"Delete record #{row['id']}?",parent=self.root):
            self.service.quality.delete(self.actor,self.quality_kind,row['id']);self.navigate('quality')

    def chart(self,kind):
        require_role(self.actor,'admin','teacher')
        try:
            from quizcore.charts import render_chart
            image=render_chart(kind,self.service.quality.read(self.actor)['defects'],self.chart_source.get())
        except ImportError:
            from quizcore.validation import AppError
            raise AppError('Install Matplotlib in this environment: python -m pip install -r requirements.txt') from None
        self.show_image(image,kind.title()+' chart',kind+'.png')

    def diagram(self,name):
        require_role(self.actor,'admin','teacher')
        self.show_image((ROOT/'assets'/name).read_bytes(),name.split('.')[0].upper(),name)

    def show_image(self,data,title,filename):
        window=tk.Toplevel(self.root);window.title(title);window.geometry('1000x700');window.configure(bg=BG);window.transient(self.root)
        scroller=ScrollFrame(window);scroller.pack(fill='both',expand=True,padx=18,pady=18)
        photo=tk.PhotoImage(master=window,data=base64.b64encode(data).decode())
        factor=max(1,(photo.width()+929)//930)
        if factor>1:photo=photo.subsample(factor)
        image_label=tk.Label(scroller.body,image=photo,bg='white');image_label.image=photo;image_label.pack(fill='both',expand=True)
        def save():
            target=filedialog.asksaveasfilename(parent=window,initialfile=filename,defaultextension='.png',filetypes=[('PNG image','*.png')])
            if target:Path(target).write_bytes(data)
        buttons=ttk.Frame(window,padding=15);buttons.pack(fill='x')
        ttk.Button(buttons,text='Save full-resolution PNG',command=self.guard(save)).pack(side='left')
        ttk.Button(buttons,text='Close',command=window.destroy).pack(side='right')
