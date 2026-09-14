<template>
  <aside class="sidebar" :class="{ collapsed: !sidebarOpen }">
    <div class="sidebar-header">
      <h3 v-show="sidebarOpen">对话历史</h3>
      <el-button
        :icon="sidebarOpen ? Fold : Expand"
        text
        @click="chatStore.toggleSidebar()"
      />
    </div>

    <div v-show="sidebarOpen" class="sidebar-actions">
      <el-button type="primary" :icon="Plus" @click="handleNewChat" block>
        新对话
      </el-button>
    </div>

    <div v-show="sidebarOpen" class="conversation-list">
      <div
        v-for="conv in chatStore.conversations"
        :key="conv.id"
        class="conversation-item"
        :class="{ active: conv.id === chatStore.currentConversationId }"
        @click="handleSelect(conv.id)"
      >
        <el-icon class="conv-icon"><ChatLineSquare /></el-icon>
        <div class="conv-info">
          <span class="conv-title">{{ conv.title }}</span>
          <span class="conv-time">{{ formatTime(conv.updated_at) }}</span>
        </div>
        <el-button
          :icon="Delete"
          text
          size="small"
          class="delete-btn"
          @click.stop="handleDelete(conv.id)"
        />
      </div>

      <div v-if="chatStore.conversations.length === 0" class="empty-history">
        <p>暂无历史对话</p>
        <p class="sub">开始第一次问答吧 🍳</p>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, Delete, Fold, Expand, ChatLineSquare } from '@element-plus/icons-vue';
import { ElMessageBox } from 'element-plus';
import { useChatStore } from '@/stores/chat';
import { storeToRefs } from 'pinia';

const router = useRouter();
const chatStore = useChatStore();
const { sidebarOpen } = storeToRefs(chatStore);

onMounted(() => {
  chatStore.fetchConversations();
});

function formatTime(timeStr) {
  if (!timeStr) return '';
  const d = new Date(timeStr);
  const now = new Date();
  const diff = now - d;
  if (diff < 86400000) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

async function handleNewChat() {
  chatStore.resetCurrent();
  router.push('/chat');
}

async function handleSelect(id) {
  await chatStore.loadConversation(id);
  router.push(`/chat/${id}`);
}

async function handleDelete(id) {
  try {
    await ElMessageBox.confirm('确定删除这条对话记录吗？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    });
    await chatStore.removeConversation(id);
    if (chatStore.currentConversationId === null) {
      router.push('/chat');
    }
  } catch {
    /* 用户取消 */
  }
}
</script>

<style scoped>
.sidebar {
  width: 280px;
  flex-shrink: 0;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  transition: width var(--transition);
  overflow: hidden;
}

.sidebar.collapsed {
  width: 52px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.sidebar-header h3 {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary-dark);
}

.sidebar-actions {
  padding: 12px 16px;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition);
  margin-bottom: 4px;
}

.conversation-item:hover {
  background: rgba(45, 106, 79, 0.06);
}

.conversation-item.active {
  background: rgba(45, 106, 79, 0.12);
  border-left: 3px solid var(--color-primary);
}

.conv-icon {
  color: var(--color-primary-light);
  flex-shrink: 0;
}

.conv-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.conv-title {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-time {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-top: 2px;
}

.delete-btn {
  opacity: 0;
  transition: opacity var(--transition);
}

.conversation-item:hover .delete-btn {
  opacity: 1;
}

.empty-history {
  text-align: center;
  padding: 40px 16px;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.empty-history .sub {
  font-size: 12px;
  margin-top: 8px;
  opacity: 0.7;
}
</style>
