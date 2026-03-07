<!-- AIMETA P=写作台侧边栏_章节目录|R=章节列表_导航|NR=不含内容编辑|E=component:WDSidebar|X=ui|A=侧边栏|D=vue|S=dom|RD=./README.ai -->
<template>
  <div>
    <!-- 侧边栏遮罩 (移动端) -->
    <div
      v-if="sidebarOpen"
      @click="$emit('closeSidebar')"
      class="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden"
    ></div>

    <!-- 左侧：蓝图和章节列表 -->
    <div
      :class="[
        'md-card md-card-elevated transition-all duration-300 h-full',
        'lg:relative lg:translate-x-0 lg:w-80 lg:flex-shrink-0',
        sidebarOpen
          ? 'fixed left-4 top-20 bottom-4 w-80 z-50 translate-x-0'
          : 'lg:w-80 lg:flex-shrink-0 -translate-x-full absolute lg:relative'
      ]"
      style="border-radius: var(--md-radius-xl);"
    >
      <div class="h-full flex flex-col">
        <!-- 蓝图预览卡片 -->
        <div class="md-card-header flex-shrink-0">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-full flex items-center justify-center" style="background-color: var(--md-primary-container);">
              <svg class="w-5 h-5" style="color: var(--md-on-primary-container);" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
            </div>
            <div>
              <h2 class="md-title-medium font-semibold">故事蓝图</h2>
              <p class="md-body-small md-on-surface-variant">{{ project.blueprint?.style || '未设定风格' }}</p>
            </div>
          </div>

          <div class="space-y-3">
            <div class="md-card md-card-filled p-3" style="border-radius: var(--md-radius-md);">
              <h3 class="md-label-large font-semibold" style="color: var(--md-on-primary-container);">故事概要</h3>
              <Tooltip :text="project.blueprint?.one_sentence_summary">
                <p class="md-body-small line-clamp-3" style="color: var(--md-on-surface-variant);">{{ project.blueprint?.one_sentence_summary || '暂无概要' }}</p>
              </Tooltip>
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs">
              <div class="md-card md-card-outlined p-2 text-center" style="border-radius: var(--md-radius-md);">
                <div class="md-title-small font-semibold" style="color: var(--md-primary);">{{ characterCount }}</div>
                <div class="md-label-small md-on-surface-variant">角色</div>
              </div>
              <div class="md-card md-card-outlined p-2 text-center" style="border-radius: var(--md-radius-md);">
                <div class="md-title-small font-semibold" style="color: var(--md-secondary);">{{ relationshipCount }}</div>
                <div class="md-label-small md-on-surface-variant">关系</div>
              </div>
            </div>
          </div>
        </div>

        <div class="reference-panel">
          <div class="reference-panel-header">
            <div>
              <p class="reference-panel-title">参考小说</p>
              <p class="reference-panel-subtitle">绑定后可在灵感模式与章节生成中复用风格/记忆卡</p>
            </div>
            <div class="reference-panel-actions">
              <button class="reference-panel-link reference-panel-link--primary" type="button" @click="openReferenceLibrary">
                添加
              </button>
              <button class="reference-panel-link" type="button" @click="refreshReferenceNovels">
                刷新
              </button>
              <button class="reference-panel-link" type="button" @click="openReferenceLibrary">
                管理
              </button>
              <button
                class="reference-panel-link text-red-500"
                type="button"
                @click="handleUnbindReferences"
                :disabled="!boundReferenceNovels.length"
              >
                解绑
              </button>
            </div>
          </div>
          <div class="reference-panel-body">
            <div v-if="referencePanelLoading" class="reference-panel-empty">加载中...</div>
            <div v-else-if="boundReferenceNovels.length" class="reference-panel-list">
              <div
                v-for="novel in boundReferenceNovels"
                :key="novel.id"
                class="reference-panel-item"
              >
                <div>
                  <p class="text-sm font-medium">{{ novel.title }}</p>
                  <p class="text-xs text-gray-500">{{ novel.author || '未知作者' }} <span v-if="novel.genre"> · {{ novel.genre }}</span><span v-if="!novel.genre"> · 未设定题材</span></p>
                </div>
                <span class="reference-panel-tag" :data-status="novel.status">{{ novel.status }}</span>
              </div>
            </div>
            <div v-else class="reference-panel-empty">
              当前项目未绑定参考小说，可在灵感模式中选取并生成后自动绑定。
            </div>
          </div>
        </div>

        <!-- 章节列表 -->
        <div ref="listContainer" class="flex-1 overflow-y-auto">
          <div class="p-6 pb-4">
            <div class="flex items-center justify-between mb-4">
              <h3 class="md-title-medium font-semibold">章节大纲</h3>
              <div class="flex items-center gap-2">
                <button
                  v-if="hasIncompleteChapters"
                  @click.stop="scrollToFirstIncompleteChapter"
                  class="md-btn md-btn-text md-ripple"
                >
                  定位到未完成
                </button>
                <span class="md-chip md-chip-filter selected">
                  {{ totalChapters }} 章
                </span>
              </div>
            </div>
          </div>

          <!-- 迷你节奏条 -->
          <div v-if="project.blueprint?.chapter_outline?.length" class="flex gap-px mx-6 mb-2 h-3">
            <div v-for="outline in project.blueprint.chapter_outline" :key="outline.chapter_number"
              class="flex-1 rounded-sm cursor-pointer transition-all duration-200 hover:h-4"
              :style="{ backgroundColor: getRhythmColor(outline) }"
              :class="{ 'opacity-40': selectedChapterNumber !== null && selectedChapterNumber !== outline.chapter_number }"
              :title="`第${outline.chapter_number}章 ${outline.title}`"
              @click="handleSelectChapter(outline)"
            />
          </div>

          <div class="px-6 pb-6">
            <div v-if="project.blueprint?.chapter_outline?.length" class="space-y-3">
              <div
                v-for="(chapter, index) in project.blueprint.chapter_outline"
                :key="chapter.chapter_number"
                :ref="el => setChapterRef(chapter.chapter_number, el)"
                @click="handleSelectChapter(chapter)"
                :class="[
                  'group cursor-pointer p-4 m3-chapter-card m3-stagger',
                  selectedForDeletion.includes(chapter.chapter_number)
                    ? 'm3-chapter-danger'
                    : selectedChapterNumber === chapter.chapter_number
                    ? 'm3-chapter-selected md-elevation-1'
                    : 'hover:md-elevation-1'
                ]"
                :style="{ animationDelay: `${index * 40}ms` }"
              >
                <div class="flex items-start gap-3">
                  <div class="flex-shrink-0 pt-1">
                    <input
                      type="checkbox"
                      :disabled="isChapterCompleted(chapter.chapter_number)"
                      :checked="selectedForDeletion.includes(chapter.chapter_number)"
                      @click.stop="toggleSelection(chapter.chapter_number)"
                      class="h-4 w-4 rounded border-[var(--md-outline)] text-[var(--md-primary)] focus:ring-[var(--md-primary)] disabled:opacity-50 accent-[var(--md-primary)]"
                    />
                  </div>
                  <div
                    :class="[
                      'w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0',
                      isChapterCompleted(chapter.chapter_number)
                        ? 'bg-[var(--md-success)] text-[var(--md-on-success)]'
                        : isChapterGenerating(chapter.chapter_number) || isChapterEvaluating(chapter.chapter_number) || isChapterSelecting(chapter.chapter_number)
                        ? 'bg-[var(--md-primary)] text-[var(--md-on-primary)] animate-pulse'
                        : isChapterFailed(chapter.chapter_number)
                        ? 'bg-[var(--md-error)] text-[var(--md-on-error)]'
                        : selectedChapterNumber === chapter.chapter_number
                        ? 'bg-[var(--md-primary)] text-[var(--md-on-primary)]'
                        : 'bg-[var(--md-surface-container-highest)] text-[var(--md-on-surface-variant)]'
                    ]"
                  >
                    <svg v-if="isChapterCompleted(chapter.chapter_number)" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
                    </svg>
                    <svg v-else-if="isChapterGenerating(chapter.chapter_number) || isChapterSelecting(chapter.chapter_number)" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                    </svg>
                    <svg v-else-if="isChapterEvaluating(chapter.chapter_number)" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M10 2a6 6 0 00-6 6v3.586l-1.707 1.707A1 1 0 003 15v1a1 1 0 001 1h12a1 1 0 001-1v-1a1 1 0 00-.293-.707L16 11.586V8a6 6 0 00-6-6zM8.05 17a2 2 0 103.9 0H8.05z"></path>
                    </svg>
                    <svg v-else-if="isChapterFailed(chapter.chapter_number)" class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                    </svg>
                    <span v-else>{{ chapter.chapter_number }}</span>
                  </div>
                  <div class="flex-1 min-w-0">
                    <Tooltip :text="`第${chapter.chapter_number}章 ${chapter.title}`">
                      <h4 class="md-body-large font-semibold mb-1 line-clamp-1">第{{ chapter.chapter_number }}章 {{ chapter.title }}</h4>
                    </Tooltip>
                    <Tooltip :text="chapter.summary">
                      <p class="md-body-small md-on-surface-variant line-clamp-2 leading-relaxed">{{ chapter.summary }}</p>
                    </Tooltip>

                    <!-- 章节状态 -->
                    <div class="mt-2 flex items-center gap-2">
                      <span
                        v-if="isChapterCompleted(chapter.chapter_number)"
                        class="md-chip"
                        style="background-color: var(--md-success-container); color: var(--md-on-success-container);"
                      >
                        已完成
                      </span>
                      <span
                        v-else-if="isChapterGenerating(chapter.chapter_number)"
                        class="md-chip animate-pulse"
                        style="background-color: var(--md-primary-container); color: var(--md-on-primary-container);"
                      >
                        生成中...
                      </span>
                      <span
                        v-else-if="isChapterSelecting(chapter.chapter_number)"
                        class="md-chip animate-pulse"
                        style="background-color: var(--md-primary-container); color: var(--md-on-primary-container);"
                      >
                        选择中...
                      </span>
                      <span
                        v-else-if="isChapterEvaluating(chapter.chapter_number)"
                        class="md-chip animate-pulse"
                        style="background-color: var(--md-secondary-container); color: var(--md-on-secondary-container);"
                      >
                        评审中...
                      </span>
                      <span
                        v-else-if="isChapterFailed(chapter.chapter_number)"
                        class="md-chip"
                        style="background-color: var(--md-error-container); color: var(--md-on-error-container);"
                      >
                        生成失败
                      </span>
                      <span
                        v-else-if="hasChapterInProgress(chapter.chapter_number)"
                        class="md-chip"
                        style="background-color: var(--md-warning-container); color: var(--md-on-warning-container);"
                      >
                        待选择版本
                      </span>
                      <span v-else class="md-chip md-chip-assist">未开始</span>
                    </div>

                    <!-- 节奏标签 -->
                    <div v-if="chapter.metadata?.prediction" class="flex gap-1 mt-1.5 flex-wrap">
                      <span v-if="chapter.metadata.prediction.cool_points?.length" class="rhythm-tag" style="background-color: #F59E0B; color: white;">爽</span>
                      <span v-if="chapter.metadata.prediction.foreshadowing_hooks?.length" class="rhythm-tag" style="background-color: #3B82F6; color: white;">伏</span>
                      <span v-if="chapter.metadata.prediction.foreshadowing_targets?.length" class="rhythm-tag" style="background-color: #10B981; color: white;">收</span>
                      <span v-if="getLastBeatType(chapter.metadata.prediction) === 'payoff'" class="rhythm-tag" style="background-color: #EF4444; color: white;">爆</span>
                      <button
                        @click.stop="previewPrediction(chapter.chapter_number)"
                        class="md-btn md-btn-text md-ripple !px-1.5 !py-0.5"
                        style="font-size: 11px; line-height: 1;"
                        title="查看剧情推演"
                      >
                        查看推演
                      </button>
                    </div>
                  </div>

                  <!-- 章节操作按钮 -->
                  <div class="flex items-center opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    <button
                      v-if="!isChapterCompleted(chapter.chapter_number)"
                      @click.stop="$emit('editChapter', chapter)"
                      class="md-icon-btn md-ripple"
                      title="编辑大纲"
                    >
                      <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z"></path>
                        <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd"></path>
                      </svg>
                    </button>
                    <button
                      v-if="canGenerateChapter(chapter.chapter_number) || isChapterFailed(chapter.chapter_number) || hasChapterInProgress(chapter.chapter_number)"
                      @click.stop="confirmGenerateChapter(chapter.chapter_number)"
                      :disabled="generatingChapter === chapter.chapter_number || isChapterGenerating(chapter.chapter_number) || props.batchGenerating"
                      class="md-icon-btn md-ripple disabled:opacity-50"
                      style="color: var(--md-primary);"
                      :title="isChapterCompleted(chapter.chapter_number) ? '重新生成' : isChapterFailed(chapter.chapter_number) ? '重试' : hasChapterInProgress(chapter.chapter_number) ? '重新生成版本' : '开始创作'"
                    >
                      <svg v-if="generatingChapter === chapter.chapter_number || isChapterGenerating(chapter.chapter_number)" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                      </svg>
                      <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
                      </svg>
                    </button>
                    <!-- Batch delete replaces the single delete button -->
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="text-center py-8 md-body-medium md-on-surface-variant">
              <svg class="w-12 h-12 mx-auto mb-3 opacity-50" fill="currentColor" viewBox="0 0 20 20">
                <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9z"></path>
              </svg>
              <p>暂无章节大纲</p>
            </div>
            <div v-if="selectedForDeletion.length > 0" class="mt-4">
              <button
                @click="handleDeleteSelected"
                class="md-btn md-btn-filled md-ripple w-full flex items-center justify-center gap-2"
                style="background-color: var(--md-error); color: var(--md-on-error);"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm4 0a1 1 0 012 0v6a1 1 0 11-2 0V8z" clip-rule="evenodd"></path>
                </svg>
                <span>删除选中的 {{ selectedForDeletion.length }} 章</span>
              </button>
            </div>
            <div class="mt-4">
              <button
                @click="$emit('generateOutline')"
                :disabled="props.isGeneratingOutline || props.batchGenerating"
                class="md-btn md-btn-tonal md-ripple w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg v-if="props.isGeneratingOutline" class="w-5 h-5 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                </svg>
                <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
                </svg>
                <span>{{ props.isGeneratingOutline ? '生成中...' : '生成后续大纲' }}</span>
              </button>
            </div>
            <!-- 连续生成按钮 -->
            <div class="mt-3">
              <button
                v-if="!props.batchGenerating"
                @click="$emit('batchGenerate')"
                :disabled="props.isGeneratingOutline || !!props.generatingChapter"
                class="md-btn md-btn-filled md-ripple w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z"></path>
                </svg>
                <span>连续生成</span>
              </button>
              <button
                v-else
                @click="$emit('cancelBatch')"
                class="md-btn md-btn-outlined md-ripple w-full flex items-center justify-center gap-2"
                style="border-color: var(--md-error); color: var(--md-error);"
              >
                <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
                </svg>
                <span>取消连续生成 ({{ props.batchProgress?.current || 0 }}/{{ props.batchProgress?.total || 0 }})</span>
              </button>
            </div>
            <div class="mt-3">
              <button
                @click="$emit('rebuildRag')"
                :disabled="props.isRebuildingRag"
                class="md-btn md-btn-tonal md-ripple w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg v-if="props.isRebuildingRag" class="w-5 h-5 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
                </svg>
                <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"></path>
                </svg>
                <span>{{ props.isRebuildingRag ? '刷新中...' : '刷新知识库' }}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <ReferenceNovelLibrary v-model:show="referenceLibraryVisible" @select="handleSelectReferenceNovel" />
