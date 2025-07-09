import asyncio
import uuid
import yaml
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import threading

from .config import settings
from .csv_storage import CSVStorage
from .scraper import ChatGPTScraper


# Prometheus metrics
scrape_counter = Counter('chatgpt_scrapes_total', 'Total number of scrape attempts')
scrape_success_counter = Counter('chatgpt_scrapes_success', 'Total number of successful scrapes')
scrape_failure_counter = Counter('chatgpt_scrapes_failed', 'Total number of failed scrapes')
scrape_duration = Histogram('chatgpt_scrape_duration_seconds', 'Time spent scraping')
active_scrapes = Gauge('chatgpt_active_scrapes', 'Number of active scrape jobs')

# CSV存储实例
storage = CSVStorage()

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
   - 地址：东京多个分店
   - 特色：豚骨拉面，独特的个人隔间用餐体验
   - 推荐理由：24小时营业，汤头浓郁，面条劲道

2. **麦丽景德 (Menya Itto)**
   - 地址：池袋东口
   - 特色：鸡白汤拉面
   - 推荐理由：被称为东京最好吃的鸡汤拉面之一

3. **俺の拉面 (Ore no Ramen)**
   - 地址：新宿歌舞伎町
   - 特色：浓厚豚骨拉面
   - 推荐理由：超级浓郁的汤头，分量十足

4. **饺子的王将**
   - 地址：东京多个分店
   - 特色：中华拉面、饺子套餐
   - 推荐理由：性价比超高，味道正宗

5. **Menba Yorozuya**
   - 地址：新宿区神楽坂
   - 特色：创新口味拉面
   - 推荐理由：每日限量，口味独特""",
        
        "上海": """上海最正宗的小笼包推荐：

**前5名地点：**

1. **南翔馒头店（城隍庙总店）**
   - 地址：上海市黄浦区豫园老街85号
   - 特色：百年老店，传统工艺
   - 推荐理由：小笼包发源地，皮薄汁多

2. **鼎泰丰**
   - 地址：上海多个分店
   - 特色：台式小笼包
   - 推荐理由：18个褶子的标准，品质稳定

3. **佳家汤包**
   - 地址：黄河路90号
   - 特色：生煎包和小笼包
   - 推荐理由：本地人最爱，价格实惠

4. **王家沙**
   - 地址：南京西路805号
   - 特色：蟹粉小笼
   - 推荐理由：季节限定，蟹黄丰富

5. **杨家厨房**
   - 地址：衡山路店
   - 特色：精品小笼包
   - 推荐理由：创新口味，环境优雅""",
        
        "广东": """广东电子配件制造工厂推荐：

**主要制造基地：**

1. **深圳市**
   - 华强北电子市场周边工厂群
   - 主营：手机配件、电子元器件
   - 优势：产业链完整，技术先进

2. **东莞市**
   - 长安镇、塘厦镇工业区
   - 主营：连接器、线缆、精密配件
   - 优势：富士康等大厂带动产业集群

3. **惠州市**
   - 仲恺高新技术产业开发区
   - 主营：电路板、传感器
   - 优势：成本相对较低，配套齐全

4. **中山市**
   - 火炬开发区
   - 主营：LED灯具、小家电配件
   - 优势：灯饰产业链成熟

5. **佛山市**
   - 顺德区、南海区
   - 主营：家电配件、工业电子
   - 优势：制造业基础雄厚""",
        
        "默认": """感谢您的提问！根据我的分析，这是一个很有趣的话题。

**主要观点：**

1. **第一个方面**
   - 详细说明和分析
   - 相关的背景信息

2. **第二个方面**
   - 深入的解释
   - 实际的应用场景

3. **第三个方面**
   - 重要的注意事项
   - 建议和推荐

