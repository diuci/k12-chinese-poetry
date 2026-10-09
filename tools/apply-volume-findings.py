#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 data/volume-findings.json 的核对结论，把仓里的册次改成统编教材的实际册次。

只改三样东西：frontmatter 的 volume / grade，篇名下面那行「> 作者 · 朝代 · 体裁 · 学段 · 册次」，
以及文件所在的目录（目录名就是册次，站点按目录浏览）。
正文、注释、译文、赏析一个字不动——册次是元数据，不是文本。

默认空跑，只打印会改什么；加 --write 才动手。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / 'data' / 'volume-findings.json'
POEMS = ROOT / 'data' / 'poems.json'

GRADE_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def grade_of(volume):
    m = re.match(r'^([一二三四五六七八九])年级', volume or '')
    return GRADE_NUM[m.group(1)] if m else None


def new_volume(finding):
    """教材目录只证明「在哪一册」，不证明这一首是课内还是课外诵读。
    仓里原来带「课外诵读」后缀的，保留后缀——去掉它会把「课外古诗词诵读」这个位置信息丢掉。
    """
    vol = finding['textbookVolume']
    # 教材目录自己就写着「课外诵读」时不许再叠一次：叠出来的是「七年级下册课外诵读课外诵读」，
    # 一个不存在的册次，站点按目录浏览会直接把它当成一个新册次。
    if finding['repoVolume'].endswith('课外诵读') and not vol.endswith('课外诵读'):
        vol += '课外诵读'
    return vol


def patch_file(path, new_vol, new_grade, old_vol):
    text = path.read_text(encoding='utf-8')
    m = re.match(r'\A---\n(.*?)\n---\n', text, re.S)
    if not m:
        return None, 'frontmatter 读不出来'
    fm = m.group(1)
    fm2 = re.sub(r'^volume:\s*.*$', 'volume: %s' % new_vol, fm, count=1, flags=re.M)
    if new_grade is not None:
        fm2 = re.sub(r'^grade:\s*.*$', 'grade: %d' % new_grade, fm2, count=1, flags=re.M)
    if fm2 == fm:
        return None, 'frontmatter 没变化'
    out = '---\n' + fm2 + '\n---\n' + text[m.end():]
    # 篇名下面那行元信息：最后一个字段是册次
    out = re.sub(r'^>\s*([^\n]*?)·\s*' + re.escape(old_vol) + r'\s*$',
                 lambda mm: '> ' + mm.group(1).rstrip() + ' · ' + new_vol,
                 out, count=1, flags=re.M)
    return out, None