</template>

<script setup lang="ts">
import { computed, ref, nextTick, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import type { NovelProject, ChapterOutline, ChapterPrediction, ReferenceNovelSummary } from '@/api/novel'
import Tooltip from '@/components/Tooltip.vue'
import { useNovelStore } from '@/stores/novel'
import ReferenceNovelLibrary from '@/components/ReferenceNovelLibrary.vue'

// 获取最后一个 beat 的 type
const getLastBeatType = (prediction: ChapterPrediction): string | null => {
  if (!prediction.beats?.length) return null
  return prediction.beats[prediction.beats.length - 1].type
}

// 根据 prediction 推导节奏条颜色
const getRhythmColor = (outline: ChapterOutline): string => {
  const prediction = outline.metadata?.prediction
  if (!prediction) return '#D1D5DB' // 灰色 - 无推演
  const coolCount = prediction.cool_points?.length || 0
  const hasForeshadowingTargets = (prediction.foreshadowing_targets?.length || 0) > 0
  if (hasForeshadowingTargets) return '#10B981' // 绿色 - 有伏笔回收
  if (coolCount >= 3) return '#EF4444' // 红色 - 爽点多
  if (coolCount >= 2) return '#F59E0B' // 橙色 - 有爽点
  if (coolCount >= 1) return '#FB923C' // 浅橙 - 少量爽点
  return '#93C5FD' // 浅蓝 - 只有基本要点
}

interface Props {
  project: NovelProject
  sidebarOpen: boolean
  selectedChapterNumber: number | null
  generatingChapter: number | null
  evaluatingChapter: number | null
  isGeneratingOutline: boolean
  isRebuildingRag: boolean
  batchGenerating: boolean
  batchProgress: { current: number; total: number } | null
}

const props = defineProps<Props>()
const novelStore = useNovelStore()

const emit = defineEmits([
  'closeSidebar',
  'selectChapter',
  'previewPrediction',
  'generateChapter',
  'editChapter',
  'deleteChapter',
  'generateOutline',
  'rebuildRag',
  'batchGenerate',
  'cancelBatch'
])

const selectedForDeletion = ref<number[]>([])
const listContainer = ref<HTMLElement | null>(null)
const chapterRefs = ref<Record<number, HTMLElement | null>>({})
const referenceLibraryVisible = ref(false)

const characterCount = computed(() => {
  return props.project?.blueprint?.characters?.length || 0
})

const relationshipCount = computed(() => {
  return props.project?.blueprint?.relationships?.length || 0
})

const boundReferenceNovels = computed(() => novelStore.projectReferenceNovels)
const referencePanelLoading = computed(
  () => novelStore.referenceNovelsLoading || novelStore.bindingReferenceNovels
)

const lastChapterNumber = computed(() => {
  if (!props.project?.blueprint?.chapter_outline || props.project.blueprint.chapter_outline.length === 0) {
    return null
  }
  return Math.max(...props.project.blueprint.chapter_outline.map(ch => ch.chapter_number))
})

const totalChapters = computed(() => {
  return props.project?.blueprint?.chapter_outline?.length || 0
})

const hasIncompleteChapters = computed(() => {
  if (!props.project?.blueprint?.chapter_outline) return false
  return props.project.blueprint.chapter_outline.some(ch => !isChapterCompleted(ch.chapter_number))
})

function toggleSelection(chapterNumber: number) {
  if (isChapterCompleted(chapterNumber)) return
  const index = selectedForDeletion.value.indexOf(chapterNumber)
  if (index > -1) {
    selectedForDeletion.value.splice(index, 1)
  } else {
    selectedForDeletion.value.push(chapterNumber)
  }
}

function handleDeleteSelected() {
  if (selectedForDeletion.value.length === 0) return

  const sortedSelection = [...selectedForDeletion.value].sort((a, b) => a - b)

  if (!lastChapterNumber.value || !sortedSelection.includes(lastChapterNumber.value)) {
    alert('批量删除必须包含最后一章。')
    return
  }

  const isContinuous = sortedSelection.every((num, i) => {
    return i === 0 || num === sortedSelection[i - 1] + 1
  })
  if (!isContinuous) {
    alert('只能删除连续的章节块。')
    return
  }

  emit('deleteChapter', sortedSelection)
  selectedForDeletion.value = []
}

async function confirmGenerateChapter(chapterNumber: number) {
  const confirmed = await globalAlert.showConfirm('重新生成会覆盖当前章节的生成结果，确定继续吗？', '重新生成确认')
  if (confirmed) {
    emit('generateChapter', chapterNumber)
  }
}

function previewPrediction(chapterNumber: number) {
  emit('previewPrediction', chapterNumber)
}

function handleSelectChapter(chapter: ChapterOutline) {
  emit('selectChapter', chapter.chapter_number)

  if (!chapter.metadata?.prediction) {
    return
  }

  const chapterStatus = props.project?.chapters?.find(
    item => item.chapter_number === chapter.chapter_number
  )?.generation_status

  if (chapterStatus === 'successful') {
    previewPrediction(chapter.chapter_number)
  }
}

function setChapterRef(chapterNumber: number, el: Element | ComponentPublicInstance | null) {
  if (!el) {
    delete chapterRefs.value[chapterNumber]
    return
  }

  const element = el instanceof Element ? el : (el.$el instanceof Element ? el.$el : null)

  if (element) {
    chapterRefs.value[chapterNumber] = element as HTMLElement
  }
}

const scrollToFirstIncompleteChapter = async () => {
  if (!props.project?.blueprint?.chapter_outline) return
  const sorted = [...props.project.blueprint.chapter_outline].sort((a, b) => a.chapter_number - b.chapter_number)
  const target = sorted.find(chapter => !isChapterCompleted(chapter.chapter_number))
  if (!target) return
  await nextTick()
  const element = chapterRefs.value[target.chapter_number]
  if (!element) return
  const container = listContainer.value
  if (container) {
    element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
  } else {
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

const refreshReferenceNovels = async () => {
  if (!props.project?.id) return
  try {
    await novelStore.loadProjectReferenceNovels(props.project.id)
  } catch (err) {
    console.error('加载参考小说失败:', err)
  }
}

watch(
  () => props.project?.id,
  () => {
    refreshReferenceNovels()
  },
  { immediate: true }
)

watch(
  () => referenceLibraryVisible.value,
  (visible) => {
    if (!visible) {
      refreshReferenceNovels()
    }
  }
)

const openReferenceLibrary = () => {
  referenceLibraryVisible.value = true
}

const handleSelectReferenceNovel = async (novel: ReferenceNovelSummary) => {
  if (!props.project?.id) return
  const currentIds = (boundReferenceNovels.value || []).map((n) => n.id)
  if (currentIds.includes(novel.id)) {
    // 已存在，仅刷新列表
    await refreshReferenceNovels()
    return
  }
  const newIds = [...currentIds, novel.id].slice(0, 3)
  try {
    await novelStore.bindProjectReferenceNovels(props.project.id, newIds)
  } catch (err) {
    globalAlert.showError(
      `绑定参考小说失败: ${err instanceof Error ? err.message : '请稍后重试'}`,
      '绑定失败'
    )
  }
}

const handleUnbindReferences = async () => {
  if (!props.project?.id || !boundReferenceNovels.value.length) return
  const confirmed = await globalAlert.showConfirm('解绑后将清空当前项目的参考小说绑定，确认继续？', '解绑参考小说')
  if (!confirmed) return
  try {
    await novelStore.bindProjectReferenceNovels(props.project.id, [])
  } catch (err) {
    globalAlert.showError(`解绑失败: ${err instanceof Error ? err.message : '请稍后重试'}`, '解绑失败')
  }
}

// 章节状态检查
const isChapterCompleted = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'successful'
}

const hasChapterInProgress = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'waiting_for_confirm'
}

const isChapterGenerating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'generating'
}

