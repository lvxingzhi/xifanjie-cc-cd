# 西番芥的秘境工具箱

WoW 大秘境技能速查站（[在线版](https://lvxingzhi.github.io/xifanjie-cc-cd/)）。
从 [MythicDungeonTools](https://github.com/Nnoggie/MythicDungeonTools)（MDT）插件源码自动提取副本怪物技能数据，
GitHub Actions 定时构建并提交 `data.json`，由 GitHub Pages 直接从 main 分支发布。

## 架构

```
MythicDungeonTools (外部上游, GPL-2.0)
        │  git 部分克隆 --filter=blob:none（只下载 ~12 个所需文件，不 clone 全仓）
        ▼
mdt_site/  (Python, 一键构建)
   ├ 读 MythicDungeonTools.toc 确定当前赛季（mainline 游戏类型）
   ├ 解析 load XML + 副本 Lua + 本地化（MDT 换赛季改 TOC，自动跟随）
   ├ Wowhead 增量补全技能描述（zhCN + enUS 中英双语，缓存提交进仓库，平时零请求）
   └ 生成 data.json（仓库根目录，与 index.html/cards.html 同级）
        ▼
commit + push → GitHub Pages 直接服务 main 分支
```

镜像策略：**以 MDT 为准，全量覆盖，不做历史归档、不做变更感知**。
MDT 当前有哪些副本/怪物/技能/翻译，站点就是什么；MDT 删掉的本，站点同步删掉；
MDT 只有站位数据、没有技能的本自动跳过（补上后自动回归）。

技能描述中英双语：Wowhead 同时拉取 zhCN + enUS，页面右上角（工具）可一键切换
中文 / EN 展示（localStorage 记忆），搜索同时命中中英文。

## 当前赛季如何确定

MDT 是 WoW 插件，当前大秘境池由 `MythicDungeonTools.toc` 声明：

```
Midnight\load_midnight.xml [AllowLoadGameType mainline]     ← 正式服大秘境（本工具只跟这个）
MistsOfPandaria\load_mop.xml [AllowLoadGameType mists]      ← MoP Remix 活动（排除）
```

换赛季时 MDT 改 TOC 一行，本工具自动跟随新赛季目录，无需任何配置。

## 本地使用

```bash
pip install -r requirements.txt        # 仅依赖 requests

python -m mdt_site                     # 默认：远程拉取 MDT master 构建
python -m mdt_site --branch ptr12.1    # 拉取指定分支（如 PTR 测试服）
python -m mdt_site --mdt ../MythicDungeonTools   # 本地开发：用本地 MDT clone（用其当前分支）
python -m mdt_site --fetch             # 新赛季：补全未缓存技能描述（Wowhead，zhCN+enUS）
python -m mdt_site --fetch --wowhead-workers 10   # 调整 Wowhead 拉取并发（默认 10）
```

生成 `data.json` 到仓库根目录。本地预览：`python3 -m http.server 8000`（打开 http://localhost:8000）。
页面右上角“中文 / EN”按钮切换技能展示语言（副本、怪物、技能名、描述、标签、表头全部随语言切换）。

## 新赛季流程

1. 本地跑 `python -m mdt_site --branch <新赛季分支> --fetch` 补全 Wowhead 缓存（断点续传可中断重跑）
2. `git commit data/spells_cache.json` 并 push
3. GitHub 上手动触发 workflow（或等每周定时任务）

平时构建全走缓存，零 Wowhead 请求。技能缓存只增不减——老副本回归时直接命中，无需重新请求。

## 数据来源与许可

- 数据提取自 [Nnoggie/MythicDungeonTools](https://github.com/Nnoggie/MythicDungeonTools)（GPL-2.0，仅提取游戏数据，不并入本仓库代码）
- 技能描述来自 Wowhead API
- 本站点仅供 WoW 玩家学习交流
