#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排盘引擎：公历/农历出生时间 → 结构化 JSON 命盘（四柱/藏干/十神/纳音/地势/胎元/命宫/身宫/大运/流年/神煞）。

用法（gender: 1=男, 0=女；sect: 2=晚子时日柱算当天(默认)）:
  python pai_pan.py --solar 1990 5 15 10 30 0 --gender 1
  python pai_pan.py --lunar 1990 4 21 10 --gender 0
输出：标准 JSON（UTF-8）。
"""
import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from lunar_python import Solar, Lunar

# ---- 神煞表（常见表法，流派有差异，仅供参考） ----
TIAN_YI = {  # 天乙贵人：日干 -> 贵人地支
    "甲": "丑未", "戊": "丑未", "庚": "丑未",
    "乙": "子申", "己": "子申",
    "丙": "亥酉", "丁": "亥酉",
    "壬": "卯巳", "癸": "卯巳",
    "辛": "午寅",
}
YANG_REN = {  # 羊刃（阳刃）：日干 -> 刃支（阴干取辰未戌丑为常见表法）
    "甲": "卯", "乙": "辰", "丙": "午", "丁": "未", "戊": "午",
    "己": "未", "庚": "酉", "辛": "戌", "壬": "子", "癸": "丑",
}
KUI_GANG = {"庚辰", "庚戌", "壬辰", "戊戌"}  # 魁罡日柱
WEN_CHANG = {  # 文昌：日干 -> 支
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
    "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
}
# 三合局：年支 -> (桃花, 驿马, 华盖, 将星)
SAN_HE = {
    "申": ("酉", "寅", "辰", "子"), "子": ("酉", "寅", "辰", "子"), "辰": ("酉", "寅", "辰", "子"),
    "寅": ("卯", "申", "戌", "午"), "午": ("卯", "申", "戌", "午"), "戌": ("卯", "申", "戌", "午"),
    "巳": ("午", "亥", "丑", "酉"), "酉": ("午", "亥", "丑", "酉"), "丑": ("午", "亥", "丑", "酉"),
    "亥": ("子", "巳", "未", "卯"), "卯": ("子", "巳", "未", "卯"), "未": ("子", "巳", "未", "卯"),
}

KIND_TO_LABEL = {"Year": "year", "Month": "month", "Day": "day", "Time": "time"}
LABEL_ZH = {"year": "年柱", "month": "月柱", "day": "日柱", "time": "时柱"}


def build_pillar(ec, kind):
    label = KIND_TO_LABEL[kind]
    return {
        "label": LABEL_ZH[label],
        "gan_zhi": getattr(ec, "get" + kind)(),
        "gan": getattr(ec, "get" + kind + "Gan")(),
        "zhi": getattr(ec, "get" + kind + "Zhi")(),
        "cang_gan": getattr(ec, "get" + kind + "HideGan")(),
        "wu_xing": getattr(ec, "get" + kind + "WuXing")(),
        "na_yin": getattr(ec, "get" + kind + "NaYin")(),
        "shi_shen_gan": getattr(ec, "get" + kind + "ShiShenGan")(),
        "shi_shen_zhi": getattr(ec, "get" + kind + "ShiShenZhi")(),
        "di_shi": getattr(ec, "get" + kind + "DiShi")(),
    }


def compute_shen_sha(ec, pillars):
    day_gan = ec.getDayGan()
    zhis = [p["zhi"] for p in pillars]
    nian_zhi = pillars[0]["zhi"]
    res = {}

    gui = TIAN_YI.get(day_gan, "")
    if gui:
        hits = [z for z in zhis if z in gui]
        if hits:
            res["天乙贵人"] = hits

    ren = YANG_REN.get(day_gan, "")
    if ren:
        hits = [z for z in zhis if z == ren]
        if hits:
            res["羊刃"] = hits

    wc = WEN_CHANG.get(day_gan, "")
    if wc:
        hits = [z for z in zhis if z == wc]
        if hits:
            res["文昌"] = hits

    if pillars[2]["gan_zhi"] in KUI_GANG:
        res["魁罡"] = "日柱" + pillars[2]["gan_zhi"] + "为魁罡"

    if nian_zhi in SAN_HE:
        tao, yi, hua, jiang = SAN_HE[nian_zhi]
        for name, z in (("桃花", tao), ("驿马", yi), ("华盖", hua), ("将星", jiang)):
            hits = [x for x in zhis if x == z]
            if hits:
                res[name] = hits

    return res


def main():
    ap = argparse.ArgumentParser(description="八字排盘")
    ap.add_argument("--solar", nargs=6, type=int, metavar=("Y", "M", "D", "H", "MI", "S"), help="公历：年 月 日 时 分 秒")
    ap.add_argument("--lunar", nargs=4, type=int, metavar=("Y", "M", "D", "H"), help="农历：年 月 日 时")
    ap.add_argument("--gender", type=int, required=True, help="性别：1=男, 0=女")
    ap.add_argument("--sect", type=int, default=2, help="流派：2=晚子时日柱算当天(默认), 1=算明天")
    args = ap.parse_args()

    if args.solar:
        solar = Solar.fromYmdHms(*args.solar)
        lunar = solar.getLunar()
    elif args.lunar:
        lunar = Lunar.fromYmdHms(args.lunar[0], args.lunar[1], args.lunar[2], args.lunar[3], 0, 0)
        solar = lunar.getSolar()
    else:
        ap.error("需要 --solar 或 --lunar")

    ec = lunar.getEightChar()
    ec.setSect(args.sect)

    pillars = [build_pillar(ec, k) for k in ("Year", "Month", "Day", "Time")]

    yun = ec.getYun(args.gender)
    da_yun_list = []
    for dy in yun.getDaYun(11):  # index 0 = 童限，1..10 = 十步大运
        if dy.getIndex() < 1:
            continue
        liu_nian = [
            {"year": ln.getYear(), "age": ln.getAge(), "gan_zhi": ln.getGanZhi()}
            for ln in dy.getLiuNian(10)
        ]
        da_yun_list.append({
            "gan_zhi": dy.getGanZhi(),
            "start_age": dy.getStartAge(),
            "end_age": dy.getEndAge(),
            "start_year": dy.getStartYear(),
            "end_year": dy.getEndYear(),
            "xun_kong": dy.getXunKong(),
            "liu_nian": liu_nian,
        })

    result = {
        "input": {
            "solar": solar.toYmdHms(),
            "lunar": lunar.toFullString(),
            "gender": "男" if args.gender == 1 else "女",
            "sect": args.sect,
        },
        "four_pillars": pillars,
        "day_master": ec.getDayGan(),
        "tai_yuan": {"gan_zhi": ec.getTaiYuan(), "na_yin": ec.getTaiYuanNaYin()},
        "ming_gong": {"gan_zhi": ec.getMingGong(), "na_yin": ec.getMingGongNaYin()},
        "shen_gong": {"gan_zhi": ec.getShenGong(), "na_yin": ec.getShenGongNaYin()},
        "xun_kong": {
            "year": ec.getYearXunKong(), "month": ec.getMonthXunKong(),
            "day": ec.getDayXunKong(), "time": ec.getTimeXunKong(),
        },
        "da_yun": {
            "start": {
                "nian": yun.getStartYear(), "yue": yun.getStartMonth(),
                "ri": yun.getStartDay(), "shi": yun.getStartHour(),
                "solar": yun.getStartSolar().toYmd(),
            },
            "list": da_yun_list,
        },
        "shen_sha": compute_shen_sha(ec, pillars),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
