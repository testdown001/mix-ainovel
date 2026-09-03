<!-- AIMETA P=写作台章节与创作工具抽屉|R=紧凑章节导航_创作工具分区_独立滚动|NR=不含正文编辑|E=component:WDSidebar|X=ui|A=章节与工具抽屉|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="wd-sidebar-shell h-full min-h-0" :class="{ 'is-embedded': embedded }">
    <!-- 侧边栏遮罩 (移动端) -->
    <div
      v-if="sidebarOpen && !embedded"
      @click="$emit('closeSidebar')"
      class="fixed inset-0 bg-black/20 backdrop-blur-sm z-40 lg:hidden"
    ></div>

    <!-- 左侧：蓝图和章节列表 -->
    <div
      :class="[
        'md-card md-card-elevated transition-all duration-300 h-full',
        embedded
          ? 'relative w-full translate-x-0'
          : 'lg:relative lg:translate-x-0 lg:w-80 lg:flex-shrink-0',
        !embedded && sidebarOpen
          ? 'fixed left-4 top-20 bottom-4 w-80 z-50 translate-x-0'
          : !embedded
            ? 'lg:w-80 lg:flex-shrink-0 -translate-x-full absolute lg:relative'
            : ''
      ]"
      style="border-radius: var(--md-radius-xl);"
    >
      <div class="h-full min-h-0 flex flex-col overflow-hidden">
        <div v-if="embedded" class="drawer-tabbar" role="tablist" aria-label="写作台抽屉">
          <button
            type="button"
            role="tab"
            :aria-selected="drawerTab === 'chapters'"
            :class="{ active: drawerTab === 'chapters' }"
            @click="drawerTab = 'chapters'"
          >
            <span>章节</span>
            <small>{{ completedChapters }}/{{ totalChapters }}</small>
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="drawerTab === 'tools'"
            :class="{ active: drawerTab === 'tools' }"
            @click="drawerTab = 'tools'"
          >
            <span>创作工具</span>
            <small>{{ props.professionalMode ? '专业' : '主线' }}</small>
          </button>
        </div>

        <!-- 故事概览（可折叠）：蓝图 / 参考小说 / 创作主线。order-2 使其排在章节列表下方 -->
        <div
          v-show="!embedded || drawerTab === 'tools'"
          class="overview-collapsible flex-shrink-0 order-2"
        >
          <button class="overview-toggle" type="button" @click="toggleOverview" :aria-expanded="!overviewCollapsed">
            <span class="overview-toggle-main">
              <svg class="overview-chevron" :class="{ 'rotate-90': !overviewCollapsed }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
              <span>故事概览</span>
              <span class="overview-toggle-meta">{{ characterCount }}角色 · {{ relationshipCount }}关系 · {{ completedChapters }}/{{ totalChapters }}章</span>
            </span>
            <span class="overview-toggle-state">{{ overviewCollapsed ? '展开' : '收起' }}</span>
          </button>
          <div v-show="!overviewCollapsed" class="overview-content max-h-[55vh] overflow-y-auto">
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

        <div class="reference-panel flex-shrink-0">
          <div class="reference-panel-header">
            <div>
              <p class="reference-panel-title">本书参考小说</p>
              <p class="reference-panel-subtitle">绑定后：构思引用桥段手法，正文按情境注入参考桥段与写法基准</p>
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
                  <p class="text-sm font-medium text-white">{{ novel.title }}</p>
                  <p class="text-xs text-[#555]">{{ novel.author || '未知作者' }} <span v-if="novel.genre"> · {{ novel.genre }}</span><span v-if="!novel.genre"> · 未设定题材</span></p>
                </div>
                <span class="reference-panel-tag" :data-status="novel.status">{{ novel.status }}</span>
              </div>
            </div>
            <div v-else class="reference-panel-empty">
              本书尚未添加参考小说，可在灵感模式中选取并生成后自动绑定。
            </div>
          </div>
        </div>

        <div class="workflow-panel flex-shrink-0">
          <div class="workflow-panel-header">
            <div>
              <p class="workflow-panel-title">创作主线</p>
              <p class="workflow-panel-subtitle">{{ workflowSubtitle }}</p>
            </div>
            <span class="workflow-progress">{{ completedChapters }}/{{ totalChapters }}</span>
          </div>
          <div class="workflow-steps">
            <div
              v-for="step in workflowSteps"
              :key="step.key"
              class="workflow-step"
              :class="{ done: step.done, active: step.active }"
            >
              <span class="workflow-step-dot"></span>
              <span>{{ step.label }}</span>
            </div>
          </div>
          <button
            class="workflow-action"
            type="button"
            :disabled="!nextWorkflowAction.enabled || props.batchGenerating"
            @click="runNextWorkflowAction"
          >
            <span>{{ nextWorkflowAction.label }}</span>
            <span class="workflow-action-hint">{{ nextWorkflowAction.hint }}</span>
          </button>
          <div class="workflow-mode-switch" role="group" aria-label="写作台模式">
            <button
              type="button"
              :class="{ active: !props.professionalMode }"
              @click="$emit('update:professionalMode', false)"
            >
              主线模式
            </button>
            <button
              type="button"
              :class="{ active: props.professionalMode }"
              @click="$emit('update:professionalMode', true)"
            >
              专业模式
            </button>
          </div>
        </div>
          </div>
        </div>

        <div
          v-if="embedded && drawerTab === 'tools'"
          class="drawer-tools-pane order-1"
          role="tabpanel"
        >
          <section class="tool-hero">
            <div>
              <p>创作控制台</p>
              <h3>{{ selectedOutline ? `第 ${selectedOutline.chapter_number} 章` : '尚未选择章节' }}</h3>
              <span>{{ selectedOutline?.title || '先从章节页选择要继续创作的章节' }}</span>
            </div>
            <button type="button" @click="$emit('openPresetSelector')">
              <small>当前档位</small>
              <strong>{{ getPresetName(props.selectedPreset || 'fast') }}</strong>
            </button>
          </section>

          <section class="tool-section">
            <div class="tool-section-head">
              <div><small>WORKFLOW</small><h4>推进创作</h4></div>
              <span>{{ completedChapters }}/{{ totalChapters }} 章定稿</span>
            </div>
            <div class="tool-action-grid">
              <button
                type="button"
                class="tool-action-card is-primary"
                :disabled="props.isGeneratingOutline || props.batchGenerating"
                @click="$emit('generateOutline')"
              >
                <span class="tool-action-icon">＋</span>
                <span><strong>生成后续章纲</strong><small>继续规划故事章节</small></span>
              </button>
              <button
                v-if="!props.batchGenerating"
                type="button"
                class="tool-action-card"
                :disabled="props.isGeneratingOutline || !!props.generatingChapter"
                @click="$emit('batchGenerate')"
              >
                <span class="tool-action-icon">↻</span>
                <span><strong>批量写正文</strong><small>按章纲顺序连续生成</small></span>
              </button>
              <button
                v-else
                type="button"
                class="tool-action-card is-danger"
                @click="$emit('cancelBatch')"
              >
                <span class="tool-action-icon">■</span>
                <span>
                  <strong>停止连续生成</strong>
                  <small>{{ props.batchProgress?.current || 0 }}/{{ props.batchProgress?.total || 0 }} 章</small>
                </span>
              </button>
              <button
                type="button"
                class="tool-action-card"
                :disabled="props.isGeneratingOutline || props.batchGenerating || !hasIncompleteChapters"
                @click="$emit('regenerateOutlines')"
              >
                <span class="tool-action-icon">◇</span>
                <span><strong>重排未完成章纲</strong><small>保留已经定稿的章节</small></span>
              </button>
              <button type="button" class="tool-action-card" @click="openReferenceLibrary">
                <span class="tool-action-icon">书</span>
                <span>
                  <strong>参考小说</strong>
                  <small>{{ boundReferenceNovels.length ? `已绑定 ${boundReferenceNovels.length} 本` : '添加本书参考' }}</small>
                </span>
              </button>
            </div>
          </section>

          <section class="tool-section">
            <div class="tool-section-head">
              <div><small>CHAPTER</small><h4>当前章节</h4></div>
              <span>{{ selectedChapterStatus }}</span>
            </div>
            <div class="tool-action-grid">
              <button
                type="button"
                class="tool-action-card"
                :disabled="!selectedOutline || isChapterCompleted(selectedOutline.chapter_number)"
                @click="selectedOutline && $emit('editChapter', selectedOutline)"
              >
                <span class="tool-action-icon">编</span>
                <span><strong>编辑本章规划</strong><small>修改功能、爽点和禁写</small></span>
              </button>
              <button
                type="button"
                class="tool-action-card"
                :disabled="!selectedOutline || props.batchGenerating || !!props.generatingChapter"
                @click="selectedOutline && confirmGenerateChapter(selectedOutline.chapter_number)"
              >
                <span class="tool-action-icon">写</span>
                <span><strong>{{ selectedOutline && isChapterCompleted(selectedOutline.chapter_number) ? '重写本章正文' : '生成本章正文' }}</strong><small>使用当前档位起草</small></span>
              </button>
              <button
                type="button"
                class="tool-action-card"
                :disabled="!selectedOutline?.metadata?.prediction"
                @click="selectedOutline && previewPrediction(selectedOutline.chapter_number)"
              >
                <span class="tool-action-icon">演</span>
                <span><strong>查看情节梳理</strong><small>高级 · 核对节拍与引用</small></span>
              </button>
              <button
                type="button"
                class="tool-action-card"
                :disabled="!selectedChapterNumber"
                @click="$emit('previewContextPlan')"
              >
                <span class="tool-action-icon">据</span>
                <span><strong>生成依据</strong><small>查看上下文计划</small></span>
              </button>
            </div>
          </section>

          <section class="tool-section">
            <div class="tool-section-head">
              <div><small>QUALITY & AI</small><h4>质量与高级工具</h4></div>
              <button
                type="button"
                class="mode-pill"
                :class="{ active: props.professionalMode }"
                @click="$emit('update:professionalMode', !props.professionalMode)"
              >
                {{ props.professionalMode ? '专业模式' : '开启专业模式' }}
              </button>
            </div>
            <div class="tool-action-grid compact">
              <button
                type="button"
                class="tool-action-card"
                :disabled="props.isRebuildingRag"
                @click="$emit('rebuildRag', false)"
                @contextmenu.prevent="$emit('rebuildRag', true)"
              >
                <span class="tool-action-icon">忆</span>
                <span><strong>{{ props.isRebuildingRag ? '刷新中…' : '刷新知识库' }}</strong><small>长篇记忆与检索</small></span>
              </button>
              <button type="button" class="tool-action-card" @click="$emit('openDiagnosticPanel')">
                <span class="tool-action-icon">检</span>
                <span><strong>章节体检</strong><small>质量与风险报告</small></span>
              </button>
              <button
                type="button"
                class="tool-action-card"
                :disabled="!props.agentEnabled"
                @click="$emit('openSkillSelector')"
              >
                <span class="tool-action-icon">技</span>
                <span><strong>Agent 技能</strong><small>{{ props.selectedSkillCount ? `${props.selectedSkillCount} 个已选` : '起草时注入' }}</small></span>
              </button>
              <button type="button" class="tool-action-card" @click="$emit('openMiddleProductViewer')">
                <span class="tool-action-icon">析</span>
                <span><strong>中间产物</strong><small>上下文与证据</small></span>
              </button>
              <button type="button" class="tool-action-card" @click="$emit('openAgentVisualizer')">
                <span class="tool-action-icon">协</span>
                <span><strong>Agent 协作</strong><small>查看生成流程</small></span>
              </button>
              <button type="button" class="tool-action-card" @click="$emit('openArchives')">
                <span class="tool-action-icon">档</span>
                <span><strong>任务档案</strong><small>生成记录与奏折</small></span>
              </button>
            </div>
          </section>
        </div>

        <!-- 章节列表（order-1 提到最上面；故事概览折叠区在其下方） -->
        <div
          v-show="!embedded || drawerTab === 'chapters'"
          ref="listContainer"
          class="chapter-drawer-pane flex-1 overflow-y-auto min-h-0 order-1"
          role="tabpanel"
        >
          <div v-if="embedded" class="compact-chapter-head">
            <div class="compact-chapter-title">
              <div><small>MANUSCRIPT</small><h3>章节目录</h3></div>
              <strong>{{ visibleOutlines.length }}/{{ totalChapters }}</strong>
            </div>
            <div class="compact-chapter-controls">
              <button type="button" @click.stop="$emit('openPresetSelector')">
                <span>写作档位</span><strong>{{ getPresetName(props.selectedPreset || 'fast') }}</strong>
              </button>
              <button
                v-if="hasIncompleteChapters"
                type="button"
                @click.stop="scrollToFirstIncompleteChapter"
              >
                <span>快捷定位</span><strong>下一未完成</strong>
              </button>
            </div>
            <div
              v-if="props.batchGenerating || incompleteChapterCount > 0"
              class="compact-batch-entry"
              :class="{ running: props.batchGenerating }"
              :aria-live="props.batchGenerating ? 'polite' : undefined"
            >
              <div>
                <small>{{ props.batchGenerating ? '正在批量生成正文' : `待写正文 ${incompleteChapterCount} 章` }}</small>
                <strong v-if="props.batchGenerating">
                  {{ props.batchProgress?.current || 0 }} / {{ props.batchProgress?.total || incompleteChapterCount }} 章
                </strong>
                <strong v-else>从第 {{ firstIncompleteChapter?.chapter_number || 1 }} 章按顺序生成</strong>
              </div>
              <button
                v-if="props.batchGenerating"
                type="button"
                class="stop"
                @click="$emit('cancelBatch')"
              >
                停止
              </button>
              <button v-else type="button" @click="$emit('batchGenerate')">批量生成</button>
              <span v-if="props.batchGenerating" class="compact-batch-progress">
                <i :style="{ width: compactBatchProgressPercent + '%' }"></i>
              </span>
            </div>
            <select v-if="volumeOptions.length" v-model="selectedVolume" class="compact-volume-select">
              <option value="all">全部分卷</option>
              <option v-for="vol in volumeOptions" :key="vol.key" :value="vol.key">
                {{ vol.label }}
              </option>
            </select>
            <div v-if="activeLoopLabels.length" class="compact-loop-labels">
              <span v-for="label in activeLoopLabels" :key="label">{{ label }}</span>
            </div>
            <p v-else-if="qualityLoops" class="compact-loop-empty">
              当前档位未启用额外质量回路。
            </p>
          </div>
          <div v-else class="p-6 pb-4">
            <div class="flex items-center justify-between mb-4">
              <h3 class="md-title-medium font-semibold">章节大纲</h3>
              <div class="flex items-center gap-2">
                <!-- 预设选择按钮 -->
                <button
                  @click.stop="$emit('openPresetSelector')"
                  class="md-btn md-btn-text md-ripple !text-xs !py-1 !px-2"
                  title="选择生成模式"
                >
                  <span class="mr-1">⚡</span>
                  <span class="hidden sm:inline">{{ getPresetName(props.selectedPreset || 'fast') }}</span>
                  <span class="sm:hidden">模式</span>
                </button>
                <button
                  v-if="hasIncompleteChapters"
                  @click.stop="scrollToFirstIncompleteChapter"
                  class="md-btn md-btn-text md-ripple"
                >
                  定位到未完成
                </button>
                <span class="md-chip md-chip-filter selected">
                  {{ visibleOutlines.length }}/{{ totalChapters }} 章
                </span>
              </div>
            </div>
            <div v-if="volumeOptions.length" class="mt-3">
              <select v-model="selectedVolume" class="md-input w-full text-sm">
                <option value="all">全部分卷</option>
                <option v-for="vol in volumeOptions" :key="vol.key" :value="vol.key">
                  {{ vol.label }}
                </option>
              </select>
            </div>
            <div v-if="activeLoopLabels.length" class="mt-2 flex flex-wrap gap-1">
              <span v-for="label in activeLoopLabels" :key="label" class="md-chip !text-[10px] !px-1.5 !py-0">{{ label }}</span>
            </div>
            <p v-else-if="qualityLoops" class="mt-2 md-body-small md-on-surface-variant">当前模式未开启质量回路（免费/极速默认关闭）。</p>
          </div>

          <!-- 迷你节奏条 -->
          <div v-if="visibleOutlines.length" class="flex gap-px mx-6 mb-2 h-3">
            <div v-for="outline in visibleOutlines" :key="outline.chapter_number"
              class="flex-1 rounded-sm cursor-pointer transition-all duration-200 hover:h-4"
              :style="{ backgroundColor: getRhythmColor(outline) }"
              :class="{ 'opacity-40': selectedChapterNumber !== null && selectedChapterNumber !== outline.chapter_number }"
              :title="`第${outline.chapter_number}章 ${outline.title}`"
              @click="handleSelectChapter(outline)"
            />
          </div>

          <div :class="embedded ? 'compact-chapter-list' : 'px-6 pb-6'">
            <div v-if="embedded && visibleOutlines.length" class="compact-chapter-rows">
              <button
                v-for="chapter in visibleOutlines"
                :key="chapter.chapter_number"
                :ref="el => setChapterRef(chapter.chapter_number, el)"
                type="button"
                class="compact-chapter-row"
                :class="{
                  active: selectedChapterNumber === chapter.chapter_number,
                  done: isChapterCompleted(chapter.chapter_number),
                }"
                @click="handleSelectChapter(chapter)"
              >
                <span class="compact-row-accent"></span>
                <span class="compact-row-index">
                  <svg
                    v-if="isChapterCompleted(chapter.chapter_number)"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2.2"
                  >
                    <path d="m6.5 12.5 3.3 3.3 7.7-8" />
                  </svg>
                  <span v-else>{{ String(chapter.chapter_number).padStart(2, '0') }}</span>
                </span>
                <span class="compact-row-copy">
                  <strong>第{{ chapter.chapter_number }}章 · {{ chapter.title }}</strong>
                  <small>{{ chapter.summary || '尚未填写章节摘要' }}</small>
                  <span v-if="chapter.metadata?.prediction" class="compact-rhythm-tags">
                    <i v-if="chapter.metadata.prediction.cool_points?.length">爽</i>
                    <i v-if="chapter.metadata.prediction.foreshadowing_hooks?.length">伏</i>
                    <i v-if="chapter.metadata.prediction.foreshadowing_targets?.length">收</i>
                  </span>
                </span>
                <em :data-state="compactChapterState(chapter.chapter_number)">
                  {{ compactChapterStatus(chapter.chapter_number) }}
                </em>
              </button>
            </div>
            <div v-else-if="visibleOutlines.length" class="space-y-3">
              <div
                v-for="(chapter, index) in visibleOutlines"
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
                    <p v-if="revisionHintOf(chapter)" class="mt-1 text-[11px] leading-4" style="color:#C9A227;">
                      修订提示：{{ revisionHintOf(chapter) }}
                    </p>

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
                        title="查看情节梳理"
                      >
                        查看梳理
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
            <template v-if="!embedded">
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
              <button
                class="md-btn md-btn-outlined md-ripple w-full flex items-center justify-center gap-2 mt-2 disabled:opacity-50"
                :disabled="props.isGeneratingOutline || props.batchGenerating || !hasIncompleteChapters"
                @click="$emit('regenerateOutlines')"
              >
                <span>{{ props.isGeneratingOutline ? '重排中...' : '重排未完成大纲' }}</span>
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
                v-if="!props.professionalMode"
                class="advanced-mode-entry"
                type="button"
                @click="$emit('update:professionalMode', true)"
              >
                <span>进入专业模式</span>
                <small>知识库、计划、体检和 Agent 工具</small>
              </button>
              <button
                v-else
                class="advanced-toggle"
                type="button"
                @click="showProfessionalTools = !showProfessionalTools"
              >
                <span>专业工具</span>
                <span>{{ showProfessionalTools ? '收起' : '展开' }}</span>
              </button>
            </div>
            <div v-if="props.professionalMode && showProfessionalTools" class="advanced-tools">
              <button
                @click="$emit('rebuildRag', false)"
                @contextmenu.prevent="$emit('rebuildRag', true)"
                :disabled="props.isRebuildingRag"
                class="advanced-tool-btn disabled:opacity-50 disabled:cursor-not-allowed"
                title="左键：增量刷新 | 右键：强制全量刷新"
              >
                <span>{{ props.isRebuildingRag ? '刷新中...' : '刷新知识库' }}</span>
                <small>修复长篇记忆与检索</small>
              </button>
              <div class="advanced-tool-grid">
                <button
                  @click="$emit('openSkillSelector')"
                  :disabled="!props.agentEnabled"
                  class="advanced-tool-btn disabled:opacity-50 disabled:cursor-not-allowed"
                  :title="props.agentEnabled ? '配置 Agent 技能增强' : '启用 Agent 模式后可配置技能'"
                >
                  <span>Agent 技能</span>
                  <small>{{ props.selectedSkillCount ? `${props.selectedSkillCount} 个已选` : '起草时注入' }}</small>
                </button>
                <button
                  @click="$emit('previewContextPlan')"
                  :disabled="!selectedChapterNumber"
                  class="advanced-tool-btn disabled:opacity-50 disabled:cursor-not-allowed"
                  title="预览本章生成计划"
                >
                  <span>计划</span>
                  <small>查看 AI 写作依据</small>
                </button>
                <button
                  @click="$emit('openMiddleProductViewer')"
                  class="advanced-tool-btn"
                  title="查看生成中间产物"
                >
                  <span>中间产物</span>
                  <small>调试上下文与证据</small>
                </button>
                <button
                  @click="$emit('openDiagnosticPanel')"
                  class="advanced-tool-btn"
                  title="生成诊断报告"
                >
                  <span>章节体检</span>
                  <small>质量与风险报告</small>
                </button>
                <button
                  @click="$emit('openAgentVisualizer')"
                  class="advanced-tool-btn"
                  title="查看 Agent 协作流程"
                >
                  <span>Agent</span>
                  <small>协作流程可视化</small>
                </button>
                <button
                  @click="$emit('openArchives')"
                  class="advanced-tool-btn"
                  title="查看写作任务档案"
                >
                  <span>任务档案</span>
                  <small>奏折与生成记录</small>
                </button>
              </div>
            </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
  <ReferenceNovelLibrary
    v-model:show="referenceLibraryVisible"
    :project-id="project.id"
    :selected-novel-ids="boundReferenceNovelIds"
    @select="handleSelectReferenceNovel"
    @remove="handleRemoveReferenceNovel"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref, nextTick, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import { NovelAPI, type NovelProject, type ChapterOutline, type ChapterPrediction, type QualityLoopsResponse, type ReferenceNovelSummary } from '@/api/novel'
