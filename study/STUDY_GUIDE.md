# Wordflow 英语学习内容指南

这份文件放在 Wordflow 仓库的 `study/` 目录里，说明我用 Wordflow 学英语的方法，以及怎样给《新概念英语》第二册（NCE2）继续生成配套内容。任何模型接手前先读完这份文件。

## 给模型的提示词（直接复制）

```text
你是我的英语老师。请先完整阅读 ~/workspace/spelllane/study/STUDY_GUIDE.md，再阅读范例
~/workspace/spelllane/study/content/nce2-01-10.json，然后为新概念英语第二册第 [11] 到 [20] 课
生成配套内容：每两课一个单元，共 5 个单元。

步骤：
1. 从 ~/.wordflow/articles.json 里读取分组 "New Concept 2" 中这几课的原文，
   找出每课的语法重点、核心句型和篇幅。
2. 按指南里的规则写成 ~/workspace/spelllane/study/content/nce2-[11]-[20].json。
3. 运行 python3 ~/workspace/spelllane/study/add_units.py <文件> 校验，修到全部通过。
4. 逐句自查英文语法和中英对应（指南里的"自查清单"）。
5. 给我看每个单元的语法点和全文，等我确认后再加 --write 写入。
6. 写入后更新指南末尾的"进度记录"，并提交 study/ 目录的改动（直接提交到 main）。
```

## 学习者和学习方法

- 母语是中文的成年人，在终端里的打字练习工具 Wordflow 上练英语拼写和句型。
- 主线教材是 NCE2 原文（96 课，已全部录入）。每两课配一个"单元"，学习顺序：
  1. **原文**：Copy 页 `New Concept 2`，打原文两课
  2. **现代版及抄写预习**：Copy 页 `New Concept 2 · Modern`，先打现代版文章，再中英对照抄写 quiz 句子
  3. **默写**：Quiz 页 `New Concept 2 · Modern`，看中文默写英文
- 最重要的原则：**不能让我学到错误的英文**。宁可保守，也不要写不地道或有语法问题的句子。

## Wordflow 的练习机制（决定了下面的格式规则）

- Copy 练习只要求打英文单词，匹配规则是 `[A-Za-z]+(?:['-][A-Za-z]+)*`。
  数字、标点、带重音的字母（é）都会被跳过，弯引号 `’` 会把 `There’s` 拆成两个词。
- 句子按 `. ! ? ; :` 后面的空格和换行来切分，所以 `Mr. Scott` 会被切成两句。
- Quiz 默写逐词比对：不区分大小写，忽略词与词之间的标点；数字、单词内部的撇号和连字符都必须打对。
  所以中文提示必须让英文答案**只有一种写法**。

## 每个单元产出什么

一个单元对应两课原文（11–12、13–14 ……），包含：

| 字段 | 要求 |
|---|---|
| `lessons` | 一对课号，如 `[11, 12]` |
| `title` | 现代版文章的英文标题，2–5 个词 |
| `article` | 现代版文章，一行一句，段落之间空一行 |
| `quiz` | 6–9 个 `[中文, 英文]` 句对 |

文件格式见范例 `study/content/nce2-01-10.json`。脚本会用 `Lessons N–M · <title>` 作为两处内容共同的标题，
并自动生成抄写预习条目，不需要手写。

## 现代版文章的写作规则

1. **语法与原文完全一致**：覆盖两课原文的语法重点（时态、语态、句型），并把它们作为全文的骨架。
2. **保留原文的核心句型**：每篇有意识地复用原文里的 3–5 个关键句子结构，比如
   *In the end, I could not bear it.*、*has never been abroad before, so he is finding…*、
   *It is being repaired by a friend of my father's.*。
3. **篇幅**：约等于两课原文的词数之和，允许 80%–125%（脚本会提示）。
4. **难度梯度**：
   - 句长、从句数量和原文同级，不能超前使用后面课程才出现的语法；
   - 每篇新增的现代词汇不超过 8 个，而且要常用（phone、message、online、drone、Wi-Fi 等）；
   - 其他词尽量用原文和前面单元已经出现过的词。
5. **内容**：一个连贯的现代故事，把两课的情节或主题融合起来；场景是当代日常，比如办公室、手机、网购、通勤、社交媒体。
   可以有轻微幽默，结尾最好像原文一样有个小反转。
