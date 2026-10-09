# -*- coding: utf-8 -*-
"""查三类「不会报错但一定不对」的问题。

起因：小学五年级下册有一首《寒下曲》(卢纶)。卢纶根本没写过这首诗，
是《塞下曲》被写错了标题。诗人、诗句、联句跟四年级下册那首完全一样。

为什么一直没被发现：
- validate.py 校验的是「一首诗自身是否合规」，不校验「这一首是否真实存在」
- 站点构建照常生成页面，链接全通，死链 0
- 游戏照常取到诗，能玩

也就是说，它通过了所有现有检查。只有把「同一首诗出现两次」单独拎出来看，
才会发现其中一份的标题是错的。

检查项：
1. 诗文完全相同的条目——逐组列出，标题不同的最可疑
2. **内容重叠**的条目：一方是另一方的子集（不同书目的节选），
   但作者/朝代标注不同——这能抓出「出处标错」的错误
3. 标题看起来是错别字（与另一条同作者、同诗文的条目标题只差一个字）

第 2 条的例子：八年级下册的《杂说》标着「韩愈·唐」，
可它的四句全是《礼记·学记》里的句子，与同册的《虽有嘉肴》
（已正确标为佚名·先秦）逐句重合。作者标错，正是靠这条抓出来的。

用法：python tools/check-duplicates.py [--selftest]
"""
import json
import pathlib
import re
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / 'data' / 'poems.json'

sys.path.insert(0, str(ROOT / 'tools'))
try:
    from common import C
    ok, bad, warn = C.OK, C.BAD, C.WARN
except Exception:
    ok, bad, warn = '[ok]', '[!!]', '[--]'

ALIASES_PATH = ROOT / 'data' / 'title-aliases.json'


def load_duplicate_aliases():
    """合法异名对登记在 data/title-aliases.json 的 duplicateTitles 里，不硬编码在这里。

    为什么：那张表自己写着「别名必须显式登记在这里，不许硬编码进匹配器——硬编码的别名没人复核」，
    而本文件先前是全仓唯一不守这条的地方（表就写在上头几行）。现在读不到文件当场停，
    不许「表读不出来就当没有、继续跑」。"""
    if not ALIASES_PATH.exists():
        raise SystemExit('!! 读不到 %s：别名表不在，不许猜' % ALIASES_PATH)
    data = json.loads(ALIASES_PATH.read_text(encoding='utf-8'))
    out = {}
    for item in data.get('duplicateTitles', []):
        ts = item.get('titles') or []
        if len(ts) >= 2:
            out[frozenset(ts)] = item.get('reason', '')
    return out


KNOWN_ALIASES = load_duplicate_aliases()

# 比对用的「一行」：只留汉字、去掉标点，短于四字的行不参与重叠判定
# （「子曰」「诗云」这种两三字行到处都有，拿它们比重叠会造出一堆假冲突）。
def _line_key(ln):
    return re.sub(r'[^\u4e00-\u9fff]', '', ln or '')


def exact_groups(poems):
    """诗文完全相同的条目分组。返回 (组列表, 标题不一致的组)。"""
    by_text = defaultdict(list)
    for p in poems:
        by_text[''.join(p.get('lines') or [])].append(p)
    groups, suspect = [], []
    for text, group in by_text.items():
        if len(group) < 2:
            continue
        groups.append(group)
        titles = [g['title'] for g in group]
        if len(set(titles)) == 1:
            continue
        if frozenset(titles) in KNOWN_ALIASES:
            continue
        suspect.append(group)
    return groups, suspect


def overlap_pairs(poems):
    """内容重叠的条目对，以及其中作者/朝代标注对不上的那些。

    必须按**整行**比对，不能把整段 CJK 连成一大串再找子串：
    不同条目的必背名句取自同一段原文的不同位置，整串拼接后彼此根本不会命中，
    检查会「零重叠」地空过——比没有检查更危险。
    """
    line_sets = {}
    for p in poems:
        line_sets[p['id']] = set(k for k in (_line_key(ln) for ln in (p.get('linesPunct') or [])) if len(k) >= 4)
    pairs, conflicts = [], []
    for i, a_ in enumerate(poems):
        for b_ in poems[i + 1:]:
            la, lb = line_sets[a_['id']], line_sets[b_['id']]
            if not la or not lb:
                continue
            inter = la & lb
            if len(inter) < 2:
                continue
            pairs.append((a_, b_, len(inter)))
            if not (a_['author'] == b_['author'] and a_['dynasty'] == b_['dynasty']):
                conflicts.append((a_, b_, len(inter)))
    return pairs, conflicts