const isChapterEvaluating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'evaluating'
}

const isChapterFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const isChapterSelecting = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'selecting'
}

const canGenerateChapter = (chapterNumber: number) => {
  if (!props.project?.blueprint?.chapter_outline) return false

  const outlines = [...props.project.blueprint.chapter_outline].sort((a, b) => a.chapter_number - b.chapter_number)
  
  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break
    
    const chapter = props.project?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    if (!chapter || chapter.generation_status !== 'successful') {
      return false
    }
  }

  const currentChapter = props.project?.chapters.find(ch => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true
  }

  return true
}
</script>

<style scoped>
.reference-panel {
  margin: 0 1rem 1rem;
  padding: 0.75rem;
  border-radius: 1rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.reference-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.reference-panel-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.reference-panel-subtitle {
  margin: 0;
  font-size: 0.7rem;
  color: #475569;
}

.reference-panel-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.reference-panel-link {
  background: transparent;
  border: none;
  color: #2563eb;
  font-size: 0.75rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 0.75rem;
}

.reference-panel-link--primary {
  font-weight: 600;
  background: #eff6ff;
}

.reference-panel-link:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.reference-panel-body {
  margin-top: 0.6rem;
}

.reference-panel-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.reference-panel-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.55rem 0.75rem;
  border-radius: 0.75rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
}

.reference-panel-tag {
  font-size: 0.7rem;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  text-transform: capitalize;
}

.reference-panel-tag[data-status="ready"] {
  background: #dcfce7;
  color: #065f46;
}

.reference-panel-tag[data-status="analyzing"] {
  background: #e0f2fe;
  color: #0c4a6e;
}

.reference-panel-tag[data-status="failed"] {
  background: #fee2e2;
  color: #b91c1c;
}

.reference-panel-empty {
  font-size: 0.75rem;
  color: #475569;
}
</style>

<style scoped>
.m3-chapter-card {
  border-radius: var(--md-radius-lg);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface);
  transition: all var(--md-duration-medium) var(--md-easing-standard);
}

.m3-chapter-card:hover {
  background-color: var(--md-surface-container-low);
}

.m3-chapter-selected {
  border-color: var(--md-primary);
  background-color: var(--md-primary-container);
}

.m3-chapter-danger {
  border-color: var(--md-error);
  background-color: var(--md-error-container);
}

.m3-stagger {
  animation: m3-rise 0.45s ease-out both;
}

@keyframes m3-rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.rhythm-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  line-height: 1;
}
</style>
