#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引文校核：把待引的原文逐条回库定位，报告「命中/未命中」及所属 book·卷·门·条。

用法:
  python verify_quotes.py "库逢空则不能聚" "有丙无甲者，豪富"
  python verify_quotes.py --file quotes.txt          # 一行一条
  python verify_quotes.py --file q.txt --need 3      # 只报前3处上下文

口径（对应 SKILL.md「引文校核」条款）:
  1) 比对前做归一化：繁简统一（有 zhconv 则用它，无则退回内置异体表）、去标点空白、全半角统一；不做同义改写匹配。
  2) 引号内文字必须是某个 chunk 的「连续子串」，否则判未命中（拼接/自造都会在这里露出来）。
  3) 命中时打印 book / juan / men / tiao 与上下文，供确认归属没有挂错书。
返回码: 0 = 全部命中；1 = 有未命中（交付前必须先处理）。
"""
import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import CORPUS as _DEFAULT_CORPUS
CORPUS = str(_DEFAULT_CORPUS)  # 默认 <包根>/data/chunks_all.jsonl；可用 --corpus 覆盖

# 归一化用到的繁简/异体/讹字映射（只做字符级，不改语义）
MAP = {
    "慳": "吝", "貲": "资", "剋": "克", "剋": "克", "尅": "克", "梟": "枭",
    "綬": "绶", "殺": "杀", "衝": "冲", "麤": "粗", "麼": "么", "倂": "并",
    "郤": "却", "卻": "却", "郤": "却", "讎": "仇", "眾": "众", "養": "养",
    "嗣": "嗣", "壻": "婿", "內": "内", "說": "说", "萬": "万", "與": "与",
    "來": "来", "為": "为", "後": "后", "於": "于", "無": "无", "則": "则",
    "處": "处", "當": "当", "謂": "谓", "機": "机", "會": "会", "歲": "岁",
    "運": "运", "財": "财", "妻": "妻", "庫": "库", "墓": "墓", "刑": "刑",
    "從": "从", "將": "将", "發": "发", "實": "实", "貴": "贵", "賤": "贱",
    "層": "层", "韻": "韵", "潤": "润", "調": "调", "候": "候", "窮": "穷",
    "鑒": "鉴", "寶": "宝", "滿": "满", "虛": "虚", "斷": "断", "詳": "详",
}

PUNCT = re.compile(r"[\s，。、；：！？“”‘’（）()《》〈〉「」『』,.;:!?\"'\-—…·※　]")

try:
    import zhconv  # 繁简统一：库里《渊海子平》是繁体，《三命通会》是简体，不统一会误判"零命中"
except Exception:
    zhconv = None


def norm(s: str) -> str:
    s = s.replace("\u3000", " ")
    if zhconv is not None:
        try:
            s = zhconv.convert(s, "zh-cn")
        except Exception:
            pass
    for k, v in MAP.items():
        s = s.replace(k, v)
    s = PUNCT.sub("", s)
    return s


def load_chunks(corpus):
    out = []
    with open(corpus, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            o["_n"] = norm(o.get("text", ""))
            out.append(o)
    return out


def search(chunks, quote):
    q = norm(quote)
    hits = []
    for c in chunks:
        if q and q in c["_n"]:
            hits.append(c)
    return q, hits


def show(c, q, raw_quote, width=40, full=False):
    txt = c.get("text", "").replace("\n", "/")
    tag = f"《{c['book']}》"
    if c.get("juan"):
        tag += f" {c['juan']}"
    tag += f"·{c.get('men','')} #{c.get('tiao')}"
    print(f"    {tag}")
    if full:
        print(f"    全文：{txt[:1200]}")
        return
    npos = c["_n"].find(q)
    # 在归一化串上的位置映射回原串是近似，直接用原串找原样片段，找不到就取头部
    p = txt.find(raw_quote)
    if p < 0:
        p = max(0, min(len(txt) - 1, npos))
    s = max(0, p - width)
    e = min(len(txt), p + len(raw_quote) + width)
    tag = f"《{c['book']}》"
    if c.get("juan"):
        tag += f" {c['juan']}"
    tag += f"·{c.get('men','')} #{c.get('tiao')}"
    print(f"    {tag}")
    print(f"    …{txt[s:e]}…")


def main():
    ap = argparse.ArgumentParser(description="引文校核：逐条回库定位")
    ap.add_argument("quotes", nargs="*", help="待核引文（可多条）")
    ap.add_argument("--file", help="引文文件，一行一条")
    ap.add_argument("--need", type=int, default=2, help="每条最多显示几处上下文（默认2）")
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--full", action="store_true", help="命中即打印该块全文（强制读全，防截半句）")
    ap.add_argument("--strict", action="store_true", help="同一句命中多部书时判为不合格，必须列出全部或指定归属")
    args = ap.parse_args()

    corpus = args.corpus
    if not os.path.exists(corpus):
        print(f"[err] 语料库不存在: {corpus}")
        return 1

    items = list(args.quotes)
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            items += [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not items:
        print("[err] 没有待核引文")
        return 1

    chunks = load_chunks(corpus)
    print(f"语料：{corpus}（{len(chunks)} 块）\n")

    miss = 0
    bad_attr = 0
    for i, raw in enumerate(items, 1):
        # 支持 "片段|书名|门名" 三段式：带书名/门名即做归属校验
        parts = [p.strip() for p in raw.split("|")]
        quote = parts[0]
        want_book = parts[1] if len(parts) > 1 and parts[1] else ""
        want_men = parts[2] if len(parts) > 2 and parts[2] else ""

        q, hits = search(chunks, quote)
        print(f"[{i}] 「{quote}」" + (f"  期望归属：《{want_book}》·{want_men}" if want_book else ""))
        if not hits:
            miss += 1
            print("    ✗零命中 —— 库里没有这段连续文字。拼接/改写/自造都在这拦下；先删掉或重查。\n")
            continue

        books = sorted({h["book"] for h in hits})
        print(f"    命中 {len(hits)} 处，涉及 {len(books)} 部：{'、'.join(books)}")

        multi_book = len(books) > 1
        if multi_book and args.strict and not want_book:
            bad_attr += 1
            print("    ✗多书并存 —— 同一句在多部书里都有，不许只取一部报出。列全如下，请指定归属后重跑：")
            for h in hits:
                show(h, q, quote, full=args.full)
            print()
            continue

        judged = hits
        verdict = "✓归属一致"
        if want_book:
            judged = [h for h in hits if want_book in h["book"]]
            if not judged:
                bad_attr += 1
                print(f"    ✗归属不符 —— 这句只在 {'、'.join(books)} 里，不在《{want_book}》名下。改挂或删。\n")
                continue
            if want_men:
                judged_men = [h for h in judged if want_men in (h.get("men") or "")]
                if not judged_men:
                    bad_attr += 1
                    actual = "；".join(sorted({f"《{h['book']}》{h.get('juan','')}·{h.get('men','')}#{h.get('tiao')}" for h in judged}))
                    print(f"    ✗归属不符 —— 书对、门不对。该书内实际在：{actual}\n")
                    continue
                judged = judged_men
            print(f"    {verdict}")

        for h in judged[: max(1, args.need)]:
            show(h, q, quote, full=args.full)
        print()

    print("=" * 60)
    if miss or bad_attr:
        print(f"结果：{len(items)} 条中 零命中 {miss} 条、归属不符或多书并存 {bad_attr} 条 —— 不合格，先修正再交付。")
        return 1
    print(f"结果：{len(items)} 条全部通过（命中 + 归属，含带归属校验的条目）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
