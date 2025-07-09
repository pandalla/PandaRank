#!/usr/bin/env python3
"""
调试脚本 - 使用邮箱密码登录ChatGPT
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.app.config import settings
import logging
from playwright.async_api import async_playwright

# 设置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_login():
    # 强制使用非headless模式
    settings.headless = False
    
    logger.info(f"Email: {settings.openai_email}")
    logger.info(f"Has password: {bool(settings.openai_pwd)}")
    
    playwright = await async_playwright().start()
    browser = await playwright.webkit.launch(headless=False)
    
    try:
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        
        logger.info("导航到ChatGPT...")
        await page.goto("https://chatgpt.com", wait_until="networkidle")
        logger.info(f"当前URL: {page.url}")
        
        # 先截图查看页面
        await page.screenshot(path="initial_page.png")
        logger.info("初始页面截图已保存到: initial_page.png")
        
        # 点击登录按钮
        logger.info("查找登录按钮...")
        try:
            # 尝试多种选择器
            login_selectors = [
                'button:has-text("Log in")',
                'button:has-text("Sign in")',
                'button:has-text("登录")',
                'button:has-text("登陆")',
                'a:has-text("Log in")',
                'a:has-text("Sign in")',
                'a:has-text("登录")',
                '[data-testid="login-button"]'
            ]
            
            clicked = False
            for selector in login_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    await element.click()
                    logger.info(f"点击了: {selector}")
                    clicked = True
                    break
                except:
                    continue
                    
            if not clicked:
                # 如果都没找到，尝试通过文本查找
                login_buttons = await page.query_selector_all('button')
                for button in login_buttons:
                    text = await button.text_content()
                    if text and ('log in' in text.lower() or 'sign in' in text.lower()):
                        logger.info(f"找到登录按钮: {text}")
                        await button.click()
                        clicked = True
                        break
                        
            if not clicked:
                logger.warning("未找到登录按钮，尝试直接导航到登录页")
                await page.goto("https://auth0.openai.com/u/login/identifier", wait_until="networkidle")
                
        except Exception as e:
            logger.error(f"查找登录按钮失败: {e}")
        
        await asyncio.sleep(3)
        
        # 截图查看登录页面
        await page.screenshot(path="login_page.png")
        logger.info("登录页面截图已保存到: login_page.png")
        logger.info(f"当前URL: {page.url}")
        
        # 输入邮箱
        logger.info("输入邮箱...")
        try:
            email_input = await page.wait_for_selector('input[type="email"], input[name="username"], input[name="email"], input[placeholder*="email"], input[placeholder*="邮箱"]', timeout=10000)
        except:
            # 如果还是没找到，尝试所有input
            logger.warning("未找到邮箱输入框，尝试查找所有input")
            inputs = await page.query_selector_all('input')
            logger.info(f"找到 {len(inputs)} 个input元素")
            for i, inp in enumerate(inputs):
                placeholder = await inp.get_attribute('placeholder') or ''
                input_type = await inp.get_attribute('type') or ''
                name = await inp.get_attribute('name') or ''
                logger.info(f"Input {i}: type={input_type}, name={name}, placeholder={placeholder}")
            raise
        await email_input.fill(settings.openai_email)
        
        # 点击继续
        continue_button = await page.wait_for_selector('button[type="submit"]', timeout=5000)
        await continue_button.click()
        
        await asyncio.sleep(2)
        
        # 输入密码
        logger.info("输入密码...")
        password_input = await page.wait_for_selector('input[type="password"], input[name="password"]', timeout=10000)
        await password_input.fill(settings.openai_pwd)
        
        # 提交登录
        submit_button = await page.wait_for_selector('button[type="submit"]', timeout=5000)
        await submit_button.click()
        
        logger.info("等待登录完成...")
        await asyncio.sleep(5)
        
        # 检查登录状态
        try:
            await page.wait_for_selector('button[aria-label="User menu"], nav[role="navigation"]', timeout=10000)
            logger.info("登录成功！")
            
            # 获取当前的session token
            cookies = await context.cookies()
            for cookie in cookies:
                if cookie['name'] == '__Secure-next-auth.session-token':
                    logger.info(f"新的Session Token (前50字符): {cookie['value'][:50]}...")
                    logger.info(f"完整Session Token已获取，长度: {len(cookie['value'])}")
                    logger.info("\n将这个token更新到.env文件中的OPENAI_SESSION_TOKEN=")
                    break
                    
        except:
            logger.error("登录失败")
            await page.screenshot(path="login_failed.png")
            logger.info("登录失败截图已保存")
        
        # 测试发送消息
        logger.info("尝试发送测试消息...")
        textarea = await page.wait_for_selector('textarea[placeholder*="Message"]', timeout=10000)
        await textarea.fill("巴厘岛有哪些必去的景点？")
        await page.press('textarea[placeholder*="Message"]', 'Enter')
        
        logger.info("等待响应...")
        await asyncio.sleep(10)
        
        await page.screenshot(path="chatgpt_test.png")
        logger.info("测试截图已保存到: chatgpt_test.png")
        
        logger.info("\n按Enter键关闭浏览器...")
        input()
        
    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_login())