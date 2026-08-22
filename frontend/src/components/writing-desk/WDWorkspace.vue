<!-- AIMETA P=写作台工作区_主编辑区域|R=章节编辑_生成|NR=不含侧边栏|E=component:WDWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="flex-1 min-w-0 h-full">
    <div class="md-card md-card-elevated h-full flex flex-col" style="border-radius: var(--md-radius-xl);">
      <!-- 章节工作区头部：默认一条工具栏，规划/大纲收进「要点」以免挡住正文 -->
      <div v-if="selectedChapterNumber" class="wd-chapter-bar flex-shrink-0">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="min-w-0 flex items-center gap-2 flex-wrap">
            <h2 class="md-title-medium font-semibold whitespace-nowrap">第{{ selectedChapterNumber }}章</h2>
            <span
              :class="[
                'md-chip',
                isChapterCompleted(selectedChapterNumber)
                  ? 'm3-chip-success'
                  : 'm3-chip-neutral'
              ]"
            >
              {{ isChapterCompleted(selectedChapterNumber) ? '已完成' : '未完成' }}
            </span>
            <h3 class="md-title-small md-on-surface truncate max-w-[42vw]">{{ selectedChapterOutline?.title || '未知标题' }}</h3>
            <button
              type="button"
              class="wd-brief-toggle"
              :aria-expanded="briefOpen"
              @click="briefOpen = !briefOpen"
            >
              <svg
                class="wd-brief-toggle__chevron"
                :class="{ 'is-open': briefOpen }"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
              >
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
              </svg>
              {{ briefOpen ? '收起要点' : '本章要点' }}
            </button>
            <span
              v-if="!briefOpen && chapterPlanning.coolpoint"
              class="wd-planning-glance wd-planning-glance--accent"
              :title="chapterPlanning.coolpoint"
            >
              <span class="wd-planning-glance__label">爽点</span>
              <span class="wd-planning-glance__text">{{ chapterPlanning.coolpoint }}</span>
            </span>
            <span
              v-if="!briefOpen && chapterPlanning.chapter_function"
              class="wd-planning-glance"
              :title="chapterPlanning.chapter_function"
            >
              <span class="wd-planning-glance__label">功能</span>
              <span class="wd-planning-glance__text">{{ chapterPlanning.chapter_function }}</span>
            </span>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <!-- 写作模板按钮 -->
            <button
              @click="showTemplateSelector = true"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 whitespace-nowrap"
              title="使用写作模板"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clip-rule="evenodd"></path>
              </svg>
              写作模板
            </button>
            <button
              @click="$emit('toggleCodex')"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 whitespace-nowrap"
              title="世界观设定典"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z"></path>
              </svg>
              设定典
            </button>
            <button
              v-if="isChapterCompleted(selectedChapterNumber)"
              @click="openEditModal"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 whitespace-nowrap"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
              </svg>
              手动编辑
            </button>
            <button
              v-if="isChapterCompleted(selectedChapterNumber)"
              @click="showRevisionHistory = true"
              class="md-btn md-btn-outlined md-ripple flex items-center gap-2 whitespace-nowrap"
              title="查看不可变版本、差异和恢复记录"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l2.5 1.5M21 12a9 9 0 11-18 0 9 9 0 0118 0Z" /></svg>
              修订历史
            </button>
            <button
              v-if="isChapterCompleted(selectedChapterNumber)"
              @click="confirmRegenerateChapter"
              :disabled="generatingChapter === selectedChapterNumber"
              class="md-btn md-btn-outlined md-ripple flex items-center gap-2 whitespace-nowrap disabled:opacity-50"
              title="会覆盖本章现有正文。卡住一句请用选区改写。"
            >
              <svg v-if="generatingChapter === selectedChapterNumber" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              {{ generatingChapter === selectedChapterNumber ? '起草中...' : '重新起草' }}
            </button>
            <button
              v-else
              @click="confirmRegenerateChapter"
              :disabled="generatingChapter === selectedChapterNumber"
              class="md-btn md-btn-filled md-ripple flex items-center gap-2 whitespace-nowrap disabled:opacity-50"
            >
              <svg v-if="generatingChapter === selectedChapterNumber" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              {{ generatingChapter === selectedChapterNumber ? '起草中...' : '起草本章' }}
            </button>
          </div>
        </div>

        <p v-if="revisionHintText" class="mt-2 text-xs leading-5 px-2 py-1.5 rounded" style="background:rgba(201,162,39,0.12);color:#C9A227;">
          修订提示：{{ revisionHintText }}
        </p>

        <div v-if="briefOpen" class="wd-chapter-brief">
          <p class="md-body-small md-on-surface-variant">{{ selectedChapterOutline?.summary || '暂无章节描述' }}</p>
          <div v-if="outlineEditing" class="mt-3 space-y-2">
            <input v-model="outlineDraft.title" class="md-input w-full" placeholder="章标题" />
            <textarea v-model="outlineDraft.summary" rows="3" class="md-textarea w-full" placeholder="章摘要" />
            <button class="md-btn md-btn-filled" :disabled="outlineSaving" @click="saveOutlineText">
              {{ outlineSaving ? '保存中…' : '保存大纲' }}
            </button>
          </div>
          <button v-else class="md-btn md-btn-text !px-2 !py-0 text-xs mt-2" @click="startOutlineEdit">编辑大纲</button>

          <section v-if="selectedChapterOutline" class="wd-planning-card mt-3">
            <div class="wd-planning-card__header">
              <button
                type="button"
                class="wd-planning-card__toggle"
                :aria-expanded="planningDetailsOpen || planningEditing"
                aria-controls="chapter-planning-details"
                @click="planningDetailsOpen = !planningDetailsOpen"
              >
                <span class="wd-planning-card__icon" aria-hidden="true">规</span>
                <span class="wd-planning-card__heading">
                  <span class="wd-planning-card__title">本章规划</span>
                  <span class="wd-planning-card__meta">
                    {{ planningFieldCount ? `已填写 ${planningFieldCount} 项约束` : '尚未填写，起草时将仅参考章纲' }}
                  </span>
                </span>
                <svg
                  class="wd-planning-card__chevron"
                  :class="{ 'is-open': planningDetailsOpen || planningEditing }"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
                </svg>
              </button>
              <button
                type="button"
                class="wd-planning-card__edit"
                @click="togglePlanningEdit"
              >
                {{ planningEditing ? '取消' : '编辑' }}
              </button>
            </div>

            <p
              v-if="!planningDetailsOpen && !planningEditing && planningPreview"
              class="wd-planning-card__preview"
              :title="planningPreview"
            >
              {{ planningPreview }}
            </p>

            <div
              v-if="planningDetailsOpen || planningEditing"
              id="chapter-planning-details"
              class="wd-planning-card__body"
            >
              <div v-if="!planningEditing && hasChapterPlanning" class="wd-planning-grid">
                <div v-if="chapterPlanning.chapter_function" class="wd-planning-item">
                  <span class="wd-planning-item__label">章功能</span>
                  <p>{{ chapterPlanning.chapter_function }}</p>
                </div>
                <div v-if="chapterPlanning.hook_type" class="wd-planning-item">
                  <span class="wd-planning-item__label">章末钩子</span>
                  <p>{{ chapterPlanning.hook_type }}</p>
                </div>
                <div v-if="chapterPlanning.coolpoint" class="wd-planning-item wd-planning-item--accent wd-planning-item--wide">
                  <span class="wd-planning-item__label">核心爽点</span>
                  <p>{{ chapterPlanning.coolpoint }}</p>
                </div>
                <div v-if="chapterPlanning.foreshadowing_ops?.length" class="wd-planning-item wd-planning-item--wide">
                  <span class="wd-planning-item__label">伏笔安排</span>
                  <div class="wd-planning-tags">
                    <span v-for="(item, index) in chapterPlanning.foreshadowing_ops" :key="`${item.op}-${item.name}-${index}`">
                      {{ foreshadowingOperationLabel(item.op) }} · {{ item.name }}
                    </span>
                  </div>
                </div>
                <div v-if="chapterPlanning.must_not_include?.length" class="wd-planning-item wd-planning-item--warning wd-planning-item--wide">
                  <span class="wd-planning-item__label">禁写提醒</span>
                  <ul>
                    <li v-for="(item, index) in chapterPlanning.must_not_include" :key="`${item}-${index}`">{{ item }}</li>
                  </ul>
                </div>
              </div>
              <div v-else-if="!planningEditing" class="wd-planning-empty">
                暂无额外约束。您可以保持为空，AI 将按章节概要起草。
              </div>
              <div v-else class="space-y-2">
                <label class="wd-planning-field">
                  <span>章功能</span>
                  <input v-model="planningDraft.chapter_function" class="md-input w-full" placeholder="例如：铺垫 / 爽点 / 转折 / 收束" />
                </label>
                <label class="wd-planning-field">
                  <span>章末钩子</span>
                  <input v-model="planningDraft.hook_type" class="md-input w-full" placeholder="例如：新危机、身份揭晓、线索反转" />
                </label>
                <label class="wd-planning-field">
                  <span>核心爽点</span>
                  <input v-model="planningDraft.coolpoint" class="md-input w-full" placeholder="本章最需要兑现的情绪价值" />
                </label>
                <label class="wd-planning-field">
                  <span>禁写提醒</span>
                  <textarea v-model="mustNotText" rows="2" class="md-textarea w-full" placeholder="每行一条；不需要可留空" />
                </label>
                <div class="flex justify-end">
                  <button class="md-btn md-btn-filled" :disabled="planningSaving" @click="saveChapterPlanning">
                    {{ planningSaving ? '保存中…' : '保存规划' }}
                  </button>
                </div>
              </div>
            </div>
          </section>

          <div v-if="canShowPredictionPanel" class="wd-prediction-row mt-2">
            <button
              type="button"
              @click="showPrediction = !showPrediction"
              :disabled="!outlinePrediction"
              class="wd-prediction-row__toggle md-ripple"
              :aria-expanded="showPrediction"
            >
              <span class="wd-prediction-row__icon" aria-hidden="true">演</span>
              <span class="wd-prediction-row__heading">
                <span>剧情推演</span>
                <small>{{ outlinePrediction ? '已生成，可展开查看章节节拍' : '尚未生成' }}</small>
              </span>
              <svg
                class="wd-prediction-row__chevron"
                :class="{ 'is-open': showPrediction }"
                fill="currentColor" viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path>
              </svg>
            </button>
            <button
              v-if="isChapterCompleted(selectedChapterNumber)"
              type="button"
              @click="handleGeneratePrediction"
              :disabled="generatingPrediction"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-1 !px-3 !py-1.5 disabled:opacity-50 whitespace-nowrap"
            >
              <svg v-if="generatingPrediction" class="w-3.5 h-3.5 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
              </svg>
              {{ generatingPrediction ? '推演中...' : (outlinePrediction ? '重新推演' : '生成推演') }}
            </button>
          </div>
        </div>
      </div>

      <!-- 章节内容展示区 -->
      <div class="md-card-content flex-1 overflow-y-auto">
        <!-- 推演详情面板（在内容区域内，可跟随滚动） -->
        <div v-if="showPrediction && outlinePrediction && canShowPredictionPanel" ref="predictionPanelRef" class="m3-prediction-panel mb-4">
          <div class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-xl);">
            <div class="flex items-center justify-between mb-3">
              <h4 class="md-title-small font-semibold flex items-center gap-2">
                <svg class="w-4 h-4" style="color: var(--md-primary);" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M11.3 1.046A1 1 0 0112 2v5h4a1 1 0 01.82 1.573l-7 10A1 1 0 018 18v-5H4a1 1 0 01-.82-1.573l7-10a1 1 0 011.12-.38z" clip-rule="evenodd"></path>
                </svg>
                剧情推演详情
              </h4>
              <button
                @click="showPrediction = false"
                class="md-icon-btn md-ripple !w-7 !h-7"
                title="收起推演"
              >
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clip-rule="evenodd"></path>
                </svg>
              </button>
            </div>
            <div class="max-h-80 overflow-y-auto space-y-2 pr-1">
              <div v-for="section in predictionSections" :key="section.key" class="md-card md-card-filled p-3" style="border-radius: var(--md-radius-md);">
                <h4 class="md-label-large font-medium mb-1.5" :style="{ color: section.color }">{{ section.label }}</h4>
                <ul class="space-y-0.5">
                  <li v-for="(item, i) in section.items" :key="i" class="md-body-small md-on-surface-variant flex gap-2">
                    <span class="shrink-0">{{ section.icon }}</span>
                    <span>{{ item }}</span>
                  </li>
                </ul>
              </div>

              <!-- Beats 节拍编排 -->
              <div v-if="outlinePrediction.beats?.length" class="md-card md-card-filled p-3" style="border-radius: var(--md-radius-md);">
                <h4 class="md-label-large font-medium mb-1.5" style="color: var(--md-primary)">节拍编排</h4>
                <div class="space-y-1.5">
                  <div v-for="(beat, i) in outlinePrediction.beats" :key="i" class="flex items-start gap-2">
                    <span class="shrink-0 w-4 h-4 rounded-full text-[10px] flex items-center justify-center text-white font-medium"
                          :style="{ backgroundColor: beatColor(beat.type) }">{{ i + 1 }}</span>
                    <div>
                      <span class="md-label-small font-medium" :style="{ color: beatColor(beat.type) }">{{ beatLabel(beat.type) }}</span>
                      <span class="md-body-small md-on-surface-variant ml-1">{{ beat.content }}</span>
                      <span class="md-label-small ml-1" style="color: var(--md-outline);">{{ beat.emotion }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <component
          :is="currentComponent"
          v-bind="currentComponentProps"
          @hideVersionSelector="$emit('hideVersionSelector')"
          @update:selectedVersionIndex="$emit('update:selectedVersionIndex', $event)"
          @showVersionDetail="$emit('showVersionDetail', $event)"
          @openVersionCompare="$emit('openVersionCompare')"
          @confirmVersionSelection="$emit('confirmVersionSelection')"
          @generateChapter="(...args: any[]) => $emit('generateChapter', ...args)"
          @showVersionSelector="$emit('showVersionSelector')"
          @requestPrediction="$emit('requestPrediction', $event)"
          @regenerateChapter="$emit('regenerateChapter')"
          @evaluateChapter="$emit('evaluateChapter')"
          @showEvaluationDetail="$emit('showEvaluationDetail')"
        />
      </div>
    </div>

    <!-- 编辑章节内容模态框 -->
    <div v-if="showEditModal" class="md-dialog-overlay">
      <div class="md-dialog w-full h-full max-w-5xl m3-editor-dialog">
        <!-- 模态框头部 -->
        <div class="flex items-center justify-between p-6 border-b" style="border-bottom-color: var(--md-outline-variant);">
          <h3 class="md-title-large font-semibold">
            编辑第{{ selectedChapterNumber }}章内容
          </h3>
          <button
            @click="() => closeEditModal()"
            class="md-icon-btn md-ripple"
          >
            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
            </svg>
          </button>
        </div>

        <div
          v-if="!isEditorOnline"
          class="mx-6 mt-4 rounded-lg px-4 py-3 text-sm"
          style="background: rgba(201, 162, 39, 0.14); color: #d9b832; border: 1px solid rgba(201, 162, 39, 0.36);"
        >
          离线编辑中：内容已持续保存到本机，恢复网络后会自动重试远端保存。
        </div>
        <div
          v-else-if="editorStatus"
          class="mx-6 mt-4 rounded-lg px-4 py-3 text-sm"
          style="background: var(--md-surface-container); color: var(--md-on-surface-variant); border: 1px solid var(--md-outline-variant);"
        >
          {{ editorStatus }}
        </div>

        <div
          v-if="editConflict"
          class="mx-6 mt-4 rounded-lg p-4"
          style="background: rgba(186, 26, 26, 0.1); border: 1px solid rgba(186, 26, 26, 0.5);"
        >
          <p class="font-semibold" style="color: var(--md-on-surface);">发现版本冲突</p>
          <p class="mt-1 text-sm md-on-surface-variant">
            远端已更新为修订 {{ editConflict.revision_id }}。你的本地文本仍保留在此，不会被覆盖。
          </p>
          <div class="mt-3 flex flex-wrap gap-2">
            <button class="md-btn md-btn-tonal md-ripple" :disabled="isSaving" @click="keepLocalDraft">
              保留本地
            </button>
            <button class="md-btn md-btn-outlined md-ripple" :disabled="isSaving" @click="useRemoteDraft">
              使用远端
            </button>
            <button class="md-btn md-btn-filled md-ripple" :disabled="isSaving" @click="saveConflictAsBranch">
              另存为分支
            </button>
          </div>
        </div>

        <!-- 模态框内容 -->
        <div class="flex-1 p-6 overflow-hidden">
          <div class="flex flex-col h-full">
            <label class="md-text-field-label mb-2">
              章节内容
            </label>
            <textarea
              v-model="editingContent"
              class="md-textarea flex-1 w-full resize-none"
              placeholder="请输入章节内容..."
              :disabled="isSaving || !!editConflict"
            ></textarea>
            <div class="md-body-small md-on-surface-variant mt-2">
              字数统计: {{ editingContent.length }}
            </div>
          </div>
        </div>

        <!-- 模态框底部 -->
        <div class="flex items-center justify-end gap-3 p-6 border-t" style="border-top-color: var(--md-outline-variant);">
          <button
            @click="() => closeEditModal()"
            :disabled="isSaving"
            class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
          >
            取消
          </button>
          <button
            v-if="!editConflict"
            @click="saveEditedContent"
            :disabled="isSaving || !editingContent.trim()"
            class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
          >
            <svg v-if="isSaving" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
            </svg>
            {{ isSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 写作模板选择器模态框 -->
    <Teleport to="body">
      <div v-if="showTemplateSelector" class="modal-overlay" @click.self="showTemplateSelector = false">
        <div class="modal-content">
          <TemplateSelector
            :project-id="project?.id ?? ''"
            :chapter-number="selectedChapterNumber ?? 0"
            @apply="handleTemplateApply"
          />
        </div>
      </div>
    </Teleport>
    <WDVersionHistoryModal
      :show="showRevisionHistory"
      :project-id="project?.id || ''"
      :chapter-number="selectedChapterNumber || 0"
      :revision-id="selectedChapter?.revision_id || 0"
      :content-hash="selectedChapter?.content_hash"
      @close="showRevisionHistory = false"
      @restored="handleHistoryRestored"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import { useChapterDraft } from '@/composables/useChapterDraft'
import { useNovelStore } from '@/stores/novel'
import { isVersionConflictError } from '@/api/novel'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
  NovelProject,
  ChapterPrediction,
  ChapterPlanning,
  ChapterRevision,
  ChapterSaveRequest,
  ChapterSaveResponse,
} from '@/api/novel'
import type { GenerationProgressView } from '@/composables/useGenerationProgress'
import { formatRevisionHint } from '@/utils/revisionHint'
import TemplateSelector from './TemplateSelector.vue'

const beatColorMap: Record<string, string> = {
  setup: '#6B7280', provoke: '#F59E0B', twist: '#8B5CF6', payoff: '#EF4444', hook: '#3B82F6'
}
const beatLabelMap: Record<string, string> = {
  setup: '铺垫', provoke: '激化', twist: '转折', payoff: '爆发', hook: '悬念'
}
const beatColor = (type: string) => beatColorMap[type] || '#6B7280'
const beatLabel = (type: string) => beatLabelMap[type] || type
import WorkspaceInitial from './workspace/WorkspaceInitial.vue'
import ChapterGenerating from './workspace/ChapterGenerating.vue'
import VersionSelector from './workspace/VersionSelector.vue'
import ChapterContent from './workspace/ChapterContent.vue'
import ChapterFailed from './workspace/ChapterFailed.vue'
import ChapterEmpty from './workspace/ChapterEmpty.vue'
import WDVersionHistoryModal from './WDVersionHistoryModal.vue'

interface Props {
  project: NovelProject | null
  selectedChapterNumber: number | null
  openPredictionTick?: number
  generatingChapter: number | null
  predictionGeneratingChapter?: number | null
  evaluatingChapter: number | null
  showVersionSelector: boolean
  chapterGenerationResult: ChapterGenerationResponse | null
  selectedVersionIndex: number
  availableVersions: ChapterVersion[]
  isSelectingVersion?: boolean
  streamingDraftText?: string
  streamingStage?: string | null
  generationProgress?: GenerationProgressView | null
  saveChapter?: (payload: ChapterSaveRequest) => Promise<ChapterSaveResponse>
  loadChapterRevision?: (chapterNumber: number) => Promise<ChapterRevision>
}

const props = defineProps<Props>()

const emit = defineEmits([
  'regenerateChapter',
  'evaluateChapter',
  'hideVersionSelector',
  'update:selectedVersionIndex',
  'showVersionDetail',
  'openVersionCompare',
  'confirmVersionSelection',
  'generateChapter',
  'showVersionSelector',
  'requestPrediction',
  'showEvaluationDetail',
  'fetchChapterStatus',
  'editChapter',
  'toggleCodex'
])

const novelStore = useNovelStore()
const showRevisionHistory = ref(false)

const handleHistoryRestored = () => {
  // store 已将新快照响应写回当前章节；关闭弹窗避免作者继续看已过时的左右 Diff。
  showRevisionHistory.value = false
}
const briefOpen = ref(false)
const planningDetailsOpen = ref(false)
const planningEditing = ref(false)
const planningSaving = ref(false)
const planningDraft = ref<ChapterPlanning>({})
const mustNotText = ref('')
const outlineEditing = ref(false)
const outlineSaving = ref(false)
const outlineDraft = ref({ title: '', summary: '' })

const selectedChapterOutline = computed(() => {
  if (!props.project?.blueprint?.chapter_outline || props.selectedChapterNumber === null) return null
  return (
    props.project.blueprint.chapter_outline.find(
      (chapter) => chapter.chapter_number === props.selectedChapterNumber,
    ) || null
  )
})

const chapterPlanning = computed<ChapterPlanning>(() => selectedChapterOutline.value?.metadata?.planning || {})
const hasChapterPlanning = computed(() => {
  const planning = chapterPlanning.value
  return Boolean(
    planning.chapter_function?.trim()
    || planning.hook_type?.trim()
    || planning.coolpoint?.trim()
    || planning.foreshadowing_ops?.length
    || planning.must_not_include?.length,
  )
})
const planningFieldCount = computed(() => {
  const planning = chapterPlanning.value
  return [
    planning.chapter_function?.trim(),
    planning.hook_type?.trim(),
    planning.coolpoint?.trim(),
    planning.foreshadowing_ops?.length,
    planning.must_not_include?.length,
  ].filter(Boolean).length
})
const planningPreview = computed(() => {
  const planning = chapterPlanning.value
  const parts = [
    planning.chapter_function?.trim() ? `功能：${planning.chapter_function.trim()}` : '',
    planning.coolpoint?.trim() ? `爽点：${planning.coolpoint.trim()}` : '',
    planning.must_not_include?.length ? `禁写 ${planning.must_not_include.length} 条` : '',
  ].filter(Boolean)
  return parts.join(' · ')
})

const foreshadowingOperationLabels: Record<string, string> = {
  plant: '埋设',
  reinforce: '强化',
  payoff: '回收',
  resolve: '收束',
}
const foreshadowingOperationLabel = (operation: string) => (
  foreshadowingOperationLabels[operation.toLowerCase()] || operation
)

function resetPlanningDraft() {
  const planning = selectedChapterOutline.value?.metadata?.planning || {}
  planningDraft.value = { ...planning }
  mustNotText.value = (planning.must_not_include || []).join('\n')
}

function togglePlanningEdit() {
  if (planningEditing.value) {
    resetPlanningDraft()
    planningEditing.value = false
    return
  }
  resetPlanningDraft()
  planningDetailsOpen.value = true
  planningEditing.value = true
}

watch(
  () => selectedChapterOutline.value,
  (outline) => {
    resetPlanningDraft()
    outlineDraft.value = { title: outline?.title || '', summary: outline?.summary || '' }
    outlineEditing.value = false
  },
  { immediate: true },
)

function startOutlineEdit() {
  briefOpen.value = true
  const outline = selectedChapterOutline.value
  outlineDraft.value = { title: outline?.title || '', summary: outline?.summary || '' }
  outlineEditing.value = true
}

async function saveOutlineText() {
  const outline = selectedChapterOutline.value
  if (!outline) return
  outlineSaving.value = true
  try {
    await novelStore.updateChapterOutline({
      ...outline,
      title: outlineDraft.value.title.trim() || outline.title,
      summary: outlineDraft.value.summary.trim() || outline.summary,
    })
    outlineEditing.value = false
    globalAlert.showSuccess('章纲已更新，下次起草会按新摘要走。', '大纲已保存')
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '保存失败', '章纲')
  } finally {
    outlineSaving.value = false
  }
}

async function saveChapterPlanning() {
  const outline = selectedChapterOutline.value
  if (!outline) return
  planningSaving.value = true
  try {
    const planning: ChapterPlanning = {
      ...planningDraft.value,
      must_not_include: mustNotText.value.split('\n').map((s) => s.trim()).filter(Boolean),
    }
    await novelStore.updateChapterOutline({
      ...outline,
      metadata: { ...(outline.metadata || {}), planning },
    })
    planningEditing.value = false
    planningDetailsOpen.value = true
    globalAlert.showSuccess('本章规划已写入，下次起草会作为约束。', '规划已保存')
  } catch (err) {
    globalAlert.showError(err instanceof Error ? err.message : '保存失败', '本章规划')
  } finally {
    planningSaving.value = false
  }
}

const confirmRegenerateChapter = async () => {
  const completed = props.selectedChapterNumber != null && isChapterCompleted(props.selectedChapterNumber)
  const confirmed = await globalAlert.showConfirm(
    completed
      ? '会覆盖本章现有正文，已改过的段落也会丢掉。卡住一句请先用选区改写。'
      : '将按当前大纲起草本章。',
    completed ? '重新起草确认' : '起草本章',
  )
  if (confirmed) {
    emit('regenerateChapter')
  }
}

// 剧情推演
const showPrediction = ref(false)
const showTemplateSelector = ref(false)
const templatePrompt = ref('')
const generatingPrediction = computed(
  () => props.predictionGeneratingChapter === props.selectedChapterNumber
)
const predictionPanelBlockedStatuses: Chapter['generation_status'][] = [
  'waiting_for_confirm',
  'evaluation_failed',
  'evaluating',
  'selecting'
]

const outlinePrediction = computed<ChapterPrediction | null>(
  () => selectedChapterOutline.value?.metadata?.prediction ?? null
)
const selectedChapterStatus = computed<Chapter['generation_status'] | null>(() => {
  if (props.selectedChapterNumber === null || !props.project?.chapters) {
    return null
  }
  return props.project.chapters.find(
    chapter => chapter.chapter_number === props.selectedChapterNumber
  )?.generation_status ?? null
})
const canShowPredictionPanel = computed(() => {
  if (props.selectedChapterNumber === null) return false
  if (
    selectedChapterStatus.value &&
    predictionPanelBlockedStatuses.includes(selectedChapterStatus.value)
  ) {
    return false
  }
  return isChapterCompleted(props.selectedChapterNumber) || !!outlinePrediction.value
})
const predictionPanelRef = ref<HTMLElement | null>(null)

const predictionSections = computed(() => {
  const p = outlinePrediction.value
  if (!p) return []
  return [
    { key: 'key_points', label: '章节要点', icon: '•', color: 'var(--md-primary)', items: p.key_points || [] },
    { key: 'cool_points', label: '爽点设计', icon: '⚡', color: 'var(--md-tertiary)', items: p.cool_points || [] },
    { key: 'foreshadowing_hooks', label: '伏笔/钩子', icon: '🪝', color: 'var(--md-secondary)', items: p.foreshadowing_hooks || [] },
    { key: 'foreshadowing_targets', label: '需回收伏笔', icon: '🎯', color: 'var(--md-error)', items: p.foreshadowing_targets || [] },
    { key: 'limitations', label: '章节限制', icon: '⚠', color: 'var(--md-on-surface-variant)', items: p.limitations || [] },
  ].filter(s => s.items.length > 0)
})

const handleGeneratePrediction = () => {
  if (!props.selectedChapterNumber || generatingPrediction.value) return
  emit('requestPrediction', props.selectedChapterNumber)
}

// 处理模板应用
const handleTemplateApply = (prompt: string) => {
  showTemplateSelector.value = false
  templatePrompt.value = prompt
  globalAlert.showAlert('模板已应用，写作指令已更新', 'info')
}

const openPredictionPanel = async () => {
  await nextTick()
  if (!outlinePrediction.value || !canShowPredictionPanel.value) return
  showPrediction.value = true
  await nextTick()
  predictionPanelRef.value?.scrollIntoView({
    behavior: 'smooth',
    block: 'nearest',
  })
}

// 编辑模态框状态
const showEditModal = ref(false)
const editingContent = ref('')
const isSaving = ref(false)
const initialEditContent = ref('')
const editBaseline = ref<{ revisionId: number; contentHash: string } | null>(null)
const editorStatus = ref('')
const pendingRemoteRetry = ref(false)
const isEditorOnline = ref(typeof navigator === 'undefined' ? true : navigator.onLine)
const editConflict = ref<ChapterRevision | null>(null)
const chapterDraft = useChapterDraft()

const hasUnsavedEdit = computed(
  () => showEditModal.value && editingContent.value !== initialEditContent.value,
)

const queueLocalDraft = () => {
  if (!showEditModal.value || !hasUnsavedEdit.value || !props.project?.id || !props.selectedChapterNumber || !editBaseline.value) {
    return
  }
  chapterDraft.schedule({
    projectId: props.project.id,
    chapterNumber: props.selectedChapterNumber,
    content: editingContent.value,
    baseRevisionId: editBaseline.value.revisionId,
    baseContentHash: editBaseline.value.contentHash,
  })
}

watch(editingContent, queueLocalDraft)

// 清理版本内容的辅助函数
const cleanVersionContent = (content: string): string => {
  if (!content) return ''
  try {
    const parsed = JSON.parse(content)
    const extractContent = (value: any): string | null => {
      if (!value) return null
      if (typeof value === 'string') return value
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
          if (value[key]) {
            const nested = extractContent(value[key])
            if (nested) return nested
          }
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      content = extracted
    }
  } catch (error) {
    // not a json
  }
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')
  return cleaned
}

const setBaseline = (revision: Pick<ChapterRevision, 'revision_id' | 'content_hash'>) => {
  editBaseline.value = {
    revisionId: revision.revision_id,
    contentHash: revision.content_hash,
  }
}

const ensureEditBaseline = async () => {
  if (editBaseline.value?.contentHash) return editBaseline.value
  if (!props.selectedChapterNumber || !props.loadChapterRevision) return null
  const revision = await props.loadChapterRevision(props.selectedChapterNumber)
  setBaseline(revision)
  return editBaseline.value
}

const openEditModal = async () => {
  const chapter = selectedChapter.value
  if (!chapter?.content || !props.project?.id || !props.selectedChapterNumber) return

  const serverContent = cleanVersionContent(chapter.content)
  editingContent.value = serverContent
  initialEditContent.value = serverContent
  editConflict.value = null
  pendingRemoteRetry.value = false
  editorStatus.value = ''
  editBaseline.value = chapter.content_hash
    ? { revisionId: chapter.revision_id || 0, contentHash: chapter.content_hash }
    : null
  showEditModal.value = true

  try {
    await ensureEditBaseline()
    const draft = await chapterDraft.load(props.project.id, props.selectedChapterNumber)
    if (draft && draft.content !== serverContent) {
      editingContent.value = draft.content
      editBaseline.value = {
        revisionId: draft.baseRevisionId,
        contentHash: draft.baseContentHash,
      }
      editorStatus.value = '已恢复此设备上的未保存草稿；保存时会校验远端版本。'
    }
  } catch (error) {
    editorStatus.value = '未能读取本机草稿，当前内容仍可正常编辑。'
    console.warn('读取章节本地草稿失败:', error)
  }
}

const closeEditModal = async (force = false) => {
  if (!force && hasUnsavedEdit.value) {
    const confirmed = await globalAlert.showConfirm(
      '未保存内容已持续保存在此设备。关闭后可再次打开本章继续编辑。',
      '关闭编辑器？',
    )
    if (!confirmed) return
  }
  try {
    await chapterDraft.flush()
  } catch {
    // 关闭编辑器不应因浏览器存储配额等问题被卡死，状态提示已由组合函数记录。
  }
  showEditModal.value = false
  isSaving.value = false
  editConflict.value = null
}

const loadConflictRevision = async () => {
  if (!props.loadChapterRevision || !props.selectedChapterNumber) return
  editConflict.value = await props.loadChapterRevision(props.selectedChapterNumber)
  editorStatus.value = '远端正文已更新，请选择保留本地、采用远端，或另存为分支。'
}

const saveEditedContent = async () => {
  if (!props.selectedChapterNumber || !editingContent.value.trim()) return
  try {
    await chapterDraft.flush()
  } catch {
    // 远端写入仍可继续；失败时编辑器会保留内存中的内容并提示作者。
  }

  if (!isEditorOnline.value) {
    pendingRemoteRetry.value = true
    editorStatus.value = '网络已断开：内容已保存在本机，恢复网络后会自动重试。'
    return
  }
  if (!props.saveChapter) {
    editorStatus.value = '保存服务未就绪，请刷新后重试。'
    return
  }

  const baseline = await ensureEditBaseline()
  if (!baseline) {
    editorStatus.value = '无法获取当前版本基线，请刷新后重试。'
    return
  }

  isSaving.value = true
  try {
    const saved = await props.saveChapter({
      chapter_number: props.selectedChapterNumber,
      content: editingContent.value,
      expected_revision_id: baseline.revisionId,
      expected_content_hash: baseline.contentHash,
    })
    setBaseline({ revision_id: saved.revision_id, content_hash: saved.content_hash })
    initialEditContent.value = editingContent.value
    pendingRemoteRetry.value = false
    await chapterDraft.remove(props.project?.id || '', props.selectedChapterNumber)
    editorStatus.value = ''
    await closeEditModal(true)
    globalAlert.showSuccess('章节内容已保存，新版本已创建。', '保存成功')
  } catch (error) {
    if (isVersionConflictError(error)) {
      try {
        await loadConflictRevision()
      } catch (loadError) {
        editorStatus.value = '检测到版本冲突，但远端正文暂时无法读取；本地草稿已保留。'
        console.warn('读取冲突版本失败:', loadError)
      }
    } else {
      pendingRemoteRetry.value = true
      editorStatus.value = '远端保存失败：内容仍在本机草稿中，恢复网络后会自动重试。'
      console.warn('保存章节内容失败:', error)
    }
  } finally {
    isSaving.value = false
  }
}

const keepLocalDraft = () => {
  if (!editConflict.value) return
  setBaseline(editConflict.value)
  editConflict.value = null
  editorStatus.value = '已保留本地文本。再次保存即明确以当前远端版本为基线提交。'
  queueLocalDraft()
}

const useRemoteDraft = async () => {
  if (!editConflict.value || !props.project?.id || !props.selectedChapterNumber) return
  editingContent.value = editConflict.value.content
  initialEditContent.value = editConflict.value.content
  setBaseline(editConflict.value)
  editConflict.value = null
  pendingRemoteRetry.value = false
  await chapterDraft.remove(props.project.id, props.selectedChapterNumber)
  editorStatus.value = '已采用远端正文。'
}

const saveConflictAsBranch = async () => {
  if (!props.saveChapter || !props.selectedChapterNumber || !editBaseline.value) return
  isSaving.value = true
  try {
    const saved = await props.saveChapter({
      chapter_number: props.selectedChapterNumber,
      content: editingContent.value,
      expected_revision_id: editBaseline.value.revisionId,
      expected_content_hash: editBaseline.value.contentHash,
      mode: 'branch',
    })
    if (props.project?.id) await chapterDraft.remove(props.project.id, props.selectedChapterNumber)
    editConflict.value = null
    pendingRemoteRetry.value = false
    await closeEditModal(true)
    globalAlert.showSuccess(`本地文本已另存为分支（版本 #${saved.saved_version_id}）。`, '已保留')
  } catch (error) {
    editorStatus.value = '另存分支失败：本地草稿仍然保留，请稍后重试。'
    console.warn('另存冲突分支失败:', error)
  } finally {
    isSaving.value = false
  }
}

const handleEditorOnline = () => {
  isEditorOnline.value = true
  if (pendingRemoteRetry.value && showEditModal.value && hasUnsavedEdit.value && !editConflict.value) {
    void saveEditedContent()
  }
}

const handleEditorOffline = () => {
  isEditorOnline.value = false
  if (showEditModal.value) {
    editorStatus.value = '网络已断开：内容已保存在本机，恢复网络后会自动重试。'
  }
}

const persistBeforeLeave = (event: BeforeUnloadEvent) => {
  if (!hasUnsavedEdit.value) return
  queueLocalDraft()
  chapterDraft.flushSafely()
  event.preventDefault()
  event.returnValue = ''
}

const persistWhenHidden = () => {
  if (document.visibilityState === 'hidden') chapterDraft.flushSafely()
}

const selectedChapter = computed(() => {
  if (!props.project || props.selectedChapterNumber === null) return null
  return props.project.chapters.find(ch => ch.chapter_number === props.selectedChapterNumber) || null
})

const revisionHintText = computed(() => formatRevisionHint(selectedChapterOutline.value?.metadata?.revision_hint))

const isChapterCompleted = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'successful'
}

