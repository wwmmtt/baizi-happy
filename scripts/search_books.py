#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多书检索：一次查六本命理书（三命通会/滴天髓/穷通宝鉴/渊海子平/命理正宗 [+子平真诠待OCR]）。

与旧版 search.py 的区别：
1. 跨书检索，结果带 book 字段，同时给出「按裁断优先级」和「全部异说」两种视图；
2. 命中门名/标签/主题加权，书目优先级参与排序（同主题下子平真诠 > 穷通宝鉴 > 滴天髓 > 命理正宗 > 三命通会 > 渊海子平）；
3. 支持 --book 限定单书、--topic 限定主题（格局/调候/旺衰/神煞/六亲/女命/纳音/基础/流年/病药）、
   --flat 关闭优先级（用于摊开流派冲突）。

用法：
  python search_books.py "正官 用神" --top 8
  python search_books.py "丁火 卯月 调候" --topic 调候 --top 6
  python search_books.py "羊刃 七杀" --book 三命通会
  python search_books.py "伤官见官" --flat --top 12
"""
import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from paths import CORPUS as CHUNKS  # 默认 <包根>/data/chunks_all.jsonl；可用 BAZI_DATA 覆盖

# 严格同义词/别名词典（确定性展开，替代向量模型的模糊匹配）
ALIASES = {
    "七杀": ["偏官", "七煞"],
    "偏官": ["七杀", "七煞"],
    "七煞": ["偏官", "七杀"],
    "羊刃": ["阳刃"],
    "阳刃": ["羊刃"],
    "咸池": ["桃花"],
    "桃花": ["咸池"],
    "枭神": ["偏印"],
    "偏印": ["枭神"],
    "驿马": ["马星"],
    "马星": ["驿马"],
    "天乙": ["天乙贵人"],
    "天乙贵人": ["天乙"],
    "用神": ["相神", "喜神"],
    "身弱": ["日主弱", "身衰"],
    "身强": ["身旺", "日主强"],
    "调候": ["调侯", "寒暖", "燥湿"],
    "格局": ["成格", "破格"],
    # 「甲木」↔「甲日」：古籍断语多写「甲日生…」，用户习惯说「甲木」
    "甲木": ["甲日"], "甲日": ["甲木"],
    "乙木": ["乙日"], "乙日": ["乙木"],
    "丙火": ["丙日"], "丙日": ["丙火"],
    "丁火": ["丁日"], "丁日": ["丁火"],
    "戊土": ["戊日"], "戊日": ["戊土"],
    "己土": ["己日"], "己日": ["己土"],
    "庚金": ["庚日"], "庚日": ["庚金"],
    "辛金": ["辛日"], "辛日": ["辛金"],
    "壬水": ["壬日"], "壬日": ["壬水"],
    "癸水": ["癸日"], "癸日": ["癸水"],
    # 支月 ↔ 数字月 ↔ 「X提」：穷通宝鉴写「五月壬水」，金不换断写「子提/寅提」，用户按「午月」提问
    "寅月": ["正月", "寅提"], "正月": ["寅月", "寅提"],
    "卯月": ["二月", "卯提"], "二月": ["卯月", "卯提"],
    "辰月": ["三月", "辰提"], "三月": ["辰月", "辰提"],
    "巳月": ["四月", "巳提"], "四月": ["巳月", "巳提"],
    "午月": ["五月", "午提"], "五月": ["午月", "午提"],
    "未月": ["六月", "未提"], "六月": ["未月", "未提"],
    "申月": ["七月", "申提"], "七月": ["申月", "申提"],
    "酉月": ["八月", "酉提"], "八月": ["酉月", "酉提"],
    "戌月": ["九月", "戌提"], "九月": ["戌月", "戌提"],
    "亥月": ["十月", "亥提"], "十月": ["亥月", "亥提"],
    "子月": ["十一月", "子提"], "十一月": ["子月", "子提"],
    "丑月": ["十二月", "丑提"], "十二月": ["丑月", "丑提"],
}

# 主题 → 书目优先级（数字小优先）
TOPIC_PRIORITY = {
    "格局": ["子平真诠", "三命通会", "渊海子平", "命理正宗"],
    "调候": ["穷通宝鉴", "三命通会", "滴天髓"],
    "旺衰": ["滴天髓", "子平真诠", "渊海子平"],
    "神煞": ["三命通会", "渊海子平"],
    "六亲": ["三命通会", "渊海子平"],
    "女命": ["三命通会", "渊海子平"],
    "纳音": ["三命通会", "渊海子平"],
    "基础": ["渊海子平", "三命通会"],
    "流年": ["三命通会", "滴天髓"],
    "病药": ["命理正宗", "滴天髓"],
}


def expand(kws):
    out = set(kws)
    for kw in kws:
        for a in ALIASES.get(kw, []):
            out.add(a)
    return sorted(out)


def load():
    recs = []
    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def book_boost(book: str, topic: str, flat: bool) -> float:
    if flat or not topic:
        return 1.0
    order = TOPIC_PRIORITY.get(topic)
    if not order or book not in order:
        return 0.9
    rank = order.index(book)
    return 1.30 - 0.12 * rank


MONTH_KEYS = {"正月", "二月", "三月", "四月", "五月", "六月",
              "七月", "八月", "九月", "十月", "十一月", "十二月"}


def score(c, kws, topic, flat):
    text = c.get("text", "")
    men = c.get("men", "")
    tags = " ".join(c.get("tags", []))
    topics = c.get("topics", [])
    s = 0.0
    for kw in kws:
        if kw in men:
            s += 8
        if kw in tags:
            s += 6
        s += text.count(kw) * 1.0
    # 「五月」+「壬水」这类成对命中门名（《穷通宝鉴》按月分节），额外重奖，
    # 否则会出现「问五月壬水、却推二月壬水」的错配
    m_hit = [k for k in kws if k in MONTH_KEYS and k in men]
    d_hit = [k for k in kws if k not in MONTH_KEYS and k in men]
    if m_hit and d_hit:
        s += 30
    if s <= 0:
        return 0.0
    if topic and topic in topics:
        s *= 1.35
    elif topic:
        s *= 0.9
    return s * book_boost(c.get("book", ""), topic, flat)


def main():
    ap = argparse.ArgumentParser(description="多书命理检索")
    ap.add_argument("query", help="检索词（空格分隔）")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--book", default=None, help="限定书名，如 三命通会")
    ap.add_argument("--topic", default=None, help="限定主题：格局/调候/旺衰/神煞/六亲/女命/纳音/基础/流年/病药")
    ap.add_argument("--flat", action="store_true", help="关闭书目优先级（摊开异说）")
    args = ap.parse_args()

    if not CHUNKS.exists():
        print(json.dumps({"error": "chunks_all.jsonl 不存在，请先运行 build_corpus.py"}, ensure_ascii=False))
        sys.exit(1)

    kws = expand([w for w in args.query.split() if w.strip()])
    if not kws:
        print("[]")
        return

    scored = []
    for c in load():
        if args.book and c.get("book") != args.book:
            continue
        # --topic 改为软偏好，不再硬排除：56% 的块 topics 为空，
        # 硬筛会漏掉《论劫财》这类没打标签却极度相关的内容。
        # 主题加权已在 score() 内（命中×1.35 / 不命中×0.9）。
        s = score(c, kws, args.topic, args.flat)
        if s > 0:
            scored.append((s, c))

    scored.sort(key=lambda x: -x[0])
    out = []
    seen_text = set()
    for s, c in scored:
        key = c.get("text", "")[:40]
        if key in seen_text:   # 跨书重复片段去重
            continue
        seen_text.add(key)
        out.append({
            "score": round(s, 2),
            "book": c.get("book"),
            "juan": c.get("juan"),
            "men": c.get("men"),
            "tiao": c.get("tiao"),
            "topics": c.get("topics", []),
            "tags": c.get("tags", []),
            "text": c.get("text", ""),
        })
        if len(out) >= args.top:
            break

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
