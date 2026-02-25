<!-- AIMETA P=章节大纲区_大纲展示|R=大纲列表_重新生成|NR=不含编辑功能|E=component:ChapterOutlineSection|X=ui|A=大纲组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h2 class="text-2xl font-bold text-slate-900">章节大纲</h2>
        <p class="text-sm text-slate-500">故事结构与章节节奏一目了然</p>
      </div>
      <div v-if="editable" class="flex items-center gap-2 flex-wrap">
        <template v-if="!batchMode">
          <!-- 生成大纲（新增/续写） -->
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors"
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
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg transition-colors"
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
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-sky-600 bg-sky-50 hover:bg-sky-100 rounded-lg transition-colors"
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
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-sky-700 bg-sky-50 hover:bg-sky-100 rounded-lg transition-colors"
            :disabled="regenerating || predictGenerating"
            @click="handleBatchPredict"
          >
            <svg v-if="predictGenerating" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <svg v-else class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            {{ predictGenerating ? '推演中...' : `一键推演 (${unpredictedCount})` }}
          </button>
          <button
            v-if="uncompletedCount > 0"
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-purple-700 bg-purple-50 hover:bg-purple-100 rounded-lg transition-colors"
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
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition-colors"
            @click="enterBatchMode"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L6.382 6H4a1 1 0 000 2h.5l.5 8.5A2 2 0 007 18.5h6a2 2 0 002-2L15.5 8H16a1 1 0 100-2h-2.382l-1.724-3.447A1 1 0 0011 2H9zm-.5 4l1-2h1l1 2h-3zM8.5 10a.5.5 0 011 0v4a.5.5 0 01-1 0v-4zm3 0a.5.5 0 011 0v4a.5.5 0 01-1 0v-4z" clip-rule="evenodd" />
            </svg>
            批量删除
          </button>
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg"
            @click="$emit('add')"
          >
            <svg class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
            新增章节
          </button>
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm text-gray-500 hover:text-indigo-600 transition-colors"
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
          <label class="flex items-center gap-2 px-3 py-2 text-sm text-slate-700 cursor-pointer select-none">
            <input
              type="checkbox"
              class="h-4 w-4 rounded border-slate-300 text-red-600 focus:ring-red-500"
              :checked="isAllUncompletedSelected"
              @change="toggleSelectAll"
            />
            全选未完成 ({{ uncompletedCount }})
          </label>
          <button
            type="button"
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
            class="flex items-center gap-1 px-3 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
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
        ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
        : 'bg-amber-50 text-amber-800 border border-amber-200'"
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
        带有 <span class="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-sky-100 text-sky-700">新</span> 标记的是本次更新的大纲。
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

    <ol class="relative border-l border-slate-200 ml-3 space-y-8">
      <li
        v-for="chapter in sortedOutline"
        :key="chapter.chapter_number"
        class="ml-6"
      >
        <span
          class="absolute -left-3 mt-1 flex h-6 w-6 items-center justify-center rounded-full text-white text-xs font-semibold"
          :class="isCompleted(chapter.chapter_number) ? 'bg-emerald-500' : 'bg-indigo-500'"
        >
          <template v-if="isCompleted(chapter.chapter_number)">
            <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </template>
          <template v-else>{{ chapter.chapter_number }}</template>
        </span>
        <div
          class="rounded-2xl border shadow-sm p-5 transition-all duration-300"
          :class="[
            isCompleted(chapter.chapter_number)
              ? 'bg-emerald-50/50 border-emerald-200'
              : isSelected(chapter.chapter_number)
                ? 'bg-red-50/60 border-red-300 ring-2 ring-red-200'
                : isRegenerated(chapter.chapter_number)
                  ? 'bg-sky-50/60 border-sky-300 ring-2 ring-sky-200'
                  : 'bg-white/95 border-slate-200'
          ]"
        >
          <div class="flex items-center justify-between gap-4">
            <div class="flex items-center gap-2 min-w-0">
              <input
                v-if="batchMode && !isCompleted(chapter.chapter_number)"
                type="checkbox"
                class="h-4 w-4 flex-shrink-0 rounded border-slate-300 text-red-600 focus:ring-red-500 cursor-pointer"
                :checked="isSelected(chapter.chapter_number)"
                @change="toggleSelect(chapter.chapter_number)"
              />
              <h3 class="text-lg font-semibold text-slate-900 truncate">{{ chapter.title || `第${chapter.chapter_number}章` }}</h3>
              <span
                v-if="isCompleted(chapter.chapter_number)"
                class="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700"
              >
                已完成
              </span>
              <span
                v-if="isRegenerated(chapter.chapter_number)"
                class="flex-shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-sky-100 text-sky-700 animate-pulse"
              >
                <svg class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M5 2a1 1 0 011 1v1h1a1 1 0 010 2H6v1a1 1 0 01-2 0V6H3a1 1 0 010-2h1V3a1 1 0 011-1zm0 10a1 1 0 011 1v1h1a1 1 0 110 2H6v1a1 1 0 11-2 0v-1H3a1 1 0 110-2h1v-1a1 1 0 011-1zM12 2a1 1 0 01.967.744L14.146 7.2 17.5 9.134a1 1 0 010 1.732l-3.354 1.935-1.18 4.455a1 1 0 01-1.933 0L9.854 12.8 6.5 10.866a1 1 0 010-1.732l3.354-1.935 1.18-4.455A1 1 0 0112 2z" clip-rule="evenodd" />
                </svg>
                新
              </span>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <button
                v-if="editable && !isCompleted(chapter.chapter_number)"
                type="button"
                class="p-1.5 text-slate-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                title="重新生成此章大纲"
                :disabled="regenerating"
                @click="handleRegenerateSingle(chapter.chapter_number)"
              >
                <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <span class="text-xs text-slate-400">#{{ chapter.chapter_number }}</span>
            </div>
          </div>
          <p class="mt-3 text-sm text-slate-600 leading-6 whitespace-pre-line">{{ chapter.summary || '暂无摘要' }}</p>

          <!-- 推演标签和展开按钮（仅已完成且有推演数据的章节显示） -->
          <div v-if="isCompleted(chapter.chapter_number) && chapter.metadata?.prediction" class="mt-3">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span v-if="chapter.metadata.prediction.cool_points?.length" class="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold text-white" style="background-color: #F59E0B;">爽</span>
              <span v-if="chapter.metadata.prediction.foreshadowing_hooks?.length" class="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold text-white" style="background-color: #3B82F6;">伏</span>
              <span v-if="chapter.metadata.prediction.foreshadowing_targets?.length" class="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold text-white" style="background-color: #10B981;">收</span>
              <span v-if="getLastBeatType(chapter.metadata.prediction) === 'payoff'" class="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-semibold text-white" style="background-color: #EF4444;">爆</span>
              <button
                type="button"
                class="text-xs text-indigo-600 hover:text-indigo-800 font-medium ml-1 transition-colors"
                @click="togglePrediction(chapter.chapter_number)"
              >
                {{ expandedPrediction === chapter.chapter_number ? '收起推演' : '查看推演' }}
              </button>
            </div>

            <!-- 推演详情展开区 -->
            <div v-if="expandedPrediction === chapter.chapter_number" class="mt-3 space-y-2 animate-slideDown">
              <div v-if="chapter.metadata.prediction.key_points?.length" class="bg-blue-50 border border-blue-100 rounded-lg p-3">
                <h5 class="text-xs font-semibold text-blue-800 mb-1.5">章节要点</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.key_points" :key="i" class="text-xs text-blue-700 flex gap-1.5">
                    <span class="shrink-0">•</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.cool_points?.length" class="bg-amber-50 border border-amber-100 rounded-lg p-3">
                <h5 class="text-xs font-semibold text-amber-800 mb-1.5">✨ 爽点设计</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.cool_points" :key="i" class="text-xs text-amber-700 flex gap-1.5">
                    <span class="shrink-0">⚡</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.foreshadowing_hooks?.length" class="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                <h5 class="text-xs font-semibold text-indigo-800 mb-1.5">🪝 伏笔/钩子</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.foreshadowing_hooks" :key="i" class="text-xs text-indigo-700 flex gap-1.5">
                    <span class="shrink-0">🪝</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.foreshadowing_targets?.length" class="bg-green-50 border border-green-100 rounded-lg p-3">
                <h5 class="text-xs font-semibold text-green-800 mb-1.5">🎯 需回收伏笔</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.foreshadowing_targets" :key="i" class="text-xs text-green-700 flex gap-1.5">
                    <span class="shrink-0">🎯</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.limitations?.length" class="bg-slate-50 border border-slate-200 rounded-lg p-3">
                <h5 class="text-xs font-semibold text-slate-700 mb-1.5">⚠️ 章节限制</h5>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in chapter.metadata.prediction.limitations" :key="i" class="text-xs text-slate-600 flex gap-1.5">
                    <span class="shrink-0">⚠</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>
              <div v-if="chapter.metadata.prediction.beats?.length" class="bg-purple-50 border border-purple-100 rounded-lg p-3">
                <h5 class="text-xs font-semibold text-purple-800 mb-1.5">节拍编排</h5>
                <div class="space-y-1">
                  <div v-for="(beat, i) in chapter.metadata.prediction.beats" :key="i" class="flex items-start gap-1.5 text-xs">
                    <span class="shrink-0 w-4 h-4 rounded-full text-[9px] flex items-center justify-center text-white font-medium"
                          :style="{ backgroundColor: beatColorMap[beat.type] || '#6B7280' }">{{ i + 1 }}</span>
                    <div>
                      <span class="font-medium" :style="{ color: beatColorMap[beat.type] || '#6B7280' }">{{ beatLabelMap[beat.type] || beat.type }}</span>
                      <span class="text-slate-600 ml-1">{{ beat.content }}</span>
                      <span class="text-slate-400 ml-1">({{ beat.emotion }})</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </li>
      <li v-if="!sortedOutline.length" class="ml-6 text-slate-400 text-sm">暂无章节大纲</li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

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
  metadata?: { prediction?: ChapterPredictionData } | null
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
const freshGenerating = ref(false) // 区分是"生成"还是"重新生成"
const regeneratedNumbers = ref<Set<number>>(new Set())
const regenerateResult = ref<{ updated: number; total: number } | null>(null)
const batchMode = ref(false)
const batchGenerating = ref(false)
const predictGenerating = ref(false)
const selectedNumbers = ref<Set<number>>(new Set())
const deleting = ref(false)
const expandedPrediction = ref<number | null>(null)

