import csv
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional


class CSVStorage:
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # CSV文件路径
        self.conversations_file = self.data_dir / "conversations.csv"
        self.messages_file = self.data_dir / "messages.csv"
        self.web_searches_file = self.data_dir / "web_searches.csv"
        self.artifacts_file = self.data_dir / "artifacts.csv"
        self.reasoning_file = self.data_dir / "reasoning.csv"
        self.search_queries_file = self.data_dir / "search_queries.csv"
        self.visited_sites_file = self.data_dir / "visited_sites.csv"
        
        # 初始化CSV文件
        self._init_csv_files()
    
    def _init_csv_files(self):
        """初始化CSV文件头部"""
        # 对话记录
        if not self.conversations_file.exists():
            with open(self.conversations_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'run_uuid', 'question_id', 'question_text', 'started_at', 'finished_at'])
        
        # 消息记录
        if not self.messages_file.exists():
            with open(self.messages_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'conversation_id', 'role', 'content_md', 'scraped_at'])
        
        # 网页搜索记录
        if not self.web_searches_file.exists():
            with open(self.web_searches_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'conversation_id', 'url', 'title', 'fetched_at'])
        
        # 文件记录
        if not self.artifacts_file.exists():
            with open(self.artifacts_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'conversation_id', 'type', 'path', 'created_at'])
        
        # 思考过程记录
        if not self.reasoning_file.exists():
            with open(self.reasoning_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'conversation_id', 'reasoning_content', 'created_at'])
        
        # 搜索查询记录
        if not self.search_queries_file.exists():
            with open(self.search_queries_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'conversation_id', 'query_text', 'created_at'])
        
        # 访问网站记录
        if not self.visited_sites_file.exists():
            with open(self.visited_sites_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'conversation_id', 'site_url', 'site_title', 'site_description', 'created_at'])
    
    def create_conversation(self, run_uuid: str, question_id: int, question_text: str) -> int:
        """创建新对话记录"""
        conversation_id = self._get_next_id(self.conversations_file)
        started_at = datetime.now(timezone.utc).isoformat()
        
        with open(self.conversations_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([conversation_id, run_uuid, question_id, question_text, started_at, ''])
        
        return conversation_id
    
    def finish_conversation(self, conversation_id: int):
        """标记对话完成"""
        finished_at = datetime.now(timezone.utc).isoformat()
        self._update_conversation_field(conversation_id, 'finished_at', finished_at)
    
    def add_message(self, conversation_id: int, role: str, content: str):
        """添加消息"""
        message_id = self._get_next_id(self.messages_file)
        scraped_at = datetime.now(timezone.utc).isoformat()
        
        with open(self.messages_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([message_id, conversation_id, role, content, scraped_at])
    
    def add_web_search(self, conversation_id: int, url: str, title: str):
        """添加网页搜索记录"""
        search_id = self._get_next_id(self.web_searches_file)
        fetched_at = datetime.now(timezone.utc).isoformat()
        
        with open(self.web_searches_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([search_id, conversation_id, url, title, fetched_at])
    
    def add_artifact(self, conversation_id: int, artifact_type: str, path: str):
        """添加文件记录"""
        artifact_id = self._get_next_id(self.artifacts_file)
        created_at = datetime.now(timezone.utc).isoformat()
        
        with open(self.artifacts_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([artifact_id, conversation_id, artifact_type, path, created_at])
    
    def add_reasoning(self, conversation_id: int, reasoning_content: str):
        """添加思考过程记录"""
        reasoning_id = self._get_next_id(self.reasoning_file)
        created_at = datetime.now(timezone.utc).isoformat()
        
        # 将换行符编码为\\n以避免CSV解析问题
        encoded_content = reasoning_content.replace('\n', '\\n').replace('\r', '\\r')
        
        with open(self.reasoning_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([reasoning_id, conversation_id, encoded_content, created_at])
    
    def add_search_query(self, conversation_id: int, query_text: str):
        """添加搜索查询记录"""
        query_id = self._get_next_id(self.search_queries_file)
        created_at = datetime.now(timezone.utc).isoformat()
        
        with open(self.search_queries_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([query_id, conversation_id, query_text, created_at])
    
    def add_visited_site(self, conversation_id: int, site_url: str, site_title: str = "", site_description: str = ""):
        """添加访问网站记录"""
        site_id = self._get_next_id(self.visited_sites_file)
        created_at = datetime.now(timezone.utc).isoformat()
        
        with open(self.visited_sites_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([site_id, conversation_id, site_url, site_title, site_description, created_at])
    
    def get_conversations(self, limit: int = 100) -> List[Dict]:
        """获取对话列表"""
        conversations = []
        if not self.conversations_file.exists():
            return conversations
        
        with open(self.conversations_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        # 按开始时间倒序排序
        rows.sort(key=lambda x: x['started_at'], reverse=True)
        
        for row in rows[:limit]:
            duration_seconds = None
            if row['finished_at'] and row['started_at']:
                try:
                    start = datetime.fromisoformat(row['started_at'])
                    finish = datetime.fromisoformat(row['finished_at'])
                    duration_seconds = (finish - start).total_seconds()
                except:
                    pass
            
            conversations.append({
                'id': int(row['id']),
                'run_uuid': row['run_uuid'],
                'question_id': int(row['question_id']) if row['question_id'] else None,
                'question_text': row['question_text'],
                'started_at': row['started_at'] if row['started_at'] else None,
                'finished_at': row['finished_at'] if row['finished_at'] else None,
                'duration_seconds': duration_seconds
            })
        
        return conversations
    
    def get_conversation_details(self, run_uuid: str) -> Optional[Dict]:
        """获取对话详情"""
        # 找到对话
        conversation = None
        if self.conversations_file.exists():
            with open(self.conversations_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['run_uuid'] == run_uuid:
                        conversation = row
                        break
        
        if not conversation:
            return None
        
        conversation_id = int(conversation['id'])
        
        # 获取消息
        messages = []
        if self.messages_file.exists():
            with open(self.messages_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['conversation_id']) == conversation_id:
                        messages.append({
                            'id': int(row['id']),
                            'role': row['role'],
                            'content': row['content_md'],
                            'scraped_at': row['scraped_at']
                        })
        
        # 获取网页搜索
        web_searches = []
        if self.web_searches_file.exists():
            with open(self.web_searches_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['conversation_id']) == conversation_id:
                        web_searches.append({
                            'id': int(row['id']),
                            'url': row['url'],
                            'title': row['title'],
                            'fetched_at': row['fetched_at']
                        })
        
        # 获取文件
        artifacts = []
        if self.artifacts_file.exists():
            with open(self.artifacts_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['conversation_id']) == conversation_id:
                        artifacts.append({
                            'id': int(row['id']),
                            'type': row['type'],
                            'path': row['path'],
                            'created_at': row['created_at']
                        })
        
        # 获取思考过程
        reasoning = []
        if self.reasoning_file.exists():
            with open(self.reasoning_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['conversation_id']) == conversation_id:
                        reasoning.append({
                            'id': int(row['id']),
                            'reasoning_content': row['reasoning_content'],
                            'created_at': row['created_at']
                        })
        
        # 获取搜索查询
        search_queries = []
        if self.search_queries_file.exists():
            with open(self.search_queries_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['conversation_id']) == conversation_id:
                        search_queries.append({
                            'id': int(row['id']),
                            'query_text': row['query_text'],
                            'created_at': row['created_at']
                        })
        
        # 获取访问网站
        visited_sites = []
        if self.visited_sites_file.exists():
            with open(self.visited_sites_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['conversation_id']) == conversation_id:
                        visited_sites.append({
                            'id': int(row['id']),
                            'site_url': row['site_url'],
                            'site_title': row['site_title'],
                            'site_description': row['site_description'],
                            'created_at': row['created_at']
                        })
        
        return {
            'id': conversation_id,
            'run_uuid': conversation['run_uuid'],
            'question': {
                'id': int(conversation['question_id']) if conversation['question_id'] else None,
                'text': conversation['question_text'],
                'cooldown_min': 1440  # 默认值
            },
            'started_at': conversation['started_at'],
            'finished_at': conversation['finished_at'],
            'messages': messages,
            'web_searches': web_searches,
            'artifacts': artifacts,
            'reasoning': reasoning,
            'search_queries': search_queries,
            'visited_sites': visited_sites
        }
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total_conversations = 0
        successful_conversations = 0
        total_messages = 0
        total_web_searches = 0
        
        # 统计对话
        if self.conversations_file.exists():
            with open(self.conversations_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_conversations += 1
                    if row['finished_at']:
                        successful_conversations += 1
        
        # 统计消息
        if self.messages_file.exists():
            with open(self.messages_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total_messages = sum(1 for _ in reader)
        
        # 统计网页搜索
        if self.web_searches_file.exists():
            with open(self.web_searches_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total_web_searches = sum(1 for _ in reader)
        
        return {
            'total_conversations': total_conversations,
            'successful_conversations': successful_conversations,
            'success_rate': successful_conversations / total_conversations if total_conversations > 0 else 0,
            'total_messages': total_messages,
            'total_web_searches': total_web_searches,
            'total_questions': 5  # 默认问题数量
        }
    
    def _get_next_id(self, csv_file: Path) -> int:
        """获取下一个ID"""
        max_id = 0
        if csv_file.exists():
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        current_id = int(row['id'])
                        max_id = max(max_id, current_id)
                    except:
                        pass
        return max_id + 1
    
    def _update_conversation_field(self, conversation_id: int, field: str, value: str):
        """更新对话字段"""
        if not self.conversations_file.exists():
            return
        
        # 读取所有行
        rows = []
        with open(self.conversations_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if int(row['id']) == conversation_id:
                    row[field] = value
                rows.append(row)
        
        # 重写文件
        with open(self.conversations_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)