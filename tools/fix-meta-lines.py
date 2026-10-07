#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每篇正文里那行元信息（作者 · 朝代 · 体裁 · 学段 · 册次）必须和 frontmatter 一致。

为什么要有这个工具：
以前有两种写法并存——「小学 · 六年级下册」和「小学五年级 · 六年级下册」。
后一种把年级写了两遍，册次一改它就变成假话：送元二使安西 从五年级下册挪到六年级下册之后，
那行成了「小学五年级 · 六年级下册」。年级本来就在册次里，重复一遍只会自己打自己。

三种模式：
  （默认）   空跑，只数有多少行不一致
  --write    按 frontmatter 重写那一行
  --check    有不一致就退出码 1（进构建链条用）
  --selftest 坏例子必须被抓到、好例子不许误报
"""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def frontmatter(text):
    m = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    if not m:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            fm[k.strip()] = v.strip()
    return fm


def want_line(fm):
    return '> %s · %s · %s · %s · %s' % (fm.get('author') or '', fm.get('dynasty') or '',
                                         fm.get('form') or '', fm.get('stage') or '',
                                         fm.get('volume') or '')


def find_meta_line(lines):
    for i, ln in enumerate(lines):
        if ln.startswith('> ') and ' · ' in ln:
            return i
    return -1


def scan(root):
    """返回 [(相对路径, 现有行, 应有行)]。"""
    bad = []
    for path in sorted((root / 'poems').rglob('*.md')):
        if path.name == '索引.md':
            continue
        text = path.read_text(encoding='utf-8')
        fm = frontmatter(text)
        if not fm:
            bad.append((path.relative_to(root), '(frontmatter 读不出来)', ''))
            continue
        want = want_line(fm)
        lines = text.split('\n')
        hit = find_meta_line(lines)
        if hit < 0:
            bad.append((path.relative_to(root), '(没有元信息行)', want))
            continue
        # 比较必须带上「> 」前缀：不带就每一篇都算「要改」，空跑永远报全仓，
        # 写完再跑还是全仓——这种数字看着像没修完，其实是比错了。
        if lines[hit].strip() != want.strip():
            bad.append((path.relative_to(root), lines[hit].strip(), want.strip()))
    return bad


GOOD = """---
id: t1
title: 假作M
author: 假作者
dynasty: 唐
form: 五言
stage: 初中
grade: 8
volume: 八年级上册
source: S9+S1
license: public-domain
---

# 假作M

> 假作者 · 唐 · 五言 · 初中 · 八年级上册

## 必背全文

床前明月光，疑是地上霜。
"""

BAD = """---
id: t2
title: 假作N
author: 假作者
dynasty: 唐
form: 五言
stage: 初中
grade: 8
volume: 八年级上册
source: S9+S1
license: public-domain
---

# 假作N

> 假作者 · 唐 · 五言 · 初中 · 七年级上册

## 必背全文

床前明月光，疑是地上霜。
"""

BAD2 = """---
id: t3
title: 假作O
author: 假作者
dynasty: 唐
form: 五言
stage: 初中
grade: 8
volume: 八年级上册
source: S9+S1
license: public-domain
---

# 假作O

> 假作者 · 唐 · 五言 · 初中八年级 · 八年级上册

## 必背全文

床前明月光，疑是地上霜。
"""


def selftest():
    """册次写错必须抓到；年级重复写两遍必须抓到；写对的不许误报。"""
    bad = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for name, text in (('good', GOOD), ('bad', BAD), ('bad2', BAD2)):
            d = root / 'poems' / '初中' / '八年级上册'
            d.mkdir(parents=True, exist_ok=True)
            (d / ('%s.md' % name)).write_text(text, encoding='utf-8')
        found = scan(root)
        got = {str(x[0]).replace('\\', '/') for x in found}
        if 'poems/初中/八年级上册/bad.md' not in got:
            bad.append('册次写错的元信息行没抓到（> … · 初中 · 七年级上册）')
        if 'poems/初中/八年级上册/bad2.md' not in got:
            bad.append('年级重复写两遍的元信息行没抓到（> … · 初中八年级 · 八年级上册）')
        if 'poems/初中/八年级上册/good.md' in got:
            bad.append('写对的元信息行被误报')
    if bad:
        print('[selftest 失败] ' + '；'.join(bad))
        return 1
    real = len(scan(ROOT))
    print('[ok] 元信息行护栏自检通过：册次写错被抓、年级重复被抓、写对的不误报；'
          '当前全仓不一致 %d 处' % real)
    return 0


def main():
    if '--selftest' in sys.argv:
        return selftest()
    bad = scan(ROOT)
    if '--write' in sys.argv:
        for rel, _cur, want in bad:
            path = ROOT / rel
            text = path.read_text(encoding='utf-8')
            lines = text.split('\n')
            hit = find_meta_line(lines)
            if hit < 0:
                continue
            lines[hit] = want
            path.write_text('\n'.join(lines), encoding='utf-8')
        print('已按 frontmatter 重写元信息行：%d 篇' % len(bad))
        return 0
    print('元信息行与 frontmatter 不一致：%d 篇' % len(bad))
    for rel, cur, want in bad[:20]:
        print('  %s\n    现有 %s\n    应有 %s' % (rel, cur, want))
    if bad and '--check' in sys.argv:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