def selftest():
    """这个脚本会改 frontmatter 的册次/年级，还会把 md 文件搬到另一个目录（站点按目录浏览）。
    它默认空跑，加 --write 才动手——所以它的错只在写盘那一刻显形。坏例子必须提前跑。"""
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    # 坏例1：年级从册次名里取，取不到必须是 None，不许蒙一个数
    must(grade_of('九年级下册') == 9, '坏例1：九年级读不出年级')
    must(grade_of('选修（2026起默写）') is None, '坏例1b：选修册被蒙成了一个年级')
    must(grade_of(None) is None, '坏例1c：册次是空的却没报错也没返回 None')

    # 坏例2：仓里带「课外诵读」后缀的必须保留——去掉它就把「课外古诗词诵读」这个位置信息丢了
    must(new_volume({'textbookVolume': '七年级下册', 'repoVolume': '七年级下册课外诵读'}) == '七年级下册课外诵读',
         '坏例2：课外诵读后缀被丢了')
    # 坏例3：教材目录自己就写着「诵读」时不许再叠一次（七年级下册课外诵读课外诵读 是假册次）
    must(new_volume({'textbookVolume': '七年级下册课外诵读', 'repoVolume': '七年级下册课外诵读'}) == '七年级下册课外诵读',
         '坏例3：后缀叠了两次')
    # 坏例4：仓里没后缀、教材有后缀——按教材落，后缀必须带上
    must(new_volume({'textbookVolume': '八年级上册课外诵读', 'repoVolume': '八年级上册'}) == '八年级上册课外诵读',
         '坏例4：教材写的后缀被丢了')

    # 坏例5/6/7：patch_file 只许动 frontmatter 的 volume/grade 与篇名下面那行元信息
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / '测试篇.md'
        p.write_text(('---\ntitle: 测试篇\nvolume: 七年级上册\ngrade: 7\n---\n'
                      '> 佚名 · 先秦 · 古诗 · 初中 · 七年级上册\n\n'
                      '正文里也有一句「七年级上册」不该被改。\n'), encoding='utf-8')
        out, err = patch_file(p, '七年级下册', 7, '七年级上册')
        must(err is None and out is not None, '坏例5：能改的却没改成')
        must('volume: 七年级下册' in out, '坏例5b：frontmatter 的册次没换')
        must('> 佚名 · 先秦 · 古诗 · 初中 · 七年级下册' in out, '坏例5c：元信息那行册次没换')
        must('正文里也有一句「七年级上册」不该被改。' in out, '坏例5d：正文被动了')

        p2 = Path(td) / '无年级.md'
        p2.write_text(('---\ntitle: 无年级\nvolume: 七年级上册\n---\n'
                       '> 佚名 · 先秦 · 古诗 · 初中 · 七年级上册\n\n正文。\n'), encoding='utf-8')
        out2, err2 = patch_file(p2, '七年级下册', None, '七年级上册')
        must(err2 is None and 'grade:' not in out2, '坏例6：没有 grade 字段却被凭空加了一个')

        p3 = Path(td) / '坏frontmatter.md'
        p3.write_text('# 没有 frontmatter\n\n正文。\n', encoding='utf-8')
        out3, err3 = patch_file(p3, '七年级下册', 7, '七年级上册')
        must(out3 is None and err3, '坏例7：frontmatter 读不出来却没报错')

        p4 = Path(td) / '元信息不匹配.md'
        p4.write_text(('---\ntitle: 甲\nvolume: 七年级上册\ngrade: 7\n---\n'
                       '> 佚名 · 先秦 · 古诗 · 初中 · 八年级上册\n\n正文。\n'), encoding='utf-8')
        out4, err4 = patch_file(p4, '七年级下册', 7, '七年级上册')
        must(out4 is not None and '· 八年级上册' in out4, '坏例8：元信息那行与册次本来就对不上，不许被顺手改成看着顺眼的样子')

    print('[ok] apply-volume-findings --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


def main():
    write = '--write' in sys.argv
    data = json.loads(POEMS.read_text(encoding='utf-8'))['poems']
    by_id = {p['id']: p for p in data}
    f = json.loads(FINDINGS.read_text(encoding='utf-8'))
    # 两种都要改：仓里册次写错的，和仓里写着「教材不收」、教材目录里却有这篇的。
    # 后者以前被审计直接跳过，假话就藏在里面。
    todo = [x for x in f['findings']
            if x['status'] in ('volume-mismatch', 'claimed-absent-but-present')]
    moved, skipped = [], []
    for x in todo:
        p = by_id.get(x['id'])
        if p is None:
            skipped.append((x['title'], 'poems.json 里没有这个 id'))
            continue
        old_path = ROOT / p['_path']
        if not old_path.exists():
            skipped.append((x['title'], '文件不存在：%s' % p['_path']))
            continue
        vol = new_volume(x)
        grade = grade_of(vol) if p.get('stage') in ('小学', '初中') else None
        new_path = old_path.parent.parent / vol / old_path.name
        if new_path == old_path and grade == p.get('grade'):
            skipped.append((x['title'], '其实不用改（册次同名）'))
            continue
        patched, err = patch_file(old_path, vol, grade, x['repoVolume'])
        if err:
            skipped.append((x['title'], err))
            continue
        moved.append((p['stage'], x['title'], x['repoVolume'], vol,
                      '%s → %s' % (p['_path'], new_path.relative_to(ROOT)),
                      x['textbookLesson'], '官方印证' if x.get('officiallyConfirmed') else ''))
        if write:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_text(patched, encoding='utf-8')
            old_path.unlink()
    print('册次改动：%d 篇%s' % (len(moved), '' if write else '（空跑，未写盘）'))
    for stage, title, old, new, path, lesson, conf in moved:
        print('  %-4s %-22s %-14s → %-16s %s %s' % (stage, title, old, new, path, conf))
    if skipped:
        print()
        print('跳过 %d 篇' % len(skipped))
        for t, why in skipped:
            print('  %-22s %s' % (t, why))
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
