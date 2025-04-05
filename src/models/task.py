from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    dependencies = Column(JSON)  # List of task IDs
    priority = Column(Integer)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    estimates = relationship("TaskEstimate", back_populates="task")
    feedback = relationship("TaskFeedback", back_populates="task")
    notes = relationship("Note", back_populates="task")

class TaskEstimate(Base):
    __tablename__ = "task_estimates"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    estimated_duration_minutes = Column(Integer)
    confidence_score = Column(Float)
    historical_data_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relationships
    task = relationship("Task", back_populates="estimates")

class TaskFeedback(Base):
    __tablename__ = "task_feedback"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    actual_duration_minutes = Column(Integer)
    estimated_duration_minutes = Column(Integer)
    accuracy_feedback = Column(Float)
    priority_feedback = Column(Float)
    notes = Column(String)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relationships
    task = relationship("Task", back_populates="feedback")

class Note(Base):
    __tablename__ = "notes"
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    tags = Column(JSON)  # List of tag strings
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    task = relationship("Task", back_populates="notes") 