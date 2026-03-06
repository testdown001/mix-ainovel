# 章节字数控制机制分析与优化方案

## 一、当前字数控制机制全景

### 1.1 配置层（入口）

| 配置项 | 位置 | 默认值 | 说明 |
|--------|------|--------|------|
| `WRITER_CHAPTER_WORD_COUNT_MIN` | `config.py:91` | **3000** | 章节最低字数 |
| `WRITER_CHAPTER_WORD_COUNT_MAX` | `config.py:96` | **4000** | 章节最高字数 |
| `WRITER_MAX_TOKENS` | `config.py:101` | **16384** | LLM 输出最大 token 数 |
| `CHAPTER_MIN_WORDS` | `constants.py:3` | 2000 | 硬编码回退常量（最低） |
| `CHAPTER_MAX_WORDS` | `constants.py:4` | 4000 | 硬编码回退常量（最高） |
| `CHAPTER_RECOMMENDED_WORDS` | `constants.py:5` | 2800 | 硬编码回退常量（推荐） |

**当前默认 `config.py` 中 min=3000, max=4000，已经是你想要的 3000-4000 范围。**

### 1.2 运行时解析

`pipeline_orchestrator.py:1545` — `_resolve_word_count_bounds()`

```python
min_words = settings.writer_chapter_word_count_min   # 默认 3000
max_words = settings.writer_chapter_word_count_max   # 默认 4000
target_words = min_words + (max_words - min_words) // 2  # = 3500
```

计算得到三个值：`(3000, 4000, 3500)`，贯穿整个生成流水线。

---

### 1.3 控制链路（字数如何从配置传递到最终输出）

#### 层级 1：Prompt 提示词注入（"软"控制）

**文件**：`pipeline_prompt.py:24-52` — `_build_word_count_rule()`

将字数要求构建成自然语言约束，注入到 LLM 的用户提示词中：

```
【硬性要求】本章正文必须控制在 3000 到 4000 字之间，目标约 3500 字。
超过 4000 字即为不合格，必须精简。
宁可少写一个场景细节，也绝对不要超过 4000 字。
```

这段文字作为 `[章节字数要求]` section 注入到 `_build_prompt_sections()` 的输出中（`pipeline_prompt.py:275-283`）。

**三个 Prompt 模板也包含字数铁律**：
- `writing_v3.md`（第 9-10 行）：「字数铁律 — 严格遵守[章节字数要求]」
- `writing_v2.md`（第 13-18 行）：同上
- `writing.md`（第 85-88 行）：「每章正文字数最少 2000 字，最多 4000 字」← **这里硬编码了旧值，与配置不同步**

#### 层级 2：max_tokens 物理限制（"硬"控制）

**标准模式**（`pipeline_orchestrator.py:1927-1940`）：

```python
dynamic_max_tokens = min(
    settings.writer_max_tokens,     # 16384
    int(max_word_count * 1.5),      # 4000 * 1.5 = 6000
)
# 实际 max_tokens = 6000
```

中文约 1.5 tokens/字，4000 字 × 1.5 = 6000 tokens，物理上限制 LLM 不会输出超过约 4000 字。

**Literary 场景分步模式**（`pipeline_orchestrator.py:1767`）：

```python
max_tokens = min(4096, int(max(700, scene_words) * 1.8))
# 每个场景独立限制，如 scene_words=700 → max_tokens = 1260
```

#### 层级 3：场景字数分配（Literary 模式）

**`_build_fallback_scenes()`**（`pipeline_orchestrator.py:1800-1808`）：

当 chapter_mission 中没有 scene_list 时，使用回退分配：
```python
total = word_budget.get("total", 3000)  # 默认 3000
scene_1: 25% → 750 字（开篇）
scene_2: 45% → 1350 字（发展）
scene_3: 30% → 900 字（高潮+收束）
总计: 3000 字
```

**chapter_plan.md 导演脚本**（`chapter_plan.md:69`）：
```
字数结构（参考[章节字数限制]中的范围，默认3000）
```

导演脚本中每个 scene 会设置 `target_words`，生成时按此分配。

#### 层级 4：后处理字数控制

