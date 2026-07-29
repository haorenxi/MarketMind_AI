# LangGraph Agent Starter

一个可扩展的全栈 Agent 骨架，技术栈为 FastAPI、LangGraph 和 Next.js。

当前工作流：`User Input → Research Node → Output`。Research Node 会读取
`skills/company_research/SKILL.md` 的原始内容作为模型提示词，并只返回 Markdown。

## 目录

```text
backend/   # FastAPI 与 LangGraph 工作流
frontend/  # Next.js 用户界面
skills/    # 未来放置 SKILL.md
tools/     # 未来放置 Agent 工具实现
```

## 启动后端

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
# 在 .env 中填入 OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000 --env-file .env
```

接口文档：`http://localhost:8000/docs`

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:3000`。

## Skill Loader

`backend/app/skill_loader.py` 以 `skills/<skill_name>/SKILL.md` 为约定读取
Skill 内容，原文不会被修改或解析。Research Node 当前加载
`company_research`；未来可以通过状态字段或路由节点选择其他 Skill。

## Research Tool

`tools/search/` 提供 `ResearchTool`，输入关键词并返回标准化的
`SearchResult` 列表（标题、链接、摘要、来源）。`graph.py` 将其注册为
`search_web` 工具，并交给 LangGraph 的 `ToolNode` 调用：模型可自行决定是否
搜索；ToolNode 的结果会进入报告上下文。现有 HTTP API 与 Markdown 输出契约不变。
未来可通过注入其他 `SearchProvider`（如 Tavily 或 SerpAPI）替换默认搜索源。

## 使用 OpenAI-compatible 第三方 API

在 `backend/.env` 设置 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 与
`OPENAI_MODEL` 即可。Research Node 会把 `OPENAI_BASE_URL` 传给
`langchain-openai`，因此兼容 OpenAI Chat Completions API 的服务可直接使用。
不要提交 `.env`，也不要在聊天或代码中粘贴真实密钥。
