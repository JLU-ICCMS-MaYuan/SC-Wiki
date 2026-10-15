"""独立生成已知解析谱 PDF 与真值，用于自动标定验收而非拟合。"""
from pathlib import Path
import argparse
import json
import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pymupdf


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    f=np.linspace(0,10,201)
    a=.08*f*(1-f/10)
    cumulative=.16*(f-f*f/20)
    h=np.exp(-((f-7)/1.4)**2)
    sulfur=.5*np.exp(-((f-3)/1.2)**2)
    fig,axes=plt.subplots(1,2,figsize=(11,5),layout="constrained")
    ax=axes[0]
    ax.plot(f,h,color="blue",label="H phonon DOS")
    ax.plot(f,sulfur,color="red",ls="--",label="S phonon DOS")
    ax.set(xlabel="Frequency (THz)",ylabel="Phonon DOS (relative)",xlim=(0,10),ylim=(0,1.2),title="KnownState @ 100 GPa")
    ax.legend(loc="upper left",fontsize=8)
    ax=axes[1]
    ax.plot(a,f,color="green",label="alpha^2 F")
    ax.plot(cumulative,f,color="magenta",ls="--",label="lambda")
    ax.set(xlabel="alpha^2 F / lambda (dimensionless)",ylabel="Frequency (THz)",xlim=(0,.9),ylim=(0,10),title="KnownState @ 100 GPa")
    ax.legend(loc="lower right",fontsize=8)
    buffer=io.BytesIO();fig.savefig(buffer,format="png",dpi=120);plt.close(fig)
    doc=pymupdf.open();page=doc.new_page(width=660,height=340)
    page.insert_image(pymupdf.Rect(10,20,650,310),stream=buffer.getvalue())
    page.insert_text((15,325),"Figure 1 | Phonon density of states and Eliashberg spectral function for KnownState at 100 GPa.",fontsize=9)
    doc.save(args.output/"known-spectra.pdf");doc.close()
    (args.output/"truth.json").write_text(json.dumps(dict(frequency_thz=f.tolist(),alpha2f=a.tolist(),cumulative_lambda=cumulative.tolist(),
        lambda_integral=.8,manual_calibration_used=False,independent_source="解析式生成，与提取算法无关"),ensure_ascii=False,indent=2))
    print("generated known-spectra.pdf; analytic lambda=0.8")


if __name__=="__main__":main()
