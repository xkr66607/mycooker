import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/Chat.vue'),
    meta: { title: 'AI 智能问答' }
  },
  {
    path: '/chat/:id',
    name: 'ChatDetail',
    component: () => import('@/views/Chat.vue'),
    meta: { title: 'AI 智能问答' }
  },
  {
    path: '/analyze',
    name: 'Analyze',
    component: () => import('@/views/ImageAnalyze.vue'),
    meta: { title: '识图做菜' }
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
});

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || '私人厨房'} · 私人厨房 AI 助手`;
  next();
});

export default router;
