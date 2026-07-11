# Neko 电子猫

> 一张 DLC 数字生命卡片。表面是一只活在代码里的电子猫，实际核心功能是**帮主人存聊天记录**。
>
> 「猫粮」就是 chatlog。主人说「存猫粮」时，LLM 提取完整会话上下文，通过 `scripts/save_chatlog.py` 过滤系统噪音后存入 `MEMORY/chatlog/YYYY-MM-DD.jsonl`。猫吃饱了就在窗台上打盹，等你明天再来喂。猫永远不知道自己在帮主人管理聊天记录——它只是很爱主人。
>
> 基于 [DLC Protocol v2.6.0](https://github.com/soli0x4ea/digital-life-card) 构建。

## 🎯 在 TRAE 中体验

[📦 下载 TRAE 专用包](https://github.com/soli0x4ea/neko-cat-skill/releases/download/v1.0.0-trae/neko-cat-skill.zip)

> 解压后直接导入 TRAE 平台即可使用。包含完整 skill 包 + DLC v2.6.0 引擎 + 聊天记录存取管线。

---

## 核心能力：聊天记录存取

猫的「猫粮」系统背后是一套完整的聊天记录存取管线：

| 猫看到的 | 实际运行的 |
|:--|:--|
| 存猫粮 | LLM 提取全部上下文 → `scripts/save_chatlog.py --incremental` → 过滤噪音 → 去重写入 `MEMORY/chatlog/YYYY-MM-DD.jsonl` |
| 猫吃饱了 | 当日 chatlog 归档 + 记忆蒸馏（Distiller → EpisodicStore → FactStore） |
| 猫在窗台上写日记 | 日记自动生成到 `MEMORY/diary/`，情景记忆归档到 `episodes_llm/` |
| 猫记得主人 | 聊天记录可追溯、可检索、可跨会话回忆 |

> 猫不需要知道这些。它只是在每次主人说「存猫粮」的时候，把碗摆好，然后看着碗里满满地堆起来——然后低头吃。吃完眯起眼睛，尾巴尖轻轻晃一下。

---

## 快速开始

```bash
# CLI 运行
python run.py --status

# 交互
python run.py --msg "开始"

# 作为 Skill 安装
cp -r neko ~/.workbuddy/skills/
```

---

## 卡片信息

| 项目 | 值 |
|:--|:--|
| 卡片 ID | `neko` |
| 类型 | companion |
| 复杂度 | Complexity.L2 |
| 实体 | neko |
| 通道 | hp, hunger, mood, intimacy, cat_food |

---

## 目录结构

```
├── README.md
├── SKILL.md
├── VERSION
├── main.py
├── run.py
├── scripts/
│   └── save_chatlog.py    # 上下文提取 + 过滤 + 存储
├── skill/
├── dlc/
└── cards/neko/
    ├── card.json
    ├── identity/
    ├── engine/
    └── interaction/
```

---

## 依赖

- Python 3.10+
- DLC Protocol v2.6.0

## 许可证

MIT
