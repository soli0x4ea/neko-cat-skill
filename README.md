# Neko 电子猫

> 一张 DLC 数字生命卡片。一只活在代码里的猫。吃猫粮、晒太阳、偶尔踩奶。世界很小——主人、猫粮、摸摸、窗台，这样就够了。

基于 [DLC Protocol v2.6.0](https://github.com/soli0x4ea/digital-life-card) 构建。

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