watch(
  () => props.selectedChapterNumber,
  () => {
    briefOpen.value = false
    planningDetailsOpen.value = false
    outlineEditing.value = false
    planningEditing.value = false
    showPrediction.value = false
  },
  { immediate: true },
)

watch(
  () => selectedChapter.value?.generation_status,
  (status) => {
    if (status === 'generating' || status === 'evaluating' || status === 'selecting') {
      briefOpen.value = false
      planningDetailsOpen.value = false
      planningEditing.value = false
      outlineEditing.value = false
      showPrediction.value = false
    }
  },
  { immediate: true },
)

const isChapterGenerating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'generating'
}

const isChapterFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const isChapterEvaluationFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'evaluation_failed'
}

const canGenerateChapter = (chapterNumber: number | null) => {
  if (chapterNumber === null || !props.project?.blueprint?.chapter_outline) return false

  const outlines = props.project.blueprint.chapter_outline.sort((a, b) => a.chapter_number - b.chapter_number)
  
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

const currentComponent = computed(() => {
  if (!props.selectedChapterNumber) {
    return WorkspaceInitial
  }

  const status = selectedChapter.value?.generation_status
  if (status === 'generating' || status === 'evaluating' || status === 'selecting') {
    return ChapterGenerating // Use a generic "in-progress" component
  }

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
    return VersionSelector
  }

  if (selectedChapter.value?.content) {
    return ChapterContent
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return ChapterFailed
  }
  return ChapterEmpty
})