import { formatRevisionHint } from '@/utils/revisionHint'
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
  embedded?: boolean
  project: NovelProject
  sidebarOpen: boolean
  selectedChapterNumber: number | null
  generatingChapter: number | null
  evaluatingChapter: number | null
  isGeneratingOutline: boolean
  isRebuildingRag: boolean
  batchGenerating: boolean
  batchProgress: { current: number; total: number } | null
  selectedPreset?: string
  selectedSkillCount?: number
  agentEnabled?: boolean
  professionalMode?: boolean
  showMiddleProductViewer?: boolean
  showDiagnosticPanel?: boolean
  showAgentVisualizer?: boolean
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
  'cancelBatch',
  'openPresetSelector',
  'openSkillSelector',
  'openMiddleProductViewer',
  'previewContextPlan',
  'openDiagnosticPanel',
  'openAgentVisualizer',
  'openArchives',
  'update:professionalMode',
  'regenerateOutlines',
])

// 预设名称映射
const presetNameMap: Record<string, string> = {
  'fast': '极速',
  'quick': '快速',
  'quality': '质量',
  'style': '文笔',
  '爽点': '爽点',
  'platinum': '铂金'
}

function revisionHintOf(chapter: ChapterOutline): string {
  return formatRevisionHint(chapter.metadata?.revision_hint)
}

