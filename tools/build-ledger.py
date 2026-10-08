#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""台账生成器：把 poems/ 与两份课标契约合成一份可核对的内容台账。

产出两份东西：
  机器版 -> data/ledger.json
  人读版 -> docs/ledger.md

铁律一：台账里的每一个数字都由脚本算出来，不许手抄、不许手写。
        docs/index.md 里手写的「拓展 11 篇」与校验器算出的 45 篇互相矛盾，
        这份工具就是要消灭这种东西。
铁律二：匹配口径与 validate.py 完全同源（都用 tools/match.py）。两边口径不一致，
        台账和校验器就会互相打脸。

用法：
  python tools/build-ledger.py            # 生成台账 + 打印账目闭合
  python tools/build-ledger.py --quiet    # 只生成文件
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import match as M  # noqa: E402
import validate as V  # noqa: E402


def body_sections(path):
    """篇目正文里出现了哪些 ## 小节。"""
    text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
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


# 一条合格的异文必须断言「这里有另一种写法」。
VARIANT_MARK = re.compile(r'一作|别本|他本|另一本|版本作|来源页作|夹注|异体|旧本作|通行本作|误作|》作')

def section_text(path, name):
    """某个 ## 小节的正文（到下一个 ## 为止）。台账要数异文条目的完成度，
    光知道「有没有这个小节」不够，得看见里面的条目。"""
    text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
    if text.startswith('---'):
        cut = text.find('\n---', 3)
        if cut > 0:
            text = text[cut + 4:]
    out, in_sec = [], False
    for line in text.splitlines():
        if line.startswith('## '):
            in_sec = line[3:].strip() == name
            continue
        if in_sec:
            out.append(line)
    return '\n'.join(out)


def frontmatter(path):
    """篇目的 frontmatter 键值（只取标量，够台账用）。"""
    text = path.read_text(encoding='utf-8').replace('\r\n', '\n')
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


