# 八字平烦心事 · 古籍语料检索与排盘工具

一个把**历法排盘**和**六本命理古籍原文检索**打包在一起的小工具。

既可以作为 WorkBuddy 技能使用，也可以直接在命令行里跑。核心思路是：排盘交给代码算，断语只来自检索到的原文，异说并列摊开，不编造、不承诺预测准确。

> **定位**：传统文化语料的检索与解读工具，不是预测系统。命理无客观真值，请勿作为人生决策依据。

## 它能做什么

- **排盘**：公历/农历出生信息 → 四柱、十神、藏干、纳音、大运、流年（基于 `lunar_python`）
- **检索**：按主题或关键词，从六本古籍的 1094 个切块里找原文，逐条标出书名、卷、门
- **混合检索（可选）**：大白话提问也能命中古文（"钱被别人借走" → 《渊海子平·论劫财》），需要自己装向量模型并建索引，见下文
- **核验**：输出前把每条引文丢回语料核对"这句在不在库、归哪本书哪一门"，繁简自动统一——《渊海子平》是繁体、《三命通会》是简体，不归一化会把繁体句误判成"查无此句"
- **摊开异说**：同一件事古书说法矛盾时并列呈现，不合并成"标准答案"

## 目录结构

```
bazi/
├── SKILL.md                        # WorkBuddy 技能定义（含七段输出骨架与防错硬规则）
├── scripts/
│   ├── pai_pan.py                  # 排盘
│   ├── search_books.py             # 多书关键词检索（零依赖主线，只要 lunar_python）
│   ├── search_hybrid.py            # 关键词 + 向量混合检索（可选，需自建索引）
│   ├── verify_quotes.py            # 引文归属核验（输出前必跑）
│   ├── paths.py                    # 数据/模型路径解析（跟安装位置无关）
│   └── requirements.txt
├── references/
│   ├── books-and-topics.md         # 六书定位、主题路由、问事映射
│   ├── interpretation-rules.md     # 解读与输出规则
│   └── 财运范例.md                  # 一份完整范例（含已过库的引文表）
├── data/
│   └── chunks_all.jsonl            # 六书合一切块，约 1.5MB（随包）
├── LICENSE
└── README.md
```

数据目录默认取 `脚本所在目录/../data`，与安装位置无关。要放别处用环境变量：`BAZI_DATA`（整个数据目录）、`BAZI_CORPUS`（语料单文件）、`BAZI_EMBS`（向量索引单文件）、`BAZI_EMBED_MODEL`（向量模型目录或 HF 名称）。

## 快速开始

### 1. 装依赖

```bash
pip install -r scripts/requirements.txt
```

核心只需 `lunar_python`：没有向量库、没有大模型 API、没有外部服务。**混合检索是可选功能**，要它才另装 `numpy` 和 `sentence-transformers`。

### 2. 排盘

```bash
# 公历：年 月 日 时 分 秒，性别 1=男 0=女
python scripts/pai_pan.py --solar 1990 5 15 10 30 0 --gender 1

# 农历
python scripts/pai_pan.py --lunar 1990 5 15 10 30 0 --gender 0
```

输出 JSON，含四柱、十神、藏干、纳音、大运。

### 3. 检索古籍（关键词，零依赖）

```bash
# 按主题检索
python scripts/search_books.py "丁火 卯月 调候" --topic 调候 --top 6

# 限定某本书
python scripts/search_books.py "财星入墓" --book 三命通会 --top 5

# 关掉书目优先级，把不同书的说法平铺开
python scripts/search_books.py "身旺财衰 比劫夺财" --topic 旺衰 --flat
```

参数：`--topic` 格局/调候/旺衰/神煞/六亲/女命/纳音/基础/流年/病药；`--book` 限定书名；`--top` 条数（默认 8）；`--flat` 关闭书目优先级。

### 4. 引文核验（写任何结论之前跑）

```bash
# 每条写成 片段|声称书名|声称门名（书/门可留空）
python scripts/verify_quotes.py "财宜藏，藏则丰厚|三命通会|论正财" "有丙无甲者，豪富|穷通宝鉴|十月戊土"

# 批量：一行一条
python scripts/verify_quotes.py --file 我的引文清单.txt

# --strict：同一句在几本书里都有 → 判不合格（必须列全或指定归属，防"只取一部报出"）
# --full  ：命中后打印整块原文（防截半句、防把别家命例当通例）
```

输出 `✓归属一致 / ✗归属不符 / ✗零命中`。返回码非 0 即不合格，先改再交付。

