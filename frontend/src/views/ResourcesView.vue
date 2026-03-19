<template>
  <div class="res-root">
    <div class="res-header">
      <div>
        <h1 class="res-title">RESOURCE MANAGER</h1>
        <p class="res-subtitle">创作素材库 · 管理你的创作资源</p>
      </div>
      <div class="res-storage">
        <span class="res-storage-label">Storage: 4.2 / 20 GB</span>
        <div class="res-storage-bar"><div class="res-storage-fill" style="width:21%"></div></div>
      </div>
    </div>

    <div class="res-body">
      <div class="res-main">
        <div class="res-categories stagger-reveal">
          <div v-for="cat in categories" :key="cat.name" class="res-cat" :class="{ 'res-cat--active': activeCat === cat.name }" @click="activeCat = cat.name">
            <div class="res-cat-icon">{{ cat.icon }}</div>
            <div class="res-cat-name">{{ cat.name }}</div>
            <div class="res-cat-count">{{ cat.count }} items</div>
          </div>
        </div>

        <div class="res-upload" @dragover.prevent @drop.prevent>
          <svg class="w-8 h-8 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
          <p>拖拽文件到此处上传，或点击浏览</p>
        </div>

        <div class="res-section-label">GALLERY</div>
        <div class="res-gallery">
          <div v-for="i in 8" :key="i" class="res-item">
            <div class="res-item-preview" :style="{ background: `hsl(${i * 40}, 30%, 12%)` }">
              <span class="res-item-type">{{ ['IMG', 'TXT', 'REF', 'IMG', 'TXT', 'AUD', 'IMG', 'TPL'][i-1] }}</span>
            </div>
            <div class="res-item-name">asset_{{ String(i).padStart(3, '0') }}.{{ ['png', 'md', 'pdf', 'jpg', 'txt', 'mp3', 'png', 'html'][i-1] }}</div>
          </div>
        </div>
      </div>

      <div class="res-panel">
        <div class="res-panel-section">
          <div class="res-section-label">AI ASSET INSIGHT</div>
          <div class="res-insight">
            <span class="neon-pulse" style="width:6px;height:6px;"></span>
            <p>检测到 3 张角色肖像可用于自动生成角色描述。建议为"凯"补充义体细节参考图。</p>
          </div>
          <button class="res-insight-btn">Auto-Tag All Assets</button>
        </div>

        <div class="res-panel-section">
          <div class="res-section-label">TAG CLOUD</div>
          <div class="res-tags">
            <span v-for="t in tags" :key="t.name" class="res-tag" :style="{ fontSize: t.size + 'px' }">{{ t.name }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const activeCat = ref('Images')
const categories = [
  { name: 'Images', icon: '🖼️', count: 24 },
  { name: 'Audio', icon: '🎵', count: 8 },
  { name: 'Text', icon: '📄', count: 45 },
  { name: 'Templates', icon: '📋', count: 12 },
]

const tags = [
  { name: '赛博朋克', size: 16 }, { name: '角色', size: 14 }, { name: '场景', size: 18 },
  { name: '义体', size: 12 }, { name: '霓虹', size: 15 }, { name: '地图', size: 11 },
  { name: '音效', size: 13 }, { name: '参考', size: 14 }, { name: '科技', size: 12 },
]
</script>

<style scoped>
.res-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.res-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px; }
.res-title { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.res-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.res-storage { text-align: right; }
.res-storage-label { font-size: 12px; color: var(--ar-text-muted); }
.res-storage-bar { width: 160px; height: 4px; background: rgba(77,70,50,0.1); border-radius: 2px; margin-top: 6px; }
.res-storage-fill { height: 100%; background: var(--ar-secondary); border-radius: 2px; }
.res-body { display: grid; grid-template-columns: 1fr 280px; gap: 24px; }
.res-main { display: flex; flex-direction: column; gap: 20px; }
.res-categories { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.res-cat { background: var(--ar-bg-surface); border-radius: 4px; padding: 16px; cursor: pointer; transition: all 0.15s; text-align: center; }
.res-cat:hover { background: var(--ar-bg-elevated); }
.res-cat--active { border: 1px solid var(--ar-primary); box-shadow: 0 0 20px rgba(250,204,21,0.06); }
.res-cat-icon { font-size: 24px; margin-bottom: 8px; }
.res-cat-name { font-size: 14px; font-weight: 600; color: var(--ar-text-primary); }
.res-cat-count { font-size: 11px; color: var(--ar-text-muted); margin-top: 2px; }
.res-upload { border: 1px dashed rgba(77,70,50,0.25); border-radius: 4px; padding: 32px; text-align: center; color: var(--ar-text-muted); font-size: 14px; cursor: pointer; transition: all 0.15s; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.res-upload:hover { border-color: var(--ar-primary); }
.res-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 12px; }
.res-gallery { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.res-item { cursor: pointer; transition: all 0.15s; }
.res-item:hover { transform: translateY(-2px); }
.res-item-preview { height: 100px; border-radius: 4px; display: flex; align-items: center; justify-content: center; }
.res-item-type { font-size: 12px; font-weight: 700; color: var(--ar-text-muted); letter-spacing: 0.1em; }
.res-item-name { font-size: 11px; color: var(--ar-text-secondary); margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.res-panel { display: flex; flex-direction: column; gap: 16px; }
.res-panel-section { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.res-insight { display: flex; align-items: flex-start; gap: 8px; font-size: 13px; color: var(--ar-text-secondary); line-height: 1.5; margin-bottom: 12px; }
.res-insight-btn { width: 100%; padding: 10px; border: 1px solid rgba(77,70,50,0.2); border-radius: 4px; background: transparent; color: var(--ar-secondary); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; }
.res-insight-btn:hover { background: var(--ar-secondary-muted); }
.res-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.res-tag { color: var(--ar-text-secondary); cursor: pointer; transition: color 0.15s; }
.res-tag:hover { color: var(--ar-primary); }
</style>
