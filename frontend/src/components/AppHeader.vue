<template>
  <header class="header">
    <div class="header-inner">
      <router-link to="/" class="logo">
        <span class="logo-icon">🍳</span>
        <span class="logo-text">私人厨房 <em>AI</em></span>
      </router-link>

      <nav class="nav">
        <router-link to="/" class="nav-link" active-class="active">
          <el-icon><HomeFilled /></el-icon>
          首页
        </router-link>
        <router-link to="/analyze" class="nav-link" active-class="active">
          <el-icon><Camera /></el-icon>
          识图做菜
        </router-link>
        <router-link to="/chat" class="nav-link" active-class="active">
          <el-icon><ChatDotRound /></el-icon>
          AI 问答
        </router-link>
      </nav>
    </div>
  </header>
</template>

<script setup>
import { HomeFilled, ChatDotRound, Camera } from '@element-plus/icons-vue';
</script>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
}

.header-inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 32px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  transition: transform var(--transition);
}

.logo:hover {
  transform: scale(1.02);
}

.logo-icon {
  font-size: 28px;
  animation: float 3s ease-in-out infinite;
}

.logo-text {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary-dark);
}

.logo-text em {
  font-style: normal;
  color: var(--color-accent);
}

.nav {
  display: flex;
  gap: 8px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-secondary);
  transition: all var(--transition);
}

.nav-link:hover {
  color: var(--color-primary);
  background: rgba(45, 106, 79, 0.06);
}

.nav-link.active {
  color: var(--color-primary);
  background: rgba(45, 106, 79, 0.1);
  font-weight: 600;
}
</style>
