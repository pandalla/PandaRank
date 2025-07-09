# PandaRank 设置指南

## 问题：为什么没有抓到对话内容？

当前系统运行正常，但没有抓到ChatGPT的对话内容，这是因为**缺少OpenAI认证**。

## 解决方案：获取OpenAI Session Token

### 方法1：通过浏览器获取（推荐）

1. **打开Chrome/Safari等浏览器**
2. **登录ChatGPT**：访问 https://chat.openai.com 并登录你的账号
3. **打开开发者工具**：按 F12 或右键选择"检查"
4. **找到Cookie**：
   - 点击 "Application"（应用程序）标签
   - 在左侧找到 "Storage" → "Cookies" → "https://chat.openai.com"
   - 找到名为 `__Secure-next-auth.session-token` 的cookie
   - 复制它的值（通常是一个很长的字符串，以eyJ开头）

### 方法2：通过Network面板获取

1. **在ChatGPT页面按F12**
2. **切换到Network标签**
3. **发送一条消息给ChatGPT**
4. **查看请求头**：
   - 找到任何一个API请求
   - 查看Request Headers
   - 找到Cookie字段中的session-token值

### 配置Token

1. **创建.env文件**：
   ```bash
   cp .env.example .env
   ```

2. **编辑.env文件**：
   ```bash
   # 替换为你的实际token
   OPENAI_SESSION_TOKEN=eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0...你的完整token
   
   # 其他配置（可选）
   SCRAPE_INTERVAL_SEC=600
   HEADLESS=true
   ```

3. **重启服务**：
   ```bash
   docker-compose down
   docker-compose up -d
   ```

## 测试流程

配置好token后：

1. **访问监控面板**：http://localhost
2. **选择一个地理问题**：比如"东京最好吃的拉面馆是什么？"
3. **点击"立即询问"**
4. **等待30-60秒**
5. **刷新页面查看结果**

## 预期结果

配置正确后，你应该能看到：
- ✅ ChatGPT的完整回答内容
- ✅ 所有搜索的网站URL
- ✅ 完整的对话历史
- ✅ 页面截图和HTML保存

## 故障排除

### 如果仍然没有内容：

1. **检查token是否有效**：
   ```bash
   docker-compose logs scraper | grep -i "login"
   ```

2. **检查token格式**：确保token完整，没有多余的空格或换行

3. **检查ChatGPT页面变化**：OpenAI可能更新了页面结构，需要调整选择器

### 如果看到"登录失败"：

- Token可能已过期（通常1-2个月有效期）
- 重新获取新的session token
- 或者配置邮箱密码登录

### Debug模式

如果需要看到浏览器操作过程：
```bash
# 在.env中设置
HEADLESS=false
```

## 安全提醒

- 🔒 不要分享你的session token
- 🔒 Token等同于你的登录凭证
- 🔒 定期更新token（建议每月更新）
- 🔒 不要将token提交到git仓库