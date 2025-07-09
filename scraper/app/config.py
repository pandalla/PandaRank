from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path
from dotenv import load_dotenv

# 尝试从多个位置加载.env文件
env_paths = [
    Path(".env"),  # 当前目录
    Path("../.env"),  # 上级目录
    Path("../../.env"),  # 上上级目录
]

for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break


class Settings(BaseSettings):
    openai_session_token: Optional[str] = None
    openai_email: Optional[str] = None
    openai_pwd: Optional[str] = None
    
    scrape_interval_sec: int = 600
    headless: bool = True
    
    db_dsn: str = "postgresql://scraper:secret@localhost:5432/chatlogs"
    
    question_pool_path: str = "/app/data/questions.yaml"
    
    metrics_port: int = 8080
    
    browser_timeout: int = 300000  # 5 minutes
    page_timeout: int = 300000  # 5 minutes
    
    # Demo mode - simulate responses without real ChatGPT
    demo_mode: bool = False
    
    # Additional settings from .env
    tz: Optional[str] = None
    scraper_port: Optional[int] = None
    db_port: Optional[int] = None
    api_port: Optional[int] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra fields from .env
        
        # Try to find .env in parent directory if not in current
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            return cls.json_schema_extra['env_prefix'] + raw_val if hasattr(cls, 'json_schema_extra') else raw_val


settings = Settings()