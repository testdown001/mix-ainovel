<!-- AIMETA P=作品公开分享阅读页_免登录|R=分享目录_章节阅读_注册转化CTA|NR=不含分享开关(owner侧在NovelDetailShell)|E=view:SharedNovelView|X=internal|A=页面组件|D=vue|S=net -->
<template>
  <div class="min-h-screen flex flex-col" style="background: #0A0A0A; font-family: 'Inter', sans-serif;">

    <!-- ==================== Top Brand Bar ==================== -->
    <header class="sticky top-0 z-40 border-b" style="background: rgba(10,10,10,0.85); backdrop-filter: blur(12px); border-color: #2A2A2A;">
      <div class="max-w-2xl mx-auto px-5 h-14 flex items-center justify-between">
        <router-link to="/" class="flex items-center gap-2.5 min-w-0">
          <div class="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style="background: #FFE500;">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color: #000;">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
            </svg>
          </div>
          <span class="text-base font-bold tracking-tight truncate" style="font-family: 'Space Grotesk', sans-serif; color: #fff;">Octopus AI Novel</span>
        </router-link>
        <router-link :to="registerLink"
          class="flex-shrink-0 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-90"
          style="background: #FFE500; color: #000;">
          免费注册
        </router-link>
      </div>
    </header>

    <!-- ==================== Loading ==================== -->
    <div v-if="isLoading" class="flex-1 flex flex-col items-center justify-center py-24">
      <div class="w-8 h-8 border-2 rounded-full animate-spin" style="border-color: #2A2A2A; border-top-color: #FFE500;"></div>
      <p class="mt-4 text-sm" style="color: #888;">加载中...</p>
    </div>

    <!-- ==================== Invalid Link ==================== -->
    <div v-else-if="isInvalid" class="flex-1 flex flex-col items-center justify-center px-5 py-24 text-center">
      <div class="w-16 h-16 rounded-full flex items-center justify-center mb-5" style="background: rgba(255, 229, 0, 0.12);">
        <svg class="w-8 h-8" style="color: #FFE500;" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
        </svg>
      </div>
      <h1 class="text-xl font-bold text-white mb-2">链接已失效</h1>
      <p class="text-sm leading-6 mb-8" style="color: #888;">这个分享链接不存在，或者作者已经关闭了分享。</p>
      <router-link to="/register"
        class="px-6 py-3 rounded-xl text-sm font-semibold transition-all hover:opacity-90"
        style="background: #FFE500; color: #000;">
        免费注册，写你自己的小说
      </router-link>
    </div>

    <!-- ==================== Reading View ==================== -->
    <main v-else-if="currentChapter" class="flex-1 w-full max-w-2xl mx-auto px-5 pt-6 pb-28">
      <button class="flex items-center gap-1.5 text-sm mb-6 transition-colors" style="color: #888;"
        @click="backToToc"
        @mouseenter="($event.currentTarget as HTMLElement).style.color='#FFE500'"
        @mouseleave="($event.currentTarget as HTMLElement).style.color='#888'">
        <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
        </svg>
        返回目录
      </button>

      <h2 class="text-xl font-bold text-white leading-snug mb-1.5">
        第{{ currentChapter.chapter_number }}章 {{ currentChapter.title }}
      </h2>
      <p class="text-xs mb-8" style="color: #666;">《{{ overview?.title }}》 · {{ overview?.author_name }}</p>

      <div v-if="isChapterLoading" class="flex justify-center py-16">
        <div class="w-7 h-7 border-2 rounded-full animate-spin" style="border-color: #2A2A2A; border-top-color: #FFE500;"></div>
      </div>
      <!-- 正文：17px/2 行高在 390px 宽下约 22 字/行，游客长读不费眼 -->
      <article v-else class="space-y-5">
        <p v-for="(paragraph, idx) in paragraphs" :key="idx"
          class="text-[17px] leading-8 tracking-[0.01em]" style="color: #D4D4D4;">
          {{ paragraph }}
        </p>
      </article>

      <!-- Prev / Next -->
      <div class="flex items-center gap-3 mt-12">
        <button class="flex-1 py-3 rounded-xl text-sm font-medium border transition-all"
          :style="currentChapter.prev !== null
            ? 'border-color: #2A2A2A; color: #fff;'
            : 'border-color: #1C1C1C; color: #444; cursor: not-allowed;'"
          :disabled="currentChapter.prev === null"
          @click="openChapter(currentChapter.prev!)">
          上一章
        </button>
        <button class="flex-1 py-3 rounded-xl text-sm font-medium border transition-all" style="border-color: #2A2A2A; color: #888;"
          @click="backToToc">
          目录
        </button>
        <button class="flex-1 py-3 rounded-xl text-sm font-semibold transition-all"
          :style="currentChapter.next !== null
            ? 'background: #FFE500; color: #000;'
            : 'background: #1C1C1C; color: #444; cursor: not-allowed;'"
          :disabled="currentChapter.next === null"
          @click="openChapter(currentChapter.next!)">
          下一章
        </button>
      </div>
    </main>

    <!-- ==================== Table of Contents ==================== -->
    <main v-else-if="overview" class="flex-1 w-full max-w-2xl mx-auto px-5 pt-8 pb-28">
      <div class="mb-8">
        <h1 class="text-2xl font-bold text-white leading-snug">《{{ overview.title }}》</h1>
        <p class="text-sm mt-2" style="color: #888;">
          {{ overview.author_name }} 著 · 共 {{ overview.chapter_count }} 章
        </p>
        <p v-if="overview.description" class="text-sm leading-6 mt-3" style="color: #999;">
          {{ overview.description }}
        </p>
      </div>

      <div v-if="overview.chapters.length === 0" class="py-16 text-center text-sm" style="color: #666;">
        作者还没有完稿的章节，稍后再来看看吧
      </div>
      <div v-else class="rounded-2xl border overflow-hidden" style="border-color: #2A2A2A; background: #121212;">
        <button v-for="(chapter, idx) in overview.chapters" :key="chapter.chapter_number"
          class="w-full flex items-center justify-between gap-3 px-5 py-4 text-left transition-colors chapter-row"
          :class="idx > 0 ? 'border-t' : ''"
          style="border-color: #1F1F1F;"
          @click="openChapter(chapter.chapter_number)">
          <span class="text-[15px] min-w-0 truncate" style="color: #E5E5E5;">
            第{{ chapter.chapter_number }}章 {{ chapter.title }}
          </span>
          <span class="text-xs flex-shrink-0" style="color: #666;">{{ formatWordCount(chapter.word_count) }}</span>
        </button>
      </div>
    </main>

    <!-- ==================== 注册转化 CTA（固定底部，带作者邀请码） ==================== -->
    <div v-if="!isLoading && !isInvalid" class="fixed bottom-0 left-0 right-0 z-40 border-t"
      style="background: rgba(10,10,10,0.92); backdrop-filter: blur(12px); border-color: #2A2A2A;">
      <div class="max-w-2xl mx-auto px-5 py-3 flex items-center justify-between gap-3">
        <p class="text-xs leading-5 min-w-0" style="color: #888;">
          本书由<span style="color: #FFE500;">章鱼AI</span>创作
        </p>
        <router-link :to="registerLink"
          class="flex-shrink-0 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all hover:opacity-90"
          style="background: #FFE500; color: #000;">
          免费注册写你自己的小说
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  shareApi,
  ShareNotFoundError,
  type SharedChapterContent,
  type SharedNovelOverview,
} from '@/api/share'

