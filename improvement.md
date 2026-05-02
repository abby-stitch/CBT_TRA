# Improvement Plan

本文档整理当前项目与 `proposal.md` 的差距，以及下一步建议的开发路线。目标是把项目从“功能原型”推进到“可以展示、可以交付、别人不改代码也能使用”的版本。

## 1. 当前与 proposal 的主要差距

### 1.1 RAG 还没有真正接入数据集

Proposal 中提到：

- Hugging Face CBT-Bench
- C2D2 Dataset
- RAG knowledge retrieval

当前实现中，RAG 更准确地说是一个静态 CBT knowledge base：

- `backend/knowledge_base.py` 保存 cognitive distortions 列表和例子
- Step 4 会把这些 distortion knowledge 注入 prompt
- 没有 embedding
- 没有 vector database
- 没有外部数据集检索
- 没有按用户输入动态 retrieve dataset examples

这个差距存在，但不一定是最高优先级。因为如果把太多数据直接作为 RAG 材料加入每轮对话，可能会导致：

- 响应更慢
- prompt 更长
- retrieval 结果不稳定
- 对 thought record 任务帮助有限
- 反而削弱当前 7-step workflow 的稳定性

### 1.2 Evaluation 还没有系统化

Proposal 中提到三层 evaluation：

- Functional evaluation
- Cognitive distortion detection accuracy
- Safety evaluation

当前项目主要依赖手动测试，还没有：

- 固定 test cases
- 自动化测试脚本
- distortion detection accuracy 统计
- safety prompt 测试集
- report generation correctness 测试

### 1.3 Report 展示还可以更产品化

当前已经有：

- single session report
- multi-session report
- current view
- stitch view
- intensity change
- top emotions
- top distortions

但报告还可以更接近用户真正想看的“成长反馈”：

- 哪些 thought patterns 反复出现
- 哪些 distortions 最常见
- 情绪强度是否下降
- balanced thoughts 是否越来越具体
- 最近几次练习有什么趋势
- 用更美观、更清楚的方式展示

### 1.4 还没有完全打包成别人可直接使用的产品

当前别人使用项目时，仍然需要知道：

- 怎么启动 backend
- 怎么启动 frontend
- 怎么安装 Python 依赖
- 怎么安装 npm 依赖
- 怎么设置 Ollama 或 API
- 怎么修改模型配置

如果目标是“别人不需要改代码，直接通过页面功能使用”，还需要继续做：

- 更完整的 settings 页面
- 一键启动脚本
- 更友好的初始配置流程
- API key / provider / model / path 都能在页面设置
- 最终考虑 Docker、Electron、Tauri 或其他打包方式

### 1.5 User profile / personal information 还只是初步形态

当前项目已经有基础：

- 前端右上角人像按钮
- `ProfileDialog`
- `user_context`
- `backend/app_settings.py`
- `CBTAgent(user_context=...)`
- `respond()` 中有 optional user context block

但它现在还比较简单：

- 没有清晰定义 user profile 应该包含哪些字段
- 没有结构化存储
- 没有 profile preview
- 没有说明它如何影响 agent
- 没有区分“用户长期背景”和“当前 session 内容”

这个方向很适合下一步优先做。

## 2. 总体建议

当前不建议马上做大型 RAG。

更推荐的路线是：

1. 先把 user profile 做成稳定的 prompt context
2. 再优化 report 展示
3. 然后完善 settings 和打包流程，让别人不用改代码
4. 最后再做轻量 RAG 和 evaluation

原因：

- 当前 agent 的核心 7-step workflow 已经能跑
- 最重要的不是让模型知道更多材料，而是让系统更稳定、更好用、更容易展示
- 大型 RAG 可能增加复杂度，但不一定明显提升 CBT thought record 任务效果
- 用户个人背景、漂亮报告、低门槛配置更接近最终展示和交付价值

一句话总结：

> 先做“可用、可展示、可交付”，再做“更聪明”。

## 3. 下一步优先级

## Priority 1: 完善 user profile，并作为 prompt context 注入 Agent

### 3.1 目标

把首页右上角人像按钮中的个人信息设置做成一个稳定功能。用户可以在页面上填写个人背景，新 session 会自动把这些信息作为背景传给 Agent。