**总结：**
综合以上分析，建议您根据具体需求选择最合适的方案。如果需要更详细的信息，建议进一步咨询相关专业人士。"""
    }
    
    # 根据关键词匹配响应
    for keyword, response in demo_responses.items():
        if keyword in question_text:
            return response
    
    return demo_responses["默认"]

def load_questions_from_yaml():
    """从YAML文件加载问题"""
    questions_file = Path("/app/data/geo_questions.yaml")
    questions = []
    
    if questions_file.exists():
        with open(questions_file, 'r', encoding='utf-8') as f:
            questions = yaml.safe_load(f)
    
    return questions or []

def get_question_by_id(question_id: int):
    """根据ID获取问题"""
    questions = load_questions_from_yaml()
    
    for q in questions:
        if q.get('id') == question_id:
            return q.get('text', 'Unknown question')
    
    return None

async def scrape_chatgpt_job(question_id: int = None):
    """Main job that runs on schedule or manually triggered"""
    job_start = time.time()
    scrape_counter.inc()
    active_scrapes.inc()
    
    run_uuid = str(uuid.uuid4())
    
    try:
        logger.info(f"Starting scrape job with run_uuid: {run_uuid}")
        
        # 获取问题
        if question_id:
            question_text = get_question_by_id(question_id)
            if not question_text:
                logger.error(f"Question with id {question_id} not found")
                return
        else:
            # 默认使用第一个问题
            questions = load_questions_from_yaml()
            if not questions:
                logger.error("No questions available")
                return
            
            # 获取第一个问题
            first_category = next(iter(questions.values()))
            question_text = first_category[0] if first_category else "Test question"
            question_id = 1
        
        # 创建对话记录
        conversation_id = storage.create_conversation(run_uuid, question_id, question_text)
        logger.info(f"Created conversation {conversation_id} for question: {question_text}")
        
        # 检查是否是demo模式
        if settings.demo_mode:
            # Demo模式 - 模拟响应
            logger.info("Running in DEMO mode - simulating ChatGPT response")
            
            # 添加用户消息
            storage.add_message(conversation_id, "user", question_text)
            
            # 生成demo响应
            demo_response = generate_demo_response(question_text)
            storage.add_message(conversation_id, "assistant", demo_response)
            
            # 添加demo网页搜索
            demo_searches = [
                ("https://www.google.com/search?q=" + question_text.replace(" ", "+"), "Google搜索结果"),
                ("https://www.tripadvisor.com", "TripAdvisor - 旅游推荐"),
                ("https://www.tabelog.com", "Tabelog - 日本美食评价网站")
            ]
            
            for url, title in demo_searches:
                storage.add_web_search(conversation_id, url, title)
            
            # 添加demo思考过程
            demo_reasoning = f"""用户想知道"{question_text}"，考虑到之前的类似查询（如"TOKYO经典豚骨"，以及"东京附近好吃的面馆"），可以推测用户确实在寻找东京的最好拉面建议。鉴于拉面店的不断变化，我会搜索最新的排名和评论。比如，可以关注米其林星级拉面店，如"那木流"、"筑地和牛"等，并提供多种风格的推荐。

我想为用户提供东京拉面店的建议，并可能提供图片和地图链接。不过，我觉得不需要过多询问，直接给出推荐会更简洁有效。

我想为用户提供东京拉面店的建议，并可能提供图片和地图链接。不过，我觉得不需要过多询问，直接给出推荐会更简洁有效。关于展示图片，我可以用图片轮播的形式展示四家拉面店。这样用户可以直观地了解每家店的特点，然后再根据需要进一步探索，也许这样的形式会更适合一些。

