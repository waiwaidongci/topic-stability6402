from sqlalchemy import select,func
from fastapi import HTTPException
from src.models import Corpus,TokenDocument
from src.utils.serialize import row
from .audit import record

def list_corpora(db):return [dict(row(c),document_count=db.scalar(select(func.count()).select_from(TokenDocument).where(TokenDocument.corpus_id==c.id))) for c in db.scalars(select(Corpus).order_by(Corpus.id))]

def iter_documents(db,corpus_id,batch=5000):
 # 按 reference 升序流式产出文档批；MySQL 下 reference 列为 utf8mb4_bin，与 Python 码位排序一致
 q=select(TokenDocument).where(TokenDocument.corpus_id==corpus_id).order_by(TokenDocument.reference).execution_options(yield_per=batch)
 buf=[]
 for d in db.scalars(q):
  buf.append({'id':d.id,'reference':d.reference,'title':d.title,'tokens_text':d.tokens_text})
  if len(buf)>=batch:yield buf;buf=[]
 if buf:yield buf

def page_documents(db,corpus_id,q,page,page_size):
 base=select(TokenDocument)
 if corpus_id:base=base.where(TokenDocument.corpus_id==corpus_id)
 if q:base=base.where(TokenDocument.reference.startswith(q,autoescape=True))
 total=db.scalar(select(func.count()).select_from(base.subquery()))
 items=db.scalars(base.order_by(TokenDocument.reference).offset((page-1)*page_size).limit(page_size))
 return {'total':total,'page':page,'page_size':page_size,'items':[row(x) for x in items]}

def create_corpus(db,data,user):
 if db.scalar(select(Corpus).where(Corpus.name==data.name)):raise HTTPException(409,'语料名称已存在')
 obj=Corpus(**data.model_dump(exclude={'documents'}));db.add(obj);db.flush();db.add_all([TokenDocument(corpus_id=obj.id,**d.model_dump()) for d in data.documents]);db.commit();record(db,user.email,'corpus.import',{'corpus_id':obj.id,'documents':len(data.documents)});return row(obj)

def append_batch(db,id,data,user):
 corpus=db.get(Corpus,id)
 if not corpus:raise HTTPException(404,'语料不存在')
 references=[d.reference for d in data.documents]
 if len(set(references))!=len(references):raise HTTPException(422,'批次内reference不可重复')
 existing=set(db.scalars(select(TokenDocument.reference).where(TokenDocument.corpus_id==id,TokenDocument.reference.in_(references))))
 if existing:raise HTTPException(409,'reference已存在于本语料：'+'、'.join(sorted(existing)[:5]))
 db.add_all([TokenDocument(corpus_id=id,**d.model_dump()) for d in data.documents]);db.commit()
 total=db.scalar(select(func.count()).select_from(TokenDocument).where(TokenDocument.corpus_id==id))
 record(db,user.email,'corpus.batch_import',{'corpus_id':id,'imported':len(data.documents),'document_count':total})
 return {'corpus_id':id,'imported':len(data.documents),'document_count':total}

def patch_document(db,id,data,user):
 obj=db.get(TokenDocument,id)
 if not obj:raise HTTPException(404,'文档不存在')
 obj.title=data.title;obj.tokens_text=data.tokens_text;db.commit();record(db,user.email,'document.edit',{'document_id':id});return row(obj)
