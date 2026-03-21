<!-- AIMETA P=章节区_章节列表展示|R=章节列表_状态|NR=不含编辑功能|E=component:ChaptersSection|X=ui|A=章节组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="flex flex-col h-full min-h-0 overflow-hidden relative">
    <div class="flex flex-row flex-1 h-full lg:min-h-0 overflow-hidden">
      <!-- 移动端遮罩层 -->
      <div
        v-if="showChapterList"
        class="fixed inset-0 bg-black/60 z-40 lg:hidden"
        @click="showChapterList = false"
      ></div>

      <!-- 章节列表侧边栏 -->
      <aside
        class="fixed lg:static inset-y-0 left-0 z-50 w-72 lg:w-72 bg-[#141414] border-r border-[#2A2A2A] flex flex-col h-full min-h-0 max-h-full overflow-hidden transition-transform duration-300 lg:translate-x-0 shadow-2xl lg:shadow-none"
        :class="showChapterList ? 'translate-x-0' : '-translate-x-full'"
      >
        <div class="px-5 py-4 border-b border-[#2A2A2A] flex items-center justify-between">
          <h3 class="text-base font-semibold text-white">章节</h3>
          <span class="text-xs text-[#888]">{{ chapters.length }} 篇</span>
        </div>
        <ul class="flex-1 h-full overflow-y-auto divide-y divide-[#1C1C1C] overscroll-contain">
          <li v-for="(chapter, index) in chapters" :key="chapter.chapter_number">
            <button
              class="w-full text-left px-5 py-3 transition-colors duration-200"
              :class="selectedChapter?.chapter_number === chapter.chapter_number
                ? 'bg-[#FFE500]/10 text-[#FFE500] font-semibold'
                : 'hover:bg-[#1C1C1C] text-[#CCCCCC]'"
              @click="selectChapter(chapter.chapter_number)"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3 min-w-0">
                  <span class="inline-flex items-center justify-center w-6 h-6 text-xs font-semibold text-[#888] bg-[#2A2A2A] rounded-full">
                    {{ index + 1 }}
                  </span>
                  <span class="truncate">{{ chapter.title || `第${chapter.chapter_number}章` }}</span>
                </div>
                <span v-if="chapterCache.has(chapter.chapter_number)" class="text-xs text-[#555] shrink-0">
                  {{ calculateWordCount(chapterCache.get(chapter.chapter_number)?.content) }} 字
                </span>
                <span v-else class="text-xs text-[#555]">-</span>
              </div>
              <p v-if="chapter.summary" class="mt-1 text-xs text-[#666] truncate">
                {{ chapter.summary }}
              </p>
            </button>
          </li>
        </ul>
      </aside>

      <section class="flex-1 flex flex-col bg-[#0A0A0A] h-full min-h-0 max-h-full overflow-hidden relative">
        <!-- 移动端浮动按钮 -->
        <button
          v-if="!showChapterList"
          @click="showChapterList = true"
          class="lg:hidden fixed bottom-6 left-6 z-30 w-14 h-14 bg-[#FFE500] text-black rounded-full shadow-lg flex items-center justify-center hover:bg-[#FFC300] transition-colors"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <!-- Loading State -->
        <div v-if="isLoading" class="h-full flex items-center justify-center">
          <div class="text-center">
            <div class="w-10 h-10 border-4 border-[#2A2A2A] border-t-[#FFE500] rounded-full animate-spin mx-auto mb-3"></div>
            <p class="text-sm text-[#888]">加载中...</p>
          </div>
        </div>

        <!-- Error State -->
        <div v-else-if="error" class="h-full flex items-center justify-center">
          <div class="text-center">
            <div class="w-12 h-12 bg-[#FF4757]/10 rounded-full flex items-center justify-center mx-auto mb-3">
              <svg class="w-6 h-6 text-[#FF4757]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p class="text-sm text-[#CCCCCC]">{{ error }}</p>
          </div>
        </div>

        <!-- Content -->
        <template v-else-if="selectedChapter">
          <!-- Header with Status and Tabs -->
          <header class="px-6 py-4 border-b border-[#2A2A2A] bg-[#141414]">
            <div class="flex items-start justify-between gap-4 mb-3">
              <div class="flex-1">
                <h4 class="text-xl font-bold text-white">{{ selectedChapter.title || `第${selectedChapter.chapter_number}章` }}</h4>
                <div class="flex items-center gap-3 mt-1.5">
                  <span class="text-sm text-[#888]">第 {{ selectedChapter.chapter_number }} 章</span>
                  <span class="text-sm text-[#444]">·</span>
                  <span class="text-sm text-[#888]">{{ calculateWordCount(selectedChapter.content) }} 字</span>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <button
                  class="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors duration-200"
                  :class="selectedChapter?.content
                    ? 'border-[#FFE500]/30 text-[#FFE500] hover:bg-[#FFE500]/10'
                    : 'border-[#2A2A2A] text-[#555] cursor-not-allowed'"
                  :disabled="!selectedChapter?.content"
                  @click="exportChapterAsTxt"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v16h16V4m-4 4l-4-4-4 4m4-4v12" />
                  </svg>
                  导出TXT
                </button>
                <span v-if="selectedChapter.generation_status"
                  class="px-3 py-1 text-xs font-medium rounded-full"
                  :class="getStatusColor(selectedChapter.generation_status)">
                  {{ getStatusLabel(selectedChapter.generation_status) }}
                </span>
              </div>
            </div>

            <!-- Tab Navigation -->
            <div class="flex gap-1">
              <button
                v-for="tab in tabs"
                :key="tab.key"
                @click="activeTab = tab.key"
                class="px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200"
                :class="activeTab === tab.key
                  ? 'bg-[#1C1C1C] text-[#FFE500]'
                  : 'text-[#888] hover:text-white hover:bg-[#1C1C1C]'"
              >
                {{ tab.label }}
                <span v-if="tab.badge && getTabBadgeCount(tab.key)"
                  class="ml-1.5 px-1.5 py-0.5 text-xs rounded-full"
                  :class="activeTab === tab.key ? 'bg-[#FFE500]/15 text-[#FFE500]' : 'bg-[#2A2A2A] text-[#888]'">
                  {{ getTabBadgeCount(tab.key) }}
                </span>
              </button>
            </div>
          </header>

          <!-- Tab Content -->
          <article class="flex-1 h-full overflow-y-auto min-h-0 overscroll-contain">
            <!-- 正文 Tab -->
            <div v-show="activeTab === 'content'" class="px-2 py-3">
              <div class="max-w-full space-y-4">
                <!-- Summary Cards -->
                <div v-if="selectedChapter.summary || selectedChapter.real_summary" class="grid gap-4">
                  <div v-if="selectedChapter.summary" class="bg-blue-500/8 border border-blue-500/15 rounded-xl p-4">
                    <h5 class="text-xs font-semibold text-blue-300 mb-2 flex items-center gap-1.5">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      计划大纲
                    </h5>
                    <p class="text-sm text-blue-200/80 leading-relaxed">{{ selectedChapter.summary }}</p>
                  </div>
                  <div v-if="selectedChapter.real_summary" class="bg-[#2ED573]/8 border border-[#2ED573]/15 rounded-xl p-4">
                    <h5 class="text-xs font-semibold text-[#2ED573] mb-2 flex items-center gap-1.5">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                      </svg>
                      实际内容概要
                    </h5>
                    <div class="prose prose-sm max-w-none text-[#2ED573]/80" v-html="renderMarkdown(selectedChapter.real_summary)"></div>
                  </div>
                </div>

                <!-- Main Content -->
                <div class="p-4 sm:p-6 rounded-xl bg-[#141414] border border-[#2A2A2A]">
                  <div class="text-base text-[#E0E0E0] leading-8 whitespace-pre-wrap font-serif">
                    {{ selectedChapter.content || '暂无内容' }}
                  </div>
                </div>
              </div>
            </div>

            <!-- 版本 Tab -->
            <div v-show="activeTab === 'versions'" class="px-2 py-3">
              <div class="max-w-full">
                <div v-if="selectedChapter.versions && selectedChapter.versions.length > 0" class="space-y-4">
                  <div v-for="(version, index) in selectedChapter.versions" :key="index"
                    class="border border-[#2A2A2A] rounded-xl p-5 hover:border-[#FFE500]/30 hover:shadow-md hover:shadow-[#FFE500]/5 transition-all duration-200 group cursor-pointer bg-[#141414]"
                    @click="openVersionModal(version, index)">
                    <div class="flex items-center justify-between mb-3">
                      <h5 class="text-sm font-semibold text-white flex items-center gap-2">
                        <span class="w-6 h-6 bg-[#FFE500]/15 text-[#FFE500] rounded-full flex items-center justify-center text-xs font-bold">
                          {{ index + 1 }}
                        </span>
                        版本 {{ index + 1 }}
                      </h5>
                      <div class="flex items-center gap-3">
                        <span class="text-xs text-[#888]">{{ calculateWordCount(version) }} 字</span>
                        <span class="text-xs font-medium text-[#FFE500] opacity-0 group-hover:opacity-100 transition-opacity">
                          点击查看全文 →
                        </span>
                      </div>
                    </div>
                    <div class="text-sm text-[#AAAAAA] leading-7 whitespace-pre-wrap line-clamp-4">
                      {{ version }}
                    </div>
                  </div>
                </div>
                <div v-else class="text-center py-12 text-[#555]">
                  暂无版本记录
                </div>
              </div>
            </div>

            <!-- 评审 Tab -->
            <div v-show="activeTab === 'evaluation'" class="px-2 py-3">
              <div class="max-w-full">
                <div v-if="evaluationData" class="space-y-4">
                  <!-- 最佳选择 -->
                  <div v-if="evaluationData.best_choice" class="bg-gradient-to-br from-[#FFE500]/8 to-[#FFE500]/4 border border-[#FFE500]/20 rounded-xl p-4">
                    <div class="flex items-start gap-4">
                      <div class="w-12 h-12 bg-[#FFE500] rounded-xl flex items-center justify-center flex-shrink-0">
                        <svg class="w-7 h-7 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                        </svg>
                      </div>
                      <div class="flex-1">
                        <h5 class="text-lg font-bold text-[#FFE500] mb-2">最佳版本选择</h5>
                        <div class="flex items-center gap-2 mb-3">
                          <span class="px-3 py-1 bg-[#FFE500] text-black text-sm font-bold rounded-full">
                            版本 {{ evaluationData.best_choice }}
                          </span>
                        </div>
                        <p v-if="evaluationData.reason_for_choice" class="text-sm text-[#CCCCCC] leading-relaxed">
                          {{ evaluationData.reason_for_choice }}
                        </p>
                      </div>
                    </div>
                  </div>

                  <!-- 各版本详细评审 -->
                  <div v-if="evaluationData.evaluation" class="space-y-4">
                    <div v-for="(versionEval, versionKey) in evaluationData.evaluation" :key="versionKey"
                      class="border border-[#2A2A2A] rounded-xl overflow-hidden bg-[#141414]"
                      :class="isSelectedVersion(versionKey, evaluationData.best_choice) ? 'ring-2 ring-[#FFE500]/40' : ''">
                      <!-- 版本标题 -->
                      <div class="px-5 py-3 bg-[#1C1C1C] border-b border-[#2A2A2A] flex items-center justify-between">
                        <h6 class="font-bold text-white flex items-center gap-2">
                          <span class="w-6 h-6 bg-[#2A2A2A] text-[#CCCCCC] rounded-full flex items-center justify-center text-xs">
                            {{ getVersionNumber(versionKey) }}
                          </span>
                          {{ getVersionLabel(versionKey) }}
                        </h6>
                        <span v-if="isSelectedVersion(versionKey, evaluationData.best_choice)"
                          class="px-2.5 py-1 bg-[#FFE500]/15 text-[#FFE500] text-xs font-semibold rounded-full">
                          最佳
                        </span>
                      </div>

                      <div class="p-4 space-y-3">
                        <!-- 优点 -->
                        <div v-if="versionEval.pros && versionEval.pros.length > 0"
                          class="bg-[#2ED573]/8 border border-[#2ED573]/15 rounded-lg p-3">
                          <h6 class="text-xs font-bold text-[#2ED573] mb-2 flex items-center gap-1.5">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                            </svg>
                            优点
                          </h6>
                          <ul class="space-y-1.5">
                            <li v-for="(item, idx) in versionEval.pros" :key="idx"
                              class="flex items-start gap-2 text-xs text-[#2ED573]/80 leading-relaxed">
                              <span class="w-1 h-1 bg-[#2ED573] rounded-full mt-1.5 flex-shrink-0"></span>
                              <span>{{ item }}</span>
                            </li>
                          </ul>
                        </div>

                        <!-- 缺点 -->
                        <div v-if="versionEval.cons && versionEval.cons.length > 0"
                          class="bg-[#FF4757]/8 border border-[#FF4757]/15 rounded-lg p-3">
                          <h6 class="text-xs font-bold text-[#FF4757] mb-2 flex items-center gap-1.5">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                            缺点
                          </h6>
                          <ul class="space-y-1.5">
                            <li v-for="(item, idx) in versionEval.cons" :key="idx"
                              class="flex items-start gap-2 text-xs text-[#FF4757]/80 leading-relaxed">
                              <span class="w-1 h-1 bg-[#FF4757] rounded-full mt-1.5 flex-shrink-0"></span>
                              <span>{{ item }}</span>
                            </li>
                          </ul>
                        </div>

                        <!-- 总体评价 -->
                        <div v-if="versionEval.overall_review"
                          class="bg-blue-500/8 border border-blue-500/15 rounded-lg p-3">
                          <h6 class="text-xs font-bold text-blue-300 mb-2">总体评价</h6>
                          <p class="text-xs text-blue-200/80 leading-relaxed">{{ versionEval.overall_review }}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- 简单格式兼容 -->
                  <div v-else-if="evaluationData.decision || evaluationData.feedback" class="space-y-4">
                    <!-- 评审决策 -->
                    <div v-if="evaluationData.decision" class="bg-gradient-to-br from-[#FFE500]/8 to-blue-500/5 border border-[#FFE500]/20 rounded-xl p-4">
                      <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 bg-[#FFE500] rounded-lg flex items-center justify-center">
                          <svg class="w-6 h-6 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <div>
                          <h5 class="text-sm font-bold text-[#FFE500]">评审决策</h5>
                          <p class="text-xs text-[#CCCCCC]">{{ evaluationData.decision }}</p>
                        </div>
                      </div>
                    </div>

                    <!-- 评分卡片 -->
                    <div v-if="evaluationData.scores" class="grid grid-cols-2 md:grid-cols-3 gap-4">
                      <div v-for="(score, key) in evaluationData.scores" :key="key"
                        class="bg-[#141414] border border-[#2A2A2A] rounded-xl p-4 hover:border-[#FFE500]/20 transition-all">
                        <div class="flex items-center justify-between mb-2">
                          <span class="text-xs font-medium text-[#888]">{{ getScoreLabel(key) }}</span>
                          <span class="text-lg font-bold" :class="getScoreColor(score)">{{ score }}</span>
                        </div>
                        <div class="w-full bg-[#2A2A2A] rounded-full h-2">
                          <div class="h-2 rounded-full transition-all duration-300"
                            :class="getScoreBarColor(score)"
                            :style="{ width: `${(score / 10) * 100}%` }"></div>
                        </div>
                      </div>
                    </div>

                    <!-- 详细反馈 -->
                    <div v-if="evaluationData.feedback"
                      class="bg-[#141414] border border-[#2A2A2A] rounded-xl p-4">
                      <h5 class="text-sm font-bold text-white mb-3">详细反馈</h5>
                      <p class="text-sm text-[#CCCCCC] leading-relaxed whitespace-pre-wrap">{{ evaluationData.feedback }}</p>
                    </div>
                  </div>
                </div>

                <div v-else class="text-center py-12">
                  <div class="w-16 h-16 bg-[#1C1C1C] rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg class="w-8 h-8 text-[#555]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <p class="text-[#555]">暂无评审意见</p>
                </div>
              </div>
            </div>
          </article>
        </template>

        <!-- Empty State -->
        <div v-else class="h-full flex items-center justify-center text-[#555]">
          <div class="text-center">
            <svg class="w-16 h-16 mx-auto mb-3 text-[#333]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <p class="text-sm">请选择章节查看详细内容</p>
          </div>
        </div>
      </section>
    </div>

    <!-- 版本全文弹窗 -->
    <transition
      enter-active-class="transition-all duration-300"
      leave-active-class="transition-all duration-300"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="versionModal.show" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
        @click="closeVersionModal">
        <div class="bg-[#141414] border border-[#2A2A2A] rounded-2xl shadow-2xl max-w-4xl w-full max-h-[85vh] overflow-hidden"
          @click.stop>
          <!-- Modal Header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-[#2A2A2A] bg-[#1C1C1C]">
            <div class="flex items-center gap-3">
              <span class="w-8 h-8 bg-[#FFE500] text-black rounded-full flex items-center justify-center text-sm font-bold">
                {{ versionModal.index + 1 }}
              </span>
              <div>
                <h3 class="text-lg font-bold text-white">版本 {{ versionModal.index + 1 }}</h3>
                <p class="text-xs text-[#888]">{{ calculateWordCount(versionModal.content) }} 字</p>
              </div>
            </div>
            <button @click="closeVersionModal"
              class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-[#2A2A2A] transition-colors">
              <svg class="w-5 h-5 text-[#888]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <!-- Modal Content -->
          <div class="overflow-y-auto p-6 max-h-[calc(85vh-5rem)]">
            <div class="text-base text-[#E0E0E0] leading-8 whitespace-pre-wrap font-serif">
              {{ versionModal.content }}
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NovelAPI } from '@/api/novel'
import { AdminAPI } from '@/api/admin'
import { useRoute } from 'vue-router'
import { marked } from 'marked'

interface ChapterItem {
  chapter_number: number
  title?: string | null
  summary?: string | null
  content?: string | null
  word_count?: number
}

interface ChapterDetail extends ChapterItem {
  real_summary?: string | null
  versions?: string[] | null
  evaluation?: string | null
  generation_status?: string
}

const props = defineProps<{
  chapters: ChapterItem[]
  isAdmin?: boolean
}>()

const route = useRoute()
const projectId = route.params.id as string

const selectedChapter = ref<ChapterDetail | null>(null)
const isLoading = ref(false)
const error = ref<string | null>(null)
const activeTab = ref<'content' | 'versions' | 'evaluation'>('content')

const showChapterList = ref(false)

const versionModal = ref({
  show: false,
  content: '',
  index: 0
})

const chapterCache = new Map<number, ChapterDetail>()

const chapters = computed(() =>
  [...(props.chapters || [])].sort((a, b) => a.chapter_number - b.chapter_number)
)

const tabs = [
  { key: 'content' as const, label: '正文', badge: false },
  { key: 'versions' as const, label: '版本', badge: true },
  { key: 'evaluation' as const, label: '评审', badge: false }
]

const calculateWordCount = (content: string | null | undefined): number => {
  if (!content) return 0
  return content.replace(/\s/g, '').length
}

const getStatusLabel = (status: string): string => {
  const statusMap: Record<string, string> = {
    'not_generated': '未生成',
    'generating': '生成中',
    'evaluating': '评审中',
    'selecting': '选择中',
    'failed': '生成失败',
    'evaluation_failed': '评审失败',
    'waiting_for_confirm': '待确认',
    'successful': '已完成'
  }
  return statusMap[status] || status
}

const getStatusColor = (status: string): string => {
  const colorMap: Record<string, string> = {
    'not_generated': 'bg-[#2A2A2A] text-[#888]',
    'generating': 'bg-blue-500/15 text-blue-400',
    'evaluating': 'bg-purple-500/15 text-purple-400',
    'selecting': 'bg-[#FFE500]/15 text-[#FFE500]',
    'failed': 'bg-[#FF4757]/15 text-[#FF4757]',
    'evaluation_failed': 'bg-orange-500/15 text-orange-400',
    'waiting_for_confirm': 'bg-amber-500/15 text-amber-400',
    'successful': 'bg-[#2ED573]/15 text-[#2ED573]'
  }
  return colorMap[status] || 'bg-[#2A2A2A] text-[#888]'
}

const getTabBadgeCount = (tabKey: string): number => {
  if (!selectedChapter.value) return 0
  if (tabKey === 'versions') {
    return selectedChapter.value.versions?.length || 0
  }
  return 0
}

const sanitizeFileName = (name: string): string => {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

const exportChapterAsTxt = () => {
  const chapter = selectedChapter.value
  if (!chapter) return

  const title = chapter.title?.trim() || `第${chapter.chapter_number}章`
  const safeTitle = sanitizeFileName(title) || `chapter-${chapter.chapter_number}`
  const content = chapter.content ?? ''
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeTitle}.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const openVersionModal = (content: string, index: number) => {
  versionModal.value = { show: true, content, index }
}

const closeVersionModal = () => {
  versionModal.value.show = false
}

const evaluationData = computed(() => {
  if (!selectedChapter.value?.evaluation) return null
  try {
    return JSON.parse(selectedChapter.value.evaluation)
  } catch {
    return { feedback: selectedChapter.value.evaluation }
  }
})

const getScoreLabel = (key: string | number): string => {
  const normalizedKey = typeof key === 'number' ? key.toString() : key
  const labelMap: Record<string, string> = {
    'plot': '情节', 'character': '人物', 'writing': '文笔', 'logic': '逻辑',
    'emotion': '情感', 'creativity': '创意', 'coherence': '连贯性', 'engagement': '吸引力'
  }
  return labelMap[normalizedKey] || normalizedKey
}

const getScoreColor = (score: number): string => {
  if (score >= 8) return 'text-[#2ED573]'
  if (score >= 6) return 'text-blue-400'
  if (score >= 4) return 'text-amber-400'
  return 'text-[#FF4757]'
}

const getScoreBarColor = (score: number): string => {
  if (score >= 8) return 'bg-[#2ED573]'
  if (score >= 6) return 'bg-blue-500'
  if (score >= 4) return 'bg-amber-500'
  return 'bg-[#FF4757]'
}

const getVersionNumber = (versionKey: string | number): number => {
  const normalizedKey = typeof versionKey === 'number' ? versionKey.toString() : versionKey
  const match = normalizedKey.match(/\d+/)
  return match ? parseInt(match[0]) : 0
}

const getVersionLabel = (versionKey: string | number): string => {
  const num = getVersionNumber(versionKey)
  return `版本 ${num}`
}

const isSelectedVersion = (versionKey: string | number, bestChoice?: number): boolean => {
  if (!bestChoice) return false
  return getVersionNumber(versionKey) === bestChoice
}

const renderMarkdown = (text: string | null | undefined): string => {
  if (!text) return ''
  try {
    return marked.parse(text, { breaks: true }) as string
  } catch (error) {
    console.error('Markdown 渲染失败:', error)
    return text
  }
}

const loadChapterDetail = async (chapterNumber: number) => {
  if (chapterCache.has(chapterNumber)) {
    selectedChapter.value = chapterCache.get(chapterNumber)!
    return
  }

  isLoading.value = true
  error.value = null

  try {
    const detail: ChapterDetail = props.isAdmin
      ? await AdminAPI.getNovelChapter(projectId, chapterNumber)
      : await NovelAPI.getChapter(projectId, chapterNumber)

    chapterCache.set(chapterNumber, detail)
    selectedChapter.value = detail
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载失败'
    console.error('加载章节详情失败:', err)
  } finally {
    isLoading.value = false
  }
}

watch(
  chapters,
  async (list) => {
    if (list.length === 0) {
      selectedChapter.value = null
      return
    }
    if (!selectedChapter.value && list.length > 0) {
      await loadChapterDetail(list[0].chapter_number)
    }
  },
  { immediate: true }
)

const selectChapter = async (chapterNumber: number) => {
  activeTab.value = 'content'
  await loadChapterDetail(chapterNumber)
  showChapterList.value = false
}

const isAdmin = computed(() => props.isAdmin ?? false)

defineExpose({
  focusChapter: async (chapterNumber: number) => {
    const target = chapters.value.find(ch => ch.chapter_number === chapterNumber)
    if (target) {
      await loadChapterDetail(chapterNumber)
    }
  }
})
</script>

<style scoped>
.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-4 {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-6 {
  display: -webkit-box;
  -webkit-line-clamp: 6;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>

<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'ChaptersSection'
})
</script>
