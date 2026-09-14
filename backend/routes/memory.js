const express = require('express');
const router = express.Router();
const {
  listMemories,
  savePreference,
  deleteMemory,
  getMemoryContext
} = require('../services/memoryService');

/**
 * GET /api/memory
 * 获取记忆列表（可选 ?category=ingredient|preference|ingredient_summary）
 */
router.get('/', (req, res) => {
  try {
    const db = req.app.locals.db;
    const data = listMemories(db, req.query.category);
    res.json({ success: true, data });
  } catch (err) {
    res.status(500).json({ success: false, message: '获取记忆失败' });
  }
});

/**
 * GET /api/memory/context
 * 获取格式化后的记忆上下文（调试用）
 */
router.get('/context', (req, res) => {
  try {
    const db = req.app.locals.db;
    const context = getMemoryContext(db);
    res.json({ success: true, data: context || '暂无记忆' });
  } catch (err) {
    res.status(500).json({ success: false, message: '获取记忆上下文失败' });
  }
});

/**
 * POST /api/memory
 * 添加/更新用户偏好记忆
 * Body: { key, value }
 */
router.post('/', (req, res) => {
  try {
    const db = req.app.locals.db;
    const { key, value } = req.body;
    if (!key || !value) {
      return res.status(400).json({ success: false, message: '缺少 key 或 value' });
    }
    savePreference(db, key, value);
    res.json({ success: true, message: '偏好已保存到记忆' });
  } catch (err) {
    res.status(500).json({ success: false, message: '保存记忆失败' });
  }
});

/**
 * DELETE /api/memory/:id
 * 删除单条记忆
 */
router.delete('/:id', (req, res) => {
  try {
    const db = req.app.locals.db;
    const result = deleteMemory(db, req.params.id);
    if (result.changes === 0) {
      return res.status(404).json({ success: false, message: '记忆不存在' });
    }
    res.json({ success: true, message: '记忆已删除' });
  } catch (err) {
    res.status(500).json({ success: false, message: '删除记忆失败' });
  }
});

module.exports = router;
