<template>
  <div class="home">
    <!-- Hero 区域 -->
    <section class="hero">
      <div class="hero-bg"></div>
      <div class="hero-content">
        <div class="hero-badge">🌿 您的专属厨房智囊</div>
        <h1 class="hero-title">
          私人厨房<br /><span class="highlight">AI 助手</span>
        </h1>
        <p class="hero-desc">
          饮食搭配、菜谱推荐、烹饪技巧、减脂餐规划、食材保存……
          一切厨房问题，小厨 AI 随时为您解答。
        </p>
        <div class="hero-actions">
          <el-button type="primary" size="large" @click="$router.push('/analyze')">
            <el-icon><Camera /></el-icon>
            识图做菜
          </el-button>
          <el-button size="large" @click="$router.push('/chat')">
            <el-icon><ChatDotRound /></el-icon>
            开始问答
          </el-button>
          <el-button size="large" plain @click="scrollToFeatures">
            了解更多
          </el-button>
        </div>
      </div>
      <div class="hero-visual">
        <div class="floating-card card-1">🥗 健康减脂餐</div>
        <div class="floating-card card-2">🍳 烹饪技巧</div>
        <div class="floating-card card-3">🥬 食材保存</div>
        <div class="hero-circle"></div>
      </div>
    </section>

    <!-- 功能卡片 -->
    <section ref="featuresRef" class="features">
      <h2 class="section-title">我能帮您做什么？</h2>
      <p class="section-sub">专注厨房场景，提供专业、实用的饮食建议</p>
      <div class="feature-grid">
        <div
          v-for="(item, index) in features"
          :key="item.title"
          class="feature-card"
          :style="{ animationDelay: `${index * 0.08}s` }"
          @click="$router.push(item.route || '/chat')"
        >
          <div class="feature-icon">{{ item.icon }}</div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.desc }}</p>
        </div>
      </div>
    </section>

    <!-- 示例问题 -->
    <section class="examples">
      <h2 class="section-title">试试这些问题</h2>
      <div class="example-tags">
        <el-tag
          v-for="q in exampleQuestions"
          :key="q"
          class="example-tag"
          effect="plain"
          round
          size="large"
          @click="goChatWithQuestion(q)"
        >
          {{ q }}
        </el-tag>
      </div>
    </section>

    <!-- CTA -->
    <section class="cta">
      <div class="cta-card">
        <h2>准备好提升您的厨艺了吗？</h2>
        <p>与小厨 AI 对话，开启您的智能厨房之旅</p>
        <el-button type="primary" size="large" round @click="$router.push('/chat')">
          立即体验 →
        </el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ChatDotRound, Camera } from '@element-plus/icons-vue';
import { useChatStore } from '@/stores/chat';

const router = useRouter();
const chatStore = useChatStore();
const featuresRef = ref(null);

const features = [
  { icon: '📷', title: '识图做菜', desc: '拍照识别食材，联网搜索菜谱', route: '/analyze' },
  { icon: '🥗', title: '饮食搭配', desc: '科学营养搭配，均衡每日膳食', route: '/chat' },
  { icon: '📖', title: '菜谱推荐', desc: '根据食材和口味推荐合适菜谱', route: '/chat' },
  { icon: '🔪', title: '烹饪技巧', desc: '火候、调味、刀工等专业指导', route: '/chat' },
  { icon: '💪', title: '减脂餐', desc: '低卡高蛋白的健康餐食方案', route: '/chat' },
  { icon: '🧊', title: '食材保存', desc: '保鲜储存方法，减少浪费', route: '/chat' }
];

const exampleQuestions = [
  '番茄炒蛋怎么做才嫩滑？',
  '一周减脂餐怎么安排？',
  '买回来的绿叶菜怎么保存更久？',
  '低卡高蛋白晚餐推荐',
  '新手学做饭从哪道菜开始？'
];

function scrollToFeatures() {
  featuresRef.value?.scrollIntoView({ behavior: 'smooth' });
}

async function goChatWithQuestion(q) {
  chatStore.resetCurrent();
  router.push('/chat');
  // 延迟发送，等 Chat 页挂载完成
  setTimeout(async () => {
    try {
      await chatStore.sendMessage(q);
    } catch {
      /* 错误在 Chat 页处理 */
    }
  }, 600);
}
</script>

<style scoped>
.home {
  overflow-x: hidden;
}

