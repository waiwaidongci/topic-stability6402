import json
import os
from collections import Counter
import numpy as np
from src.constants.vocabulary import WHITELIST

_ALLOWED=set(WHITELIST)

def whitelist_tokens(text):return [w for w in text.split() if w in _ALLOWED]

def vocabulary_from_df(df,n,min_df):
 if not isinstance(min_df,int) or min_df<1:raise ValueError('min_df不合法')
 vocabulary=sorted(w for w,count in df.items() if count>=min_df)
 if not vocabulary:raise ValueError('白名单与min_df后词汇为空')
 idf=np.asarray([np.log((1+n)/(1+df[w]))+1 for w in vocabulary])
 return vocabulary,idf

def tfidf_row(tokens,lookup,idf,out):
 # raw TF×idf 写入 out，再 L2 归一；返回该行是否非零（与一次性路径逐位一致）
 out[:]=0.
 for w,count in Counter(tokens).items():
  j=lookup.get(w)
  if j is not None:out[j]=count*idf[j]
 norm=np.linalg.norm(out)
 if norm:out/=norm
 return norm>0

def build_tfidf(documents,min_df):
 # 一次性参考口径：与流式两遍路径共用 vocabulary_from_df/tfidf_row，用于小语料对拍验证
 if not documents or not isinstance(min_df,int) or min_df<1:raise ValueError('语料为空或min_df不合法')
 tokens=[whitelist_tokens(d['tokens_text']) for d in documents]
 df=Counter(w for doc in tokens for w in set(doc));n=len(documents)
 vocabulary,idf=vocabulary_from_df(df,n,min_df);lookup={w:i for i,w in enumerate(vocabulary)};X=np.zeros((n,len(vocabulary)))
 for i,doc in enumerate(tokens):tfidf_row(doc,lookup,idf,X[i])
 kept=np.flatnonzero(np.linalg.norm(X,axis=1)>0);excluded=[{'id':d['id'],'reference':d['reference'],'reason':'白名单后空词' if not tokens[i] else 'min_df后空词'} for i,d in enumerate(documents) if i not in set(kept)]
 return {'X':X[kept],'kept_indices':kept,'excluded':excluded,'vocabulary':vocabulary,'idf':idf.tolist(),'document_frequency':[df[w] for w in vocabulary],'idf_n_documents':n,'parameters':tfidf_parameters(min_df)}

def tfidf_parameters(min_df):
 return {'tokenizer':'str.split whitespace only; exact whitelist match','tf':'raw count','idf':'ln((1+n_documents)/(1+document_frequency))+1','norm':'L2 per document','min_df':min_df,'whitelist':list(WHITELIST),'empty_documents':'excluded from NMF; still counted in IDF n_documents'}

def count_document_frequencies(batches):
 # 第一遍流式：全库 df 统计，不抽样不截断；内存只占词汇表大小
 df=Counter();n=0
 for batch in batches:
  for d in batch:
   n+=1;df.update(set(whitelist_tokens(d['tokens_text'])))
 return df,n

def write_matrix(batches,vocabulary,idf,x_path,disposition_path):
 # 第二遍流式：kept 行紧密写入 X.dat（先按上限分配、结尾截断），处置记录逐行写 jsonl
 # disposition 每行 {"i":id,"r":reference,"t":title,"s":1} 或 {"i":..,"r":..,"t":..,"s":0,"e":reason}
 lookup={w:i for i,w in enumerate(vocabulary)};v=len(vocabulary)
 kept=0;excluded=0;x_sq=0.;total=0;any_nonzero=False
 mm=np.memmap(x_path,dtype='float64',mode='w+',shape=(16,v));capacity=16
 fd=os.open(x_path,os.O_RDWR)
 def grow(need):
  nonlocal mm,capacity
  while capacity<need:capacity*=2
  mm.flush();del mm
  os.ftruncate(fd,capacity*v*8)
  mm=np.memmap(x_path,dtype='float64',mode='r+',shape=(capacity,v))
 with open(disposition_path,'w',encoding='utf-8') as disp:
  for batch in batches:
   for d in batch:
    total+=1;tokens=whitelist_tokens(d['tokens_text'])
    if kept>=capacity:grow(kept+1)
    row=mm[kept]
    nonzero=tfidf_row(tokens,lookup,idf,row)
    if nonzero:
     if not np.isfinite(row).all() or (row<0).any():raise ValueError('NMF矩阵必须有限非负且非空')
     x_sq+=float((row*row).sum());any_nonzero=True;kept+=1
     disp.write(json.dumps({'i':d['id'],'r':d['reference'],'t':d['title'],'s':1},ensure_ascii=False)+'\n')
    else:
     excluded+=1
     disp.write(json.dumps({'i':d['id'],'r':d['reference'],'t':d['title'],'s':0,'e':'白名单后空词' if not tokens else 'min_df后空词'},ensure_ascii=False)+'\n')
 mm.flush();del mm
 os.ftruncate(fd,kept*v*8);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED);os.close(fd)
 if not kept or not any_nonzero:raise ValueError('NMF矩阵必须有限非负且非空')
 return {'kept':kept,'excluded':excluded,'total':total,'x_sq':x_sq}