def main():
    quiet = '--quiet' in sys.argv

    poems = V.load_poems()
    syll_o, extra = V.parse_syllabus(V.SYLLABUS)
    syll_h, _ = V.parse_syllabus(V.SYLLABUS_HS)
    syllabus = syll_o + syll_h

    assignments, problems = M.match_syllabus(poems, syllabus)
    matched = {}
    for ei, p, strength in assignments:
        stage, idx, title, author = syllabus[ei]
        matched[p['id']] = (stage, idx, title, author, strength)

    known = {}
    if V.KNOWN_DEFECTS.exists():
        for d in json.loads(V.KNOWN_DEFECTS.read_text(encoding='utf-8')).get('defects', []):
            known[d['key']] = d

    dup_groups = []
    for g in M.find_duplicates(poems):
        ids = sorted(p['id'] for p in g)
        key = 'duplicate:' + '|'.join(ids)
        dup_groups.append({'ids': ids, 'title': g[0]['title'], 'key': key,
                           'paths': [p['_path'] for p in g],
                           'phase': known.get(key, {}).get('phase', '未登记')})

    # 归类口径与 validate.py 完全一致：课标命中 → 重复副本 → 教材拓展 → 来源不明。
    # 两边口径不一致，台账和校验器就会互相打脸。
    import hashlib
    def fingerprint(p):
        return hashlib.sha256(''.join(p.get('lines') or []).encode('utf-8')).hexdigest()
    assigned_fp = {}
    for _ei, p, _s in assignments:
        assigned_fp.setdefault(fingerprint(p), p)
    dup_ids = {p['id'] for p in poems if p['id'] not in matched and fingerprint(p) in assigned_fp}
    extra_ids = {p['id'] for p in poems if V.canon_title(p['title']) in extra}

    rows = []
    for p in poems:
        path = ROOT / p['_path']
        sec = body_sections(path)
        fm = frontmatter(path)
        lines = p.get('lines') or []
        chars = sum(len(x) for x in lines)
        syl = matched.get(p['id'])
        if syl:
            group, no, stitle, sauthor, strength = syl
            category = '课标·义务教育' if group in ('小学', '初中') else '课标·高中'
        elif p['id'] in dup_ids:
            group, no, stitle, sauthor = ('重复副本', None, p['title'], p['author'])
            category = '重复副本'
        elif p['id'] in extra_ids:
            group, no, stitle, sauthor = ('教材拓展', None, p['title'], p['author'])
            category = '教材拓展'
        else:
            group, no, stitle, sauthor = (None, None, None, None)
            category = '来源不明'

        # 异文条目的完成度：一条合格的异文要有「出处」和「取舍」（docs/variants.md）。
        # 只数条目数，不当成错误——现在绝大多数条目还没有出处，这是进度，不是缺陷。
        vtext = section_text(path, '异文').strip()
        ventries = [x.strip() for x in re.split(r'\n(?=- )', vtext) if x.strip().startswith('- ')] if vtext else []
        # 只有断言「这里有另一种写法」的条目才是异文。版权说明、校勘待办、通假字解释
        # 以前也被算进「异文条目总数」，分母是虚的。不静默丢掉：单列一个计数。
        ventries_variant = [x for x in ventries if VARIANT_MARK.search(x)]
        v_other = len(ventries) - len(ventries_variant)
        # 「出处：仓内没核到」不是出处。把它算进带出处，等于把没核实伪装成已核实。
        v_unverified = sum(1 for x in ventries_variant if '出处：仓内没核到' in x)
        v_with_source = sum(1 for x in ventries_variant if '出处' in x and '出处：仓内没核到' not in x)
        v_with_choice = sum(1 for x in ventries_variant if '取舍' in x)

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
        if category == '重复副本':
            flags.append('与另一篇原文完全相同')

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
            'textbookStatus': p.get('textbookStatus'),
            'form': p.get('form'),
            'category': category,
            'syllabusGroup': group,
            'syllabusNo': no,
            'syllabusTitle': stitle,
            'matchStrength': syl[4] if syl else None,
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
            'variantEntries': len(ventries_variant),
        'variantNonEntries': v_other,
        'variantUnverified': v_unverified,
            'variantWithSource': v_with_source,
            'variantWithChoice': v_with_choice,
            # 「有全文」按 build.py 抽出来的全文正文算，不按小节标题叫什么算：
            # 短篇的正文直接写在篇名下面，没有「## 全文」这个标题，但它就是全文。
            # 只看标题会把 49 篇短篇误报成「没有全文」。
            # 口径只有一处实现：build.py::has_full_text。台账直接用它导出的字段。
            'hasFulltext': bool(p.get('hasFulltext')),
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

    problem_rows = []
    note_rows = []
    for pr in problems:
        d = known.get(pr['key'])
        item = {'key': pr['key'], 'text': pr['text'],
                'phase': d['phase'] if d else '未登记',
                'reason': d.get('reason', '') if d else ''}
        if pr['key'].startswith('shared:') or pr['key'].startswith('alias:'):
            item['phase'] = '正常'
            note_rows.append(item)
        else:
            problem_rows.append(item)
    unregistered = [x for x in problem_rows if x['phase'] == '未登记']

    summary = {
        'generated': date.today().isoformat(),
        'poemCount': len(rows),
        'syllabusCount': len(syllabus),
        'syllabusPrimary': len(syll_o),
        'syllabusSenior': len(syll_h),
        'categoryCounts': counts,
        'stageCounts': stage_counts,
        'matchStrengths': {str(s): sum(1 for r in rows if r['matchStrength'] == s) for s in (3, 2, 1)},
        'problems': problem_rows,
        'notes': note_rows,
        'unregisteredProblems': unregistered,
        'duplicates': dup_groups,
        'gapCounts': {
            '缺背诵要求': sum(1 for r in rows if '缺背诵要求 recite' in r['flags']),
            '只有必背名句（节选收录）': sum(1 for r in rows if not r['hasFulltext']),
            '仓内有全文正文': sum(1 for r in rows if r['hasFulltext']),
            '无异文记录': sum(1 for r in rows if not r['hasVariant']),
            # 异文考证的完成度（docs/variants.md）：条目总数 / 带出处 / 带取舍 / 缺出处
            '异文条目总数': sum(r['variantEntries'] for r in rows),
            '异文条目带出处': sum(r['variantWithSource'] for r in rows),
            '异文条目带取舍': sum(r['variantWithChoice'] for r in rows),
            '异文条目缺出处': sum(r['variantEntries'] - r['variantWithSource'] for r in rows),
        '异文小节里的非异文条目': sum(r.get('variantNonEntries', 0) for r in rows),
        '异文条目写明「仓内没核到」': sum(r.get('variantUnverified', 0) for r in rows),
            # （旧口径：按 flag 数无异文；现改用 hasVariant，与明细列同源）
            '缺全文（课标首句找不到）': sum(1 for x in problem_rows if x['key'].startswith('fulltext:')),
            '课标要求但仓内缺失': sum(1 for x in problem_rows if x['key'].startswith('missing:')),
            '重复副本': counts.get('重复副本', 0),
            '来源不明': counts.get('来源不明', 0),
            # 统编教材到底收没收（结论从 data/volume-findings.json 来，见 docs/textbook-audit.md）
            '统编教材收录': sum(1 for r in rows if r.get('textbookStatus') == '统编教材收录'),
            '统编教材未收（课标要求）': sum(1 for r in rows if r.get('textbookStatus') == '统编教材未收（课标要求）'),
            '统编教材收的是同名另一篇': sum(1 for r in rows if r.get('textbookStatus') == '统编教材收的是同名另一篇'),
        '统编教材收在别的课里': sum(1 for r in rows if r.get('textbookStatus') == '统编教材收在别的课里'),
            '没有教材收录状态': sum(1 for r in rows if not r.get('textbookStatus')),
        },
    }

    (ROOT / 'data' / 'ledger.json').write_text(
        json.dumps({'summary': summary, 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')

    if not quiet:
        print('丢词大作战 · 内容台账')
        print('仓内篇目：%d 篇（%s）' % (len(rows), ' / '.join('%s %d' % (k, v) for k, v in sorted(stage_counts.items()))))
        print('课标条目：%d 条（义务教育 %d + 高中 %d）' % (len(syllabus), len(syll_o), len(syll_h)))
        print('归类：' + ' · '.join('%s %d 篇' % (k, v) for k, v in sorted(counts.items())))
        print('匹配强度：首句 %d · 完整标题 %d · 仅主干标题 %d'
              % (summary['matchStrengths']['3'], summary['matchStrengths']['2'], summary['matchStrengths']['1']))
        total = sum(counts.values())
        print('账目闭合：' + ' + '.join('%s %d' % (k, v) for k, v in sorted(counts.items()))
              + ' = %d，仓内 %d' % (total, len(rows)))
        print()
        print('问题 %d 条（未登记 %d 条）：' % (len(problem_rows), len(unregistered)))
        for x in problem_rows:
            print('  [%s] %s' % (x['phase'], x['text']))
        print()
        print('缺口：')
        for k, v in summary['gapCounts'].items():
            print('  %s：%d' % (k, v))

    write_markdown(summary, rows, ROOT / 'docs' / 'ledger.md')
    if not quiet:
        print()
        print('已写 data/ledger.json（%d 行）与 docs/ledger.md' % len(rows))
    return 1 if unregistered else 0


def write_markdown(summary, rows, out):
    L = []
    L.append('# 内容台账（自动生成）')
    L.append('')
    L.append('> 由 `python tools/build-ledger.py` 生成于 %s。**不要手改本文件**：' % summary['generated'])
    L.append('> 要改台账就改 poems/ 里的篇目、两份课标契约或 data/known-defects.json，然后重新生成。')
    L.append('> 机器版在 data/ledger.json。匹配口径与 tools/validate.py 同源（tools/match.py）。')
    L.append('')
    L.append('## 账目闭合')
    L.append('')
    L.append('| 项 | 数 |')
    L.append('|---|---|')
    L.append('| 仓内篇目 | %d |' % summary['poemCount'])
    L.append('| 课标条目合计 | %d（义务教育 %d + 高中 %d） |' % (summary['syllabusCount'], summary['syllabusPrimary'], summary['syllabusSenior']))
    for k in sorted(summary['categoryCounts']):
        L.append('| %s | %d 篇 |' % (k, summary['categoryCounts'][k]))
    L.append('| 合计 | %d 篇 |' % sum(summary['categoryCounts'].values()))
    L.append('')
    L.append('匹配强度分布：首句对上 %d 篇、完整标题对上 %d 篇、只对上主干标题 %d 篇。'
             % (summary['matchStrengths']['3'], summary['matchStrengths']['2'], summary['matchStrengths']['1']))
    L.append('只对上主干标题的那批最危险：副题与首句都没核对，缺篇会被漏检。')
    L.append('')
    L.append('## 问题清单（每一条都必须有登记与负责阶段）')
    L.append('')
    L.append('| 负责阶段 | 问题 |')
    L.append('|---|---|')
    for x in summary['problems']:
        L.append('| %s | %s |' % (x['phase'], x['text']))
    if not summary['problems']:
        L.append('| — | 无 |')
    L.append('')
    L.append('## 缺口统计')
    L.append('')
    L.append('| 缺口 | 数量 |')
    L.append('|---|---|')
    for k in sorted(summary['gapCounts']):
        L.append('| %s | %d |' % (k, summary['gapCounts'][k]))
    L.append('')
    L.append('## 明细')
    L.append('')
    L.append('| 学段 | 册次 | 编号 | 篇目 | 作者 | 体裁 | 背诵要求 | 句 | 字 | 名句 | 全文 | 玩法 | 异文 | 归类 |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r in rows:
        L.append('| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            r['stage'] or '', r['volume'] or '',
            ('%02d' % r['syllabusNo']) if r['syllabusNo'] is not None else '—',
            r['title'], r['author'], r['form'] or '', r['recite'] or '**缺**',
            r['lineCount'], r['charCount'],
            '有' if r['hasFamous'] else '—', '有' if r['hasFulltext'] else '—',
            '有' if r['hasPlay'] else '—', '有' if r['hasVariant'] else '—', r['category']))
    L.append('')
    out.write_text('\n'.join(L) + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
