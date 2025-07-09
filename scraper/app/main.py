import asyncio
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import threading

from .config import settings
from .models import Base, Conversation, Message, WebSearch
from .question_pool import QuestionPoolManager
from .scraper import ChatGPTScraper


# Prometheus metrics
scrape_counter = Counter('chatgpt_scrapes_total', 'Total number of scrape attempts')
scrape_success_counter = Counter('chatgpt_scrapes_success', 'Total number of successful scrapes')
scrape_failure_counter = Counter('chatgpt_scrapes_failed', 'Total number of failed scrapes')
scrape_duration = Histogram('chatgpt_scrape_duration_seconds', 'Time spent scraping')
active_scrapes = Gauge('chatgpt_active_scrapes', 'Number of active scrape jobs')


# Database setup
engine = create_engine(settings.db_dsn)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI app for HTTP endpoints
app = FastAPI(title="PandaRank Scraper", version="1.0.0")

class TriggerRequest(BaseModel):
    question_id: int


def generate_demo_response(question_text: str) -> str:
    """Generate a demo response based on the question"""
    demo_responses = {
        "东京": """根据我的搜索和了解，东京最好吃的拉面馆推荐如下：

**前5名推荐：**

1. **一兰拉面 (Ichiran Ramen)**
   - 地址：涩谷、新宿、银座等多个分店
   - 特色：豚骨拉面，可自定义口味浓度
   - 价格：约1000-1500日元

2. **蟹汇拉面 (Ippudo)**
   - 地址：恳亲寺本店、银座店等
   - 特色：白丸元味拉面，汤头浓郁
   - 价格：约1200-1800日元

3. **山岸一雄制作所**
   - 地址：港区高轮
   - 特色：蘸面（つけ麺），面条Q弹
   - 价格：约1300-1600日元

4. **鸣龙**
   - 地址：大塚
   - 特色：拉面界的米其林一星，担担面著名
   - 价格：约1500-2000日元

5. **麦まる**
   - 地址：京桥
   - 特色：家庭式拉面，味道温和
   - 价格：约800-1200日元

以上推荐来自多个美食网站和当地人推荐，建议提前查询营业时间。""",
        
        "香港": """香港最好的粤菜餐厅推荐：

**顶级粤菜餐厅（前5名）：**

1. **唐阁 (Tang Court)**
   - 地址：朗廷酒店
   - 特色：米其林三星，传统粤菜精髓
   - 人均：800-1200港币

2. **龙景轩 (Lung King Heen)**
   - 地址：四季酒店
   - 特色：米其林三星，海景用餐环境
   - 人均：1000-1500港币

3. **天龙轩**
   - 地址：丽思卡尔顿酒店
   - 特色：创新粤菜，摆盘精美
   - 人均：600-1000港币

4. **金叶庭**
   - 地址：康莱德酒店
   - 特色：现代粤菜，服务一流
   - 人均：500-800港币

5. **海天楼**
   - 地址：太古广场
   - 特色：传统茶餐厅升级版
   - 人均：300-500港币

建议提前预订，特别是米其林餐厅。""",
        
        "深圳": """深圳电子配件优质工厂推荐：

**深圳地区：**
1. **华强北电子市场**
   - 位置：福田区华强北
   - 特色：全球最大电子元器件市场
   - 推荐：赛格电子市场、华强电子世界

2. **富士康科技集团**
   - 位置：龙华新区
   - 特色：苹果供应商，品质保证
   - 主营：手机、电脑组装

**东莞地区：**
3. **步步高电子**
   - 位置：东莞长安
   - 特色：OPPO、vivo制造商
   - 主营：智能手机配件

4. **德赛电池**
   - 位置：东莞塘厦
   - 特色：电池技术领先
   - 主营：手机电池、充电器

5. **立讯精密**
   - 位置：昆山/东莞
   - 特色：苹果连接器供应商
   - 主营：连接器、声学器件

**联系建议：**
- 通过阿里巴巴平台联系
- 参加深圳电子展会
- 实地考察工厂资质""",
        
        "新加坡": """在新加坡注册公司的详细流程：

**注册流程（约7-14天）：**

1. **准备阶段**
   - 确定公司名称（需通过ACRA检查）
   - 准备董事资料（至少1名新加坡居民董事）
   - 确定注册地址

2. **ACRA注册**
   - 在线提交申请 (BizFile+)
   - 费用：300新币
   - 审核时间：1-2个工作日

3. **必要文件**
   - 公司章程 (Memorandum & Articles)
   - 董事决议书
   - 股东协议

**费用明细：**
- 注册费：300新币
- 代理费：800-2000新币
- 秘书服务：1000-3000新币/年
- 办公地址：500-2000新币/月

**后续义务：**
- 年度申报：必须
- 审计要求：年营业额超过500万新币
- 税务申报：公司所得税17%

**建议：**
委托专业代理机构办理，确保合规。""",
        
        "默认": f"""根据您的问题："{question_text}"

这是一个演示回答。系统正在模拟ChatGPT的响应过程。

**分析过程：**
1. 理解问题的核心需求
2. 搜索相关信息和数据源
3. 整理并提供结构化回答

**搜索的信息源：**
- 官方网站和政府数据
- 行业报告和统计数据
- 用户评价和专业推荐
- 当地人经验分享

**回答要点：**
- 提供具体可行的建议
- 包含地址、价格等详细信息
- 注明数据来源和时效性
- 给出额外的实用提示

*注：这是演示模式的回答，实际使用时会连接真实的ChatGPT进行问答。*"""
    }
    
    # 根据问题关键词选择合适的回答
    for keyword, response in demo_responses.items():
        if keyword in question_text:
            return response
    
    return demo_responses["默认"]


