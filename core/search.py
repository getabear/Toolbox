"""
搜索引擎 —— 关键字 + 模糊 + 自然语言描述。

评分策略(无需联网、无模型依赖):
  1. 精确/前缀命中 id、name          → 最高分
  2. 关键字(keywords)命中           → 高分
  3. 模糊匹配(rapidfuzz)name/desc   → 中分,容忍拼写错误
  4. 自然语言查询:中英文分词后,
     每个词在 description/keywords 中按权重累加
中文查询用字符 bigram 近似分词,英文按空格/驼峰切分。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz
except ImportError:  # 降级:无 rapidfuzz 时只用子串匹配
    fuzz = None

from .registry import Manifest

STOPWORDS = {
    "的", "了", "是", "我", "想", "要", "用", "有", "什么", "哪个", "哪些",
    "可以", "能", "帮我", "请问", "工具", "app", "the", "a", "an", "is",
    "to", "for", "of", "i", "want", "need", "me", "can", "that", "this",
    "and", "or", "with", "do", "you", "have",
}


@dataclass
class SearchResult:
    manifest: Manifest
    score: float
    reason: str = ""


def _tokenize(q: str) -> list[str]:
    q = q.strip().lower()
    if not q:
        return []
    tokens: list[str] = []
    # 英文/数字词
    tokens += re.findall(r"[a-z0-9]+", q)
    # 中文串 → 单字 + bigram
    for run in re.findall(r"[\u4e00-\u9fff]+", q):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
            if len(run) <= 4:
                tokens.append(run)
    return [t for t in tokens if t not in STOPWORDS] or [q]


class SearchEngine:
    # 各字段命中权重
    W_ID = 100.0
    W_NAME = 90.0
    W_KEYWORD = 60.0
    W_CATEGORY = 40.0
    W_DESC = 25.0
    W_FUZZY = 0.35   # 模糊分系数(0-100 → 0-35)

    def __init__(self, manifests: list[Manifest]):
        self._manifests = manifests

    def update(self, manifests: list[Manifest]) -> None:
        self._manifests = manifests

    def search(self, query: str, limit: int = 50) -> list[SearchResult]:
        q = (query or "").strip().lower()
        if not q:
            return [SearchResult(m, 0.0) for m in self._manifests]
        tokens = _tokenize(q)
        results: list[SearchResult] = []
        for m in self._manifests:
            score, reasons = self._score(m, q, tokens)
            if score > 0:
                results.append(SearchResult(m, score, " / ".join(reasons)))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    # ---- 内部 ----
    def _score(self, m: Manifest, q: str, tokens: list[str]) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        mid, mname = m.id.lower(), m.name.lower()
        mdesc = m.description.lower()
        mkeys = [k.lower() for k in m.keywords]
        mcat = m.category.lower()

        # 精确 / 前缀
        if q == mid or q == mname:
            score += self.W_ID
            reasons.append("精确匹配")
        elif mid.startswith(q) or mname.startswith(q):
            score += self.W_ID * 0.7
            reasons.append("前缀匹配")
        elif q in mname or q in mid:
            score += self.W_NAME * 0.6
            reasons.append("名称包含")

        # 关键字
        for k in mkeys:
            if q in k or k in q:
                score += self.W_KEYWORD
                reasons.append(f"关键字:{k}")
                break

        # 分类
        if q in mcat or mcat in q:
            score += self.W_CATEGORY
            reasons.append("分类匹配")

        # 描述包含
        if q in mdesc:
            score += self.W_DESC
            reasons.append("描述包含")

        # 模糊(容忍错拼 / 部分记忆)
        if fuzz is not None:
            fuzzy = max(
                fuzz.partial_ratio(q, mname),
                fuzz.partial_ratio(q, mdesc),
                max((fuzz.ratio(q, k) for k in mkeys), default=0),
            )
            if fuzzy >= 60:
                score += fuzzy * self.W_FUZZY
                reasons.append(f"模糊{fuzzy:.0f}")

        # 自然语言:多 token 覆盖度
        if len(tokens) > 1:
            hay_name = mname + " " + mid + " " + mcat
            hay_kw = " ".join(mkeys)
            hits = 0
            for t in tokens:
                if t in hay_name:
                    hits += 2
                elif t in hay_kw:
                    hits += 2
                elif t in mdesc:
                    hits += 1
                elif fuzz is not None and fuzz.partial_ratio(t, mdesc) >= 85:
                    hits += 1
            if hits:
                coverage = hits / (2 * len(tokens))
                score += coverage * self.W_DESC * 2
                reasons.append(f"语义覆盖{coverage:.0%}")
        return score, reasons
