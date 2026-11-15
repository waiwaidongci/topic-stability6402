import json
import numpy as np
from sqlalchemy import select,func
from src.config.database import Base,engine,SessionLocal
from src.models import *
from src.utils.security import hash_password
from src.utils.serialize import row
from src.constants.vocabulary import GROUPS,SHARED
from src.services.execution import execute_run

def seed():
 Base.metadata.create_all(engine)
 with SessionLocal() as db:
  for role,name in [('admin','岑知 · 编辑研究负责人'),('analyst','周字 · 主题研究编辑'),('viewer','林页 · 展签观察员')]:
   email=role+'@zicen.demo'
   if not db.scalar(select(User).where(User.email==email)):db.add(User(email=email,name=name,role=role,password_hash=hash_password('Zicen2026!')))
  db.commit();corpus=db.scalar(select(Corpus).where(Corpus.name=='秋季展签分词摘要 · 360篇'))
  if not corpus:
   corpus=Corpus(name='秋季展签分词摘要 · 360篇',filename='zc-exhibition-tokens-2026.jsonl',description='合成空白分词摘要，4个混合来源主题；含空词、白名单外词和低频词。');db.add(corpus);db.flush();rng=np.random.default_rng(221)
   for i in range(360):
    primary=i%4;secondary=(primary+int(rng.integers(1,4)))%4;tokens=[]
    for j in range(50):
     draw=rng.random();group=GROUPS[primary] if draw<.72 else GROUPS[secondary] if draw<.9 else SHARED[:5];tokens.append(str(rng.choice(group)))
    if i==0:tokens=[]
    elif i==1:tokens=['陌词','占位']
    elif i==2:tokens=['研究']
    elif i==3:tokens+=['矿脉']
    db.add(TokenDocument(corpus_id=corpus.id,reference=f'ZC-{i+1:04d}',title=f'匿名展签摘要{i+1:03d}',tokens_text=' '.join(tokens)))
   db.commit()
  if not db.scalar(select(TopicRun).where(TopicRun.name=='四主题多初始化校对')):
   admin=db.scalar(select(User).where(User.role=='admin'));config={'k':4,'repeats':5,'seed':221,'min_df':2,'max_iter':2000,'tolerance':.0001}
   run=TopicRun(corpus_id=corpus.id,name='四主题多初始化校对',config=config,status='running',creator_id=admin.id);db.add(run);db.flush()
   execute_run(db,run,actor='seed')
   profiles=list(db.scalars(select(TopicProfile).where(TopicProfile.run_id==run.id).order_by(TopicProfile.topic_index)))
   if run.status=='succeeded' and profiles:
    db.add(EditorialNote(run_id=run.id,name='混合展签主题编辑草案',profile_ids=[profiles[0].id],profile_snapshot=[row(profiles[0])],interpretation='词权和相对激活仅作编辑线索，主题需人工命名；初始化稳定不等于语义真值。',next_step='阅读代表文档并与策展编辑核对，再安排展签改稿。',creator_id=admin.id))
   db.add(AuditLog(actor='seed',action='demo.created',detail={'documents':360,'seed':221}));db.commit()
  counts={t.__tablename__:db.scalar(select(func.count()).select_from(t)) for t in [User,Corpus,TokenDocument,TopicRun,TopicProfile,EditorialNote]};print(json.dumps(counts));return counts
if __name__=='__main__':seed()
