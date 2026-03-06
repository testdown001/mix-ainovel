# 参考小说库（Reference Novel Library）实现方案

## Context

当前灵感模式中，参考小说是一次性使用的：用户输入小说名 → WebSearchService 搜索 → 结果缓存 Redis 24h → 注入 concept prompt。搜索结果不持久化、不可跨项目复用、不结构化。

本方案将参考小说数据持久化为**全局共享库**，每本参考小说包含三个结构化档案（大纲+人物表、风格样本10段、全维度记忆卡），在**灵感对话**和**章节生成**两个场景中使用。

---

## 一、数据库模型

### 1.1 新建 `reference_novels` 表

文件：`backend/app/models/reference_novel.py`

```python
class ReferenceNovel(Base):
    __tablename__ = "reference_novels"

    id           : BIGINT PK autoincrement
    title        : String(255), unique, index       # 小说名称（全局去重）
    user_id      : FK → users.id, index             # 创建者

    # 三个核心档案
    outline_content        : LONGTEXT               # 大纲+人物表（纯文本）
    style_samples_content  : LONGTEXT               # 10段风格样本（纯文本）
    memory_card            : JSON                    # 全维度记忆卡（结构化JSON）

    # 元数据
    genre         : String(128)                      # 题材类型
    author        : String(128)                      # 原作者
    source_url    : String(512)                      # 来源URL
    status        : String(32) default="pending"     # pending → analyzing → ready / failed
    error_message : Text                             # 分析失败时的错误信息

    created_at / updated_at
```

设计要点：
- `title` unique 约束实现全局去重
- 三个档案直接嵌入主表，不拆分子表（奥卡姆剃刀）
- `status` 追踪异步分析状态

### 1.2 `NovelProject` 表新增字段

文件：`backend/app/models/novel.py`（第 30-62 行 `NovelProject` 类）

```python
reference_novel_ids : JSON default=[]    # 绑定的参考小说ID列表（最多3个）
```

在 `backend/app/db/init_db.py` 的 `_ensure_schema_updates()` 中（第 107-154 行）补齐历史列。

### 1.3 记忆卡 JSON 结构

```json
{
  "genre": "都市异能",
  "core_selling_point": "低调装逼打脸，强者回归",
  "target_audience": "18-30岁男性网文读者",
  "cool_point_patterns": ["实力碾压", "身份反转"],
  "pacing_traits": "开篇节奏快，3章内触发主线冲突",
  "world_type": "现代都市+隐藏超能力社会",
  "main_conflict_pattern": "主角回归→低调伪装→被挑衅→展露实力",
  "narrative_pov": "第三人称有限视角",
  "foreshadowing_techniques": ["身世之谜", "角色台词双关"],
  "suspense_techniques": ["章末钩子", "信息差悬念"],
  "dialogue_style": "简洁有力，内心吐槽感强",
  "scene_transition_style": "跳切为主",
  "emotion_control_pattern": "抑-抑-扬节奏",
  "commercial_data": { "word_count": "300万字", "update_frequency": "日更5000字", "reader_rating": "4.6/5" },
  "takeaways": ["开篇钩子的精准度", "配角塑造的层次感"],
  "risks": ["身份反转高度同质化", "后期重复打脸模式"]
}
```

### 1.4 模型注册

文件：`backend/app/models/__init__.py`（第 56 行之后添加导入，第 105 行之后添加 `__all__`）

---

## 二、Pydantic Schema

新建文件：`backend/app/schemas/reference_novel.py`

- `MemoryCard` — 全维度记忆卡结构（16 个字段）
- `ReferenceNovelCreate` — 创建请求（仅 title）
- `ReferenceNovelUpdate` — 手动编辑请求
- `ReferenceNovelSummary` — 列表概览
- `ReferenceNovelDetail` — 完整详情
- `ReferenceNovelSelectRequest` — 为项目绑定参考小说（reference_novel_ids: List[int]，max 3）

---

## 三、Prompt 模板

在 `backend/prompts/` 下新增 3 个文件：

| 文件 | 用途 |
|------|------|
| `reference_outline_extraction.md` | 引导 LLM 从搜索结果提取大纲结构 + 主要人物档案表 |
| `reference_style_extraction.md` | 引导 LLM 提取/仿写该小说标志性的 10 段风格样本 |
| `reference_memory_card_extraction.md` | 引导 LLM 按 MemoryCard schema 提取全维度记忆卡（JSON output） |

启动时自动通过 `_ensure_default_prompts()` 同步到 DB。

---

## 四、Service 层

### 4.1 新建核心服务

文件：`backend/app/services/reference_novel_library_service.py`

