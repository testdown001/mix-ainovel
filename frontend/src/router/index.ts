// AIMETA P=路由配置_所有页面路由定义|R=路由表_导航守卫_权限控制|NR=不含组件实现|E=router:index|X=internal|A=router实例|D=vue-router|S=none|RD=./README.ai
import { createRouter, createWebHistory } from 'vue-router'
import NovelWorkspace from '../views/NovelWorkspace.vue'
import InspirationMode from '../views/InspirationMode.vue'
import WritingDesk from '../views/WritingDesk.vue'
import NovelDetail from '../views/NovelDetail.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'landing',
      component: () => import('../views/LandingView.vue'),
    },
    {
      path: '/home',
      name: 'workspace-entry',
      component: () => import('../views/WorkspaceEntry.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/workspace',
      name: 'novel-workspace',
      component: NovelWorkspace,
      meta: { requiresAuth: true },
    },
    {
      path: '/inspiration',
      name: 'inspiration-mode',
      component: InspirationMode,
      meta: { requiresAuth: true },
    },
    {
      path: '/detail/:id',
      name: 'novel-detail',
      component: NovelDetail,
      props: true,
      meta: { requiresAuth: true },
    },
    {
      path: '/novel/:id',
      name: 'writing-desk',
      component: WritingDesk,
      props: true,
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: Login,
    },
    {
      path: '/register',
      name: 'register',
      component: Register,
    },
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('../views/ForgotPassword.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/novel/:id',
      name: 'admin-novel-detail',
      component: () => import('../views/AdminNovelDetail.vue'),
      props: true,
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/pricing',
      name: 'pricing',
      component: () => import('../views/PricingView.vue'),
    },
    {
      path: '/terms',
      name: 'terms',
      component: () => import('../views/TermsView.vue'),
    },
    {
      path: '/privacy',
      name: 'privacy',
      component: () => import('../views/PrivacyView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('../views/NotFound.vue'),
    },
  ],
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  
  if (authStore.token && !authStore.user) {
    await authStore.fetchUser()
  }

  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)
  const requiresAdmin = to.matched.some(record => record.meta.requiresAdmin)
  const isAuthenticated = authStore.isAuthenticated
  const isAdmin = authStore.user?.is_admin

  const mustChangePassword = authStore.user?.is_admin && authStore.mustChangePassword

  if (requiresAuth && !isAuthenticated) {
    next('/')
  } else if (requiresAdmin && !isAdmin) {
    next('/home')
  } else if (isAuthenticated && mustChangePassword) {
    if (to.name !== 'admin' || to.query.tab !== 'password') {
      next({ name: 'admin', query: { tab: 'password' } })
    } else {
      next()
    }
  } else {
    next()
  }
})

// ---------------------------------------------------------------------------
// 发版自愈：旧标签页遇到已被删除的 chunk 时整页重载一次
//
// 路由组件都是懒加载（() => import(...)），chunk 文件名带内容 hash。发版后旧文件
// 即被删除，而**已经打开着的**标签页跑的仍是旧 SPA，切路由时就会去请求那个不存在的
// chunk → "Failed to fetch dynamically imported module"，页面卡死在原地。
// 服务端已把 index.html 设为 no-cache（见 backend/app/main.py 的 _apply_spa_cache_headers），
// 所以整页重载必定拿到新 index 与新 chunk 名。
//
// sessionStorage 打标防死循环：重载后若仍失败（真的服务端坏了），不再继续刷。
// ---------------------------------------------------------------------------
const CHUNK_RELOAD_FLAG = 'arb:chunk-reload'
const CHUNK_ERROR_RE =
  /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed/i

function reloadOnceForStaleChunk(target?: string): boolean {
  if (sessionStorage.getItem(CHUNK_RELOAD_FLAG)) return false
  sessionStorage.setItem(CHUNK_RELOAD_FLAG, '1')
  window.location.assign(target || window.location.href)
  return true
}

router.onError((error, to) => {
  if (!CHUNK_ERROR_RE.test(String((error as Error)?.message ?? ''))) return
  reloadOnceForStaleChunk(to?.fullPath)
})

// Vite 对 <link rel=modulepreload> 的加载失败走这个事件，不经过 router.onError
window.addEventListener('vite:preloadError', () => {
  reloadOnceForStaleChunk()
})

// 导航成功即说明当前构建产物可用，清标；下次发版才能再自愈一次
router.afterEach(() => {
  sessionStorage.removeItem(CHUNK_RELOAD_FLAG)
})

export default router
