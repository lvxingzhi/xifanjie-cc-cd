"""
站点数据构建模块

把解析结果（含 Wowhead 数据）直接输出为前端查询站用的 data.json（仓库根目录），
HTML 页面即仓库根目录的 index.html / cards.html。字符串统一清洗（去控制字符/归一化空白）。
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .parser import DungeonData


def sanitize(value) -> str:
    """清洗字符串字段：去控制字符、折叠空白。"""
    if value is None:
        return ""
    s = str(value)
    s = re.sub(r"[\x00-\x1f\x7f]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _row(d: DungeonData, e, spell_id: int, attrs, spell_data: dict) -> dict:
    sd = spell_data.get(spell_id, {})
    # Wowhead 缓存按语言嵌套（zhCN/enUS）；旧版单语言平铺格式兜底视为 zhCN
    zh = sd.get("zhCN") or (sd if "name" in sd else {})
    en = sd.get("enUS") or {}
    spell_name = zh.get("name") or en.get("name") or str(spell_id)
    spell_name_en = en.get("name") or zh.get("name") or str(spell_id)
    return {
        "dungeonZh": sanitize(d.name_cn or d.english_name),
        "dungeonEn": sanitize(d.english_name),
        "mobZh": sanitize(e.name_cn or e.name),
        "mobEn": sanitize(e.name),
        "npcId": sanitize(e.npc_id),
        "creatureType": sanitize(e.creature_type),
        "ccTypes": sanitize(", ".join(e.characteristics)),
        "isBoss": bool(e.is_boss),
        "spellName": sanitize(spell_name),
        "spellNameEn": sanitize(spell_name_en),
        "spellId": sanitize(spell_id),
        "description": sanitize(zh.get("description") or ""),
        "descriptionEn": sanitize(en.get("description") or ""),
        "interruptible": bool(attrs.interruptible),
        "isMagic": bool(attrs.magic),
        "isEnrage": bool(attrs.enrage),
        "isBleed": bool(attrs.bleed),
        "isPoison": bool(attrs.poison),
        "isDisease": bool(attrs.disease),
        "isCurse": bool(attrs.curse),
        "season": sanitize(d.season),
    }


def build_data(dungeons: list[DungeonData], spell_data: dict, mdt_sha: str) -> dict:
    """生成 data.json 载荷（结构与前端约定保持不变）。"""
    rows = []
    for d in dungeons:
        for e in d.enemies:
            for sid, attrs in e.spells.items():
                rows.append(_row(d, e, sid, attrs, spell_data))

    # 副本摘要（前端用 name/en/count，season 用于联动筛选）
    dungeon_map: dict[str, dict] = {}
    for d in dungeons:
        name = sanitize(d.name_cn or d.english_name)
        if name not in dungeon_map:
            dungeon_map[name] = {
                "name": name, "en": sanitize(d.english_name),
                "season": d.season, "count": 0,
            }
    for r in rows:
        dungeon_map[r["dungeonZh"]]["count"] += 1
    # 跳过无技能数据的副本（如 MDT 只导入了站位、还没填技能的本）
    skipped = [d.english_name for d in dungeons
               if dungeon_map[sanitize(d.name_cn or d.english_name)]["count"] == 0]
    if skipped:
        print(f"  跳过 {len(skipped)} 个无技能数据的副本（MDT 未提供技能）: {', '.join(skipped)}")
    dungeon_map = {k: v for k, v in dungeon_map.items() if v["count"] > 0}

    seasons: dict[str, list[str]] = {}
    for d in dungeons:
        name = sanitize(d.name_cn or d.english_name)
        if name in dungeon_map:  # 只有有数据的副本计入赛季
            seasons.setdefault(d.season, []).append(sanitize(d.english_name))

    return {
        "seasons": seasons,
        "dungeons": list(dungeon_map.values()),
        "rows": rows,
        "total": len(rows),
        "builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mdtSha": mdt_sha,
    }


def write(data_path: Path, payload: dict) -> None:
    """写出 data.json 到仓库根目录（与 index.html 同级，供 Pages 直接服务）。"""
    data_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  写出: {data_path}（{payload['total']} 行）")