**a) 扩写（字数不足时）** — `enrichment_service.py`
- 触发条件：当前字数 < 目标字数 × 80%（即 < 2800 字）
- 迭代扩写直到达到目标字数的 90%（即 3150 字）
- max_tokens 限制：`int(max_word_count * 1.5)`

**b) 密度压缩（字数接近上限时）** — `pipeline_orchestrator.py:1029-1038`
- 标准模式：仅在字数 ≥ max × 90%（≥ 3600 字）时才执行密度压缩
- 低于 90% 则跳过

**c) 超字数压缩（最终兜底）** — `pipeline_orchestrator.py:756-758, 1057-1060`
- 触发条件：`len(best_content) > chapter_word_count_max`（> 4000 字）
- 使用 LLM 压缩到目标范围内
- `_compress_overlength()` 方法：最多重试 2 次，max_tokens = `int(target_max * 1.2)` = 4800

**d) 超 102% 后处理压缩** — `pipeline_orchestrator.py:2003-2011`
- 标准模式 `_generate_chapter_version` 内
- 触发条件：`len(final_text) > max_word_count * 1.02`（> 4080 字）

---

## 二、当前问题诊断

### 问题 1：`writing.md` 硬编码字数与配置不同步

`writing.md:86` 写的是：
```
每章正文字数最少 2000 字，最多 4000 字
```
这个 2000 和 `config.py` 的 min=3000 不一致。如果使用 writing.md 作为 system_prompt，LLM 可能会生成 2000-3000 字的内容，低于配置的最低要求。

### 问题 2：`constants.py` 回退常量偏低

```python
CHAPTER_MIN_WORDS = 2000        # 比 config 的 3000 低
CHAPTER_RECOMMENDED_WORDS = 2800  # 比计算出的 3500 低
```
如果 `config.py` 的值解析失败，会回退到这些较低的常量。

### 问题 3：场景分步生成的 total 默认值偏低

`_build_fallback_scenes()` 中：
```python
total = word_budget.get("total", 3000)  # 默认 3000
```
如果 chapter_mission 没有 word_budget，则只分配 3000 字，低于目标 3500 字。

### 问题 4：chapter_plan.md 导演脚本的默认值

```
字数结构（参考[章节字数限制]中的范围，默认3000）
```
导演脚本默认目标 3000，偏向下限，导致生成的 scene_list 字数总和偏低。

### 问题 5：扩写触发阈值偏低

enrichment 触发条件是字数 < 目标 × 80% = 2800 字，意味着 2800-3500 字之间的内容不会触发扩写，可能不够充实。

---

## 三、优化执行方案

### 目标：确保章节最终输出正文稳定控制在 3000-4000 中文字符

---

### Step 1：同步 `constants.py` 常量与 `config.py` 默认值

**文件**：`backend/app/core/constants.py`

```python
# 改动前
CHAPTER_MIN_WORDS = 2000
CHAPTER_MAX_WORDS = 4000
CHAPTER_RECOMMENDED_WORDS = 2800

# 改动后
CHAPTER_MIN_WORDS = 3000
CHAPTER_MAX_WORDS = 4000
CHAPTER_RECOMMENDED_WORDS = 3500
```

同步更新 `CHAPTER_WORD_COUNT_RULE` 字符串中的数值（因为它引用了上述常量，会自动同步）。

**影响**：当 `config.py` 的值解析失败回退时，不会降到 2000。

---

### Step 2：修正 `writing.md` 硬编码字数

**文件**：`backend/prompts/writing.md`（第 86-88 行）

```markdown
# 改动前
*   **必须满足**：每章正文字数最少 2000 字，最多 4000 字（含边界）。

# 改动后
*   **必须满足**：严格遵守[章节字数要求]中指定的字数区间。
```

让 `writing.md` 不再硬编码数字，而是引用动态注入的 `[章节字数要求]` section（与 `writing_v2.md`、`writing_v3.md` 保持一致）。

---

### Step 3：修正场景回退分配的默认总字数

**文件**：`backend/app/services/pipeline_orchestrator.py`（`_build_fallback_scenes` 方法，约第 1802 行）