function getPresetName(preset: string): string {
  return presetNameMap[preset] || preset
}

const selectedForDeletion = ref<number[]>([])
const listContainer = ref<HTMLElement | null>(null)
const chapterRefs = ref<Record<number, HTMLElement | null>>({})
const referenceLibraryVisible = ref(false)
const showProfessionalTools = ref(!!props.professionalMode)
const selectedVolume = ref('all')
const qualityLoops = ref<QualityLoopsResponse | null>(null)
type DrawerTab = 'chapters' | 'tools'
const drawerTab = ref<DrawerTab>(
  typeof window !== 'undefined' && window.matchMedia('(min-width: 1024px)').matches
    ? 'tools'
    : 'chapters',
)

const selectedOutline = computed(() =>
  props.project.blueprint?.chapter_outline?.find(
    (outline) => outline.chapter_number === props.selectedChapterNumber,
  ),
)

const selectedChapterStatus = computed(() => {
  const chapterNumber = props.selectedChapterNumber
  if (!chapterNumber) return '未选择'
  if (isChapterGenerating(chapterNumber)) return '生成中'
  if (isChapterEvaluating(chapterNumber)) return '评审中'
  if (isChapterFailed(chapterNumber)) return '生成失败'
  if (hasChapterInProgress(chapterNumber)) return '等待选版'
  if (isChapterCompleted(chapterNumber)) return '已定稿'
  return '未开始'
})

