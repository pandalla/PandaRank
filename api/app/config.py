from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_dsn: str = "postgresql://scraper:secret@localhost:5432/chatlogs"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()