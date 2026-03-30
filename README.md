# 织章 Zhizhang Writer

[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-purple.svg)](https://claude.ai/claude-code)
[![Version](https://img.shields.io/badge/version-v5.25.1-blue.svg)](https://github.com/qianchongyang/zhizhang-writer)

> **长篇网文连载辅助系统**：自动追踪设定/状态/伏笔，六维审查防冲突，动态大纲随写随调，200 万字不乱。

---

## 10 秒体验

```bash
# 1. 安装（一行命令）
claude plugin marketplace add qianchongyang/zhizhang-writer --scope user

# 2. 初始化项目
/zhizhang-init

# 3. 开始写作（自动走完所有流程）
/zhizhang-write 1
```

写完第 1 章，系统自动完成：上下文构建 → 起草 → 六维审查 → 润色 → 数据落盘 → **动态大纲评估**（自动判断后续窗口是否需要调整）。

---

## 动态大纲是什么？

**传统方式**：写完第 45 章 → 手动翻大纲 → 发现要插副本 → 手动改总纲 → 重新编号 → 花 2 小时

**织章方式**：写完第 45 章 → Step 5.5A 自动评估 → "第 46-48 章需要关系铺垫" → Step 5.5B 自动扩展窗口 → 写第 46 章时上下文自动带上铺垫内容

**保证不偏**：
- 锚点保护机制，确保副本永远服务主线
- 扩窗有 1.5 倍硬上限，不会无限膨胀
- 调纲失败阻断 Git 提交，不留脏数据

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **防幻觉三定律** | 大纲即法律 / 设定即物理 / 发明需入库 |
| **双 Agent** | Context Agent 构建上下文，Data Agent 提取状态 |
| **六维并行审查** | 爽点、一致性、节奏、人设、连贯性、追读力 |
| **动态大纲** | 写完即评估、影响预览、原子性写回、失败阻断 |
| **记忆召回** | state.json / index.db / vectors.db / story_memory.json |
| **Dashboard** | 只读可视化面板，写前排查上下文 |
| **经营化** | 读者反馈、追读力分析、连载节奏模板 |

---

## 适用场景

| 场景 | 用什么命令 |
|------|-----------|
| 写一章小说 | `/zhizhang-write 45` |
| 生成卷+章大纲 | `/zhizhang-plan 1` |
| 审查已写章节 | `/zhizhang-review 1-10` |
| 查角色/伏笔状态 | `/zhizhang-query 萧炎` |
| 写一半中断了 | `/zhizhang-resume` |
| 手动调大纲 | `/zhizhang-adjust`（调试用） |
| 看菜单 | `/zhizhang-menu` |

---

## 写作流程（Step 0 → Step 6）

```
Step 0: 预检（环境/Git/断点）
Step 1: Context Agent（加载上下文 + 生成任务书）
Step 2A: 起草（~2000字正文）
Step 2B: 风格适配（消除模板腔）
Step 3: 六维审查（核心3并行 + 条件3按需）
Step 4: 润色 + Anti-AI 检测
Step 5: Data Agent（实体提取 + 状态落盘）
Step 5.5A: 动态大纲评估 ← 新增（v5.25）
Step 5.5B: 动态大纲执行 ← 新增（v5.25）
Step 6: Git 备份
```

**速度模式**：

| 模式 | 命令 | 耗时 | 适用 |
|------|------|------|------|
| 标准 | `/zhizhang-write 45` | ~30分钟 | 重要章节 |
| `--fast` | `/zhizhang-write 45 --fast` | ~20分钟 | 日常更新 |
| `--turbo` | `/zhizhang-write 45 --turbo` | ~15分钟 | 赶进度日更 |

---

## 安装

**前提**：已安装 [Claude Code](https://claude.ai/claude-code)

```bash
# 一键安装
claude plugin marketplace add qianchongyang/zhizhang-writer --scope user
claude plugin install zhizhang-writer@zhizhang-marketplace --scope user

# 验证安装
/zhizhang-menu
```

**进阶**：

```bash
# 更新插件
claude plugin update zhizhang-writer@zhizhang-marketplace --scope user

# 仅当前项目生效（不加 --scope user）
```

详细说明见 [安装文档](docs/commands.md)。

---

## 快速导航

- [命令详解](docs/commands.md) — 所有命令的场景化说明
- [动态大纲手册](docs/dynamic-outline-guide.md) — 动态大纲原理与配置
- [架构文档](docs/architecture.md) — 系统模块设计
- [运维手册](docs/operations.md) — 索引重建、数据迁移、故障恢复
- [新手/贡献指南](docs/open-source-guide.md)

---

## 数据文件

```
PROJECT_ROOT/
├── .webnovel/
│   ├── state.json              # 运行时真相（角色/关系/势力/伏笔）
│   ├── index.db                # SQLite 实体索引
│   ├── vectors.db              # RAG 向量检索
│   ├── outline_runtime.json     # 动态大纲运行层（v5.25）
│   ├── outline_adjustments.jsonl  # 调纲审计记录（v5.25）
│   └── project_config.json     # 项目配置（可覆盖 default_window_size）
├── 设定集/                      # 世界观/角色卡/力量体系
├── 大纲/                       # 总纲/卷纲/章节大纲
└── 正文/                       # 章节正文
```

---

## 最近更新

| 版本 | 说明 |
|------|------|
| **v5.25.1** | 动态大纲 Bug 修复：模块调用路径 + CLI 测试 fixture + 上下文契约版本 |
| **v5.25.0** | 动态大纲正式上线：Step 5.5A/5.5B 内嵌到写作主流程，窗口自动评估/扩展/阻断，完整原子性保证 |
| **v5.24.0** | 读者反馈 + 追读力经营模块 |
| **v5.23.0** | 健康检查 + 一致性修复 |

完整日志见 [CHANGELOG](docs/CHANGELOG.md)。

---

## 适合谁

- 长篇连载作者（50 章以上）
- 需要管理大量设定、人物关系、伏笔的复杂世界观的作者
- 想在 Claude Code 上搭建自动化写作流水线的开发者
- 想用 AI 辅助写作但担心"AI 味"和"前后矛盾"的作者

**不适合**：短篇（10 章以内）、纯大纲创作、不需要自动审查的写作流程。

---

## 命令一览

| 命令 | 用途 |
|------|------|
| `/zhizhang-init` | 初始化项目 |
| `/zhizhang-plan [卷号]` | 生成卷/章大纲 |
| `/zhizhang-write 章号` | 写一章（核心命令） |
| `/zhizhang-review 范围` | 审查章节质量 |
| `/zhizhang-query 关键词` | 查询角色/伏笔/状态 |
| `/zhizhang-resume` | 恢复中断任务 |
| `/zhizhang-dashboard` | 可视化面板 |
| `/zhizhang-menu` | 文字菜单入口 |
| `/zhizhang-learn` | 提取写作模式 |

---

## 开源协议

GPL v3 © qianchongyang

基于 [lingfengQAQ/webnovel-writer](https://github.com/lingfengQAQ/webnovel-writer) fork，保留 GPL-3.0 开源协议。

---

## 参与贡献

- [贡献指南](CONTRIBUTING.md)
- [安全披露](SECURITY.md)
- [提交规范](docs/commit-rules.md)