## 混合检索（可选）· 模型与索引不随包提供

**一句话：谁要用谁自己装。** 本包只发整理好的语料，不发向量模型，也不发索引文件（体积大、还跟模型版本绑定）。

需要两步：

```bash
# 1) 装依赖
pip install numpy sentence-transformers

# 2) 建索引（首次约 6 分钟，CPU；产物 data/embeddings_bge_base_6books.npy ≈3.3MB）
python scripts/search_hybrid.py --build
```

关于向量模型（约 400MB）：

- **联网**：不用管，`--build` 时 `sentence-transformers` 会自动下载 `BAAI/bge-base-zh-v1.5`；
- **离线**：自己把模型目录下好，然后指过去——

```bash
# Windows PowerShell
$env:BAZI_EMBED_MODEL="D:\models\bge-base-zh-v1.5"
# macOS / Linux
export BAZI_EMBED_MODEL=/models/bge-base-zh-v1.5
```

建好之后：

```bash
python scripts/search_hybrid.py "钱被别人借走" --top 6
python scripts/search_hybrid.py "身旺财衰 比劫夺财" --mode keyword   # 只用关键词
python scripts/search_hybrid.py "中年以后财运什么时候好" --mode vector --top 5
```

`--mode`：`keyword` 精确引文 / `vector` 纯语义 / `hybrid`（默认，RRF 融合排名）。`--topic`、`--book`、`--flat` 与关键词版一致。结果多两列诊断分：`kw_score`、`vec_score`。

没有索引时，`hybrid`/`vector` 会直接提示"请先 --build"，`keyword` 模式不受影响——**不装模型也能用全套关键词检索与核验**。

## 作为 WorkBuddy 技能使用

把整个目录放到技能目录并重启：

```
Windows:     C:\Users\<用户名>\.workbuddy\skills\bazi\
macOS/Linux: ~/.workbuddy/skills/bazi/
```

新会话里说"算一卦""看八字""帮我看看财运"即可触发。技能定义（七段输出骨架、空亡以日柱为准、墓库逢冲属俗说等硬规则）都在 `SKILL.md`。

## 语料来源

六本古籍，共 **1094 个切块**，存于 `data/chunks_all.jsonl`（UTF-8 JSONL，一行一块）：

| 书名 | 块数 |
|---|---|
| 三命通会 | 476 |
| 滴天髓 | 257 |
| 穷通宝鉴 | 143 |
| 渊海子平 | 131 |
| 子平真诠 | 69 |
| 命理正宗 | 18 |

主题分布：调候 174、六亲 99、基础 95、格局 64、神煞 52、旺衰 47、女命 14、流年 11。

每块字段：`book`（书名）、`juan`（卷）、`men`（门/篇）、`tiao`（条号）、`tags`（十神神煞标签）、`topics`（主题标签）、`text`（正文）、`prio`（书目优先级）。

原始书（txt/pdf）**不随包**：本包只发切块结果，不带原件，也不带切块脚本。要加书换书，得自备原件并按 `references/books-and-topics.md` 里的口径自行切块。

## 设计原则

1. **排盘靠代码**：四柱、节气换月、起运、藏干、十神、纳音一律用 `lunar_python` 计算，不靠模型心算
2. **断语靠原文**：只用检索到的原文，不靠记忆补写，不编造出处；每条引文先过 `verify_quotes.py`
3. **异说并列**：两本书说法相反时分别标注，不合成"标准答案"
4. **现实归现实**：涉及婚姻、财务、健康、法律，明确建议咨询专业人士
5. **不搞迷信化解**：不写佩戴物品、改名、做法事、花钱消灾这类内容
6. **不编造用户的人生**：用户没说过的事实不许写进判断，推断必须标明是推断

## 边界说明

这套系统**不能证伪**：算准了被传颂，算错了总有台阶——时辰不准、心不诚、运没到。所以它更像解释系统，不是预测系统。

《三命通会·卷六·十干十二年生大贵人例》里，万民英自己列了七八个"命同运异"的例子，结论是"自求多福"；《了凡四训》讲"命由我作，福自己求"。两本书撞到同一个地方：**人的作为比盘重要。**

本项目据此定位为一面镜子，不是一张地图。

## 许可与免责

- 代码：MIT License，详见 [LICENSE](LICENSE)
- 语料：古籍原文属公有领域，切块整理结果随本项目一并公开
- 本项目仅供文化研究与个人消遣，**不预测未来，不提供医疗、法律、财务建议**。命运掌握在自己手里。
