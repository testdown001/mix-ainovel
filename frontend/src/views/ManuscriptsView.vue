<template>
  <div class="ms-root">
    <div class="ms-header">
      <div>
        <h1 class="ms-title">MANUSCRIPTS</h1>
        <p class="ms-subtitle">你的作品档案库</p>
      </div>
      <button class="ms-cta">+ Start New Archive</button>
    </div>

    <div class="ms-filters">
      <button v-for="f in filters" :key="f" class="ms-filter" :class="{ 'ms-filter--active': activeFilter === f }" @click="activeFilter = f">{{ f }}</button>
      <select class="ms-sort">
        <option>最近更新</option>
        <option>创建时间</option>
        <option>字数最多</option>
      </select>
    </div>

    <div class="ms-grid stagger-reveal">
      <div v-for="m in manuscripts" :key="m.id" class="ms-card">
        <div class="ms-cover" :style="{ background: m.color }">
          <span class="ms-cover-text">{{ m.title.charAt(0) }}</span>
        </div>
        <div class="ms-info">
          <div class="ms-genre">{{ m.genre }}</div>
          <h3 class="ms-name">{{ m.title }}</h3>
          <div class="ms-stats">
            <span>{{ m.words.toLocaleString() }} 字</span>
            <span>AI {{ m.aiPct }}%</span>
            <span class="ms-quality">Q: {{ m.quality }}</span>
          </div>
          <div class="ms-progress-bar"><div class="ms-progress-fill" :style="{ width: m.progress + '%' }"></div></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const activeFilter = ref('全部')
const filters = ['全部', '科幻', '奇幻', '悬疑', '都市']

const manuscripts = [
  { id: 1, title: '霓虹边界', genre: '赛博朋克', words: 156000, aiPct: 22, quality: 92, progress: 68, color: 'linear-gradient(135deg, #0f1419, #1a2332)' },
  { id: 2, title: '星际记忆商', genre: '太空歌剧', words: 89000, aiPct: 15, quality: 88, progress: 45, color: 'linear-gradient(135deg, #0f1419, #1a1f32)' },
  { id: 3, title: '量子之梦', genre: '硬科幻', words: 210000, aiPct: 30, quality: 95, progress: 82, color: 'linear-gradient(135deg, #0f1419, #2a1f19)' },
  { id: 4, title: '灵魂代码', genre: '赛博朋克', words: 42000, aiPct: 8, quality: 78, progress: 20, color: 'linear-gradient(135deg, #0f1419, #19302a)' },
  { id: 5, title: '暗影协议', genre: '悬疑', words: 125000, aiPct: 18, quality: 90, progress: 55, color: 'linear-gradient(135deg, #0f1419, #2a2019)' },
]
</script>

<style scoped>
.ms-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.ms-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.ms-title { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.ms-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.ms-cta { padding: 10px 20px; border: none; border-radius: 4px; background: var(--ar-primary); color: var(--ar-on-primary); font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.ms-cta:hover { box-shadow: 0 0 20px rgba(250,204,21,0.3); }
.ms-filters { display: flex; align-items: center; gap: 8px; margin-bottom: 24px; }
.ms-filter { padding: 6px 14px; border-radius: 2px; border: 1px solid rgba(77,70,50,0.2); background: transparent; color: var(--ar-text-secondary); font-size: 13px; cursor: pointer; transition: all 0.15s; }
.ms-filter--active { background: var(--ar-primary); color: var(--ar-on-primary); border-color: var(--ar-primary); }
.ms-sort { margin-left: auto; padding: 8px 12px; background: var(--ar-bg-surface); border: 1px solid rgba(77,70,50,0.15); border-radius: 4px; color: var(--ar-text-primary); font-size: 13px; outline: none; }
.ms-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.ms-card { background: var(--ar-bg-surface); border-radius: 4px; overflow: hidden; transition: all 0.2s; cursor: pointer; }
.ms-card:hover { box-shadow: 0 0 30px rgba(255,236,185,0.06); transform: translateY(-2px); }
.ms-cover { height: 120px; display: flex; align-items: center; justify-content: center; }
.ms-cover-text { font-family: var(--ar-font-manuscript); font-size: 48px; font-weight: 700; color: rgba(250,204,21,0.3); }
.ms-info { padding: 16px; }
.ms-genre { font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ar-secondary); margin-bottom: 6px; }
.ms-name { font-family: var(--ar-font-display); font-size: 18px; font-weight: 700; color: var(--ar-text-primary); margin-bottom: 10px; }
.ms-stats { display: flex; gap: 12px; font-size: 12px; color: var(--ar-text-muted); margin-bottom: 10px; }
.ms-quality { font-weight: 700; color: var(--ar-secondary); }
.ms-progress-bar { height: 3px; background: rgba(77,70,50,0.1); border-radius: 2px; }
.ms-progress-fill { height: 100%; background: var(--ar-primary); border-radius: 2px; }
</style>
