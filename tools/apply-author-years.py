#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""丢词大作战 · 作者卒年注入脚本

把 data/authors.json 里的作者卒年写进 poems/**/*.md 的 frontmatter，
让「这篇为什么是公有领域」在每一篇上自带证据，而不是只在文档里口头承诺。

写入字段：
    authorDied: 762        作者卒年（公元年，公元前为负数）
    authorEraEnd: 1300     作者卒年不详时的年代上限（佚名、乐府、民歌等）

用法：
    python tools/apply-author-years.py            写入
    python tools/apply-author-years.py --check    只比对不写（CI 用）
    python tools/apply-author-years.py --selftest 自检：坏样本必须被抓到
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POEMS_DIR = ROOT / 'poems'
AUTHORS_JSON = ROOT / 'data' / 'authors.json'


class AuthorError(Exception):
    pass


def load_authors(path=AUTHORS_JSON):
    if not path.exists():
        raise AuthorError('找不到 ' + str(path))
    data = json.loads(path.read_text(encoding='utf-8'))
    authors = data.get('authors')
    if not isinstance(authors, dict) or not authors:
        raise AuthorError('authors.json 里没有 authors 对象')
    return authors


def expected_line(author, authors):
    """该篇 frontmatter 应有的那一行。作者不在表里直接报错，不静默跳过。"""
    entry = authors.get(author)
    if entry is None:
        raise AuthorError('作者 %s 不在 data/authors.json 里，先补表再入库' % author)
    died = entry.get('died')
    if died is None:
        era = entry.get('eraEnd')
        if not isinstance(era, int):
            raise AuthorError('作者 %s 的 eraEnd 不是整数' % author)
        return 'authorEraEnd: %d' % era, era
    if not isinstance(died, int):
        raise AuthorError('作者 %s 的 died 不是整数' % author)
    return 'authorDied: %d' % died, died


def frontmatter_bounds(lines):
    """返回 frontmatter 内容行的 (起, 止) 下标；找不到返回 None。"""
    if not lines or lines[0].strip() != '---':
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            return 1, i
    return None


def author_of(text):
    lines = text.split('\n')
    bounds = frontmatter_bounds(lines)
    if bounds is None:
        raise AuthorError('frontmatter 缺失或未闭合')
    for i in range(*bounds):
        if lines[i].startswith('author:'):
            return lines[i][len('author:'):].strip()
    raise AuthorError('frontmatter 里没有 author 行')


def inject(text, author, authors):
    """把卒年行写进 frontmatter，返回 (新文本, 是否有改动)。"""
    want, _ = expected_line(author, authors)
    lines = text.split('\n')
    bounds = frontmatter_bounds(lines)
    if bounds is None:
        raise AuthorError('frontmatter 缺失或未闭合')
    start, end = bounds
    pat = re.compile(r'^(authorDied|authorEraEnd):\s*(.*)$')
    found = None
    for i in range(start, end):
        if pat.match(lines[i]):
            if found is not None:
                raise AuthorError('frontmatter 里同时出现 authorDied 与 authorEraEnd')
            found = i
    anchor = None
    for i in range(start, end):
        if lines[i].startswith('dynasty:'):
            anchor = i
            break
    if anchor is None:
        for i in range(start, end):
            if lines[i].startswith('author:'):
                anchor = i
                break
    if anchor is None:
        raise AuthorError('frontmatter 里没有 author/dynasty 行，不知道往哪儿插')
    if found is not None:
        if lines[found] == want:
            return text, False
        lines[found] = want
        return '\n'.join(lines), True
    lines.insert(anchor + 1, want)
    return '\n'.join(lines), True


def poem_files(root=POEMS_DIR):
    # 索引.md 是自动生成的导航页，没有 frontmatter，不是篇目（与 build.py 同一口径）
    return sorted(p for p in root.rglob('*.md') if p.is_file() and p.name != '索引.md')


def run(check):
    authors = load_authors()
    changed, checked, problems = 0, 0, []
    for p in poem_files():
        text = p.read_text(encoding='utf-8')
        try:
            author = author_of(text)
            new, dirty = inject(text, author, authors)
        except AuthorError as e:
            problems.append('%s：%s' % (p.relative_to(ROOT), e))
            continue
        checked += 1
        if dirty:
            if check:
                problems.append('%s：卒年行缺失或过期，应为 %s'
                                % (p.relative_to(ROOT), expected_line(author, authors)[0]))
            else:
                p.write_text(new, encoding='utf-8')
                changed += 1
    return checked, changed, problems


GOOD = '---\nauthor: 李白\ndynasty: 唐\nlicense: public-domain\n---\n\n# 静夜思\n'


def selftest():
    problems = []
    authors = {'李白': {'died': 762}, '佚名': {'died': None, 'eraEnd': 1300}}

    new, dirty = inject(GOOD, '李白', authors)
    if 'authorDied: 762' not in new or not dirty:
        problems.append('正常注入失败：没写进 authorDied: 762')

    new2, dirty2 = inject(new, '李白', authors)
    if dirty2:
        problems.append('重复运行应当幂等，却报告有改动')

    # 坏样本 1：卒年过期必须被纠正
    stale = '---\nauthor: 李白\nauthorDied: 9999\ndynasty: 唐\n---\n'
    new3, dirty3 = inject(stale, '李白', authors)
    if not dirty3 or 'authorDied: 762' not in new3:
        problems.append('过期卒年没被纠正')

    # 坏样本 2：作者不在表里必须报错（防止有人把仍在保护期的作品塞进来）
    try:
        inject('---\nauthor: 冰心\n---\n', '冰心', authors)
        problems.append('表里没有的作者应当报错，却静默通过了')
    except AuthorError:
        pass

    # 坏样本 3：frontmatter 未闭合必须报错
    try:
        inject('---\nauthor: 李白\n', '李白', authors)
        problems.append('frontmatter 未闭合应当报错')
    except AuthorError:
        pass

    # 佚名走 eraEnd
    new4, _ = inject('---\nauthor: 佚名\ndynasty: 宋\n---\n', '佚名', authors)
    if 'authorEraEnd: 1300' not in new4:
        problems.append('佚名应当写 authorEraEnd，实得：' + new4)

    if problems:
        print('[!!] apply-author-years --selftest 失败：', file=sys.stderr)
        for x in problems:
            print('  - ' + x, file=sys.stderr)
        return 1
    print('[ok] apply-author-years --selftest 通过（注入、幂等、过期卒年纠正、'
          '缺作者报错、frontmatter 未闭合报错、佚名走 eraEnd 都试到了）')
    return 0


def main():
    args = sys.argv[1:]
    if '--selftest' in args:
        sys.exit(selftest())
    check = '--check' in args
    try:
        checked, changed, problems = run(check)
    except AuthorError as e:
        print('[!!] ' + str(e), file=sys.stderr)
        sys.exit(1)
    if problems:
        print('[!!] 作者卒年校验失败（%d 条）：' % len(problems), file=sys.stderr)
        for x in problems[:40]:
            print('  - ' + x, file=sys.stderr)
        sys.exit(1)
    if check:
        print('[ok] %d 篇的卒年行与 authors.json 一致' % checked)
    else:
        print('[ok] %d 篇已核对，写入 %d 篇' % (checked, changed))


if __name__ == '__main__':
    main()
