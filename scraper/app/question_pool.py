import yaml
import random
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from loguru import logger

from .models import Question
from .config import settings


class QuestionPoolManager:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.question_pool_path = settings.question_pool_path
        # Try GEO questions file first, fallback to default
        geo_path = self.question_pool_path.replace('questions.yaml', 'geo_questions.yaml')
        if os.path.exists(geo_path):
            self.question_pool_path = geo_path
    
    def load_questions_from_yaml(self):
        """Load questions from YAML file and sync with database"""
        try:
            with open(self.question_pool_path, 'r') as f:
                yaml_questions = yaml.safe_load(f)
            
            for q in yaml_questions:
                existing = self.db_session.query(Question).filter_by(id=q['id']).first()
                if not existing:
                    new_question = Question(
                        id=q['id'],
                        text=q['text'],
                        cooldown_min=q.get('cooldown_min', 720)
                    )
                    self.db_session.add(new_question)
                else:
                    # Update existing question
                    existing.text = q['text']
                    existing.cooldown_min = q.get('cooldown_min', 720)
            
            self.db_session.commit()
            logger.info(f"Loaded {len(yaml_questions)} questions from YAML")
        except FileNotFoundError:
            logger.warning(f"Question pool file not found at {self.question_pool_path}, using database only")
        except Exception as e:
            logger.error(f"Error loading questions from YAML: {e}")
    
    def get_next_question(self) -> Optional[Question]:
        """Get the next question using weighted-random selection favoring least-recently-asked"""
        now = datetime.now(timezone.utc)
        
        # Get all questions
        questions = self.db_session.query(Question).all()
        
        if not questions:
            logger.error("No questions available in the pool")
            return None
        
        # Filter out questions still in cooldown
        available_questions = []
        for q in questions:
            if q.last_asked_at is None:
                available_questions.append(q)
            else:
                cooldown_end = q.last_asked_at + timedelta(minutes=q.cooldown_min)
                if now >= cooldown_end:
                    available_questions.append(q)
        
        if not available_questions:
            logger.warning("All questions are in cooldown period")
            # Find the question with the earliest cooldown end
            next_available = min(questions, key=lambda q: 
                q.last_asked_at + timedelta(minutes=q.cooldown_min) if q.last_asked_at else now
            )
            return next_available
        
        # Calculate weights (inverse of recency)
        weights = []
        for q in available_questions:
            if q.last_asked_at is None:
                weight = 1000  # High weight for never-asked questions
            else:
                time_since_asked = (now - q.last_asked_at).total_seconds() / 3600  # hours
                weight = max(1, time_since_asked)
            weights.append(weight)
        
        # Select question using weighted random
        selected = random.choices(available_questions, weights=weights, k=1)[0]
        
        # Update last_asked_at
        selected.last_asked_at = now
        self.db_session.commit()
        
        logger.info(f"Selected question {selected.id}: {selected.text[:50]}...")
        return selected