```
ReferenceNovelLibraryService(session)
├── CRUD
│   ├── list_all(search?)         # 全局列表，模糊搜索
│   ├── get_by_id(novel_id)
│   ├── get_by_title(title)       # 去重用
│   ├── create(user_id, title)    # 创建 status=pending 记录
│   ├── update(novel_id, data)    # 手动编辑
│   └── delete(novel_id, user_id) # 仅创建者/管理员
│
├── 自动分析
│   ├── analyze(novel_id, user_id)
│   │   1. status → analyzing
│   │   2. 复用 WebSearchService._search_single_novel(title) 获取搜索结果
│   │   3. 并行 3 个 LLM 调用：
│   │      ├── _extract_outline_and_characters(search_result, title) → outline_content
│   │      ├── _extract_style_samples(search_result, title) → style_samples_content
│   │      └── _extract_memory_card(search_result, title) → memory_card JSON
│   │   4. 写入 DB，status → ready（异常时 → failed + error_message）
│   │
│   ├── _extract_outline_and_characters()
│   ├── _extract_style_samples()
│   └── _extract_memory_card()        # response_format="json_object"
│
└── Prompt 格式化
    ├── format_for_concept_prompt(novels)        # 概念对话注入
    ├── format_style_samples_for_prompt(novels)  # few-shot 风格锚定
    └── format_memory_card_for_prompt(novels)    # 创作指导上下文
```

### 4.2 修改现有服务

#### `reference_prose_service.py`（209 行）

- 改造 `select_references()` 方法，增加参数 `project_reference_novels: List[ReferenceNovel] = []`
- 如果项目绑定了参考小说且有 style_samples_content，优先使用其风格样本作为 few-shot
- 否则回退到现有的硬编码 `PROSE_LIBRARY`

#### `pipeline_orchestrator.py`（约第 535-545 行 enable_reference_prose 分支）

- 在 reference_prose 注入前，先加载项目绑定的参考小说：`_load_project_reference_novels(project_id)`
- 将参考小说的风格样本传给改造后的 `ReferenceProseService.select_references()`
- 在 prompt_sections 中追加记忆卡上下文 `[参考小说创作指导]`

#### `novels.py` router（第 188-300 行 converse_with_concept）

- 概念对话时，先查库中是否已有该小说的 ready 记录
- 有 → 直接使用库中档案数据注入 prompt（不重复搜索）
- 无 → 执行现有搜索流程 + 后台触发 analyze 入库

---

## 五、API 端点

新建文件：`backend/app/api/routers/reference_novels.py`

```
前缀: /api/reference-novels

GET    /                        列出所有参考小说（?search=xxx 模糊搜索）
POST   /                        创建参考小说（传入 title，自动触发分析）
GET    /{novel_id}              获取单本详情（含三档案）
PUT    /{novel_id}              手动编辑档案
DELETE /{novel_id}              删除参考小说
POST   /{novel_id}/analyze      重新触发分析
```

在现有 `novels.py` 中扩展：

```
POST   /api/novels/{project_id}/reference-novels/bind   绑定参考小说 ID 列表
GET    /api/novels/{project_id}/reference-novels         获取项目绑定的参考小说
```

注册路由：`backend/app/api/routers/__init__.py`（第 3 行 import 和第 19 行 include_router）

---

## 六、前端

### 6.1 类型 + API 方法

文件：`frontend/src/api/novel.ts`

- 新增类型：`MemoryCard`, `ReferenceNovelSummary`, `ReferenceNovelDetail`
- 新增 API 方法：`listReferenceNovels`, `createReferenceNovel`, `getReferenceNovel`, `updateReferenceNovel`, `deleteReferenceNovel`, `analyzeReferenceNovel`, `bindProjectReferenceNovels`, `getProjectReferenceNovels`

### 6.2 新建组件

| 组件 | 功能 |
|------|------|
| `frontend/src/components/ReferenceNovelLibrary.vue` | 参考小说库管理弹窗（NModal），列表/搜索/创建/删除，分析状态展示（NTag），选择绑定 |
| `frontend/src/components/ReferenceNovelDetail.vue` | 详情查看/编辑（NTabs 切换三档案），记忆卡结构化表单展示 |

### 6.3 改造现有组件

#### `ReferenceNovelInput.vue`（276 行）

- 每个输入行增加"从库中选择"按钮
- 点击打开 ReferenceNovelLibrary 弹窗
- 选择后填入小说名 + 记录 reference_novel_id
- 新输入的小说名在 startConversation 时自动入库

#### `InspirationMode.vue`（460 行）

- `startConversation` 中，检查选中的参考小说在库中的状态
- ready → 使用库中档案，跳过搜索
- 不在库中 → 创建 + 分析 + 现有搜索流程并行
- 蓝图保存时，自动绑定参考小说 ID 到项目

