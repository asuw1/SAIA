from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from database import Base


class Clause(Base):
    """
    Represents a single regulatory clause from NCA / SAMA / CST / IA.
    e.g. framework=NCA, code=ACC-4.2.1, title=Access Control
    """
    __tablename__ = "clauses"

    id          = Column(Integer, primary_key=True, index=True)
    framework   = Column(String(20), nullable=False, index=True)   # NCA | SAMA | CST | IA
    code        = Column(String(50), unique=True, nullable=False)   # e.g. NCA-ACC-4.2.1
    title       = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category    = Column(String(100), nullable=True)                # Access Control, Encryption, etc.

    rules  = relationship("Rule", back_populates="clause")
    alerts = relationship("Alert", back_populates="clause")
