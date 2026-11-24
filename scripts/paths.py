# -*- coding: utf-8 -*-
"""统一的数据/模型路径解析（让脚本跟安装位置无关）。

默认布局：
    包根/
      data/
        chunks_all.jsonl                     # 六书语料（随包）
        embeddings_bge_base_6books.npy       # 向量索引（不随包，自己 --build 生成）

覆盖方式（环境变量优先）：
    BAZI_DATA          整个数据目录
    BAZI_CORPUS        语料文件
    BAZI_EMBS          向量索引文件
    BAZI_EMBED_MODEL   向量模型目录或 HF 名称（默认 BAAI/bge-base-zh-v1.5）
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("BAZI_DATA") or (ROOT / "data"))
CORPUS = Path(os.environ.get("BAZI_CORPUS") or (DATA / "chunks_all.jsonl"))
EMBS = Path(os.environ.get("BAZI_EMBS") or (DATA / "embeddings_bge_base_6books.npy"))
MODEL_PATH = os.environ.get("BAZI_EMBED_MODEL") or "BAAI/bge-base-zh-v1.5"
