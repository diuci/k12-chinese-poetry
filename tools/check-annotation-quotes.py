# -*- coding: utf-8 -*-
"""注释/译文/赏析 里带引号的「原文引文」，在本篇正文里到底有没有。

   只出报告，不当链条闸门：试过两道宽口径的判法，命中 228 处 / 775 条，绝大多数是
   我们自己写的白话转述和篇名——天天报警的护栏最后会被人关掉，比没有更危险。
   这一版把口径收窄到「像原文引文」：>=6 字、带句读、在本篇正文里找不到。
   命中的逐条人工看，看一条改一条。

用法：
  python tools/check-annotation-quotes.py            # 出报告 docs/annotation-quotes.md
  python tools/check-annotation-quotes.py --selftest # 坏例子自检
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POEMS = ROOT / 'poems'
ANN = ROOT / 'content' / 'annotations'
OUT = ROOT / 'docs' / 'annotation-quotes.md'

SECTIONS = ('全文', '必背全文', '必背名句')


def norm(s):
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]', '', s)


def poem_body(md_text):
    """一篇的正文：有 ## 全文 就取它；没有就取 H1 之后到第一个 H2 之前（短诗没有 ## 全文）。"""
    parts = []
    for sec in SECTIONS:
        m = re.search(r'^## ' + sec + r'\r?\n([\s\S]*?)(?=^## |\Z)', md_text, re.M)
        if m:
            parts.append('\n'.join(x for x in m.group(1).splitlines() if not x.startswith('>')))
    if not parts:
        m = re.search(r'^# [^\n]*\r?\n\r?\n(?:>[^\n]*\r?\n)*\r?\n([\s\S]*?)(?=^## |\Z)', md_text, re.M)
        if m:
            parts.append(m.group(1))
    return norm('\n'.join(parts))


def load_texts():
    texts = {}
    for p in POEMS.rglob('*.md'):
        t = p.read_text(encoding='utf-8')
        m = re.search(r'^---\r?\n([\s\S]*?)\r?\n---', t)
        if not m:
            continue
        idm = re.search(r'^id:\s*(\S+)', m.group(1), re.M)
        if not idm:
            continue
        texts[idm.group(1)] = poem_body(t)
    return texts


QUOTE = re.compile(r'[「“]([^」”]{6,60})[」”]')
BOOK = re.compile(r'《[^》]{2,24}》')


def cited_from(chunk, pos):
    """引文前后写了书名/篇名，就是注明出处的跨书引用，不算引错。"""
    return BOOK.findall(chunk[max(0, pos - 30): pos + 100])


def looks_like_quote(q):
    """像原文引文：够长、带句读。白话转述一般不带原文的句读。"""
    if not re.search(r'[，。？！；]', q):
        return False
    return len(norm(q)) >= 6


def scan(texts):
    hits = []
    for jf in sorted(ANN.glob('*.json')):
        data = json.loads(jf.read_text(encoding='utf-8'))
        for pid, val in data.items():
            if pid not in texts:
                continue
            for field in ('note', 'trans', 'appr'):
                raw = val.get(field)
                chunks = [str(x) for x in raw] if isinstance(raw, list) else ([raw] if isinstance(raw, str) else [])
                for chunk in chunks:
                    for m in QUOTE.finditer(chunk):
                        q = m.group(1)
                        if not looks_like_quote(q):
                            continue
                        nq = norm(q)
                        if nq in texts[pid]:
                            continue
                        other = [o for o, t in texts.items() if o != pid and nq in t]
                        hits.append({'id': pid, 'file': jf.name, 'field': field,
                                     'quote': q, 'elsewhere': other,
                                     'cited': cited_from(chunk, m.start())})
    return hits


