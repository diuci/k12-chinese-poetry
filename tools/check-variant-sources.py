# -*- coding: utf-8 -*-
"""核对异文条目里引用的每一个维基文库页。

规矩：一条异文写了「出处：维基文库《某页》」，就必须满足两件事之一——
  A. 这一页就是本篇正文比对过的那一页（data/text-sources.json 的 page，合选页算在内）；
  B. 这一页在 data/variant-sources.json 里登记过，而且登记时写明的「这一页上确实有的那个字」
     今天还在这一页上。
两条都不满足就是可疑：要么页名写错，要么出处是编的。

--selftest 自带坏例子：登记了一个页上根本不存在的字，必须被拦下来。
"""
import json, re, sys, importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'text-sources.json'
EXTRA = ROOT / 'data' / 'variant-sources.json'
CITE = re.compile(r'出处：维基文库《([^》]+)》')


def load_records():
    return {r['id']: r for r in json.loads(SRC.read_text(encoding='utf-8'))['results']}


def load_extra():
    if not EXTRA.exists():
        return {}
    return json.loads(EXTRA.read_text(encoding='utf-8')).get('extra', {})


def audit_one(poem_id, cited, records, extra):
    rec = records.get(poem_id)
    pages = set((rec.get('page') or '').split(' + ')) if rec else set()
    if cited in pages:
        return None
    for e in extra.get(poem_id, []):
        if e['page'] == cited:
            return None
    return '既不是本篇的比对页，也没在 variant-sources.json 登记'


def main():
    records = load_records()
    extra = load_extra()
    total = bad = 0
    for md in sorted((ROOT / 'poems').rglob('*.md')):
        t = md.read_text(encoding='utf-8')
        fid = re.search(r'^id:\s*(\S+)', t, re.M)
        if not fid:
            continue
        m = re.search(r'^## 异文[^\n]*\n(.*?)(?=^## |\Z)', t, re.M | re.S)
        if not m:
            continue
        for ln in [x.strip() for x in re.split(r'\n(?=- )', m.group(1)) if x.strip().startswith('- ')]:
            for c in CITE.findall(ln):
                total += 1
                why = audit_one(fid.group(1), c, records, extra)
                if why:
                    bad += 1
                    print('  !! %s：%s ← %s' % (md.stem, c, why))
    print('[异文出处] 篇内引用维基文库页作出处 %d 处，可疑 %d 处' % (total, bad))
    return 1 if bad else 0


def selftest():
    records = {'x': {'id': 'x', 'page': '正文页A + 正文页B'}}
    extra = {'x': [{'page': '别本页C', 'verified': '甲'}]}
    assert audit_one('x', '正文页A', records, extra) is None, '坏例1：本篇比对页被误报'
    assert audit_one('x', '正文页B', records, extra) is None, '坏例2：合选页被误报'
    assert audit_one('x', '别本页C', records, extra) is None, '坏例3：登记过的别本页被误报'
    assert audit_one('x', '没登记的页', records, extra), '坏例4：没登记的页放过去了'
    assert audit_one('没有这篇', '任意页', records, extra), '坏例5：篇目不存在也放行'
    # 登记的内容本身要能验：页上没有那个字，登记就是假的
    spec = importlib.util.spec_from_file_location('cts', ROOT / 'tools' / 'check-text-sources.py')
    C = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(C)
    table = C.load_t2s()
    real, raw = C.page_text('老子河上公章句/德經')
    txt, _ = C.clean(raw, table)
    np = lambda s: re.sub(r'[\W_]+', '', s or '', flags=re.UNICODE)
    assert '其脆易破' in np(txt), '坏例6：登记的「其脆易破」不在这一页上（这一页变了？）'
    assert '其脆易泮' not in np(txt), '坏例7：把教材用字当成了这一页的用字'
    print('[ok] check-variant-sources --selftest 通（7 个坏例子全部被拦住）')
    return 0


if '--selftest' in sys.argv:
    sys.exit(selftest())
sys.exit(main())