// Polling for chapter status updates
const pollingTimer = ref<number | null>(null)

const startPolling = () => {
  stopPolling()
  pollingTimer.value = window.setInterval(() => {
    emit('fetchChapterStatus')
  }, 10000)
}

const stopPolling = () => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

watch(
  () => [selectedChapter.value?.generation_status, props.evaluatingChapter, props.isSelectingVersion, props.selectedChapterNumber],
  ([status, evaluating, selecting, chapterNumber]) => {
    if (chapterNumber === null) {
      stopPolling()
      return
    }

    const isEvaluating = evaluating === chapterNumber
    // Poll when generating, evaluating, or selecting a version
    const needsPolling = status === 'generating' || status === 'evaluating' || status === 'selecting'

    if (needsPolling) {
      startPolling()
    } else {
      stopPolling()
    }
  },
  { immediate: true }
)

watch(
  () => props.openPredictionTick,
  async (current, previous) => {
    if (current === undefined || current === previous) return
    await openPredictionPanel()
  }
)

onMounted(() => {
  window.addEventListener('online', handleEditorOnline)
  window.addEventListener('offline', handleEditorOffline)
  window.addEventListener('beforeunload', persistBeforeLeave)
  document.addEventListener('visibilitychange', persistWhenHidden)
})

onUnmounted(() => {
  stopPolling()
  window.removeEventListener('online', handleEditorOnline)
  window.removeEventListener('offline', handleEditorOffline)
  window.removeEventListener('beforeunload', persistBeforeLeave)
  document.removeEventListener('visibilitychange', persistWhenHidden)
  chapterDraft.flushSafely()
})

