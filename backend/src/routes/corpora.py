from fastapi import APIRouter,Depends,Query
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.controllers.dependencies import current_user,writers
from src.schemas.corpus import CorpusInput,BatchInput,DocumentPatch
from src.services import corpora
from src.constants.vocabulary import WHITELIST
router=APIRouter()
@router.get('/corpora')
def index(db:Session=Depends(get_db),user=Depends(current_user)):return corpora.list_corpora(db)
@router.post('/corpora',status_code=201)
def create(data:CorpusInput,db:Session=Depends(get_db),user=Depends(writers)):return corpora.create_corpus(db,data,user)
@router.post('/corpora/{id}/batches',status_code=201)
def append(id:int,data:BatchInput,db:Session=Depends(get_db),user=Depends(writers)):return corpora.append_batch(db,id,data,user)
@router.get('/documents')
def documents(corpus_id:int=0,q:str='',page:int=Query(1,ge=1),page_size:int=Query(40,ge=1,le=200),db:Session=Depends(get_db),user=Depends(current_user)):return corpora.page_documents(db,corpus_id,q,page,page_size)
@router.patch('/documents/{id}')
def document(id:int,data:DocumentPatch,db:Session=Depends(get_db),user=Depends(writers)):return corpora.patch_document(db,id,data,user)
@router.get('/whitelist')
def whitelist(user=Depends(current_user)):return list(WHITELIST)