def selftest():
    bad = 0
    # 1) 本篇正文里有的引文，不许报
    texts = {'a': norm('数月之后，时时而间进；期年之后，虽欲言。')}
    # 直接测判定函数，不绕 scan
    if looks_like_quote('时时而间进；期年之后，') and norm('时时而间进；期年之后') in texts['a']:
        pass
    else:
        print('坏例1：正文里有的引文被判成不在'); bad += 1
    # 2) 白话转述（没有原文句读）不许当引文
    if looks_like_quote('我有自己的世界不缺观众'):
        print('坏例2：没有句读的白话被判成引文'); bad += 1
    # 3) 带句读的白话会被判成引文——这是已知代价，必须承认，不许假装没有
    if not looks_like_quote('人生苦短，不如喝'):
        print('坏例3：口径判不住带逗号的白话（已知代价，报告里必须写明）'); bad += 1
    # 4) 太短的篇名/词牌名不许当引文
    if looks_like_quote('竹里馆，'):
        print('坏例4：三字的篇名被判成引文'); bad += 1
    # 5) 正文抽取：没有 ## 全文 的短诗，正文跟在 H1 之后，必须抽到
    md = '# 画\n\n> 王维 · 唐\n\n远看山有色，近听水无声。\n\n## 注释\n'
    if norm('远看山有色') not in poem_body(md):
        print('坏例5：短诗的正文没抽到，会造出假命中'); bad += 1
    # 6) 有 ## 全文 的必须取全文，不能把注释也算进正文
    md2 = '# 甲\n\n## 全文\n\n床前明月光，\n\n## 注释\n\n疑是地上霜：这是比喻。\n'
    if norm('疑是地上霜') in poem_body(md2):
        print('坏例6：注释被算进正文，护栏会被自己喂饱'); bad += 1
    # 7) 注明出处的跨书引用不许当「引错了」；没注明的要抓到
    if not cited_from('《论语·述而》里那句「我非生而知之者，好古，敏以求之者也」', 12):
        print('坏例7：写明了出处的跨书引用没被认出来'); bad += 1
    if cited_from('他接着说「我非生而知之者，好古，敏以求之者也」', 6):
        print('坏例8：没注明出处的引文被当成注明了'); bad += 1
    if bad:
        print('[!] check-annotation-quotes --selftest 失败 %d 项' % bad)
        return 1
    print('[ok] check-annotation-quotes --selftest 通（8 个坏例子全部试到）')
    return 0


def main():
    if '--selftest' in sys.argv:
        return selftest()
    texts = load_texts()
    hits = scan(texts)
    own = [h for h in hits if not h['elsewhere']]
    nocite = [h for h in own if not h['cited']]
    cited = [h for h in own if h['cited']]
    lines = ['# 注释/译文/赏析 里的引文核对（报告，不是闸门）', '',
             '口径：带引号、>=6 字、带句读、**在本篇正文里找不到**。',
             '前后写了《书名》的，算注明出处的跨书引用，不算引错。',
             '',
             '已知代价（不藏）：带逗号的白话转述会被判成引文（例：「人生苦短，不如喝」）。',
             '所以这一版**不当闸门**，只出数字和清单，命中的逐条人工看。',
             '',
             '## 汇总', '',
             '- 像引文的片段：%d 处' % len(hits),
             '- 本篇没有、别篇有（跨篇引用）：%d 处' % (len(hits) - len(own)),
             '- 本篇没有、别篇也没有：%d 处' % len(own),
             '  - 其中**注明了出处**：%d 处' % len(cited),
             '  - 其中**没注明出处**（要逐条看）：%d 处' % len(nocite),
             '',
             '## 没注明出处（最可能是引错了，或者是我们自己的白话）', '',
             '| 篇 | 字段 | 引文 |',
             '| --- | --- | --- |']
    for h in nocite:
        lines.append('| %s | %s | %s |' % (h['id'], h['field'], h['quote'].replace('|', '｜')))
    lines += ['', '## 注明了出处的跨书引用', '', '| 篇 | 字段 | 引文 | 注明在哪 |', '| --- | --- | --- | --- |']
    for h in cited:
        lines.append('| %s | %s | %s | %s |' % (h['id'], h['field'], h['quote'].replace('|', '｜'), '、'.join(h['cited'])))
    lines += ['', '## 跨篇引用（在别篇正文里找得到）', '',
              '| 篇 | 字段 | 引文 | 在哪一篇 |', '| --- | --- | --- | --- |']
    for h in hits:
        if h['elsewhere']:
            lines.append('| %s | %s | %s | %s |' % (h['id'], h['field'], h['quote'].replace('|', '｜'), '、'.join(h['elsewhere'])))
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('[引文核对] 像引文 %d 处；本篇没有 %d 处（注明出处 %d / 没注明 %d）；报告 docs/annotation-quotes.md'
          % (len(hits), len(own), len(cited), len(nocite)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
