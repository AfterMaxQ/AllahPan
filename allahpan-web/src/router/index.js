import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/set-password',
    name: 'SetPassword',
    component: () => import('@/views/SetPassword.vue'),
  },
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    children: [
      { path: '', name: 'FileBrowser', component: () => import('@/views/FileBrowser.vue') },
      { path: 'favorites', name: 'Favorites', component: () => import('@/views/Favorites.vue') },
      { path: 'search', name: 'Search', component: () => import('@/views/Search.vue') },
      { path: 'trash', name: 'Trash', component: () => import('@/views/Trash.vue') },
    ],
  },
  {
    path: '/share/:code',
    name: 'SharedView',
    component: () => import('@/views/SharedView.vue'),
    meta: { public: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  if (!to.meta.public && !userStore.token) {
    return next('/login')
  }

  if (userStore.token && userStore.isFirstLogin && to.path !== '/set-password') {
    return next('/set-password')
  }

  if (to.path === '/login' && userStore.token) {
    return next('/')
  }

  next()
})

export default router
