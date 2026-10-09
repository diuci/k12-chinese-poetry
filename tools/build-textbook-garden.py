#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""语文园地收录表：把「藏在语文园地里的古诗文」从园地页面上取下来。

为什么要有这张表：仓里 53 篇被判成「教材里没有这篇」（data/textbook-attestations.json）。
其中一批（咏鹅、古朗月行、悯农其二……）其实统编教材收了，只是不收在第几课，
收在「语文园地」里。按课文目录去找当然找不到——于是站点会告诉学生「教材没有这一课」，
而教材明明有。这一条要是错了，是要误导人备考的。

来源地位（见 docs/sources.md）：
  - 园地页与课文目录页同源（第三方镜像 yw.suyang123.com），所以这张表本身只是**一条来源**；
  - 它只证明「这一册的语文园地页面上出现了这一篇」，不证明它属于哪个栏目
    （页面上《咏鹅》排在「字词句运用」之后，栏目归属页面上看不出来，就不写）；
  - 教材的注释、译文、赏析一个字不进仓。
判定要等第二条独立来源；这张表先把「镜像确实收了」这件事登记下来，
让「教材里没有」这一档不再把这类篇目一并抹掉。

用法：
  python tools/build-textbook-garden.py            # 生成/刷新 data/textbook-garden.json
  python tools/build-textbook-garden.py --refresh  # 重抓页面
  python tools/build-textbook-garden.py --selftest # 坏例子自检（不联网）
