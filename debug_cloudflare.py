#!/usr/bin/env python3
"""
调试脚本 - 处理Cloudflare验证
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.app.config import settings
import logging
from playwright.async_api import async_playwright
from pathlib import Path

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def handle_cloudflare():
    # 强制使用非headless模式
    settings.headless = False
    
    playwright = await async_playwright().start()
    browser = await playwright.webkit.launch(headless=False)
    
    try:
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        logger.info("导航到ChatGPT...")
        await page.goto("https://chatgpt.com", wait_until="networkidle")
        logger.info(f"当前URL: {page.url}")
        
        # 等待一下看是否有Cloudflare验证
        await asyncio.sleep(3)
        
        # 截图当前页面
        screenshot_path = "cloudflare_challenge.png"
        await page.screenshot(path=screenshot_path)
        logger.info(f"截图已保存到: {screenshot_path}")
        
        # 检查是否有Cloudflare验证
        cloudflare_selectors = [
            'iframe[src*="challenges.cloudflare.com"]',
            'div:has-text("正在验证")',
            'div:has-text("Checking")',
            '.cf-turnstile',
            '#turnstile-wrapper'
        ]
        
        has_cloudflare = False
        for selector in cloudflare_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=1000)
                if element:
                    has_cloudflare = True
                    logger.info(f"检测到Cloudflare验证: {selector}")
                    break
            except:
                continue
        
        if has_cloudflare:
            logger.info("需要完成Cloudflare验证")
            
            # 查找验证按钮或复选框
            verify_selectors = [
                'input[type="checkbox"]',
                'button:has-text("验证")',
                'button:has-text("Verify")',
                '.cf-turnstile input',
                'iframe[src*="challenges.cloudflare.com"]'
            ]
            
            for selector in verify_selectors:
                try:
                    if 'iframe' in selector:
                        # 处理iframe内的验证
                        logger.info("发现iframe验证")
                        iframe_element = await page.wait_for_selector(selector, timeout=2000)
                        frame = await iframe_element.content_frame()
                        if frame:
                            # 在iframe内查找checkbox
                            checkbox = await frame.wait_for_selector('input[type="checkbox"]', timeout=2000)
                            if checkbox:
                                await checkbox.click()
                                logger.info("点击了iframe内的验证框")
                    else:
                        element = await page.wait_for_selector(selector, timeout=2000)
                        if element:
                            await element.click()
                            logger.info(f"点击了验证元素: {selector}")
                            break
                except Exception as e:
                    logger.debug(f"尝试 {selector} 失败: {e}")
                    continue
            
            # 等待验证完成
            logger.info("等待验证完成...")
            await asyncio.sleep(5)
            
            # 再次截图
            await page.screenshot(path="after_verification.png")
            logger.info("验证后截图已保存")
        
        # 检查是否到达登录页面
        if "chatgpt.com" in page.url:
            logger.info("成功通过验证，现在在ChatGPT页面")
            
            # 尝试登录
            logger.info("查找登录按钮...")
            login_selectors = [
                'button:has-text("登录")',
                'button:has-text("Log in")',
                '[data-testid="login-button"]'
            ]
            
            for selector in login_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    await element.click()
                    logger.info(f"点击了登录按钮: {selector}")
                    break
                except:
                    continue
            
            await asyncio.sleep(3)
            
            # 使用session token登录
            if settings.openai_session_token:
                logger.info("尝试使用session token登录")
                await context.add_cookies([{
                    'name': '__Secure-next-auth.session-token',
                    'value': settings.openai_session_token,
                    'domain': '.chatgpt.com',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True,
                    'sameSite': 'Lax'
                }])
                await page.reload()
                await asyncio.sleep(3)
                
                # 检查登录状态
                try:
                    await page.wait_for_selector('textarea[placeholder*="Message"]', timeout=5000)
                    logger.info("登录成功！找到消息输入框")
                    
                    # 保存cookies
                    cookies = await context.cookies()
                    logger.info(f"已获取 {len(cookies)} 个cookies")
                    
                    # 测试发送消息
                    textarea = await page.wait_for_selector('textarea[placeholder*="Message"]')
                    await textarea.fill("巴厘岛有哪些必去的景点？")
                    await page.press('textarea[placeholder*="Message"]', 'Enter')
                    
                    logger.info("已发送测试消息，等待响应...")
                    await asyncio.sleep(10)
                    
                    await page.screenshot(path="chatgpt_response.png")
                    logger.info("响应截图已保存")
                    
                except:
                    logger.error("登录失败或未找到输入框")
                    await page.screenshot(path="login_failed.png")
        
        # 清理验证码截图
        if Path(screenshot_path).exists() and has_cloudflare:
            os.remove(screenshot_path)
            logger.info("已删除验证码截图")
        
        logger.info("\n按Enter键关闭浏览器...")
        input()
        
    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(handle_cloudflare())