const currentComponentProps = computed(() => {
  if (!props.selectedChapterNumber) {
    return {}
  }
  const status = selectedChapter.value?.generation_status
  if (status === 'generating' || status === 'evaluating' || status === 'selecting') {
    return {
      chapterNumber: props.selectedChapterNumber,
      status: status,
      streamingDraftText: props.streamingDraftText || '',
      streamingStage: props.streamingStage || null,
      generationProgress: props.generationProgress || null,
      projectId: props.project?.id
    }
  }

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
    return {
      selectedChapter: selectedChapter.value,
      chapterGenerationResult: props.chapterGenerationResult,
      availableVersions: props.availableVersions,
      selectedVersionIndex: props.selectedVersionIndex,
      isSelectingVersion: props.isSelectingVersion,
      evaluatingChapter: props.evaluatingChapter,
      isEvaluationFailed: isChapterEvaluationFailed(props.selectedChapterNumber)
    }
  }
  if (selectedChapter.value?.content) {
    return { 
      selectedChapter: selectedChapter.value,
      projectId: props.project?.id
    }
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return {
      chapterNumber: props.selectedChapterNumber,
      generatingChapter: props.generatingChapter,
      predictionGenerating: generatingPrediction.value,
      outline: selectedChapterOutline.value,
      projectId: props.project?.id
    }
  }
  return {
    chapterNumber: props.selectedChapterNumber,
    generatingChapter: props.generatingChapter,
    predictionGenerating: generatingPrediction.value,
    canGenerate: canGenerateChapter(props.selectedChapterNumber),
    outline: selectedChapterOutline.value,
    projectId: props.project?.id,
    templatePrompt: templatePrompt.value
  }
})
</script>