```python
# 改动前
total = word_budget.get("total", 3000) if isinstance(word_budget, dict) else 3000

# 改动后
total = word_budget.get("total", 3500) if isinstance(word_budget, dict) else 3500
```

改为 3500（min 和 max 的中间值），使回退场景分配更接近目标字数。

---

### Step 4：修正导演脚本默认字数描述

**文件**：`backend/prompts/chapter_plan.md`（第 69 行）

```markdown
# 改动前
### 2.3 字数结构（参考[章节字数限制]中的范围，默认3000，浮动）

# 改动后
### 2.3 字数结构（参考[章节字数限制]中的范围，默认3500，浮动）
```

同时调整各结构段的默认字数分配（第 70-74 行）：

```markdown
# 改动前
- opening_hook：200-500
- development：1200-1800
- climax：600-1200
- ending_hook：100-400

# 改动后
- opening_hook：300-500
- development：1500-2000
- climax：800-1200
- ending_hook：100-400
```

---

### Step 5：（可选）调整扩写触发阈值

**文件**：`backend/app/services/pipeline_orchestrator.py`（调用 `_run_enrichment` 的地方）

当前 enrichment_service 的默认 threshold 是 0.8（即 80%），意味着只有低于 3500 × 0.8 = 2800 字时才触发。

可以考虑将调用处的 threshold 提高到 0.85，使得低于 2975 字时就触发扩写，但这不是必须的——当前的多层控制已经比较充分。

---

### Step 6：确认 `.env` 配置

确认实际部署的 `.env` 文件中包含：

```env
WRITER_CHAPTER_WORD_COUNT_MIN=3000
WRITER_CHAPTER_WORD_COUNT_MAX=4000
WRITER_MAX_TOKENS=16384
```

如果 `.env` 中没有这两个变量，`config.py` 会使用默认值 3000/4000，已经正确。但显式声明更安全。

---

## 四、字数控制完整流程图（优化后）

```
配置解析
├── config.py: min=3000, max=4000
├── _resolve_word_count_bounds() → (3000, 4000, 3500)
│
Prompt 层控制
├── [章节字数要求]: "控制在 3000-4000 字，目标 3500 字"
├── writing_v3.md: "严格遵守[章节字数要求]"
├── chapter_plan.md 导演脚本: word_budget_total ≈ 3500
│
生成层控制
├── 标准模式: max_tokens = min(16384, 4000×1.5) = 6000
├── Literary 场景分步: 每场景 max_tokens = min(4096, words×1.8)
│   └── 回退场景总字数: 3500（25%+45%+30%）
│
后处理控制
├── 扩写(enrichment): 低于 3500×80%=2800 字时触发
├── 密度压缩: 高于 4000×90%=3600 字时执行
├── 超字数压缩: 超过 4000 字时 LLM 压缩
└── 最终兜底: 超过 4000×102%=4080 字时强制压缩
```

---

## 五、变更文件清单

| 文件 | 改动内容 | 风险 |
|------|----------|------|
| `backend/app/core/constants.py` | MIN 2000→3000, RECOMMENDED 2800→3500 | 低：仅影响回退值 |
| `backend/prompts/writing.md` | 硬编码字数改为引用 [章节字数要求] | 低：与 v2/v3 对齐 |
| `backend/app/services/pipeline_orchestrator.py` | `_build_fallback_scenes` 默认 3000→3500 | 低：仅影响无 scene_list 时的回退 |
| `backend/prompts/chapter_plan.md` | 默认字数 3000→3500，结构分配微调 | 低：建议性文本 |
| `.env`（如需要） | 显式声明 WRITER_CHAPTER_WORD_COUNT_MIN/MAX | 无风险 |

**总计改动 4 个文件，均为参数/文本调整，不涉及逻辑重构。**

---

## 六、验证方式

1. 启动后端，生成一个章节，检查日志中的 `_resolve_word_count_bounds` 输出是否为 `(3000, 4000, 3500)`
2. 检查生成的 prompt 中 `[章节字数要求]` section 是否正确显示 3000-4000 范围
3. 生成 3-5 个章节，统计最终正文字数是否稳定落在 3000-4000 区间
4. 测试边界情况：故意低于 2800 字时是否触发扩写，超过 4000 字时是否触发压缩
