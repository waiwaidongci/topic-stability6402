from celery import Celery
from src.config.database import SessionLocal
from src.config.settings import REDIS_URL
from src.models import TopicRun
from src.services.execution import execute_run
app=Celery('topic_stability',broker=REDIS_URL,backend=REDIS_URL)
app.conf.update(task_track_started=True,worker_prefetch_multiplier=1,task_acks_late=True)
@app.task(name='topic.analyze',soft_time_limit=7200,time_limit=7500)
def analyze_run(id):
 with SessionLocal() as db:
  run=db.get(TopicRun,id)
  if not run or run.status=='succeeded':return
  run.status='running';db.commit()
  execute_run(db,run)