const volumeOptions = computed(() =>
  (props.project.blueprint?.volumes || []).map((vol, i) => ({
    key: String(i),
    label: `${vol.name || `第${i + 1}卷`} ${vol.start_chapter || '?'}-${vol.end_chapter || '?'}`,
    start: vol.start_chapter || 1,
    end: vol.end_chapter || 99999,
  })),
)

const visibleOutlines = computed(() => {
  const all = props.project.blueprint?.chapter_outline || []
  if (selectedVolume.value === 'all') return all
  const vol = volumeOptions.value.find((item) => item.key === selectedVolume.value)
  if (!vol) return all
  return all.filter((outline) => outline.chapter_number >= vol.start && outline.chapter_number <= vol.end)
})

const LOOP_LABELS: Record<string, string> = {
  outline_revision: '滚动细纲',
  volume_retrospective: '卷级复盘',
  character_significance: '人物意义层',
  two_pass_draft: '两遍制',
}

const activeLoopLabels = computed(() =>
  Object.entries(qualityLoops.value?.loops || {})
    .filter(([, status]) => status.active)
    .map(([key]) => LOOP_LABELS[key] || key),
)

async function loadQualityLoops() {
  try {
    qualityLoops.value = await NovelAPI.getQualityLoops(props.selectedPreset || 'fast')
  } catch {
    qualityLoops.value = null
  }
}

