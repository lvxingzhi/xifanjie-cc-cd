#!/usr/bin/env python3
"""
mdt_site - WoW 大秘境技能速查站构建器（合并原 MDTSpellExporter + MythicSpellShow）

镜像策略：以 MDT 当前内容为准，全量覆盖重建，不做历史归档、不做变更感知。

用法:
    python -m mdt_site                          # 远程拉取 MDT master 并构建（默认）
    python -m mdt_site --branch ptr12.1         # 拉取指定 MDT 分支（如 PTR 12.1）
    python -m mdt_site --mdt ../MythicDungeonTools   # 用本地 MDT clone（本地开发）
    python -m mdt_site --fetch                  # 全量重拉 Wowhead 技能描述（新赛季/PTR 用，失败回退缓存）
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

from .parser import parse_all, parse_locales, apply_localization
from .wowhead import SpellFetcher
from .builder import build_data, write
from .fetch import fetch_mdt


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 WoW 大秘境技能速查站")
    parser.add_argument("--mdt", type=Path, help="本地 MDT 源码目录（默认远程定向拉取）")
    parser.add_argument("--branch", default="master",
                        help="远程拉取的 MDT 分支（如 ptr12.1，默认 master）")
    parser.add_argument("--lang", default="zhCN", choices=["zhCN", "enUS", "zhTW"],
                        help="本地化语言")
    parser.add_argument("--fetch", action="store_true",
                        help="全量重拉 Wowhead 技能描述（新赛季/PTR 用，失败回退缓存）")
    parser.add_argument("--wowhead-workers", type=int, default=10,
                        help="Wowhead 拉取并发线程数（--fetch 时生效，默认 10）")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data",
                        help="Wowhead 缓存目录")
    return parser.parse_args()


def local_sha(mdt_root: Path) -> str:
    """本地 MDT clone 的 HEAD SHA（仅备注用途，不参与对比）。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(mdt_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip()[:12] if out.returncode == 0 else ""
    except Exception:
        return ""


def main() -> int:
    args = parse_args()

    print("=" * 56)
    print("mdt_site - WoW 大秘境技能速查站构建")
    print("=" * 56)

    # [0] 数据源：本地 clone 或远程定向拉取
    if args.mdt:
        mdt_root = args.mdt
        mdt_sha = local_sha(mdt_root)
        print(f"数据源: 本地 {mdt_root.resolve()} @ {mdt_sha or '?'}")
    else:
        print(f"数据源: 远程定向拉取 Nnoggie/MythicDungeonTools 分支 {args.branch}（仅所需文件）")
        mdt_root, mdt_sha = fetch_mdt(args.branch, args.lang)

    # [1] 解析
    print("\n[1/3] 解析 MDT 副本...")
    dungeons = parse_all(mdt_root)
    if not dungeons:
        print("错误: 未解析到任何副本数据")
        return 1
    print(f"  共 {len(dungeons)} 个副本（赛季: {sorted({d.season for d in dungeons})}）")

    # [2] 本地化
    print("\n[2/3] 应用本地化...")
    locale_map = parse_locales(mdt_root / "Locales", args.lang)
    apply_localization(dungeons, locale_map)

    # [3] 技能数据（Wowhead 中英双语，缓存只增不减）
    print("\n[3/3] 技能数据...")
    all_ids = {sid for d in dungeons for e in d.enemies for sid in e.spells}
    print(f"  涉及 {len(all_ids)} 个技能")
    # Wowhead 固定拉取 zhCN + enUS 双语（与 MDT 本地化 --lang 无关）
    fetcher = SpellFetcher(args.data_dir / "spells_cache.json",
                           no_fetch=not args.fetch, workers=args.wowhead_workers)
    spell_data = fetcher.fetch_all_spells(all_ids)

    # 构建站点数据（data.json 写到仓库根目录，与 index.html/cards.html 同级）
    print("\n构建站点数据...")
    payload = build_data(dungeons, spell_data, mdt_sha)
    write(PROJECT_ROOT / "data.json", payload)

    print(f"\n完成! data.json 已更新（{payload['total']} 条技能记录, {len(payload['dungeons'])} 个副本）")
    if not args.fetch:
        print("提示: 如需补全新技能描述，运行 python -m mdt_site --fetch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
