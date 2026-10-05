# -*- coding: utf-8 -*-
"""按上下文修掉内容 JSON 里的替换字符（U+FFFD）。

U+FFFD 是写入时编码坏掉留下的，损坏的字符个数不固定（2 个、3 个都有），
所以必须用正则匹配整段，不能按固定长度替换。

用法：python tools/fixmojibake.py content/annotations/*.json
"""
import json
import pathlib
import re
import sys

BAD = '\ufffd+'

# (正则, 替换)
RULES = [
    (r'宦游：离' + BAD + r'做官。', '宦游：离乡在外做官。'),
    (r'李白交朋友的' + BAD + r'式', '李白交朋友的方式'),
    (r'把自己最' + BAD + r'的东', '把自己最好的东'),
]


def fix(path):
    raw = path.read_text(encoding='utf-8')
    total = 0
    for pat, rep in RULES:
        raw, n = re.subn(pat, rep, raw)
        if n:
            print('   %s -> %d 处' % (rep[:16], n))
        total += n
    if total:
        path.write_text(raw, encoding='utf-8')
    # 复查
    d = json.loads(raw)
    left = []
    for pid, v in d.items():
        for f in ('note', 'trans', 'appr'):
            val = v.get(f)
            for it in (val if isinstance(val, list) else [val]):
                if it and '\ufffd' in it:
                    left.append('%s.%s' % (pid, f))
    return total, left


for a in sys.argv[1:]:
    p = pathlib.Path(a)
    print('[fix] %s' % p.name)
    n, left = fix(p)
    if left:
        print('   [!!] 仍需人工处理: %s' % ', '.join(left))
    else:
        print('   [ok] 已清理 %d 处' % n)
