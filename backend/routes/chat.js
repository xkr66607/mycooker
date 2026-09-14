const express = require('express');
const router = express.Router();
const { chatWithAI } = require('../services/aiService');
const { getMemoryContext } = require('../services/memoryService');

/**
 * POST /api/chat
 * 发送消息并获取 AI 回复（含历史上下文 + 用户记忆）
 * Body: { conversationId?, message, history? }
 */
router.post('/', async (req, res) => {
  try {
    const { message, history = [] } = req.body;

    if (!message || typeof message !== 'string' || !message.trim()) {
      return res.status(400).json({ success: false, message: '消息内容不能为空' });
    }

    const memoryContext = getMemoryContext(req.app.locals.db);
    const reply = await chatWithAI(history, message.trim(), memoryContext);

    res.json({
      success: true,
      data: {
        role: 'assistant',
        content: reply
      }
    });
  } catch (err) {
    console.error('[Chat Error]', err.message);
    res.status(500).json({
      success: false,
      message: err.message || 'AI 服务暂时不可用，请稍后重试'
    });
  }
});

module.exports = router;
