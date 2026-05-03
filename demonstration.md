# CBT Thought Record Agent Current Work Record

本文档是当前项目工作的阶段性记录和展示准备材料，不是最终项目报告。它根据 `proposal.md` 的项目目标，并结合当前仓库的真实代码状态，说明本项目是什么、已经实现了什么、各文件的作用、如何运行、如何使用，以及后续如何修改和扩展。

## 1. 项目说明

本项目实现的是一个基于 LLM 的 CBT Thought Record Agent。它不是医疗系统、诊断系统或正式治疗工具，而是一个结构化的自我记录与反思辅助工具，帮助用户围绕一个具体情绪事件完成 CBT thought record。

根据 proposal，本项目目标包括：

- 引导用户完成结构化 thought-record 流程
- 识别可能的 cognitive distortions
- 使用 Socratic-style questioning 促进反思
- 将会话以结构化 JSON 形式保存在本地
- 基于历史 session 生成 progress report
- 保持安全边界，遇到高风险语言时给出支持性提醒

当前项目实际已经实现：

- 一个 7-step CBT Thought Record Agent
- Terminal 交互版
- FastAPI JSON API 后端
- React + Vite 前端
- 本地 session JSON 保存。空 session 不会落盘，用户发送第一条消息后才开始保存
- 单 session / 多 session 报告生成。报告生成时会调用 LLM 生成 summary 和 action items
- 已保存 report 页面。可读取、查看和删除本地 report JSON，删除 report 不会修改原始 session
- session archive 页面。展示本地已保存且有用户输入的 session，支持 `completed` / `in_progress` / `stopped` 状态；详情只展示 thought record，不展示 conversation transcript
- settings 页面，用于切换模型、API 地址、保存路径和个人背景信息
- safety check，用于识别 self-harm / suicide 相关风险语言
- 一个轻量 RAG/knowledge-base 模块，用静态 CBT knowledge snippets 辅助 thought-record steps，尤其是 Step 4 cognitive distortions 和 Step 5 balanced thought

需要注意：proposal 中提到 Hugging Face CBT-Bench、C2D2 Dataset。当前代码并没有真正接入这些外部数据集，也没有实现向量数据库检索；目前的 RAG 更准确地说是基于 `backend/knowledge_base.py` 的静态知识库注入。

### 1.1 Cognitive Distortion 分类来源与权威性

当前项目使用的 cognitive distortion 分类方式是 Beck CBT 体系中的 worksheet taxonomy。具体 label set 来自 Beck Institute 的 `CBT Worksheet Packet 2020 Edition`，该 packet 标注为 adapted from Judith S. Beck, *Cognitive Behavior Therapy: Basics and Beyond*, 3rd edition (2020)。Beck Institute 官方资源页也说明这些 worksheets 是配套 Judith Beck 第三版 CBT 教材的 clinical resources。

因此，这套分类在 CBT thought record / worksheet 使用场景下是权威且合适的。需要注意的是，它不是 DSM/ICD 诊断分类，也不应该被系统用作 clinical diagnosis。本项目把这些 labels 作为 self-reflection / thought-record guidance 中的 tentative cognitive pattern labels：模型可以建议 1-3 个可能的 distortion，最终以用户确认的 `distortions` 为正式记录。

Reference links / 参考链接:

- [Beck Institute, `CBT Worksheet Packet 2020 Edition`](https://learn.beckinstitute.org/cms/delivery/media/MCPNPP5FFGJVDJ7C74SMXCMM5CWY)
- [Beck Institute, `Resources from Cognitive Behavior Therapy: Basics and Beyond, 3rd Edition`](https://beckinstitute.org/cbt-resources/resources-for-professionals-and-students/cbtresources/)
- [Beck Institute Cares, `Coping with Depression`](https://cares.beckinstitute.org/wp-content/uploads/sites/2/2021/06/Coping-with-Depression.pdf)
- [Guilford Press, Judith S. Beck, *Cognitive Behavior Therapy: Basics and Beyond*, 3rd edition](https://www.guilford.com/books/Cognitive-Behavior-Therapy/Judith-Beck/9781462544196)

### 1.2 当前已完成的最新修改

最近一轮功能完善后，当前项目状态如下：

- Profile / personal context 已接入。用户可以在首页右上角人像按钮中填写个人背景，这些内容会作为新 conversation 和 report summary 的上下文，但不是自动 memory。
- Session archive 已接入。顶部 `Session` 导航进入 `/sessions`，展示本地已保存且有用户输入的 sessions，分页展示，每页约 10 条。
- Session 详情只展示 thought record 字段，不展示 conversation transcript；`in_progress` session 可以从 archive 恢复继续，`completed` / `stopped` session 可以查看结构化记录。
- Session archive 支持删除本地 session JSON。删除 session 不会自动删除已经保存过的 report。
- 空 session 不会保存。只有用户发送消息后，session 才会写入本地 JSON。
- Report 页面只保留 Stitch 风格版本。
- Single-session 和 multi-session report 都有专门的 LLM summary/action-items prompt。
- 报告生成与保存已经分离。生成报告会调用 LLM；保存、查看已保存报告、删除报告都不会调用 LLM。
- 已保存 report 可以在页面删除。删除只影响 `reports/report_<report_id>.json`，不会改变任何 `sessions/session_<session_id>.json`。
- Multi-session report 中点击单个 session 会回到 session archive 查看原始 thought record，不会生成新的 single-session report。
- Multi-session report 的强度对比颜色已调整：调整前为浅红色，调整后为浅绿色。
- Conversation 使用的 LLM 会写入 session JSON 的 `conversation_llm`，report 生成使用的 LLM 会写入 report JSON 的 `report_llm`，前端会显示实际模型名称。
- OpenAI-compatible API key 推荐放在项目根目录 `.env` 文件中；`.env` 不提交 git，`.env.example` 提供示例。

## 2. 当前系统架构

项目现在主要分为四层：

```text
User
  |
  | Terminal / React Web UI
  v
FastAPI API / CLI entry
  |
  v
CBTAgent state machine
  |
  |-- LLM call
  |-- safety check
  |-- prompt rules
  |-- cognitive distortion knowledge base
  v
Local JSON storage
  |
  |-- sessions/session_<session_id>.json
  |-- reports/report_<report_id>.json
```

核心类是 `backend/agent.py` 中的 `CBTAgent`。它维护：

- `current_step`
- `session_id`
- `thought_record`
- `chat_history`
- `turns`
- `session_status`
- `safety_state`

每一轮用户输入后，Agent 大致执行：

```text
append user message
  -> safety check
  -> extract_and_fill()
  -> hard check current step completion
  -> maybe current_step += 1
  -> respond()
  -> append assistant message
  -> save_session()
```

注意：创建新 session 时，系统会先生成第一条 assistant 引导消息，但不会立刻写入 `sessions/`。只有用户真正发送消息后，session 才会保存到本地。这样可以避免用户只打开页面但没有完成任何输入时产生大量空 session 文件。

## 3. Thought Record 工作流

当前系统使用固定的 7-step workflow：

1. Situation + Emotion + Intensity Before + Automatic Thought
2. Evidence For
3. Evidence Against
4. Cognitive Distortions
5. Balanced Thought
6. Intensity After
7. Final Summary

每一步对应 `backend/prompts.py` 中的一个 prompt 方法：

- `CBTPrompts.step1()`
- `CBTPrompts.step2()`
- `CBTPrompts.step3()`
- `CBTPrompts.step4()`
- `CBTPrompts.step5()`
- `CBTPrompts.step6()`
- `CBTPrompts.step7()`

每一步必须满足 `CBTAgent.REQUIRED_FIELDS` 中定义的字段，才会进入下一步：

```python
{
    1: ["situation", "emotion", "intensity_before", "automatic_thought"],
    2: ["evidence_for"],
    3: ["evidence_against"],
    4: ["distortions"],
    5: ["balanced_thought"],
    6: ["intensity_after"],
    7: ["summary"]
}
```

最终 `thought_record` 的主要字段包括：

- `date`
- `situation`
- `emotion`
- `intensity_before`
- `automatic_thought`
- `evidence_for`
- `evidence_against`
- `distortions`
- `predicted_distortion`
- `balanced_thought`
- `intensity_after`
- `summary`

## 4. 项目结构

当前仓库主要结构如下：

```text
tra_test/
  proposal.md
  README.md
  demonstration.md
  workflow design.md
  test_case.md
  pyproject.toml
  uv.lock
  thought_record.json
  chat_history.json
  app_settings.json              # 运行后可能生成，用于保存前端 settings

  backend/
    __init__.py
    agent.py
    api_app.py
    app_settings.py
    config.py
    knowledge_base.py
    llm_io.py
    main.py
    prompts.py
    report_cli.py
    report_service.py
    safety.py
    storage.py
    web_app.py
    unused/
      agent_test.py
      prompts_old.py

  frontend/
    index.html
    package.json
    package-lock.json
    vite.config.ts
    vite.config.js
    tsconfig.json
    tsconfig.node.json
    src/
      App.tsx
      api.ts
      main.tsx
      styles.css
      types.ts

  sessions/
    session_<session_id>.json

  reports/
    report_<report_id>.json
```

## 5. 文件内容和作用

### 5.1 根目录文件

`proposal.md`

项目 proposal，说明项目目标、动机、挑战、架构设想、评估计划和项目定位。

`README.md`

当前已有的运行说明，包含 terminal 版本、web app 版本、API、报告功能和 settings 的使用方式。

`demonstration.md`

本文档。用于把 proposal 目标和当前实际代码状态整理成展示、答辩、开发交接都能使用的说明文档。

`workflow design.md`

CBT thought record 的理论材料和工作流参考，包括 identifying thoughts、thought records、testing your thoughts、cognitive distortions 等内容。

`test_case.md`

一个简单测试场景示例，内容围绕 job interview nervousness，可用于手动测试 Agent 是否能抽取 thought record 字段。

`pyproject.toml`

Python 项目配置。当前项目要求 Python `>=3.12`，依赖包括：

- `fastapi`
- `pydantic`
- `requests`
- `uvicorn`

`uv.lock`

`uv` 生成的 Python 依赖锁文件。

`thought_record.json` / `chat_history.json`

旧的或临时的记录文件。当前主流程主要使用 `sessions/` 下的 session JSON。

### 5.2 backend 文件

`backend/config.py`

全局默认配置。当前默认：

```python
LLM_PROVIDER = "ollama"
LLM_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma3:27b"
API_KEY_ENV_VAR = "OPENAI_API_KEY"
SESSIONS_DIR = "<project_root>/sessions"
REPORTS_DIR = "<project_root>/reports"
```

如果只想直接改默认模型、Ollama 地址、session 保存目录、report 保存目录，可以改这个文件。

`backend/app_settings.py`

用于读取和保存运行时 settings。React 前端右上角 settings 修改的内容会写入项目根目录下的 `app_settings.json`。它会把相对路径如 `sessions`、`reports` 自动解析为当前项目根目录下的路径，方便换电脑运行。

它也会在启动时读取项目根目录的 `.env` 文件，把里面的环境变量加载到当前后端进程。真实 API key 推荐放在 `.env` 中，`app_settings.json` 只保存环境变量名，例如 `OPENAI_API_KEY`。

`backend/llm_io.py`

统一封装 LLM 调用。当前支持两种 provider：

- `ollama`
- `openai_compatible` / `api`

当 provider 是 `ollama` 时，请求格式是：

```text
POST <LLM_URL>
{
  "model": "...",
  "prompt": "...",
  "stream": false,
  "temperature": ...
}
```

当 provider 是 `openai_compatible` 或 `api` 时，会调用：

```text
<LLM_URL>/chat/completions
```

并从环境变量读取 API key。

`backend/prompts.py`

保存系统 prompt、安全检测 prompt，以及 7 个 step 的具体 prompt 规则。它控制 Agent 的角色边界、语气、字段抽取标准、每一步的完成条件和 safety override 规则。

`backend/knowledge_base.py`

保存 CBT 轻量知识库。当前知识库内容都基于 Beck Institute 官方 worksheet / booklet 的说明，并在代码里保留 source notes。当前知识库分为两类：

1. Step-specific thought-record guidance：用于 Step 1/2/3/5，覆盖 identifying automatic thoughts、evidence for、evidence against 和 adaptive / alternative response guidance。
2. Cognitive distortion guidance：用于 Step 4，采用 Beck Institute `CBT Worksheet Packet 2020 Edition` 中的 12 个 cognitive distortion labels，并结合 Beck Institute `Coping with Depression` booklet 中的 thinking errors definitions 进行 paraphrased definitions 和 source-grounded examples。

这样系统不需要大型向量数据库，也不需要把 CBT-Bench / C2D2 全量塞进 prompt；每个 step 只注入当前最相关的小段 CBT knowledge，保持 prompt 可控。

当前 knowledge injection 方式是 step-based static injection，不是真正的 embedding/vector database RAG。具体流程是：

```text
current_step
  -> CBTPrompts.stepX()
  -> DistortionKnowledge.get_step_knowledge(step) 或 get_full_distortions()
  -> 拼入当前 step prompt
  -> agent.py 中的 extract_and_fill() / respond() 把 step prompt 放进 LLM prompt
```

也就是说，系统不是根据用户 query 去搜索知识库，而是根据当前 CBT step 固定注入一小段官方来源的相关知识：

- Step 1 注入 identifying automatic thoughts / situation-emotion-thought guidance
- Step 2 注入 evidence for guidance
- Step 3 注入 evidence against guidance
- Step 4 注入 cognitive distortion label set 和 definitions
- Step 5 注入 adaptive / alternative response guidance
- Step 6 不注入额外知识，只收集新的 emotion intensity
- Step 7 不注入额外知识，只基于完整 thought record 生成 summary

这对应 `improvement.md` 中建议的 rule-based lightweight RAG 思路，但当前没有单独拆成 `backend/rag.py`。

当前 label set 包括：

- All-or-nothing thinking
- Catastrophizing (fortune telling)
- Disqualifying or discounting the positive
- Emotional reasoning
- Labeling
- Magnification/minimization
- Mental filter
- Mind reading
- Overgeneralization
- Personalization
- Should and must statements
- Tunnel vision

Step 4 会把 cognitive distortion guidance 注入 prompt，让 LLM 只能从这些 label 中选择 distortion。由于 cognitive distortions 的边界本身可能重叠，系统设计上把模型输出视为 tentative suggestions；正式 `distortions` 字段应来自用户选择、接受或确认，而不是模型单方面诊断。

`backend/safety.py`

安全检测逻辑。它会先调用 LLM 做 semantic safety check，要求返回：

```json
{"risk_level":"normal|supportive_warning|acute_warning","reason":"short reason"}
```

如果 LLM 输出无法解析，会 fallback 到正则规则，例如检测 `suicide`、`kill myself`、`want to die` 等高风险表达。

`backend/storage.py`

负责把 session 保存为 JSON 文件。当前保存时机是：用户发送消息后，`process_user_turn()` 会更新并保存 session；仅创建新 session、尚未发送用户输入时不会保存空文件。保存内容包括：

- `session_id`
- `last_updated`
- `current_step`
- `session_status`
- `safety_state`
- `safety_reason`
- `thought_record`
- `chat_history`
- `turns`

默认保存到：

```text
sessions/session_<session_id>.json
```

`backend/agent.py`

项目核心文件。主要实现：

- `CBTAgent.__init__()`
- `process_user_turn()`
- `extract_and_fill()`
- `respond()`
- `ensure_predicted_distortions()`
- `update_record()`
- `save_session()`

其中 `extract_and_fill()` 负责调用 LLM 从用户输入中抽取 thought record 字段；`respond()` 负责生成下一轮自然语言引导；`process_user_turn()` 把 safety check、字段抽取、step 判断、回复生成和保存串起来。

`backend/main.py`

Terminal 版本入口。运行后会启动一个命令行 thought record session。

`backend/api_app.py`

当前推荐使用的 FastAPI JSON API 后端。React 前端通过这个服务访问后端能力。

主要接口：

- `GET /api/health`
- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/start`
- `POST /api/message`
- `GET /api/report-sessions`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/resume`
- `DELETE /api/sessions/{session_id}`
- `POST /api/reports/generate`
- `POST /api/reports/save`
- `GET /api/reports`
- `GET /api/reports/session/{session_id}`
- `GET /api/reports/multi`
- `GET /api/reports/{report_id}`
- `DELETE /api/reports/{report_id}`

`backend/report_service.py`

报告生成核心逻辑。它会读取 completed sessions，支持：

- 单个 session report
- 最近 N 个 session report
- 自定义多个 session report
- LLM-generated synthesis
- LLM-generated action items

报告指标包括：

- session 数量
- emotion 分布
- distortion 分布
- intensity before / after / delta
- improved sessions
- emotion trend
- distortion trends

保存后的报告文件位置：

```text
reports/report_<report_id>.json
```

当前前端中，`/reports/session/<session_id>` 和 `/reports/multi?...` 是“生成报告预览”，会调用 LLM，但不会自动保存；点击页面上的 `Save Report` 后，才会把当前已经生成好的 report 写入 `reports/`，不会再次调用 LLM。`/reports/<report_id>` 和 `/reports/saved` 只读取本地 JSON，不调用 LLM。

`backend/report_cli.py`

独立报告命令行工具。不需要打开前端，也可以直接列出 completed sessions 或生成报告。

`backend/web_app.py`

旧版一体化 FastAPI 页面。它直接在 Python 文件中拼接 HTML/CSS/JS。现在保留作为迁移前对照，推荐开发和展示使用 `backend/api_app.py` + React 前端。

`backend/unused/`

旧代码或测试代码，目前不属于主运行路径。

### 5.3 frontend 文件

`frontend/package.json`

前端项目配置。当前使用：

- React 19
- Vite 7
- TypeScript

主要命令：

```bash
npm run dev
npm run build
npm run preview
```

`frontend/vite.config.ts`

Vite 配置。当前前端服务端口为 `5173`，并把 `/api` 代理到：

```text
http://127.0.0.1:8000
```

所以运行 React 前端时，需要同时启动 FastAPI 后端。

`frontend/src/main.tsx`

React 入口文件，把 `App` 挂载到 `index.html` 中的 `#root`。

`frontend/src/App.tsx`

前端主页面和路由逻辑。当前包括：

- Home page
- Thought Record Session chat page
- Completed sessions archive page
- Reports home page
- Single session report page
- Multi-session report page
- Stitch report view
- Saved reports page
- Settings dialog
- Personal context dialog

当前前端没有使用 React Router，而是通过 `window.location.pathname` 和普通 `<a href>` 实现页面切换。

`frontend/src/api.ts`

前端 API 封装。包括：

- `startSession()`
- `sendMessage()`
- `listReportSessions()`
- `listSessions()`
- `getSession()`
- `getSingleSessionReport()`
- `getMultiSessionReport()`
- `getSavedReport()`
- `listSavedReports()`
- `saveGeneratedReport()`
- `deleteSavedReport()`
- `getSettings()`
- `updateSettings()`

`frontend/src/types.ts`

前后端数据结构的 TypeScript 类型定义，例如：

- `ThoughtRecord`
- `ChatMessage`
- `StartResponse`
- `MessageResponse`
- `ReportSession`
- `Report`
- `AppSettings`

`frontend/src/styles.css`

所有前端页面样式。

## 6. 如何运行

### 6.1 Python 后端准备

推荐使用 `uv`：

```bash
uv sync
```

如果不用 `uv`，也可以自己创建 venv 后安装：

```bash
pip install -e .
```

项目要求 Python `>=3.12`。

### 6.2 使用 Ollama 运行

默认配置使用本地 Ollama：

```python
LLM_PROVIDER = "ollama"
LLM_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma3:27b"
```

先启动 Ollama 并下载模型：

```bash
ollama serve
ollama pull gemma3:27b
```

如果想换模型，例如 `qwen2.5:7b`：

```bash
ollama pull qwen2.5:7b
```

然后修改 `backend/config.py` 或前端 settings：

```python
LLM_MODEL = "qwen2.5:7b"
```

### 6.3 使用 OpenAI-compatible API 运行

可以在前端 settings 或 `backend/config.py` 中设置：

```python
LLM_PROVIDER = "openai_compatible"
LLM_URL = "https://api.openai.com/v1"
LLM_MODEL = "<your_model_name>"
API_KEY_ENV_VAR = "OPENAI_API_KEY"
```

启动后端前设置环境变量：

```bash
export OPENAI_API_KEY="your_real_api_key"
```

项目不会把真实 API key 写入代码或 settings 文件，只保存环境变量名。推荐方式是在项目根目录复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

然后编辑 `.env`：

```text
OPENAI_API_KEY=your_real_api_key
```

`.env` 已加入 `.gitignore`，不会上传；`.env.example` 会保留在仓库中，方便别人知道需要配置哪些变量。

## 7. Terminal 版本使用方法

在项目根目录运行：

```bash
uv run python -m backend.main
```

程序会输出：

```text
=== CBT Session Started (ID: <session_id>) ===
Agent: Hello, I'm here to support you. What's on your mind today?
```

然后在 `You:` 后输入内容即可。用户开始输入后，每轮会自动：

- 做 safety check
- 抽取 thought record 字段
- 判断当前 step 是否完成
- 生成下一轮引导
- 保存 session JSON

退出方式：

```text
exit
quit
```

保存位置：

```text
sessions/session_<session_id>.json
```

## 8. Web App 使用方法

Web App 当前推荐使用：

- 后端：`backend.api_app`
- 前端：React + Vite

### 8.1 启动 FastAPI 后端

在项目根目录运行：

```bash
uv run uvicorn backend.api_app:app --reload --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

### 8.2 启动 React 前端

第一次运行需要安装前端依赖：

```bash
cd frontend
npm install
```

启动前端：

```bash
npm run dev
```

打开：

```text
http://127.0.0.1:5173/
```

前端会通过 Vite proxy 把 `/api/...` 请求转发到 `http://127.0.0.1:8000`。

### 8.3 页面使用流程

1. 打开首页
2. 点击 `Start Thought Record`
3. 在聊天框中描述一个最近情绪明显变化的具体时刻
4. Agent 会一步步引导你填写 situation、emotion、automatic thought、evidence、distortion、balanced thought 等内容
5. 用户发送第一条消息后开始保存本地 session JSON；完全空的 session 不会落盘
6. 完成 Step 7 后，页面会出现 `View Thought Record`
7. 点击后进入 session archive 中的 thought record 详情页，不会生成报告，也不会调用 LLM

### 8.4 Session Archive 页面

Session archive 入口：

```text
http://127.0.0.1:5173/sessions
```

当前规则：

- 展示本地已保存且有用户输入的 session，包括 `completed`、`in_progress` 和 `stopped`
- 列表每页约 10 条
- 点击 `completed` 或 `stopped` session 后进入 thought record 详情
- 点击 `in_progress` session 后会恢复到 conversation 页面继续完成
- 详情只展示结构化 thought record 字段，不展示 conversation transcript
- 详情页里的 `Generate Report` 只对 `completed` session 显示，点击后才会进入单 session report 生成页面并调用 LLM
- Session archive 支持删除本地 session JSON；删除 session 不会自动删除已经保存的 report
- 可以通过 `/sessions?session_id=<session_id>` 直接打开某个 session 的详情

### 8.5 报告页面

报告入口：

```text
http://127.0.0.1:5173/reports
```

单 session 报告：

```text
http://127.0.0.1:5173/reports/session/<session_id>
```

打开这个页面会调用 LLM 生成 report synthesis 和 action items，但不会自动保存。

最近 N 个 session 汇总报告：

```text
http://127.0.0.1:5173/reports/multi?mode=recent&limit=3
```

打开这个页面会调用 LLM 生成多个 session 的综合 summary。

自定义多个 session 汇总报告：

```text
http://127.0.0.1:5173/reports/multi?mode=custom&session_ids=<id1,id2,id3>
```

已保存报告列表：

```text
http://127.0.0.1:5173/reports/saved
```

当前只保留 Stitch 风格的 report 页面，不再维护旧版 report 页面，也不再需要 `style=stitch` 参数。

Report 操作规则：

- `Generate Report`：调用 LLM，生成当前页面中的 report 预览
- `Save Report`：保存当前已经生成好的 report JSON，不会再次调用 LLM
- `Saved Reports`：读取本地 report JSON，不会调用 LLM
- `Delete Report`：只删除 `reports/report_<report_id>.json`，不会修改或删除 `sessions/session_<session_id>.json`
- multi-session report 中点击单个 session，会跳转到 `/sessions?session_id=<session_id>` 查看原始 thought record，不会生成 single report

## 9. Report CLI 使用方法

如果只想在终端生成报告，可以使用：

```bash
uv run python -m backend.report_cli list-sessions
```

列出已保存的 reports：

```bash
uv run python -m backend.report_cli list-reports
```

生成单个 session report：

```bash
uv run python -m backend.report_cli generate --mode single --session-id <session_id>
```

生成最近 N 个 completed sessions 的汇总 report：

```bash
uv run python -m backend.report_cli generate --mode recent --limit 5
```

生成自定义 sessions 的汇总 report：

```bash
uv run python -m backend.report_cli generate --mode custom --session-ids <id1,id2,id3>
```

如果想直接打印完整 JSON：

```bash
uv run python -m backend.report_cli generate --mode recent --limit 5 --print-json
```

## 10. API 使用说明

### `GET /api/health`

检查后端是否启动。

返回示例：

```json
{"status":"ok"}
```

### `GET /api/settings`

读取当前模型、路径和个人背景配置。

### `PUT /api/settings`

保存 settings。前端 settings dialog 使用这个接口。

### `POST /api/start`

创建新 session。

返回：

```json
{
  "session_id": "20260502_181651",
  "message": "Hello, I'm here to support you. What's on your mind today?",
  "current_step": 1,
  "thought_record": {}
}
```

实际 `thought_record` 会包含所有默认字段。

### `POST /api/message`

处理一轮用户输入。

请求：

```json
{
  "session_id": "<session_id>",
  "message": "I failed the interview and I feel anxious, maybe 80."
}
```

返回：

```json
{
  "session_id": "<session_id>",
  "message": "<assistant reply>",
  "current_step": 1,
  "step_completed": false,
  "session_completed": false,
  "record_url": null,
  "thought_record": {}
}
```

### `GET /api/report-sessions`

列出可用于报告的 completed sessions。

### `GET /api/sessions`

列出 session archive 页面使用的本地 sessions。它会返回已经保存且有用户输入的 sessions，包括 `completed`、`in_progress` 和 `stopped`，但不会返回 conversation transcript。

### `GET /api/sessions/{session_id}`

读取某个 session 的完整 thought record 数据。前端 session archive 详情页使用这个接口。它不会调用 LLM，也不会生成 report。

### `POST /api/sessions/{session_id}/resume`

从本地 session JSON 恢复一个 `in_progress` session，并返回当前对话状态。前端点击进行中的 session 时会使用这个接口回到 conversation 页面继续。

### `DELETE /api/sessions/{session_id}`

删除本地 `sessions/session_<session_id>.json`。如果该 session 正在内存中的 active agent 列表里，也会一并移除。这个操作不会修改或删除已经保存的 report。

### `POST /api/reports/generate`

生成并保存 report JSON。这个接口适合直接 API 或 CLI 式使用。

支持 mode：

- `single`
- `recent`
- `custom`

前端当前保存按钮不使用这个接口，因为它会重新生成 report。

### `POST /api/reports/save`

保存当前前端已经生成好的 report JSON。这个接口只写入 `reports/report_<report_id>.json`，不会调用 LLM，也不会重新生成 summary。

### `GET /api/reports/session/{session_id}`

动态生成一个单 session report。当前前端会在打开这个页面时调用 LLM 生成 summary 和 action items，但不会自动保存到 `reports/`。

### `GET /api/reports/multi`

动态生成多 session report。当前前端会在打开这个页面时调用 LLM 生成 summary 和 action items，但不会自动保存到 `reports/`。

### `GET /api/reports/{report_id}`

读取已经保存的 report JSON。不会调用 LLM。

### `DELETE /api/reports/{report_id}`

删除已经保存的 report JSON。只删除 `reports/report_<report_id>.json`，不会修改原始 session 文件。

## 11. 数据文件格式

### 11.1 Session JSON

保存路径：

```text
sessions/session_<session_id>.json
```

大致结构：

```json
{
  "session_id": "20260502_181651",
  "last_updated": "2026-05-02 18:16:51",
  "current_step": 3,
  "session_status": "in_progress",
  "safety_state": "normal",
  "safety_reason": null,
  "last_safety_warning_turn": 0,
  "user_context": "optional user profile/context text",
  "conversation_llm": {
    "provider": "ollama",
    "model": "gemma2:9b",
    "url": "http://localhost:11434/api/generate",
    "api_key_env_var": "OPENAI_API_KEY"
  },
  "thought_record": {
    "date": "2026-05-02 18:16",
    "situation": "...",
    "emotion": "...",
    "intensity_before": 75,
    "automatic_thought": "...",
    "evidence_for": [],
    "evidence_against": [],
    "distortions": [],
    "predicted_distortion": [],
    "balanced_thought": "",
    "intensity_after": 0,
    "summary": ""
  },
  "chat_history": [
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "turns": [
    {
      "step_before": 1,
      "step_after": 2,
      "user": "...",
      "assistant": "...",
      "risk_state": "normal",
      "risk_reason": null,
      "include_safety_note": false
    }
  ]
}
```

`session_status` 可能是：

- `in_progress`
- `completed`
- `stopped`

报告功能默认只读取 `completed` sessions。

Session archive 页面显示所有已经保存且有用户输入的 sessions。创建 session 但完全没有发送用户消息时，不会产生 session JSON 文件；如果 session 已保存但未完成，会保留为 `in_progress`，并可从 session archive 恢复继续。

### 11.2 Report JSON

保存路径：

```text
reports/report_<report_id>.json
```

主要结构：

```json
{
  "report_id": "20260428_224844_920973",
  "generated_at": "2026-04-28 22:48:44",
  "scope": {
    "mode": "recent",
    "requested_limit": 5,
    "session_ids": ["..."],
    "report_type": "multi_session",
    "date_range": {
      "start": "...",
      "end": "..."
    }
  },
  "metrics": {},
  "sessions": [],
  "llm_summary": "...",
  "llm_action_items": ["...", "...", "..."],
  "llm_error": null,
  "include_llm_summary": true,
  "profile_context_used": true,
  "report_llm": {
    "provider": "openai_compatible",
    "model": "gpt-4o-mini",
    "url": "https://api.openai.com/v1",
    "api_key_env_var": "OPENAI_API_KEY"
  }
}
```

`llm_summary` 和 `llm_action_items` 只在生成报告时调用 LLM 得到。保存、查看和删除已保存报告都不会再次调用 LLM。

## 12. 如何修改项目

### 12.1 修改默认模型或 provider

方式一：改 `backend/config.py`

```python
LLM_PROVIDER = "ollama"
LLM_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "gemma3:27b"
```

方式二：打开网页右上角 settings，修改：

- Provider
- Model
- API / Ollama URL
- API key env var
- Sessions path
- Reports path

网页 settings 会写入 `app_settings.json`，新 session 会使用更新后的配置。

右上角人像按钮打开 personal context dialog。用户可以填写身份、性格、当前压力源、偏好的回复方式等背景信息。这不是长期 memory，也不会自动总结历史 session；它只是一个用户主动填写的 profile/context。当前它会用于：

- 新的 thought record conversation prompt
- report summary prompt

这些信息也会随 session 保存到本地 JSON 中，方便之后解释 report 时知道当时使用过什么背景。

### 12.2 修改工作流步骤

主要改两个地方：

1. `backend/prompts.py`
2. `backend/agent.py` 中的 `REQUIRED_FIELDS`

例如如果想增加一个新 Step，需要：

- 在 `CBTPrompts` 中添加新 `stepX()`
- 在 `REQUIRED_FIELDS` 中添加该 step 的必填字段
- 确认 `respond()` 中 `getattr(CBTPrompts, f"step{self.current_step}")()` 可以找到新 step
- 确认前端显示 current step 时不会出错
- 确认报告生成是否需要展示新增字段

### 12.3 修改 thought record 字段

主要改：

- `backend/agent.py` 中 `thought_record` 默认结构
- `backend/agent.py` 中 `REQUIRED_FIELDS`
- `backend/agent.py` 中 `_normalize_field()`
- `backend/prompts.py` 中相关 step prompt
- `backend/report_service.py` 中 report item 结构
- `frontend/src/types.ts`
- `frontend/src/App.tsx` 中 report 展示部分

### 12.4 修改 CBT knowledge base

改：

```text
backend/knowledge_base.py
```

当前知识库包含：

- `get_step_knowledge(step)`：按 step 返回短小的 source-grounded thought-record guidance
- `get_full_distortions()`：返回 Step 4 使用的 cognitive distortion label set 和判断说明

注意：`agent.py` 里的 `_distortion_label_set()` 会从 `get_full_distortions()` 中解析形如：

```text
1. All-or-nothing thinking
```

这样的编号 label。所以新增 distortion 时建议保持相同格式。

### 12.5 修改 safety 规则

主要改：

- `backend/prompts.py` 中 `safety_check()`
- `backend/safety.py`
- `backend/agent.py` 中 `SAFETY_FALLBACK_PATTERNS`

如果要支持更多风险类型，可以扩展 risk label，但要同步修改：

- `semantic_safety_check()` 允许的 label
- `support_guidance_line()`
- `respond()` 中的 safety prompt block

### 12.6 修改前端页面

主要改：

- 页面结构：`frontend/src/App.tsx`
- 样式：`frontend/src/styles.css`
- API：`frontend/src/api.ts`
- 类型：`frontend/src/types.ts`

当前前端路由是手写的，不是 React Router。如果页面数量继续增加，可以考虑引入 React Router，但现在项目规模下手写路由还能工作。

### 12.7 修改报告内容

主要改：

- `backend/report_service.py`
- `frontend/src/App.tsx` 中的 report pages
- `frontend/src/types.ts`

当前 report 已经有专门的 LLM summary prompt，核心函数是 `backend/report_service.py` 中的 `_generate_llm_report_summary()`。它要求 LLM 输出 JSON：

```json
{
  "synthesis": "...",
  "action_items": ["...", "...", "..."]
}
```

如果要修改报告生成的语言风格、summary 重点或 action items 的结构，优先修改这个 prompt。前端展示主要在 `StitchSingleReportPage`、`StitchMultiReportPage`、`StitchSynthesisCard`、`StitchActionItems` 这些组件中。

当前重要边界：

- 进入 `/reports/session/<session_id>` 或 `/reports/multi?...` 会调用 LLM 生成 report
- 点击 `Save Report` 不会调用 LLM，只保存当前 report
- 打开 saved report 不会调用 LLM
- 删除 saved report 不会调用 LLM，也不会修改 session

## 13. 当前实现与 proposal 的对应关系

| Proposal 功能 | 当前实现情况 | 主要文件 |
| --- | --- | --- |
| Prompt-constrained LLM | 已实现 | `backend/prompts.py`, `backend/agent.py` |
| Structured multi-step Agent | 已实现，7-step workflow | `backend/agent.py` |
| RAG / CBT knowledge | 部分实现，当前是静态 distortion knowledge base | `backend/knowledge_base.py` |
| Socratic questioning | 通过 step prompts 引导实现 | `backend/prompts.py` |
| Local record storage | 已实现，保存为 session JSON | `backend/storage.py`, `sessions/` |
| Report generator | 已实现结构化报告、统计指标、LLM summary 和 action items | `backend/report_service.py`, `backend/report_cli.py` |
| Saved report management | 已实现保存、查看、删除本地 report JSON；删除不影响 session | `backend/api_app.py`, `backend/report_service.py`, `frontend/src/App.tsx` |
| User profile/context | 已实现用户主动填写的 personal context，可用于新 session 和 report prompt | `backend/app_settings.py`, `backend/agent.py`, `backend/report_service.py`, `frontend/src/App.tsx` |
| Web interface | 已实现 React 前端 | `frontend/src/App.tsx` |
| Terminal interface | 已实现 | `backend/main.py` |
| Safety boundaries | 已实现基础 self-harm/suicide 检测和提醒 | `backend/safety.py`, `backend/prompts.py`, `backend/agent.py` |
| Evaluation with CBT-Bench / C2D2 | 尚未实现 | 可作为后续扩展 |

## 14. 手动演示建议

可以用 `test_case.md` 中的 interview nervousness 例子演示。

建议演示顺序：

1. 启动后端：

```bash
uv run uvicorn backend.api_app:app --reload --port 8000
```

2. 启动前端：

```bash
cd frontend
npm run dev
```

3. 打开：

```text
http://127.0.0.1:5173/
```

4. 点击 `Start Thought Record`

5. 输入类似：

```text
Thinking about the job interview, I will be so nervous, I won't know what to say, and then I won't get the job.
```

6. 按 Agent 提示继续补充：

```text
anxious 75
```

```text
I sometimes freeze when I am nervous.
```

```text
When I was nervous in the past, like when I got a new boss, I didn't have trouble talking.
```

```text
Catastrophizing (fortune telling)
```

```text
I'm nervous now, but I can practice more and I have handled nervous conversations before.
```

```text
45
```

7. 完成后点击 `View Thought Record`，展示结构化 thought record，不调用 report LLM。
8. 在 session 详情页点击 `Generate Report`，生成单 session report。
9. 打开 `/reports`，选择 recent 或 custom，生成多 session report。多 session report 中点击单个 session 会回到 session archive，而不是生成新的 single report。
10. 点击 `Save Report` 保存当前 report，再到 `/reports/saved` 查看或删除保存的 report。

## 15. 打包前检查与建议

当前仓库还没有正式的 `Dockerfile` 或 `docker-compose.yml`。如果要以 demonstration 为基础打包，建议先按下面顺序整理：

1. 确认本地直接运行稳定：

```bash
uv sync
uv run uvicorn backend.api_app:app --reload --port 8000
cd frontend
npm install
npm run dev
```

2. 确认 `.env`、`app_settings.json`、`sessions/session_*.json`、`reports/report_*.json` 没有被提交。真实 API key、个人 profile、测试 session 和 report 都应该留在本地。

3. 如果使用 Ollama，打包说明里需要提醒使用者单独安装 Ollama 并提前 pull 模型，例如：

```bash
ollama pull gemma2:9b
```

4. 如果使用 OpenAI-compatible API，使用者需要复制 `.env.example` 为 `.env`，填写 `OPENAI_API_KEY`，然后在页面 settings 里选择 `openai_compatible` provider 和模型名。

5. 如果下一步做 Docker，建议使用 `docker-compose.yml` 管理：

- backend container：运行 FastAPI，暴露 `8000`
- frontend container 或静态构建：React build 后由 nginx 或后端静态服务托管
- volume：把 `sessions/` 和 `reports/` 挂载出来，避免容器重建后数据丢失
- `.env`：通过 compose 的 env file 或 environment 注入，不写进镜像

6. 当前页面 settings 会写 `app_settings.json`。如果是给别人使用，推荐不要随项目提交这个文件，让每台电脑首次启动时使用默认配置，然后用户在页面里修改 provider、model、路径和 profile。

## 16. 当前限制和后续改进方向

当前限制：

- 没有真正接入外部 CBT-Bench / C2D2 数据集
- 没有向量数据库或 embedding retrieval
- LLM 输出 JSON 解析依赖正则提取第一个 `{...}`，复杂错误输出时可能失败
- `in_progress` session 已经可以从本地 JSON 恢复继续，但恢复逻辑仍然比较轻量，后续可以增加更严格的状态校验和冲突处理
- Personal context 不是自动 memory，不会自动从历史 session 中学习或更新用户画像
- 前端没有自动化测试
- 项目没有完整单元测试或端到端测试

后续可以改进：

- 接入真正的 RAG，例如 embedding + vector database
- 增加 CBT distortion detection evaluation dataset
- 给 `extract_and_fill()` 增加更稳定的 structured output 机制
- 增加用户可控的 profile 总结或 memory 功能，但需要明确展示、编辑和删除机制
- 加入 pytest 测试 Agent 字段抽取、step 流转和 report metrics
- 给前端引入 React Router 和基础组件拆分
- 增加更多 safety case 测试

## 17. 快速命令汇总

安装 Python 依赖：

```bash
uv sync
```

运行 terminal 版本：

```bash
uv run python -m backend.main
```

运行 API 后端：

```bash
uv run uvicorn backend.api_app:app --reload --port 8000
```

安装前端依赖：

```bash
cd frontend
npm install
```

运行前端：

```bash
cd frontend
npm run dev
```

列出 completed sessions：

```bash
uv run python -m backend.report_cli list-sessions
```

生成最近 5 个 session 的报告：

```bash
uv run python -m backend.report_cli generate --mode recent --limit 5
```

生成单 session 报告：

```bash
uv run python -m backend.report_cli generate --mode single --session-id <session_id>
```

访问前端：

```text
http://127.0.0.1:5173/
```

访问报告页：

```text
http://127.0.0.1:5173/reports
```