"""
import json
import re
import sys
import time
import importlib.util
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

_spec = importlib.util.spec_from_file_location('checktextbook', ROOT / 'tools' / 'check-textbook.py')
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

OUT = ROOT / 'data' / 'textbook-garden.json'

# 园地页上的栏目头与篇名同一个标签，靠「《…》原文朗读」区分：
#   <h2 class="tit">《语文园地一 · 识字加油站》原文朗读</h2>   ← 栏目头，不是一篇
#   <h2 class="tit">《咏鹅》原文朗读</h2> <p class="author">作者：[唐代] 骆宾王</p>
# 尾巴塞不得太贪：上一栏目的尾巴把下一篇的标题吞掉，finditer 就跳过了那一篇（自检当场抓到过）。
TIT = re.compile(r'<h2\s+class="tit"[^>]*>\s*《([^》]{1,40})》\s*原文朗读\s*</h2>')
AUTHOR = re.compile(r'<p\s+class="author"[^>]*>\s*作者：\s*([^<]{1,40})</p>')
CJK = re.compile(r'[\u4e00-\u9fff]')
NAV_JUNK = ('语文朗读', '英语点读', '数学口算', '名师视频', '名校真题', '首页', '拼音版',
            '朗读', '译文', '注释', '赏析', '写字表', '识字表', '词语表', '资料宝', '同步课堂')


def is_section(title):
    """栏目头：「语文园地一 · 识字加油站」这种，不是一篇诗文。"""
    return '语文园地' in title or '·' in title


HEAD = re.compile(r'<h2\s+class="tit"[^>]*>\s*《([^》]{1,40})》\s*原文朗读\s*</h2>')


def garden_headers(html):
    """这一页上所有《…》原文朗读的标题（栏目头与篇名同一个标签）。"""
    out = []
    for m in HEAD.finditer(html):
        t = re.sub(r'\s+', '', m.group(1))
        if t and CJK.search(t) and not any(j in t for j in NAV_JUNK):
            out.append(t)
    return out


def garden_items(html):
    """从一页园地页里取出（栏目, 篇名, 作者原文）。纯函数，坏例子直接喂进来。"""
    out, section = [], ''
    for m in TIT.finditer(html):
        title = re.sub(r'\s+', '', m.group(1))
        # 作者只在这一篇自己的范围内找：下一个栏目标签之前
        nxt = html.find('<h2', m.end())
        stop = m.end() + 220
        if nxt >= 0 and nxt < stop:
            stop = nxt
        tail = html[m.end():stop]
        if not title or not CJK.search(title):
            continue
        if any(j in title for j in NAV_JUNK):
            continue
        if is_section(title):
            section = title
            continue
        am = AUTHOR.search(tail)
        out.append((section, title, (am.group(1).strip() if am else '')))
    return out


def build(refresh=False):
    data = {'note': '统编教材「语文园地」收录表。园地页与课文目录页同源（第三方镜像），'
                    '所以这张表只是一条来源：它证明「这一册的语文园地页面上出现了这一篇」，'
                    '不证明栏目归属，也不单独作为「教材收了」的判定。'
                    '教材的注释、译文、赏析不进仓。',
            'generated': time.strftime('%Y-%m-%d'),
            'source': T.BASE,
            'volumes': {},
            'summary': {}}
    total = vols = sections_only = 0
    problems = []
    for vol, path in T.VOLUMES.items():
        try:
            index = T.volume_index(path, refresh)
        except Exception as exc:
            problems.append('%s 目录页取不到：%s' % (vol, type(exc).__name__))
            continue
        gardens = [(name, url) for name, url in index if '语文园地' in name]
        if not gardens:
            continue
        rows = []
        for gname, gurl in gardens:
            try:
                html = T.cached(gurl, refresh)
            except Exception as exc:
                problems.append('%s %s 园地页取不到：%s' % (vol, gname, type(exc).__name__))
                continue
            items = garden_items(html)
            heads = garden_headers(html)
            if not items and not heads:
                # 整页一个《…》原文朗读都没有 = 页面改版或抽取失效。静默产出空表最危险。
                problems.append('%s %s 这一页连一个《…》原文朗读都没有（页面改版？）' % (vol, gname))
                continue
            if not items:
                # 只有栏目头：日积月累的内容在段落里，页面上没把篇名单独标出来。
                # 这一档要登记，不许静默丢掉——它说明「这一页查过，篇名没标出来」。
                rows.append({'garden': gname, 'status': 'sections-only',
                             'sections': heads, 'url': gurl})
                continue
            for section, title, author in items:
                row = {'garden': gname, 'title': title, 'url': gurl}
                if section:
                    row['section'] = section
                if author:
                    row['authorRaw'] = author
                rows.append(row)
        if not rows:
            continue
        data['volumes'][vol] = rows
        total += sum(1 for r in rows if r.get('title'))
        sections_only += sum(1 for r in rows if r.get('status') == 'sections-only')
        vols += 1
    data['summary'] = {'volumesWithGarden': vols, 'items': total, 'sectionsOnlyPages': sections_only}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data, problems


def selftest():
    """坏例子：抽取失效、栏目头被当成一篇、导航词被当成篇名、作者混进篇名、好例子不误伤。"""
    tried = [0]
    def must(cond, msg):
        tried[0] += 1
        if not cond:
            print('[!!] 坏例子没抓住：' + msg)
            return False
        return True
    ok = True
    good = ('<h2 class="tit">《语文园地一 · 识字加油站》原文朗读</h2>'
            '<p class="text-wrap">一片两片三四片，</p>'
            '<h2 class="tit">《咏鹅》原文朗读</h2> <p class="author">作者：[唐代] 骆宾王</p>'
            '<h3 class="tit">拼音版</h3>'
            '<h2 class="tit">《剪窗花》原文朗读</h2>')
    got = garden_items(good)
    titles = [g[1] for g in got]
    ok &= must(titles == ['咏鹅', '剪窗花'], '好例子应当只抽到两篇，抽到 %s' % titles)
    ok &= must(got[0][2] == '[唐代] 骆宾王', '作者没取到：%r' % got[0][2])
    # 栏目名里的空格被去掉（与仓里其它地方同一口径）：断言要按工具真正该产出的样子写
    ok &= must(got[0][0] == '语文园地一·识字加油站', '栏目没跟住：%r' % got[0][0])
    # 1) 栏目头被当成一篇
    ok &= must(garden_items('<h2 class="tit">《语文园地二 · 日积月累》原文朗读</h2>') == [],
               '栏目头被当成了一篇')
    # 2) 导航词被当成篇名
    ok &= must(garden_items('<h2 class="tit">《语文朗读宝》原文朗读</h2>') == [],
               '导航词被当成了篇名')
    # 3) 没有篇名的页（改版）必须抽到 0 条，让 build 报错
    ok &= must(garden_items('<div class="tit-box"><h3>换了标签</h3></div>') == [],
               '改版页应当抽到 0 条（这样 build 才会报「没抽到任何一篇」）')
    # 4) 作者行不许混进篇名
    ok &= must(garden_items('<h2 class="tit">《静夜思》原文朗读</h2><p class="author">作者：[唐代] 李白</p>')[0][1] == '静夜思',
               '作者串进了篇名')
    # 5) 非汉字标题
    ok &= must(garden_items('<h2 class="tit">《ABC》原文朗读</h2>') == [], '非汉字标题被收进来了')
    # 6) 真产物：一年级上册那份必须有咏鹅
    real = json.loads(OUT.read_text(encoding='utf-8')) if OUT.exists() else None
    if real is None:
        print('     （data/textbook-garden.json 还没生成，真产物那一条没跑）')
    else:
        y1 = [r['title'] for r in real['volumes'].get('一年级上册', [])]
        ok &= must('咏鹅' in y1, '真产物里一年级上册没有咏鹅（抽取失效？）')
    if not ok:
        return 1
    print('[ok] build-textbook-garden --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


def main():
    if '--selftest' in sys.argv:
        return selftest()
    data, problems = build(refresh='--refresh' in sys.argv)
    print('[ok] 语文园地收录表：有园地的册 %d 册 / 标出篇名的条目 %d 条 / 只有栏目头的页 %d 页 → %s' % (
        data['summary']['volumesWithGarden'], data['summary']['items'],
        data['summary']['sectionsOnlyPages'], OUT))
    if problems:
        for p in problems[:20]:
            print('  !! ' + p)
        print('     共 %d 条问题' % len(problems))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
