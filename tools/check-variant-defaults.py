#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""默认口径核对器：没有写「取舍」的异文条目，默认口径到底成不成立。

仓里的默认口径是：异文只登记，正文不改，用字以统编教材 / 来源页主文为准。
这条默认是**可以验的**：如果某条目断言的别本写法其实就在仓内正文里，
而条目引的那句仓内用字反而不在正文里——那说明这一条其实做过取舍，只是没写下来。

这个工具不写取舍。enrich-variants.py 的第一条规矩是「不替人做取舍」，
编一个「从教材」出来比空着更糟。它只做一件事：把「其实做过取舍却没写」的挑出来。
"""
import re, sys, json, importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
POEMS = ROOT / 'poems'
sys.path.insert(0, str(ROOT / 'tools'))

_spec = importlib.util.spec_from_file_location('bl', ROOT / 'tools' / 'build-ledger.py')
_bl = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_bl)
VM = _bl.VARIANT_MARK

QUOTE = re.compile(r'「([^」]+)」')
ALT_CITE = re.compile(r'(?:本作|一本作|一本无|别本作|来源页作|来源页注|页作|文库作|通行本作|旧本作|他本作|另一本作|误作|》作|一作)\s*「?([^，、。；「」]{1,24})」?')

def np(t):
    return re.sub(r'[\W_]+', '', t or '', flags=re.UNICODE)

def section_body(text, name):
    out, on = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            on = line[3:].strip() == name
            continue
        if on:
            out.append(line)
    return out

def entries(lines):
    out, cur = [], None
    for ln in lines:
        if ln.startswith('- '):
            if cur: out.append(cur)
            cur = [ln]
        elif cur and ln.strip():
            cur.append(ln)
        elif ln.strip():
            if cur: out.append(cur); cur = None
    if cur: out.append(cur)
    return [' '.join(x).strip() for x in out]

def body_text(text):
    """仓内正文：全文 / 必背全文 / 必背名句 三节里的句子。"""
    lines = []
    for name in ('全文', '必背全文', '必背名句'):
        lines += [x.strip() for x in section_body(text, name) if x.strip() and not x.startswith('>')]
    return np(' '.join(lines))

def check_one(entry):
    """返回 (是否违规, 说明)。违规 = 别本写法在正文里、仓内那句反而不在。"""
    qs = [q.replace('*', '') for q in QUOTE.findall(entry)]
    if len(qs) < 2:
        return False, ''
    anchor = np(qs[0])
    hits = [np(x.strip('，、。 ')) for x in ALT_CITE.findall(entry.replace('*', ''))]
    hits = [h for h in hits if h]
    if not hits:
        return False, ''
    return hits[-1], (anchor, hits[-1])

def run():
    bad, checked = [], 0
    for md in sorted(POEMS.rglob('*.md')):
        if md.name == '索引.md':
            continue
        text = md.read_text(encoding='utf-8')
        body = body_text(text)
        if not body:
            continue
        for e in entries(section_body(text, '异文')):
            if not VM.search(e):
                continue
            if '取舍' in e:
                continue          # 这一条自己写了取舍：不是「做过却没写」，不许报
            alt, info = check_one(e)
            if not alt:
                continue
            checked += 1
            anchor, altk = info
            if altk in body and anchor and anchor not in body:
                bad.append((md.name, e, anchor, altk))
    return bad, checked

def selftest():
    # 1) 默认口径成立：别本写法不在正文里
    ok = '## 全文\n\n檐牙高啄。\n\n## 异文\n- 「檐牙高啄」：来源页夹注「啄，一作琢」。出处：X\n'
    # 2) 违规：别本写法就是正文用的那个字，仓内那句反而不在
    bad = '## 全文\n\n吾理天下，官戒。\n\n## 异文\n- 「官戒也」：别本作「官戒」。出处：X\n'
    # 3) 正文里另有这个字但仓内那句也在正文里 —— 不是取舍，是巧合，不许报
    coincidence = '## 全文\n\n檐牙高啄，官戒也。\n\n## 异文\n- 「檐牙高啄」：别本作「官戒」。出处：X\n'
    # 4) 没有别本断言的条目不判
    plain = '## 全文\n\n甲乙。\n\n## 异文\n- 「甲乙」：句式与仓内一致。出处：X\n'
    def one(t):
        body = body_text(t)
        for e in entries(section_body(t, '异文')):
            if '取舍' in e:
                continue
            alt, info = check_one(e)
            if alt:
                a, k = info
                if k in body and a and a not in body:
                    return True
        return False
    assert not one(ok), '坏例1：默认口径成立的被报成违规'
    assert one(bad), '坏例2：其实做过取舍却没写的没被抓到'
    assert not one(coincidence), '坏例3：正文里另有这个字就被报，误报'
    assert not one(plain), '坏例4：没有别本断言的条目被拿去判定'
    # 5) 已经写了取舍的条目不许报——这个工具找的是「做过取舍却没写下来」
    chosen = '## 全文\n\n孤城落日斗兵稀。\n\n## 异文\n- 「孤城落日鬬兵稀」：来源页作「鬬兵稀」。取舍：从教材本作「斗」。出处：X\n'
    assert not one(chosen), '坏例5：写了取舍的条目被报成没写'
    import inspect
    print('[ok] check-variant-defaults --selftest 通（%d 个坏例子全部试到）'
          % inspect.getsource(selftest).count('assert '))
    return 0

def main():
    if '--selftest' in sys.argv:
        return selftest()
    bad, checked = run()
    print('[默认口径核对] 判了 %d 条没有取舍的异文条目，其中其实做过取舍却没写下来的：%d 条' % (checked, len(bad)))
    for name, e, anchor, alt in bad[:20]:
        print('  !! %s：正文用的是「%s」，条目却引仓内「%s」 → %s' % (name, alt, anchor, e[:110]))
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