我会根据用户的信息寻找东京的最佳拉面店。在这过程中，我打算先通过搜索获取2025年排名、米其林星级和一些新兴的拉面店。然后，再根据风味（如酱油、盐味、豚骨等）进行分类总结。我将提供详细的店名、地址、推荐理由以及一些小贴士（如排队的最佳时段等）。最后，我可能会展示几家店的图片，确保用户有一个全面的视觉体验。"""
            
            storage.add_reasoning(conversation_id, demo_reasoning)
            
            # 添加demo搜索查询
            demo_queries = [
                "best ramen in Tokyo 2025 list",
                "Michelin star ramen Tokyo 2024 Nakiryu Hototogisu Konjiki Tsuta update", 
                "new ramen shop Tokyo 2024 award winning"
            ]
            
            for query in demo_queries:
                storage.add_search_query(conversation_id, query)
            
            # 添加demo访问网站
            demo_sites = [
                {"url": "https://www.twowanderingsoles.com", "title": "Two Wandering Soles", "description": "Travel and food blog"},
                {"url": "https://www.timeout.com", "title": "Time Out Tokyo", "description": "Tokyo dining guide"},
                {"url": "https://www.reddit.com", "title": "Reddit - Tokyo Ramen Discussion", "description": "Community recommendations"},
                {"url": "https://tabelog.com", "title": "Tabelog", "description": "Japanese restaurant reviews"},
                {"url": "https://www.tokyocheapo.com", "title": "Tokyo Cheapo", "description": "Budget dining guide"},
                {"url": "https://gurunavi.com", "title": "Gurunavi", "description": "Restaurant booking platform"}
            ]
            
            for site in demo_sites:
                storage.add_visited_site(conversation_id, site["url"], site["title"], site["description"])
            
            # 标记对话完成
            storage.finish_conversation(conversation_id)
            
            logger.info(f"DEMO: Generated response for question {question_id}")
            scrape_success_counter.inc()
            
        else:
            # 真实模式 - 使用ChatGPT
            scraper = ChatGPTScraper(None)  # 不需要数据库session
            await scraper.initialize()
            
            try:
                # 登录
                await scraper.login()
                logger.info("ChatGPT login successful")
                
                # 添加用户消息
                storage.add_message(conversation_id, "user", question_text)
                
                # 提交问题并获取响应
                result = await scraper.submit_prompt_csv(conversation_id, question_text, storage)
                
                # 标记对话完成
                storage.finish_conversation(conversation_id)
                
                logger.info(f"Successfully scraped response for question {question_id}")
                logger.info(f"Response preview: {result.get('response', '')[:100]}...")
                logger.info(f"Browsing events: {len(result.get('browsing_events', []))}")
                
                scrape_success_counter.inc()
                
            except Exception as e:
                logger.error(f"ChatGPT scraping failed: {e}")
                # 即使失败也标记对话完成
                storage.finish_conversation(conversation_id)
                raise
                
            finally:
                await scraper.cleanup()
            
    except Exception as e:
        logger.error(f"Scrape job failed: {e}")
        scrape_failure_counter.inc()
        
    finally:
        active_scrapes.dec()
        duration = time.time() - job_start
        scrape_duration.observe(duration)
        logger.info(f"Scrape job completed in {duration:.2f} seconds")

@app.post("/scrape/{question_id}")
async def scrape_endpoint(question_id: int):
    """HTTP endpoint to trigger scraping"""
    asyncio.create_task(scrape_chatgpt_job(question_id))
    return {"status": "triggered", "question_id": question_id}

@app.get("/")
async def root():
    return {"status": "ok", "message": "PandaRank ChatGPT Scraper"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# 调度器
scheduler = AsyncIOScheduler()

def start_scheduler():
    """Start the background scheduler"""
    try:
        # 添加定时任务
        scheduler.add_job(
            scrape_chatgpt_job,
            IntervalTrigger(seconds=settings.scrape_interval_sec),
            id='scrape_job',
            max_instances=1,
            replace_existing=True
        )
        
        if not scheduler.running:
            scheduler.start()
            logger.info(f"Scheduler started with interval: {settings.scrape_interval_sec} seconds")
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

@app.on_event("startup")
async def startup():
    """Application startup"""
    logger.info("Starting PandaRank ChatGPT Scraper")
    
    # 启动Prometheus监控
    try:
        start_http_server(9090)  # 修改端口避免冲突
        logger.info("Prometheus metrics available on port 9090")
    except Exception as e:
        logger.warning(f"Failed to start Prometheus server: {e}")
    
    # 初始化CSV存储
    logger.info("CSV storage initialized")
    
    # 启动调度器
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    logger.info("Scheduler thread started")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)