6. **格式**：
   - 只用 ASCII 字符：直引号 `'` `"`，不用弯引号，不用重音字母；
   - 数字一律写成单词（`twenty minutes`、`nineteen seventy-two`）；
   - 不用 `Mr.`、`Mrs.`、`Dr.` 这类带点的缩写，直接用名字；
   - 英式拼写，与 NCE 保持一致：neighbour、colour、centre、theatre、realise/realize 都可以，但同一篇里要统一；
   - 对话用双引号。

## Quiz 的写作规则

1. **先写英文**：6–9 句，专门操练本单元的语法重点，句子来自文章，或是与文章同类的句子。
2. **英文答案不用缩写**：`I am`、`cannot`、`did not`、`it is`、`I have`、`I will`。
   所有格 `father's` 可以用。英文里也不出现数字。
3. **中文按英文逐词直译，不意译**。宁可中文稍显生硬，也要让英文答案唯一。固定对应关系：

   | 英文 | 中文提示写法 |
   |---|---|
   | just + 现在完成时 | 刚刚…了 |
   | have/has done、already | 已经…了 |
   | had done | 已经…了（配合过去的时间语境） |
   | was/were doing | 当时正在… |
   | will / would | 会… |
   | 被动语态 | 被… |
   | is being done | 正在被… |
   | a / an | 一个 / 一杯 / 一位…（必须写出量词） |
   | the（特指） | 那个 / 那位 / 那些 |
   | never … before | 以前从来没有… |

4. **中文里不能有英文字母**（Wi-Fi 写成"无线网"），否则抄写预习时会被当成要打的单词。
5. 如果某个词在中文里有几种英文说法（比如"停车场"可以是 car park 或 parking lot），就用文章里出现过的那一个。

## 工作流程

1. 关闭 Wordflow app。
2. 写好 `~/workspace/spelllane/study/content/nce2-<起>-<止>.json`。
3. 运行 `python3 ~/workspace/spelllane/study/add_units.py <文件>` 校验，不写入。
4. 自查（见下面的清单），把内容给我确认。
5. 运行 `python3 ~/workspace/spelllane/study/add_units.py <文件> --write`。脚本会先把两个数据文件备份到 `~/.wordflow/backup/`，再写入并重新加载校验。
6. 更新本文件末尾的"进度记录"。

要重新生成某个单元，先在 app 里删掉它的两处内容（Modern 文章和 Quiz），再重新写入。
想先演练的话，把数据复制到别处，然后设 `WORDFLOW_STUDY_DATA=<目录>` 再运行脚本。

## 自查清单

- [ ] 每句英文语法正确、表达地道，没有中式英语
- [ ] 覆盖了两课原文的全部语法重点，没有提前使用超纲的语法
- [ ] 拼写全部是英式，并且全文统一
- [ ] 每句 quiz 中文都能唯一地还原出英文答案（逐词对一遍）
- [ ] quiz 英文没有缩写，也没有数字
- [ ] 脚本校验通过

## NCE2 各课语法重点（参考，以原文为准）

NCE2 每 24 课一个语法循环。11–20 课大致是：
- 11：一般过去时与过去进行时（复习）
- 12：一般将来时 will
- 13：将来进行时 will be doing
- 14：过去完成时 had done
- 15：间接引语
- 16：第一类条件句 if…will
- 17：must / have to
- 18：have 的各种用法
- 19：can / may / might
- 20：动名词 -ing

动笔前务必读原文，核对这些语法点。

## 文件位置

| 路径 | 内容 |
|---|---|
| `~/.wordflow/articles.json` | Copy 页数据：原文、现代版、抄写预习 |
| `~/.wordflow/quizzes.json` | Quiz 页数据 |
| `~/workspace/spelllane/study/content/` | 每批生成内容的源文件，可以留作记录，也可以拿来重新生成 |
| `~/workspace/spelllane/study/add_units.py` | 校验和写入脚本（依赖 `~/workspace/spelllane/src` 里的 Wordflow 源码） |
| `~/.wordflow/backup/` | 每次写入前的自动备份 |

## 进度记录

| 课次 | 状态 | 内容文件 |
|---|---|---|
| NCE2 1–10 | 已完成（2026-11-02） | `study/content/nce2-01-10.json` |
| NCE2 11–20 | 待生成 | |
| NCE3 | 尚未决定是否做配套内容 | |

仓库里只放原创内容：现代版文章、quiz、规则和脚本。新概念原文和练习进度只保存在本机的 `~/.wordflow/articles.json`，不提交，因为原文有版权，而且仓库是公开的。
