import asyncio
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pathlib import Path
import json

from playwright.async_api import async_playwright, Page, BrowserContext
from sqlalchemy.orm import Session
from loguru import logger

from .models import Conversation, Message, WebSearch, Artifact
from .config import settings


class ChatGPTScraper:
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.browser = None
        self.context = None
        self.page = None
        self.run_uuid = uuid.uuid4()
        self.artifacts_dir = Path("/app/artifacts")
        self.artifacts_dir.mkdir(exist_ok=True)
        
    async def initialize(self):
        """Initialize Playwright browser and context"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=settings.headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        # Create context with viewport
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        # Set up request interception
        self.context.on("requestfinished", self._handle_request_finished)
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(settings.page_timeout)
        
        # Set up console monitoring
        self.page.on("console", self._handle_console)
        
        logger.info("Browser initialized successfully")
    
    async def login(self):
        """Login to ChatGPT using session token or credentials"""
        logger.info("开始导航到 ChatGPT...")
        await self.page.goto("https://chat.openai.com", wait_until="networkidle")
        logger.info(f"当前URL: {self.page.url}")
        
        # Try session token first
        if settings.openai_session_token:
            logger.info(f"尝试使用session token登录 (长度: {len(settings.openai_session_token)})")
            await self.context.add_cookies([{
                'name': '__Secure-next-auth.session-token',
                'value': settings.openai_session_token,
                'domain': '.openai.com',
                'path': '/',
                'secure': True,
                'httpOnly': True,
                'sameSite': 'Lax'
            }])
            await self.page.reload()
            logger.info("页面重新加载中...")
            await asyncio.sleep(3)
            
            # Check if logged in
            login_status = await self._is_logged_in()
            logger.info(f"登录状态检查结果: {login_status}")
            if login_status:
                logger.info("Logged in successfully with session token")
                return
            else:
                logger.warning("Session token登录失败")
        
        # Fallback to email/password
        if settings.openai_email and settings.openai_pwd:
            await self._login_with_credentials()
        else:
            error_msg = """
❌ 无法登录ChatGPT - 缺少认证信息

请配置以下任一认证方式：

方法1（推荐）- Session Token:
1. 浏览器打开 https://chat.openai.com 并登录
2. 按F12打开开发者工具
3. Application → Cookies → chat.openai.com
4. 复制 '__Secure-next-auth.session-token' 的值
5. 在.env文件中设置: OPENAI_SESSION_TOKEN=你的token

方法2 - 邮箱密码:
在.env文件中设置:
OPENAI_EMAIL=your@email.com
OPENAI_PWD=your_password

