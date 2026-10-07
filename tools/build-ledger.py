#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""台账生成器：把 poems/ 与两份课标契约合成一份可核对的内容台账。

产出两份东西：
  机器版 -> data/ledger.json
  人读版 -> docs/ledger.md

铁律：台账里的每一个数字都由脚本算出来，不许手抄、不许手写。
      docs/index.md 里手写的「拓展 11 篇」与校验器算出的 45 篇互相矛盾，
      这份工具就是要消灭这种东西。

用法：
  python tools/build-ledger.py            # 生成台账 + 打印账目闭合
  python tools/build-ledger.py --quiet    # 只生成文件
"""
import json
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import validate as V  # noqa: E402


def body_sections(path):
    """篇目正文里出现了哪些 ## 小节。"""
    text = path.read_text(encoding='utf-8')
    if text.startswith('---'):
        cut = text.find('\n---', 3)
        if cut > 0:
            text = text[cut + 4:]
    have = {}
    for line in text.splitlines():
        if line.startswith('## '):
            name = line[3:].strip()
            have[name] = have.get(name, 0) + 1
    return have


def frontmatter(path):
    """篇目的 frontmatter 键值（只取标量，够台账用）。"""
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---'):
        return {}
    cut = text.find('\n---', 3)
    if cut < 0:
        return {}
    out = {}
    for line in text[4:cut].splitlines():
        if ':' not in line or line.startswith(' '):
            continue
        key, value = line.split(':', 1)
        out[key.strip()] = value.strip()
    return out


def strip_frontmatter(path):
    text = path.read_text(encoding='utf-8')
    if text.startswith('---'):
        cut = text.find('\n---', 3)
        if cut > 0:
            text = text[cut + 4:]
    return text


