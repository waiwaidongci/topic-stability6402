import hashlib,json
from src.constants.vocabulary import WHITELIST

def _doc_fragment(d):
 return json.dumps({'id':d['id'],'reference':d['reference'],'title':d['title'],'tokens_text':d['tokens_text']},sort_keys=True,allow_nan=False,separators=(',',':'))

def _parts(corpus,config):
 head={'algorithm':'whitespace-tfidf-nmf-reference-hungarian-v1','config':config,'corpus':{k:corpus[k] for k in ('id','name','filename','description')}}
 prefix='{'+json.dumps(head,sort_keys=True,allow_nan=False,separators=(',',':'))[1:-1]+',"documents":['
 suffix='],"whitelist":'+json.dumps(list(WHITELIST),allow_nan=False,separators=(',',':'))+'}'
 return prefix,suffix

def fingerprint(corpus,documents,config):
 payload={'corpus':{k:corpus[k] for k in ('id','name','filename','description')},'documents':sorted([{'id':d['id'],'reference':d['reference'],'title':d['title'],'tokens_text':d['tokens_text']} for d in documents],key=lambda x:x['reference']),'config':config,'whitelist':list(WHITELIST),'algorithm':'whitespace-tfidf-nmf-reference-hungarian-v1'}
 return hashlib.sha256(json.dumps(payload,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()

class StreamingFingerprint:
 # 与 fingerprint() 字节级一致的流式版本：文档按 reference 升序逐篇喂入，不驻留全量明细
 def __init__(self,corpus,config):
  self._prefix,self._suffix=_parts(corpus,config);self._hash=hashlib.sha256(self._prefix.encode());self._first=True
 def add(self,document):
  fragment=_doc_fragment(document)
  self._hash.update((fragment if self._first else ','+fragment).encode());self._first=False
 def hexdigest(self):
  final=self._hash.copy();final.update(self._suffix.encode());return final.hexdigest()