const props = defineProps<{ token: string }>()

const route = useRoute()
const router = useRouter()

const isLoading = ref(true)
const isInvalid = ref(false)
const overview = ref<SharedNovelOverview | null>(null)
const currentChapter = ref<SharedChapterContent | null>(null)
const isChapterLoading = ref(false)

// 注册 CTA 带作者邀请码：分享转化直接接进邀请返积分闭环
const registerLink = computed(() =>
  overview.value?.author_invite_code
    ? `/register?invite=${encodeURIComponent(overview.value.author_invite_code)}`
    : '/register'
)

const paragraphs = computed(() => {
  if (!currentChapter.value) return []
  return currentChapter.value.content
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
})

const formatWordCount = (count: number) => {
  if (count >= 10000) return `${(count / 10000).toFixed(1)}万字`
  return `${count}字`
}

const openChapter = async (chapterNumber: number) => {
  isChapterLoading.value = true
  // 先切到阅读视图（骨架转圈），避免长章节加载时页面看起来没反应
  if (!currentChapter.value) {
    currentChapter.value = {
      chapter_number: chapterNumber,
      title: overview.value?.chapters.find((c) => c.chapter_number === chapterNumber)?.title || '',
      content: '',
      prev: null,
      next: null,
    }
  }
  try {
    currentChapter.value = await shareApi.getSharedChapter(props.token, chapterNumber)
    // 章号进 query：手机上转发/刷新能回到同一章
    router.replace({ query: { c: String(chapterNumber) } })
    window.scrollTo({ top: 0 })
  } catch (error) {
    if (error instanceof ShareNotFoundError) {
      isInvalid.value = true
    }
    currentChapter.value = null
  } finally {
    isChapterLoading.value = false
  }
}

const backToToc = () => {
  currentChapter.value = null
  router.replace({ query: {} })
  window.scrollTo({ top: 0 })
}

onMounted(async () => {
  try {
    overview.value = await shareApi.getSharedNovel(props.token)
    const initialChapter = Number(route.query.c)
    if (Number.isInteger(initialChapter) && initialChapter > 0) {
      await openChapter(initialChapter)
    }
  } catch (error) {
    if (error instanceof ShareNotFoundError) {
      isInvalid.value = true
    } else {
      // 网络类错误也走失效页兜底：游客页没有更好的重试入口
      isInvalid.value = true
      console.error('加载分享内容失败:', error)
    }
  } finally {
    isLoading.value = false
  }
})
</script>

<style scoped>
.chapter-row:hover {
  background: #1A1A1A;
}
.chapter-row:active {
  background: #1F1F1F;
}
</style>
