# -*- coding: utf-8 -*-
"""删掉内容 JSON 里诗库中不存在的幽灵条目。"""
import json, pathlib, sys

VALID = {p['id'] for p in json.loads(
    pathlib.Path('data/poems.json').read_text(encoding='utf-8'))['poems']}

for a in sys.argv[1:]:
    p = pathlib.Path(a)
    d = json.loads(p.read_text(encoding='utf-8'))
    ghost = sorted(set(d) - VALID)
    for g in ghost:
        d.pop(g)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    print('%s 删除幽灵条目 %d 个: %s' % (p.name, len(ghost), ghost))
    print('   剩余 %d 条' % len(d))
