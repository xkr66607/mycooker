const express = require('express');
const router = express.Router();

/**
 * GET /api/history
 * 获取对话列表（按更新时间倒序）
 */
router.get('/', (req, res) => {
  try {
    const db = req.app.locals.db;
    const conversations = db
      .prepare(
        `SELECT c.*,
          (SELECT content FROM messages
           WHERE conversation_id = c.id AND role = 'user'
           ORDER BY created_at ASC LIMIT 1) AS first_message
         FROM conversations c
         ORDER BY c.updated_at DESC`
      )
      .all();

    res.json({ success: true, data: conversations });
  } catch (err) {
    console.error('[History List Error]', err.message);
    res.status(500).json({ success: false, message: '获取历史记录失败' });
  }
});

/**
 * GET /api/history/:id
 * 获取指定对话的全部消息
 */
router.get('/:id', (req, res) => {
  try {
    const db = req.app.locals.db;
    const { id } = req.params;

    const conversation = db
      .prepare('SELECT * FROM conversations WHERE id = ?')
      .get(id);

    if (!conversation) {
      return res.status(404).json({ success: false, message: '对话不存在' });
    }

    const messages = db
      .prepare(
        `SELECT id, role, content, created_at
         FROM messages
         WHERE conversation_id = ? AND role != 'system'
         ORDER BY created_at ASC`
      )
      .all(id);

    res.json({ success: true, data: { conversation, messages } });
  } catch (err) {
    console.error('[History Detail Error]', err.message);
    res.status(500).json({ success: false, message: '获取对话详情失败' });
  }
});

/**
 * POST /api/history
 * 创建新对话
 * Body: { title? }
 */
router.post('/', (req, res) => {
  try {
    const db = req.app.locals.db;
    const title = req.body.title || '新对话';

    const result = db
      .prepare('INSERT INTO conversations (title) VALUES (?)')
      .run(title);

    const conversation = db
      .prepare('SELECT * FROM conversations WHERE id = ?')
      .get(result.lastInsertRowid);

    res.json({ success: true, data: conversation });
  } catch (err) {
    console.error('[Create Conversation Error]', err.message);
    res.status(500).json({ success: false, message: '创建对话失败' });
  }
});

/**
 * POST /api/history/:id/messages
 * 向对话追加消息
 * Body: { role, content }
 */
router.post('/:id/messages', (req, res) => {
  try {
    const db = req.app.locals.db;
    const { id } = req.params;
    const { role, content } = req.body;

    if (!role || !content) {
      return res.status(400).json({ success: false, message: '缺少 role 或 content' });
    }

    const conversation = db
      .prepare('SELECT id FROM conversations WHERE id = ?')
      .get(id);

    if (!conversation) {
      return res.status(404).json({ success: false, message: '对话不存在' });
    }

    const result = db
      .prepare(
        'INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)'
      )
      .run(id, role, content);

    // 首条用户消息自动更新对话标题
    if (role === 'user') {
      const msgCount = db
        .prepare(
          'SELECT COUNT(*) AS cnt FROM messages WHERE conversation_id = ? AND role = ?'
        )
        .get(id, 'user');

      if (msgCount.cnt === 1) {
        const shortTitle =
          content.length > 20 ? content.slice(0, 20) + '…' : content;
        db.prepare('UPDATE conversations SET title = ?, updated_at = datetime(\'now\', \'localtime\') WHERE id = ?')
          .run(shortTitle, id);
      } else {
        db.prepare('UPDATE conversations SET updated_at = datetime(\'now\', \'localtime\') WHERE id = ?')
          .run(id);
      }
    } else {
      db.prepare('UPDATE conversations SET updated_at = datetime(\'now\', \'localtime\') WHERE id = ?')
        .run(id);
    }

    const message = db
      .prepare('SELECT * FROM messages WHERE id = ?')
      .get(result.lastInsertRowid);

    res.json({ success: true, data: message });
  } catch (err) {
    console.error('[Save Message Error]', err.message);
    res.status(500).json({ success: false, message: '保存消息失败' });
  }
});

/**
 * DELETE /api/history/:id
 * 删除指定对话及其所有消息
 */
router.delete('/:id', (req, res) => {
  try {
    const db = req.app.locals.db;
    const { id } = req.params;

    const result = db
      .prepare('DELETE FROM conversations WHERE id = ?')
      .run(id);

    if (result.changes === 0) {
      return res.status(404).json({ success: false, message: '对话不存在' });
    }

    res.json({ success: true, message: '对话已删除' });
  } catch (err) {
    console.error('[Delete Conversation Error]', err.message);
    res.status(500).json({ success: false, message: '删除对话失败' });
  }
});

module.exports = router;
