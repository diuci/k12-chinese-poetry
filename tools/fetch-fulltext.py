#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「只有必背名句、没有全文」的篇目去维基文库取全篇原文，取回来先核验，不直接写进仓。

为什么分两步：全文要进仓，就必须先证明「这一页写的确实是这一篇」。
证明方式：仓里已有的必背名句，逐句在这一页里找得到。找不齐就不给进仓。

产物 data/fulltext-candidates.json 是**候选**，不是结论。写进篇目文件要人过一遍。
"""
import importlib.util
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
_spec = importlib.util.spec_from_file_location('cts', ROOT / 'tools' / 'check-text-sources.py')
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)

OUT = ROOT / 'data' / 'fulltext-candidates.json'


def split_params(seg):
    """按顶层的 | 切模板参数，嵌套的 {{}} 和 [[ ]] 里的 | 不算。"""
    parts, depth, cur = [], 0, []
    i = 0
    while i < len(seg):
        if seg.startswith('{{', i) or seg.startswith('[[', i):
            depth += 1
            cur.append(seg[i])
            i += 2
            continue
        if seg.startswith('}}', i) or seg.startswith(']]', i):
            depth -= 1
            cur.append(seg[i])
            i += 2
            continue
        if seg[i] == '|' and depth == 0:
            parts.append(''.join(cur))
            cur = []
            i += 1
            continue
        cur.append(seg[i])
        i += 1
    parts.append(''.join(cur))
    return parts


KEEP_FIRST = {'專', '专', 'YL', 'YL2', '另', '另2', '校', '别', 'ProperNoun'}
# 「注」原来也在白名单里，结果把校勘笔记写进了正文：出师表那一页写作
# 「益州疲敝{{注|《诸葛亮集》作「敝」。}}」，留第一个参数就变成「益州疲敝《诸葛亮集》作「敝」。。」——
# 注释混进了课文。现在丢掉整个 {{注|…}}；真丢了正文，必背句核验会找不到，宁可不做。
DROP_ALL = {'Header', 'header', 'PD', 'PD-old', 'PD-art', 'CQ', 'YearCat', 'TitleTOC',
            '北宋作品', '唐詩', 'ProperNoun', 'noinclude', '底', 'Foot', 'notices'}


def strip_templates(w):
    """模板里的正文要留下，模板本身不许漏进正文。

    实测两个方向都踩过：
    - 整块删掉：岳阳楼记原文写作「{{專|慶曆}}四年，{{專|滕子京}}謫守{{專|巴陵郡}}」，
      删完变成「春，谪守」，年号人名全没了，看着像缺字，其实是删错了；
    - 一律留第一个参数：{{PD-old}}、{{ProperNoun}}、{{南梁作品}} 这些装饰模板被当成正文留下，
      正文里就冒出「Header」「PD-old」「ProperNoun」这种词。
    规则：只认白名单（專/YL/另/…——第一个参数就是页面正文用的那个字），其余一律丢。
    嵌套的从最里层往外剥，一层一层来，不然 {{YL|{{專|慶曆}}四年|1044年}} 会把内层整块当参数留下。"""
    for _ in range(12):
        if '{{' not in w:
            break
        m = re.search(r'\{\{((?:(?!\{\{|\}\}).)*?)\}\}', w, re.S)
        if not m:
            break
        parts = [x.strip() for x in m.group(1).split('|')]
        name = parts[0]
        if name == '!':
            rep = '|'
        elif name in KEEP_FIRST:
            unnamed = [x for x in parts[1:] if '=' not in x]
            rep = unnamed[0] if unnamed else ''
        else:
            rep = ''
        w = w[:m.start()] + rep + w[m.end():]
    return w

def expand_transclusions(w, depth=0):
    """把 {{:子页面}} 展开成子页面的正文。

    为什么必须展开：维基文库的组诗页只是目录——短歌行、出师表、行路难、无题 这几页
    正文全在子页面里，页面上只写着 {{:短歌行其一 (曹操)}}、{{:前出師表}}。
    不展开就抽到 0 行，看起来像「维基文库没有这首诗」，其实是目录页被当成了正文页。"""
    if depth > 2 or '{{:' not in w:
        return w
    def repl(m):
        title = m.group(1).strip()
        if not title:
            return ''
        try:
            _u, sub = C.page_wikitext(title)
        except Exception:
            return ''
        if not sub:
            return ''
        return expand_transclusions(sub, depth + 1)
    return re.sub(r'\{\{:([^{}|]+)\}\}', repl, w, flags=re.S)


def extract_body(w):
    """从 wikitext 里取正文：优先 <poem> 块；没有就取 Header 之后的正文段。"""
    w = expand_transclusions(w)
    # 维基文库的语言转换标记：-{zh-hans:余;zh-hant:余 馀;} 这种，取简体那一支。
    def _lc(m):
        body = m.group(1)
        for part in body.split(';'):
            if part.startswith('zh-hans:'):
                return part[7:]
        return body.split(';')[0].split(':', 1)[-1]
    w = re.sub(r'-\{([^{}]*?)\}-', _lc, w)
    # HTML 标签不是正文：过零丁洋那一页整首包在 <poem><CENTER><div class="Kaiti"> 里，
    # 不剥掉就会把 <templatestyles src="楷体/style.css" /> 这种东西写进课文。
    w = re.sub(r'</?[A-Za-z][A-Za-z0-9_]*(?:\s[^>]*)?/?>', '', w)
    w = re.sub(r'<!--.*?-->', '', w, flags=re.S)
    w = re.sub(r'</?onlyinclude>', '', w, flags=re.I)
    w = re.sub(r'</?noinclude>', '', w, flags=re.I)
    w = re.sub(r'<ref[^>]*/>', '', w)
    w = re.sub(r'<ref[^>]*>.*?</ref>', '', w, flags=re.S)
    w = re.sub(r'<references\s*/>', '', w)
    poems = re.findall(r'<poem[^>]*>(.*?)</poem>', w, flags=re.S)
    src = '\n'.join(poems) if poems else w
    src = strip_templates(src)
    src = re.sub(r'\[\[w:[^\]|]*\|([^\]]*)\]\]', r'\1', src)
    src = re.sub(r'\[\[([^\]|]*)\|([^\]]*)\]\]', r'\2', src)
    src = re.sub(r'\[\[([^\]]*)\]\]', r'\1', src)
    src = re.sub(r'\[http[^\]]*\|([^\]]*)\]', r'\1', src)
    src = re.sub(r'\[http[^\]]*\]', '', src)
    src = src.replace('{{!', '|').replace('&#124;', '|')
    lines = []
    for raw in src.split('\n'):
        ln = raw.strip()
        if not ln:
            lines.append('␞')
            continue
        if ln.startswith(('{|', '|}', '|-', '|class=', '[[File', '[[Image', '[[Category', 'Category:')):
            continue
        if re.match(r'^[-=]{2,}$', ln):
            continue
        if re.match(r'^(previous|next|section|times|author|title|from|notes|type|to\s*=)', ln):
            continue
        ln = re.sub(r'^[!*#;:]+', '', ln).strip()
        if ln:
            lines.append(ln)
    # 按空行分块：组诗一页里几十首，必须挑出「我们这一首」那一块，不能整页倒进仓。
    blocks, cur = [], []
    for ln in lines:
        if ln == '␞':
            if cur:
                blocks.append(cur)
            cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    return [b for b in blocks if b]


def main():
    only = None
    if '--limit' in sys.argv:
        only = int(sys.argv[sys.argv.index('--limit') + 1])
    poems = json.loads((ROOT / 'data' / 'poems.json').read_text(encoding='utf-8'))['poems']
    targets = [p for p in poems if not p.get('hasFulltext')]
    led = json.loads((ROOT / 'data' / 'ledger.json').read_text(encoding='utf-8'))
    src = json.loads((ROOT / 'data' / 'text-sources.json').read_text(encoding='utf-8'))
    src_by_id = {r['id']: r for r in src['results']}
    table = C.load_t2s()
    if only:
        targets = targets[:only]
    out = []
    for n, p in enumerate(targets, 1):
        rec = src_by_id.get(p['id']) or {}
        page = rec.get('page')
        if not page:
            cand = C.candidates(p['title'], p.get('author') or '', p.get('dynasty') or '', table,
                                lines=p.get('lines'))
            page = cand[0][0] if cand else None
        entry = {'id': p['id'], 'title': p['title'], 'author': p.get('author'),
                 'stage': p.get('stage'), 'page': page, 'lines': len(p.get('lines') or [])}
        if not page:
            entry['status'] = 'no-page'
            out.append(entry)
            print('[%3d/%3d] !! %s 找不到来源页' % (n, len(targets), p['title']))
            continue
        _u, w = C.page_wikitext(page)
        if not w:
            entry['status'] = 'page-empty'
            out.append(entry)
            print('[%3d/%3d] !! %s 页面取不到内容（%s）' % (n, len(targets), p['title'], page))
            continue
        blocks = extract_body(w)
        simp_blocks = [[C.to_simplified(x, table) for x in b] for b in blocks]
        norm = lambda t: re.sub(r'[，。！？；：、（）「」『』《》\s　·—…-]', '', t)
        norm_each = [norm('\n'.join(b)) for b in simp_blocks]
        where, miss = {}, []
        for ln in (p.get('linesPunct') or p.get('lines') or []):
            key = norm(C.to_simplified(ln, table))
            at = [i for i, t in enumerate(norm_each) if key and key in t]
            if at:
                where[ln] = at[0]
            else:
                miss.append(ln)
        hit = len(where)
        # 全部必背句落在同一块 → 那一块就是这一首；跨块 → 取最小连续跨度
        idx = sorted(set(where.values()))
        span = range(idx[0], idx[-1] + 1) if idx else []
        simp = [ln for i in span for ln in simp_blocks[i]]
        whole_page = len(simp_blocks) == 1
        entry.update({'status': 'ok' if hit == len(p.get('lines') or []) else 'partial',
                      'url': 'https://zh.wikisource.org/wiki/' + page,
                      'pageBlocks': len(simp_blocks), 'wholePage': whole_page,
                      'blockSpan': [idx[0], idx[-1]] if idx else None,
                      'bodyLines': len(simp), 'matched': hit, 'missed': miss,
                      'text': simp})
        out.append(entry)
        tail = '  整页一块' if whole_page else '  页内 %d 块，取第 %d-%d 块' % (
            len(simp_blocks), idx[0] + 1, idx[-1] + 1) if idx else '  一句都没对上'
        print('[%3d/%3d] %s %s（%s） 页=%s 正文 %d 行  必背句 %d/%d 对上%s' % (
            n, len(targets), 'ok' if entry['status'] == 'ok' else '!!', p['title'],
            p.get('author') or '', page, len(simp), hit, len(p.get('lines') or []), tail))
        time.sleep(0.12)
    OUT.write_text(json.dumps({'generated': time.strftime('%Y-%m-%d'),
                               'note': '候选全文：从维基文库页面抽出的正文（繁体转简体只用于本文件）。'
                                       'matched 是仓内必背名句在这一页里逐句找得到的数量；不齐的不许进仓。',
                               'results': out}, ensure_ascii=False, indent=2), encoding='utf-8')
    ok = sum(1 for x in out if x['status'] == 'ok')
    print()
    print('候选全文：%d 篇全对上 / %d 篇没全对上 / %d 篇取不到页面'
          % (ok, sum(1 for x in out if x['status'] == 'partial'),
             sum(1 for x in out if x['status'] in ('no-page', 'page-empty'))))
    print('已写 data/fulltext-candidates.json（候选，未进仓）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