async def scrape_chatgpt_job(question_id: int = None):
    """Main job that runs on schedule or manually triggered"""
    job_start = time.time()
    scrape_counter.inc()
    active_scrapes.inc()
    
    db = SessionLocal()
    run_uuid = uuid.uuid4()
    
    try:
        logger.info(f"Starting scrape job with run_uuid: {run_uuid}")
        
        # Get specific question or next question from pool
        if question_id:
            from .models import Question
            question = db.query(Question).filter(Question.id == question_id).first()
            if not question:
                logger.error(f"Question with id {question_id} not found")
                return
        else:
            # Get next question from pool
            qpm = QuestionPoolManager(db)
            qpm.load_questions_from_yaml()  # Sync questions from YAML
            question = qpm.get_next_question()
        
        if not question:
            logger.error("No question available to ask")
            return
        
        # Create conversation record
        conversation = Conversation(
            run_uuid=run_uuid,
            question_id=question.id,
            started_at=datetime.now(timezone.utc)
        )
        db.add(conversation)
        db.commit()
        
        # Check if demo mode
        if settings.demo_mode:
            # Demo mode - simulate response
            logger.info("Running in DEMO mode - simulating ChatGPT response")
            
            # Create demo messages
            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content_md=question.text
            )
            db.add(user_msg)
            
            # Generate demo response based on question
            demo_response = generate_demo_response(question.text)
            assistant_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content_md=demo_response
            )
            db.add(assistant_msg)
            
            # Add demo web searches
            demo_searches = [
                {"url": "https://www.google.com/search?q=" + question.text.replace(" ", "+"), "title": "Google搜索结果"},
                {"url": "https://www.tripadvisor.com", "title": "TripAdvisor - 旅游推荐"},
                {"url": "https://www.tabelog.com", "title": "Tabelog - 日本美食评价网站"}
            ]
            
            for search in demo_searches:
                web_search = WebSearch(
                    conversation_id=conversation.id,
                    url=search["url"],
                    title=search["title"]
                )
                db.add(web_search)
            
            # Update conversation finish time
            conversation.finished_at = datetime.now(timezone.utc)
            db.commit()
            
            logger.info(f"DEMO: Generated response for question {question.id}")
            scrape_success_counter.inc()
            
        else:
            # Real mode - use ChatGPT
            scraper = ChatGPTScraper(db)
            await scraper.initialize()
            
            try:
                # Login
                await scraper.login()
                
                # Submit prompt and get response
                result = await scraper.submit_prompt(conversation.id, question.text)
                
                # Update conversation finish time
                conversation.finished_at = datetime.now(timezone.utc)
                db.commit()
                
                logger.info(f"Successfully scraped response for question {question.id}")
                logger.info(f"Response preview: {result['response'][:100]}...")
                logger.info(f"Browsing events: {len(result['browsing_events'])}")
                
                scrape_success_counter.inc()
                
            finally:
                await scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Scrape job failed: {e}")
        scrape_failure_counter.inc()
        
        # Mark conversation as failed
        if 'conversation' in locals():
            conversation.finished_at = datetime.now(timezone.utc)
            db.commit()
    
    finally:
        db.close()
        active_scrapes.dec()
        scrape_duration.observe(time.time() - job_start)


@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.post("/scrape/{question_id}")
async def trigger_scrape(question_id: int):
    """Trigger scraping for a specific question"""
    try:
        # Run the scrape job in background
        asyncio.create_task(scrape_chatgpt_job(question_id))
        return {"message": f"Scraping triggered for question {question_id}"}
    except Exception as e:
        logger.error(f"Failed to trigger scrape: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def start_scheduler():
    """Start the scheduler in a separate thread"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Initialize scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    
    # Add the scraping job
    scheduler.add_job(
        scrape_chatgpt_job,
        trigger=IntervalTrigger(seconds=settings.scrape_interval_sec),
        id="ask_chatgpt",
        name="ChatGPT Scraping Job",
        replace_existing=True
    )
    
    # Start scheduler
    scheduler.start()
    logger.info(f"Scheduler started with interval: {settings.scrape_interval_sec} seconds")
    
    try:
        # Keep the scheduler running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down scheduler...")
        scheduler.shutdown()


async def startup():
    """Startup event handler"""
    logger.info("Starting PandaRank ChatGPT Scraper")
    
    # Start Prometheus metrics server on different port
    start_http_server(9090)  # Use 9090 for metrics, 8080 for FastAPI
    logger.info(f"Prometheus metrics available on port 9090")
    
    # Initialize database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler thread started")


app.add_event_handler("startup", startup)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)