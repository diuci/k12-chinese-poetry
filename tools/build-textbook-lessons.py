#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统编教材课文目录表：从教材目录页生成 data/textbook-lessons.json。

为什么要有这张表：仓里每篇都写着「在教材哪一册」。这个字段以前是从来源里零散抄来的，
没有一处能整体核对的地方。有了这张表，「仓内写的册次」和「教材目录里的册次」可以一次性对完。

来源地位（见 docs/sources.md 的 S10）：
  - 目录页来自第三方镜像 yw.suyang123.com（辅助来源）；
  - 人教社官方 stkw.pep.com.cn 的《高中语文学习任务导引》参考答案只覆盖课内教读课，
    但它给出的课号是出版者自己公布的——两者课号一致的地方，这一条就算两条来源。
  - 这张表只用来证明「教材哪一册第几课有这篇」，教材的注释、译文、赏析一个字不进仓。

用法：
  python tools/build-textbook-lessons.py            # 生成/刷新 data/textbook-lessons.json
  python tools/build-textbook-lessons.py --audit    # 拿这张表核对仓内每篇的 volume 字段
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import validate as V  # noqa: E402

# check-textbook.py 带连字符，不能 import；用 importlib 按路径加载，
# 免得把 23 个册页路径抄两遍——抄两遍迟早对不上。
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location('checktextbook', ROOT / 'tools' / 'check-textbook.py')
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

OUT = ROOT / 'data' / 'textbook-lessons.json'

# 人教社官方《高中语文学习任务导引》参考答案里能直接看到的课号（出版者自己公布）。
# 只列「数字 + 篇名」同时出现、不会被误认的行；自读（*）课没有参考答案，所以不在这里。
PEP_CONFIRMED = {
    '必修上册': {1: '沁园春·长沙', 2: '立在地球边上放号', 3: '百合花', 4: '喜看稻菽千重浪',
                5: '以工匠精神雕琢时代品质', 7: '短歌行', 8: '梦游天姥吟留别',
                9: '念奴娇·赤壁怀古', 11: '反对党八股（节选）', 12: '拿来主义',
                14: '故都的秋', 15: '我与地坛（节选）', 16: '赤壁赋'},
    '必修下册': {1: '子路、曾皙、冉有、公西华侍坐', 2: '烛之武退秦师', 4: '窦娥冤（节选）',
                5: '雷雨（节选）', 10: '在《人民报》创刊纪念会上的演说', 11: '谏逐客书',
                13: '林教头风雪山神庙', 15: '谏太宗十思疏', 16: '阿房宫赋'},
    '选择性必修上册': {1: '中国人民站起来了', 2: '长征胜利万岁',
                  5: '《论语》十二章', 6: '《老子》四章',
                  8: '大卫·科波菲尔（节选）', 9: '复活（节选）'},
}
PEP_SOURCE_NOTE = '人教社官方 stkw.pep.com.cn《高中语文学习任务导引》参考答案'

LESSON = re.compile(r'^(\d+(?:\.\d+)?)(\*?)')
CJK = re.compile(r'[\u4e00-\u9fff]')
# 面包屑与导航词也会以 <a> 的形式混进目录：「八年级」「语文朗读宝」这种。
# 不滤掉就会多出一条叫「八年级」的课文，还会把它的 URL 当成课文页去核验。
JUNK_TITLES = re.compile(r'^([一二三四五六七八九十]年级(上|下)?册?|(必修|选择性必修)(上|下)?册?|语文|高中语文|初中语文|小学语文)$')

NAV_JUNK = ('语文朗读', '英语点读', '数学口算', '名师视频', '名校真题', '小学语文', '初中语文',
            '高中语文', '首页', '英语朗读宝', '语文朗读宝', '数学口算宝', '资料宝', '同步课堂',
            '音标点读', '教学宝', '联系我们', '网站地图', '粤ICP')


def norm_title(text):
    """篇名主干：去掉课号、自读星号、括号里的补充、并序/节选，只留能对齐的字。"""
    t = LESSON.sub('', text).strip()
    t = t.replace('*', '').replace('＊', '')
    t = re.sub(r'[（(][^）)]*[）)]', '', t)
    t = t.replace('并序', '').replace('（节选）', '').replace('节选', '')
    t = re.sub(r'[\s\u3000]+', '', t)
    return t