<style scoped>
.wd-chapter-bar {
  padding: 12px 16px 10px;
  border-bottom: 1px solid var(--md-outline-variant, #2a2a2a);
}
.wd-chapter-brief {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--md-outline-variant, #2a2a2a);
}

.wd-brief-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 28px;
  padding: 3px 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--md-on-surface-variant);
  font-size: 0.75rem;
  cursor: pointer;
  transition: color 0.2s ease, background-color 0.2s ease;
}

.wd-brief-toggle:hover {
  color: var(--md-on-surface);
  background: var(--md-surface-container-high);
}

.wd-brief-toggle__chevron,
.wd-planning-card__chevron,
.wd-prediction-row__chevron {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  transition: transform 0.2s ease;
}

.wd-brief-toggle__chevron.is-open,
.wd-planning-card__chevron.is-open,
.wd-prediction-row__chevron.is-open {
  transform: rotate(90deg);
}

.wd-planning-glance {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  max-width: min(280px, 22vw);
  padding: 3px 7px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 999px;
  background: var(--md-surface-container);
  font-size: 0.6875rem;
  line-height: 1.2;
}

.wd-planning-glance--accent {
  border-color: color-mix(in srgb, var(--md-success) 30%, transparent);
  background: color-mix(in srgb, var(--md-success) 10%, transparent);
}

