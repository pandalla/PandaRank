from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import json
import uuid
import httpx
import yaml
import csv
from pathlib import Path
from loguru import logger

# 简化的CSV存储类
class SimpleCSVStorage:
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # CSV文件路径
        self.conversations_file = self.data_dir / "conversations.csv"
        self.messages_file = self.data_dir / "messages.csv"
        self.web_searches_file = self.data_dir / "web_searches.csv"
        
        # CSV模块已在顶部导入
    
    def get_conversations(self, limit: int = 100):
        """获取对话列表"""
        conversations = []
        if not self.conversations_file.exists():
            return conversations
        
        with open(self.conversations_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        # 按开始时间倒序排序
        rows.sort(key=lambda x: x.get('started_at', ''), reverse=True)
        
        for row in rows[:limit]:
            duration_seconds = None
            if row.get('finished_at') and row.get('started_at'):
                try:
                    start = datetime.fromisoformat(row['started_at'])
                    finish = datetime.fromisoformat(row['finished_at'])
                    duration_seconds = (finish - start).total_seconds()
                except:
                    pass
            
            conversations.append({
                'id': int(row['id']) if row.get('id') else 0,
                'run_uuid': row.get('run_uuid', ''),
                'question_id': int(row['question_id']) if row.get('question_id') else None,
                'question_text': row.get('question_text', ''),
                'started_at': row.get('started_at') if row.get('started_at') else None,
                'finished_at': row.get('finished_at') if row.get('finished_at') else None,
                'duration_seconds': duration_seconds
            })
        
        return conversations
    
    def get_conversation_details(self, run_uuid: str):
        """获取对话详情"""
        # 找到对话
        conversation = None
        if self.conversations_file.exists():
            with open(self.conversations_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('run_uuid') == run_uuid:
                        conversation = row
                        break
        
        if not conversation:
            return None
        
        conversation_id = int(conversation['id']) if conversation.get('id') else 0
        
        # 获取消息
        messages = []
        if self.messages_file.exists():
            with open(self.messages_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get('conversation_id', 0)) == conversation_id:
                            messages.append({
                                'id': int(row['id']) if row.get('id') else 0,
                                'role': row.get('role', ''),
                                'content': row.get('content_md', ''),
                                'scraped_at': row.get('scraped_at', '')
                            })
        
        # 获取网页搜索
        web_searches = []
        if self.web_searches_file.exists():
            with open(self.web_searches_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get('conversation_id', 0)) == conversation_id:
                            web_searches.append({
                                'id': int(row['id']) if row.get('id') else 0,
                                'url': row.get('url', ''),
                                'title': row.get('title', ''),
                                'fetched_at': row.get('fetched_at', '')
                            })
        
        # 获取思考过程
        reasoning = []
        reasoning_file = self.data_dir / "reasoning.csv"
        if reasoning_file.exists():
            with open(reasoning_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get('conversation_id', 0)) == conversation_id:
                        # 解码换行符
                        content = row.get('reasoning_content', '').replace('\\n', '\n').replace('\\r', '\r')
                        reasoning.append({
                            'id': int(row['id']) if row.get('id') else 0,
                            'reasoning_content': content,
                            'created_at': row.get('created_at', '')
                        })
        
        # 获取搜索查询
        search_queries = []
        search_queries_file = self.data_dir / "search_queries.csv"
        if search_queries_file.exists():
            with open(search_queries_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get('conversation_id', 0)) == conversation_id:
                            search_queries.append({
                                'id': int(row['id']) if row.get('id') else 0,
                                'query_text': row.get('query_text', ''),
                                'created_at': row.get('created_at', '')
                            })
        
        # 获取访问网站
        visited_sites = []
        visited_sites_file = self.data_dir / "visited_sites.csv"
        if visited_sites_file.exists():
            with open(visited_sites_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get('conversation_id', 0)) == conversation_id:
                            visited_sites.append({
                                'id': int(row['id']) if row.get('id') else 0,
                                'site_url': row.get('site_url', ''),
                                'site_title': row.get('site_title', ''),
                                'site_description': row.get('site_description', ''),
                                'created_at': row.get('created_at', '')
                            })
        
        return {
            'id': conversation_id,
            'run_uuid': conversation.get('run_uuid', ''),
            'question': {
                'id': int(conversation['question_id']) if conversation.get('question_id') else None,
                'text': conversation.get('question_text', ''),
                'cooldown_min': 1440
            },
            'started_at': conversation.get('started_at'),
            'finished_at': conversation.get('finished_at'),
            'messages': messages,
            'web_searches': web_searches,
            'artifacts': [],
            'reasoning': reasoning,
            'search_queries': search_queries,
            'visited_sites': visited_sites
        }
    
    def get_stats(self):
        """获取统计信息"""
        total_conversations = 0
        successful_conversations = 0
        total_messages = 0
        total_web_searches = 0
        
        # 统计对话
        if self.conversations_file.exists():
            with open(self.conversations_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_conversations += 1
                    if row.get('finished_at'):
                        successful_conversations += 1
        
        # 统计消息
        if self.messages_file.exists():
            with open(self.messages_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total_messages = sum(1 for _ in reader)
        
        # 统计网页搜索
        if self.web_searches_file.exists():
            with open(self.web_searches_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total_web_searches = sum(1 for _ in reader)
        
        return {
            'total_conversations': total_conversations,
            'successful_conversations': successful_conversations,
            'success_rate': successful_conversations / total_conversations if total_conversations > 0 else 0,
            'total_messages': total_messages,
            'total_web_searches': total_web_searches,
            'total_questions': 5
        }


app = FastAPI(title="PandaRank API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSV存储实例
storage = SimpleCSVStorage()

class TriggerRequest(BaseModel):
    question_id: Optional[int] = None
    custom_question: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "PandaRank ChatGPT Scraper API", "version": "1.0.0"}

@app.get("/runs")
async def list_runs(
    since: Optional[datetime] = Query(None, description="Filter runs started after this timestamp"),
    limit: int = Query(100, le=1000)
):
    """List all scraping runs"""
    conversations = storage.get_conversations(limit)
    
    # 如果有since过滤条件
    if since:
        conversations = [
            conv for conv in conversations 
            if conv['started_at'] and datetime.fromisoformat(conv['started_at']) >= since
        ]
    
    return {"runs": conversations, "count": len(conversations)}

@app.get("/runs/{run_uuid}")
async def get_run_details(run_uuid: str):
    """Get detailed information about a specific run"""
    conversation = storage.get_conversation_details(run_uuid)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return conversation

@app.get("/questions")
async def list_questions():
    """List all questions in the pool"""
    questions_file = Path("/app/data/geo_questions.yaml")
    questions = []
    
    if questions_file.exists():
        with open(questions_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data:
                for q in data:
                    questions.append({
                        "id": q.get('id', 0),
                        "text": q.get('text', ''),
                        "cooldown_min": q.get('cooldown_min', 1440),
                        "last_asked_at": None,
                        "created_at": "2025-07-08T00:00:00+00:00"
                    })
    
    return {"questions": questions, "count": len(questions)}

@app.get("/stats")
async def get_stats():
    """Get overall statistics"""
    return storage.get_stats()

@app.get("/debug/csv")
async def debug_csv_data(conversation_id: int = Query(...)):
    """Debug CSV data reading"""
    debug_info = {}
    
    # 检查reasoning.csv
    reasoning_file = Path("/app/data/reasoning.csv")
    if reasoning_file.exists():
        with open(reasoning_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            reasoning_rows = []
            for row in reader:
                if int(row.get('conversation_id', 0)) == conversation_id:
                    reasoning_rows.append(row)
            debug_info['reasoning_rows'] = reasoning_rows
    
    # 检查search_queries.csv
    search_file = Path("/app/data/search_queries.csv")
    if search_file.exists():
        with open(search_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            search_rows = []
            for row in reader:
                if int(row.get('conversation_id', 0)) == conversation_id:
                    search_rows.append(row)
            debug_info['search_rows'] = search_rows
    
    return debug_info

@app.post("/trigger")
async def trigger_scrape(
    request: TriggerRequest,
    background_tasks: BackgroundTasks
):
    """Manually trigger a scraping job"""
    
    # 验证请求
    if not request.question_id and not request.custom_question:
        raise HTTPException(status_code=400, detail="Either question_id or custom_question must be provided")
    
    # 获取问题文本
    if request.custom_question:
        question_text = request.custom_question
        question_id = 999  # 自定义问题使用特殊ID
    else:
        # 从YAML文件获取问题
        questions_file = Path("/app/data/geo_questions.yaml")
        question_text = "Test question"
        question_id = request.question_id
        
        if questions_file.exists():
            with open(questions_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data:
                    for q in data:
                        if q.get('id') == request.question_id:
                            question_text = q.get('text', 'Unknown question')
                            break
    
    # 创建运行UUID
    run_uuid = str(uuid.uuid4())
    
    # 调用scraper服务
    background_tasks.add_task(call_scraper_service, question_id)
    
    return {
        "message": "Scraping job triggered successfully",
        "run_uuid": run_uuid,
        "question_id": question_id,
        "question_text": question_text
    }

async def call_scraper_service(question_id: int):
    """Call the scraper service to process a specific question"""
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
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