def main():
    quiet = '--quiet' in sys.argv

    poems = V.load_poems()
    syll_o, extra = V.parse_syllabus(V.SYLLABUS)
    syll_h, _ = V.parse_syllabus(V.SYLLABUS_HS)
    syllabus = syll_o + syll_h

    norm_map = {}
    for p in poems:
        norm_map.setdefault(V.canon_title(p['title']), []).append(p)

    # 课标条目 -> 仓内篇目。一篇课标条目在仓里对应多篇时，每篇都算命中。
    matched = {}
    unmatched_syllabus = []
    for stage, idx, title, author in syllabus:
        base = V.canon_title(title.split('（')[0].split('(')[0])
        hit = norm_map.get(base) or norm_map.get(V.canon_title(title))
        if hit:
            for p in hit:
                matched[p['id']] = (stage, idx, title, author)
        else:
            unmatched_syllabus.append((stage, idx, title, author))

    rows = []
    for p in poems:
        path = ROOT / p['_path']
        sec = body_sections(path)
        lines = p.get('lines') or []
        chars = sum(len(x) for x in lines)
        syl = matched.get(p['id'])
        if syl:
            group, no, stitle, sauthor = syl
            category = '课标·义务教育' if group in ('小学', '初中') else '课标·高中'
        elif V.canon_title(p['title']) in extra:
            group, no, stitle, sauthor = ('教材拓展', None, p['title'], p['author'])
            category = '教材拓展'
        else:
            group, no, stitle, sauthor = (None, None, None, None)
            category = '来源不明'

        fm = frontmatter(path)
        recite = fm.get('recite') or p.get('recite') or ''

        flags = []
        if not recite:
            flags.append('缺背诵要求 recite')
        if '必背名句' not in sec:
            flags.append('无「必背名句」小节')
        if '异文' not in sec:
            flags.append('无异文记录')
        if not p.get('pairs') and len(lines) >= 2:
            flags.append('有 %d 句但无 pairs' % len(lines))
        if category == '来源不明':
            flags.append('既不在课标也不在教材拓展表')

        rows.append({
            'id': p['id'],
            'title': p['title'],
            'subtitle': p.get('subtitle'),
            'author': p['author'],
            'dynasty': p.get('dynasty'),
            'authorDied': p.get('authorDied'),
            'authorEraEnd': p.get('authorEraEnd'),
            'license': p.get('license'),
            'source': p.get('source'),
            'stage': p.get('stage'),
            'grade': p.get('grade'),
            'volume': p.get('volume'),
            'form': p.get('form'),
            'category': category,
            'syllabusGroup': group,
            'syllabusNo': no,
            'syllabusTitle': stitle,
            'recite': recite,
            'lineCount': len(lines),
            'charCount': chars,
            'sections': sorted(sec.keys()),
            'hasNotes': '注释' in sec,
            'hasTranslation': '译文' in sec,
            'hasAppreciation': '赏析' in sec,
            'hasFamous': '必背名句' in sec,
            'hasPlay': '玩法数据' in sec,
            'hasVariant': '异文' in sec,
            'pairsCount': len(p.get('pairs') or []),
            'flags': flags,
            'path': p['_path'],
        })

    rows.sort(key=lambda r: (r['stage'] or '', r['grade'] if r['grade'] is not None else 99,
                             r['syllabusNo'] if r['syllabusNo'] is not None else 999, r['id']))

    counts = {}
    for r in rows:
        counts[r['category']] = counts.get(r['category'], 0) + 1
    stage_counts = {}
    for r in rows:
        stage_counts[r['stage']] = stage_counts.get(r['stage'], 0) + 1

    matched_poems = len({r['id'] for r in rows if r['category'].startswith('课标')})

    # 一条课标条目对应仓内多篇：这不是错，但必须点名，否则「207 条 vs 208 篇」
    # 这种对不上的账就只能靠猜。
    by_syllabus = {}
    for r in rows:
        if r['syllabusNo'] is not None:
            by_syllabus.setdefault((r['syllabusGroup'], r['syllabusNo'], r['syllabusTitle']), []).append(r['title'])
    duplicates = [{'group': k[0], 'no': k[1], 'syllabusTitle': k[2], 'repoTitles': v}
                  for k, v in sorted(by_syllabus.items()) if len(v) > 1]

    summary = {
        'generated': date.today().isoformat(),
        'poemCount': len(rows),
        'syllabusCount': len(syllabus),
        'syllabusPrimary': len(syll_o),
        'syllabusSenior': len(syll_h),
        'categoryCounts': counts,
        'stageCounts': stage_counts,
        'syllabusEntriesMatched': matched_poems,
        'missingFromRepo': [{'stage': s, 'no': i, 'title': t, 'author': a}
                            for s, i, t, a in unmatched_syllabus],
        'duplicateSyllabusEntries': duplicates,
        'gapCounts': {
            '缺背诵要求': sum(1 for r in rows if '缺背诵要求 recite' in r['flags']),
            '无必背名句小节': sum(1 for r in rows if '无「必背名句」小节' in r['flags']),
            '无异文记录': sum(1 for r in rows if '无异文记录' in r['flags']),
            '来源不明': counts.get('来源不明', 0),
        },
    }

    (ROOT / 'data' / 'ledger.json').write_text(
        json.dumps({'summary': summary, 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')

    if not quiet:
        print('丢词大作战 · 内容台账')
        print('仓内篇目：%d 篇（%s）' % (len(rows), ' / '.join('%s %d' % (k, v) for k, v in sorted(stage_counts.items()))))
        print('课标条目：%d 条（义务教育 %d + 高中 %d）' % (len(syllabus), len(syll_o), len(syll_h)))
        print('归类：' + ' · '.join('%s %d 篇' % (k, v) for k, v in sorted(counts.items())))
        print()
        total = matched_poems + counts.get('教材拓展', 0) + counts.get('来源不明', 0)
        print('账目闭合：课标命中 %d + 拓展 %d + 来源不明 %d = %d，仓内 %d'
              % (matched_poems, counts.get('教材拓展', 0), counts.get('来源不明', 0), total, len(rows)))
        if unmatched_syllabus:
            print()
            print('课标要求但仓内没有：%d 篇' % len(unmatched_syllabus))
            for s, i, t, a in unmatched_syllabus:
                print('  · %s %02d %s（%s）' % (s, i, t, a))
        if duplicates:
            print()
            print('一条课标条目对应仓内多篇（%d 处）：' % len(duplicates))
            for d in duplicates:
                print('  · %s %02d「%s」→ 仓内 %s' % (d['group'], d['no'], d['syllabusTitle'], '、'.join(d['repoTitles'])))
        print()
        print('缺口：')
        for k, v in summary['gapCounts'].items():
            print('  %s：%d 篇' % (k, v))

    write_markdown(summary, rows, ROOT / 'docs' / 'ledger.md')
    if not quiet:
        print()
        print('已写 data/ledger.json（%d 行）与 docs/ledger.md' % len(rows))
    return 0


def write_markdown(summary, rows, out):
    L = []
    L.append('# 内容台账（自动生成）')
    L.append('')
    L.append('> 由 `python tools/build-ledger.py` 生成于 %s。**不要手改本文件**：' % summary['generated'])
    L.append('> 要改台账就改 poems/ 里的篇目或两份课标契约，然后重新生成。机器版在 data/ledger.json。')
    L.append('')
    L.append('## 账目闭合')
    L.append('')
    L.append('| 项 | 数 |')
    L.append('|---|---|')
    L.append('| 仓内篇目 | %d |' % summary['poemCount'])
    L.append('| 课标条目合计 | %d（义务教育 %d + 高中 %d） |' % (summary['syllabusCount'], summary['syllabusPrimary'], summary['syllabusSenior']))
    L.append('| 课标条目在仓内命中 | %d 篇 |' % summary['syllabusEntriesMatched'])
    for k in sorted(summary['categoryCounts']):
        L.append('| %s | %d 篇 |' % (k, summary['categoryCounts'][k]))
    L.append('| 课标要求但仓内缺失 | %d 篇 |' % len(summary['missingFromRepo']))
    L.append('')
    L.append('「命中篇数」可以大于「课标条目数」：一篇课标条目在仓里对应多篇时（如课标「凉州」')
    L.append('对应仓内《凉州词（王翰）》与《凉州（王翰）》）每篇都算命中。两边对不上的每一篇')
    L.append('都必须能在下面的明细里找到归类，找不到就是漏了。')
    L.append('')
    if summary['missingFromRepo']:
        L.append('### 课标要求但仓内缺失')
        L.append('')
        for m in summary['missingFromRepo']:
            L.append('- %s %02d %s（%s）' % (m['stage'], m['no'], m['title'], m['author']))
        L.append('')
    if summary['duplicateSyllabusEntries']:
        L.append('### 一条课标条目对应仓内多篇')
        L.append('')
        for d in summary['duplicateSyllabusEntries']:
            L.append('- %s %02d「%s」→ 仓内 %s' % (d['group'], d['no'], d['syllabusTitle'], '、'.join(d['repoTitles'])))
        L.append('')
    L.append('## 缺口统计')
    L.append('')
    L.append('| 缺口 | 篇数 |')
    L.append('|---|---|')
    for k in sorted(summary['gapCounts']):
        L.append('| %s | %d |' % (k, summary['gapCounts'][k]))
    L.append('')
    L.append('## 明细')
    L.append('')
    L.append('| 学段 | 册次 | 编号 | 篇目 | 作者 | 体裁 | 背诵要求 | 句 | 字 | 名句 | 玩法 | 归类 |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        L.append('| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            r['stage'] or '', r['volume'] or '',
            ('%02d' % r['syllabusNo']) if r['syllabusNo'] is not None else '—',
            r['title'], r['author'], r['form'] or '', r['recite'] or '**缺**',
            r['lineCount'], r['charCount'],
            '有' if r['hasFamous'] else '—', '有' if r['hasPlay'] else '—', r['category']))
    L.append('')
    out.write_text('\n'.join(L) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
