import json
import shutil
from pathlib import Path
import numpy as np
from sqlalchemy import select,delete,insert
from src.config.database import SessionLocal
from src.config.settings import ARTIFACT_DIR
from src.models import TopicRun,Corpus,TopicProfile,RunDocument
from src.utils.serialize import row
from .corpora import iter_documents
from .analysis import analyze
from .audit import record

PERSIST_BATCH=2000

def _persist_documents(db,run_id,disposition_path,w_paths):
 # 逐篇激活只在全部分析成功后入库；分批 commit，失败路径由 execute_run 整体清除
 matrices=[np.load(p,mmap_mode='r') for p in w_paths]
 buf=[];kept_row=0
 with open(disposition_path,encoding='utf-8') as lines:
  for line in lines:
   d=json.loads(line)
   if d['s']==1:
    activations=[[float(x) for x in W[kept_row]] for W in matrices];kept_row+=1
    buf.append({'run_id':run_id,'document_id':d['i'],'reference':d['r'],'title':d['t'],'status':'kept','reason':None,'activations':activations})
   else:
    buf.append({'run_id':run_id,'document_id':d['i'],'reference':d['r'],'title':d['t'],'status':'excluded','reason':d['e'],'activations':None})
   if len(buf)>=PERSIST_BATCH:db.execute(insert(RunDocument),buf);db.commit();buf=[]
 if buf:db.execute(insert(RunDocument),buf);db.commit()

def execute_run(db,run,actor='worker'):
 workdir=Path(ARTIFACT_DIR)/f'run-{run.id}-work'
 try:
  corpus=row(db.get(Corpus,run.corpus_id))
  with SessionLocal() as scan:
   # 扫描会话提供一致性快照：两遍全库统计读取同一时点的文档
   source=lambda:iter_documents(scan,run.corpus_id)
   result,disposition_path,w_paths=analyze(corpus,source,dict(run.config),workdir)
  _persist_documents(db,run.id,disposition_path,w_paths)
  for p in result['profiles']:
   if not db.scalar(select(TopicProfile).where(TopicProfile.run_id==run.id,TopicProfile.topic_index==p['topic_index'])):db.add(TopicProfile(run_id=run.id,topic_index=p['topic_index'],label=p['label'],weights=p['weights'],mean_similarity=p['mean_similarity']))
  run.result=result;run.status='succeeded';run.error=None;db.commit()
  Path(ARTIFACT_DIR).mkdir(parents=True,exist_ok=True);Path(ARTIFACT_DIR,f'topic-{run.id}.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False))
  record(db,actor,'topic.succeeded',{'run_id':run.id,'repeats':run.config['repeats']})
 except Exception as e:
  db.rollback()
  run=db.get(TopicRun,run.id)
  # 失败不留半份主题册：清除任何已入库的逐篇明细，再标记失败
  db.execute(delete(RunDocument).where(RunDocument.run_id==run.id));db.commit()
  run.status='failed';run.error=str(e)[:1000];db.commit();record(db,actor,'topic.failed',{'run_id':run.id,'error':run.error})
 finally:
  shutil.rmtree(workdir,ignore_errors=True)
