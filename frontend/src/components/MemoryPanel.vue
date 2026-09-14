<template>
  <div class="memory-panel">
    <div class="memory-header">
      <h3>🧠 我的厨房记忆</h3>
      <el-button text size="small" :icon="Refresh" @click="loadMemories" />
    </div>

    <div v-if="memories.length === 0" class="memory-empty">
      暂无记忆，识图或对话后会自动记录
    </div>

    <div v-else class="memory-list">
      <div v-for="item in memories" :key="item.id" class="memory-item">
        <div class="memory-tag">{{ categoryLabel(item.category) }}</div>
        <div class="memory-content">{{ item.value }}</div>
        <div class="memory-meta">
          <span>{{ formatTime(item.created_at) }}</span>
          <el-button
            text
            type="danger"
            size="small"
            :icon="Delete"
            @click="handleDelete(item.id)"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { Delete, Refresh } from '@element-plus/icons-vue';
import { ElMessageBox } from 'element-plus';
import { getMemories, deleteMemory } from '@/api';

const memories = ref([]);

const categoryMap = {
  ingredient: '识图食材',
  ingredient_summary: '食材汇总',
  preference: '个人偏好'
};

function categoryLabel(cat) {
  return categoryMap[cat] || cat;
}

function formatTime(t) {
  if (!t) return '';
  return new Date(t).toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

async function loadMemories() {
  const res = await getMemories();
  memories.value = res.data || [];
}

async function handleDelete(id) {
  try {
    await ElMessageBox.confirm('确定删除这条记忆吗？', '提示', { type: 'warning' });
    await deleteMemory(id);
    await loadMemories();
  } catch {
    /* 取消 */
  }
}

onMounted(loadMemories);

defineExpose({ loadMemories });
</script>

<style scoped>
.memory-panel {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow-sm);
}

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.memory-header h3 {
  font-family: var(--font-display);
  font-size: 16px;
  color: var(--color-primary-dark);
}

.memory-empty {
  text-align: center;
  color: var(--color-text-secondary);
  font-size: 13px;
  padding: 24px 0;
}

.memory-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 400px;
  overflow-y: auto;
}

.memory-item {
  padding: 12px;
  background: var(--color-bg);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--color-primary-light);
}

.memory-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary);
  background: rgba(45, 106, 79, 0.1);
  padding: 2px 8px;
  border-radius: 10px;
  margin-bottom: 6px;
}

.memory-content {
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text);
}

.memory-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
</style>
