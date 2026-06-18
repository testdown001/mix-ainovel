<template>
  <div class="min-h-screen flex flex-col items-center justify-center p-4"
    style="background:#0A0A0A; font-family:'Inter',sans-serif;">

    <div class="fixed inset-0 pointer-events-none" style="background-image:linear-gradient(#161616 1px,transparent 1px),linear-gradient(90deg,#161616 1px,transparent 1px);background-size:48px 48px;opacity:0.6;"></div>
    <div class="fixed inset-0 pointer-events-none" style="background:radial-gradient(ellipse 60% 40% at 50% 0%,rgba(255,229,0,0.04) 0%,transparent 70%);"></div>

    <div class="relative text-center max-w-lg">

      <!-- 404 number -->
      <div class="mb-6 select-none" style="font-size:9rem; font-weight:900; line-height:1; color:#1A1A1A; font-family:'Space Grotesk',sans-serif; letter-spacing:-4px;">
        404
      </div>

      <!-- Icon -->
      <div class="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-6 -mt-8"
        style="background:#FFE500;">
        <svg class="w-8 h-8" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>

      <h1 class="text-2xl font-bold text-white mb-3" style="font-family:'Space Grotesk',sans-serif;">
        页面不见了
      </h1>
      <p class="text-sm mb-8" style="color:#555; line-height:1.7;">
        你访问的页面可能已被删除、移走，或者从未存在过。<br>不要担心，回到首页继续你的创作之旅吧。
      </p>

      <div class="flex items-center justify-center gap-3">
        <button @click="router.push('/')"
          class="px-6 py-3 rounded-xl font-semibold text-sm transition-all"
          style="background:#FFE500; color:#000;"
          @mouseenter="($event.currentTarget as HTMLElement).style.background='#FFF000'"
          @mouseleave="($event.currentTarget as HTMLElement).style.background='#FFE500'">
          返回首页
        </button>
        <button @click="router.go(-1)"
          class="px-6 py-3 rounded-xl font-semibold text-sm transition-all"
          style="background:#1A1A1A; color:#888; border:1px solid #2A2A2A;"
          @mouseenter="($event.currentTarget as HTMLElement).style.borderColor='#444'"
          @mouseleave="($event.currentTarget as HTMLElement).style.borderColor='#2A2A2A'">
          返回上一页
        </button>
      </div>

      <!-- Logo -->
      <div class="flex items-center justify-center gap-2 mt-12 cursor-pointer" @click="router.push('/')">
        <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background:#FFE500;">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" style="color:#000;">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
          </svg>
        </div>
        <span class="text-sm font-bold text-white" style="font-family:'Space Grotesk',sans-serif;">Octopus AI Novel</span>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
</script>
