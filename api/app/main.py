from fastapi import FastAPI, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import json
import io
import uuid
import asyncio
import httpx
from loguru import logger

from .config import settings
from .models import Base, Conversation, Message, WebSearch, Artifact, Question


# Database setup
engine = create_engine(settings.db_dsn)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="PandaRank API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TriggerRequest(BaseModel):
    question_id: Optional[int] = None
    custom_question: Optional[str] = None


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
async def root():
    return {"message": "PandaRank ChatGPT Scraper API", "version": "1.0.0"}


@app.get("/runs")
async def list_runs(
    since: Optional[datetime] = Query(None, description="Filter runs started after this timestamp"),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    """List all scraping runs"""
    query = db.query(Conversation)
    
    if since:
        query = query.filter(Conversation.started_at >= since)
    
    conversations = query.order_by(Conversation.started_at.desc()).limit(limit).all()
    
    results = []
    for conv in conversations:
        results.append({
            "id": conv.id,
            "run_uuid": str(conv.run_uuid),
            "question_id": conv.question_id,
            "question_text": conv.question.text if conv.question else None,
            "started_at": conv.started_at.isoformat() if conv.started_at else None,
            "finished_at": conv.finished_at.isoformat() if conv.finished_at else None,
            "duration_seconds": (
                (conv.finished_at - conv.started_at).total_seconds() 
                if conv.finished_at and conv.started_at else None
            )
        })
    
    return {"runs": results, "count": len(results)}


@app.get("/runs/{run_uuid}")
async def get_run_details(run_uuid: str, db: Session = Depends(get_db)):
    """Get detailed information about a specific run"""
    conversation = db.query(Conversation).filter(
        Conversation.run_uuid == run_uuid
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Build response with all related data
    messages = []
    for msg in conversation.messages:
        messages.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content_md,
            "scraped_at": msg.scraped_at.isoformat() if msg.scraped_at else None
        })
    
    web_searches = []
    for search in conversation.web_searches:
        web_searches.append({
            "id": search.id,
            "url": search.url,
            "title": search.title,
            "fetched_at": search.fetched_at.isoformat() if search.fetched_at else None
        })
    
    artifacts = []
    for artifact in conversation.artifacts:
        artifacts.append({
            "id": artifact.id,
            "type": artifact.type,
            "path": artifact.path,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None
        })
    
    return {
        "id": conversation.id,
        "run_uuid": str(conversation.run_uuid),
        "question": {
            "id": conversation.question.id,
            "text": conversation.question.text,
            "cooldown_min": conversation.question.cooldown_min
        } if conversation.question else None,
        "started_at": conversation.started_at.isoformat() if conversation.started_at else None,
        "finished_at": conversation.finished_at.isoformat() if conversation.finished_at else None,
        "messages": messages,
        "web_searches": web_searches,
        "artifacts": artifacts
    }


@app.get("/export/ndjson")
async def export_ndjson(
    since: Optional[datetime] = Query(None, description="Export runs started after this timestamp"),
    db: Session = Depends(get_db)
):
    """Export all data as newline-delimited JSON"""
    query = db.query(Conversation)
    
    if since:
        query = query.filter(Conversation.started_at >= since)
    
    conversations = query.order_by(Conversation.started_at.asc()).all()
    
    def generate():
        for conv in conversations:
            # Build conversation data
            data = {
                "conversation_id": conv.id,
                "run_uuid": str(conv.run_uuid),
                "question": {
                    "id": conv.question.id,
                    "text": conv.question.text
                } if conv.question else None,
                "started_at": conv.started_at.isoformat() if conv.started_at else None,
                "finished_at": conv.finished_at.isoformat() if conv.finished_at else None,
                "messages": [
                    {
                        "role": msg.role,
                        "content": msg.content_md,
                        "scraped_at": msg.scraped_at.isoformat() if msg.scraped_at else None
                    }
                    for msg in conv.messages
                ],
                "web_searches": [
                    {
                        "url": search.url,
                        "title": search.title,
                        "fetched_at": search.fetched_at.isoformat() if search.fetched_at else None
                    }
                    for search in conv.web_searches
                ]
            }
            
            yield json.dumps(data) + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f"attachment; filename=chatgpt_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.ndjson"
        }
    )


@app.get("/questions")
async def list_questions(db: Session = Depends(get_db)):
    """List all questions in the pool"""
    questions = db.query(Question).all()
    
    results = []
    for q in questions:
        results.append({
            "id": q.id,
            "text": q.text,
            "cooldown_min": q.cooldown_min,
            "last_asked_at": q.last_asked_at.isoformat() if q.last_asked_at else None,
            "created_at": q.created_at.isoformat() if q.created_at else None
        })
    
    return {"questions": results, "count": len(results)}


@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get overall statistics"""
    total_conversations = db.query(Conversation).count()
    successful_conversations = db.query(Conversation).filter(
        Conversation.finished_at.isnot(None)
    ).count()
    total_messages = db.query(Message).count()
    total_web_searches = db.query(WebSearch).count()
    total_questions = db.query(Question).count()
    
    return {
        "total_conversations": total_conversations,
        "successful_conversations": successful_conversations,
        "success_rate": (
            successful_conversations / total_conversations 
            if total_conversations > 0 else 0
        ),
        "total_messages": total_messages,
        "total_web_searches": total_web_searches,
        "total_questions": total_questions
    }


@app.post("/trigger")
async def trigger_scrape(
    request: TriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger a scraping job"""
    
    # Validate request
    if not request.question_id and not request.custom_question:
        raise HTTPException(status_code=400, detail="Either question_id or custom_question must be provided")
    
    # If custom question, create it in the database
    if request.custom_question:
        # Create a temporary question
        new_question = Question(
            text=request.custom_question,
            cooldown_min=0  # No cooldown for custom questions
        )
        db.add(new_question)
        db.commit()
        db.refresh(new_question)
        question_id = new_question.id
        question_text = new_question.text
    else:
        # Get existing question
        question = db.query(Question).filter(Question.id == request.question_id).first()
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        question_id = question.id
        question_text = question.text
    
    # Create a new conversation record
    run_uuid = uuid.uuid4()
    conversation = Conversation(
        run_uuid=run_uuid,
        question_id=question_id,
        started_at=datetime.now(timezone.utc)
    )
    db.add(conversation)
    db.commit()
    
    # Call the scraper service asynchronously
    background_tasks.add_task(call_scraper_service, question_id)
    
    return {
        "message": "Scraping job triggered successfully",
        "run_uuid": str(run_uuid),
        "question_id": question_id,
        "question_text": question_text
    }


async def call_scraper_service(question_id: int):
    """Call the scraper service to process a specific question"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Call the scraper service
            response = await client.post(f"http://scraper:8080/scrape/{question_id}")
            if response.status_code == 200:
                logger.info(f"Successfully triggered scraper for question {question_id}")
            else:
                logger.error(f"Failed to trigger scraper: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Failed to call scraper service: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)