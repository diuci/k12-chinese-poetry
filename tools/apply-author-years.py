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


def justified(found_line, want, authors):
    """篇上已经写着的年代上限，满足下面任一条就算有依据，不许被表的通用值覆盖：

      1. 比表里的上限更早（更保守）。《十五从军征》写 220（汉乐府），
         表里给「佚名」的通用上限是 1900 —— 220 更安全，照表硬写反而把它放宽了。
      2. 这个年代能在作者表里找到出处。《古代文论选段》收《人间词话》，
         上限必须是王国维卒年 1927；写 1900 就是编出一句假话。

    两条都不满足的（比表晚、表里又查不到这个年代）照样要报问题。"""
    if found_line.strip() == want.strip():
        return True
    m = re.match(r'^authorEraEnd:\s*(-?\d+)$', found_line.strip())
    if not m:
        return False
    got = int(m.group(1))
    wm = re.match(r'^author(?:Died|EraEnd):\s*(-?\d+)$', want.strip())
    if wm and got <= int(wm.group(1)):
        return True
    for entry in authors.values():
        for key in ('died', 'eraEnd'):
            if entry.get(key) == got:
                return True
    return False


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
        if justified(lines[found], want, authors):
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

    # 坏样本 4：上限比表晚、作者表里又查不到这个年代 —— 必须被纠正
    bogus = '---\nauthor: 佚名\nauthorEraEnd: 2500\ndynasty: 宋\n---\n'
    new5, dirty5 = inject(bogus, '佚名', authors)
    if not dirty5 or 'authorEraEnd: 1300' not in new5:
        problems.append('没有依据的年代上限（2500）没被纠正')

    # 坏样本 5：比表更保守的上限不许被表的通用值放宽
    safer = '---\nauthor: 佚名\nauthorEraEnd: 220\ndynasty: 汉\n---\n'
    new6, dirty6 = inject(safer, '佚名', authors)
    if dirty6 or 'authorEraEnd: 220' not in new6:
        problems.append('更保守的上限 220 被表的通用值改掉了')

    # 坏样本 6：作者表里查得到的年代（王国维 1927）就是依据，不许改
    authors2 = dict(authors)
    authors2['王国维'] = {'died': 1927}
    sel = '---\nauthor: 佚名\nauthorEraEnd: 1927\ndynasty: 先秦\n---\n'
    new7, dirty7 = inject(sel, '佚名', authors2)
    if dirty7 or 'authorEraEnd: 1927' not in new7:
        problems.append('作者表里查得到的 1927 被误改')

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
          '缺作者报错、frontmatter 未闭合报错、佚名走 eraEnd、'
          '无依据上限被纠正、更保守上限被保留、表里查得到的年代被保留 都试到了）')
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
