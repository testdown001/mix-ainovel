<template>
  <div class="cat-root">
    <div class="cat-banner">
      <span class="neon-pulse" style="width:6px;height:6px;"></span>
      <span>AI 建议：尝试将 "记忆碎片" 与 "时间循环" 主题结合，可能产生高冲突剧情</span>
    </div>

    <div class="cat-header">
      <h1 class="cat-title">AI CATALYST</h1>
      <p class="cat-subtitle">创意催化引擎 · 从灵感种子到完整剧情</p>
    </div>

    <div class="cat-body">
      <div class="cat-main">
        <div class="cat-inputs">
          <div class="cat-input-group">
            <label class="cat-label">THEMATIC ANCHOR</label>
            <textarea class="cat-textarea" v-model="thematicAnchor" placeholder="输入你想探索的主题核心..."></textarea>
          </div>
          <div class="cat-input-group">
            <label class="cat-label">CHARACTER ARCHETYPE</label>
            <div class="cat-chips">
              <button v-for="a in archetypes" :key="a" class="cat-chip" :class="{ 'cat-chip--active': selectedArchetypes.includes(a) }" @click="toggleArchetype(a)">{{ a }}</button>
            </div>
          </div>
          <button class="cat-generate-btn" @click="generate">
            <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/></svg>
            Generate Plot Branches
          </button>
        </div>

        <div class="cat-results" v-if="branches.length">
          <div class="cat-section-label">GENERATED PLOT BRANCHES</div>
          <div class="cat-branches">
            <div v-for="b in branches" :key="b.id" class="cat-branch">
              <div class="cat-branch-header">
                <span class="cat-branch-tag">Branch {{ b.id }}</span>
                <span class="cat-branch-score">
                  <span class="neon-pulse" style="width:5px;height:5px;"></span>
                  Score: {{ b.score }}
                </span>
              </div>
              <h3 class="cat-branch-title">{{ b.title }}</h3>
              <p class="cat-branch-desc">{{ b.desc }}</p>
              <div class="cat-branch-actions">
                <button class="cat-action">采用此方案</button>
                <button class="cat-action cat-action--sec">继续推演</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="cat-panel">
        <div class="cat-panel-section">
          <div class="cat-section-label">INFERENCE PARAMETERS</div>
          <div class="cat-param"><span>Chaos Factor</span><input type="range" min="0" max="100" v-model="chaosFactor" class="neon-slider" /><span class="cat-param-val">{{ chaosFactor }}%</span></div>
          <div class="cat-param"><span>Emotional Depth</span><input type="range" min="0" max="100" v-model="emotionalDepth" class="neon-slider" /><span class="cat-param-val">{{ emotionalDepth }}%</span></div>
          <div class="cat-param"><span>Conflict Density</span><input type="range" min="0" max="100" v-model="conflictDensity" class="neon-slider" /><span class="cat-param-val">{{ conflictDensity }}%</span></div>
        </div>

        <div class="cat-panel-section">
          <div class="cat-section-label">GENERATION HISTORY</div>
          <div class="cat-history">
            <div class="cat-hist-item" v-for="h in history" :key="h">
              <span class="cat-hist-dot"></span>
              {{ h }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'

const thematicAnchor = ref('在一个记忆可以被编辑的世界，什么才是真实的自我？')
const chaosFactor = ref(42)
const emotionalDepth = ref(75)
const conflictDensity = ref(60)

const archetypes = ['反英雄', '智者导师', '堕落天使', '局外人', '复仇者', '守护者']
const selectedArchetypes = reactive(['反英雄', '堕落天使'])

const toggleArchetype = (a: string) => {
  const idx = selectedArchetypes.indexOf(a)
  if (idx >= 0) selectedArchetypes.splice(idx, 1)
  else selectedArchetypes.push(a)
}

const branches = reactive([
  { id: 1, title: '记忆商人的阴谋', desc: '凯发现城市中存在一个地下记忆交易网络，而他的导师萨拉正是这个网络的创始人。当他试图揭露真相时，却发现自己的记忆也被篡改过...', score: 94 },
  { id: 2, title: '数字灵魂的觉醒', desc: '一个被删除的AI人格在虚拟空间中重生，它声称拥有凯已故妹妹的全部记忆。凯必须在情感与理性之间做出抉择...', score: 87 },
  { id: 3, title: '时间环的崩塌', desc: '城市的记忆编辑系统出现了时间回环bug，同一段记忆不断被覆写。凯意识到每次循环都在改变现实的基础结构...', score: 81 },
])

const generate = () => { /* mock */ }

const history = ['2 小时前 · "赛博朋克 + 哲学" 生成', '昨天 · "AI觉醒" 主题推演', '3天前 · "记忆伦理" 分支探索']
</script>

<style scoped>
.cat-root { min-height: calc(100vh - 56px); background: var(--ar-bg-base); padding: 32px; }
.cat-banner { display: flex; align-items: center; gap: 8px; padding: 10px 16px; background: linear-gradient(90deg, rgba(74,222,128,0.08), transparent); border-radius: 4px; font-size: 13px; color: var(--ar-secondary); margin-bottom: 24px; border-left: 3px solid var(--ar-secondary); }
.cat-header { margin-bottom: 28px; }
.cat-title { font-family: var(--ar-font-display); font-size: 28px; font-weight: 700; color: var(--ar-primary); letter-spacing: 0.04em; }
.cat-subtitle { font-size: 13px; color: var(--ar-text-muted); margin-top: 4px; }
.cat-body { display: grid; grid-template-columns: 1fr 300px; gap: 24px; }
.cat-main { display: flex; flex-direction: column; gap: 24px; }
.cat-inputs { background: var(--ar-bg-surface); border-radius: 4px; padding: 24px; }
.cat-input-group { margin-bottom: 20px; }
.cat-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; display: block; margin-bottom: 8px; }
.cat-textarea { width: 100%; min-height: 80px; background: var(--ar-bg-elevated); border: none; border-radius: 4px; padding: 12px 16px; font-family: var(--ar-font-ui); font-size: 14px; color: var(--ar-text-primary); resize: vertical; outline: none; }
.cat-textarea:focus { box-shadow: 0 0 0 2px rgba(74,222,128,0.2); }
.cat-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.cat-chip { padding: 6px 14px; border-radius: 2px; border: 1px solid rgba(77,70,50,0.2); background: transparent; color: var(--ar-text-secondary); font-size: 13px; cursor: pointer; transition: all 0.15s; }
.cat-chip--active { background: var(--ar-primary); color: var(--ar-on-primary); border-color: var(--ar-primary); }
.cat-generate-btn { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 14px; border: none; border-radius: 4px; background: linear-gradient(135deg, var(--ar-primary-dim, #eec200), var(--ar-primary)); color: var(--ar-on-primary); font-size: 15px; font-weight: 700; cursor: pointer; transition: all 0.15s; }
.cat-generate-btn:hover { box-shadow: 0 0 24px rgba(250,204,21,0.35); }
.cat-section-label { font-size: 10px; font-weight: 600; letter-spacing: 0.1em; color: var(--ar-text-muted); text-transform: uppercase; margin-bottom: 16px; }
.cat-branches { display: flex; flex-direction: column; gap: 16px; }
.cat-branch { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; transition: all 0.15s; }
.cat-branch:hover { box-shadow: 0 0 30px rgba(255,236,185,0.06); }
.cat-branch-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.cat-branch-tag { font-size: 10px; font-weight: 600; letter-spacing: 0.08em; color: var(--ar-primary); text-transform: uppercase; padding: 3px 10px; background: var(--ar-primary-muted); border-radius: 2px; }
.cat-branch-score { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ar-secondary); font-weight: 600; }
.cat-branch-title { font-family: var(--ar-font-display); font-size: 18px; font-weight: 700; color: var(--ar-text-primary); margin-bottom: 8px; }
.cat-branch-desc { font-size: 14px; color: var(--ar-text-secondary); line-height: 1.6; margin-bottom: 14px; }
.cat-branch-actions { display: flex; gap: 8px; }
.cat-action { padding: 8px 16px; border-radius: 4px; border: none; background: var(--ar-primary); color: var(--ar-on-primary); font-size: 13px; font-weight: 600; cursor: pointer; }
.cat-action--sec { background: transparent; border: 1px solid rgba(77,70,50,0.3); color: var(--ar-text-primary); }
.cat-panel { display: flex; flex-direction: column; gap: 16px; }
.cat-panel-section { background: var(--ar-bg-surface); border-radius: 4px; padding: 20px; }
.cat-param { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--ar-text-secondary); margin-bottom: 12px; }
.cat-param span:first-child { min-width: 100px; }
.cat-param-val { font-family: var(--ar-font-display); font-weight: 700; color: var(--ar-primary); min-width: 40px; text-align: right; }
.cat-history { display: flex; flex-direction: column; gap: 8px; }
.cat-hist-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--ar-text-muted); }
.cat-hist-dot { width: 4px; height: 4px; border-radius: 50%; background: var(--ar-text-muted); }
.neon-slider { flex: 1; -webkit-appearance: none; height: 4px; border-radius: 2px; background: var(--ar-bg-highlight); outline: none; }
.neon-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 14px; height: 14px; border-radius: 50%; background: var(--ar-primary); cursor: pointer; box-shadow: 0 0 8px rgba(250,204,21,0.4); }
</style>