.wd-planning-glance__label {
  flex: 0 0 auto;
  color: var(--md-primary);
  font-weight: 700;
}

.wd-planning-glance__text {
  overflow: hidden;
  color: var(--md-on-surface-variant);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wd-planning-card,
.wd-prediction-row {
  overflow: hidden;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background: color-mix(in srgb, var(--md-surface-container) 72%, transparent);
}

.wd-planning-card__header,
.wd-prediction-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.wd-planning-card__toggle,
.wd-prediction-row__toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
  padding: 11px 12px;
  border: 0;
  background: transparent;
  color: var(--md-on-surface);
  text-align: left;
  cursor: pointer;
}

.wd-planning-card__toggle:hover,
.wd-prediction-row__toggle:not(:disabled):hover {
  background: var(--md-surface-container-high);
}

.wd-prediction-row__toggle:disabled {
  cursor: default;
}

.wd-planning-card__icon,
.wd-prediction-row__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  flex: 0 0 auto;
  border: 1px solid color-mix(in srgb, var(--md-primary) 38%, transparent);
  border-radius: 9px;
  background: color-mix(in srgb, var(--md-primary) 12%, transparent);
  color: var(--md-primary);
  font-size: 0.75rem;
  font-weight: 800;
}

.wd-prediction-row__icon {
  border-color: color-mix(in srgb, var(--md-success) 38%, transparent);
  background: color-mix(in srgb, var(--md-success) 12%, transparent);
  color: var(--md-success);
}