const beatColorMap: Record<string, string> = {
  setup: '#6B7280', provoke: '#F59E0B', twist: '#8B5CF6', payoff: '#EF4444', hook: '#3B82F6'
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

// 按 chapter_number 排序，防止显示乱序
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
  const input = window.prompt('请输入要生成的章节数量（将自动分批生成）', '20')
  if (!input) return
  const total = parseInt(input, 10)
  if (isNaN(total) || total < 1 || total > 500) {
    alert('请输入 1-500 之间的正整数')
    return
  }
  freshGenerating.value = true
  emit('regenerate', { totalChapters: total })
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
  const input = window.prompt(`要连续生成几个章节？（最多 ${maxCount}）`, String(defaultCount))
  if (!input) return
  const count = parseInt(input, 10)
  if (isNaN(count) || count < 1 || count > maxCount) {
    alert(`请输入 1-${maxCount} 之间的正整数`)
    return
  }
  // 取前 count 个未完成章节
  const chapters = uncompletedNumbers.value.slice(0, count)
  emit('batch-generate', { chapterNumbers: chapters })
}

const handleBatchPredict = () => {
  if (predictGenerating.value || regenerating.value) return
  emit('batch-predict')
}

const markRegenerated = (updatedChapters: number[], totalTarget: number) => {
  regeneratedNumbers.value = new Set(updatedChapters)
  regenerateResult.value = { updated: updatedChapters.length, total: totalTarget }
}

// 批量删除相关
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
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>

