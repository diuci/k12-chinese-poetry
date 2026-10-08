# data/opencc

`TSCharacters.txt` 取自 OpenCC（BYVoid/OpenCC）的 `data/dictionary/TSCharacters.txt`，
授权 Apache License 2.0；来源 <https://github.com/BYVoid/OpenCC>。

仓内共四张表，方向不同，用途不同，不许混用：

| 文件 | 方向 | 谁在用 |
|---|---|---|
| `TSCharacters.txt` / `TSPhrases.txt` | 繁 → 简 | `tools/check-text-sources.py`、`tools/build-traditional.py` 的可逆性检查 |
| `STCharacters.txt` / `STPhrases.txt` | 简 → 繁 | 只有 `tools/build-traditional.py` 用它**出候选** |

**用途限定**：

1. TS 表只用于把繁体来源（维基文库）转成简体来**比对**，以及把派生出的繁体转回简体做可逆性检查。
2. ST 表**只给候选，不给结论**。表的首选项是照现代繁体习惯写的，直接照抄会把古籍的字换掉：
   `古之欲明明德`→`古之慾明明德`、`吞二周`→`吞二週`、`百里奚`→`百裏奚`、`五溪`→`五谿`、
   `逝者如斯夫`→`逝者如斯伕`、`明月几时有`里的 `云`（说）→`雲`。这类表在换词，不是换字。
3. 所以繁体派生的优先级是：**来源页亲眼写作那个字 > `data/s2t-rules.json` 的裁定（每条必须带理由） > 表的首选项**；
   三样都没依据的，留在待定清单，不许静默择一。
4. 表里的扩展区残迹（`願`→`𫖸`、`開`→`𫔭`）一律拒收，除非那个字本来就出现在本篇正文里。

来源 <https://github.com/BYVoid/OpenCC>，授权 Apache License 2.0。
