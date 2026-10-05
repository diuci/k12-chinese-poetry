# -*- coding: utf-8 -*-
"""把注释/译文/赏析注入 poems/*.md。

为什么单独一个工具：内容（253 篇）和文件编辑（253 个 md）必须解耦。
内容放在 content/annotations/*.json 里按 id 索引，写错了只改 json，
不会把正文或 frontmatter 碰坏；注入是幂等的，可以反复跑。

格式（content/annotations/<stage>.json）：

    {
      "jingyesi": {
        "note": ["床：睡床。", "疑：好像、仿佛。"],
        "trans": "明亮的月光洒在床前……",
        "appr": "全诗二十字……"
      }
    }

- note  是「词：释义」的列表，只收**孩子真会卡住**的字词，不逐字解释
- trans 逐联一行，用全角标点
- appr  说形式、意象、手法、情感；不编造出处轶闻

用法：
    python tools/inject-annotations.py            # 注入已有内容
    python tools/inject-annotations.py --check    # 只体检不写
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POEMS = ROOT / 'poems'
CONTENT = ROOT / 'content' / 'annotations'

CJK = re.compile(r'[\u4e00-\u9fff]')
PLACEHOLDER = {
    'note': '- （待补：字词注释）',
    'trans': '（待补：白话译文）',
    'appr': '（待补：文学常识与赏析）',
}
FIELD = {'note': '注释', 'trans': '译文', 'appr': '赏析'}
ORDER = ['note', 'trans', 'appr']


def load_annotations():
    data = {}
    if not CONTENT.exists():
        return data
    for f in sorted(CONTENT.glob('*.json')):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception as e:
            print('!! %s 解析失败: %s' % (f.name, e))
            continue
        for k, v in d.items():
            data[k] = v
    return data


def poem_files():
    # poems/索引.md 是 gen-index.py 自动生成的目录，不是诗，没有 frontmatter
    return sorted(f for f in POEMS.rglob('*.md') if f.name != '索引.md')


def read_parts(text):
    """拆成 frontmatter / body，并在 body 里定位注释、译文、赏析三节。"""
    m = re.match(r'^(---\s*\n.*?\n---\s*\n)(.*)$', text, re.S)
    if not m:
        return None
    return m.group(1), m.group(2)


def replace_section(body, sec, new_text):
    """替换（或插入）body 里的 '## <sec>' 一节。返回 (body, ok)。"""
    pat = re.compile(r'(^##\s*' + re.escape(sec) + r'\s*\n)(.*?)(?=^##\s|\Z)',
                     re.M | re.S)
    block = '## %s\n\n%s\n\n' % (sec, new_text)
    if pat.search(body):
        return pat.sub(lambda _m: block, body, count=1), True
    # 插到最后一个 '## ' 之前；没有就追加
    heads = list(re.finditer(r'^##\s', body, re.M))
    if heads:
        at = heads[-1].start()
        return body[:at] + block + body[at:], True
    return body.rstrip() + '\n\n' + block, True


def main():
    check = '--check' in sys.argv
    ann = load_annotations()
    print('=== 注释/译文/赏析 注入 ===')
    print('已载入内容 %d 条（来自 %s）' % (len(ann), CONTENT.name if CONTENT.exists() else '缺失'))
    print('')

    written = 0
    covered = 0
    missing = []
    problems = []

    for pf in poem_files():
        text = pf.read_text(encoding='utf-8')
        parts = read_parts(text)
        if not parts:
            problems.append('%s: frontmatter 解析失败' % pf.name)
            continue
        head, body = parts

        pid = None
        mi = re.search(r'^id:\s*(\S+)\s*$', head, re.M)
        if mi:
            pid = mi.group(1)
        if pid not in ann:
            missing.append(pid or pf.name)
            continue

        a = ann[pid]
        changed = False
        for k in ORDER:
            val = a.get(k)
            if not val:
                problems.append('%s(%s): %s 缺内容' % (pid, pf.name, FIELD[k]))
                continue
            txt = val if isinstance(val, str) else '\n'.join('- ' + x for x in val)
            if PLACEHOLDER[k] in body and txt not in body:
                changed = True
            body, _ = replace_section(body, FIELD[k], txt)
        if changed or (not check and PLACEHOLDER['note'] not in body):
            if not check:
                pf.write_text(head + body, encoding='utf-8')
                written += 1
        covered += 1

    total = len(poem_files())
    print('诗篇 %d，已有内容 %d，还缺 %d' % (total, covered, len(missing)))
    if missing:
        print('  尚无内容（前 10）: %s' % ', '.join(missing[:10]))
    if problems:
        print('  问题:')
        for p in problems[:10]:
            print('    ' + p)
    print('写入 %d 个文件' % written)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
