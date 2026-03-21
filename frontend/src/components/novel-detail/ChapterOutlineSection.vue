<!-- AIMETA P=章节大纲区_大纲展示|R=大纲列表_重新生成|NR=不含编辑功能|E=component:ChapterOutlineSection|X=ui|A=大纲组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-5">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-xl font-bold text-white">章节大纲</h2>
        <p class="text-sm text-[#666] mt-0.5">故事结构与章节节奏一目了然</p>
      </div>
      <div v-if="editable" class="flex items-center gap-2 flex-wrap">
        <template v-if="!batchMode">
          <!-- 生成大纲（新增/续写） -->
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-[#2ED573] bg-[rgba(46,213,115,0.08)] hover:bg-[rgba(46,213,115,0.14)] rounded-lg transition-colors"
            :disabled="regenerating"
            @click="handleGenerateFresh"
          >
            <svg v-if="regenerating && freshGenerating" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <svg v-else class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
            {{ generateFreshText }}
          </button>
          <!-- 重新生成未完成大纲 -->
          <button
            v-if="uncompletedCount > 0"
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-[#FFE500] bg-[rgba(255,229,0,0.06)] hover:bg-[rgba(255,229,0,0.12)] rounded-lg transition-colors"
            :disabled="regenerating"
            @click="handleRegenerateUncompleted"
          >
            <svg v-if="regenerating && !freshGenerating" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ regenerating && !freshGenerating ? '生成中...' : `重新生成未完成大纲 (${uncompletedCount})` }}
          </button>
          <button
            v-if="regeneratedNumbers.size > 0"
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-[#06B6D4] bg-[rgba(6,182,212,0.08)] hover:bg-[rgba(6,182,212,0.14)] rounded-lg transition-colors"
            @click="clearRegenerated"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            清除新生成标记
          </button>
          <button
            v-if="unpredictedCount > 0"
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-[#06B6D4] bg-[rgba(6,182,212,0.08)] hover:bg-[rgba(6,182,212,0.14)] rounded-lg transition-colors"
            :disabled="regenerating || predictGenerating"
            @click="handleBatchPredict"
          >
            <svg v-if="predictGenerating" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            {{ predictGenerating ? (predictProgress ? `推演中 (${predictProgress.completed}/${predictProgress.total})` : '推演中...') : `一键推演 (${unpredictedCount})` }}
          </button>
          <button
            v-if="uncompletedCount > 0"
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-[#A855F7] bg-[rgba(168,85,247,0.08)] hover:bg-[rgba(168,85,247,0.14)] rounded-lg transition-colors"
            :disabled="regenerating || batchGenerating"
            @click="handleBatchGenerate"
          >
            <svg v-if="batchGenerating" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            {{ batchGenerating ? '连续生成中...' : `连续生成 (${uncompletedCount})` }}
          </button>
          <button
            v-if="uncompletedCount > 0"
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-[#FF4757] bg-[rgba(255,71,87,0.08)] hover:bg-[rgba(255,71,87,0.14)] rounded-lg transition-colors"
            @click="enterBatchMode"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L6.382 6H4a1 1 0 000 2h.5l.5 8.5A2 2 0 007 18.5h6a2 2 0 002-2L15.5 8H16a1 1 0 100-2h-2.382l-1.724-3.447A1 1 0 0011 2H9zm-.5 4l1-2h1l1 2h-3zM8.5 10a.5.5 0 011 0v4a.5.5 0 01-1 0v-4zm3 0a.5.5 0 011 0v4a.5.5 0 01-1 0v-4z" clip-rule="evenodd" />
            </svg>
            批量删除
          </button>
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-[#FFE500] bg-[rgba(255,229,0,0.08)] hover:bg-[rgba(255,229,0,0.14)] rounded-lg"
            @click="$emit('add')"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
            新增章节
          </button>
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm text-[#555] hover:text-[#FFE500] transition-colors"
            @click="emitEdit('chapter_outline', '章节大纲', outline)"
          >
            <svg class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
              <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
            </svg>
            编辑大纲
          </button>
        </template>
        <!-- 批量删除模式工具栏 -->
        <template v-else>
          <label class="flex items-center gap-2 px-3 py-2 text-sm text-[#888] cursor-pointer select-none">
            <input
              type="checkbox"
              class="h-4 w-4 rounded border-[#2A2A2A] text-red-600 focus:ring-red-500"
              :checked="isAllUncompletedSelected"
              @change="toggleSelectAll"
            />
            全选未完成 ({{ uncompletedCount }})
          </label>
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-white bg-[#FF4757] hover:bg-[rgba(255,71,87,0.85)] rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="selectedNumbers.size === 0 || deleting"
            @click="handleDeleteSelected"
          >
            <svg v-if="deleting" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <svg v-else class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L6.382 6H4a1 1 0 000 2h.5l.5 8.5A2 2 0 007 18.5h6a2 2 0 002-2L15.5 8H16a1 1 0 100-2h-2.382l-1.724-3.447A1 1 0 0011 2H9zm-.5 4l1-2h1l1 2h-3zM8.5 10a.5.5 0 011 0v4a.5.5 0 01-1 0v-4zm3 0a.5.5 0 011 0v4a.5.5 0 01-1 0v-4z" clip-rule="evenodd" />
            </svg>
            {{ deleting ? '删除中...' : `删除选中 (${selectedNumbers.size})` }}
          </button>
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-[#888] bg-[#1C1C1C] hover:bg-[#222] rounded-lg transition-colors"
            :disabled="deleting"
            @click="exitBatchMode"
          >
            取消
          </button>
        </template>
      </div>
    </div>

    <!-- 生成结果提示 -->
    <div
      v-if="regenerateResult"
      class="flex items-start gap-3 px-4 py-3 rounded-lg text-sm"
      :class="regenerateResult.updated === regenerateResult.total
        ? 'bg-[rgba(46,213,115,0.06)] text-[#2ED573] border border-[rgba(46,213,115,0.2)]'
        : 'bg-[rgba(255,229,0,0.06)] text-[#FFE500] border border-[rgba(255,229,0,0.2)]'"
    >
      <svg class="h-5 w-5 flex-shrink-0 mt-0.5" viewBox="0 0 20 20" fill="currentColor">
        <path v-if="regenerateResult.updated === regenerateResult.total" fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
        <path v-else fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
      </svg>
      <span>
        已重新生成 {{ regenerateResult.updated }}/{{ regenerateResult.total }} 个章节大纲。
        <template v-if="regenerateResult.updated < regenerateResult.total">
          有 {{ regenerateResult.total - regenerateResult.updated }} 个章节未能生成，可尝试再次重新生成。
        </template>
        带有 <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-[rgba(6,182,212,0.15)] text-[#06B6D4]">新</span> 标记的是本次更新的大纲。
      </span>
      <button
        type="button"
        class="ml-auto flex-shrink-0 text-current opacity-60 hover:opacity-100"
        @click="regenerateResult = null"
      >
        <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
      </button>
    </div>

    <ol class="relative border-l border-[#2A2A2A] ml-3 space-y-6">
      <li
        v-for="chapter in sortedOutline"
        :key="chapter.chapter_number"
        class="ml-6"
      >
        <span
          class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold"
          :class="isCompleted(chapter.chapter_number) ? 'bg-[#2ED573] text-black' : 'bg-[#FFE500] text-black'"
        >
          <template v-if="isCompleted(chapter.chapter_number)">
            <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </template>
          <template v-else>{{ chapter.chapter_number }}</template>
        </span>
        <div
          class="rounded-2xl border p-5 transition-all duration-300"
          :class="[
            isCompleted(chapter.chapter_number)
              ? 'bg-[rgba(46,213,115,0.04)] border-[rgba(46,213,115,0.18)]'
              : isSelected(chapter.chapter_number)
                ? 'bg-[rgba(255,71,87,0.04)] border-[rgba(255,71,87,0.25)] ring-1 ring-[rgba(255,71,87,0.15)]'
                : isRegenerated(chapter.chapter_number)
                  ? 'bg-[rgba(6,182,212,0.04)] border-[rgba(6,182,212,0.25)] ring-1 ring-[rgba(6,182,212,0.15)]'
                  : 'bg-[#141414] border-[#2A2A2A]'
          ]"
        >
          <div class="flex items-center justify-between gap-4">
            <div class="flex items-center gap-2 min-w-0">
              <input
                v-if="batchMode && !isCompleted(chapter.chapter_number)"
                type="checkbox"
                class="h-4 w-4 flex-shrink-0 rounded border-[#2A2A2A] text-red-600 focus:ring-red-500 cursor-pointer"
                :checked="isSelected(chapter.chapter_number)"
                @change="toggleSelect(chapter.chapter_number)"
              />
              <h3 class="text-base font-semibold text-white truncate">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
              <span
                v-if="isCompleted(chapter.chapter_number)"
                class="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[rgba(46,213,115,0.12)] text-[#2ED573]"
              >
                已完成
              </span>
              <span
                v-if="isRegenerated(chapter.chapter_number)"
                class="flex-shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-[rgba(6,182,212,0.12)] text-[#06B6D4] animate-pulse"
              >
                <svg class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zM12 2a1 1 0 01.967.744L14.146 7.2 17.5 9.134a1 1 0 010 1.732l-3.354 1.935-1.18 4.455a1 1 0 01-1.933 0L9.854 12.8 6.5 10.866a1 1 0 010-1.732l3.354-1.935 1.18-4.455A1 1 0 0112 2z" clip-rule="evenodd" />
                </svg>
                新
              </span>
              <span
                v-if="chapter.metadata?.prediction"
                class="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[rgba(168,85,247,0.12)] text-[#A855F7]"
              >
                已推演
              </span>
              <span
                v-else
                class="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[#1C1C1C] text-[#555]"
              >
                未推演
              </span>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <button
                v-if="editable && !isCompleted(chapter.chapter_number)"
                type="button"
                class="p-1.5 text-[#555] hover:text-[#FFE500] hover:bg-[rgba(255,229,0,0.08)] rounded-lg transition-colors"
                title="重新生成此章大纲"
                :disabled="regenerating"
                @click="handleRegenerateSingle(chapter.chapter_number)"
              >
                <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <span class="text-xs text-[#444]">#{{ chapter.chapter_number }}</span>
            </div>
          </div>
          <p class="mt-3 text-sm text-[#888] leading-6 whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>

          <!-- 推演标签和展开按钮 -->
          <div v-if="chapter.metadata?.prediction" class="mt-3">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span v-if="chapter.metadata.prediction.cool_points?.length" class="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold text-black" style="background-color: #FFE500;">爽</span>
              <span v-if="chapter.metadata.prediction.foreshadowing_hooks?.length" class="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold text-white" style="background-color: #3B82F6;">伏</span>
              <span v-if="chapter.metadata.prediction.foreshadowing_targets?.length" class="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold text-black" style="background-color: #2ED573;">收</span>
              <span v-if="getLastBeatType(chapter.metadata.prediction) === 'payoff'" class="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold text-white" style="background-color: #FF4757;">爆</span>
              <button
                type="button"
                class="text-xs text-[#FFE500] hover:text-[#FFC300] font-medium ml-1 transition-colors"
                @click="togglePrediction(chapter.chapter_number)"
              >
                {{ expandedPrediction === chapter.chapter_number ? '收起推演' : '查看推演' }}
              </button>
            </div>

            <!-- 推演详情展开区 -->
            <div v-if="expandedPrediction === chapter.chapter_number" class="mt-3 space-y-2 animate-slideDown">
              <div v-if="chapter.metadata.prediction.key_points?.length" class="bg-[rgba(6,182,212,0.05)] border border-[rgba(6,182,212,0.15)] rounded-lg p-3">
                <h5 class="text-xs font-semibold text-[#06B6D4] mb-1.5">章节要点</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.key_points" :key="i" class="text-xs text-[#88CFDA] flex gap-1.5">
                    <span class="shrink-0">•</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.cool_points?.length" class="bg-[rgba(255,229,0,0.04)] border border-[rgba(255,229,0,0.15)] rounded-lg p-3">
                <h5 class="text-xs font-semibold text-[#FFE500] mb-1.5">✨ 爽点设计</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.cool_points" :key="i" class="text-xs text-[#D4BA00] flex gap-1.5">
                    <span class="shrink-0">⚡</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.foreshadowing_hooks?.length" class="bg-[rgba(99,102,241,0.05)] border border-[rgba(99,102,241,0.15)] rounded-lg p-3">
                <h5 class="text-xs font-semibold text-[#818CF8] mb-1.5">🪝 伏笔/钩子</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.foreshadowing_hooks" :key="i" class="text-xs text-[#7C83E0] flex gap-1.5">
                    <span class="shrink-0">🪝</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.foreshadowing_targets?.length" class="bg-[rgba(46,213,115,0.04)] border border-[rgba(46,213,115,0.15)] rounded-lg p-3">
                <h5 class="text-xs font-semibold text-[#2ED573] mb-1.5">🎯 需回收伏笔</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.foreshadowing_targets" :key="i" class="text-xs text-[#27BE65] flex gap-1.5">
                    <span class="shrink-0">🎯</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.limitations?.length" class="bg-[#1C1C1C] border border-[#2A2A2A] rounded-lg p-3">
                <h5 class="text-xs font-semibold text-[#bbb] mb-1.5">⚠️ 章节限制</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.limitations" :key="i" class="text-xs text-[#888] flex gap-1.5">
                    <span class="shrink-0">⚠</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.beats?.length" class="bg-[rgba(168,85,247,0.04)] border border-[rgba(168,85,247,0.15)] rounded-lg p-3">
                <h5 class="text-xs font-semibold text-[#A855F7] mb-1.5">节拍编排</h5>
                <div class="space-y-1">
                  <div v-for="(beat, i) in chapter.metadata.prediction.beats" :key="i" class="flex items-start gap-1.5 text-xs">
                    <span class="shrink-0 w-4 h-4 rounded-full text-[9px] flex items-center justify-center text-white font-medium"
                          :style="{ backgroundColor: beatColorMap[beat.type] || '#6B7280' }">{{ i + 1 }}</span>
                    <div>
                      <span class="font-medium" :style="{ color: beatColorMap[beat.type] || '#888' }">{{ beatLabelMap[beat.type] || beat.type }}</span>
                      <span class="text-[#888] ml-1">{{ beat.content }}</span>
                      <span class="text-[#555] ml-1">({{ beat.emotion }})</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 场景编辑器 -->
          <SceneEditor
            :project-id="projectId"
            :chapter-number="chapter.chapter_number"
            :initial-scenes="chapter.metadata?.scenes || []"
          />
        </div>
      </li>
      <li v-if="!sortedOutline.length" class="ml-6 text-[#555] text-sm">暂无章节大纲</li>
    </ol>
  </div>

  <!-- 章节数量输入弹窗 -->
  <teleport to="body">
    <transition
      enter-active-class="transition-all duration-200"
      leave-active-class="transition-all duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="modal.show"
        class="fixed inset-0 z-[999] flex items-center justify-center p-4"
        style="background: rgba(0,0,0,0.75);"
        @click.self="modal.show = false"
      >
        <div
          class="w-full max-w-md bg-[#141414] border border-[#2A2A2A] rounded-2xl shadow-2xl overflow-hidden"
          @click.stop
        >
          <!-- Header -->
          <div class="px-6 pt-6 pb-4 border-b border-[#1C1C1C]">
            <div class="flex items-center gap-3 mb-1">
              <div class="w-9 h-9 rounded-xl bg-[#FFE500]/10 flex items-center justify-center flex-shrink-0">
                <svg class="w-5 h-5 text-[#FFE500]" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
                </svg>
              </div>
              <div>
                <h3 class="text-base font-bold text-white">{{ modal.title }}</h3>
                <p class="text-xs text-[#888] mt-0.5">{{ modal.subtitle }}</p>
              </div>
            </div>
          </div>

          <!-- Body -->
          <div class="px-6 py-5 space-y-5">
            <!-- Number input -->
            <div>
              <label class="block text-sm font-medium text-[#CCCCCC] mb-2">{{ modal.inputLabel }}</label>
              <input
                type="number"
                v-model.number="modal.value"
                :min="1"
                :max="modal.max"
                class="w-full bg-[#0A0A0A] border border-[#2A2A2A] rounded-xl px-4 py-3 text-white text-base font-semibold focus:outline-none focus:border-[#FFE500] transition-colors"
                @keydown.enter="handleModalConfirm"
              />
              <p v-if="modal.error" class="mt-2 text-xs text-[#FF4757]">{{ modal.error }}</p>
            </div>

            <!-- Quick picks -->
            <div>
              <p class="text-xs text-[#555] mb-2">快速选择</p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="q in modal.quickPicks"
                  :key="q.value"
                  type="button"
                  class="px-3 py-1.5 rounded-lg text-sm font-medium border transition-all"
                  :class="modal.value === q.value
                    ? 'bg-[#FFE500] text-black border-[#FFE500]'
                    : 'bg-transparent text-[#888] border-[#2A2A2A] hover:border-[#FFE500]/40 hover:text-[#FFE500]'"
                  @click="modal.value = q.value"
                >
                  {{ q.label }}
                </button>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-6 pb-6 flex gap-3 justify-end">
            <button
              type="button"
              class="px-5 py-2.5 rounded-xl text-sm font-medium text-[#888] bg-[#1C1C1C] hover:bg-[#222] transition-colors"
              @click="modal.show = false"
            >
              取消
            </button>
            <button
              type="button"
              class="px-5 py-2.5 rounded-xl text-sm font-bold text-black bg-[#FFE500] hover:bg-[#FFC300] transition-colors"
              @click="handleModalConfirm"
            >
              确认生成
            </button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import SceneEditor from './SceneEditor.vue'

const route = useRoute()
const projectId = route.params.id as string

interface ChapterPredictionData {
  key_points?: string[]
  cool_points?: string[]
  foreshadowing_hooks?: string[]
  foreshadowing_targets?: string[]
  limitations?: string[]
  beats?: Array<{ type: string; content: string; emotion: string }>
}

interface OutlineItem {
  chapter_number: number
  title: string
  summary: string
  metadata?: { prediction?: ChapterPredictionData; scenes?: any[] } | null
}

interface ChapterItem {
  chapter_number: number
  generation_status?: string
}

const props = defineProps<{
  outline: OutlineItem[]
  chapters?: ChapterItem[]
  editable?: boolean
}>()

const regenerating = ref(false)
const freshGenerating = ref(false)
const regeneratedNumbers = ref<Set<number>>(new Set())
const regenerateResult = ref<{ updated: number; total: number } | null>(null)
const batchMode = ref(false)
const batchGenerating = ref(false)
const predictGenerating = ref(false)
const predictProgress = ref<{ total: number; completed: number; failed: number } | null>(null)
const selectedNumbers = ref<Set<number>>(new Set())
const deleting = ref(false)
const expandedPrediction = ref<number | null>(null)

type ModalMode = 'fresh' | 'batch'

const modal = ref<{
  show: boolean
  mode: ModalMode
  title: string
  subtitle: string
  inputLabel: string
  value: number
  max: number
  error: string
  quickPicks: { label: string; value: number }[]
}>({
  show: false,
  mode: 'fresh',
  title: '',
  subtitle: '',
  inputLabel: '',
  value: 20,
  max: 500,
  error: '',
  quickPicks: [],
})

const beatColorMap: Record<string, string> = {
  setup: '#6B7280', provoke: '#FFE500', twist: '#A855F7', payoff: '#FF4757', hook: '#3B82F6'
}
const beatLabelMap: Record<string, string> = {
  setup: '铺垫', provoke: '激化', twist: '转折', payoff: '爆发', hook: '悬念'
}

const getLastBeatType = (prediction: ChapterPredictionData): string | null => {
  if (!prediction.beats?.length) return null
  return prediction.beats[prediction.beats.length - 1].type
}

const togglePrediction = (chapterNumber: number) => {
  expandedPrediction.value = expandedPrediction.value === chapterNumber ? null : chapterNumber
}

const sortedOutline = computed(() =>
  [...props.outline].sort((a, b) => a.chapter_number - b.chapter_number)
)

const emit = defineEmits<{
  (e: 'edit', payload: { field: string; title: string; value: any }): void
  (e: 'add'): void
  (e: 'regenerate', payload: { chapterNumbers?: number[]; totalChapters?: number }): void
  (e: 'delete-outlines', payload: { chapterNumbers: number[] }): void
  (e: 'batch-generate', payload: { chapterNumbers: number[] }): void
  (e: 'batch-predict'): void
}>()

const completedNumbers = computed(() => {
  if (!props.chapters) return new Set<number>()
  return new Set(
    props.chapters
      .filter(ch => ch.generation_status === 'successful')
      .map(ch => ch.chapter_number)
  )
})

const uncompletedCount = computed(() => {
  return sortedOutline.value.filter(o => !completedNumbers.value.has(o.chapter_number)).length
})

const unpredictedCount = computed(() => {
  return sortedOutline.value.filter(o => !(o.metadata?.prediction)).length
})

const generateFreshText = computed(() => {
  if (regenerating.value && freshGenerating.value) return '生成中...'
  if (sortedOutline.value.length === 0) return '基于简介生成大纲'
  return '生成后续大纲'
})

const isCompleted = (chapterNumber: number): boolean => {
  return completedNumbers.value.has(chapterNumber)
}

const isRegenerated = (chapterNumber: number): boolean => {
  return regeneratedNumbers.value.has(chapterNumber)
}

const clearRegenerated = () => {
  regeneratedNumbers.value = new Set()
  regenerateResult.value = null
}

const emitEdit = (field: string, title: string, value: any) => {
  if (!props.editable) return
  emit('edit', { field, title, value })
}

const handleGenerateFresh = () => {
  if (regenerating.value) return
  modal.value = {
    show: true,
    mode: 'fresh',
    title: sortedOutline.value.length === 0 ? '基于简介生成大纲' : '生成后续大纲',
    subtitle: '系统将自动分批生成，请稍候',
    inputLabel: '要生成的章节数量',
    value: 20,
    max: 500,
    error: '',
    quickPicks: [
      { label: '20 章', value: 20 },
      { label: '50 章', value: 50 },
      { label: '100 章', value: 100 },
      { label: '200 章', value: 200 },
    ],
  }
}

const handleRegenerateUncompleted = () => {
  if (regenerating.value) return
  freshGenerating.value = false
  emit('regenerate', {})
}

const handleRegenerateSingle = (chapterNumber: number) => {
  if (regenerating.value) return
  emit('regenerate', { chapterNumbers: [chapterNumber] })
}

const handleBatchGenerate = () => {
  if (batchGenerating.value || regenerating.value) return
  const maxCount = uncompletedCount.value
  const defaultCount = Math.min(5, maxCount)
  const picks: { label: string; value: number }[] = []
  if (maxCount >= 3) picks.push({ label: '3 章', value: 3 })
  if (maxCount >= 5) picks.push({ label: '5 章', value: 5 })
  if (maxCount >= 10) picks.push({ label: '10 章', value: 10 })
  if (maxCount >= 20) picks.push({ label: '20 章', value: 20 })
  if (!picks.find(p => p.value === maxCount)) picks.push({ label: `全部 (${maxCount})`, value: maxCount })
  modal.value = {
    show: true,
    mode: 'batch',
    title: '连续生成章节',
    subtitle: `将按顺序连续生成，最多可选 ${maxCount} 章`,
    inputLabel: '生成章节数量',
    value: defaultCount,
    max: maxCount,
    error: '',
    quickPicks: picks,
  }
}

const handleModalConfirm = () => {
  const v = modal.value.value
  if (isNaN(v) || v < 1 || v > modal.value.max) {
    modal.value.error = `请输入 1–${modal.value.max} 之间的正整数`
    return
  }
  modal.value.error = ''
  modal.value.show = false
  if (modal.value.mode === 'fresh') {
    freshGenerating.value = true
    emit('regenerate', { totalChapters: v })
  } else {
    const chapters = uncompletedNumbers.value.slice(0, v)
    emit('batch-generate', { chapterNumbers: chapters })
  }
}

const handleBatchPredict = () => {
  if (predictGenerating.value || regenerating.value) return
  emit('batch-predict')
}

const markRegenerated = (updatedChapters: number[], totalTarget: number) => {
  regeneratedNumbers.value = new Set(updatedChapters)
  regenerateResult.value = { updated: updatedChapters.length, total: totalTarget }
}

const uncompletedNumbers = computed(() =>
  sortedOutline.value
    .filter(o => !completedNumbers.value.has(o.chapter_number))
    .map(o => o.chapter_number)
)

const isAllUncompletedSelected = computed(() =>
  uncompletedNumbers.value.length > 0 && uncompletedNumbers.value.every(n => selectedNumbers.value.has(n))
)

const isSelected = (chapterNumber: number): boolean => {
  return selectedNumbers.value.has(chapterNumber)
}

const toggleSelect = (chapterNumber: number) => {
  const next = new Set(selectedNumbers.value)
  if (next.has(chapterNumber)) {
    next.delete(chapterNumber)
  } else {
    next.add(chapterNumber)
  }
  selectedNumbers.value = next
}

const toggleSelectAll = () => {
  if (isAllUncompletedSelected.value) {
    selectedNumbers.value = new Set()
  } else {
    selectedNumbers.value = new Set(uncompletedNumbers.value)
  }
}

const enterBatchMode = () => {
  batchMode.value = true
  selectedNumbers.value = new Set()
}

const exitBatchMode = () => {
  batchMode.value = false
  selectedNumbers.value = new Set()
}

const handleDeleteSelected = () => {
  if (selectedNumbers.value.size === 0 || deleting.value) return
  const confirmed = window.confirm(`确定删除选中的 ${selectedNumbers.value.size} 个未完成大纲吗？此操作不可撤销。`)
  if (!confirmed) return
  emit('delete-outlines', { chapterNumbers: [...selectedNumbers.value] })
}

defineExpose({
  setRegenerating: (v: boolean) => {
    regenerating.value = v
    if (!v) freshGenerating.value = false
  },
  setDeleting: (v: boolean) => {
    deleting.value = v
    if (!v) exitBatchMode()
  },
  setBatchGenerating: (v: boolean) => {
    batchGenerating.value = v
  },
  setPredictGenerating: (v: boolean) => {
    predictGenerating.value = v
    if (!v) predictProgress.value = null
  },
  setPredictProgress: (p: { total: number; completed: number; failed: number }) => {
    predictProgress.value = p
  },
  markRegenerated,
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChapterOutlineSection'
})
</script>

<style scoped>
.animate-slideDown {
  animation: slideDown 0.2s ease-out both;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
