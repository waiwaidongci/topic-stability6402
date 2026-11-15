from sqlalchemy import select,func
from fastapi import HTTPException
from src.models import Corpus,TopicRun,RunDocument
from src.constants.enums import RunStatus
from src.utils.serialize import row
from .audit import record

SUMMARY_KEYS=('fingerprint','k','repeats','reference_seed','effective_documents','excluded_count','vocabulary_size','idf_n_documents','mean_alignment_similarity','baseline_relative_error')

def _summarize(result):return {k:result[k] for k in SUMMARY_KEYS if k in result}

def list_runs(db):
 # 列表只带摘要：首页与队列不一次取回全量逐篇明细
 return [dict(row(x),result=_summarize(x.result or {})) for x in db.scalars(select(TopicRun).order_by(TopicRun.id.desc()))]

def get_run(db,id):
 obj=db.get(TopicRun,id)
 if not obj:raise HTTPException(404,'主题运行不存在')
 return obj

def create_run(db,data,user):
 if not db.get(Corpus,data.corpus_id):raise HTTPException(404,'语料不存在')
 obj=TopicRun(corpus_id=data.corpus_id,name=data.name,config=data.model_dump(exclude={'name','corpus_id'}),creator_id=user.id);db.add(obj);db.commit()
 from src.worker import analyze_run
 try:analyze_run.delay(obj.id)
 except Exception:obj.status=RunStatus.FAILED;obj.error='队列不可用';db.commit();raise HTTPException(503,obj.error)
 record(db,user.email,'topic.queued',{'run_id':obj.id});return row(obj)

def page_run_documents(db,id,status,reference,page,page_size):
 run=db.get(TopicRun,id)
 if not run:raise HTTPException(404,'主题运行不存在')
 if run.status!=RunStatus.SUCCEEDED:raise HTTPException(409,'主题册未成形：仅成功运行提供逐篇激活与排除明细')
 q=select(RunDocument).where(RunDocument.run_id==id)
 if status in ('kept','excluded'):q=q.where(RunDocument.status==status)
 if reference:q=q.where(RunDocument.reference.startswith(reference,autoescape=True))
 total=db.scalar(select(func.count()).select_from(q.subquery()))
 items=[_payload(d) for d in db.scalars(q.order_by(RunDocument.reference).offset((page-1)*page_size).limit(page_size))]
 return {'total':total,'page':page,'page_size':page_size,'items':items}

def _payload(d):
 activations=d.activations;relative=None
 if activations:
  relative=[]
  for row_values in activations:
   total=sum(row_values);relative.append([x/total for x in row_values] if total>1e-14 else None)
 return {'reference':d.reference,'title':d.title,'status':d.status,'reason':d.reason,'activations':activations,'relative_activations':relative}
