"""Matplotlib SQC graphics generated from the checksheet, never fabricated."""
import io
import threading
from collections import Counter

CHART_LOCK=threading.Lock()

def render_chart(kind,defects,scope="Observed"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows=[d for d in defects if d["source"]==scope]
    with CHART_LOCK:
        fig,ax=plt.subplots(figsize=(11,5.6),layout="constrained")
        fig.patch.set_facecolor("#f8fafc")
        ax.set_facecolor("#f8fafc")
        if kind=="pareto":
            counts=Counter()
            for row in rows: counts[row["title"]] += row["occurrences"]
            items=counts.most_common()
            ax.set_title(f"Pareto analysis • {scope.lower()} defects",loc="left",fontweight="bold",fontsize=16,pad=18)
            if not items:
                ax.text(.5,.5,"No defects recorded in this source category.\nAdd checksheet entries to generate the analysis.",ha="center",va="center",transform=ax.transAxes)
                ax.set_axis_off()
            else:
                import textwrap
                labels=["\n".join(textwrap.wrap(k,22)) for k,_ in items]
                vals=[v for _,v in items]
                cumulative=[]; total=sum(vals); running=0
                for v in vals: running+=v; cumulative.append(running/total*100)
                ax.bar(range(len(vals)),vals,color="#0f766e",width=.62)
                ax.set_xticks(range(len(vals)),labels,fontsize=9)
                ax.set_ylabel("Occurrences")
                ax.set_ylim(0,max(vals)*1.2)
                ax.spines[["top","right"]].set_visible(False)
                ax2=ax.twinx()
                ax2.plot(range(len(vals)),cumulative,color="#e08631",marker="o",linewidth=2)
                ax2.axhline(80,color="#64748b",linestyle="--",linewidth=1)
                ax2.set_ylim(0,110); ax2.set_ylabel("Cumulative percentage")
                for i,v in enumerate(vals): ax.text(i,v+max(vals)*.025,str(v),ha="center",fontsize=10)
                ax2.spines["top"].set_visible(False)
        elif kind=="fishbone":
            ax.set_title("Root causes of unreliable quiz delivery",loc="left",fontweight="bold",fontsize=16,pad=18)
            ax.set_xlim(0,12); ax.set_ylim(-3.5,3.5); ax.axis("off")
            ax.annotate("",xy=(10,0),xytext=(.3,0),arrowprops=dict(arrowstyle="->",lw=3,color="#0f766e"))
            ax.text(10.15,0,"Unreliable\nquiz\ndelivery",va="center",fontweight="bold",fontsize=12)
            groups=[(3,2.6,"People",["Repeated submit clicks","Unfamiliar restore process"]),(7.5,2.6,"Process",["No restore drill","Unreviewed question changes"]),(3,-2.6,"Software Code",["Missing validation or roles","Mutable answer key"]),(7.5,-2.6,"Infrastructure",["App or power interruption","Disk full or device loss"])]
            for x,y,title,causes in groups:
                ax.plot([x,x+1.5],[y,0],color="#64748b",lw=1.8)
                ax.text(x-1.5,y+(0.25 if y>0 else -0.3),title,fontsize=12,fontweight="bold",color="#0f766e")
                for j,cause in enumerate(causes):
                    yy=y*(.7-.23*j)
                    ax.text(x-1.6,yy,cause,fontsize=9.5,va="center")
            ax.text(.1,-3.4,"Cause hypotheses for investigation; validated causes must be linked to a defect and test.",fontsize=9,color="#475569")
        else:
            raise ValueError("Unknown chart")
        buffer=io.BytesIO()
        fig.savefig(buffer,format="png",dpi=170)
        plt.close(fig)
        return buffer.getvalue()
