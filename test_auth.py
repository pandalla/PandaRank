#!/usr/bin/env python3
"""
测试OpenAI认证配置
"""

import os
from dotenv import load_dotenv

def test_auth_config():
    """检查认证配置"""
    print("🔍 检查PandaRank认证配置...")
    print("=" * 50)
    
    # 加载环境变量
    load_dotenv()
    
    # 检查session token
    session_token = os.getenv('OPENAI_SESSION_TOKEN')
    if session_token:
        print(f"✅ Session Token: 已配置 (长度: {len(session_token)} 字符)")
        if session_token.startswith('eyJ'):
            print("   ✅ Token格式看起来正确")
        else:
            print("   ⚠️  Token格式可能不正确 (应该以'eyJ'开头)")
    else:
        print("❌ Session Token: 未配置")
    
    # 检查邮箱密码
    email = os.getenv('OPENAI_EMAIL')
    password = os.getenv('OPENAI_PWD')
    
    if email:
        print(f"✅ 邮箱: {email}")
    else:
        print("❌ 邮箱: 未配置")
    
    if password:
        print(f"✅ 密码: 已配置 (长度: {len(password)} 字符)")
    else:
        print("❌ 密码: 未配置")
    
    print("\n📋 配置状态总结:")
    if session_token:
        print("   ✅ 可以使用Session Token登录")
        print("   💡 这是推荐的登录方式")
    elif email and password:
        print("   ✅ 可以使用邮箱密码登录")
        print("   ⚠️  注意：可能需要处理验证码")
    else:
        print("   ❌ 无可用的登录方式")
        print("   💡 请至少配置Session Token或邮箱密码")
    
    print("\n🚀 下一步:")
    if session_token or (email and password):
        print("   1. 重启服务: docker-compose restart scraper")
        print("   2. 测试功能: curl -X POST -d '{\"question_id\": 101}' -H 'Content-Type: application/json' http://localhost:8000/trigger")
        print("   3. 查看日志: docker-compose logs scraper")
        print("   4. 访问面板: http://localhost")
    else:
        print("   1. 配置认证信息（参考 SETUP_GUIDE.md）")
        print("   2. 重新运行此脚本验证配置")


if __name__ == "__main__":
    test_auth_config()