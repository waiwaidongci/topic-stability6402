import os
import tempfile
import warnings
import numpy as np
from sklearn.decomposition import NMF
from sklearn.decomposition._nmf import _update_coordinate_descent
from sklearn.exceptions import ConvergenceWarning
from sklearn.utils import check_random_state
from .alignment import normalize_factors

def _matrix_rank(X,tol,workdir):
 # 与 np.linalg.matrix_rank(X,tol=tol) 同一 gesdd 奇异值与 >tol 判定；
 # 大矩阵时把 X 物化为文件支撑的 F 连续副本，直接 dgesdd(overwrite_a)，匿名内存不随语料增长
 if X.nbytes<=64*2**20:return int(np.linalg.matrix_rank(X,tol=tol))
 from scipy.linalg.lapack import dgesdd
 fd,tmp=tempfile.mkstemp(dir=workdir,suffix='.dat');os.close(fd)
 try:
  buf=np.memmap(tmp,dtype='float64',mode='w+',shape=X.shape,order='F');buf[:]=X;buf.flush()
  _,s,_,info=dgesdd(buf,compute_uv=0,overwrite_a=1)
  if info!=0:raise ValueError('SVD秩检验失败')
  del buf
  return int((s>tol).sum())
 finally:
  try:os.unlink(tmp)
  except OSError:pass

def check_matrix(X,k,max_iter,tolerance,workdir=None):
 # K 可行性/秩/迭代参数校验：每次拟合幂等，编排层对同一矩阵只做一次
 X=np.asarray(X,dtype=float)
 if X.ndim!=2 or min(X.shape)<2 or not np.isfinite(X).all() or (X<0).any() or not X.any():raise ValueError('NMF矩阵必须有限非负且非空')
 if not isinstance(k,int) or not 2<=k<=6 or k>min(X.shape) or _matrix_rank(X,1e-10,workdir)<k:raise ValueError('K超出文档/词汇/数值秩；常量或低秩语料不可估计此K')
 if not isinstance(max_iter,int) or max_iter<1 or not np.isfinite(tolerance) or tolerance<=0:raise ValueError('迭代参数不合法')

def fit_matrix(X,k,seed,max_iter,tolerance):
 X=np.asarray(X,dtype=float);check_matrix(X,k,max_iter,tolerance)
 model=NMF(n_components=k,init='random',solver='cd',beta_loss='frobenius',random_state=seed,max_iter=max_iter,tol=tolerance,alpha_W=0.,alpha_H=0.,l1_ratio=0.,shuffle=False)
 with warnings.catch_warnings(record=True) as seen:
  warnings.simplefilter('always',ConvergenceWarning);W=model.fit_transform(X)
 if any(issubclass(w.category,ConvergenceWarning) for w in seen):raise ValueError(f'未收敛：seed={seed} max_iter={max_iter}；增加上限后重新运行')
 Wn,Hn=normalize_factors(W,model.components_);error=float(np.linalg.norm(X-Wn@Hn))
 return {'W':Wn,'H':Hn,'iterations':int(model.n_iter_),'reconstruction_error':error,'relative_error':error/float(np.linalg.norm(X))}

def fit_matrix_streaming(X,x_sq,k,seed,max_iter,tolerance):
 # 与 fit_matrix 同一数值口径（sklearn cd、random 初始化、Frobenius、无正则、固定 random_state），
 # 但 X 可为 memmap：自驱动 _update_coordinate_descent，X 只参与 safe_sparse_dot，不做全量复制；
 # X.T 是 F 连续视图，np.dot 走 F 序 BLAS 不复制。512MiB 进程内可承载百万篇。
 n,v=X.shape
 avg=np.sqrt(X.mean()/k)
 rng=check_random_state(seed)
 H=avg*rng.standard_normal((k,v));W=avg*rng.standard_normal((n,k))
 np.abs(H,out=H);np.abs(W,out=W)
 Ht=np.ascontiguousarray(H.T);rng_cd=check_random_state(seed)
 violation_init=None;n_iter=0
 for n_iter in range(1,max_iter+1):
  violation=_update_coordinate_descent(X,W,Ht,0.,0.,False,rng_cd)
  violation+=_update_coordinate_descent(X.T,Ht,W,0.,0.,False,rng_cd)
  if n_iter==1:violation_init=violation
  if violation_init==0:break
  if violation/violation_init<=tolerance:break
 if n_iter==max_iter and tolerance>0:raise ValueError(f'未收敛：seed={seed} max_iter={max_iter}；增加上限后重新运行')
 Wn,Hn=normalize_factors(W,Ht.T)
 # 分块恒等式 ||X-WH||²=||X||²-2⟨X,WH⟩+||WH||²，不物化 n×v 残差
 inner=float(((X@Hn.T)*Wn).sum());wh_sq=float(((Wn.T@Wn)*(Hn@Hn.T)).sum())
 error=float(np.sqrt(max(x_sq-2*inner+wh_sq,0.)))
 return {'W':Wn,'H':Hn,'iterations':n_iter,'reconstruction_error':error,'relative_error':error/float(np.sqrt(x_sq))}
