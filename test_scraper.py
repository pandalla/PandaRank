#!/usr/bin/env python3
"""
Test script to verify scraper functionality
"""

import asyncio
import sys
import os
sys.path.append('scraper')

from scraper.app.scraper import ChatGPTScraper
from scraper.app.config import settings
from scraper.app.models import Base, Conversation, Message, Question
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import uuid

async def test_scraper():
    """Test the scraper with a simple question"""
    
    # Database setup
    engine = create_engine(settings.db_dsn)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        # Create a test question
        test_question = Question(
            text="What is the capital of Japan?",
            cooldown_min=0
        )
        db.add(test_question)
        db.commit()
        db.refresh(test_question)
        
        # Create a test conversation
        conversation = Conversation(
            run_uuid=uuid.uuid4(),
            question_id=test_question.id,
            started_at=datetime.now(timezone.utc)
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        # Test the scraper
        scraper = ChatGPTScraper(db)
        
        print("Initializing browser...")
        await scraper.initialize()
        
        print("Attempting to login...")
        await scraper.login()
        
        print("Submitting prompt...")
        result = await scraper.submit_prompt(conversation.id, test_question.text)
        
        print(f"Response: {result['response']}")
        print(f"Browsing events: {len(result['browsing_events'])}")
        
        # Update conversation
        conversation.finished_at = datetime.now(timezone.utc)
        db.commit()
        
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'scraper' in locals():
            await scraper.cleanup()
        db.close()

if __name__ == "__main__":
    if not settings.openai_session_token:
        print("Please set OPENAI_SESSION_TOKEN in your .env file")
        sys.exit(1)
    
    asyncio.run(test_scraper())