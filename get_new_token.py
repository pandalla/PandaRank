#!/usr/bin/env python3
"""
半自动获取新的Session Token
"""
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'scraper'))

from scraper.app.config import settings
import logging
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_new_token():
    logger.info("=" * 60)
    logger.info("ChatGPT Session Token 获取工具")
    logger.info("=" * 60)
    
    playwright = await async_playwright().start()
    browser = await playwright.webkit.launch(headless=False)
    
    try:
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        
        page = await context.new_page()
        
        logger.info("\n步骤1: 打开ChatGPT网站...")
        await page.goto("https://chatgpt.com")
        
        logger.info("\n请手动完成以下操作：")
        logger.info("1. 如果有Cloudflare验证，请点击'确认您是真人'")
        logger.info("2. 点击右上角'登录'按钮")
        logger.info("3. 使用邮箱密码登录")
        logger.info("4. 登录成功后，按Enter键继续...")
        
        input("\n按Enter键继续（确保已经成功登录）...")
        
        # 检查是否登录成功
        try:
            await page.wait_for_selector('textarea[placeholder*="Message"], textarea[placeholder*="消息"]', timeout=5000)
            logger.info("\n✅ 检测到已登录！")
            
            # 获取所有cookies
            cookies = await context.cookies()
            session_token = None
            
            for cookie in cookies:
                if cookie['name'] == '__Secure-next-auth.session-token':
                    session_token = cookie['value']
                    break
            
            if session_token:
                logger.info("\n🎉 成功获取Session Token!")
                logger.info(f"Token长度: {len(session_token)}")
                logger.info(f"Token前50字符: {session_token[:50]}...")
                
                # 保存到文件
                with open("new_token.txt", "w") as f:
                    f.write(f"OPENAI_SESSION_TOKEN={session_token}\n")
                
                logger.info("\n✅ Token已保存到: new_token.txt")
                logger.info("请将这行内容复制到.env文件中")
                
                # 更新.env文件
                logger.info("\n是否自动更新.env文件？(y/n): ")
                if input().lower() == 'y':
                    # 读取现有.env
                    env_lines = []
                    if os.path.exists('.env'):
                        with open('.env', 'r') as f:
                            env_lines = f.readlines()
                    
                    # 更新或添加token
                    updated = False
                    for i, line in enumerate(env_lines):
                        if line.startswith('OPENAI_SESSION_TOKEN='):
                            env_lines[i] = f"OPENAI_SESSION_TOKEN={session_token}\n"
                            updated = True
                            break
                    
                    if not updated:
                        env_lines.append(f"OPENAI_SESSION_TOKEN={session_token}\n")
                    
                    # 写回文件
                    with open('.env', 'w') as f:
                        f.writelines(env_lines)
                    
                    logger.info("✅ .env文件已更新!")
                
            else:
                logger.error("❌ 未找到Session Token，请确认已经登录")
                
        except Exception as e:
            logger.error(f"❌ 检测登录状态失败: {e}")
            logger.error("请确保已经成功登录ChatGPT")
        
        logger.info("\n按Enter键关闭浏览器...")
        input()
        
    except Exception as e:
        logger.error(f"错误: {e}")
    finally:
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_new_token())