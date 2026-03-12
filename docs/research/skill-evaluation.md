# 调研辅助 Skill 评估记录

> 评估日期: 2026-03-13
> 任务编号: G-00

## 搜索关键词

共搜索 7 个关键词，覆盖调研工作流各环节：

| # | 关键词 | 结果数 | 有效候选 |
|---|--------|--------|----------|
| 1 | research | 6 | tavily-ai/skills@research, 199-biotechnologies@deep-research, shubhamsaboo@academic-researcher |
| 2 | web | 6 | 无直接相关（均为 web 开发类） |
| 3 | fetch | 6 | 无直接相关（均为特定平台数据抓取） |
| 4 | paper | 6 | karpathy/nanochat@read-arxiv-paper, ailabs-393@research-paper-writer |
| 5 | arxiv | 6 | yorkeccak/scientific-skills@arxiv-search, karpathy/nanochat@read-arxiv-paper, langchain-ai/deepagents@arxiv-search |
| 6 | summary | 6 | 无直接相关（均为新闻/PR 摘要类） |
| 7 | document | 6 | 无直接相关（均为代码文档生成类） |

## 候选 Skill 评估

### 1. karpathy/nanochat@read-arxiv-paper

- **安装量**: 532
- **功能**: 给定 arXiv URL，下载论文 TeX 源码并阅读全文，生成结构化摘要到 `./knowledge/` 目录
- **安全性**: ✅ 通过。纯 prompt 指令（SKILL.md），无可执行脚本。仅指导 Claude 下载 TeX 到 `~/.cache/nanochat/knowledge/` 并读取，无数据外传行为
- **社区信誉**: Andrej Karpathy（前 Tesla AI 总监、OpenAI 创始成员）维护。母仓库 46,774 Stars，活跃更新（最后推送 2026-03-10）
- **依赖**: 无外部依赖，仅使用 Claude Code 内置工具
- **匹配度**: 高 — 直接读取 arXiv 论文全文，非常适合调研阶段精读论文
- **安全扫描**: Gen=Safe, Socket=0 alerts, Snyk=Med Risk
- **结论**: ✅ **已安装**

### 2. 199-biotechnologies/claude-deep-research-skill@deep-research

- **安装量**: 1,900
- **功能**: 8 阶段深度研究流水线（范围定义→搜索→交叉验证→综合分析→批判审查→报告生成），支持 Quick/Standard/Deep/UltraDeep 四种模式
- **安全性**: ✅ 通过。源码审查：仅使用 Python 标准库，无 eval/exec，无子进程调用，无环境变量读取，文件写入限于 `~/Documents/` 和 `~/.claude/research_output/`
- **社区信誉**: 98 Stars，无许可证声明，代码已停更约 4 个月（最后推送 2025-11-05）
- **依赖**: 无外部 API 依赖，使用 Claude 内置 WebSearch/WebFetch
- **匹配度**: 高 — 端到端研究流水线，可直接产出调研报告
- **结论**: ❌ **未安装** — Star 数偏低，代码停更时间较长

### 3. yorkeccak/scientific-skills@arxiv-search

- **安装量**: 400
- **功能**: 通过 Valyu API 对 arXiv 进行语义搜索，返回全文内容和图片链接
- **安全性**: ✅ 通过。Node.js 脚本仅调用 Valyu API（`https://api.valyu.ai/v1`），API Key 存储在 `~/.valyu/config.json`，零外部依赖
- **社区信誉**: 23 Stars，MIT 许可，维护活跃度一般
- **依赖**: 需要 Valyu API Key（免费 $10 额度），Node.js 18+
- **匹配度**: 高 — 语义搜索 arXiv 论文
- **结论**: ❌ **未安装** — 需要注册第三方服务（Valyu）

### 4. tavily-ai/skills@research

- **安装量**: 5,400
- **功能**: 调用 Tavily Research API 进行深度网络搜索，支持 mini/pro/auto 模式
- **安全性**: ✅ 通过。Shell 脚本仅调用 Tavily MCP 端点，OAuth 认证流程安全
- **社区信誉**: Tavily 官方出品，69 Stars，MIT 许可，活跃维护
- **依赖**: 需要 Tavily 账号（免费额度）
- **匹配度**: 中 — 通用网络搜索，Claude Code 内置 WebSearch 已可替代
- **结论**: ❌ **未安装** — 与 Claude Code 内置 WebSearch 功能重叠

### 5. shubhamsaboo/awesome-llm-apps@academic-researcher

- **安装量**: 1,500
- **功能**: 纯 prompt 增强，提供学术研究助手角色（文献综述、论文分析、引用格式化）
- **安全性**: ✅ 通过。纯 SKILL.md 文件，无可执行代码
- **社区信誉**: 母仓库 101,772 Stars（LLM 应用合集，非此 skill 专属），Apache 2.0
- **依赖**: 无
- **匹配度**: 中 — Claude 本身已具备类似学术分析能力，边际收益有限
- **结论**: ❌ **未安装** — 边际收益小，母仓库 Star 数不代表此 skill 质量

## 安装结果汇总

| Skill | 安装状态 | 原因 |
|-------|----------|------|
| karpathy/nanochat@read-arxiv-paper | ✅ 已安装 | 零依赖、安全、功能匹配、作者信誉高 |
| 199-biotechnologies@deep-research | ❌ 未安装 | Star 偏低、停更较久 |
| yorkeccak@arxiv-search | ❌ 未安装 | 需注册第三方服务 |
| tavily-ai@research | ❌ 未安装 | 与内置功能重叠 |
| shubhamsaboo@academic-researcher | ❌ 未安装 | 边际收益有限 |
