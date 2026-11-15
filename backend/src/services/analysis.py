from pathlib import Path
import numpy as np
from .tfidf import count_document_frequencies,vocabulary_from_df,write_matrix,tfidf_parameters
from .factorization import check_matrix,fit_matrix_streaming
from .alignment import align_topics
from .fingerprint import StreamingFingerprint

def analyze(corpus,source_factory,config,workdir):
 # 流式两遍全库统计 + 多次独立初始化；source_factory() 每次返回按 reference 升序的文档批迭代器
 # 文档不重复由 (corpus_id,reference) 唯一约束保证；排序由 reference 列二进制 collation 保证（与 Python 码位一致）
 if not isinstance(config['repeats'],int) or not 5<=config['repeats']<=10:raise ValueError('初始化重复数必须5..10')
 if not isinstance(config['seed'],int) or not 0<=config['seed']<=1000000000:raise ValueError('seed范围不合法')
 workdir=Path(workdir);workdir.mkdir(parents=True,exist_ok=True)
 # 第一遍：全库 df 与冻结输入指纹（不驻留文档）
 fingerprint=StreamingFingerprint(corpus,config)
 def tapped():
  for batch in source_factory():
   for d in batch:fingerprint.add(d)
   yield batch
 df,n=count_document_frequencies(tapped())
 if not n:raise ValueError('语料为空或min_df不合法')
 vocabulary,idf=vocabulary_from_df(df,n,config['min_df'])
 # 第二遍：X 与逐篇处置落盘
 x_path=workdir/'X.dat';disposition_path=workdir/'documents.jsonl'
 stats=write_matrix(source_factory(),vocabulary,idf,x_path,disposition_path)
 X=np.memmap(x_path,dtype='float64',mode='r',shape=(stats['kept'],len(vocabulary)))
 k=config['k'];check_matrix(X,k,config['max_iter'],config['tolerance'],workdir)
 # 独立初始化：每次 W 立即落盘释放，H/误差留内存
 fits=[];w_paths=[]
 for index in range(config['repeats']):
  seed=config['seed']+index
  fit=fit_matrix_streaming(X,stats['x_sq'],k,seed,config['max_iter'],config['tolerance'])
  w_path=workdir/f'W-{index}.npy';np.save(w_path,fit['W']);w_paths.append(w_path)
  fits.append({'H':fit['H'],'iterations':fit['iterations'],'reconstruction_error':fit['reconstruction_error'],'relative_error':fit['relative_error']})
  del fit
 reference=fits[0]['H'];replicates=[]
 for index,fit in enumerate(fits):
  match=align_topics(reference,fit['H']);permutation=match['permutation']
  replicates.append({'index':index,'seed':config['seed']+index,'iterations':fit['iterations'],'reconstruction_error':fit['reconstruction_error'],'relative_error':fit['relative_error'],'H':fit['H'].tolist(),'aligned_H':fit['H'][permutation].tolist(),'alignment':match})
 stability=np.asarray([r['alignment']['similarities'] for r in replicates[1:]])
 profiles=[]
 for topic in range(k):
  weights=reference[topic];order=np.argsort(-weights,kind='stable');profiles.append({'topic_index':topic,'label':f'待命名主题{topic+1:02d}','weights':[{'term':vocabulary[int(i)],'weight':float(weights[i])} for i in order],'mean_similarity':float(stability[:,topic].mean()),'similarities':stability[:,topic].tolist()})
 result={'fingerprint':fingerprint.hexdigest(),'k':k,'repeats':config['repeats'],'reference_repeat':0,'reference_seed':config['seed'],'vocabulary':vocabulary,'vocabulary_size':len(vocabulary),'idf':idf.tolist(),'document_frequency':[df[w] for w in vocabulary],'tfidf_parameters':tfidf_parameters(config['min_df']),'idf_n_documents':n,'effective_documents':stats['kept'],'excluded_count':stats['excluded'],'profiles':profiles,'replicates':replicates,'mean_alignment_similarity':float(stability.mean()),'baseline_relative_error':fits[0]['relative_error'],'interpretation':'K is preselected, not optimized by decreasing reconstruction error. Relative activations are not posterior probabilities. Stability measures seed sensitivity, not semantic truth; editorial names are human input. All repeats refit independently with random init.'}
 return result,disposition_path,w_paths