/* Hero */
.hero {
  position: relative;
  max-width: 1280px;
  margin: 0 auto;
  padding: 60px 32px 80px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 48px;
  align-items: center;
  min-height: 520px;
}

.hero-bg {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at 30% 20%, rgba(45, 106, 79, 0.08) 0%, transparent 60%),
    radial-gradient(ellipse at 70% 80%, rgba(224, 122, 95, 0.06) 0%, transparent 50%);
  pointer-events: none;
}

.hero-content {
  position: relative;
  z-index: 1;
}

.hero-badge {
  display: inline-block;
  padding: 6px 16px;
  background: rgba(45, 106, 79, 0.1);
  color: var(--color-primary);
  border-radius: 20px;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 20px;
}

.hero-title {
  font-family: var(--font-display);
  font-size: 48px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--color-primary-dark);
  margin-bottom: 20px;
}

.hero-title .highlight {
  color: var(--color-accent);
}

.hero-desc {
  font-size: 17px;
  line-height: 1.8;
  color: var(--color-text-secondary);
  margin-bottom: 32px;
  max-width: 480px;
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.hero-actions .el-button {
  padding: 12px 28px;
  font-size: 15px;
  border-radius: var(--radius-sm);
}

/* Hero 视觉 */
.hero-visual {
  position: relative;
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero-circle {
  width: 280px;
  height: 280px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(45, 106, 79, 0.15), rgba(224, 122, 95, 0.1));
  animation: float 4s ease-in-out infinite;
}

.floating-card {
  position: absolute;
  padding: 14px 22px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  animation: float 3s ease-in-out infinite;
}

.card-1 { top: 60px; left: 20px; animation-delay: 0s; }
.card-2 { top: 140px; right: 10px; animation-delay: 0.8s; }
.card-3 { bottom: 60px; left: 60px; animation-delay: 1.6s; }

/* Features */
.features {
  max-width: 1280px;
  margin: 0 auto;
  padding: 60px 32px;
}

.section-title {
  font-family: var(--font-display);
  font-size: 32px;
  font-weight: 700;
  text-align: center;
  color: var(--color-primary-dark);
  margin-bottom: 8px;
}

.section-sub {
  text-align: center;
  color: var(--color-text-secondary);
  margin-bottom: 40px;
  font-size: 15px;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.feature-card {
  padding: 32px 28px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all var(--transition);
  animation: fadeIn 0.5s ease both;
}

.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: var(--color-primary-light);
}

.feature-icon {
  font-size: 36px;
  margin-bottom: 16px;
}

.feature-card h3 {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--color-primary-dark);
}

.feature-card p {
  font-size: 14px;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

/* Examples */
.examples {
  max-width: 900px;
  margin: 0 auto;
  padding: 40px 32px 60px;
  text-align: center;
}

.example-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  margin-top: 24px;
}

.example-tag {
  cursor: pointer;
  padding: 10px 20px !important;
  font-size: 14px !important;
  border-color: var(--color-border) !important;
  color: var(--color-text) !important;
  transition: all var(--transition);
}

.example-tag:hover {
  border-color: var(--color-primary-light) !important;
  color: var(--color-primary) !important;
  background: rgba(45, 106, 79, 0.06) !important;
}

/* CTA */
.cta {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 32px 80px;
}

.cta-card {
  text-align: center;
  padding: 56px 40px;
  background: linear-gradient(135deg, var(--color-primary-dark), var(--color-primary));
  border-radius: var(--radius-lg);
  color: #fff;
  box-shadow: var(--shadow-lg);
}

.cta-card h2 {
  font-family: var(--font-display);
  font-size: 28px;
  margin-bottom: 12px;
}

.cta-card p {
  opacity: 0.85;
  margin-bottom: 28px;
  font-size: 15px;
}

.cta-card .el-button {
  background: #fff;
  color: var(--color-primary-dark);
  border: none;
  font-weight: 600;
  padding: 12px 32px;
}

.cta-card .el-button:hover {
  background: rgba(255, 255, 255, 0.9);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 900px) {
  .hero {
    grid-template-columns: 1fr;
    text-align: center;
    padding: 40px 24px 60px;
  }
  .hero-desc { margin: 0 auto 32px; }
  .hero-actions { justify-content: center; }
  .hero-visual { height: 200px; }
  .hero-title { font-size: 36px; }
  .feature-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 600px) {
  .feature-grid { grid-template-columns: 1fr; }
  .hero-title { font-size: 30px; }
}
</style>
