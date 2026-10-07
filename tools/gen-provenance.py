#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""丢词大作战 · 版权台账生成

PROVENANCE.md 的「逐篇台账」以前是一张空表，却写着「由 validate.py 校验完整性」——
空表校验空表，比没有检查更危险。本脚本把台账改成从数据生成：
每篇一行，卒年直接取 frontmatter，改内容就重新生成，不手工维护。

用法：
    python tools/gen-provenance.py            重写 PROVENANCE.md 的台账段
    python tools/gen-provenance.py --check    只比对（CI 用，不一致 exit 1）
    python tools/gen-provenance.py --selftest 自检：坏样本必须被抓到
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_JSON = ROOT / 'data' / 'poems.json'
PROVENANCE = ROOT / 'PROVENANCE.md'

MARK_START = '<!-- 逐篇台账：由 tools/gen-provenance.py 生成，勿手改 -->'
MARK_END = '<!-- 台账结束 -->'


class ProvenanceError(Exception):
    pass


def load_poems():
    if not DATA_JSON.exists():
        raise ProvenanceError('缺少 data/poems.json，先跑 python tools/build.py')
    data = json.loads(DATA_JSON.read_text(encoding='utf-8'))
    poems = data.get('poems')
    if not isinstance(poems, list) or not poems:
        raise ProvenanceError('data/poems.json 里没有 poems 数组')
    return data['contentVersion'], poems


def year_cell(p):
    died = p.get('authorDied')
    era = p.get('authorEraEnd')
    if isinstance(died, int):
        return '卒 %s' % ('公元前 %d' % -died if died < 0 else died)
    if isinstance(era, int):
        return '年代上限 %s' % ('公元前 %d' % -era if era < 0 else era)
    raise ProvenanceError('%s：没有 authorDied / authorEraEnd' % p.get('title'))


def build_table(poems):
    rows = [
        '| id | 篇目 | 作者 | 朝代 | 公有领域证据 | 原文版权 | 来源 | 体裁 | 学段 · 册次 |',
        '|---|---|---|---|---|---|---|---|---|',
    ]
    for p in sorted(poems, key=lambda x: (str(x.get('stage') or ''), x.get('grade') or 0, x['title'])):
        rows.append('| %s | %s | %s | %s | %s | public-domain | %s | %s | %s · %s |' % (
            p['id'], p['title'], p.get('author') or '', p.get('dynasty') or '',
            year_cell(p), p.get('source') or '', p.get('form') or '',
            p.get('stage') or '', p.get('volume') or ''))
    return rows


def render(poems, content_version):
    head = [
        MARK_START,
        '',
        "> 本表由 `tools/gen-provenance.py` 从 `data/poems.json` 生成，共 %d 篇。" % len(poems),
        "> 改篇目后跑 `python tools/gen-provenance.py` 重新生成，不要手改这张表。",
        "> 「公有领域证据」一列就是 `validate.py` 第 8 项核验的那个年份。",
        '',
    ]
    tail = ['', MARK_END]
    return head + build_table(poems) + tail


def current_block(text):
    i = text.find(MARK_START)
    j = text.find(MARK_END)
    if i < 0 or j < 0 or j < i:
        return None
    return text[i:j + len(MARK_END)]


def run(check):
    content_version, poems = load_poems()
    if not PROVENANCE.exists():
        raise ProvenanceError('缺少 PROVENANCE.md')
    text = PROVENANCE.read_text(encoding='utf-8')
    block = current_block(text)
    new_block = '\n'.join(render(poems, content_version))
    if block is None:
        if check:
            raise ProvenanceError('PROVENANCE.md 里没有台账标记，跑 python tools/gen-provenance.py 生成')
        PROVENANCE.write_text(text.rstrip() + '\n\n' + new_block + '\n', encoding='utf-8')
        return len(poems), True
    same = block.strip() == new_block.strip()
    if not same:
        if check:
            raise ProvenanceError('台账与 data/poems.json 不一致，跑 python tools/gen-provenance.py 重新生成')
        text = text.replace(block, new_block)
        PROVENANCE.write_text(text, encoding='utf-8')
    return len(poems), not same


def selftest():
    problems = []
    good = [{'id': 'a', 'title': '甲', 'author': '李白', 'dynasty': '唐', 'authorDied': 762,
             'authorEraEnd': None, 'source': 'S3', 'form': '五言', 'stage': '小学', 'grade': 3, 'volume': '三年级上册'}]
    rows = build_table(good)
    if '卒 762' not in rows[2]:
        problems.append('正常篇目的卒年没进表')
    if 'public-domain' not in rows[2]:
        problems.append('版权列没填')

    # 坏样本：没有卒年证据的篇目必须报错，不能生成一张看起来完整的空表
    bad = [{'id': 'b', 'title': '乙', 'author': '某人', 'dynasty': '今',
            'authorDied': None, 'authorEraEnd': None, 'source': 'S1', 'form': '文言',
            'stage': '初中', 'grade': 8, 'volume': '八年级上册'}]
    try:
        build_table(bad)
        problems.append('缺卒年证据的篇目应当报错，却静默生成了表格')
    except ProvenanceError:
        pass

    # 公元前卒年要写成人话，不能写成「卒 -278」
    bc = [{'id': 'c', 'title': '丙', 'author': '屈原', 'dynasty': '战国', 'authorDied': -278,
           'authorEraEnd': None, 'source': 'S3', 'form': '杂言', 'stage': '高中', 'grade': 10, 'volume': '必修上册'}]
    if '公元前 278' not in build_table(bc)[2]:
        problems.append('公元前卒年写法不对')

    if problems:
        print('[!!] gen-provenance --selftest 失败：', file=sys.stderr)
        for x in problems:
            print('  - ' + x, file=sys.stderr)
        return 1
    print('[ok] gen-provenance --selftest 通过（卒年入表、缺证据报错、公元前写法都试到了）')
    return 0


def main():
    args = sys.argv[1:]
    if '--selftest' in args:
        sys.exit(selftest())
    check = '--check' in args
    try:
        n, changed = run(check)
    except ProvenanceError as e:
        print('[!!] ' + str(e), file=sys.stderr)
        sys.exit(1)
    if check:
        print('[ok] 台账与 poems.json 一致（%d 篇）' % n)
    else:
        print('[ok] 台账已生成：%d 篇%s' % (n, '（有更新）' if changed else '（无变化）'))


if __name__ == '__main__':
    main()
