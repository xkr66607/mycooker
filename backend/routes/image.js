const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const router = express.Router();
const { analyzeFoodImage } = require('../services/visionService');
const { searchRecipesByIngredients } = require('../services/aiService');
const {
  saveIngredientsMemory,
  saveImageRecord,
  listImageRecords,
  getImageRecord
} = require('../services/memoryService');

// 上传目录
const UPLOAD_DIR = path.join(__dirname, '..', 'uploads');
if (!fs.existsSync(UPLOAD_DIR)) {
  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
}

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, UPLOAD_DIR),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname) || '.jpg';
    cb(null, `${Date.now()}-${Math.random().toString(36).slice(2)}${ext}`);
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    if (file.mimetype.startsWith('image/')) cb(null, true);
    else cb(new Error('仅支持图片文件（jpg/png/webp/gif）'));
  }
});

/**
 * POST /api/image/analyze
 * 上传图片 → 识图 → 联网搜菜谱 → 存入记忆
 */
router.post('/analyze', upload.single('image'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ success: false, message: '请上传图片文件' });
    }

    const db = req.app.locals.db;
    const filePath = req.file.path;
    const fileBuffer = fs.readFileSync(filePath);
    const base64 = fileBuffer.toString('base64');
    const mimeType = req.file.mimetype || 'image/jpeg';
    const dataUrl = `data:${mimeType};base64,${base64}`;

    // 1. 视觉识图
    const visionResult = await analyzeFoodImage(dataUrl);
    const ingredients = visionResult.ingredients || [];
    const description = visionResult.description || '';

    if (ingredients.length === 0) {
      return res.json({
        success: true,
        data: {
          ingredients: [],
          description,
          recipes: '图片中未识别到食材，请尝试上传包含食物/食材的清晰照片。',
          imageUrl: `/uploads/${req.file.filename}`,
          recordId: null
        }
      });
    }

    // 2. 存入记忆
    saveIngredientsMemory(db, ingredients, description);

    // 3. 联网搜索菜谱
    const recipes = await searchRecipesByIngredients(ingredients);

    // 4. 保存识图记录
    const record = saveImageRecord(
      db,
      req.file.filename,
      ingredients,
      description,
      recipes
    );

    res.json({
      success: true,
      data: {
        ingredients,
        description,
        confidence: visionResult.confidence || 'medium',
        recipes,
        imageUrl: `/uploads/${req.file.filename}`,
        recordId: record.id
      }
    });
  } catch (err) {
    console.error('[Image Analyze Error]', err.message);
    res.status(500).json({
      success: false,
      message: err.message || '图片解析失败，请稍后重试'
    });
  }
});

/**
 * GET /api/image/history
 * 识图历史记录
 */
router.get('/history', (req, res) => {
  try {
    const db = req.app.locals.db;
    const records = listImageRecords(db);
    const parsed = records.map((r) => ({
      ...r,
      ingredients: JSON.parse(r.ingredients || '[]')
    }));
    res.json({ success: true, data: parsed });
  } catch (err) {
    res.status(500).json({ success: false, message: '获取识图历史失败' });
  }
});

/**
 * GET /api/image/history/:id
 * 识图详情（含完整菜谱结果）
 */
router.get('/history/:id', (req, res) => {
  try {
    const db = req.app.locals.db;
    const record = getImageRecord(db, req.params.id);
    if (!record) {
      return res.status(404).json({ success: false, message: '记录不存在' });
    }
    res.json({
      success: true,
      data: {
        ...record,
        ingredients: JSON.parse(record.ingredients || '[]'),
        imageUrl: `/uploads/${record.filename}`
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, message: '获取详情失败' });
  }
});

module.exports = router;