watch(() => props.selectedPreset, loadQualityLoops)
onMounted(loadQualityLoops)

// 故事概览折叠态：默认折叠（让章节列表占据主区域），并持久化到 localStorage
const OVERVIEW_COLLAPSE_KEY = 'wd_sidebar_overview_collapsed'
const overviewCollapsed = ref(localStorage.getItem(OVERVIEW_COLLAPSE_KEY) !== 'false')
function toggleOverview() {
  overviewCollapsed.value = !overviewCollapsed.value
  localStorage.setItem(OVERVIEW_COLLAPSE_KEY, String(overviewCollapsed.value))
}

const characterCount = computed(() => {
  return props.project?.blueprint?.characters?.length || 0
})

const relationshipCount = computed(() => {
  return props.project?.blueprint?.relationships?.length || 0
})

const boundReferenceNovels = computed(() => novelStore.projectReferenceNovels)
const boundReferenceNovelIds = computed(() =>
  boundReferenceNovels.value.map((novel) => novel.id),
)
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

const completedChapters = computed(() => {
  return props.project?.chapters?.filter(ch => ch.generation_status === 'successful').length || 0
})

const incompleteChapterCount = computed(() =>
  (props.project?.blueprint?.chapter_outline || []).filter(
    chapter => !isChapterCompleted(chapter.chapter_number)
  ).length
)

const compactBatchProgressPercent = computed(() => {
  const total = props.batchProgress?.total || incompleteChapterCount.value
  if (!total) return 0
  return Math.min(100, Math.round(((props.batchProgress?.current || 0) / total) * 100))
})

const firstIncompleteChapter = computed(() => {
  const outlines = [...(props.project?.blueprint?.chapter_outline || [])].sort(
    (a, b) => a.chapter_number - b.chapter_number
  )
  return outlines.find(chapter => !isChapterCompleted(chapter.chapter_number)) || null
})

const waitingChapter = computed(() => {
  const chapter = props.project?.chapters?.find(ch => ch.generation_status === 'waiting_for_confirm')
  if (!chapter) return null
  return props.project?.blueprint?.chapter_outline?.find(
    outline => outline.chapter_number === chapter.chapter_number
  ) || null
})

const workflowSubtitle = computed(() => {
  if (!totalChapters.value) return '先把蓝图转成可执行章节'
  if (waitingChapter.value) return `第 ${waitingChapter.value.chapter_number} 章等待选版`
  if (firstIncompleteChapter.value) return `下一步推进第 ${firstIncompleteChapter.value.chapter_number} 章`
  return '已完成当前大纲，可做体检或继续扩展'
})

const workflowSteps = computed(() => [
  {
    key: 'blueprint',
    label: props.project.blueprint ? '蓝图已建立' : '建立故事蓝图',
    done: !!props.project.blueprint,
    active: !props.project.blueprint,
  },
  {
    key: 'outline',
    label: totalChapters.value ? `${totalChapters.value} 章大纲` : '生成章节大纲',
    done: totalChapters.value > 0,
    active: !!props.project.blueprint && totalChapters.value === 0,
  },
  {
    key: 'draft',
    label: completedChapters.value ? `${completedChapters.value} 章已定稿` : '生成第一章',
    done: totalChapters.value > 0 && completedChapters.value === totalChapters.value,
    active: totalChapters.value > 0 && completedChapters.value < totalChapters.value,
  },
])

