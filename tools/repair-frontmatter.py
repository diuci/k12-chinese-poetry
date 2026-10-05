# -*- coding: utf-8 -*-
"""修复 frontmatter 里混入的孤立标量行。

起因：18 个篇目的 frontmatter 里，grade 和 volume 之间多了一行孤零零的 `9`：

    ---
    grade: 3
    9            <-- 不该有
    volume: 三年级下册
    ---

它不是任何字段的值，是一段损坏。之所以一直没被发现：
- 站点构建用正则解析 frontmatter，多一行不影响
- validate.py 也用正则，同样忽略
- 页面照常生成、照常上线

只有严格按 YAML 解析才会报错——而现在没人这么解析。

跑法：
    python tools/repair-frontmatter.py           # 只体检
    python tools/repair-frontmatter.py --fix     # 修复
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POEMS = ROOT / 'poems'
KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*\s*:')
FIX = '--fix' in sys.argv

bad = []
for f in sorted(POEMS.rglob('*.md')):
    text = f.read_text(encoding='utf-8')
    m = re.match(r'^(---\s*\n)(.*?)(\n---\s*\n)', text, re.S)
    if not m:
        continue
    head, fm, tail = m.group(1), m.group(2), m.group(3)
    lines = fm.split('\n')
    junk = [i for i, ln in enumerate(lines)
            if ln.strip() and not KEY.match(ln) and not ln.strip().startswith('#')]
    if not junk:
        continue
    bad.append((f, [lines[i] for i in junk]))
    if FIX:
        keep = [ln for i, ln in enumerate(lines) if i not in set(junk)]
        f.write_text(head + '\n'.join(keep) + tail + text[m.end():], encoding='utf-8')

print('=== frontmatter 体检 ===')
print('frontmatter 中有孤立行的文件：%d' % len(bad))
for f, lines in bad[:20]:
    print('  %s -> %s' % (f.relative_to(ROOT), [s.strip() for s in lines]))
if FIX and bad:
    print('')
    print('已修复 %d 个文件' % len(bad))
elif bad:
    print('')
    print('加 --fix 执行修复')
sys.exit(1 if (bad and not FIX) else 0)