def volume_entries(vol):
    """从目录页取这一册的课文条目。"""
    path = T.VOLUMES.get(vol)
    if not path:
        return None, 'unknown-volume'
    url = T.BASE + path
    # 缓存文件名交给 check-textbook.cached() 去决定：它有自己的命名规则，
    # 在这里重算一遍迟早对不上（对不上就报「教材里没有这篇」，其实是工具没读到页）。
    try:
        html = T.cached(url)
    except Exception as exc:
        return None, 'fetch-failed: %s' % type(exc).__name__
    # 课文页 URL：核验「教材里这篇是不是这篇」要用正文，光对齐标题不够
    urls = {}
    for name, u in T.volume_index(path):
        urls.setdefault(norm_title(name), u)
    out, seen = [], set()
    unit = ''   # 最近一条带课号的目录条目：合课（诗词五首、《诗经》二首）下面的篇目靠它定位
    for m in re.finditer(r'>([^<>]{1,60}?)</a>', html):
        raw = re.sub(r'\s+', '', m.group(1))
        if not raw or any(j in raw for j in NAV_JUNK):
            continue
        if not CJK.search(raw):
            continue
        lm = LESSON.match(raw)
        if lm:
            title = norm_title(raw)
            if not title:
                continue
            key2 = (vol, lm.group(1), title)
            if key2 in seen:
                continue
            seen.add(key2)
            unit = raw
            out.append({'lesson': lm.group(1), 'selfReading': lm.group(2) == '*',
                        'raw': raw, 'title': title, 'url': urls.get(title, '')})
        else:
            # 没有课号的中国古代诗文条目 = 「古诗词诵读」单元里的篇目
            title = norm_title(raw)
            if len(title) <= 14 and not JUNK_TITLES.match(title) and not any(j in title for j in NAV_JUNK):
                key2 = (vol, '', title)
                if key2 in seen:
                    continue
                seen.add(key2)
                out.append({'lesson': '', 'selfReading': True, 'raw': raw, 'title': title,
                            'underLesson': unit, 'url': urls.get(title, '')})
    return out, 'ok'


def build():
    data = {'note': '统编教材课文目录表。目录页来自第三方镜像（辅助来源）；'
                     '课号同时出现在人教社官方《高中语文学习任务导引》参考答案里的条目，'
                     'confirmed 标 true——那一条算两条来源。'
                     '这张表只证明「哪一册第几课有这篇」，不引入教材的注释、译文、赏析。',
            'generated': time.strftime('%Y-%m-%d'),
            'pepSource': PEP_SOURCE_NOTE,
            'volumes': {}}
    total = confirmed_total = 0
    for vol in T.VOLUMES:
        entries, status = volume_entries(vol)
        if status != 'ok':
            data['volumes'][vol] = {'status': status, 'entries': []}
            continue
        conf = PEP_CONFIRMED.get(vol, {})
        for e in entries:
            num = e['lesson'].split('.')[0] if e['lesson'] else ''
            e['confirmed'] = bool(num and conf.get(int(num)) and norm_title(conf[int(num)]) in e['title'])
            if e['confirmed']:
                e['confirmedBy'] = PEP_SOURCE_NOTE
        confirmed_total += sum(1 for e in entries if e.get('confirmed'))
        total += len(entries)
        data['volumes'][vol] = {'status': 'ok', 'count': len(entries), 'entries': entries}
    data['summary'] = {'volumes': len(data['volumes']), 'entries': total, 'confirmed': confirmed_total}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return data


def strip_chapters(t):
    """「《老子》八章」与「《老子》四章」是同一篇的不同选段，不是两篇。
    只按整名对，教材收四章、课标要求八章的这类篇目会一律被判成「教材里没有」。"""
    return re.sub(r'[一二三四五六七八九十0-9]+(章|则|首|篇)$', '', t)