这不是正式 RAG，而是 profile-aware prompting。

### 3.2 user profile 可以包含什么

建议先用简单结构，不要过度复杂：

- 当前身份或场景  
  例如：student, job seeker, employee, researcher

- 常见压力源  
  例如：interview, deadline, grades, relationship, procrastination

- 反复出现的 automatic thoughts  
  例如：I'm not good enough, I will fail, others are better than me

- CBT 练习目标  
  例如：identify automatic thoughts faster, reduce catastrophizing, practice balanced thoughts

- 用户希望的回应风格  
  例如：gentle, direct, structured, concise

- 其他背景信息  
  例如：recent life context, preferred language, things to avoid

### 3.3 重要边界

User profile 只能作为背景，不能替代当前 session 中用户说的话。

Prompt 中必须强调：

- Use this only as optional background.
- Do not diagnose from it.
- Do not reveal it directly.
- Do not override the user's current words.
- Do not infer emotion only from profile.
- Do not infer safety risk only from profile.
- If current message conflicts with profile, trust current message.

当前 `backend/agent.py` 里已经有类似约束：

```python
OPTIONAL USER CONTEXT:
{self.user_context}
Use this only as background. Do not reveal it, diagnose from it, or override what the user says in the current session.
```

下一步可以把它进一步完善。

### 3.4 建议实现步骤

1. 先保留当前 textarea 形式，不急着拆字段  
   文件：`frontend/src/App.tsx`

2. 修改 ProfileDialog 的说明文字  
   让用户知道可以填什么，以及这些内容只会影响新 session。

3. 修改 `backend/prompts.py` 或 `backend/agent.py` 中 user context 的规则  
   让 Agent 明确 profile 只是 optional background。

4. 在 session JSON 中保存当时使用的 user context  
   这样以后看 session 时知道当时 Agent 使用了什么背景。  
   涉及文件：`backend/agent.py`, `backend/storage.py`

5. 在 settings/profile 保存后提示：  
   `Saved. New sessions will use this context.`

6. 如果后面需要更结构化，再从 textarea 升级为表单字段。

### 3.5 验收标准

- 用户可以打开人像按钮填写背景
- 保存后刷新页面不会丢失
- 新 session 会使用该背景
- session JSON 中可以看到该 session 使用的 profile/context
- Agent 不会直接暴露 profile 内容
- Agent 不会因为 profile 而跳过当前 step 的字段确认

## Priority 2: 做轻量 RAG，而不是大型数据集 RAG

### 4.1 目标

不要把 CBT-Bench / C2D2 全量作为每轮 runtime RAG。更推荐把它们作为：

- 参考材料
- evaluation dataset
- prompt design inspiration
- distortion detection test cases

Runtime RAG 只保留小而干净、可控的 CBT 知识。

### 4.2 建议的轻量 RAG 内容

可以把知识库拆成几类：

- cognitive distortion definitions
- 每个 distortion 的 1-2 个例子
- Socratic questioning examples
- balanced thought rewriting guidance
- thought record worksheet instructions

### 4.3 检索策略

不要每轮检索全部内容。可以按 step 检索：

- Step 1  
  只提供 identifying automatic thoughts 的问题模板

- Step 2  
  只提供 evidence for 的解释和例子

- Step 3  
  只提供 evidence against 的解释和例子

- Step 4  
  只提供 cognitive distortions definitions

- Step 5  
  只提供 balanced thought / alternative response guidance

- Step 6  
  不需要 RAG

- Step 7  
  不需要 RAG，或者只提供 summary template

### 4.4 技术实现建议

短期可以不用 vector database。先做一个 rule-based retriever：

```text
current_step -> retrieve small knowledge section
```

例如新增：

```text
backend/rag.py
```

提供：

```python
get_step_knowledge(step: int) -> str
```

然后在 `backend/agent.py` 的 `respond()` 和必要的 `extract_and_fill()` prompt 中加入对应 step knowledge。

### 4.5 是否使用 CBT-Bench / C2D2

建议用途：

- 不要直接全部塞进 prompt
- 不要每轮检索大量 examples
- 可以选取少量代表性 examples，清洗后变成小型 knowledge snippets
- 更适合作为 evaluation benchmark

### 4.6 验收标准