当前配置状态:
- Session Token: {f'已配置({len(settings.openai_session_token)}字符)' if settings.openai_session_token else '❌ 未配置'}
- 邮箱: {f'已配置({settings.openai_email})' if settings.openai_email else '❌ 未配置'}
- 密码: {f'已配置({len(settings.openai_pwd)}字符)' if settings.openai_pwd else '❌ 未配置'}
            """.strip()
            raise Exception(error_msg)
    
    async def _login_with_credentials(self):
        """Login using email and password"""
        # Click login button
        await self.page.click('button:has-text("Log in")')
        await asyncio.sleep(2)
        
        # Enter email
        await self.page.fill('input[name="username"]', settings.openai_email)
        await self.page.click('button[type="submit"]')
        await asyncio.sleep(2)
        
        # Enter password
        await self.page.fill('input[name="password"]', settings.openai_pwd)
        await self.page.click('button[type="submit"]')
        
        # Wait for login to complete
        await self.page.wait_for_url("https://chat.openai.com/**", timeout=30000)
        
        if await self._is_logged_in():
            logger.info("Logged in successfully with credentials")
        else:
            raise Exception("Login failed")
    
    async def _is_logged_in(self) -> bool:
        """Check if user is logged in"""
        try:
            # Look for the new chat button or user menu
            logger.debug("检查登录状态...")
            await self.page.wait_for_selector('button[aria-label="User menu"]', timeout=5000)
            logger.debug("找到用户菜单按钮")
            return True
        except:
            logger.debug("未找到用户菜单按钮")
            # 尝试其他选择器
            try:
                await self.page.wait_for_selector('nav[role="navigation"]', timeout=3000)
                logger.debug("找到导航栏")
                return True
            except:
                logger.debug("未找到导航栏")
                return False
    
    async def submit_prompt(self, conversation_id: int, prompt_text: str) -> Dict:
        """Submit a prompt and capture the response"""
        # Navigate to new chat
        logger.info(f"提交问题: {prompt_text[:50]}...")
        await self.page.goto("https://chat.openai.com", wait_until="networkidle")
        await asyncio.sleep(2)
        logger.info(f"当前页面URL: {self.page.url}")
        
        # Store browsing events
        self.browsing_events = []
        
        # Find and fill the prompt textarea
        logger.info("查找输入框...")
        textarea = await self.page.wait_for_selector('textarea[placeholder*="Message"]')
        logger.info("找到输入框，填入文本")
        await textarea.fill(prompt_text)
        
        # Submit the prompt
        logger.info("按下Enter键提交")
        await self.page.press('textarea[placeholder*="Message"]', 'Enter')
        
        # Save user message
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content_md=prompt_text
        )
        self.db_session.add(user_msg)
        self.db_session.commit()
        
        # Wait for response to complete
        logger.info("等待响应完成...")
        await self._wait_for_response_completion()
        
        # Capture the assistant's response
        logger.info("提取助手响应...")
        response_text = await self._extract_assistant_response()
        logger.info(f"响应长度: {len(response_text)} 字符")
        
        # Save assistant message
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content_md=response_text
        )
        self.db_session.add(assistant_msg)
        
        # Save browsing events
        for event in self.browsing_events:
            web_search = WebSearch(
                conversation_id=conversation_id,
                url=event.get('url'),
                title=event.get('title')
            )
            self.db_session.add(web_search)
        
        # Capture artifacts
        await self._capture_artifacts(conversation_id)
        
        self.db_session.commit()
        
        return {
            "response": response_text,
            "browsing_events": self.browsing_events
        }
    
    async def submit_prompt_csv(self, conversation_id: int, prompt_text: str, storage) -> Dict:
        """Submit a prompt and capture the response (CSV version)"""
        # Navigate to new chat
        await self.page.goto("https://chat.openai.com", wait_until="networkidle")
        await asyncio.sleep(2)
        
        # Store browsing events
        self.browsing_events = []
        
        # Find and fill the prompt textarea
        logger.info("查找输入框...")
        textarea = await self.page.wait_for_selector('textarea[placeholder*="Message"]')
        logger.info("找到输入框，填入文本")
        await textarea.fill(prompt_text)
        
        # Submit the prompt
        logger.info("按下Enter键提交")
        await self.page.press('textarea[placeholder*="Message"]', 'Enter')
        
        # Wait for response to complete
        logger.info("等待响应完成...")
        await self._wait_for_response_completion()
        
        # Capture the assistant's response
        logger.info("提取助手响应...")
        response_text = await self._extract_assistant_response()
        logger.info(f"响应长度: {len(response_text)} 字符")
        
        # Save assistant message to CSV
        storage.add_message(conversation_id, "assistant", response_text)
        
        # Save browsing events to CSV
        for event in self.browsing_events:
            storage.add_web_search(
                conversation_id,
                event.get('url', ''),
                event.get('title', '')
            )
        
        # 抓取思考过程和搜索信息
        await self._capture_reasoning_and_search_info_csv(conversation_id, storage)
        
        # Capture artifacts (simplified for CSV)
        await self._capture_artifacts_csv(conversation_id, storage)
        
        return {
            "response": response_text,
            "browsing_events": self.browsing_events
        }
    
    async def _wait_for_response_completion(self):
        """Wait for the assistant to finish responding"""
        # Wait for typing indicator to appear and disappear
        try:
            logger.debug("等待输入指示器出现...")
            await self.page.wait_for_selector('.typing-cursor', state='attached', timeout=10000)
            logger.debug("检测到输入指示器，等待完成...")
            await self.page.wait_for_selector('.typing-cursor', state='detached', timeout=120000)
            logger.debug("输入指示器消失")
        except:
            # Alternative: wait for the stop generating button to disappear
            logger.debug("未找到输入指示器，尝试其他方法")
            try:
                await self.page.wait_for_selector('button:has-text("Stop generating")', state='detached', timeout=120000)
                logger.debug("停止生成按钮消失")
            except:
                logger.debug("未找到停止生成按钮")
                pass
        
        # Additional wait to ensure content is fully rendered
        await asyncio.sleep(2)
    
    async def _extract_assistant_response(self) -> str:
        """Extract the assistant's response from the page"""
        logger.debug("开始提取助手响应")
        # Try multiple selectors to find the response
        selectors = [
            '[data-testid*="conversation-turn"]:has(.markdown)',
            '[data-message-author-role="assistant"]',
            '.group:has(.markdown)',
            '.markdown',
            '[class*="markdown"]',
            '.prose'
        ]
        
        for selector in selectors:
            try:
                logger.debug(f"尝试选择器: {selector}")
                messages = await self.page.query_selector_all(selector)
                if messages:
                    logger.debug(f"找到 {len(messages)} 个消息元素")
                    # Get the last message
                    last_message = messages[-1]
                    
                    # Try to extract text content
                    text = await last_message.inner_text()
                    if text and text.strip():
                        logger.info(f"Found response using selector: {selector}")
                        return text.strip()
                        
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        # Fallback: try to get any text content from the page
        try:
            # Look for any recent text that might be the response
            await asyncio.sleep(3)  # Wait a bit more
            full_text = await self.page.inner_text('body')
            
            # Try to find the response in the full page text
            # This is a simple approach - look for text after the question
            if full_text:
                lines = full_text.split('\n')
                response_lines = []
                found_response = False
                
                for line in lines:
                    if found_response and line.strip():
                        response_lines.append(line.strip())
                    elif line.strip() and not found_response:
                        # Look for a line that might indicate the start of assistant response
                        if any(word in line.lower() for word in ['assistant', 'chatgpt', 'response']):
                            found_response = True
                
                if response_lines:
                    return '\n'.join(response_lines[:50])  # Limit to first 50 lines
                    
        except Exception as e:
            logger.warning(f"Fallback text extraction failed: {e}")
        
        logger.warning("Could not extract assistant response")
        return ""
    
    async def _handle_console(self, msg):
        """Handle console messages to detect browsing events"""
        text = msg.text
        if "Searching" in text or "Visiting" in text:
            logger.info(f"Browsing event detected: {text}")
            self.browsing_events.append({
                "type": "console",
                "text": text,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    async def _handle_request_finished(self, request):
        """Handle finished requests to capture browsing URLs"""
        url = request.url
        # Filter for relevant domains
        relevant_domains = ['google.com', 'wikipedia.org', 'bing.com', 'duckduckgo.com']
        
        if any(domain in url for domain in relevant_domains):
            logger.info(f"Captured browsing URL: {url}")
            self.browsing_events.append({
                "type": "request",
                "url": url,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    async def _capture_artifacts(self, conversation_id: int):
        """Capture screenshots and HTML content"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        conv_dir = self.artifacts_dir / str(conversation_id)
        conv_dir.mkdir(exist_ok=True)
        
        # Capture screenshot
        screenshot_path = conv_dir / f"screenshot_{timestamp}.png"
        await self.page.screenshot(path=str(screenshot_path), full_page=True)
        
        screenshot_artifact = Artifact(
            conversation_id=conversation_id,
            type="screenshot",
            path=str(screenshot_path)
        )
        self.db_session.add(screenshot_artifact)
        
        # Capture HTML
        html_content = await self.page.content()
        html_path = conv_dir / f"page_{timestamp}.html"
        html_path.write_text(html_content)
        
        html_artifact = Artifact(
            conversation_id=conversation_id,
            type="html",
            path=str(html_path)
        )
        self.db_session.add(html_artifact)
        
        logger.info(f"Captured artifacts for conversation {conversation_id}")
    
    async def _capture_artifacts_csv(self, conversation_id: int, storage):
        """Capture screenshots and HTML content (CSV version)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        conv_dir = self.artifacts_dir / str(conversation_id)
        conv_dir.mkdir(exist_ok=True)
        
        # Capture screenshot
        screenshot_path = conv_dir / f"screenshot_{timestamp}.png"
        await self.page.screenshot(path=str(screenshot_path), full_page=True)
        storage.add_artifact(conversation_id, "screenshot", str(screenshot_path))
        
        # Capture HTML
        html_content = await self.page.content()
        html_path = conv_dir / f"page_{timestamp}.html"
        html_path.write_text(html_content)
        storage.add_artifact(conversation_id, "html", str(html_path))
        
        logger.info(f"Captured artifacts for conversation {conversation_id}")
    
    async def _capture_reasoning_and_search_info_csv(self, conversation_id: int, storage):
        """抓取思考过程和搜索信息 (CSV版本)"""
        try:
            # 等待页面完全加载
            await asyncio.sleep(3)
            
            # 尝试查找和点击思考过程按钮
            reasoning_content = await self._extract_reasoning_process()
            if reasoning_content:
                storage.add_reasoning(conversation_id, reasoning_content)
                logger.info(f"Captured reasoning process for conversation {conversation_id}")
            
            # 抓取搜索查询和访问网站
            search_info = await self._extract_search_information()
            
            # 保存搜索查询
            for query in search_info.get('queries', []):
                storage.add_search_query(conversation_id, query)
            
            # 保存访问网站
            for site in search_info.get('sites', []):
                storage.add_visited_site(
                    conversation_id,
                    site.get('url', ''),
                    site.get('title', ''),
                    site.get('description', '')
                )
            
            logger.info(f"Captured {len(search_info.get('queries', []))} search queries and {len(search_info.get('sites', []))} visited sites")
            
        except Exception as e:
            logger.warning(f"Failed to capture reasoning/search info: {e}")
    
    async def _extract_reasoning_process(self) -> str:
        """提取思考过程"""
        try:
            # 尝试多种可能的思考过程按钮选择器
            reasoning_selectors = [
                'button[aria-label*="reasoning"]',
                'button[aria-label*="思考"]',
                'button[aria-label*="Reasoning"]',
                '[data-testid*="reasoning"]',
                'button:has-text("思考过程")',
                'button:has-text("推理")',
                'button:has-text("Show reasoning")',
                'button[aria-expanded="false"]',
                '.reasoning-toggle',
                '.thinking-toggle'
            ]
            
            for selector in reasoning_selectors:
                try:
                    reasoning_button = await self.page.query_selector(selector)
                    if reasoning_button:
                        # 点击展开思考过程
                        await reasoning_button.click()
                        await asyncio.sleep(2)
                        
                        # 尝试提取思考过程内容
                        reasoning_content_selectors = [
                            '[data-testid*="reasoning-content"]',
                            '.reasoning-content',
                            '.thinking-content',
                            '[role="region"][aria-label*="reasoning"]',
                            '.expandable-content',
                            '[data-message-author-role="system"]'
                        ]
                        
                        for content_selector in reasoning_content_selectors:
                            reasoning_element = await self.page.query_selector(content_selector)
                            if reasoning_element:
                                content = await reasoning_element.inner_text()
                                if content and len(content.strip()) > 10:
                                    logger.info(f"Found reasoning content using selector: {content_selector}")
                                    return content.strip()
                        
                        break
                except Exception as e:
                    logger.debug(f"Reasoning selector {selector} failed: {e}")
                    continue
            
            return ""
            
        except Exception as e:
            logger.warning(f"Failed to extract reasoning process: {e}")
            return ""
    
    async def _extract_search_information(self) -> Dict:
        """提取搜索信息"""
        try:
            search_info = {"queries": [], "sites": []}
            
            # 查找搜索区域
            search_area_selectors = [
                '[aria-label*="search"]',
                '[data-testid*="search"]',
                '.search-results',
                '.web-search-results',
                '[role="region"]:has-text("搜索")',
                '[role="region"]:has-text("已搜索网页")',
                '.search-queries',
                '.browsing-section'
            ]
            
            for selector in search_area_selectors:
                try:
                    search_area = await self.page.query_selector(selector)
                    if search_area:
                        # 提取搜索查询
                        query_elements = await search_area.query_selector_all('text=/^(best|new|top|how|what|where|when|why)/i')
                        for element in query_elements:
                            query_text = await element.inner_text()
                            if query_text and len(query_text.strip()) > 3:
                                search_info["queries"].append(query_text.strip())
                        
                        # 提取访问的网站
                        site_elements = await search_area.query_selector_all('a[href*="http"]')
                        for element in site_elements:
                            try:
                                url = await element.get_attribute('href')
                                title = await element.inner_text()
                                
                                if url and title:
                                    search_info["sites"].append({
                                        "url": url,
                                        "title": title.strip(),
                                        "description": ""
                                    })
                            except:
                                continue
                        
                        break
                except Exception as e:
                    logger.debug(f"Search area selector {selector} failed: {e}")
                    continue
            
            # 尝试点击"显示更多"按钮获取额外搜索结果
            try:
                show_more_selectors = [
                    'button:has-text("显示")',
                    'button:has-text("更多")',
                    'button:has-text("Show more")',
                    'button:has-text("再显示")',
                    '[data-testid*="show-more"]',
                    '.show-more-button'
                ]
                
                for selector in show_more_selectors:
                    show_more_button = await self.page.query_selector(selector)
                    if show_more_button:
                        await show_more_button.click()
                        await asyncio.sleep(2)
                        
                        # 重新提取更多的网站信息
                        additional_sites = await self.page.query_selector_all('a[href*="http"]')
                        for element in additional_sites[-10:]:  # 只取最后10个新的
                            try:
                                url = await element.get_attribute('href')
                                title = await element.inner_text()
                                
                                if url and title and not any(site['url'] == url for site in search_info["sites"]):
                                    search_info["sites"].append({
                                        "url": url,
                                        "title": title.strip(),
                                        "description": ""
                                    })
                            except:
                                continue
                        break
            except Exception as e:
                logger.debug(f"Failed to click show more: {e}")
            
            # 去重
            search_info["queries"] = list(set(search_info["queries"]))
            seen_urls = set()
            unique_sites = []
            for site in search_info["sites"]:
                if site["url"] not in seen_urls:
                    seen_urls.add(site["url"])
                    unique_sites.append(site)
            search_info["sites"] = unique_sites
            
            return search_info
            
        except Exception as e:
            logger.warning(f"Failed to extract search information: {e}")
            return {"queries": [], "sites": []}
    
    async def cleanup(self):
        """Clean up browser resources"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser cleanup completed")