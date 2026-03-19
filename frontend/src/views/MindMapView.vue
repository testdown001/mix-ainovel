<template>
  <div class="mm-root">
    <div class="mm-toolbar">
      <h1 class="mm-title">MIND MAP</h1>
      <div class="mm-tools">
        <button class="mm-tool" :class="{ 'mm-tool--active': activeTool === 'select' }" @click="activeTool = 'select'">Select</button>
        <button class="mm-tool" :class="{ 'mm-tool--active': activeTool === 'add' }" @click="activeTool = 'add'">+ Node</button>
        <button class="mm-tool" :class="{ 'mm-tool--active': activeTool === 'connect' }" @click="activeTool = 'connect'">Connect</button>
        <button class="mm-tool">Export</button>
      </div>
      <button class="mm-ai-btn">
        <span class="neon-pulse" style="width:6px;height:6px;"></span>
        AI Enhance
      </button>
    </div>

    <div class="mm-body">
      <div class="mm-canvas" @click="selectNode(null)">
        <div v-for="n in nodes" :key="n.id" class="mm-node" :class="'mm-node--' + n.type + (selectedNode === n.id ? ' mm-node--selected' : '')" :style="{ left: n.x + 'px', top: n.y + 'px' }" @click.stop="selectNode(n.id)">
          {{ n.label }}
        </div>
        <svg class="mm-connections" viewBox="0 0 800 500">
          <line v-for="c in connections" :key="c.from + '-' + c.to" :x1="getNode(c.from)!.x + 60" :y1="getNode(c.from)!.y + 20" :x2="getNode(c.to)!.x + 60" :y2="getNode(c.to)!.y + 20" stroke="rgba(77,70,50,0.3)" stroke-width="1" />
        </svg>
      </div>

      <div class="mm-inspector" v-if="inspectedNode">
        <div class="mm-section-label">NODE INSPECTOR</div>
        <div class="mm-insp-field">
          <label>Name</label>
          <input :value="inspectedNode.label" class="mm-insp-input" />
        </div>
        <div class="mm-insp-field">
          <label>Type</label>
          <select :value="inspectedNode.type" class="mm-insp-input">
            <option value="character">Character</option>
            <option value="event">Event</option>
            <option value="setting">Setting</option>
          </select>
        </div>
        <div class="mm-insp-field">
          <label>Notes</label>
          <textarea class="mm-insp-textarea" placeholder="添加笔记..."></textarea>
        </div>

        <div class="mm-section-label" style="margin-top:20px;">AI SUGGESTIONS</div>
        <div class="mm-ai-suggestions">
          <div class="mm-suggestion">
            <span class="neon-pulse" style="width:5px;height:5px;"></span>
            建议添加"凯的过去"子节点以丰富角色深度
          </div>
          <div class="mm-suggestion">
            <span class="neon-pulse" style="width:5px;height:5px;"></span>
            "霓虹城"与"萨拉"之间可能存在隐藏关联
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const activeTool = ref('select')
const selectedNode = ref<number | null>(1)

const nodes = [
  { id: 1, label: '凯 (Kai)', type: 'character', x: 120, y: 80 },
  { id: 2, label: '萨拉 (Sara)', type: 'character', x: 350, y: 60 },
  { id: 3, label: '霓虹城', type: 'setting', x: 220, y: 220 },
  { id: 4, label: '记忆编辑事件', type: 'event', x: 500, y: 150 },
  { id: 5, label: '博士', type: 'character', x: 550, y: 300 },
  { id: 6, label: '地下实验室', type: 'setting', x: 380, y: 350 },
]

const connections = [
  { from: 1, to: 2 }, { from: 1, to: 3 }, { from: 2, to: 4 },
  { from: 3, to: 6 }, { from: 4, to: 5 }, { from: 5, to: 6 },
]

const getNode = (id: number) => nodes.find(n => n.id === id)
const inspectedNode = computed(() => selectedNode.value ? getNode(selectedNode.value) : null)
const selectNode = (id: number | null) => { selectedNode.value = id }
</script>

<style scoped>
.mm-root { height: calc(100vh - 56px); background: var(--ar-bg-base); display: flex; flex-direction: column; }
.mm-toolbar { display: flex; align-items: center; gap: 16px; padding: 12px 24px; background: var(--ar-bg-surface); }
.mm-title { font-family: var(--ar-font-display); font-size: 18px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.mm-tools { display: flex; gap: 4px; margin-left: 24px; }
.mm-tool { padding: 6px 14px; border-radius: 4px; border: 1px solid rgba(77,70,50,0.15); background: transparent; color: var(--ar-text-secondary); font-size: 13px; cursor: pointer; transition: all 0.15s; }
.mm-tool--active { background: var(--ar-primary); color: var(--ar-on-primary); border-color: var(--ar-primary); }
.mm-ai-btn { display: flex; align-items: center; gap: 6px; margin-left: auto; padding: 6px 14px; border: 1px solid rgba(74,222,128,0.3); border-radius: 4px; background: transparent; color: var(--ar-secondary); font-size: 13px; font-weight: 600; cursor: pointer; }
.mm-body { flex: 1; display: flex; overflow: hidden; }
.mm-canvas { flex: 1; position: relative; overflow: auto; }
.mm-connections { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.mm-node { position: absolute; padding: 10px 20px; border-radius: 4px; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.15s; white-space: nowrap; z-index: 1; }
.mm-node--character { background: var(--ar-bg-elevated); color: var(--ar-primary); border: 1px solid rgba(250,204,21,0.2); }
.mm-node--event { background: var(--ar-bg-elevated); color: var(--ar-secondary); border: 1px solid rgba(74,222,128,0.2); }
.mm-node--setting { background: var(--ar-bg-elevated); color: var(--ar-text-primary); border: 1px solid rgba(77,70,50,0.2); }
.mm-node--selected { box-shadow: 0 0 16px rgba(250,204,21,0.15); border-color: var(--ar-primary); }
.mm-inspector { width: 280px; background: var(--ar-bg-surface); padding: 20px; overflow-y: auto; flex-shrink: 0; }
.mm-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 12px; }
.mm-insp-field { margin-bottom: 14px; }
.mm-insp-field label { display: block; font-size: 12px; color: var(--ar-text-muted); margin-bottom: 4px; }
.mm-insp-input { width: 100%; padding: 8px 12px; background: var(--ar-bg-elevated); border: none; border-radius: 4px; color: var(--ar-text-primary); font-size: 13px; outline: none; }
.mm-insp-textarea { width: 100%; min-height: 60px; padding: 8px 12px; background: var(--ar-bg-elevated); border: none; border-radius: 4px; color: var(--ar-text-primary); font-size: 13px; resize: vertical; outline: none; font-family: var(--ar-font-ui); }
.mm-ai-suggestions { display: flex; flex-direction: column; gap: 8px; }
.mm-suggestion { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; color: var(--ar-text-secondary); line-height: 1.5; padding: 8px; background: var(--ar-bg-elevated); border-radius: 4px; }
</style>