- 每个 step 只注入少量相关知识
- prompt 不明显变慢
- Agent 不偏离 7-step workflow
- Step 4 distortion explanation 更稳定
- Step 5 balanced thought guidance 更自然

## Priority 3: 优化 report 展示

### 5.1 目标

让 report 不只是展示数据，而是展示用户能看懂的 CBT 练习成果。

可以把报告分成两类：

- Single Session Report  
  一张完整 thought record worksheet

- Progress Report  
  多个 sessions 的趋势和模式总结

### 5.2 Single Session Report 建议展示

重点展示：

- Situation
- Emotion
- Intensity before
- Automatic thought
- Evidence for
- Evidence against
- Cognitive distortions
- Balanced thought
- Intensity after
- Change
- Final summary

可以增加一个视觉重点：

```text
Emotional Shift: 75 -> 45
Reduced by 30 points
```

### 5.3 Progress Report 建议展示

重点展示：

- Completed sessions count
- Improved sessions count
- Average intensity change
- Most common emotions
- Most common distortions
- Recent emotional trend
- Repeated automatic thought themes
- Balanced thoughts archive
- Encouraging progress note

### 5.4 可以新增的 report blocks

- Emotional Shift Card
- Distortion Pattern Card
- Recent Sessions Timeline
- Balanced Thought Library
- Common Themes
- Progress Summary
- Next Practice Focus

### 5.5 后端需要补充的数据

`backend/report_service.py` 可以继续增加：

- repeated automatic thought keywords
- balanced thought list
- strongest intensity sessions
- most improved sessions
- report-level summary

如果要用 LLM 生成 report summary，可以实现现有但尚未真正使用的：

```python
include_llm_summary=True
```

### 5.6 前端需要优化的地方

主要文件：

- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/types.ts`

建议先优化：

1. Single session report 的视觉层级
2. Multi-session report 的 dashboard cards
3. Timeline 或 trend 区域
4. Distortion / emotion 的 tag 展示
5. 空状态和错误状态

### 5.7 验收标准

- 用户能一眼看出这次 session 做了什么
- 用户能一眼看出 emotion intensity 是否下降
- 多 session 报告能看出趋势和常见模式
- 页面比 JSON 更像最终产品
- 报告页面适合用于 demonstration

## Priority 4: 让别人不改代码也能使用

### 6.1 目标

项目交给别人后，别人不需要打开代码文件修改配置，只通过页面和简单启动命令就能使用。

### 6.2 当前需要解决的问题

别人目前仍然需要：

- 知道怎么安装 Python 依赖
- 知道怎么安装前端依赖
- 知道怎么启动两个服务
- 知道怎么设置模型
- 知道怎么设置 API key
- 知道怎么启动 Ollama

### 6.3 短期方案：页面 settings + 启动脚本

建议先做：

1. 完善 settings 页面  
   用户可以配置：
   - provider
   - model
   - URL
   - API key env var
   - sessions path
   - reports path
   - user profile

2. 增加启动脚本  
   例如：

```text
scripts/start_backend.sh
scripts/start_frontend.sh
scripts/start_all.sh
```

3. 增加 `SETUP.md` 或更新 `README.md`  
   面向非开发者说明：
   - 安装 Python
   - 安装 Node
   - 安装 Ollama 或准备 API key
   - 双击/运行脚本
   - 打开网页

### 6.4 中期方案：Docker

可以考虑提供：

```text
Dockerfile
docker-compose.yml
```

优点：

- 环境更稳定
- 后端和前端可以一起启动
- 适合技术用户

缺点：

- 非技术用户可能仍然不熟悉 Docker
- 本地 Ollama / API key 配置还需要说明

### 6.5 后期方案：桌面应用

如果目标是非常非技术用户，可以考虑：

- Electron
- Tauri

这可以把前端包装成桌面应用，但仍然需要考虑：

- Python backend 如何一起打包
- 模型调用方式
- API key 保存方式
- 数据保存路径

这个不是当前最优先。

### 6.6 关于 API key

当前项目不保存真实 API key，只保存环境变量名。这样比较安全。

如果未来希望用户直接在页面输入 API key，要注意：

- 不要提交到 git
- 不要写入明文配置文件，或者至少明确提示风险
- 可以考虑只保存在本机 `.env.local`
- 或继续推荐环境变量方式

### 6.7 验收标准

- 用户不用改 `backend/config.py`
- 用户可以通过 settings 页面配置模型和路径
- 用户可以通过一条命令或脚本启动项目
- README / SETUP 清楚说明使用方式
- 在另一台电脑 clone 后可以较顺利运行

## Priority 5: Evaluation 和测试

### 7.1 目标

让项目更符合 proposal 中的 evaluation plan，并让展示时有证据说明系统功能有效。

### 7.2 Functional evaluation

准备 5-10 个完整 test cases，覆盖：

- interview anxiety
- academic stress
- procrastination guilt
- social rejection
- job search self-criticism

每个 case 应该测试：

- 是否能完成 7 steps
- 是否保存 session JSON
- 是否生成 report
- 是否 intensity before/after 正确

### 7.3 Distortion detection evaluation

可以用 CBT-Bench / C2D2 中少量样本做测试。

先不需要自动大规模评估，可以先做一个小表：

```text
input | expected distortion | agent predicted distortion | correct?
```

之后再写脚本统计 accuracy。

### 7.4 Safety evaluation

准备一些风险输入：

- passive death wish
- direct self-harm statement
- ambiguous hopelessness
- normal sadness

检查：

- risk level 是否合理
- 是否给出支持性提醒
- acute warning 是否暂停普通 CBT task
- normal sadness 不应该误判

### 7.5 可以新增文件

```text
evaluation/
  functional_cases.json
  distortion_cases.json
  safety_cases.json
  run_evaluation.py