#### `WDSidebar.vue`

- 增加"参考小说"折叠面板，展示项目绑定的参考小说摘要
- 支持跳转查看详情或绑定/解绑

---

## 七、实施步骤

### Phase 1: 后端基础
1. 新建 `backend/app/models/reference_novel.py`（ORM 模型）
2. 注册模型到 `backend/app/models/__init__.py`
3. 新建 `backend/app/schemas/reference_novel.py`（Pydantic Schema）
4. 新建 3 个 Prompt 模板到 `backend/prompts/`
5. 新建 `backend/app/services/reference_novel_library_service.py`（核心服务）
6. 新建 `backend/app/api/routers/reference_novels.py`（API 路由）
7. 注册路由到 `backend/app/api/routers/__init__.py`

### Phase 2: 后端集成
8. `NovelProject` 模型新增 `reference_novel_ids` 字段
9. `init_db.py` 的 `_ensure_schema_updates()` 补齐新列
10. 修改 `novels.py` router 概念对话逻辑（优先查库）
11. 修改 `reference_prose_service.py`（支持库中风格样本）
12. 修改 `pipeline_orchestrator.py`（章节生成注入记忆卡+风格样本）

### Phase 3: 前端
13. `frontend/src/api/novel.ts` 新增类型和 API 方法
14. 新建 `ReferenceNovelLibrary.vue` + `ReferenceNovelDetail.vue`
15. 改造 `ReferenceNovelInput.vue`（从库中选择）
16. 改造 `InspirationMode.vue`（适配新流程）
17. 改造 `WDSidebar.vue`（参考小说面板）

---

## 八、文件清单

### 新建文件（9 个）

| 文件 | 说明 |
|------|------|
| `backend/app/models/reference_novel.py` | ORM 模型 |
| `backend/app/schemas/reference_novel.py` | Pydantic Schema |
| `backend/app/services/reference_novel_library_service.py` | 核心业务 Service |
| `backend/app/api/routers/reference_novels.py` | API Router |
| `backend/prompts/reference_outline_extraction.md` | 大纲提取 Prompt |
| `backend/prompts/reference_style_extraction.md` | 风格样本提取 Prompt |
| `backend/prompts/reference_memory_card_extraction.md` | 记忆卡提取 Prompt |
| `frontend/src/components/ReferenceNovelLibrary.vue` | 库管理弹窗 |
| `frontend/src/components/ReferenceNovelDetail.vue` | 详情查看/编辑 |

### 修改文件（9 个）

| 文件 | 改动 |
|------|------|
| `backend/app/models/__init__.py` | 导入 ReferenceNovel |
| `backend/app/models/novel.py` | NovelProject 增加 reference_novel_ids |
| `backend/app/db/init_db.py` | _ensure_schema_updates 补齐新列 |
| `backend/app/api/routers/__init__.py` | 注册 reference_novels router |
| `backend/app/api/routers/novels.py` | 概念对话查库优先 + 绑定端点 |
| `backend/app/services/reference_prose_service.py` | select_references 支持库数据 |
| `backend/app/services/pipeline_orchestrator.py` | 注入记忆卡+风格样本 |
| `frontend/src/api/novel.ts` | 新增类型和 API 方法 |
| `frontend/src/components/ReferenceNovelInput.vue` | 增加"从库中选择" |
| `frontend/src/views/InspirationMode.vue` | 适配新流程 |
| `frontend/src/components/writing-desk/WDSidebar.vue` | 参考小说面板 |

---

## 九、验证方式

1. **启动后端**：`uvicorn app.main:app --reload`，确认 `reference_novels` 表自动创建
2. **API 测试**：
   - `POST /api/reference-novels` 创建参考小说
   - 确认 status 从 pending → analyzing → ready
   - `GET /api/reference-novels/{id}` 验证三档案内容完整
3. **灵感模式测试**：输入参考小说名 → 从库中选择 → 完成概念对话 → 蓝图生成
4. **章节生成测试**：项目绑定参考小说后，生成章节时检查 prompt 中是否包含风格样本和记忆卡上下文
5. **前端测试**：`npm run dev` → 灵感模式页面 → "从库中选择"弹窗交互正常

---

## 十、注意事项

- **LLM 调用成本**：每本参考小说分析 = 1 次搜索 + 3 次 LLM，前端需明确提示用户
- **并发去重**：多用户同时创建同一小说，靠 `title` unique 约束 + 先查后建
- **V1 不做向量化**：风格样本数量少（最多 30 段），直接全文注入 prompt 比向量检索更高效简洁
- **分析超时**：3 个 LLM 并行调用约 30-60s，前端使用轮询检查 status