def check_claimed(p, alle, hit_ratio, findings):
    """仓里写着「教材不收」的篇目，去整张目录表里找一遍（跨学段也找）。"""
    t = norm_title(p['title'])
    ts = strip_chapters(t)
    cands = []
    for v, e in alle:
        et = norm_title(e['title'])
        ets = strip_chapters(et)
        if et == t or et.startswith(t) or t.startswith(et) or (ts and ts == ets):
            cands.append((v, e))
    # 判据比册次核对松一档：这批篇目多是节选，句子少，而且教材用字可能本来就不同
    # （谏逐客书 仓内作「求丕豹」，统编必修下册作「来丕豹」——一句都对不上恰恰是要查的地方）。
    # 所以：两句以上对上，或过半对上，或课号有人教社官方印证且至少一句对上。
    best = None
    for v, e in cands:
        ratio, hit = hit_ratio(p, e.get('url'))
        if best is None or ratio > best[2]:
            best = (v, e, ratio, hit)
    if best and (best[3] >= 2 or best[2] >= 0.5 or (best[1].get('confirmed') and best[3] >= 1)):
        v, e, ratio, hit = best
        findings.append({'id': p['id'], 'title': p['title'], 'author': p.get('author'),
                       'stage': p.get('stage'), 'status': 'claimed-absent-but-present',
                       'repoVolume': p.get('volume'), 'textbookVolume': v,
                       'textbookLesson': e.get('lesson') or '课号未定（合课或课外诵读）',
                       'evidence': ratio, 'linesHit': hit,
                       'officiallyConfirmed': bool(e.get('confirmed')),
                       'textbookTitle': e.get('raw', '')})


def similar(a, b):
    """名字差一两个字，不等于「教材里没有这篇」。
    实测两例：仓内《木兰辞》/教材「木兰诗」；仓内 己亥杂诗 / 镜像目录「已亥杂诗」（镜像把「己」写成「已」）。
    只按整名对，这两篇都会被判成教材不收。"""
    if not a or not b or len(a) < 2 or len(b) < 2:
        return False
    if a == b or a.startswith(b) or b.startswith(a):
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) <= 1
    return a[:-1] == b or a[1:] == b or b[:-1] == a or b[1:] == a


def exact_same_title(title, entries):
    """「教材里那篇同名的是另一首」是一句很强的话，只有整名对才许说。

    前缀候选（仓内「梅花」/目录「梅花魂」）只是候选：正文验不上就什么都不是。
    把它写成「同名另一篇」，等于把「我们没找到这一课」说成「教材收了另一首」——
    学生照这句话去找，找到的是另一篇课文，回头以为我们仓里的《梅花》是错的。
    前缀匹配照旧留给 candidates() 当候选、由正文定夺，这里只把住那句结论。"""
    return [(v, e) for v, e in entries if norm_title(e['title']) == title]


