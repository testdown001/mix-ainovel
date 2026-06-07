# Arboris-Novel | 网文作者的 AI 写作助手

## 简介

Arboris 是一个面向中文网文作者的 AI 辅助写作平台。它不是替代作者创作，而是作为"编辑团队"帮助作者：

- **管理设定**：角色、门派、世界观，不再前后矛盾
- **梳理灵感**：把零散的想法串成完整的故事线
- **智能写作**：AI 生成初稿，作者修改润色
- **质量把控**：多版本对比、角色一致性检查、伏笔追踪

---

## 核心特性

### 1. 完整写作工作流

```
概念对话 → 蓝图大纲 → 章节大纲 → AI 生成 → 多版本审核 → 向量存储
```

- **概念对话**：和 AI 聊聊你的想法，帮你梳理主线
- **蓝图管理**：设定世界观、修炼体系、势力分布
- **章节大纲**：每章的纲要在手，写作不跑偏
- **智能生成**：基于 RAG 检索上下文，生成符合设定的章节
- **版本对比**：一次生成多个版本，挑选最满意的
- **向量记忆**：已写内容自动向量化，供后续章节检索

### 2. 自创先进多 Agent 协作架构

面向长篇网文创作自研的可选 Agent 执行模式。当前主流程已收敛为顺序调用，核心生成仍复用 `PipelineOrchestrator`：

| Agent | 职能 | 说明 |
|-------|------|------|
| **TaiziAgent** | 需求解析 | 理解用户指令，提取写作目标 |
| **HubuAgent** | 技能增强 | 写作手法、风格模板 |
| **ZhongshuAgent** | 上下文规划 | 组装上下文，构建写作任务 |
| **BingbuAgent** | 章节生成 | 通过生成桥接复用传统流水线 |
| **MenxiaAgent** | 质量审核 | 章节质量把关 |

> **提示**：默认使用传统 `PipelineOrchestrator` 服务化流水线；通过 `HybridExecutor` 可选择 Agent 包装流程。

### 3. 多维度质量保障

- **六维评审**：情节、人物、文笔、节奏、爽点、伏笔
- **角色一致性**：自动检测人物设定矛盾
- **伏笔追踪**：记录埋下的坑，确保后续填上
- **护栏检查**：自动过滤违规内容
- **人味优化**：消除 AI 写作的机械感

### 4. 丰富的参考功能

- **参考书库**：上传喜欢的作品，学习其风格
- **参考风格提取**：从参考书中提取写作风格
- **写作模板**：预设各种场景的写作模板
- **作家 persona**：定义你的写作风格

---

## 技术架构

### 后端技术栈

| 技术 | 用途 |
|------|------|
| **FastAPI** | Web 框架 |
| **SQLAlchemy** | ORM (支持 SQLite/MySQL) |
| **Python 3.11+** | 运行环境 |
| **OpenAI API** | LLM 调用 (兼容 Ollama) |
| **Qdrant** | 向量检索与记忆存储 |

### 前端技术栈

| 技术 | 用途 |
|------|------|
| **Vue 3** | UI 框架 |
| **TypeScript** | 类型安全 |
| **Naive UI** | 组件库 |
| **TailwindCSS 4** | 样式 |
| **Pinia** | 状态管理 |
| **Vite** | 构建工具 |

### 项目结构

```
arboris-novel/
├── backend/
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── services/     # 业务逻辑 (110+ 服务模块)
│   │   ├── models/       # 数据模型
│   │   ├── schemas/      # Pydantic 模型
│   │   ├── agents/       # Agent 系统
│   │   ├── prompts/      # 提示词模板
│   │   └── core/         # 核心配置
│   └── prompts/          # Markdown 提示词
├── frontend/
│   └── src/
│       ├── views/         # 页面组件
│       ├── components/    # 可复用组件
│       ├── stores/        # Pinia 状态
│       └── api/           # API 客户端
├── deploy/                # Docker 部署
└── docs/                 # 设计文档
```

---

## 快速开始

### 方式一：Docker 一键部署

```bash
# 1. 复制配置
cp deploy/.env.example .env

# 2. 编辑 .env，填入必要配置
#    - SECRET_KEY: JWT 密钥
#    - OPENAI_API_KEY: 你的 API Key
#    - ADMIN_DEFAULT_PASSWORD: 管理员密码

# 3. 启动
docker compose up -d

# 4. 访问 http://localhost:端口
```

### 方式二：本地开发

**后端：**
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

---

## 配置说明

### 必填配置

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | JWT 加密密钥 |
| `OPENAI_API_KEY` | LLM API Key |

### LLM 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENAI_API_BASE_URL` | OpenAI 地址 | API 端点 |
| `OPENAI_MODEL_NAME` | gpt-3.5-turbo | 模型名称 |
| `WRITER_CHAPTER_VERSION_COUNT` | 3 | 生成版本数 |

### Embedding 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_PROVIDER` | openai | embedding 提供商 |
| `EMBEDDING_MODEL` | text-embedding-3-small | 模型 |

### 向量检索配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VECTOR_TOP_K_CHUNKS` | 5 | 检索片段数 |
| `VECTOR_TOP_K_SUMMARIES` | 3 | 检索摘要数 |
| `VECTOR_CHUNK_SIZE` | 480 | 片段大小 |

---

## 预设模式

系统内置多种写作预设，适应不同场景：

| 模式 | 说明 | 特点 |
|------|------|------|
| `basic` | 基础模式 | 快速生成，适合初稿 |
| `platinum` | 铂金模式 | 质量优先，六维评审 |
| `fast` | 极速模式 | 轻量处理，快速产出 |
| `literary` | 文笔模式 | 精细打磨，文学性强 |

---

## 常见问题

### 生成相关

**Q: 提示"未配置默认 LLM API Key"？**  
A: 检查 `.env` 中的 `OPENAI_API_KEY` 是否正确配置。

**Q: AI 返回内容无法解析？**  
A: 常见于某些逆向 API，建议：多试几次、更换模型、切换到官方 API。

**Q: 生成内容质量不理想？**  
A: 尝试：完善角色/世界观设定、优化章节纲要、使用多版本生成功能。

### 使用相关

**Q: 如何让 AI 懂我的写作风格？**  
A: 在"作家 persona"中定义你的风格，或上传参考书让系统学习。

**Q: 角色设定总是前后矛盾？**  
A: 启用"角色一致性检查"、实体注册表、角色状态和审核服务；Agent 模式下由规划/审核阶段一起约束。

**Q: 想用自己部署的模型？**  
A: 配置 `OPENAI_API_BASE_URL` 指向你的 Ollama 或其他兼容 API。

*祝你写作顺利，故事精彩！*
