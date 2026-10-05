# -*- coding: utf-8 -*-
"""把 JSON 里的裸控制字符修成合法转义。

手写大批量内容时，很容易在某处敲进一个真回车而不是 \\n。
Python 的 json 会立刻报 Invalid control character，位置给得很准。

这个脚本按报错位置逐个修补，直到能解析为止——不猜测、不整体重写，
所以不会把已经写对的地方弄坏。

用法：
    python tools/fix-json.py content/annotations/*.json
"""
import json
import pathlib
import sys

ESC = {'\n': '\\n', '\r': '\\r', '\t': '\\t'}
LIMIT = 500


def fix(path):
    raw = path.read_text(encoding='utf-8')
    original = raw
    for i in range(LIMIT):
        try:
            json.loads(raw)
            if raw != original:
                path.write_text(raw, encoding='utf-8')
            return 'ok %d 处已修' % i if raw != original else 'ok 本来就合法'
        except json.JSONDecodeError as e:
            if e.pos >= len(raw):
                return '报错位置越界 pos=%d len=%d' % (e.pos, len(raw))
            ch = raw[e.pos]
            if ch in ESC:
                raw = raw[:e.pos] + ESC[ch] + raw[e.pos + 1:]
                continue
            return ('位置 %d 是 U+%04X，无法自动转义\n  上下文: %s'
                    % (e.pos, ord(ch), repr(raw[max(0, e.pos - 70):e.pos + 30])))
    return '修了两轮以上仍未成功'


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    bad = 0
    for a in sys.argv[1:]:
        p = pathlib.Path(a)
        msg = fix(p)
        flag = 'ok ' if msg.startswith('ok') else '[!!]'
        if not msg.startswith('ok'):
            bad += 1
        print('%s %-46s %s' % (flag, p.name, msg))
    sys.exit(1 if bad else 0)
