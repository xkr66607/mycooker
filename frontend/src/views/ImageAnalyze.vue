<template>
  <div class="analyze-page">
    <div class="page-header">
      <h1>📷 识图做菜</h1>
      <p>上传食材图片，AI 自动识别并联网搜索能做什么菜</p>
    </div>

    <div class="analyze-layout">
      <!-- 左侧：上传 + 分析 -->
      <div class="main-col">
        <ImageUpload ref="uploadRef" @select="onFileSelect" @clear="onClear" />

        <div class="action-bar">
          <el-button
            type="primary"
            size="large"
            :loading="analyzing"
            :disabled="!selectedFile"
            @click="handleAnalyze"
          >
            <el-icon><Search /></el-icon>
            {{ analyzing ? '识别中，正在联网搜菜谱…' : '开始识图 & 搜菜谱' }}
          </el-button>
        </div>

        <!-- 分析进度 -->
        <div v-if="analyzing" class="progress-steps">
          <div class="step" :class="{ active: step >= 1, done: step > 1 }">
            <span class="step-num">1</span> 千问视觉识图
          </div>
          <div class="step" :class="{ active: step >= 2, done: step > 2 }">
            <span class="step-num">2</span> 存入厨房记忆
          </div>
          <div class="step" :class="{ active: step >= 3 }">
            <span class="step-num">3</span> 联网搜索菜谱
          </div>
        </div>

        <!-- 识别结果 -->
        <transition name="fade-slide">
          <div v-if="result" class="result-card">
            <div class="result-section">
              <h3>🥬 识别到的食材</h3>
              <div v-if="result.ingredients.length" class="ingredient-tags">
                <el-tag
                  v-for="item in result.ingredients"
                  :key="item"
                  type="success"
                  effect="plain"
                  round
                  size="large"
                >
                  {{ item }}
                </el-tag>
              </div>
              <p v-else class="no-ingredient">未识别到食材，请换一张更清晰的照片</p>
              <p v-if="result.description" class="desc">{{ result.description }}</p>
            </div>

            <div v-if="result.recipes" class="result-section recipes">
              <h3>🍳 联网搜到的菜谱推荐</h3>
              <div class="recipe-content" v-html="formatRecipes(result.recipes)"></div>
            </div>

            <div class="result-actions">
              <el-button @click="goChatWithResult">💬 继续追问小厨</el-button>
              <el-button plain @click="resetAll">重新上传</el-button>
            </div>
          </div>
        </transition>
      </div>

      <!-- 右侧：记忆 + 历史 -->
      <div class="side-col">
        <MemoryPanel ref="memoryRef" />

        <div class="history-panel">
          <h3>📋 识图历史</h3>
          <div v-if="historyList.length === 0" class="history-empty">暂无记录</div>
          <div
            v-for="item in historyList"
            :key="item.id"
            class="history-item"
            @click="loadHistoryDetail(item.id)"
          >
            <div class="history-ingredients">
              {{ formatIngredients(item.ingredients) }}
            </div>
            <div class="history-time">{{ formatTime(item.created_at) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Search } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import ImageUpload from '@/components/ImageUpload.vue';
import MemoryPanel from '@/components/MemoryPanel.vue';
import { analyzeImage, getImageHistory, getImageDetail } from '@/api';
import { useChatStore } from '@/stores/chat';

const router = useRouter();
const chatStore = useChatStore();

const uploadRef = ref(null);
const memoryRef = ref(null);
const selectedFile = ref(null);
const analyzing = ref(false);
const step = ref(0);
const result = ref(null);
const historyList = ref([]);

function onFileSelect(file) {
  selectedFile.value = file;
  result.value = null;
}

function onClear() {
  selectedFile.value = null;
  result.value = null;
}

async function handleAnalyze() {
  if (!selectedFile.value || analyzing.value) return;

  analyzing.value = true;
  step.value = 1;
  result.value = null;

  try {
    // 模拟步骤进度（实际请求一次性完成）
    setTimeout(() => { step.value = 2; }, 1500);
    setTimeout(() => { step.value = 3; }, 3000);

    const res = await analyzeImage(selectedFile.value);
    result.value = res.data;
    step.value = 3;

    await loadHistory();
    memoryRef.value?.loadMemories();

    if (result.value.ingredients?.length) {
      ElMessage.success(`识别到 ${result.value.ingredients.length} 种食材，菜谱已生成`);
    }
  } catch (err) {
    ElMessage.error(err.message || '识图失败');
  } finally {
    analyzing.value = false;
  }
}

function formatRecipes(text) {
  if (!text) return '';
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/^#{1,3}\s+(.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^[-•]\s+(.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
  html = html.replace(/\n/g, '<br/>');
  return html;
}

async function loadHistory() {
  const res = await getImageHistory();
  historyList.value = res.data || [];
}

async function loadHistoryDetail(id) {
  try {
    const res = await getImageDetail(id);
    result.value = {
      ingredients: res.data.ingredients,
      description: res.data.description,
      recipes: res.data.recipe_result,
      imageUrl: res.data.imageUrl
    };
  } catch (err) {
    ElMessage.error(err.message);
  }
}

function goChatWithResult() {
  if (!result.value?.ingredients?.length) return;
  const q = `我手上有这些食材：${result.value.ingredients.join('、')}，请根据之前的菜谱推荐，告诉我最简单的一道怎么做？`;
  chatStore.resetCurrent();
  router.push('/chat');
  setTimeout(async () => {
    try {
      await chatStore.sendMessage(q);
      router.replace(`/chat/${chatStore.currentConversationId}`);
    } catch {
      /* Chat 页处理 */
    }
  }, 500);
}

function resetAll() {
  uploadRef.value?.clearPreview();
  result.value = null;
  selectedFile.value = null;
}

function formatTime(t) {
  if (!t) return '';
  return new Date(t).toLocaleString('zh-CN', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  });
}

