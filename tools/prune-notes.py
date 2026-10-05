# -*- coding: utf-8 -*-
"""按站点实际显示的范围裁剪注释。

站点上每篇只显示「必背全文」或「必背名句」，不是整首诗的全文。
按全文写的注释会挂到没显示出来的句子上——护栏会报「在诗里没有」。

这里自动剔除显示范围里不存在的注释词，并列出来供人工确认，
而不是让它们悄悄混进产物。
"""
import json, pathlib, re, sys

CJK = re.compile(r'[\u4e00-\u9fff]')
poems = {p['id']: p for p in json.loads(
    pathlib.Path('data/poems.json').read_text(encoding='utf-8'))['poems']}

for a in sys.argv[1:]:
    path = pathlib.Path(a)
    data = json.loads(path.read_text(encoding='utf-8'))
    dropped = []
    for pid, v in data.items():
        p = poems.get(pid)
        if not p:
            continue
        text = ''.join(CJK.findall((p.get('title') or '') + (p.get('subtitle') or '')
                                   + ''.join(p.get('lines') or [])))
        notes = v.get('note') or []
        if isinstance(notes, str):
            notes = [notes]
        keep = []
        for nline in notes:
            m = re.match(r'^\s*[-*]?\s*(.+?)\s*[:：]', nline)
            if not m:
                keep.append(nline)
                continue
            term = m.group(1).strip()
            chars = CJK.findall(term)
            if chars and all(c in text for c in chars):
                keep.append(nline)
            else:
                dropped.append('%s.%s' % (pid, term))
        v['note'] = keep
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('%s 剔除 %d 条越界注释' % (path.name, len(dropped)))
    for d in dropped:
        print('   - ' + d)
