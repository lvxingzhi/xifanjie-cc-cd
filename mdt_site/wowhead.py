"""
Wowhead 技能数据获取（原 spell_fetcher）

按 spell_id 从 nether.wowhead.com tooltip API 获取技能名与描述。
支持多语言（默认 zhCN + enUS），缓存按语言嵌套存储：

    { "<spell_id>": { "zhCN": {"name": ..., "description": ...},
                      "enUS": {"name": ..., "description": ...} } }

--fetch 模式：全量重拉所有技能，不信任旧缓存（PTR/赛季初 Wowhead 数据常残缺、
404 占位或翻译错误，每次构建都拿最新值，修正自动跟上）；单技能失败时回退
缓存旧值保证 data.json 完整。缓存仅作兑底，不再"永久封印"错误。
非 --fetch 模式：只读缓存，零请求（本地快速构建用）。

拉取支持线程池并发（--wowhead-workers）+ 全局限流 + 指数退避/429 退避 + 断点续传。
"""
from __future__ import annotations
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests


class _RateLimiter:
    """进程内全局限流：保证整体请求速率不超过 rate 次/秒（多线程共享）。"""

    def __init__(self, rate_per_sec: float):
        self._interval = 1.0 / max(rate_per_sec, 0.1)
        self._lock = threading.Lock()
        self._next_ok = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            delay = self._next_ok - now
            if delay > 0:
                time.sleep(delay)
            self._next_ok = max(now, self._next_ok) + self._interval


class SpellFetcher:
    API_URL = "https://nether.wowhead.com/tooltip/spell/{spell_id}"
    MAX_RETRIES = 4
    TIMEOUT = 20
    SAVE_EVERY = 20       # 每完成 N 个技能批量落盘一次（断点续传）

    def __init__(self, cache_path: Path, langs: tuple[str, ...] = ("zhCN", "enUS"),
                 no_fetch: bool = False, workers: int = 10):
        self.cache_path = cache_path
        self.langs = list(langs)
        self.no_fetch = no_fetch
        self.workers = max(1, workers)
        self.cache = self._load_cache()
        # 限流速率 = 并发数（Wowhead 服务端单请求 ~几秒，实际吞吐远低于此，限流只做保险）
        self._rate = _RateLimiter(self.workers)

    # ------------------------------------------------------------------
    # 缓存读写
    # ------------------------------------------------------------------

    def _load_cache(self) -> dict:
        if self.cache_path.exists():
            try:
                raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
            return self._migrate(raw)
        return {}

    @staticmethod
    def _migrate(raw: dict) -> dict:
        """旧版缓存（单语言平铺）→ 新版按语言嵌套；缺的语言留空，待 --fetch 补。"""
        migrated = {}
        for sid, v in raw.items():
            if not isinstance(v, dict):
                continue
            if "zhCN" in v or "enUS" in v:  # 已是新格式
                migrated[sid] = v
                continue
            # 旧格式：{"name": ..., "description": ...} → 视为 zhCN
            migrated[sid] = {
                "zhCN": {"name": v.get("name", ""), "description": v.get("description", "")},
            }
        return migrated

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # 拉取
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_tooltip(tooltip_html: str) -> str:
        """从 Wowhead tooltip HTML 提取纯文本描述。"""
        m = re.search(r'<div class="q">(.+?)</div>', tooltip_html, re.DOTALL)
        desc_html = m.group(1) if m else tooltip_html.split("</table>")[-1]
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", desc_html)).strip()

    def _request(self, spell_id: int, lang: str) -> dict:
        """单个请求，返回 {"name","description"}；彻底失败抛异常由上层处理。"""
        url = self.API_URL.format(spell_id=spell_id)
        if lang != "enUS":
            url += f"?locale={lang}"

        for attempt in range(self.MAX_RETRIES):
            self._rate.wait()  # 全局限流
            try:
                resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=self.TIMEOUT)
            except requests.RequestException:
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)  # 网络错误：指数退避 1s/2s/4s/8s
                continue
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "name": data.get("name", str(spell_id)),
                    "description": self._clean_tooltip(data.get("tooltip", "")),
                }
            if resp.status_code == 404:
                return {"name": str(spell_id), "description": ""}  # 缓存空结果防重复请求
            if resp.status_code == 429:
                time.sleep(5 * (attempt + 1))  # 被限流：多等一会儿再重试
                continue
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        raise RuntimeError(f"技能 {spell_id} ({lang}) 请求失败")

    def fetch_spell(self, spell_id: int) -> dict | None:
        """单个技能：--fetch 时全量重拉两种语言，失败或 404 时回退缓存旧值；否则只读缓存。"""
        key = str(spell_id)
        entry = dict(self.cache.get(key) or {})
        if self.no_fetch:
            return entry or None

        for lang in self.langs:
            try:
                fresh = self._request(spell_id, lang)
            except RuntimeError:
                continue  # 拉取失败：保留缓存旧值兑底
            # 404 占位（name=spell_id, desc 空）不覆盖已有真实数据，
            # 避免 Wowhead 临时性未收录把好值降级成占位符
            if fresh["name"] == str(spell_id) and lang in entry:
                continue
            entry[lang] = fresh
        if not entry:
            return None  # 全部失败且无缓存
        self.cache[key] = entry
        return entry

    def fetch_all_spells(self, spell_ids: set[int]) -> dict[int, dict]:
        """批量获取（线程池并发）：--fetch 时全量重拉所有技能（失败回退缓存），否则零请求只读缓存。

        并发安全：工作线程只负责网络请求并返回结果，缓存写入/落盘都在主线程完成。
        每 SAVE_EVERY 个批量落盘一次 + 结束/中断时，断点续传。
        """
        results = {}
        if self.no_fetch:
            for sid in spell_ids:
                if str(sid) in self.cache:
                    results[sid] = self.cache[str(sid)]
            print(f"  未开启 --fetch，读取缓存 {len(results)}/{len(spell_ids)} 个技能，零请求")
            return results

        total = len(spell_ids)
        print(f"  全量重拉 {total} 个技能（语言: {', '.join(self.langs)}，并发 {self.workers} 线程）")
        done = 0
        interrupted = False
        executor = ThreadPoolExecutor(max_workers=self.workers)
        try:
            futures = {executor.submit(self.fetch_spell, sid): sid for sid in spell_ids}
            for fut in as_completed(futures):
                sid = futures[fut]
                try:
                    entry = fut.result()
                except Exception:
                    entry = None
                done += 1
                if entry:
                    names = " / ".join(
                        entry.get(l, {}).get("name", "?") for l in self.langs if entry.get(l))
                    print(f"  [{done}/{total}] 技能 {sid} ✓ {names}")
                else:
                    print(f"  [{done}/{total}] 技能 {sid} ✗ 失败且无缓存")
                if done % self.SAVE_EVERY == 0:
                    self._save_cache()  # 批量落盘，断点续传
        except KeyboardInterrupt:
            interrupted = True
            self._save_cache()
            print(f"\n  用户中断，进度已保存（{done}/{total}），下次从断点继续")
            raise
        finally:
            # 正常完成：等全部收尾；中断：不等待在途请求，直接取消
            executor.shutdown(wait=not interrupted, cancel_futures=interrupted)
            self._save_cache()

        for sid in spell_ids:
            key = str(sid)
            if key in self.cache:
                results[sid] = self.cache[key]
        return results