function formatIngredients(ingredients) {
  const list = Array.isArray(ingredients)
    ? ingredients
    : JSON.parse(ingredients || '[]');
  return list.join('、') || '未知';
}

onMounted(loadHistory);
</script>

<style scoped>
.analyze-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px 60px;
}

.page-header {
  text-align: center;
  margin-bottom: 36px;
}

.page-header h1 {
  font-family: var(--font-display);
  font-size: 32px;
  color: var(--color-primary-dark);
  margin-bottom: 8px;
}

.page-header p {
  color: var(--color-text-secondary);
  font-size: 15px;
}

.analyze-layout {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 24px;
  align-items: start;
}

.action-bar {
  margin-top: 16px;
  text-align: center;
}

.action-bar .el-button {
  min-width: 240px;
  border-radius: var(--radius-sm);
}

.progress-steps {
  display: flex;
  justify-content: center;
  gap: 24px;
  margin-top: 24px;
  padding: 16px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  transition: color var(--transition);
}

.step.active { color: var(--color-primary); font-weight: 600; }
.step.done { color: var(--color-primary-light); }

.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  transition: background var(--transition);
}

.step.active .step-num {
  background: var(--color-primary);
  color: #fff;
}

.result-card {
  margin-top: 24px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 28px;
  box-shadow: var(--shadow-md);
}

.result-section {
  margin-bottom: 24px;
}

.result-section h3 {
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--color-primary-dark);
  margin-bottom: 14px;
}

.ingredient-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.desc {
  margin-top: 12px;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.no-ingredient {
  color: var(--color-text-secondary);
  font-size: 14px;
}

.recipe-content {
  line-height: 1.8;
  font-size: 15px;
}

.recipe-content :deep(h4) {
  font-family: var(--font-display);
  color: var(--color-primary-dark);
  margin: 16px 0 8px;
}

.recipe-content :deep(ul) {
  padding-left: 20px;
  margin: 8px 0;
}

.recipe-content :deep(strong) {
  color: var(--color-primary);
}

.result-actions {
  display: flex;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--color-border);
}

.history-panel {
  margin-top: 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow-sm);
}

.history-panel h3 {
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--color-primary-dark);
  margin-bottom: 12px;
}

.history-empty {
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 13px;
  padding: 16px 0;
}

.history-item {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition);
  margin-bottom: 6px;
}

.history-item:hover {
  background: rgba(45, 106, 79, 0.06);
}

.history-ingredients {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-time {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

@media (max-width: 900px) {
  .analyze-layout {
    grid-template-columns: 1fr;
  }
}
</style>
