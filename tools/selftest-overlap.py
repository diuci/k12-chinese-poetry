# -*- coding: utf-8 -*-
"""自测：把《杂说》的作者改回韩愈，看检查会不会报警。

一个「零冲突」的检查很容易是因为根本没检出重叠，而不是因为数据干净。
所以必须拿一个已知错误去试它。
"""
import json, pathlib, shutil, subprocess, sys, tempfile

SRC = pathlib.Path('data/poems.json')
backup = SRC.read_text(encoding='utf-8')
try:
    d = json.loads(backup)
    for p in d['poems']:
        if p['id'] == 'zashuo4':
            print('注入错误: zashuo4 作者 %s·%s -> 韩愈·唐' % (p['author'], p['dynasty']))
            p['author'], p['dynasty'] = '韩愈', '唐'
    SRC.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')

    r = subprocess.run([sys.executable, '-X', 'utf8', 'tools/check-duplicates.py'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    caught = 'zashuo4' in r.stdout
    print()
    for ln in r.stdout.splitlines():
        if 'zashuo4' in ln or 'suoyoujiayao' in ln or '冲突' in ln:
            print('  ' + ln)
    print()
    print('检查是否抓到注入的错误: %s  退出码=%d' % ('抓到' if caught else '漏了', r.returncode))
finally:
    SRC.write_text(backup, encoding='utf-8')
    print('已还原 poems.json')
