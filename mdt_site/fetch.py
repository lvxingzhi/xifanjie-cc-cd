"""
MDT 定向拉取模块：只下载解析所需的最小文件集

不 clone 整个仓库（全仓 2521 个文件，实际只用 ~12 个），而是用 git 部分克隆：
  1. git clone --filter=blob:none --no-checkout
     只下载 HEAD 提交与文件树元数据（~几百 KB），不下载任何文件内容
  2. git show HEAD:<path> 按需拉取单个文件的 blob（GitHub 支持 on-demand fetch）

git 协议不走 GitHub API 配额（无 403 限流），CI 与本地一致。
目录结构与 MDT 仓库相同，直接交给 parser 解析。
"""
from __future__ import annotations
import re
import subprocess
import tempfile
from pathlib import Path

from .parser import toc_seasons, toc_interface_targets, seasons_from_tree

REPO_URL = "https://github.com/Nnoggie/MythicDungeonTools.git"


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd)} - {out.stderr.strip()}")
    return out.stdout


def fetch_mdt(branch: str = "master", lang: str = "zhCN") -> tuple[Path, str]:
    """部分克隆 MDT 指定分支并提取所需文件，返回 (可解析目录, HEAD SHA)。"""
    tmp = Path(tempfile.mkdtemp(prefix="mdt-"))
    mdt = tmp / "mdt"

    # 只拉提交+树元数据，不拉任何文件内容
    _run(["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
          "-b", branch, REPO_URL, str(mdt)])
    sha = _run(["git", "-C", str(mdt), "rev-parse", "HEAD"]).strip()

    # 文件树（本地树对象，不触发网络下载）
    files = _run(["git", "-C", str(mdt), "ls-tree", "-r", "--name-only", "HEAD"]).splitlines()
    tree = set(files)

    def read(path: str) -> str:
        """git show 按需拉取单个文件 blob。"""
        return _run(["git", "-C", str(mdt), "show", f"HEAD:{path}"])

    # 1. 读 .toc 确定当前赛季（mainline），只下载 TOC 声明的内容
    toc = read("MythicDungeonTools.toc")
    seasons = toc_seasons(toc)
    if not seasons:
        # MDT 6.2+ 新格式：.toc 不再声明赛季 load XML（旧式 AllowLoadGameType 行已移除），
        # mainline 由整包注释 WOW_INTERFACE_TARGETS 标识，赛季目录 = 顶层含 load_*.xml 的目录
        targets = toc_interface_targets(toc)
        if "mainline" not in targets:
            raise RuntimeError(
                f".toc 未找到 mainline 赛季声明（无旧式 AllowLoadGameType 行，"
                f"WOW_INTERFACE_TARGETS={targets or '缺失'}）")
        seasons = seasons_from_tree(tree)
        if not seasons:
            raise RuntimeError(
                f".toc 声明了 mainline（WOW_INTERFACE_TARGETS={targets}），"
                "但文件树中未找到含 load_*.xml 的赛季目录")

    needed: set[str] = {"MythicDungeonTools.toc"}
    for season, load_xml in seasons:
        load_path = f"{season}/{load_xml}"
        if load_path not in tree:
            print(f"  警告: TOC 声明的 {load_path} 不存在，跳过")
            continue
        needed.add(load_path)
        # load XML 引用的副本 Lua（跳过注释行，注释 = MDT 停用的本）
        for line in read(load_path).splitlines():
            stripped = line.strip()
            if stripped.startswith("<!--"):
                continue
            m = re.search(r"file\s*=\s*'([^']+)'", stripped)
            if not m:
                continue
            lua = f"{season}/{m.group(1)}"
            if lua in tree:
                needed.add(lua)

    # 2. 本地化文件（目标语言 + enUS 回退基础）
    for l in {lang, "enUS"}:
        needed.add(f"Locales/{l}.lua")

    # 3. 写出到 clone 目录（结构即 MDT 仓库结构，可直接解析）
    for path in sorted(needed):
        target = mdt / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(read(path), encoding="utf-8")

    print(f"  已拉取 {len(needed)} 个文件（HEAD @ {sha[:12]}，赛季: {[s for s, _ in seasons]}）")
    return mdt, sha
