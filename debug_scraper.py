#!/usr/bin/env python3
"""
调试脚本 - 以可见浏览器模式运行爬虫
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.app.config import settings
import logging

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_scrape():
    # 强制使用非headless模式
    original_headless = settings.headless
    settings.headless = False
    
    # 确保不是demo模式
    logger.info(f"Demo mode: {settings.demo_mode}")
    logger.info(f"Headless: {settings.headless}")
    logger.info(f"Has session token: {bool(settings.openai_session_token)}")
    logger.info(f"Has email/pwd: {bool(settings.openai_email and settings.openai_pwd)}")
    
    from playwright.async_api import async_playwright
    
    try:
        logger.info("初始化浏览器...")
        playwright = await async_playwright().start()
        # 尝试使用webkit（Safari引擎）来避免chromium崩溃问题
        browser = await playwright.webkit.launch(
            headless=settings.headless
        )
        
        # Create context with viewport
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        page.set_default_timeout(settings.page_timeout)
        
        logger.info("导航到ChatGPT...")
        await page.goto("https://chat.openai.com", wait_until="networkidle")
        logger.info(f"当前URL: {page.url}")
        
        # Try session token
        if settings.openai_session_token:
            logger.info(f"尝试使用session token登录 (长度: {len(settings.openai_session_token)})")
            # 尝试两个域名
            cookies = [
                {
                    'name': '__Secure-next-auth.session-token',
                    'value': settings.openai_session_token,
                    'domain': '.chatgpt.com',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True,
                    'sameSite': 'Lax'
                },
                {
                    'name': '__Secure-next-auth.session-token',
                    'value': settings.openai_session_token,
                    'domain': '.openai.com',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True,
                    'sameSite': 'Lax'
                }
            ]
            for cookie in cookies:
                try:
                    await context.add_cookies([cookie])
                    logger.info(f"添加cookie到域名: {cookie['domain']}")
                except Exception as e:
                    logger.warning(f"添加cookie失败 {cookie['domain']}: {e}")
            await page.reload()
            logger.info("页面重新加载中...")
            await asyncio.sleep(3)
            
            # Check if logged in
            try:
                await page.wait_for_selector('button[aria-label="User menu"]', timeout=5000)
                logger.info("登录成功！找到用户菜单")
            except:
                logger.warning("未找到用户菜单，可能登录失败")
                # 尝试其他选择器
                try:
                    await page.wait_for_selector('nav[role="navigation"]', timeout=3000)
                    logger.info("找到导航栏，可能已登录")
                except:
                    logger.error("登录失败")
                    # 截图查看当前页面
                    await page.screenshot(path="login_failed.png")
                    logger.info("登录失败截图已保存到: login_failed.png")
        
        # 测试问题
        test_question = "巴厘岛有哪些必去的景点？需要注意什么？"
        logger.info(f"发送测试问题: {test_question}")
        
        # 查找输入框
        logger.info("查找输入框...")
        textarea = await page.wait_for_selector('textarea[placeholder*="Message"]')
        logger.info("找到输入框，填入文本")
        await textarea.fill(test_question)
        
        # 提交
        logger.info("按下Enter键提交")
        await page.press('textarea[placeholder*="Message"]', 'Enter')
        
        # 等待响应
        logger.info("等待响应...")
        await asyncio.sleep(5)  # 等待一会儿
        
        # 获取页面截图
        screenshot_path = "chatgpt_response.png"
        await page.screenshot(path=screenshot_path)
        logger.info(f"页面截图已保存到: {screenshot_path}")
        
        # 等待一下让你看看页面
        logger.info("\n按Enter键关闭浏览器...")
        input()
        
    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)
    finally:
        await browser.close()
        settings.headless = original_headless

if __name__ == "__main__":
    asyncio.run(debug_scrape())