def main():
    poems = json.loads(DATA.read_text(encoding='utf-8'))['poems']
    groups, suspect = exact_groups(poems)

    print('=== 重复诗文检查 ===')
    print('总篇数 %d，唯一诗文 %d' % (len(poems), len(poems) - sum(len(g) - 1 for g in groups)))
    print('')
    for group in groups:
        titles = [g['title'] for g in group]
        same_title = len(set(titles)) == 1
        print('%s %d 首同诗：%s' % (
            warn if same_title else bad,
            len(group),
            '  |  '.join('%s《%s》%s' % (g['id'], g['title'], g['volume']) for g in group)))
        if not same_title:
            note = KNOWN_ALIASES.get(frozenset(titles))
            if note:
                print('       %s 已登记为合法异名：%s' % (ok, note))

    print('')
    print('内容重叠检查（取自同一段原文的不同位置）')
    pairs, overlap_bad = overlap_pairs(poems)
    for a_, b_, n in overlap_bad:
        print('   %s %s《%s》(%s·%s)  vs  %s《%s》(%s·%s)  重合 %d 句'
              % (bad, a_['id'], a_['title'], a_['author'], a_['dynasty'],
                 b_['id'], b_['title'], b_['author'], b_['dynasty'], n))
    print('   检出内容重叠的条目对: %d' % len(pairs))
    if not pairs:
        print('   %s 一处重叠都没有——很可能是比对方式写错了，不是诗库真这么干净' % warn)
    print('')
    if overlap_bad:
        print('%s 有 %d 处作者/朝代标注与内容出处对不上，需人工确认' % (bad, len(overlap_bad)))
    else:
        print('%s 没有发现出处标注冲突' % ok)

    print('')
    if suspect or overlap_bad:
        print('%s 标题不一致的组 %d，需人工确认哪一份的标题是对的：' % (bad, len(suspect)))
        for g in suspect:
            print('    %s' % '  vs  '.join('%s《%s》(%s)' % (x['author'], x['title'], x['author']) for x in g))
        sys.exit(1)
    print('%s 没有标题不一致的重复' % ok)
    if not pairs:
        # 空过的重叠检查比没有重叠检查更危险：当场红，不许绿着过去。
        print('%s 全仓一处内容重叠都没有——这道检查自己不可信，不许算通过' % bad)
        sys.exit(1)
    return 0


