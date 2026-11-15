from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,JSON,ForeignKey,Index
from src.config.database import Base
class RunDocument(Base):
 __tablename__='run_documents'
 __table_args__=(Index('ix_run_documents_run_reference','run_id','reference'),Index('ix_run_documents_run_status','run_id','status'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 run_id:Mapped[int]=mapped_column(ForeignKey('topic_runs.id'))
 document_id:Mapped[int]=mapped_column(ForeignKey('token_documents.id'))
 reference:Mapped[str]=mapped_column(String(80))
 title:Mapped[str]=mapped_column(String(120))
 status:Mapped[str]=mapped_column(String(10))
 reason:Mapped[str|None]=mapped_column(String(40),nullable=True)
 activations:Mapped[list|None]=mapped_column(JSON,nullable=True)
