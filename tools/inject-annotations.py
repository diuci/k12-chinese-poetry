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


def render_value(val):
    """注释是列表（一行一条），译文赏析是字符串。渲染规则只许有一份。"""
    return val if isinstance(val, str) else '\n'.join('- ' + x for x in val)


def missing_fields(a):
    """这一篇的注释内容缺哪几样。空字符串、空列表都算缺——不许「有键」就算有内容。"""
    return [FIELD[k] for k in ORDER if not a.get(k)]


def count_section(body, sec):
    """body 里 '## <sec>' 出现几次。注入必须幂等：跑两遍不许长出第二个小节。"""
    return len(re.findall(r'^##\s*' + re.escape(sec) + r'\s*$', body, re.M))


def selftest():
    """注入器直接改 252 个 md。它一旦把正文覆盖掉、或者跑两遍长出两节，
    下游四个仓读到的就是坏数据，而构建、链接检查全都照样绿。"""
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    body0 = ('# 测试篇\n\n> 佚名 · 先秦\n\n床前明月光，疑是地上霜。\n\n'
             '## 注释\n\n- （待补：字词注释）\n\n## 译文\n\n（待补：白话译文）\n\n'
             '## 赏析\n\n（待补：文学常识与赏析）\n')

    # 坏例1：替换已有的注释节，正文与别的小节一个字不许动
    b1, ok1 = replace_section(body0, '注释', '- 床：卧具。')
    must(ok1 and '床：卧具。' in b1 and '（待补：字词注释）' not in b1, '坏例1：注释节没被替换')
    must('床前明月光，疑是地上霜。' in b1, '坏例1b：正文被注入器动了')
    must('## 译文' in b1 and '## 赏析' in b1, '坏例1c：别的小节被弄丢了')

    # 坏例2：小节不存在时插入，不许插到正文之前（正文起点护栏会拦，但注入器自己不许造）
    body_no_sec = '# 测试篇\n\n床前明月光。\n\n## 注释\n\n- 床：卧具。\n'
    b2, ok2 = replace_section(body_no_sec, '译文', '月光洒在床前。')
    must(ok2 and '## 译文' in b2, '坏例2：缺失的小节没被插入')
    must(b2.index('床前明月光') < b2.index('## 译文'), '坏例2b：新小节插到了正文之前')

    # 坏例3：完全没有小节时追加，不许报错
    b3, ok3 = replace_section('# 测试篇\n\n床前明月光。\n', '注释', '- 床：卧具。')
    must(ok3 and '## 注释' in b3 and '床前明月光' in b3, '坏例3：没有小节时追加失败')

    # 坏例4：幂等——同一份内容注入两遍，不许长出第二个同名小节
    b4a, _ = replace_section(body0, '注释', '- 床：卧具。')
    b4b, _ = replace_section(b4a, '注释', '- 床：卧具。')
    must(count_section(b4b, '注释') == 1, '坏例4：注入两遍长出两个「## 注释」（实际 %d 个）' % count_section(b4b, '注释'))
    must(count_section(b4b, '译文') == 1, '坏例4b：注入注释把「## 译文」挤成了两个')

    # 坏例5：替换不许越界吃掉下一节
    b5, _ = replace_section(body0, '注释', '- 床：卧具。')
    must(b5.index('## 译文') > b5.index('## 注释'), '坏例5：替换吃掉了下一节的起点')
    must('（待补：白话译文）' in b5, '坏例5b：下一节的内容被顺手改掉了')

    # 坏例6：空字符串、空列表都算「缺内容」，不许「有键」就算有内容
    must(missing_fields({'note': [], 'trans': '', 'appr': '有'}) == ['注释', '译文'],
         '坏例6：空的注释/译文没被算成缺内容')
    must(missing_fields({'note': ['床：卧具。'], 'trans': '译文', 'appr': '赏析'}) == [],
         '坏例6b：三样齐全却被报了')

    # 坏例7：渲染规则——注释一行一条，译文原样
    must(render_value(['床：卧具。', '疑：好像。']) == '- 床：卧具。\n- 疑：好像。',
         '坏例7：注释列表没渲染成一行一条')
    must(render_value('月光洒在床前。') == '月光洒在床前。', '坏例7b：字符串被改动了')

    # 坏例8：frontmatter 读不出来必须返回 None（不许静默当成「没有正文」）
    must(read_parts('# 没有 frontmatter\n\n正文。\n') is None, '坏例8：没有 frontmatter 却没报错')
    parts = read_parts('---\nid: a\n---\n# 测试篇\n\n正文。\n')
    must(parts and parts[1].startswith('# 测试篇'), '坏例8b：frontmatter 与正文没切开')

    # 坏例9：内容库比 md 旧——注入必须被看得见（本轮真实踩过：注入把 屈原列传 的注释改回旧版，
    # 把已经裁定删掉的「睠顾楚国」放回正文，审计当场报红）
    _b9 = '# 测试篇\n\n床前明月光。\n\n## 注释\n\n- 眷顾：眷恋牵挂。仓内旧作「睠顾」，出入写在「异文」那一节。\n\n## 译文\n\n月光洒在床前。\n\n## 赏析\n\n二十字。\n'
    _e9 = {'note': ['「睠顾楚国」：睠，同「眷」。'], 'trans': '月光洒在床前。', 'appr': '二十字。'}
    must(body_would_change(_b9, _e9), '坏例9：内容库与 md 不一致却没被看出来（注入会悄悄把正文改回旧文本）')
    must('睠顾楚国' in injected_body(_b9, _e9), '坏例9a：没复现出「旧文本被写回正文」这件事')
    # 坏例9b：一致就不许报（否则 --verify 天天红，等于没有）
    _e9b = {'note': ['眷顾：眷恋牵挂。仓内旧作「睠顾」，出入写在「异文」那一节。'], 'trans': '月光洒在床前。', 'appr': '二十字。'}
    must(not body_would_change(_b9, _e9b), '坏例9b：内容库与 md 一致却被判成会改动')
    # 坏例9c：内容库里某一项是空的，那一节不许被动（不许把已有正文清空）
    _e9c = {'note': ['眷顾：眷恋牵挂。'], 'trans': '', 'appr': '二十字。'}
    must('月光洒在床前。' in injected_body(_b9, _e9c), '坏例9c：内容库里的空译文把 md 的译文清掉了')

    # 坏例10：内容库里的值带 \r——从 md 抽小节时只按 \n 切，行尾回车就留在值里。
    # 本轮真实踩过：把 md 的小节抽回内容库，四篇的值全带 \r，注入会把整节行尾改掉；
    # 内容一个字没变，文件却被重写。这种改动 diff 里全是行尾，最容易看漏。
    must(store_problems({'a': {'note': ['甲\r乙'], 'trans': '丙', 'appr': '丁'}}) != [],
         '坏例10：内容库带 \\r 却没报错')
    must(store_problems({'a': {'note': ['甲'], 'trans': '丙', 'appr': '丁'}}) == [],
         '坏例10b：干净的内容库被误伤')
    _n10 = len(store_problems({'a': {'note': ['甲\r'], 'trans': '丙\r', 'appr': '丁'}}))
    must(_n10 == 2, '坏例10c：两处带 \\r 只报了 %d 处' % _n10)
    must(len(store_problems({'a': {'note': ['甲\r']}, 'b': {'appr': '丁\r'}})) == 2, '坏例10d：跨篇的 \\r 只报了 %d 处' % len(store_problems({'a': {'note': ['甲\r']}, 'b': {'appr': '丁\r'}})))
    print('[ok] inject-annotations --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


def body_would_change(body, entry):
    """注入会不会改动这一篇的正文。只比内容，不比空行。

    为什么不比空行：md 是手改出来的，有的篇目「## 注释」下面多一个空行；注入写的是规范形状。
    空行差异不是内容差异——把它报成「会改动」，这条检查天天红，等于没有。
    真正要抓的是：内容库里存的是旧文本，注入把 md 里已经改好的注释、译文、赏析换回旧版。"""
    def norm(s):
        return re.sub(r'\n{3,}', '\n\n', (s or '').strip())
    new = injected_body(body, entry)
    for sec in FIELD.values():
        pat = re.compile(r'^##\s*' + re.escape(sec) + r'\s*\n(.*?)(?=^##\s|\Z)', re.M | re.S)
        a = pat.search(body)
        b = pat.search(new)
        if norm(a.group(1) if a else '') != norm(b.group(1) if b else ''):
            return True
    return norm(new) != norm(body)


def injected_body(body, entry):
    """按内容库把 注释/译文/赏析 三节写进 body，返回写完之后的样子（不落盘）。"""
    out = body
    for k in ORDER:
        val = entry.get(k)
        if not val:
            continue
        out, _ = replace_section(out, FIELD[k], render_value(val))
    return out


def store_problems(ann):
    """内容库自己得先过一遍：值里不许带 \\r。"""
    out = []
    for pid in sorted(ann):
        for k, val in (ann[pid] or {}).items():
            txt = '\n'.join(val) if isinstance(val, list) else (val or '')
            if '\r' in txt:
                out.append('%s: 内容库里的 %s 带 \\r（从 md 抽小节时只按 \\n 切，行尾回车留在了值里），注入会把整节的行尾改掉' % (pid, FIELD.get(k, k)))
    return out


def main():
    check = '--check' in sys.argv
    verify = '--verify' in sys.argv
    ann = load_annotations()
    print('=== 注释/译文/赏析 注入 ===')
    print('已载入内容 %d 条（来自 %s）' % (len(ann), CONTENT.name if CONTENT.exists() else '缺失'))
    print('')

    written = 0
    covered = 0
    missing = []
    problems = []
    problems.extend(store_problems(ann))

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
        body_before = body
        body = injected_body(body_before, a)
        changed = (body != body_before)
        # --verify：内容库与 md 不一致时当场报红。本轮真实踩过——内容库里存的是旧注释，
        # 注入把 屈原列传 的注释改回旧版，把已经裁定删掉的「睠顾楚国」放回正文，审计当场报红。
        # 没有这一条，注入就是一只随时能把正文改回旧文本的手，而且改完没人知道。
        if verify and body_would_change(body_before, a):
            problems.append('%s(%s): 注入会改动这一篇——内容库与 md 不一致，注入会把 md 改回内容库里那份' % (pid, pf.name))
        for name in missing_fields(a):
            problems.append('%s(%s): %s 缺内容' % (pid, pf.name, name))
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
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    main()
