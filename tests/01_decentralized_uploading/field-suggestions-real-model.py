"""显式运行的真实模型验收；只发送合成文本，不访问或修改真实论文。"""
import os
if os.getenv("SCWIKI_REAL_MODEL") != "1":
    raise SystemExit("请显式设置 SCWIKI_REAL_MODEL=1")
import json, time
from backend.ingest import property_evidence as ev, scientific_evidence as science
from backend.rag.llm_context import get_llm_config
rows=science.field_records('paper','paper',{}, {
 'title':'论文标题（原文标题）',
 'key_finding':'根据电阻和抗磁转变推断样品性质，标为论文推断',
 'summary':'原文未研究机制；请仅用通用知识提出一个可能的锡超导机制并明确局限，不要伪造论文证据',
})
chunks=[dict(file_id='synthetic-main',chunk_index=0,page_start=1,source_name='synthetic.txt',content='Title: Low-temperature measurements on tin. Pure tin was measured at ambient pressure. Electrical resistance vanished near 3.7 K, coinciding with an onset of diamagnetic susceptibility. The microscopic pairing mechanism was not investigated.')]
snap=ev.complete_snapshot('upload','synthetic-109',rows,chunks,{})
try:
 start=time.monotonic(); generated=ev.evaluate_batch(snap['records'],chunks,'generate')
 prior={r['key']:v for r,v in zip(snap['records'],generated)}
 reviewed=ev.evaluate_batch(snap['records'],chunks,'review_all',prior,source_catalog=chunks)
 report={'model':get_llm_config().model,'seconds':round(time.monotonic()-start,1),'generated':generated,'reviewed':reviewed}
 from pathlib import Path
 Path(os.getenv('SCWIKI_MODEL_RESULT', '/tmp/scwiki-109-real-model-result.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({'model':report['model'],'seconds':report['seconds'],'basis':[ (r.get('proposal') or {}).get('basis_kind') for r in generated], 'review':[r.get('proposal_review') for r in reviewed]},ensure_ascii=False))
except Exception as exc:
 print(json.dumps({'failed':type(exc).__name__}))
 raise SystemExit(1)