def selftest():
    """这道检查自己也得有坏例子：它抓出过一次真错，抓不住的话没人知道它已经失效。"""
    tried = [0]

    def must(cond, msg):
        tried[0] += 1
        assert cond, msg

    def poem(pid, title, author, dynasty, lines, lines_punct):
        return {'id': pid, 'title': title, 'author': author, 'dynasty': dynasty,
                'volume': '测试册', 'lines': lines, 'linesPunct': lines_punct}

    # 坏例1：《寒下曲》/《塞下曲》——同诗不同标题，必须被拎出来
    a = poem('saixiaqu', '塞下曲', '卢纶', '唐', ['林暗草惊风', '将军夜引弓'],
             ['林暗草惊风，', '将军夜引弓，'])
    b = poem('hanxiaqu', '寒下曲', '卢纶', '唐', ['林暗草惊风', '将军夜引弓'],
             ['林暗草惊风，', '将军夜引弓，'])
    groups, suspect = exact_groups([a, b])
    must(len(groups) == 1 and len(suspect) == 1, '坏例1：同诗不同标题没被抓出来')

    # 坏例2：标题相同的两条（各归各册）不算可疑，但必须仍然算重复组——不许静默放过
    c = poem('lunyu12', '《论语》十二章', '孔子', '先秦', ['子曰学而时习之'], ['子曰学而时习之，'])
    d = poem('lunyu12g', '《论语》十二章', '孔子', '先秦', ['子曰学而时习之'], ['子曰学而时习之，'])
    g2, s2 = exact_groups([c, d])
    must(len(g2) == 1 and not s2, '坏例2：同标题重复要么没被抓成组，要么被当成可疑')

    # 坏例3：登记过的合法异名不许报警，但没登记的同一对标题必须报警（别名表不许顺手扩大）
    e = poem('liyundao', '大道之行也', '佚名', '先秦', ['大道之行也天下为公'], ['大道之行也，天下为公，'])
    f = poem('liyun', '礼运', '佚名', '先秦', ['大道之行也天下为公'], ['大道之行也，天下为公，'])
    g3, s3 = exact_groups([e, f])
    must(len(g3) == 1 and not s3, '坏例3：登记过的合法异名被当成可疑')
    g4, s4 = exact_groups([e, poem('liyun2', '礼运上', '佚名', '先秦',
                                   ['大道之行也天下为公'], ['大道之行也，天下为公，'])])
    must(len(s4) == 1, '坏例3b：没登记的异名（礼运 / 礼运上）却没报警')

    # 坏例4：《杂说》/《虽有嘉肴》——名句取自同一段原文的不同位置，作者标注不同，必须报警
    z1 = poem('zashuo', '杂说', '韩愈', '唐', ['玉不琢不成器'],
              ['玉不琢，不成器；', '人不学，不知道。'])
    z2 = poem('suoyoujiayao', '虽有嘉肴', '佚名', '先秦', ['虽有嘉肴弗食不知其旨也'],
              ['虽有嘉肴，弗食，不知其旨也；', '玉不琢，不成器；', '人不学，不知道。'])
    pairs, conflicts = overlap_pairs([z1, z2])
    must(len(pairs) == 1 and len(conflicts) == 1, '坏例4：整段拼接式比对会零重叠空过，这一对没被抓出来')

    # 坏例5：同一作者同一朝代的重叠不许报警（那是正常的节选），但必须仍然算重叠对
    y1 = poem('a1', '节选甲', '李白', '唐', ['床前明月光'], ['床前明月光，', '疑是地上霜。'])
    y2 = poem('a2', '节选乙', '李白', '唐', ['举头望明月'],
              ['举头望明月，', '低头思故乡。', '床前明月光，', '疑是地上霜。'])
    p5, c5 = overlap_pairs([y1, y2])
    must(len(p5) == 1 and not c5, '坏例5：同作者同朝代的重叠被误报，或重叠对没被数到')

    # 坏例6：短于四字的行不许参与重叠判定（「子曰」「诗云」到处都有，会造出一堆假冲突）
    s1 = poem('s1', '甲篇', '佚名', '先秦', ['子曰'], ['子曰，', '学而时习之。'])
    s2 = poem('s2', '乙篇', '李白', '唐', ['子曰'], ['子曰，', '床前明月光。'])
    p6, c6 = overlap_pairs([s1, s2])
    must(not p6 and not c6, '坏例6：两三字的短行造出了假重叠')

    # 坏例7：只重合一句（<2）不算重叠——否则任何两篇引同一句名诗都要报警，检查会被噪音淹掉
    q1 = poem('q1', '甲', '李白', '唐', ['床前明月光'], ['床前明月光，'])
    q2 = poem('q2', '乙', '杜甫', '唐', ['床前明月光'], ['床前明月光，'])
    p7, c7 = overlap_pairs([q1, q2])
    must(not p7 and not c7, '坏例7：只重合一句就被当成内容重叠')

    # 坏例8：比对键必须去标点——带标点的行彼此对不上，检查会空过
    must(_line_key('床前明月光，') == _line_key('床前明月光'), '坏例8：去标点这一步没生效')
    must(_line_key('疑是地上霜。') != '疑是地上霜上', '坏例8b：比对键把字也去掉了')

    # 坏例9：合法异名对必须真的从 data/title-aliases.json 读出来，不是写死在本文件里
    must(len(KNOWN_ALIASES) >= 2, '坏例9：别名表没从 data/title-aliases.json 读出来（读到 %d 对）' % len(KNOWN_ALIASES))
    must(frozenset(['虽有嘉肴', '《礼记》一则']) in KNOWN_ALIASES,
         '坏例9b：登记表里那对《礼记》一则 / 虽有嘉肴没读出来')
    j1 = poem('liji1', '《礼记》一则', '佚名', '先秦', ['虽有嘉肴弗食不知其旨也'], ['虽有嘉肴，弗食，不知其旨也。'])
    j2 = poem('suoyoujiayao2', '虽有嘉肴', '佚名', '先秦', ['虽有嘉肴弗食不知其旨也'], ['虽有嘉肴，弗食，不知其旨也。'])
    g9, s9 = exact_groups([j1, j2])
    must(len(g9) == 1 and not s9, '坏例9c：登记过的异名对还被当成可疑')
    saved = dict(KNOWN_ALIASES)
    KNOWN_ALIASES.clear()
    g10, s10 = exact_groups([j1, j2])
    must(len(s10) == 1, '坏例10：把别名表清空，这对却没报警——别名表是摆设')
    KNOWN_ALIASES.update(saved)

    print('[ok] check-duplicates --selftest 通（当场数到 %d 个坏例子，全部试到）' % tried[0])
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
