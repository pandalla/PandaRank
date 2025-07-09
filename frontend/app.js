const API_URL = 'http://localhost:8000';

// 全局变量
let responseTimeChart = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadQuestions();
    loadRecentRuns();
    initResponseTimeChart();
    
    // 每30秒刷新数据
    setInterval(() => {
        loadStats();
        loadRecentRuns();
    }, 30000);
});

// 加载统计数据
async function loadStats() {
    try {
        const response = await axios.get(`${API_URL}/stats`);
        const stats = response.data;
        
        document.getElementById('totalConversations').textContent = stats.total_conversations;
        document.getElementById('successRate').textContent = (stats.success_rate * 100).toFixed(1) + '%';
        document.getElementById('totalMessages').textContent = stats.total_messages;
        document.getElementById('totalSearches').textContent = stats.total_web_searches;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

// 加载问题列表
async function loadQuestions() {
    try {
        const response = await axios.get(`${API_URL}/questions`);
        const questions = response.data.questions;
        
        const select = document.getElementById('questionSelect');
        select.innerHTML = '<option value="">选择一个问题...</option>';
        
        questions.forEach(q => {
            const option = document.createElement('option');
            option.value = q.id;
            option.textContent = `${q.id}. ${q.text}`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load questions:', error);
    }
}

// 加载最近运行记录
async function loadRecentRuns() {
    try {
        const response = await axios.get(`${API_URL}/runs?limit=10`);
        const runs = response.data.runs;
        
        const tbody = document.getElementById('runsTableBody');
        tbody.innerHTML = '';
        
        if (runs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center py-4">暂无运行记录</td></tr>';
            return;
        }
        
        runs.forEach(run => {
            const row = document.createElement('tr');
            row.className = 'border-t hover:bg-gray-50';
            
            const startTime = new Date(run.started_at).toLocaleString('zh-CN');
            const status = run.finished_at ? 
                '<span class="text-green-600">✓ 完成</span>' : 
                '<span class="text-yellow-600">⏳ 进行中</span>';
            const duration = run.duration_seconds ? 
                `${run.duration_seconds.toFixed(1)}秒` : '-';
            
            row.innerHTML = `
                <td class="px-4 py-2">${startTime}</td>
                <td class="px-4 py-2 max-w-md truncate">${run.question_text || '-'}</td>
                <td class="px-4 py-2">${status}</td>
                <td class="px-4 py-2">${duration}</td>
                <td class="px-4 py-2">
                    <button onclick="viewDetails('${run.run_uuid}')" 
                        class="text-blue-500 hover:underline">查看详情</button>
                </td>
            `;
            tbody.appendChild(row);
        });
        
        // 更新响应时间图表
        updateResponseTimeChart(runs);
    } catch (error) {
        console.error('Failed to load runs:', error);
    }
}

// 手动触发爬取
async function triggerScrape() {
    const questionId = document.getElementById('questionSelect').value;
    if (!questionId) {
        alert('请选择一个问题');
        return;
    }
    
    try {
        const response = await axios.post(`${API_URL}/trigger`, {
            question_id: parseInt(questionId)
        });
        
        alert('已触发爬取任务！');
        setTimeout(() => loadRecentRuns(), 2000);
    } catch (error) {
        alert('触发失败：' + (error.response?.data?.detail || error.message));
    }
}

// 触发自定义问题
async function triggerCustomScrape() {
    const customQuestion = document.getElementById('customQuestion').value.trim();
    if (!customQuestion) {
        alert('请输入问题内容');
        return;
    }
    
    try {
        const response = await axios.post(`${API_URL}/trigger`, {
            custom_question: customQuestion
        });
        
        alert('已发送自定义问题！');
        document.getElementById('customQuestion').value = '';
        setTimeout(() => loadRecentRuns(), 2000);
    } catch (error) {
        alert('触发失败：' + (error.response?.data?.detail || error.message));
    }
}

// 查看详情
async function viewDetails(runUuid) {
    try {
        const response = await axios.get(`${API_URL}/runs/${runUuid}`);
        const data = response.data;
        
        let content = `
            <div class="space-y-4">
                <div>
                    <h4 class="font-semibold">基本信息</h4>
                    <p>运行ID: ${data.run_uuid}</p>
                    <p>开始时间: ${new Date(data.started_at).toLocaleString('zh-CN')}</p>
                    <p>结束时间: ${data.finished_at ? new Date(data.finished_at).toLocaleString('zh-CN') : '进行中'}</p>
                </div>
                
                <div>
                    <h4 class="font-semibold">问题</h4>
                    <p class="bg-gray-100 p-3 rounded">${data.question.text}</p>
                </div>
                
                <div>
                    <h4 class="font-semibold">对话内容</h4>
        `;
        
        data.messages.forEach(msg => {
            const bgColor = msg.role === 'user' ? 'bg-blue-50' : 'bg-green-50';
            const label = msg.role === 'user' ? '用户' : 'ChatGPT';
            content += `
                <div class="${bgColor} p-3 rounded mb-2">
                    <p class="font-semibold text-sm">${label}</p>
                    <p class="whitespace-pre-wrap">${msg.content}</p>
                </div>
            `;
        });
        
        if (data.web_searches.length > 0) {
            content += `
                <div>
                    <h4 class="font-semibold">网页搜索记录</h4>
                    <ul class="list-disc list-inside">
            `;
            data.web_searches.forEach(search => {
                content += `<li><a href="${search.url}" target="_blank" class="text-blue-500 hover:underline">${search.title || search.url}</a></li>`;
            });
            content += '</ul></div>';
        }
        
        content += '</div>';
        
        document.getElementById('modalContent').innerHTML = content;
        document.getElementById('detailModal').classList.remove('hidden');
    } catch (error) {
        alert('加载详情失败：' + error.message);
    }
}

// 关闭模态框
function closeModal() {
    document.getElementById('detailModal').classList.add('hidden');
}

// 初始化响应时间图表
function initResponseTimeChart() {
    const ctx = document.getElementById('responseTimeChart').getContext('2d');
    responseTimeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '响应时间 (秒)',
                data: [],
                borderColor: 'rgb(59, 130, 246)',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// 更新响应时间图表
function updateResponseTimeChart(runs) {
    if (!responseTimeChart) return;
    
    const validRuns = runs.filter(r => r.duration_seconds).slice(0, 20).reverse();
    
    responseTimeChart.data.labels = validRuns.map(r => 
        new Date(r.started_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    );
    responseTimeChart.data.datasets[0].data = validRuns.map(r => r.duration_seconds);
    responseTimeChart.update();
}