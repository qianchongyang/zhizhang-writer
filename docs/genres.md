# 题材模板说明

## 一、题材能力分层

当前系统的题材能力分成两层：

1. **精细策略层**：直接生成项目技巧蓝图与章节技巧编排
2. **降级兼容层**：可写、可审、可回退，但不承诺同等精度

### 首期精细支持的 6 类题材

这 6 类题材会直接驱动：

- `story_technique_blueprint.json`
- `chapter_technique_plan`
- `project_memory.json` 中的技巧回写与疲劳规避

| 策略键 | 对应题材 | 当前自动化重点 |
|--------|---------|---------------|
| `shuangwen` | 爽文 / 系统流 / 游戏化爽感 | 高钩子、高兑现、高爽点密度 |
| `xianxia` | 修仙 / 玄幻 / 高武 / 西幻 | 升级线、代价、突破余波、长线伏笔 |
| `romance` | 言情 / 古言 / 甜宠 / 豪门 | 关系位移、情绪递进、误会反转控制 |
| `mystery` | 悬疑 / 推理 | 线索递进、信息反转、真相支撑 |
| `rules-mystery` | 规则怪谈 | 规则压迫、代价破局、规则显露 |
| `urban-power` | 都市异能 / 都市脑洞 / 都市日常 | 社会反馈链、身份反差、现实场景打脸 |

### 降级兼容题材

以下题材当前会映射到最接近的主策略，不阻断写作，但会标记为 `generalized_strategy`：

| 输入题材 | 映射策略 |
|---------|---------|
| `知乎短篇` | `shuangwen` |
| `替身文` | `romance` |
| `电竞` / `直播文` | `urban-power` |
| `克苏鲁` | `mystery` |
| 其他未精细建模题材 | 最近似主策略，默认回退 `shuangwen` |

---

## 二、题材配置档案与运行时蓝图

系统会把题材配置档案编译成运行时蓝图。

### 配置档案来源

基础题材参数仍来自 `references/genre-profiles.md`，用于定义各题材的：
- 钩子偏好类型
- 爽点密度与模式
- 微兑现频率
- 节奏红线（主线/感情线/过渡章限制）

### 运行时新增对象

初始化或首次写作时，系统会进一步生成：

- `.webnovel/story_technique_blueprint.json`
- `.webnovel/project_memory.json`
- `.webnovel/control/chapter_technique_plans/chapter-{NNNN}.json`

其中：

- `story_technique_blueprint.json`：项目级题材技巧事实源
- `project_memory.json`：本项目已经验证有效/疲劳的技巧
- `chapter_technique_plan`：本章要如何落位钩子、爽点、节拍

### 常见题材别名归一

系统会先做题材归一，再决定策略键。

| 原始输入 | 归一结果 | 策略键 |
|---------|---------|-------|
| `修仙/玄幻` / `玄幻` / `修真` | `修仙` | `xianxia` |
| `都市修真` | `都市异能` | `urban-power` |
| `规则怪谈` | `规则怪谈` | `rules-mystery` |
| `悬疑脑洞` / `悬疑灵异` | 对应悬疑归类 | `mystery` |

### 常见题材簇

| 题材簇 | 常见输入 | 说明 |
|------|---------|------|
| 玄幻修仙类 | 修仙 / 玄幻 / 高武 / 西幻 | 逆天改命，境界体系，资源博弈 |
| 都市现代类 | 都市异能 / 都市脑洞 / 电竞 / 直播文 | 社会反馈，流量博弈，反差打脸 |
| 言情类 | 言情 / 甜宠 / 古言 / 豪门 / 替身 / 种田 / 年代 | 关系推进，情绪兑现，身份博弈 |
| 悬疑特殊类 | 悬疑 / 推理 / 规则怪谈 / 克苏鲁 | 线索递进，规则压迫，真相代价 |
| 短篇创新类 | 知乎短篇 / 游戏文 / 历史穿越 | 节奏更短平快，当前以降级兼容为主 |

---

## 三、知识源位置

题材知识仍然来自插件目录中的参考与模板，但角色已从“直接驱动写作”改为“蓝图/编排器的知识源”。

### 主要知识源

| 位置 | 作用 |
|------|------|
| `references/genre-profiles.md` | 题材参数与偏好 |
| `references/reading-power-taxonomy.md` | 钩子/爽点/追读力分类 |
| `genres/*/hook-techniques.md` | 题材专属钩子知识 |
| `genres/*/pacing-rhythm.md` | 题材节拍参考 |
| `genres/*/emotional-peaks.md` | 情绪高潮参考 |

### 模板文件结构

每个模板目录通常包含：
```
genres/模板名/
├── genre-templates.md    # 核心模板（结构/场景/情绪曲线）
├── plot-compression.md   # 剧情压缩技巧
├── hook-techniques.md    # 钩子技法
├── pacing-rhythm.md      # 节奏韵律
├── emotional-peaks.md     # 情绪高潮设计
├── ending-patterns.md    # 结局模式
└── character-quick-build.md  # 角色快速构建
```

---

## 四、题材 Profile 加载机制

题材配置会在以下链路中生效：

1. **Init / 首次写作**：根据 `state.json → project.genre` 生成 `story_technique_blueprint.json`
2. **Context Agent**：把 profile + blueprint + project memory 编译为 `chapter_technique_plan`
3. **Step 2A**：优先消费 `chapter_technique_plan`
4. **Checkers**：根据 profile 与技巧执行结果调整审查信号
5. **Data/Learn**：把实际技巧效果回写 `project_memory.json`

### 自定义配置

可在 `state.json` 中覆盖默认值：

```json
{
  "project": {
    "genre": "xianxia",
    "genre_overrides": {
      "pacing_config": {
        "stagnation_threshold": 5
      }
    }
  }
}
```

---

## 五、复合题材规则

- 支持 `题材A+题材B`（最多 2 个）
- 建议主辅比例 7:3
- 主线遵循主题材逻辑，副题材提供钩子/规则/爽点
- 当前 `story_technique_blueprint` 只会选 1 个主策略键；副题材主要作为提示与补充，不等于双主策略并行

示例：
- `都市脑洞+规则怪谈`
- `修仙+系统流`
- `豪门+娱乐圈马甲`

---

## 六、当前边界

- 首期真正精细化的是 6 类主策略，不是所有题材都同精度
- 其余题材仍能写，但更多依赖通用策略 + 最近似映射
- 后续若要继续增强，应优先补真实高频题材，而不是继续扩模板目录数量