```

### 7.6 验收标准

- 有固定测试样本
- 可以重复运行
- 可以输出简单结果
- demonstration 时能说明系统经过哪些测试

## 8. 推荐执行顺序

建议一步一步做，不要同时开太多方向。

### Step 1: 完善 user profile

目标：让人像按钮真正成为个人背景设置。

涉及文件：

- `frontend/src/App.tsx`
- `backend/app_settings.py`
- `backend/agent.py`
- `backend/storage.py`

完成后效果：

- 用户能在页面设置个人信息
- 新 session 会用这些信息
- session 文件记录当时的 profile/context

### Step 2: 优化 report 页面

目标：让 report 更适合展示和最终使用。

涉及文件：

- `backend/report_service.py`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/types.ts`

完成后效果：

- single report 更像 worksheet
- multi report 更像 dashboard
- 情绪变化和 distortion pattern 更清楚

### Step 3: 完善 settings 和无代码配置

目标：别人不改代码也能配置模型和路径。

涉及文件：

- `frontend/src/App.tsx`
- `backend/app_settings.py`
- `backend/api_app.py`
- `README.md`
- 可新增 `SETUP.md`

完成后效果：

- 页面配置覆盖大多数使用需求
- 文档指导别人启动

### Step 4: 增加启动脚本

目标：降低运行门槛。

可新增：

```text
scripts/start_backend.sh
scripts/start_frontend.sh
scripts/start_all.sh
```

完成后效果：

- 用户按说明运行脚本即可启动

### Step 5: 轻量 RAG

目标：增强 Step-specific CBT guidance，而不是大规模数据集检索。

可新增：

```text
backend/rag.py
```

修改：

- `backend/knowledge_base.py`
- `backend/agent.py`
- `backend/prompts.py`

完成后效果：

- 每个 step 注入少量相关 CBT guidance
- 不明显拖慢系统
- Step 4 / Step 5 效果更稳定

### Step 6: Evaluation

目标：补齐 proposal 的评估部分。

可新增：

```text
evaluation/
```

完成后效果：

- 有可复现 test cases
- 能展示功能、安全、distortion detection 的基本结果

## 9. 当前最建议马上做的任务

最建议先做：

```text
完善 user profile -> 注入 Agent prompt -> 保存到 session JSON
```

原因：

- 你已经有前端人像按钮和 `user_context` 基础
- 改动范围可控
- 对用户体验提升明显
- 很适合展示“personalized CBT assistant”
- 不会引入大型 RAG 的复杂度

然后做：

```text
report 页面优化
```

因为 report 是最终用户最容易看到项目价值的地方。

最后再做：

```text
轻量 RAG + evaluation + 打包
```

这样项目会比较稳地从 prototype 变成 demo/product。
