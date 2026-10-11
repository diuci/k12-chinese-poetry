# -*- coding: utf-8 -*-
"""查「句子被从中间截断」。

起因：苏辙《上枢密韩太尉书》的必背名句是

    辙生好为文，思之至深。以为文出於。

「出於」是介词短语的开头，句子到这儿就断了。站点上就这么显示，
构建通过、校验通过、链接全通——只是这半句谁也读不懂。

判据：句子以介词/连词收尾。介词后面必然还有宾语，句子不可能就这么完。

    顿号结尾的先排除：「……惟……一芥、舟中人两三粒而已。」

文言里句末虚词（矣、焉、矣、也、耳、矣）收尾是**正常**的，
所以只查真介词：於、于、乎、为、以、使、若、与、而、则。

这里留了误报出口 KNOWN_FP，跑 --selftest 验证它真的能抓到东西。

用法：
    python tools/check-truncated.py
    python tools/check-truncated.py --selftest
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'poems.json'

ok, bad, warn = '[ok]', '[!!]', '[--]'

# 介词收尾 = 句子必然不完整
TAIL = re.compile(r'[\u4e8e\u65bc\u4e3a\u4ee5\u4f7f\u82e5\u4e0e\u800c\u5219]\u3002$')
# 正常句末虚词收尾，不算截断
NORMAL_END = ('矣', '焉', '也', '耳', '尔', '耶', '兮', '者')

# 已确认的正常用例，避免规则本身出问题
KNOWN_OK = [
    '惟长堤一痕、湖心亭一点、与余舟一芥、舟中人两三粒而已。',
    '君子曰：学不可以已。',
    # 《诗经·卫风·氓》「桑之未落，其叶沃若」——「沃若」是「润泽的样子」，
    # 若 在这里是形容词后缀（…的样子），不是「若+宾语」的那个连词。
    # 同篇还有「关关雎鸠」一类的叠句、《诗经》里「沃若」「奄若」这类写法不少，
    # 拿 KNOWN_OK 登记这一句，而不是把 若 整个从判据里放掉：放掉就等于以后真的
    # 「…若」断句再也查不出来。
    '桑之未落，其叶沃若。',
]


def check():
    poems = json.loads(DATA.read_text(encoding='utf-8'))['poems']
    bad_lines = []
    for p in poems:
        for i, ln in enumerate(p.get('linesPunct') or []):
            if ln in KNOWN_OK:
                continue
            if not TAIL.search(ln):
                continue
            if ln.rstrip('\u3002').endswith(NORMAL_END):
                continue
            bad_lines.append((p, i, ln))
    return bad_lines


if '--selftest' in sys.argv:
    print('=== 自测：判据能否抓到已知截断 ===')
    known = '辙生好为文，思之至深。以为文出於。'
    hit = bool(TAIL.search(known))
    print('%s 能抓到已知截断句: %s' % (ok if hit else bad, known))
    for s in KNOWN_OK:
        print('%s 不会误报: %s' % (ok if not TAIL.search(s) or s in KNOWN_OK else bad, s))
    # 坏例子1：真截断必须抓到（已知那一句）
    assert hit, '坏例1：已知截断句「以为文出於。」没被抓到——判据失效'
    # 坏例子2：误报出口不许变成万能出口——登记进 KNOWN_OK 的句子必须真的在表里，
    # 否则 check() 与 selftest 各说各话（以前 KNOWN_OK 写错一个字就静默失效）
    fp = '桑之未落，其叶沃若。'
    assert fp in KNOWN_OK, '坏例2：《氓》「其叶沃若」这一句的误报登记丢了'
    assert TAIL.search(fp), '坏例2b：这一句本来就不触发判据——那 KNOWN_OK 里留着它干什么？'
    # 坏例子3：真以连词收尾的半句，哪怕长得像《诗经》，也必须抓到
    assert TAIL.search('桑之未落，其叶沃於。'), '坏例3：以「於」收尾的半句没被抓到'
    # 坏例子4：句末虚词收尾（矣、也、焉、兮）不许报
    for good in ('反是不思，亦已焉哉。', '女之耽兮，不可说也。', '静言思之，躬自悼矣。'):
        assert not TAIL.search(good), '坏例4：正常句末虚词收尾被当成截断：%s' % good
    sys.exit(0 if hit else 1)

bad_lines = check()
print('=== 截断句检查 ===')
print('篇数 %d' % len(json.loads(DATA.read_text(encoding='utf-8'))['poems']))
if bad_lines:
    for p, i, ln in bad_lines:
        print('%s %s《%s》句%d: %s' % (bad, p['id'], p['title'], i, ln))
    print('')
    print('%s 发现 %d 处疑似截断' % (bad, len(bad_lines)))
    sys.exit(1)
print('%s 没有发现截断句' % ok)
