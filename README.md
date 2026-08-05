# 西番芥的秘境工具箱

WoW 大秘境技能速查站（[在线版](https://lvxingzhi.github.io/xifanjie-cc-cd/)）。
数据从 [MythicDungeonTools](https://github.com/Nnoggie/MythicDungeonTools)（MDT）插件源码提取，
GitHub Actions 定时构建并提交 `data.json`，GitHub Pages 直接从 main 分支发布。

## 架构

```
MythicDungeonTools (上游, GPL-2.0)
  │  git 部分克隆 --filter=blob:none（只拉 ~12 个所需文件）
  ▼
mdt_site/  (Python)
  ├ 读 MythicDungeonTools.toc 确定当前赛季
  ├ 解析 load XML、副本 Lua、本地化文本
  ├ Wowhead 补全技能描述（zhCN + enUS，只补缓存缺失项，缓存提交进仓库）
  └ 生成 data.json（仓库根目录）
  ▼
commit + push → GitHub Pages
```

以 MDT 为准，全量覆盖：MDT 有什么站点就有什么，MDT 删掉的本站点跟着删，
只有站位数据、没有技能的本直接跳过。不做历史归档，也不做变更记录。

技能描述中英双语，页面右上角可切换中文 / EN（localStorage 记住选择），搜索同时命中中英文。

## 当前赛季如何确定

当前大秘境池由 `MythicDungeonTools.toc` 声明：

```
Midnight\load_midnight.xml [AllowLoadGameType mainline]     ← 正式服大秘境
MistsOfPandaria\load_mop.xml [AllowLoadGameType mists]      ← MoP Remix 活动（排除）
```

MDT 换赛季改 TOC 里的目录，本工具跟着读，不用额外配置。

## 本地使用

```bash
pip install -r requirements.txt        # 仅依赖 requests

python -m mdt_site                     # 默认拉 MDT master 构建
python -m mdt_site --branch ptr12.1    # 拉指定分支（如 PTR 测试服）
python -m mdt_site --mdt ../MythicDungeonTools   # 用本地 MDT clone 构建
python -m mdt_site --fetch             # 新赛季补全未缓存技能描述（Wowhead）
python -m mdt_site --fetch --wowhead-workers 10   # Wowhead 并发数，默认 10
```

生成 `data.json` 到仓库根目录。本地预览：`python3 -m http.server 8000`。
右上角“中文 / EN”按钮切换语言，副本、怪物、技能名、描述、标签、表头一起换。

## 新赛季流程

1. 在 GitHub 手动触发 workflow（或等每周定时任务），branch 输入框填新赛季分支名
2. CI 自动 `--fetch` 补全 Wowhead 缓存并提交

技能缓存只增不减：老副本回归时直接命中缓存，每次构建只补缺失项，缓存完整时不会请求 Wowhead。

## 数据来源与许可

- 数据提取自 [Nnoggie/MythicDungeonTools](https://github.com/Nnoggie/MythicDungeonTools)（GPL-2.0，只提取游戏数据，不并入本仓库代码）
- 技能描述来自 Wowhead API
- 站点仅供 WoW 玩家学习交流
