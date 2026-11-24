#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""混合检索：关键词 + bge-base-zh 向量（六书语料版）。

解决大白话查询零召回的问题：
  "钱被别人借走" → 命中《渊海子平·论劫财》"五阳见五阴为败财"
  "老婆跑了"     → 命中《滴天髓·夫妻》"其妻不贤，妒悍异常"
  "冬天出生要温暖" → 命中《滴天髓·寒暖》"天道有寒暖"

三种模式：
  keyword  纯关键词（精确引文用，如"戊生子月坐正财"）
  vector   纯向量（大白话探索用）
  hybrid   混合，RRF 融合排名（默认，兼顾两者）

用法：
  python search_hybrid.py "钱被别人借走"
  python search_hybrid.py "身旺财衰 比劫夺财" --mode keyword
  python search_hybrid.py "中年以后财运什么时候好" --mode vector --top 5
  python search_hybrid.py "老婆跑了" --topic 六亲 --top 6

首次使用需建索引（约 6 分钟，CPU）：
  python search_hybrid.py --build
"""
import argparse
import json
import sys
import time
from pathlib import Path



try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import search_books as KB  # 复用别名扩展 + 关键词打分

from paths import CORPUS as CHUNKS, EMBS, MODEL_PATH

RRF_K = 60  # Reciprocal Rank Fusion 常数


def load_chunks():
    return [json.loads(l) for l in CHUNKS.read_text(encoding="utf-8").splitlines() if l.strip()]


def doc_text(c):
    """建索引时的文档表示：门名 + 标签 + 正文（必须与 --build 一致）。"""
    return (c.get("men", "") + " " + " ".join(c.get("tags", [])) + " " + c.get("text", "")).strip()


def build_index(recs):
    import numpy as np
    from sentence_transformers import SentenceTransformer
    t0 = time.time()
    print(f"加载模型 {MODEL_PATH} ...（首次会自动下载；也可用环境变量 BAZI_EMBED_MODEL 指向本地目录）", flush=True)
    model = SentenceTransformer(MODEL_PATH)
    print(f"模型加载 {time.time()-t0:.1f}s，开始编码 {len(recs)} 块（约 6 分钟）...", flush=True)
    texts = [doc_text(c) for c in recs]
    t0 = time.time()
    embs = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    np.save(EMBS, embs)
    print(f"完成：{time.time()-t0:.1f}s, shape={embs.shape}, 保存至 {EMBS}", flush=True)


def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_PATH)


def main():
    ap = argparse.ArgumentParser(description="六书混合检索（关键词 + 向量）")
    ap.add_argument("query", nargs="?", help="检索词，大白话也行")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--mode", default="hybrid", choices=["keyword", "vector", "hybrid"])
    ap.add_argument("--book", default=None, help="限定书名")
    ap.add_argument("--topic", default=None, help="限定主题")
    ap.add_argument("--flat", action="store_true", help="关闭书目优先级")
    ap.add_argument("--build", action="store_true", help="（重新）生成向量索引")
    args = ap.parse_args()

    if not CHUNKS.exists():
        print(json.dumps({"error": f"语料不存在: {CHUNKS}"}, ensure_ascii=False))
        return

    recs = load_chunks()

    if args.build:
        build_index(recs)
        return

    if not args.query:
        print(json.dumps({"error": "请提供检索词，或用 --build 建索引"}, ensure_ascii=False))
        return

    # 过滤：book 仍硬筛；topic 改为软加权，不再硬排除。
    # 原因：约 56% 的块 topics 为空（TOPIC_RULES 要命中≥3词才打标），
    # 硬筛会漏掉《论劫财》这类没标签但高度相关的内容。
    # 主题匹配在 KB.score() 里当加权项（命中×1.35 / 不命中×0.9）。
    idxs = [i for i, c in enumerate(recs)
            if not args.book or c.get("book") == args.book]

    # 关键词分
    kws = KB.expand([w for w in args.query.split() if w.strip()])
    kw_scores = {}
    if args.mode in ("keyword", "hybrid"):
        for i in idxs:
            s = KB.score(recs[i], kws, args.topic, args.flat)
            if s > 0:
                kw_scores[i] = s

    # 向量相似度
    vec_scores = {}
    if args.mode in ("vector", "hybrid"):
        if not EMBS.exists():
            print(json.dumps({"error": f"向量索引不存在，请先运行: python {Path(__file__).name} --build"}, ensure_ascii=False))
            return
        try:
            import numpy as np
        except ImportError:
            print(json.dumps({"error": "未安装 numpy，向量检索用不了：pip install numpy（纯关键词模式不受影响）"}, ensure_ascii=False))
            return
        model = get_model()
        qv = model.encode([args.query], normalize_embeddings=True)[0]
        embs = np.load(EMBS, mmap_mode="r")
        sims = embs[idxs] @ qv
        for j, i in enumerate(idxs):
            vec_scores[i] = float(sims[j])

    # 排名
    kw_order = sorted(kw_scores, key=lambda i: -kw_scores[i])
    vec_order = sorted(vec_scores, key=lambda i: -vec_scores[i])
    kw_rank = {i: r for r, i in enumerate(kw_order)}
    vec_rank = {i: r for r, i in enumerate(vec_order)}

    if args.mode == "keyword":
        order = kw_order
        fused = {i: kw_scores[i] for i in order}
    elif args.mode == "vector":
        order = vec_order
        fused = {i: vec_scores[i] for i in order}
    else:
        # RRF 融合：两个排名的倒数相加，规避分数尺度差异
        cand = set(kw_scores) | set(vec_scores)
        def rrf(i):
            s = 0.0
            if i in kw_rank: s += 1.0 / (RRF_K + kw_rank[i] + 1)
            if i in vec_rank: s += 1.0 / (RRF_K + vec_rank[i] + 1)
            return s
        order = sorted(cand, key=lambda i: -rrf(i))
        fused = {i: rrf(i) for i in order}

    out = []
    seen = set()
    for i in order[:args.top * 2]:
        c = recs[i]
        key = c.get("text", "")[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "score": round(fused[i], 5),
            "kw_score": round(kw_scores.get(i, 0), 2),
            "vec_score": round(vec_scores.get(i, 0), 4),
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
