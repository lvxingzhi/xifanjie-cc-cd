"""
MDT 数据解析模块（合并原 dungeon_loader / lua_parser / locale_parser）

当前赛季由 MythicDungeonTools.toc（mainline 游戏类型）决定，
解析其 load XML 声明的副本 Lua 与本地化文件。镜像策略：MDT 有什么就解析什么。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SpellAttr:
    """技能属性。已知属性走显式字段，未知属性自动捕获进 extra。"""
    interruptible: bool = False
    magic: bool = False
    enrage: bool = False
    bleed: bool = False
    poison: bool = False
    disease: bool = False
    curse: bool = False
    extra: dict[str, bool] = field(default_factory=dict)

    KNOWN_ATTRS = frozenset({
        "interruptible", "magic", "enrage", "bleed", "poison", "disease", "curse",
    })

    def set_attr(self, name: str, value: bool) -> None:
        if name in self.KNOWN_ATTRS:
            setattr(self, name, value)
        else:
            self.extra[name] = value


@dataclass
class Enemy:
    """怪物。"""
    name: str = ""                # 英文名（MDT Lua 内名）
    name_cn: str = ""             # 本地化中文名
    npc_id: int = 0
    creature_type: str = ""
    characteristics: list[str] = field(default_factory=list)
    spells: dict[int, SpellAttr] = field(default_factory=dict)
    is_boss: bool = False


@dataclass
class DungeonData:
    """副本。season 标记来源赛季目录。"""
    season: str = ""
    english_name: str = ""
    name_key: str = ""
    name_cn: str = ""
    short_name_key: str = ""
    short_name_cn: str = ""
    enemies: list[Enemy] = field(default_factory=list)


# ---------------------------------------------------------------------------
# .toc 赛季发现：MDT 是 WoW 插件，当前赛季由 MythicDungeonTools.toc 决定
# ---------------------------------------------------------------------------

# TOC 里声明的赛季 load XML：目录名 + 文件名 + 游戏类型（如 mainline/mists）
_TOC_LOAD_XML = re.compile(
    r'([A-Za-z0-9]+)\\load_([a-z0-9_]+)\.xml\s*\[AllowLoadGameType\s+([\w\-]+)\]'
)

# 无 TOC 时的兜底：含 load_*.xml 但非赛季目录
_IGNORE_DIRS = {"AceGUIWidgets", "Core", "Developer", "libs", "Modules", "Textures", "scripts"}


def toc_seasons(toc_content: str) -> list[tuple[str, str]]:
    """从 .toc 文本提取 mainline（正式服大秘境）赛季配置：[(赛季目录, load_xml文件名)]。

    换赛季 = MDT 改 TOC 一行（如 Midnight\load_midnight.xml → 新赛季\load_xxx.xml）；
    mists 等非 mainline 游戏类型（如 MoP Remix 活动）不属于大秘境池，排除。
    文件名必须取 TOC 原名（如 MistsOfPandaria 的 load_mop.xml），不能靠赛季名推导。
    """
    return [(m.group(1), f"load_{m.group(2)}.xml")
            for m in _TOC_LOAD_XML.finditer(toc_content)
            if "mainline" in m.group(3)]


def find_seasons(mdt_root: Path) -> list[tuple[str, str]]:
    """确定当前赛季配置：优先读 .toc，找不到时兜底扫描所有 load XML。"""
    toc = mdt_root / "MythicDungeonTools.toc"
    if toc.exists():
        try:
            seasons = toc_seasons(toc.read_text(encoding="utf-8"))
            if seasons:
                return seasons
        except Exception:
            pass
    # 兜底：扫描所有含 load_*.xml 的顶层目录（跳过非赛季目录）
    return sorted(
        (p.parent.name, p.name) for p in mdt_root.glob("*/load_*.xml")
        if p.is_file() and p.parent.name not in _IGNORE_DIRS
    )


def parse_load_xml(xml_path: Path) -> list[str]:
    """解析 load_{season}.xml，返回未注释的副本 Lua 文件名列表。"""
    if not xml_path.exists():
        return []
    try:
        content = xml_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  警告: 无法读取 {xml_path.name}: {e}")
        return []

    active = []
    for line in content.splitlines():
        stripped = line.strip()
        # 跳过单行注释（MDT 用 <!-- <Script file='x.lua'/> --> 停用副本）
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        m = re.search(r"file\s*=\s*'([^']+)'", stripped)
        if m:
            active.append(m.group(1))
    return active


# ---------------------------------------------------------------------------
# 副本 Lua 解析
# ---------------------------------------------------------------------------

def parse_dungeon_file(file_path: Path) -> Optional[DungeonData]:
    """解析单个 MDT 副本 Lua 文件（状态机逐行扫描）。无怪物数据返回 None。"""
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception as e:
        print(f"  警告: 无法读取 {file_path.name}: {e}")
        return None

    dungeon = DungeonData()
    content = "\n".join(lines)

    m = re.search(r'englishName\s*=\s*"([^"]+)"', content)
    if m:
        dungeon.english_name = m.group(1)
    m = re.search(r'MDT\.dungeonList\[dungeonIndex\]\s*=\s*L\["([^"]+)"\]', content)
    if m:
        dungeon.name_key = m.group(1)
    m = re.search(r'shortName\s*=\s*L\["([^"]+)"\]', content)
    if m:
        dungeon.short_name_key = m.group(1)

    in_enemies = in_enemy = in_characteristics = in_spells = in_spell_entry = False
    spells_depth = 0
    current_enemy = Enemy()
    current_spell_id = 0

    for line in lines:
        stripped = line.strip()

        if "MDT.dungeonEnemies[dungeonIndex] = {" in stripped:
            in_enemies = True
            continue
        if not in_enemies:
            continue

        m = re.match(r'\["name"\]\s*=\s*"([^"]+)"', stripped)
        if m:
            if current_enemy.name:
                dungeon.enemies.append(current_enemy)
            current_enemy = Enemy(name=m.group(1))
            in_enemy = True
            in_characteristics = in_spells = False
            continue

        if not in_enemy:
            continue

        m = re.match(r'\["id"\]\s*=\s*(\d+)', stripped)
        if m:
            current_enemy.npc_id = int(m.group(1))
            continue
        m = re.match(r'\["creatureType"\]\s*=\s*"([^"]+)"', stripped)
        if m:
            current_enemy.creature_type = m.group(1)
            continue
        m = re.match(r'\["isBoss"\]\s*=\s*(true|false)', stripped)
        if m:
            current_enemy.is_boss = m.group(1) == "true"
            continue

        m = re.match(r'\["characteristics"\]\s*=\s*\{', stripped)
        if m:
            in_characteristics = True
            continue
        if in_characteristics:
            m = re.match(r'\["([^"]+)"\]\s*=\s*true', stripped)
            if m:
                current_enemy.characteristics.append(m.group(1))
            if stripped == "},":
                in_characteristics = False
            continue

        m = re.match(r'\["spells"\]\s*=\s*\{', stripped)
        if m:
            in_spells = True
            spells_depth = 1
            continue
        if in_spells:
            spells_depth += stripped.count("{") - stripped.count("}")
            m = re.match(r"\[(\d+)\]\s*=\s*\{", stripped)
            if m:
                current_spell_id = int(m.group(1))
                current_enemy.spells[current_spell_id] = SpellAttr()
                in_spell_entry = True
                continue
            if in_spell_entry:
                m = re.match(r'\["([a-zA-Z]+)"\]\s*=\s*(true|false)', stripped)
                if m:
                    current_enemy.spells[current_spell_id].set_attr(m.group(1), m.group(2) == "true")
                if stripped in ("},", "}"):
                    in_spell_entry = False
            if spells_depth <= 0:
                in_spells = False

    if current_enemy.name:
        dungeon.enemies.append(current_enemy)

    return dungeon if dungeon.enemies else None


def parse_all(mdt_root: Path) -> list[DungeonData]:
    """解析当前赛季（由 .toc 决定）的活跃副本，合并去重（按 english_name）。

    镜像策略：load XML 里勾掉的本自然消失；换赛季 = MDT 改 TOC，自动跟随。
    """
    dungeons: dict[str, DungeonData] = {}
    for season, load_name in find_seasons(mdt_root):
        season_dir = mdt_root / season
        load_xml = season_dir / load_name
        active = parse_load_xml(load_xml) if load_xml.exists() else []
        if active:
            lua_files = [season_dir / f for f in active if (season_dir / f).exists()]
        else:  # 没有 load XML 时扫描目录下全部 Lua
            lua_files = sorted(season_dir.glob("*.lua"))

        for lua_file in lua_files:
            d = parse_dungeon_file(lua_file)
            if d is None:
                continue
            d.season = season
            # 同名副本出现在多个赛季目录时保留第一个
            if d.english_name not in dungeons:
                dungeons[d.english_name] = d
    return list(dungeons.values())


# ---------------------------------------------------------------------------
# 本地化
# ---------------------------------------------------------------------------

def parse_locale_file(file_path: Path) -> dict[str, str]:
    """解析单个本地化 Lua 文件，提取 L["key"] = "value" 映射。"""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  警告: 无法读取 {file_path.name}: {e}")
        return {}
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r'L\["([^"]+)"\]\s*=\s*"([^"]*)"', content)
        if m.group(2)
    }


def parse_locales(locale_dir: Path, lang: str = "zhCN") -> dict[str, str]:
    """解析本地化，目标语言优先、回退 enUS。"""
    enus = parse_locale_file(locale_dir / "enUS.lua")
    target = parse_locale_file(locale_dir / f"{lang}.lua")
    merged = dict(enus)
    merged.update(target)
    print(f"  本地化: {len(target)} 条{lang}, {len(enus)} 条 enUS, 合并 {len(merged)} 条")
    return merged


def _lookup(locale_map: dict[str, str], lower_map: dict[str, str],
             key: str, default: str = "") -> str:
    """读取本地化值：精确命中优先，再大小写不敏感回退。lower_map 预计算一次即可。"""
    if not key:
        return default
    if key in locale_map:
        return locale_map[key]
    return lower_map.get(key.lower(), default)


def apply_localization(dungeons: list[DungeonData], locale_map: dict[str, str]) -> None:
    """把本地化中文名填入副本/怪物。"""
    lower_map = {k.lower(): v for k, v in locale_map.items()}
    for d in dungeons:
        fallback = d.english_name.replace(" ", "")
        d.name_cn = (
            _lookup(locale_map, lower_map, d.name_key)
            or _lookup(locale_map, lower_map, fallback)
            or _lookup(locale_map, lower_map, d.english_name, d.english_name)
        )
        d.short_name_cn = _lookup(locale_map, lower_map, d.short_name_key)
        for e in d.enemies:
            e.name_cn = _lookup(locale_map, lower_map, e.name, e.name)
