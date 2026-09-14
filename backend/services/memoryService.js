/**
 * 用户记忆服务 — 持久化食材、偏好、识图记录等
 */

/** 获取全部记忆，格式化为注入 AI 的上下文字符串 */
function getMemoryContext(db) {
  const memories = db
    .prepare(
      `SELECT category, key, value, created_at FROM user_memory
       ORDER BY updated_at DESC LIMIT 30`
    )
    .all();

  if (memories.length === 0) return '';

  const lines = memories.map((m) => {
    const label = m.key ? `[${m.category}/${m.key}]` : `[${m.category}]`;
    return `- ${label} ${m.value} (${m.created_at})`;
  });

  return lines.join('\n');
}

/** 保存识图识别的食材到记忆 */
function saveIngredientsMemory(db, ingredients, description) {
  if (!ingredients || ingredients.length === 0) return;

  const value = `识别食材：${ingredients.join('、')}${description ? '（' + description + '）' : ''}`;
  db.prepare(
    `INSERT INTO user_memory (category, key, value) VALUES (?, ?, ?)`
  ).run('ingredient', ingredients.join(','), value);

  // 同时维护一份汇总记忆（最近识别的食材合集）
  const existing = db
    .prepare(`SELECT id, value FROM user_memory WHERE category = 'ingredient_summary' LIMIT 1`)
    .get();

  const allIngredients = new Set(ingredients);
  if (existing) {
    existing.value.split('、').forEach((i) => allIngredients.add(i.trim()));
    db.prepare(
      `UPDATE user_memory SET value = ?, updated_at = datetime('now','localtime') WHERE id = ?`
    ).run([...allIngredients].join('、'), existing.id);
  } else {
    db.prepare(
      `INSERT INTO user_memory (category, key, value) VALUES (?, ?, ?)`
    ).run('ingredient_summary', 'all', ingredients.join('、'));
  }
}

/** 保存用户偏好 */
function savePreference(db, key, value) {
  const existing = db
    .prepare(`SELECT id FROM user_memory WHERE category = 'preference' AND key = ?`)
    .get(key);

  if (existing) {
    db.prepare(
      `UPDATE user_memory SET value = ?, updated_at = datetime('now','localtime') WHERE id = ?`
    ).run(value, existing.id);
  } else {
    db.prepare(
      `INSERT INTO user_memory (category, key, value) VALUES (?, ?, ?)`
    ).run('preference', key, value);
  }
}

/** 获取记忆列表 */
function listMemories(db, category) {
  if (category) {
    return db
      .prepare(
        `SELECT * FROM user_memory WHERE category = ? ORDER BY updated_at DESC`
      )
      .all(category);
  }
  return db
    .prepare(`SELECT * FROM user_memory ORDER BY updated_at DESC LIMIT 50`)
    .all();
}

/** 删除单条记忆 */
function deleteMemory(db, id) {
  return db.prepare('DELETE FROM user_memory WHERE id = ?').run(id);
}

/** 保存识图记录 */
function saveImageRecord(db, filename, ingredients, description, recipeResult) {
  const result = db
    .prepare(
      `INSERT INTO image_records (filename, ingredients, description, recipe_result)
       VALUES (?, ?, ?, ?)`
    )
    .run(
      filename,
      JSON.stringify(ingredients),
      description || '',
      recipeResult || ''
    );

  return db
    .prepare('SELECT * FROM image_records WHERE id = ?')
    .get(result.lastInsertRowid);
}

/** 获取识图历史 */
function listImageRecords(db, limit = 20) {
  return db
    .prepare(
      `SELECT id, filename, ingredients, description, created_at
       FROM image_records ORDER BY created_at DESC LIMIT ?`
    )
    .all(limit);
}

/** 获取识图详情 */
function getImageRecord(db, id) {
  return db.prepare('SELECT * FROM image_records WHERE id = ?').get(id);
}

module.exports = {
  getMemoryContext,
  saveIngredientsMemory,
  savePreference,
  listMemories,
  deleteMemory,
  saveImageRecord,
  listImageRecords,
  getImageRecord
};