const nextWorkflowAction = computed(() => {
  if (!totalChapters.value) {
    return {
      type: 'generate-outline',
      enabled: !props.isGeneratingOutline,
      label: props.isGeneratingOutline ? '正在生成大纲' : '生成章节大纲',
      hint: '把蓝图拆成可写章节',
      chapterNumber: null,
    }
  }

  if (waitingChapter.value) {
    return {
      type: 'select-chapter',
      enabled: true,
      label: `处理第 ${waitingChapter.value.chapter_number} 章版本`,
      hint: '选中满意版本并定稿',
      chapterNumber: waitingChapter.value.chapter_number,
    }
  }

  const selected = props.selectedChapterNumber
  if (selected && canGenerateChapter(selected) && !isChapterGenerating(selected)) {
    return {
      type: 'generate-chapter',
      enabled: !props.generatingChapter,
      label: isChapterCompleted(selected) ? `重写第 ${selected} 章` : `生成第 ${selected} 章`,
      hint: '按当前模式推进正文',
      chapterNumber: selected,
    }
  }

  if (firstIncompleteChapter.value) {
    return {
      type: 'select-chapter',
      enabled: true,
      label: `定位第 ${firstIncompleteChapter.value.chapter_number} 章`,
      hint: '继续下一章创作',
      chapterNumber: firstIncompleteChapter.value.chapter_number,
    }
  }

  return {
    type: 'diagnose',
    enabled: true,
    label: '生成全书体检',
    hint: '检查一致性与返工风险',
    chapterNumber: null,
  }
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
  if (!isChapterCompleted(chapterNumber) && !hasChapterInProgress(chapterNumber) && !isChapterFailed(chapterNumber)) {
    emit('generateChapter', chapterNumber)
    return
  }

  const message = isChapterCompleted(chapterNumber)
    ? '重新生成会覆盖当前章节的生成结果，确定继续吗？'
    : hasChapterInProgress(chapterNumber)
      ? '重新生成会替换当前待选择版本，确定继续吗？'
      : '将重新尝试生成该章节，确定继续吗？'
  const confirmed = await globalAlert.showConfirm(message, '生成确认')
  if (confirmed) {
    emit('generateChapter', chapterNumber)
  }
}

function previewPrediction(chapterNumber: number) {
  emit('previewPrediction', chapterNumber)
}

async function runNextWorkflowAction() {
  const action = nextWorkflowAction.value
  if (!action.enabled) return
  if (action.type === 'generate-outline') {
    emit('generateOutline')
    return
  }
  if (action.type === 'generate-chapter' && action.chapterNumber) {
    await confirmGenerateChapter(action.chapterNumber)
    return
  }
  if (action.type === 'select-chapter' && action.chapterNumber) {
    const outline = props.project?.blueprint?.chapter_outline?.find(
      chapter => chapter.chapter_number === action.chapterNumber
    )
    if (outline) handleSelectChapter(outline)
    return
  }
  if (action.type === 'diagnose') {
    emit('openDiagnosticPanel')
  }
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
  () => props.selectedChapterNumber,
  async (num) => {
    if (num === null) return
    await nextTick()
    const el = chapterRefs.value[num]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
)

watch(
  () => referenceLibraryVisible.value,
  (visible) => {
    if (!visible) {
      refreshReferenceNovels()
    }
  }
)

watch(
  () => props.professionalMode,
  (enabled) => {
    showProfessionalTools.value = !!enabled
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
  if (currentIds.length >= 3) {
    globalAlert.showError('本书最多可添加 3 本参考小说，请先移出一本后再添加。', '已达上限')
    return
  }
  const newIds = [...currentIds, novel.id]
  try {
    await novelStore.bindProjectReferenceNovels(props.project.id, newIds)
  } catch (err) {
    globalAlert.showError(
      `绑定参考小说失败: ${err instanceof Error ? err.message : '请稍后重试'}`,
      '绑定失败'
    )
  }
}

const handleRemoveReferenceNovel = async (novelId: number) => {
  if (!props.project?.id) return
  const remainingIds = boundReferenceNovelIds.value.filter((id) => id !== novelId)
  try {
    await novelStore.bindProjectReferenceNovels(props.project.id, remainingIds)
  } catch (err) {
    globalAlert.showError(
      `移出本书失败: ${err instanceof Error ? err.message : '请稍后重试'}`,
      '操作失败',
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

const compactChapterState = (chapterNumber: number) => {
  if (isChapterGenerating(chapterNumber) || isChapterSelecting(chapterNumber)) return 'working'
  if (isChapterEvaluating(chapterNumber)) return 'evaluating'
  if (isChapterFailed(chapterNumber)) return 'failed'
  if (hasChapterInProgress(chapterNumber)) return 'confirm'
  if (isChapterCompleted(chapterNumber)) return 'done'
  return 'planned'
}

const compactChapterStatus = (chapterNumber: number) => {
  const labels: Record<string, string> = {
    working: '生成中',
    evaluating: '评审中',
    failed: '失败',
    confirm: '待选版',
    done: '已完成',
    planned: '已规划',
  }
  return labels[compactChapterState(chapterNumber)]
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
.wd-sidebar-shell,
.wd-sidebar-shell > div:not(.fixed) {
  min-height: 0;
}

.drawer-tabbar {
  display: grid;
  flex: 0 0 auto;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  margin: 0 14px 10px;
  padding: 4px;
  border: 1px solid #292b26;
  border-radius: 12px;
  background: #0e0f0d;
}

.drawer-tabbar button {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 42px;
  padding: 0 12px;
  border: 0;
  border-radius: 9px;
  color: #777a73;
  background: transparent;
  cursor: pointer;
  transition: 0.18s ease;
}

.drawer-tabbar button:hover {
  color: #f2f2ec;
  background: #171815;
}

.drawer-tabbar button.active {
  color: #11120f;
  background: #ffe500;
  box-shadow: 0 8px 25px rgba(255, 229, 0, 0.12);
}

.drawer-tabbar span {
  font-size: 13px;
  font-weight: 780;
}

.drawer-tabbar small {
  font-size: 9px;
  font-weight: 750;
}

.drawer-tools-pane,
.chapter-drawer-pane {
  min-height: 0;
  scrollbar-color: #383a34 transparent;
  scrollbar-width: thin;
}

.drawer-tools-pane {
  flex: 1 1 auto;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 4px 14px 20px;
}

.tool-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 16px;
  border: 1px solid #292b26;
  border-radius: 14px;
  background:
    radial-gradient(circle at 100% 0, rgba(255, 229, 0, 0.09), transparent 42%),
    #151613;
}

.tool-hero p,
.tool-hero h3,
.tool-hero span,
.tool-section-head h4,
.tool-section-head small {
  margin: 0;
}

.tool-hero p,
.tool-section-head small {
  color: #676a62;
  font-size: 8px;
  font-weight: 850;
  letter-spacing: 0.16em;
}

.tool-hero h3 {
  margin-top: 5px;
  color: #f5f5ef;
  font-size: 17px;
  font-weight: 780;
}

.tool-hero > div > span {
  display: block;
  max-width: 210px;
  margin-top: 4px;
  overflow: hidden;
  color: #858880;
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-hero > button {
  display: flex;
  flex: 0 0 auto;
  min-width: 86px;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
  padding: 9px 11px;
  border: 1px solid rgba(255, 229, 0, 0.23);
  border-radius: 10px;
  color: #ffe500;
  background: rgba(255, 229, 0, 0.06);
}

.tool-hero > button small {
  color: #777a72;
  font-size: 8px;
}

.tool-hero > button strong {
  font-size: 11px;
}

.tool-section {
  margin-top: 18px;
}

.tool-section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin: 0 2px 9px;
}

.tool-section-head h4 {
  margin-top: 3px;
  color: #f0f0eb;
  font-size: 13px;
  font-weight: 760;
}

.tool-section-head > span {
  color: #777a72;
  font-size: 9px;
}

.tool-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.tool-action-card {
  display: flex;
  min-width: 0;
  min-height: 70px;
  align-items: center;
  gap: 10px;
  padding: 11px;
  border: 1px solid #292b26;
  border-radius: 12px;
  color: #f2f2ed;
  text-align: left;
  background: #151613;
  cursor: pointer;
  transition: 0.18s ease;
}

.tool-action-card:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: #4a4d43;
  background: #1a1b17;
}

.tool-action-card.is-primary {
  border-color: rgba(255, 229, 0, 0.3);
  background: rgba(255, 229, 0, 0.065);
}

.tool-action-card.is-danger {
  border-color: rgba(242, 94, 94, 0.28);
  color: #ff8989;
  background: rgba(170, 45, 45, 0.08);
}

.tool-action-card:disabled {
  cursor: not-allowed;
  opacity: 0.38;
}

.tool-action-card > span:last-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.tool-action-card strong,
.tool-action-card small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tool-action-card strong {
  font-size: 11px;
  font-weight: 760;
  white-space: nowrap;
}

.tool-action-card small {
  color: #6f726b;
  font-size: 8px;
  line-height: 1.35;
}

.tool-action-icon {
  display: grid;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  place-items: center;
  border: 1px solid #34362f;
  border-radius: 9px;
  color: #ffe500;
  font-size: 10px;
  font-weight: 850;
  background: #20211d;
}

.mode-pill {
  padding: 5px 8px;
  border: 1px solid #34362f;
  border-radius: 999px;
  color: #8a8d85;
  background: #171815;
  font-size: 8px;
  font-weight: 750;
}

.mode-pill.active {
  border-color: rgba(255, 229, 0, 0.25);
  color: #ffe500;
  background: rgba(255, 229, 0, 0.05);
}

.compact-chapter-head {
  padding: 5px 16px 11px;
}

.compact-chapter-title {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
}

.compact-chapter-title small {
  color: #5f625b;
  font-size: 8px;
  font-weight: 850;
  letter-spacing: 0.17em;
}

.compact-chapter-title h3 {
  margin: 3px 0 0;
  color: #f5f5ef;
  font-size: 17px;
  font-weight: 760;
}

.compact-chapter-title > strong {
  color: #ffe500;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.compact-chapter-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 7px;
  margin-top: 11px;
}

.compact-chapter-controls button {
  display: flex;
  min-width: 0;
  min-height: 38px;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 0 9px;
  border: 1px solid #292b26;
  border-radius: 9px;
  color: #71746c;
  background: #151613;
}

.compact-chapter-controls span {
  font-size: 8px;
}

.compact-chapter-controls strong {
  overflow: hidden;
  color: #e7e8e1;
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-batch-entry {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  margin-top: 7px;
  padding: 9px 9px 10px;
  overflow: hidden;
  border: 1px solid rgba(255, 229, 0, 0.2);
  border-radius: 9px;
  background: rgba(255, 229, 0, 0.045);
}

.compact-batch-entry.running {
  padding-bottom: 13px;
}

.compact-batch-entry > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.compact-batch-entry small,
.compact-batch-entry strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-batch-entry small {
  color: #ffe500;
  font-size: 8px;
  font-weight: 780;
}

.compact-batch-entry strong {
  color: #b6b8b0;
  font-size: 9px;
  font-weight: 620;
}

.compact-batch-entry > button {
  min-height: 28px;
  padding: 0 9px;
  border: 0;
  border-radius: 7px;
  color: #11120f;
  background: #ffe500;
  font-size: 9px;
  font-weight: 820;
}

.compact-batch-entry > button.stop {
  border: 1px solid rgba(242, 112, 112, 0.25);
  color: #ef8585;
  background: rgba(151, 48, 48, 0.09);
}

.compact-batch-progress {
  position: absolute;
  right: 9px;
  bottom: 6px;
  left: 9px;
  height: 2px;
  overflow: hidden;
  border-radius: 99px;
  background: #303129;
}

.compact-batch-progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #ffe500;
  transition: width 0.3s ease;
}

.compact-volume-select {
  width: 100%;
  height: 36px;
  margin-top: 7px;
  padding: 0 10px;
  border: 1px solid #292b26;
  border-radius: 9px;
  outline: none;
  color: #b4b6af;
  background: #151613;
  font-size: 10px;
}

.compact-loop-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 7px;
}

.compact-loop-labels span {
  padding: 3px 6px;
  border-radius: 999px;
  color: #888b83;
  background: #1b1c19;
  font-size: 8px;
}

.compact-loop-empty {
  margin: 7px 2px 0;
  color: #62655e;
  font-size: 8px;
}

.compact-chapter-list {
  padding: 0 10px 18px;
}

.compact-chapter-rows {
  display: grid;
  gap: 4px;
}

.compact-chapter-row {
  position: relative;
  display: grid;
  width: 100%;
  min-height: 78px;
  grid-template-columns: 35px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 11px 10px;
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 11px;
  color: inherit;
  text-align: left;
  background: transparent;
  transition: 0.18s ease;
}

.compact-chapter-row:hover {
  background: #181916;
}

.compact-chapter-row.active {
  border-color: #31332d;
  background: #20211d;
}

.compact-row-accent {
  position: absolute;
  top: 11px;
  bottom: 11px;
  left: 0;
  width: 3px;
  border-radius: 0 4px 4px 0;
  background: transparent;
}

.compact-chapter-row.active .compact-row-accent {
  background: #ffe500;
}

.compact-row-index {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid #343630;
  border-radius: 50%;
  color: #858880;
  font-size: 10px;
  font-weight: 760;
  background: #20211e;
}

.compact-row-index svg {
  width: 16px;
  color: #36d885;
}

.compact-chapter-row.active:not(.done) .compact-row-index {
  border-color: #ffe500;
  color: #10110e;
  background: #ffe500;
}

.compact-row-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.compact-row-copy strong,
.compact-row-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-row-copy strong {
  color: #f0f0eb;
  font-size: 11px;
  font-weight: 740;
}

.compact-row-copy small {
  color: #6f726b;
  font-size: 9px;
}

.compact-chapter-row > em {
  align-self: start;
  margin-top: 3px;
  color: #6e7169;
  font-size: 8px;
  font-style: normal;
  white-space: nowrap;
}

.compact-chapter-row > em[data-state='done'] {
  color: #36d885;
}

.compact-chapter-row > em[data-state='working'],
.compact-chapter-row > em[data-state='evaluating'] {
  color: #ffe500;
}

.compact-chapter-row > em[data-state='failed'] {
  color: #ff8181;
}

.compact-chapter-row > em[data-state='confirm'] {
  color: #ffbd56;
}

.compact-rhythm-tags {
  display: flex;
  gap: 3px;
}

.compact-rhythm-tags i {
  display: grid;
  width: 16px;
  height: 16px;
  place-items: center;
  border-radius: 4px;
  color: #ffe500;
  background: rgba(255, 229, 0, 0.08);
  font-size: 7px;
  font-style: normal;
}

.overview-collapsible {
  border-top: 1px solid #2A2A2A;
}

.overview-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.7rem 1rem;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #ffffff;
  font-size: 0.85rem;
  font-weight: 700;
}

.overview-toggle:hover {
  background: #161616;
}

.overview-toggle-main {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.overview-toggle-meta {
  color: #777777;
  font-size: 0.7rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.overview-chevron {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  color: #FFE500;
  transition: transform 0.2s;
}

.overview-toggle-state {
  flex-shrink: 0;
  color: #FFE500;
  font-size: 0.72rem;
  font-weight: 700;
}

.reference-panel {
  margin: 0 1rem 1rem;
  padding: 0.75rem;
  border-radius: 1rem;
  background: #1C1C1C;
  border: 1px solid #2A2A2A;
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
  color: #ffffff;
}

.reference-panel-subtitle {
  margin: 0;
  font-size: 0.7rem;
  color: #666666;
}

.reference-panel-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.reference-panel-link {
  background: transparent;
  border: none;
  color: #FFE500;
  font-size: 0.75rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 0.75rem;
  transition: color 0.15s;
}

.reference-panel-link:hover {
  color: #FFC300;
}

.reference-panel-link--primary {
  font-weight: 600;
  background: rgba(255, 229, 0, 0.08);
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
  background: #141414;
  border: 1px solid #2A2A2A;
}

.reference-panel-tag {
  font-size: 0.7rem;
  border-radius: 999px;
  padding: 0.1rem 0.5rem;
  text-transform: capitalize;
}

.reference-panel-tag[data-status="ready"] {
  background: rgba(46, 213, 115, 0.12);
  color: #2ED573;
}

.reference-panel-tag[data-status="analyzing"] {
  background: rgba(6, 182, 212, 0.12);
  color: #06B6D4;
}

.reference-panel-tag[data-status="failed"] {
  background: rgba(255, 71, 87, 0.12);
  color: #FF4757;
}

.reference-panel-empty {
  font-size: 0.75rem;
  color: #555555;
}

.workflow-panel {
  margin: 0 1rem 1rem;
  padding: 0.9rem;
  border-radius: 1rem;
  background: #141414;
  border: 1px solid #2A2A2A;
}

.workflow-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.workflow-panel-title {
  margin: 0;
  color: #ffffff;
  font-size: 0.95rem;
  font-weight: 700;
}

.workflow-panel-subtitle {
  margin: 0.15rem 0 0;
  color: #777777;
  font-size: 0.72rem;
}

.workflow-progress {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  color: #FFE500;
  background: rgba(255, 229, 0, 0.08);
  border: 1px solid rgba(255, 229, 0, 0.18);
  font-size: 0.72rem;
  font-weight: 700;
}

.workflow-steps {
  display: grid;
  gap: 0.35rem;
  margin-top: 0.8rem;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  color: #666666;
  font-size: 0.74rem;
}

.workflow-step.done {
  color: #A0A0A0;
}

.workflow-step.active {
  color: #FFFFFF;
}

.workflow-step-dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 999px;
  background: #333333;
}

.workflow-step.done .workflow-step-dot {
  background: #2ED573;
}

.workflow-step.active .workflow-step-dot {
  background: #FFE500;
  box-shadow: 0 0 0 3px rgba(255, 229, 0, 0.12);
}

.workflow-action {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: 0.85rem;
  padding: 0.7rem 0.85rem;
  border: none;
  border-radius: 0.85rem;
  background: #FFE500;
  color: #000000;
  cursor: pointer;
  font-size: 0.83rem;
  font-weight: 800;
}

.workflow-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.workflow-action-hint {
  color: rgba(0, 0, 0, 0.58);
  font-size: 0.68rem;
  font-weight: 600;
}

.workflow-mode-switch {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.35rem;
  margin-top: 0.75rem;
  padding: 0.25rem;
  border-radius: 0.75rem;
  background: #0F0F0F;
  border: 1px solid #242424;
}

.workflow-mode-switch button {
  min-height: 2rem;
  border: none;
  border-radius: 0.55rem;
  background: transparent;
  color: #777777;
  cursor: pointer;
  font-size: 0.72rem;
  font-weight: 700;
}

.workflow-mode-switch button.active {
  background: #FFE500;
  color: #000000;
}

.advanced-mode-entry {
  display: flex;
  width: 100%;
  min-height: 3rem;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 0.15rem;
  padding: 0.65rem 0.8rem;
  border: 1px dashed rgba(255, 229, 0, 0.32);
  border-radius: 0.85rem;
  background: rgba(255, 229, 0, 0.05);
  color: #FFE500;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 800;
  text-align: left;
}

.advanced-mode-entry small {
  color: #777777;
  font-size: 0.66rem;
  font-weight: 500;
}

.advanced-toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 0.8rem;
  border: 1px solid #2A2A2A;
  border-radius: 0.85rem;
  background: #141414;
  color: #A0A0A0;
  font-size: 0.78rem;
  font-weight: 700;
}

.advanced-tools {
  display: grid;
  gap: 0.55rem;
  margin-top: 0.6rem;
}

.advanced-tool-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.advanced-tool-btn {
  display: flex;
  min-height: 3.2rem;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 0.15rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid #2A2A2A;
  border-radius: 0.85rem;
  background: #141414;
  color: #FFFFFF;
  font-size: 0.78rem;
  font-weight: 700;
  text-align: left;
}

.advanced-tool-btn small {
  color: #666666;
  font-size: 0.66rem;
  font-weight: 500;
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
