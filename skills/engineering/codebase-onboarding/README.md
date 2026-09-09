# Codebase Onboarding Skill

> 第三方 Skill 收录，用于把一个代码仓库讲透、生成 DeepWiki 风格 onboarding 文档，并进一步用于 AI 项目交接。

## Source

- Upstream: https://github.com/eabait/codebase-onboarding-skill
- License: MIT

## Why I saved this

适合在 AI 项目交接前，让 Agent 对整个 repo 做系统理解，而不是只生成浅层摘要。

它会生成：

- 项目整体定位与 TL;DR
- High-level Architecture
- Mermaid 架构图 / 时序图
- 核心模块与关键概念
- Request / Data Flow
- 关键入口文件
- 源码级引用（file + line）
- `[NEEDS INVESTIGATION]` 未验证项
- 完整 `wiki/` 文档目录

## Install

```bash
# 安装到所有 Agent
npx skills add eabait/codebase-onboarding-skill --all

# 仅安装到 Claude Code
npx skills add eabait/codebase-onboarding-skill -a claude-code
```

## Basic invocation

在目标项目目录中让 Agent 执行：

> Onboard me to this codebase.

## Recommended prompt for AI project handoff

> Use the codebase-onboarding skill to deeply understand this entire AI project and generate a handoff-oriented wiki. Do not stop at a code summary. Explain the project goal, architecture, data flow, key modules, entry points, business rules, semantic mappings, important design decisions, current limitations, validation mechanisms, known pitfalls, unresolved questions, and recommended reading order for the next owner. Link conclusions back to real source files whenever possible. Then add a final handoff page containing: Current State, Completed / In Progress / Blocked, Key Decisions & Constraints, Pitfalls & Learnings, Open Questions, and concrete Next Steps.

## Jon's use case

优先用于现有 AI 项目交接，例如：

- Excel → Parquet / Data Agent
- 费用审批 Skill
- 底稿逆向与语义层
- 财经数据工程 / Agent 流程

目标不是“展示代码”，而是把项目从代码资产转成 **可理解、可交接、可继续开发的知识资产**。
