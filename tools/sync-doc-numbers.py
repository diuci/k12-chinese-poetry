# -*- coding: utf-8 -*-
"""把 docs/accuracy.md 里写死的数字改成产物当场的数。

存在的理由：这些数字是抄来的，抄来的数字会过期。护栏（audit-content 的「文档里写死的数字与产物一致」）
只查不改——于是每改一次正文，派生计数的四个数就动一下，文档立刻过期，护栏变红，整条链重跑一遍，
只为把三个数字手抄对一遍。手抄这一步本身就是最容易出错的地方，也是最没必要的地方。

这个工具只改数字，不改句子：句子里的口径、理由、哪一年核对的，一律照原样。
匹配器用 audit-content 里那一份（doc_number_actuals），两边不许各写一套——
改的那套和查的那套要是各写一套，链条就会永远跟自己打架。

用法：
  python tools/sync-doc-numbers.py            改 docs/accuracy.md（只在产物在场时改）
  python tools/sync-doc-numbers.py --selftest 试坏例子
"""
import json
import re
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / 'tools' / 'audit-content.py'
DOC = ROOT / 'docs' / 'accuracy.md'


def _load_audit():
    spec = importlib.util.spec_from_file_location('audit_content_for_sync', AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sync_text(doc_text, actuals):
    """按当场的数改文档里的数字。返回 (新文本, 改动列表)。

    产物不在场（某个当场数是 -1）而文档里正好写了这一处的数字——直接停：
    没有产物的时候把数字改成 -1，等于把「没数过」写成「数过」。"""
    if doc_text is None:
        raise SystemExit('[文档数字] 文档不在场：没有文档可改')
    changes = []
    out = doc_text
    for pat, want in actuals.items():
        found = list(re.finditer(pat, out))
        if not found:
            continue
        if want < 0:
            msg = '[文档数字] 文档写了「%s」，可这一轮的产物不在场，数不出来——不许改，也不许凭空写一个' % found[0].group(0).strip()
            raise SystemExit(msg)
        def _sub(m, want=want):
            if int(m.group(1)) == want:
                return m.group(0)
            changes.append('%s → %s' % (m.group(0).strip(), m.group(0).replace(m.group(1), str(want)).strip()))
            return m.group(0).replace(m.group(1), str(want))
        out = re.sub(pat, _sub, out)
    return out, changes


def selftest():
    bad = []
    # 坏例1：数字过期了必须被改到当场的数
    got, ch = sync_text('当场数：按表 35029 处、按裁定表 2074 处', {r'按表\s*(\d+)': 35030, r'按裁定表\s*(\d+)': 2075})
    if '按表 35030' not in got or '按裁定表 2075' not in got or len(ch) != 2:
        bad.append('坏例1：过期的数字没被改全（%s）' % got)
    # 坏例2：数字本来就对，不许误改（误改也是错：它让人以为这一处动过）
    got, ch = sync_text('当场数：按表 35030 处', {r'按表\s*(\d+)': 35030})
    if ch or got != '当场数：按表 35030 处':
        bad.append('坏例2：本来对的数字被改了')
    # 坏例3：产物不在场（-1）时必须停，不许把 -1 写进文档
    try:
        sync_text('当场数：按表 35030 处', {r'按表\s*(\d+)': -1})
        bad.append('坏例3：产物不在场还是改了数字')
    except SystemExit:
        pass
    # 坏例4：文档里没这些数字，不许报错也不许凭空加
    got, ch = sync_text('这一页没有那些计数。', {r'按表\s*(\d+)': 35030})
    if ch or got != '这一页没有那些计数。':
        bad.append('坏例4：文档里没有的数字被添上了')
    # 坏例5：不在匹配表里的数字一律不许动
    got, ch = sync_text('站内共 252 篇，链条 50 步。按表 10 处', {r'按表\s*(\d+)': 11})
    if '252 篇' not in got or '50 步' not in got or '按表 11 处' not in got:
        bad.append('坏例5：不该动的数字被动了（%s）' % got)
    # 坏例6：改完必须让护栏无话可说——这个工具存在的意义就是让那一项不再红
    A = _load_audit()
    act = {r'(\d+)\s*全对上': 218, r'(\d+)\s*部分对上': 33}
    got, ch = sync_text('219 全对上 / 32 部分对上', act)
    if A.doc_number_claims(got, act):
        bad.append('坏例6：改完护栏还报错，说明改的和查的不是同一份口径')
    # 坏例7：同一句里出现两次，两处都要改
    got, ch = sync_text('按表 10 处，另说按表 12 处', {r'按表\s*(\d+)': 11})
    if got.count('按表 11') != 2 or '按表 10' in got or '按表 12' in got:
        bad.append('坏例7：同一处出现两次只改了一遍（%s）' % got)
    # 坏例8：只许改数字，句子一个字不许动
    src = '出处核对那四个数本轮动了：219 全对上 / 32 部分对上 / 0 一句都对不上 / 1 核过没有正文页。'
    act8 = {r'(\d+)\s*全对上': 218, r'(\d+)\s*部分对上': 33, r'(\d+)\s*一句都对不上': 0, r'(\d+)\s*核过没有正文页': 1}
    got, ch = sync_text(src, act8)
    if re.sub(r'\d+', '#', got) != re.sub(r'\d+', '#', src):
        bad.append('坏例8：句子被改了，不只是数字')
    # 坏例9：空文档不许报错
    got, ch = sync_text('', {r'按表\s*(\d+)': 1})
    if got != '' or ch:
        bad.append('坏例9：空文档被改了')
    # 坏例10：文档为 None 必须停，不许默默写出一份
    try:
        sync_text(None, {r'按表\s*(\d+)': 1})
        bad.append('坏例10：文档不在场还继续')
    except SystemExit:
        pass
    if bad:
        for b in bad:
            print('  ' + b)
        raise SystemExit('[文档数字] --selftest 没通过：%d 个坏例子没试到' % len(bad))
    print('[ok] sync-doc-numbers --selftest 通（10 个坏例子全部试到）')


def main():
    if '--selftest' in sys.argv:
        selftest()
        return
    A = _load_audit()
    tj = ROOT / 'data' / 'traditional.json'
    sj = ROOT / 'data' / 'text-sources.json'
    vy = ROOT / '.github' / 'workflows' / 'verify.yml'
    trad = json.loads(tj.read_text(encoding='utf-8')) if tj.exists() else None
    tsrc = json.loads(sj.read_text(encoding='utf-8')) if sj.exists() else None
    yml = vy.read_text(encoding='utf-8') if vy.exists() else ''
    if trad is None or tsrc is None:
        raise SystemExit('[文档数字] 产物不在场（data/traditional.json 或 data/text-sources.json 缺）——先跑构建，再谈改文档')
    actuals, meta = A.doc_number_actuals(trad, tsrc, yml)
    if not DOC.exists():
        raise SystemExit('[文档数字] 缺 %s' % DOC)
    old = DOC.read_text(encoding='utf-8')
    new, changes = sync_text(old, actuals)
    if changes:
        DOC.write_text(new, encoding='utf-8')
        print('[文档数字] 改了 %d 处（数字由产物当场给出，句子没动）：' % len(changes))
        for c in changes[:12]:
            print('  ' + c)
        if len(changes) > 12:
            print('  …共 %d 处' % len(changes))
    else:
        print('[文档数字] 文档里的数字与产物当场一致，没改（当场数：出处核对 %s、apparatus %s）' % (json.dumps(meta['tstats'], ensure_ascii=False), json.dumps(meta['ca'], ensure_ascii=False)))


if __name__ == '__main__':
    main()
