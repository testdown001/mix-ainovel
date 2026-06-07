# 章节质量审核机制 - 数据库迁移与使用文档

## 概述

章节质量审核机制是第二阶段的核心功能，旨在将"评审"从事后诸葛变为强制关卡，确保章节质量符合标准。

## 一、数据库迁移

### 方式一：使用迁移脚本（推荐）

```bash
cd /path/to/arboris-novel

# 执行迁移脚本（会自动创建 chapter_reviews 表）
bash deploy/scripts/run_migrations.sh
```

迁移脚本会自动执行 `backend/db/migrations/add_chapter_reviews.sql`，创建以下表：

```sql
CREATE TABLE chapter_reviews (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(36) NOT NULL,
    chapter_number INT NOT NULL,
    approved TINYINT(1) NOT NULL DEFAULT 0,
    overall_score FLOAT NOT NULL,
    scores JSON,
    issues JSON,
    review_comment TEXT,
    rewrite_required TINYINT(1) NOT NULL DEFAULT 0,
    chapter_version_id BIGINT,
    created_at DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_project_chapter (project_id, chapter_number)
);
```

### 方式二：手动执行 SQL

```bash
mysql -h localhost -u arboris -p arboris < backend/db/migrations/add_chapter_reviews.sql
```

### 验证迁移

```bash
# 检查表是否创建成功
mysql -h localhost -u arboris -p arboris -e "DESCRIBE chapter_reviews;"
```

## 二、功能说明

### 审核维度

| 维度 | 字段名 | 说明 |
|------|--------|------|
| 剧情一致性 | consistency | 与大纲、前文、世界观的衔接 |
| 角色立体度 | character_depth | 角色动机、性格一致性、成长变化 |
| 节奏张力 | pacing | 节拍、高潮转折、节奏把握 |
| 伏笔呼应 | foreshadowing | 伏笔呼应、新伏笔埋入 |
| 文笔质量 | prose_quality | 精彩句子、描写生动性 |
| 情绪曲线 | emotion_curve | 情绪起伏、共情能力 |

### 审核阈值

```python
REVIEW_THRESHOLDS = {
    "overall_score": 70,         # 综合评分 >= 70
    "min_dimension_score": 50,   # 单项最低 >= 50
    "max_high_issues": 2,       # 严重问题 <= 2
}
```

### 判定逻辑

1. 综合评分 >= 70 且
2. 所有单项评分 >= 50 且
3. 严重问题数量 <= 2

→ 审核通过 (approved = true)

否则 → 需要修改 (approved = false)

## 三、API 接口

### 1. 执行审核

```bash
POST /api/review/gatekeeper

Request:
{
    "project_id": "项目ID",
    "chapter_number": 1,
    "chapter_version_id": 123  # 可选，默认使用最新版本
}

Response:
{
    "project_id": "项目ID",
    "review": {
        "id": 1,
        "project_id": "项目ID",
        "chapter_number": 1,
        "approved": true,
        "overall_score": 85,
        "scores": {
            "consistency": 85,
            "character_depth": 70,
            "pacing": 90,
            "foreshadowing": 60,
            "prose_quality": 75,
            "emotion_curve": 80
        },
        "issues": [...],
        "review_comment": "总体评价...",
        "rewrite_required": false,
        "created_at": "2026-03-07T10:00:00"
    }
}
```

### 2. 获取审核结果

```bash
GET /api/review/gatekeeper/{project_id}/{chapter_number}
```

## 四、前端使用

### 组件

- `GatekeeperResult.vue` - 审核结果展示组件

### API 文件

- `gatekeeperReview.ts` - 审核 API 封装

```typescript
// 执行审核
import { runGatekeeperReview } from '@/api/gatekeeperReview'
const result = await runGatekeeperReview(projectId, chapterNumber)

// 获取审核结果
import { getGatekeeperReview } from '@/api/gatekeeperReview'
const result = await getGatekeeperReview(projectId, chapterNumber)
```

## 五、流水线集成

审核机制目前为**可选手动触发**模式。用户可以在章节生成完成后：

1. 点击"审核"按钮
2. 系统调用 `POST /api/review/gatekeeper` 执行审核
3. 展示审核结果（通过/需要修改）
4. 如需修改，可点击"重新生成"

如需在生成流程中自动触发审核，可修改 `pipeline_orchestrator.py` 在章节生成完成后自动调用 `GatekeeperReviewService.review_chapter()`。

## 六、文件清单

| 文件 | 说明 |
|------|------|
| `backend/app/models/chapter_review.py` | ChapterReview 模型 |
| `backend/app/services/gatekeeper_review_service.py` | 审核服务 |
| `backend/prompts/gatekeeper_review.md` | 审核 prompt 模板 |
| `backend/app/api/routers/review.py` | 审核 API 路由 |
| `backend/db/migrations/add_chapter_reviews.sql` | 数据库迁移脚本 |
| `frontend/src/api/gatekeeperReview.ts` | 前端 API |
| `frontend/src/components/writing-desk/GatekeeperResult.vue` | 前端组件 |

## 七、注意事项

1. **Prompt 加载**：审核 prompt 模板位于 `backend/prompts/gatekeeper_review.md`，启动时会自动加载到数据库
2. **内容长度限制**：审核时内容限制在 15000 字符内
3. **上下文获取**：审核时会尝试获取大纲、前文摘要、世界观设定作为参考
4. **并发安全**：审核服务使用独立 session，支持并发调用
