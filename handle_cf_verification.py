#!/usr/bin/env python3
"""
智能处理Cloudflare验证
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.app.config import settings
import logging
from playwright.async_api import async_playwright
from pathlib import Path
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def smart_cloudflare_handler():
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
        await page.goto("https://chatgpt.com", wait_until="domcontentloaded")
        
        # 等待页面加载
        await asyncio.sleep(3)
        
        # 处理Cloudflare验证
        cf_handled = False
        max_attempts = 5
        
        for attempt in range(max_attempts):
            logger.info(f"检查Cloudflare验证 (尝试 {attempt + 1}/{max_attempts})")
            
            # 截图当前状态
            screenshot_path = f"cf_check_{attempt}.png"
            await page.screenshot(path=screenshot_path)
            
            # 检查是否还在Cloudflare页面
            page_content = await page.content()
            if "cloudflare" in page_content.lower() or "正在验证" in page_content or "确认您是真人" in page_content:
                logger.info("检测到Cloudflare验证页面")
                
                # 查找并点击复选框
                checkbox_clicked = False
                
                # 尝试直接点击复选框
                checkbox_selectors = [
                    'input[type="checkbox"]',
                    '.cf-checkbox',
                    '#cf-turnstile-response',
                    'div[class*="checkbox"]'
                ]
                
                for selector in checkbox_selectors:
                    try:
                        checkbox = await page.wait_for_selector(selector, timeout=2000)
                        if checkbox:
                            # 获取元素的边界框
                            box = await checkbox.bounding_box()
                            if box:
                                # 点击复选框中心
                                await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
                                logger.info(f"点击了复选框: {selector}")
                                checkbox_clicked = True
                                break
                    except:
                        continue
                
                # 如果没找到复选框，尝试点击整个验证区域
                if not checkbox_clicked:
                    try:
                        # 根据截图，验证框在页面中间
                        await page.mouse.click(640, 408)  # 大概的复选框位置
                        logger.info("点击了预估的复选框位置")
                    except:
                        pass
                
                # 等待验证完成
                await asyncio.sleep(5)
                
                # 检查是否通过验证
                current_url = page.url
                if "chatgpt.com" in current_url and "auth" not in current_url:
                    logger.info("成功通过Cloudflare验证！")
                    cf_handled = True
                    break
            else:
                logger.info("未检测到Cloudflare验证，可能已经通过")
                cf_handled = True
                break
        
        # 删除验证截图
        for i in range(max_attempts):
            try:
                os.remove(f"cf_check_{i}.png")
            except:
                pass
        
        if cf_handled:
            # 现在尝试登录
            logger.info("开始登录流程...")
            
            # 查找并点击登录按钮
            login_clicked = False
            login_selectors = [
                'button:has-text("登录")',
                'button:has-text("Log in")',
                '[data-testid="login-button"]',
                'a:has-text("登录")'
            ]
            
            for selector in login_selectors:
                try:
                    btn = await page.wait_for_selector(selector, timeout=3000)
                    await btn.click()
                    logger.info(f"点击了登录按钮: {selector}")
                    login_clicked = True
                    break
                except:
                    continue
            
            if login_clicked:
                await asyncio.sleep(3)
                
                # 检查是否需要输入邮箱密码
                try:
                    email_input = await page.wait_for_selector('input[type="email"], input[name="username"]', timeout=5000)
                    if email_input:
                        logger.info("需要邮箱密码登录")
                        await email_input.fill(settings.openai_email)
                        
                        # 点击继续
                        continue_btn = await page.wait_for_selector('button[type="submit"]', timeout=3000)
                        await continue_btn.click()
                        
                        await asyncio.sleep(2)
                        
                        # 输入密码
                        pwd_input = await page.wait_for_selector('input[type="password"]', timeout=5000)
                        await pwd_input.fill(settings.openai_pwd)
                        
                        # 提交
                        submit_btn = await page.wait_for_selector('button[type="submit"]', timeout=3000)
                        await submit_btn.click()
                        
                        logger.info("已提交登录信息，等待登录完成...")
                        await asyncio.sleep(5)
                except:
                    logger.info("未找到邮箱输入框，可能已经登录或使用其他方式")
            
            # 最终截图
            await page.screenshot(path="final_state.png")
            logger.info("最终状态截图已保存")
            
            # 检查是否成功登录
            try:
                textarea = await page.wait_for_selector('textarea[placeholder*="Message"], textarea[placeholder*="消息"]', timeout=5000)
                if textarea:
                    logger.info("✅ 登录成功！找到聊天输入框")
                    
                    # 获取新的session token
                    cookies = await context.cookies()
                    for cookie in cookies:
                        if cookie['name'] == '__Secure-next-auth.session-token':
                            logger.info("\n🔑 获取到新的Session Token!")
                            logger.info(f"Token前50字符: {cookie['value'][:50]}...")
                            logger.info(f"Token长度: {len(cookie['value'])}")
                            logger.info("\n请将此token更新到.env文件的OPENAI_SESSION_TOKEN中")
                            
                            # 保存token到文件
                            with open("new_session_token.txt", "w") as f:
                                f.write(cookie['value'])
                            logger.info("Token已保存到: new_session_token.txt")
                            break
                    
                    # 测试发送消息
                    await textarea.fill("巴厘岛有哪些必去的景点？需要注意什么？")
                    await page.press('textarea[placeholder*="Message"], textarea[placeholder*="消息"]', 'Enter')
                    
                    logger.info("已发送测试消息，等待响应...")
                    await asyncio.sleep(15)
                    
                    await page.screenshot(path="test_response.png")
                    logger.info("测试响应截图已保存到: test_response.png")
            except:
                logger.error("未能成功登录")
        
        logger.info("\n浏览器将保持打开状态，你可以手动操作")
        logger.info("完成后按Ctrl+C关闭")
        
        # 保持浏览器打开
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("用户中断，关闭浏览器")
    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(smart_cloudflare_handler())