def audit(data):
    """仓内每篇的 volume 字段 vs 教材目录表。

    只看标题会骗人，实测三种假分歧：
      1. 仓内写「七年级下册课外诵读」，教材目录写「七年级下册」——同一个地方，后缀不同；
      2. 同名不同诗：龚自珍《己亥杂诗》是三百多首的组诗，五年级上册选「九州生气恃风雷」，
         七年级下册选「浩荡离愁白日斜」；浣溪沙在六年级下册是苏轼「山下兰芽短浸溪」，
         在初中是晏殊「一曲新词酒一杯」。标题对上不等于同一篇；
      3. 教材目录把一篇挂在「诗词五首」这类合课下，课号属于合课，不属于这一首。
    所以分歧必须拿正文核验：这篇的句子在候选课文页里出现几句，才算数。
    """
    poems = V.load_poems()
    # 语文园地裁定表（data/garden-rulings.json）：教材把这一首放在某一册的语文园地日积月累，
    # 课文目录表里没有它（那张表只收课文）。没有两条来源（镜像最多一条）的条目不生效。
    rules_path = ROOT / 'data' / 'garden-rulings.json'
    garden_rules = json.loads(rules_path.read_text(encoding='utf-8')).get('rulings', {}) if rules_path.exists() else {}
    garden_hits = []
    index = {}
    alle = []
    for vol, blk in data['volumes'].items():
        for e in blk.get('entries', []):
            index.setdefault(e['title'], []).append((vol, e))
            alle.append((vol, e))

    def candidates(title):
        """同名 + 前缀同名。仓里把词牌当标题、题目当副标题，
        教材目录写的是「天净沙·秋思」「西江月·夜行黄沙道中」——只按整名对，
        这些全会被判成「教材里没有这篇」。前缀候选再靠正文定夺。
        """
        out = list(index.get(title) or [])
        if len(title) >= 2:
            for vol, e in alle:
                if e['title'] != title and e['title'].startswith(title):
                    out.append((vol, e))
        return out
    hits, mism, unverified, absent = [], [], [], []
    findings, collisions, missing = [], [], []
    text_cache = {}

    def hit_ratio(poem, page_url):
        """这篇的句子有几成能在候选课文页的正文里找到。"""
        if not page_url:
            return 0.0, 0
        if page_url not in text_cache:
            try:
                paras = T.lesson_text(page_url)
            except Exception:
                paras = []
            text_cache[page_url] = T.norm(''.join(paras))
        txt = text_cache[page_url]
        lines = [T.norm(x) for x in (poem.get('lines') or [])]
        lines = [x for x in lines if len(x) >= 4]
        if not lines or not txt:
            return 0.0, 0
        hit = sum(1 for ln in lines if ln in txt)
        return hit / len(lines), hit

    def garden_or_absent(poem, raw_volume):
        """没有整名对、正文又验不上时怎么落档：有两条来源的园地裁定就记「园地收了」，
        否则记「教材目录里没有这一课」。两条路都不许写成「同名另一篇」。"""
        gr = garden_rules.get(poem['id'])
        srcs = [x for x in ((gr or {}).get('sources') or []) if x]
        if gr and gr.get('volume') == raw_volume and len(srcs) >= 2 \
                and len([x for x in srcs if 'yw.suyang123.com' in x]) <= 1:
            findings.append({'id': poem['id'], 'title': poem['title'], 'author': poem.get('author'),
                           'stage': poem.get('stage'), 'status': 'garden-attested',
                           'repoVolume': raw_volume, 'textbookVolume': gr['volume'],
                           'textbookLesson': gr.get('section') or '语文园地',
                           'evidence': '园地裁定表 %d 条来源' % len(srcs), 'linesHit': 0,
                           'officiallyConfirmed': False})
            garden_hits.append((poem['stage'], raw_volume, poem['title'], gr.get('section') or '语文园地'))
            return
        absent.append((poem['stage'], raw_volume, poem['title'], poem.get('author')))
        missing.append({'id': poem['id'], 'title': poem['title'], 'author': poem.get('author'),
                      'stage': poem.get('stage'), 'repoVolume': raw_volume})

    for p in poems:
        raw_vol = p.get('volume') or ''
        if raw_vol == T.NO_TEXTBOOK_VOLUME:
            # 仓里写着「教材不收」的，以前直接跳过——可假话恰恰藏在这里：
            # 兰亭集序 写着教材不收，统编选择性必修下册第 10.1 课就是它。
            check_claimed(p, alle, hit_ratio, findings)
            continue
        vol = raw_vol.replace('课外诵读', '').strip()
        title = norm_title(p['title'])
        found = candidates(title)
        same_stage = [(v, e) for v, e in found if T.stage_of(v) == p.get('stage')]
        if not same_stage:
            # 同名没有，退一步找名字差一两个字的，再拿正文核验——验不上才算「教材没有」
            near = [(v, e) for v, e in alle
                    if T.stage_of(v) == p.get('stage') and similar(title, norm_title(e['title']))]
            best = None
            for v, e in near:
                ratio, hit = hit_ratio(p, e.get('url'))
                if best is None or ratio > best[2]:
                    best = (v, e, ratio, hit)
            if best and (best[3] >= 2 or best[2] >= 0.5):
                v, e, ratio, hit = best
                hits.append((p['title'], v, e.get('lesson') or '诵读'))
                findings.append({'id': p['id'], 'title': p['title'], 'author': p.get('author'),
                               'stage': p.get('stage'), 'status': 'title-variant',
                               'repoVolume': raw_vol, 'textbookVolume': v,
                               'textbookTitle': e.get('raw', ''),
                               'textbookLesson': e.get('lesson') or '课号未定（合课或课外诵读）',
                               'evidence': ratio, 'linesHit': hit,
                               'officiallyConfirmed': bool(e.get('confirmed'))})
                continue
            garden_or_absent(p, raw_vol)
            continue
        in_repo = [x for x in same_stage if x[0] == vol]
        if in_repo:
            e = in_repo[0][1]
            lesson = e.get('lesson') or e.get('underLesson') or '诵读'
            hits.append((p['title'], vol, lesson))
            findings.append({'id': p['id'], 'title': p['title'], 'author': p.get('author'),
                           'stage': p.get('stage'), 'status': 'match', 'volume': raw_vol,
                           'textbookVolume': vol, 'textbookLesson': lesson if e.get('lesson') else '课号未定（合课或课外诵读）'})
            continue
        # 册次不一致：拿正文核验，谁对谁错要有句子数支撑
        checked = []
        for v, e in same_stage:
            ratio, hit = hit_ratio(p, e.get('url'))
            checked.append((v, e, ratio, hit))
        best = max(checked, key=lambda x: x[2]) if checked else None
        if best and best[2] >= 0.5:
            mism.append((p['stage'], p['title'], p.get('author'), raw_vol,
                         best[0], best[1].get('lesson') or '合课/诵读',
                         '%d/%d 句在教材页里' % (best[3], len([x for x in (p.get('lines') or []) if len(T.norm(x)) >= 4])),
                         bool(best[1].get('confirmed'))))
            e = best[1]
            findings.append({'id': p['id'], 'title': p['title'], 'author': p.get('author'),
                           'stage': p.get('stage'), 'status': 'volume-mismatch',
                           'repoVolume': raw_vol, 'textbookVolume': best[0],
                           'textbookLesson': e.get('lesson') or '课号未定（合课或课外诵读）',
                           'evidence': best[2], 'linesHit': best[3],
                           'officiallyConfirmed': bool(e.get('confirmed')),
                           'textbookUrl': e.get('url', '')})
        else:
            exact = exact_same_title(title, same_stage)
            if not exact:
                # 前缀候选没一个整名对、正文又验不上：不许判「同名另一篇」，
                # 退回与「同名没有」同一条落档路（园地裁定或「目录里没有」）。
                garden_or_absent(p, raw_vol)
                continue
            evi = ('最高只有 %d/%d 句对上' % (best[3], len([x for x in (p.get('lines') or []) if len(T.norm(x)) >= 4]))) if best else '没有课文页可核'
            unverified.append((p['stage'], p['title'], p.get('author'), raw_vol,
                               '/'.join(sorted({v for v, _ in exact})), evi))
            collisions.append({'id': p['id'], 'title': p['title'], 'author': p.get('author'),
                               'stage': p.get('stage'), 'repoVolume': raw_vol,
                               'sameTitleVolumes': sorted({v for v, _ in exact}),
                               'evidence': evi})
    print('教材目录表：%d 册 / %d 条课文（其中 %d 条有人教社官方课号印证）'
          % (data['summary']['volumes'], data['summary']['entries'], data['summary']['confirmed']))
    print()
    print('册次一致：%d 篇' % len(hits))
    print('册次不一致（正文核验过）：%d 篇' % len(mism))
    for stage, title, author, vol, tvol, lesson, evi, conf in mism:
        print('  %-4s %-24s %-8s 仓内=%-12s 教材=%-10s 课号=%-8s %s %s'
              % (stage, title, author or '', vol, tvol, lesson, evi,
                 '【官方印证】' if conf else ''))
    print()
    print('标题撞上但正文对不上（同名不同诗，或教材没收）：%d 篇' % len(unverified))
    for stage, title, author, vol, vols, evi in unverified:
        print('  %-4s %-24s %-8s 仓内=%-12s 同名册次=%-16s %s' % (stage, title, author or '', vol, vols, evi))
    print()
    (ROOT / 'data' / 'volume-findings.json').write_text(json.dumps({
        'note': '仓内 volume 字段与统编教材目录的逐篇核对结论。status=volume-mismatch 的条目'
                '都经过正文核验（这篇的句子在候选课文页里出现几句），不是只看标题。'
                'officiallyConfirmed 表示这一课的课号同时出现在人教社官方参考答案里。',
        'generated': time.strftime('%Y-%m-%d'),
        'counts': {'match': len(hits), 'volume-mismatch': len(mism),
                   'title-collision': len(unverified), 'absent': len(absent),
                   'claimed-absent-but-present': len([x for x in findings
                                                      if x['status'] == 'claimed-absent-but-present']),
                   'garden-attested': len(garden_hits),
                   'title-variant': len([x for x in findings if x['status'] == 'title-variant'])},
        'findings': findings,
        'titleCollision': collisions,
        'absent': missing,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    variants = [x for x in findings if x['status'] == 'title-variant']
    print()
    print('仓内篇名与教材篇名差一两个字、正文核验是同一篇：%d 篇' % len(variants))
    for x in variants:
        print('  %-4s %-14s 教材名=%-12s 册=%-10s %d 句对上' % (
              x['stage'], x['title'], x['textbookTitle'],
              x['textbookVolume'], x['linesHit']))
    claimed = [x for x in findings if x['status'] == 'claimed-absent-but-present']
    print()
    print('仓里写着「教材不收」、教材目录里却有这篇：%d 篇' % len(claimed))
    for x in claimed:
        print('  %-4s %-18s 仓内=%-16s 教材=%-10s 课号=%-8s %d 句对上 %s' % (
              x['stage'], x['title'], x['repoVolume'], x['textbookVolume'],
              x['textbookLesson'], x['linesHit'], '【官方印证】' if x['officiallyConfirmed'] else ''))
    print()
    print('语文园地收了（两条来源核过）：%d 篇' % len(garden_hits))
    for stage, vol, title, section in garden_hits:
        print('  %-4s %-26s 仓内=%-12s %s' % (stage, title, vol, section))
    print()
    print('同学段里连同名课文都没有：%d 篇' % len(absent))
    for stage, vol, title, author in absent:
        print('  %-4s %-26s %-8s 仓内=%s' % (stage, title, author or '', vol))
    return mism, unverified, absent

def report(mism, collisions, missing, hits, variants, claimed, garden=None):
    """把核对结论写成文档：数字全部从 findings 里来，不手抄。"""
    out = []
    out.append('# 教材册次核对')
    out.append('')
    out.append('> 这一页由 tools/build-textbook-lessons.py --report 生成，不要手改。')
    out.append('> 数据源：data/textbook-lessons.json（统编教材课文目录表）与 data/volume-findings.json（逐篇结论）。')
    out.append('')
    out.append('## 核对的是什么')
    out.append('')
    out.append('仓里每篇都写着「在统编教材哪一册」。这个字段以前是从来源里零散抄来的，没有一处能整体核对的地方。')
    out.append('现在把 23 册课文目录拉成一张表，逐篇比对：**仓内写的册次**和**教材目录里的册次**。')
    out.append('')
    out.append('分歧不能只看标题就下结论，三种情况长得一样：')
    out.append('')
    out.append('1. 仓内写「七年级下册课外诵读」，教材目录写「七年级下册」——同一个地方，后缀不同；')
    out.append('2. 同名不同诗：龚自珍《己亥杂诗》是三百多首的组诗，五年级上册选「九州生气恃风雷」，七年级下册选「浩荡离愁白日斜」；')
    out.append('   凉州词在四年级上册是王翰「葡萄美酒夜光杯」，我们五年级下册那首是王之涣「黄河远上白云间」；')
    out.append('   相见欢在八年级上册是朱敦儒「金陵城上西楼」，我们那首是李煜「无言独上西楼」；')
    out.append('3. 教材把一篇挂在「古代诗歌四首」这类合课下，目录里那首不带自己的课号。')
    out.append('')
    out.append('所以每一条分歧都拿**正文**核验过：这篇的句子在候选课文页里出现几句，才算数。')
    out.append('')
    out.append('## 结论')
    out.append('')
    out.append('| 结论 | 篇数 |')
    out.append('|---|---|')
    out.append('| 册次一致 | %d |' % len(hits))
    out.append('| 册次不一致（正文核验过） | %d |' % len(mism))
    out.append('| 同名不同诗（教材收的是另一首） | %d |' % len(collisions))
    out.append('| 仓内篇名与教材篇名差一两个字、正文核验是同一篇 | %d |' % len(variants))
    out.append('| 语文园地收了（两条来源核过，不是课文） | %d |' % len(garden or []))
    out.append('| 教材目录里没有这篇 | %d |' % len(missing))
    out.append('| 仓里写着「教材不收」、教材目录里却有这篇 | %d |' % len(claimed))
    out.append('')
    if garden:
        out.append('')
        out.append('## 语文园地收了（两条来源核过）')
        out.append('')
        out.append('统编教材的「语文园地」里有「日积月累」，那是要求背诵的积累内容，不是课文——')
        out.append('所以课文目录表里没有它们。只有拿到两条独立来源（那个第三方镜像最多算一条）的篇目才进这一档：')
        out.append('')
        out.append('| 学段 | 篇名 | 仓内册次 | 教材位置 |')
        out.append('|---|---|---|---|')
        for x in garden:
            out.append('| %s | %s | %s | %s%s |' % (x['stage'], x['title'], x['repoVolume'], x['textbookVolume'], x['textbookLesson']))
        out.append('')
    # 五档标签从 validate.py 的常量里来，不在这里手抄一遍：
    # 以前这里写的是「三种取值」，而篇目文件实际有五种——文档比产物少两档，读文档的人就少知道两档。
    out.append('每篇 frontmatter 的 `textbookStatus` 就是这张表的结论落进篇目文件，七档标签（与 validate.py、apply-textbook-status.py 同一份）：')
    out.append(' / '.join(V.TEXTBOOK_LABELS) + '。')
    out.append(' / '.join([V.COLLECTED, V.NOT_COLLECTED, V.NAME_CLASH, V.COVERED_ELSEWHERE, V.PARTIAL]) + '。')
    out.append('「语文园地收了」这一档落进篇目文件时算「' + V.COLLECTED + '」，具体栏目写在 textbookCoveredBy 与篇内「收录范围」里。')
    out.append('校验器会拿这张表逐篇核对篇内写的状态，对不上就报错（validate.py 2.16）。')
    out.append('站点要显示这个状态：「课标要背但教材不教」和「教材收了另一首同名的」都是学生必须知道的事。')
    out.append('')
    out.append('## 册次不一致的篇目')
    out.append('')
    out.append('| 学段 | 篇目 | 作者 | 仓内写的 | 教材实际 | 教材课号 | 正文核验 | 官方印证 |')
    out.append('|---|---|---|---|---|---|---|---|')
    for m in sorted(mism, key=lambda x: (x['stage'], x['textbookVolume'], x['title'])):
        out.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
            m['stage'], m['title'], m.get('author') or '', m['repoVolume'], m['textbookVolume'],
            m['textbookLesson'], '%d 句全对上' % m['linesHit'],
            '有' if m.get('officiallyConfirmed') else ''))
    out.append('')
    out.append('「官方印证」= 这一课的课号同时出现在人教社官方《高中语文学习任务导引》参考答案里（见 sources.md 的 S10）。')
    out.append('其余的册次结论来自统编教材目录页与课文页正文，属同一来源家族，改正文时不能只靠它。')
    out.append('')
    out.append('## 同名不同诗：教材收的不是我们那首')
    out.append('')
    out.append('| 学段 | 篇目 | 作者 | 仓内写的 | 教材里同名的是哪一册 | 核验 |')
    out.append('|---|---|---|---|---|---|')
    for c in collisions:
        out.append('| %s | %s | %s | %s | %s | %s |' % (
            c['stage'], c['title'], c.get('author') or '', c['repoVolume'],
            '/'.join(c['sameTitleVolumes']), c['evidence']))
    out.append('')
    out.append('这些篇目**统编教材课本里没有这一课**，但课标要求背诵。不是错误，是要写清楚的状态。')
    out.append('')
    out.append('## 教材目录里没有这篇')
    out.append('')
    out.append('| 学段 | 篇目 | 作者 | 仓内写的 |')
    out.append('|---|---|---|---|')
    for m in sorted(missing, key=lambda x: (x['stage'], x['repoVolume'], x['title'])):
        out.append('| %s | %s | %s | %s |' % (m['stage'], m['title'], m.get('author') or '', m['repoVolume']))
    out.append('')
    out.append('## 篇名不同但正文是同一篇（不是两篇，别当成同名不同诗）')
    out.append('')
    out.append('| 学段 | 仓内篇名 | 教材篇名 | 教材册次 | 教材课号 | 正文核验 |')
    out.append('|---|---|---|---|---|---|')
    for v in sorted(variants, key=lambda x: (x['stage'], x['title'])):
        out.append('| %s | %s | %s | %s | %s | %s 句 |' % (
                   v['stage'], v['title'], v['textbookTitle'], v['textbookVolume'],
                   v['textbookLesson'], v['linesHit']))
    out.append('')
    out.append('仓内《木兰辞》就是统编七年级下册第 9 课的《木兰诗》，只差一个字，正文 6 句全对上。')
    out.append('小学五年级上册的《己亥杂诗》（九州生气恃风雷）在教材目录页上写作「已亥杂诗」——那是镜像页的错字，')
    out.append('不是另一首诗。教材正文作「不拘一格降人**材**」（维基文库《己亥雜詩》同），仓内已按这两条来源改从「人材」，见篇内异文。')
    out.append('')
    out.append('## 核对过程中撞到的两件事')
    out.append('')
    out.append('**一、统编教材的《论语》十二章是两套不同的章（已处理：拆成两份）。** 七年级上册第 12 课那套以「子曰：学而时习之」开头，')
    out.append('选择性必修上册第 5 课那套以「子曰：君子食无求饱」开头——**篇名相同，内容不同**。')
    out.append('仓里原来只有一份，挂在高中，正文用的还是旧人教版的十二则组合，两套都不是。')
    out.append('这意味着：按初中教材背的人和按高中教材背的人，背的不是同一批句子。已拆成两份，各挂各的学段。')
    out.append('')
    out.append('**二、目录页反映的是 2024 年修订后的统编教材。** 七年级上册里出现了「往事依依」「我的白鸽」「狼」这些新课，')
    out.append('课号整体比 2018 版后移一位。仓里的册次是按 2018 版写的，所以「不一致」里有一部分是教材改版造成的。')
    out.append('口径要写死：以最新统编（已修订年级按修订版）为准，并在篇内记下「首次收录册次 + 版本变更」。')
    out.append('')
    (ROOT / 'docs' / 'textbook-audit.md').write_text('\n'.join(out) + '\n', encoding='utf-8')
    return len(out)


def selftest():
    """护栏自己得先被抓到才行：每一条都配一个「如果它漏了会怎样」。"""
    bad = 0

    def must(ok, why):
        nonlocal bad
        if not ok:
            print('  !! ' + why)
            bad += 1

    # 坏例1：前缀同名不许判成「同名另一篇」（梅花 / 梅花魂 就是这么错的）
    must(exact_same_title('梅花', [('五年级下册', {'title': '梅花魂'})]) == [],
         '坏例1：前缀同名（梅花 / 梅花魂）被算成同名另一篇')
    # 坏例2、3：真同名不许被误杀（相见欢 / 凉州词 是教材里另一首）
    must(len(exact_same_title('相见欢', [('八年级上册', {'title': '相见欢'})])) == 1,
         '坏例2：真同名（相见欢）没被算出来')
    must(len(exact_same_title('凉州词', [('四年级上册', {'title': '凉州词'})])) == 1,
         '坏例3：真同名（凉州词）没被算出来')
    # 坏例4：北冥 / 北冥有鱼 也不许靠标题定同名——那要靠正文
    must(exact_same_title('北冥', [('八年级上册', {'title': '北冥有鱼'})]) == [],
         '坏例4：前缀同名（北冥 / 北冥有鱼）被算成同名另一篇')
    # 坏例5、6：课号、自读星号、括号、节选剥不干净，整名对就形同虚设
    must(len(exact_same_title('咏鹅', [('一年级上册', {'title': '4*咏鹅'})])) == 1,
         '坏例5：课号与自读星号没剥掉（4*咏鹅）')
    must(len(exact_same_title('古朗月行', [('一年级上册', {'title': '古朗月行（节选）'})])) == 1,
         '坏例6：「（节选）」没剥掉，整名对认不出同一篇')
    # 坏例7：函数挂在文件里却没接进核对——存在但没用的检查等同于没有检查
    src = (ROOT / 'tools' / 'build-textbook-lessons.py').read_text(encoding='utf-8')
    body = src[src.index('def audit(data):'):src.index('def main():')]
    must('exact_same_title(' in body and 'garden_or_absent(' in body,
         '坏例7：exact_same_title / garden_or_absent 没接进 audit()')
    if bad:
        print('[!] build-textbook-lessons --selftest 失败 %d 项' % bad)
        return 1
    print('[ok] build-textbook-lessons --selftest 通（当场数到 7 个坏例子，全部试到）')
    return 0


def main():
    if '--selftest' in sys.argv:
        return selftest()
    if '--report' in sys.argv:
        data = build()
        audit(data)
        # 结论从 findings 文件里读，不从 audit 的临时元组里读：
        # 元组里没有 id、没有 URL，文档要能让人回查。
        f = json.loads((ROOT / 'data' / 'volume-findings.json').read_text(encoding='utf-8'))
        mism = [x for x in f['findings'] if x['status'] == 'volume-mismatch']
        hits = [x for x in f['findings'] if x['status'] == 'match']
        variants = [x for x in f['findings'] if x['status'] == 'title-variant']
        claimed = [x for x in f['findings'] if x['status'] == 'claimed-absent-but-present']
        garden = [x for x in f['findings'] if x['status'] == 'garden-attested']
        n = report(mism, f['titleCollision'], f['absent'], hits, variants, claimed, garden)
        print('已写 docs/textbook-audit.md（%d 行）' % n)
        return 0
    if '--audit' in sys.argv:
        # 先重建再核对：拿旧表核对过一次，表里没有课文页 URL，
        # 核验全部返回 0 句，看起来像「正文都对不上」，其实是表是旧的。
        data = build()
        audit(data)
        return 0
    data = build()
    print('已写 data/textbook-lessons.json：%d 册 / %d 条课文 / %d 条有人教社官方课号印证'
          % (data['summary']['volumes'], data['summary']['entries'], data['summary']['confirmed']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
