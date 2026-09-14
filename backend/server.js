const express = require('express');
const cors = require('cors');
const path = require('path');
const { initDatabase } = require('./db/database');
const chatRouter = require('./routes/chat');
const historyRouter = require('./routes/history');
const imageRouter = require('./routes/image');
const memoryRouter = require('./routes/memory');
const { validateConfig } = require('./services/aiService');

const app = express();
const PORT = process.env.PORT || 3001;

// 中间件
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// 静态文件：上传的图片
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// 初始化数据库
const db = initDatabase();
app.locals.db = db;

// 路由
app.use('/api/chat', chatRouter);
app.use('/api/history', historyRouter);
app.use('/api/image', imageRouter);
app.use('/api/memory', memoryRouter);

// 健康检查
app.get('/api/health', (req, res) => {
  const missing = validateConfig();
  res.json({
    success: true,
    message: '私人厨房 AI 助手后端运行中',
    aiConfigured: missing.length === 0,
    missingConfig: missing,
    features: ['chat', 'image-analyze', 'web-search', 'memory']
  });
});

app.listen(PORT, () => {
  console.log(`\n🍳 私人厨房 AI 助手后端已启动`);
  console.log(`   地址: http://localhost:${PORT}`);
  console.log(`   健康检查: http://localhost:${PORT}/api/health`);

  const missing = validateConfig();
  if (missing.length > 0) {
    console.log(`\n⚠️  千问 API 尚未配置，请编辑 backend/config/ai.config.js：`);
    console.log(`   缺少: ${missing.join(', ')}`);
    console.log(`   获取 Key: https://dashscope.console.aliyun.com/apiKey`);
  } else {
    console.log(`\n✅ 千问 API 配置已完成`);
  }
  console.log('');
});
