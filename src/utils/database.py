from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from src.models.task import Base
import os
from dotenv import load_dotenv
from src.utils.logging import logger

load_dotenv()

# Get database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./task_agent.db")

# Create engine
engine = create_engine(DATABASE_URL)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initialize the database by creating all tables"""
    try:
        # Create tables defined in Base models
        Base.metadata.create_all(bind=engine)
        
        # Define and create the tenants table explicitly
        metadata = MetaData()
        tenants = Table(
            'tenants', metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String),
        )
        
        # Create the additional tables
        metadata.create_all(bind=engine)
        
        # Create default tenant if needed
        db = SessionLocal()
        try:
            # Use text() for raw SQL
            result = db.execute(text("SELECT COUNT(*) FROM tenants")).scalar()
            if result == 0:
                db.execute(text("INSERT INTO tenants (id, name) VALUES (1, 'default')"))
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating default tenant: {str(e)}")
        finally:
            db.close()
            
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {str(e)}")
        return False

def get_db():
    """Get a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def add_task(db, task_data):
    """Add a new task to the database"""
    from src.models.task import Task  # Fixed import path
    task = Task(**task_data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

def add_task_estimate(db, estimate_data):
    """Add a new task estimate to the database"""
    from src.models.task import TaskEstimate  # Fixed import path
    estimate = TaskEstimate(**estimate_data)
    db.add(estimate)
    db.commit()
    db.refresh(estimate)
    return estimate

def add_task_feedback(db, feedback_data):
    """Add new task feedback to the database"""
    from src.models.task import TaskFeedback  # Fixed import path
    feedback = TaskFeedback(**feedback_data)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback

def get_task(db, task_id):
    """Get a task by ID"""
    from src.models.task import Task  # Fixed import path
    return db.query(Task).filter(Task.id == task_id).first()

def get_task_estimates(db, task_id):
    """Get all estimates for a task"""
    from src.models.task import TaskEstimate  # Fixed import path
    return db.query(TaskEstimate).filter(TaskEstimate.task_id == task_id).all()

def get_task_feedback(db, task_id):
    """Get all feedback for a task"""
    from src.models.task import TaskFeedback  # Fixed import path
    return db.query(TaskFeedback).filter(TaskFeedback.task_id == task_id).all()

def update_task(db, task_id, update_data):
    """Update a task"""
    from src.models.task import Task  # Fixed import path
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        for key, value in update_data.items():
            setattr(task, key, value)
        db.commit()
        db.refresh(task)
    return task

def add_note(db, note_data):
    """Add a new note to the database"""
    from src.models.task import Note
    note = Note(**note_data)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

def get_note(db, note_id):
    """Get a note by ID"""
    from src.models.task import Note
    return db.query(Note).filter(Note.id == note_id).first()

def get_task_notes(db, task_id):
    """Get all notes for a task"""
    from src.models.task import Note
    return db.query(Note).filter(Note.task_id == task_id).all()

def update_note(db, note_id, update_data):
    """Update a note"""
    from src.models.task import Note
    note = db.query(Note).filter(Note.id == note_id).first()
    if note:
        for key, value in update_data.items():
            setattr(note, key, value)
        db.commit()
        db.refresh(note)
    return note

def delete_note(db, note_id):
    """Delete a note"""
    from src.models.task import Note
    note = db.query(Note).filter(Note.id == note_id).first()
    if note:
        db.delete(note)
        db.commit()
    return True