"""
SQLAlchemy models for database manager service
Represents subjects and chunked course materials
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from pgvector.sqlalchemy import Vector

db = SQLAlchemy()


class Subject(db.Model):
    """School subject model (haircutting, plumbing, etc)"""
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True, index=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chunks = db.relationship('Chunk', backref='subject', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'chunk_count': len(self.chunks) if self.chunks else 0
        }


class Chunk(db.Model):
    """Chunked course material model"""
    __tablename__ = 'chunks'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    source_file = db.Column(db.String(255))
    embedding = db.Column(Vector(384), nullable=True)  # all-MiniLM-L6-v2 dimension
    chunk_metadata = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, include_embedding=False):
        data = {
            'id': self.id,
            'subject_id': self.subject_id,
            'content': self.content,
            'source_file': self.source_file,
            'chunk_metadata': self.chunk_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_embedding and self.embedding is not None:
            data['embedding'] = self.embedding.tolist() if hasattr(self.embedding, 'tolist') else list(self.embedding)
        return data


class Prompt(db.Model):
    """System prompts for LLM model"""
    __tablename__ = 'prompts'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'subject_id': self.subject_id,
            'title': self.title,
            'content': self.content,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
