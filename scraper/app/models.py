from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class Question(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    cooldown_min = Column(Integer, default=720)
    last_asked_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    conversations = relationship("Conversation", back_populates="question")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True)
    run_uuid = Column(UUID, nullable=False, default=uuid.uuid4)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    
    question = relationship("Question", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    web_searches = relationship("WebSearch", back_populates="conversation", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    content_md = Column(Text)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="messages")


class WebSearch(Base):
    __tablename__ = "web_searches"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    url = Column(Text)
    title = Column(Text)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="web_searches")


class Artifact(Base):
    __tablename__ = "artifacts"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    type = Column(String, nullable=False)  # screenshot, html, har
    path = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="artifacts")