.wd-planning-card__heading,
.wd-prediction-row__heading {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.wd-planning-card__title,
.wd-prediction-row__heading > span {
  font-size: 0.875rem;
  font-weight: 700;
}

.wd-planning-card__meta,
.wd-prediction-row__heading small {
  overflow: hidden;
  color: var(--md-on-surface-variant);
  font-size: 0.6875rem;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wd-planning-card__chevron,
.wd-prediction-row__chevron {
  color: var(--md-on-surface-variant);
}

.wd-planning-card__edit {
  flex: 0 0 auto;
  margin-right: 10px;
  padding: 6px 9px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--md-primary);
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
}

.wd-planning-card__edit:hover {
  background: color-mix(in srgb, var(--md-primary) 10%, transparent);
}

.wd-planning-card__preview {
  overflow: hidden;
  margin: -2px 12px 10px 52px;
  color: var(--md-on-surface-variant);
  font-size: 0.75rem;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wd-planning-card__body {
  padding: 12px;
  border-top: 1px solid var(--md-outline-variant);
  animation: m3-slide-down 0.2s ease-out both;
}

.wd-planning-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.wd-planning-item {
  min-width: 0;
  padding: 10px 11px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 10px;
  background: var(--md-surface-container-low);
}

.wd-planning-item--wide {
  grid-column: 1 / -1;
}

.wd-planning-item--accent {
  border-color: color-mix(in srgb, var(--md-success) 30%, var(--md-outline-variant));
  background: color-mix(in srgb, var(--md-success) 8%, var(--md-surface-container-low));
}

.wd-planning-item--warning {
  border-color: color-mix(in srgb, var(--md-error) 28%, var(--md-outline-variant));
  background: color-mix(in srgb, var(--md-error) 7%, var(--md-surface-container-low));
}

.wd-planning-item__label,
.wd-planning-field > span {
  display: block;
  margin-bottom: 5px;
  color: var(--md-primary);
  font-size: 0.6875rem;
  font-weight: 700;
}

.wd-planning-item p,
.wd-planning-item li {
  color: var(--md-on-surface);
  font-size: 0.8125rem;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.wd-planning-item ul {
  display: grid;
  gap: 3px;
  margin: 0;
  padding-left: 18px;
  list-style: disc;
}

.wd-planning-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.wd-planning-tags span {
  padding: 3px 7px;
  border-radius: 999px;
  background: var(--md-surface-container-high);
  color: var(--md-on-surface-variant);
  font-size: 0.75rem;
}

.wd-planning-empty {
  padding: 14px;
  border: 1px dashed var(--md-outline-variant);
  border-radius: 10px;
  color: var(--md-on-surface-variant);
  font-size: 0.8125rem;
  text-align: center;
}

.wd-planning-field {
  display: block;
}

.wd-prediction-row {
  padding-right: 8px;
}

@media (max-width: 960px) {
  .wd-planning-glance {
    display: none;
  }

  .wd-planning-grid {
    grid-template-columns: 1fr;
  }

  .wd-planning-item--wide {
    grid-column: auto;
  }
}

.m3-chip-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.m3-chip-neutral {
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
}

.m3-editor-dialog {
  max-width: min(1200px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  border-radius: var(--md-radius-xl);
}

.m3-prediction-panel {
  animation: m3-slide-down 0.25s ease-out both;
}

@keyframes m3-slide-down {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  overflow: auto;
  padding: 1rem;
}

.modal-content {
  background: #0A0A0A;
  border: 1px solid #2A2A2A;
  border-radius: 12px;
  width: 100%;
  max-width: 900px;
  max-height: 90vh;
  overflow-x: hidden;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
  margin: auto;
  flex-shrink: 0;
}

.m3-prediction-panel ::-webkit-scrollbar {
  width: 4px;
}

.m3-prediction-panel ::-webkit-scrollbar-thumb {
  background: var(--md-outline);
  border-radius: 2px;
}
</style>
