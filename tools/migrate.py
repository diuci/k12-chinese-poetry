#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性迁移工具：把游戏内嵌的 poems.js 转成本仓的 Markdown 篇目。

背景：丢词大作战游戏原先把 45 首诗硬编码在
      inkwave-main/src/game/poems/poems.js里。本仓要把它们变成
      Markdown 源文件（人可读、可校订），再由 build.py 编成 JSON。

本脚本做两件事：
  1. 解析 poems.js 的POEMS 数组（用正则，不依赖 JS 运行时）
  2. 合并本文件下方的 METADATA（册次/主题/情感/手法/难度/高频度）
     和 PUNCT（带标点正文，用于人读），写出 poems/**/*.md

为什么元数据放在脚本里而不是逐个手写 frontmatter：
  45 首一次性迁移需要人工核对，集中在一处更易审阅；迁移完成后
  每篇的 .md 就是唯一事实源，后续校订直接改 .md。

用法：
    python tools/migrate.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / 'inkwave-main' / 'src' / 'game' / 'poems' / 'poems.js'
POEMS_DIR = ROOT / 'poems'

# ---------------------------------------------------------------- 元数据
# volume:统编教材册次（据人教社教材目录）
# theme / emotion / technique / difficulty: 文学常识（自行撰写，CC BY 4.0）
# exam_freq: 中考出现频率估值（0~1，用于玩法排序，非精确统计）
METADATA = {
    # ---------------- 一年级
    'yonge': dict(volume='一年级上册', theme=['咏物', '童趣'], emotion='孩童观察鹅时的欣喜', technique=['拟人'], difficulty=1, exam_freq=0.85),
    'jiangnan': dict(volume='一年级上册', theme=['田园', '劳动'], emotion='采莲的欢快', technique=['复沓', '比喻'], difficulty=2, exam_freq=0.5),
    'hua': dict(volume='一年级上册', theme=['咏物', '哲理'], emotion='对自然之妙的新奇', technique=['反问', '对偶'], difficulty=1, exam_freq=0.3),
    'minnong2': dict(volume='一年级上册', theme=['田园', '劳动'], emotion='对农人的悯叹', technique=['对比'], difficulty=1, exam_freq=0.9),
    'gulangyuexing': dict(volume='一年级上册', theme=['咏物', '想象'], emotion='童年望月的稚趣想象', technique=['比喻', '想象'], difficulty=2, exam_freq=0.6),
    'feng': dict(volume='一年级上册', theme=['咏物', '自然'], emotion='对风之力的赞叹', technique=['对偶', '拟人'], difficulty=2, exam_freq=0.5),
    'chunxiao': dict(volume='一年级下册', theme=['春天', '惜春'], emotion='春日清晨的喜悦与怜惜', technique=['拟人'], difficulty=1, exam_freq=0.95),
    'zengwanglun': dict(volume='一年级下册', theme=['送别', '友情'], emotion='送友的深情', technique=['比喻'], difficulty=1, exam_freq=0.7),
    'jingyesi': dict(volume='一年级下册', theme=['思乡', '月亮'], emotion='客居思乡的深切', technique=['比喻', '夸张'], difficulty=1, exam_freq=1.0),
    'xunyinzhe': dict(volume='一年级下册', theme=['山居', '访友'], emotion='寻访不遇的怅然', technique=['白描'], difficulty=1, exam_freq=0.6),
    'chishang': dict(volume='一年级下册', theme=['童趣', '劳动'], emotion='孩童撑舟的憨态', technique=['白描'], difficulty=1, exam_freq=0.6),
    'xiaochi': dict(volume='一年级下册', theme=['夏天', '荷'], emotion='初夏的清新喜悦', technique=['拟人', '比喻'], difficulty=2, exam_freq=0.7),
    'huaji': dict(volume='一年级下册', theme=['咏物', '志趣'], emotion='对画鸡的赞许', technique=['拟人', '对比'], difficulty=2, exam_freq=0.5),
    'xiangsi': dict(volume='一年级下册', theme=['咏物', '相思'], emotion='托物寄相思', technique=['双关'], difficulty=2, exam_freq=0.5),
    # ---------------- 二年级
    'meihua': dict(volume='二年级上册', theme=['咏物', '冬天'], emotion='凌寒独放的傲骨', technique=['拟人', '对比'], difficulty=2, exam_freq=0.8),
    'xiaoerchuidiao': dict(volume='二年级上册', theme=['童趣', '垂钓'], emotion='孩童垂钓的天真', technique=['白描'], difficulty=2, exam_freq=0.5),
    'dengguanquelou': dict(volume='二年级上册', theme=['哲理', '登高'], emotion='开阔进取的胸襟', technique=['对偶'], difficulty=2, exam_freq=0.9),
    'wanglushanpubu': dict(volume='二年级上册', theme=['山水', '夸张'], emotion='瀑布的雄奇惊叹', technique=['夸张', '比喻'], difficulty=2, exam_freq=0.9),
    'jiangxue': dict(volume='二年级上册', theme=['冬天', '山水'], emotion='雪江独钓的孤高', technique=['对偶', '夸张'], difficulty=2, exam_freq=0.8),
    'yesushansi': dict(volume='二年级上册', theme=['夸张', '夜游'], emotion='登楼摘星的童趣想象', technique=['夸张'], difficulty=2, exam_freq=0.6),
    'chilege': dict(volume='二年级上册', theme=['草原', '牧歌'], emotion='草原辽阔的欢欣', technique=['比喻', '反复'], difficulty=2, exam_freq=0.7),
    'cunju': dict(volume='二年级下册', theme=['春天', '童趣'], emotion='放学放风筝的欢快', technique=['白描'], difficulty=1, exam_freq=0.8),
    'yongliu': dict(volume='二年级下册', theme=['春天', '咏物'], emotion='对春柳的赞叹', technique=['比喻', '拟人'], difficulty=2, exam_freq=0.9),
    'guyuancao': dict(volume='二年级下册', theme=['咏物', '哲理'], emotion='野草顽强的生命力', technique=['叠词', '对比'], difficulty=3, exam_freq=0.8),
    'jingcisi': dict(volume='二年级下册', theme=['夏天', '荷'], emotion='西湖荷景的明艳', technique=['对偶'], difficulty=2, exam_freq=0.7),
    'jueju-huangli': dict(volume='二年级下册', theme=['春天', '写景'], emotion='明媚春景的欣喜', technique=['对偶'], difficulty=2, exam_freq=0.9),
    'minnong1': dict(volume='二年级下册', theme=['田园', '劳动'], emotion='对丰收与不公的追问', technique=['对比'], difficulty=2, exam_freq=0.7),
    'zhouyeshujian': dict(volume='二年级下册', theme=['夜晚', '写景'], emotion='渔火满河的惊喜', technique=['比喻'], difficulty=3, exam_freq=0.5),
    # ---------------- 三年级
    'suojian': dict(volume='三年级上册', theme=['童趣', '夏天'], emotion='捕蝉忽然静默的童趣', technique=['白描'], difficulty=1, exam_freq=0.6),
    'shanxing': dict(volume='三年级上册', theme=['秋天', '山水'], emotion='秋山枫林的赞美', technique=['对偶'], difficulty=2, exam_freq=0.9),
    'zengliujingwen': dict(volume='三年级上册', theme=['秋天', '勉励'], emotion='勉友珍惜光阴', technique=['拟人', '对比'], difficulty=3, exam_freq=0.7),
    'yeshusuojian': dict(volume='三年级上册', theme=['秋天', '思乡'], emotion='客居思乡的怅惘', technique=['对比'], difficulty=2, exam_freq=0.7),
    'wangtianmenshan': dict(volume='三年级上册', theme=['山水', '壮阔'], emotion='长江天门山的壮阔', technique=['对偶', '夸张'], difficulty=2, exam_freq=0.9),
    'yinhushang': dict(volume='三年级上册', theme=['山水', '西湖'], emotion='西湖晴雨皆奇', technique=['比喻', '对偶'], difficulty=2, exam_freq=0.8),
    'wangdongting': dict(volume='三年级上册', theme=['山水', '月夜'], emotion='洞庭月色的空明', technique=['比喻', '对偶'], difficulty=3, exam_freq=0.8),
    'zaofabaidicheng': dict(volume='三年级上册', theme=['山水', '喜悦'], emotion='轻舟已过的轻快', technique=['夸张'], difficulty=2, exam_freq=0.9),
    'cailianqu': dict(volume='三年级上册', theme=['夏天', '劳动'], emotion='采莲人乐在其中的欢娱', technique=['拟人', '夸张'], difficulty=3, exam_freq=0.5),
    'jueju-chiri': dict(volume='三年级下册', theme=['春天', '写景'], emotion='春日迟景的慵懒', technique=['对偶'], difficulty=2, exam_freq=0.8),
    'huichongchunjiang': dict(volume='三年级下册', theme=['春天', '哲理'], emotion='由景物见哲理的欣喜', technique=['比喻'], difficulty=3, exam_freq=0.7),
    'sanqudaozhong': dict(volume='三年级下册', theme=['初夏', '山行'], emotion='山行遇雨前的闲适', technique=['对偶'], difficulty=2, exam_freq=0.7),
    'yuanri': dict(volume='三年级下册', theme=['节日', '春节'], emotion='新年的喜庆与革新之志', technique=['对偶', '借代'], difficulty=2, exam_freq=0.9),
    'qingming': dict(volume='三年级下册', theme=['节日', '清明'], emotion='清明踏青的惆怅', technique=['白描'], difficulty=2, exam_freq=0.9),
    'jiuyuejiuri': dict(volume='三年级下册', theme=['思乡', '节日'], emotion='重阳独处的思亲', technique=['对比'], difficulty=3, exam_freq=1.0),
    'chuzhouxijian': dict(volume='三年级下册', theme=['山水', '闲适'], emotion='涧边幽独自守', technique=['对比'], difficulty=3, exam_freq=0.8),
    'dalinsitaohua': dict(volume='三年级下册', theme=['春天', '哲理'], emotion='山寺春迟的惊喜', technique=['对比'], difficulty=3, exam_freq=0.7),
}

# 带标点正文（人读用）。游戏内的 lines[] 已剥离标点，这里补回，
# 使Markdown 正文可直接阅读与朗读。格式：与 METADATA 同序。
PUNCT = {
    'yonge': ['鹅，鹅，鹅，曲项向天歌。', '白毛浮绿水，红掌拨清波。'],
    'jiangnan': ['江南可采莲，莲叶何田田。', '鱼戏莲叶间。', '鱼戏莲叶东，鱼戏莲叶西。', '鱼戏莲叶南，鱼戏莲叶北。'],
    'hua': ['远看山有色，近听水无声。', '春去花还在，人来鸟不惊。'],
    'minnong2': ['锄禾日当午，汗滴禾下土。', '谁知盘中餐，粒粒皆辛苦。'],
    'gulangyuexing': ['小时不识月，呼作白玉盘。', '又疑瑶台镜，飞在青云端。', '仙人垂两足，桂树何团团。', '白兔捣药成，问言与谁餐。'],
    'feng': ['解落三秋叶，能开二月花。', '过江千尺浪，入竹万竿斜。'],
    'chunxiao': ['春眠不觉晓，处处闻啼鸟。', '夜来风雨声，花落知多少。'],
    'zengwanglun': ['李白乘舟将欲行，忽闻岸上踏歌声。', '桃花潭水深千尺，不及汪伦送我情。'],
    'jingyesi': ['床前明月光，疑是地上霜。', '举头望明月，低头思故乡。'],
    'xunyinzhe': ['松下问童子，言师采药去。', '只在此山中，云深不知处。'],
    'chishang': ['小娃撑小艇，偷采白莲回。', '不解藏踪迹，浮萍一道开。'],
    'xiaochi': ['泉眼无声惜细流，树阴照水爱晴柔。', '小荷才露尖尖角，早有蜻蜓立上头。'],
    'huaji': ['头上红冠不用裁，满身雪白走将来。', '平生不敢轻言语，一叫千门万户开。'],
    'xiangsi': ['红豆生南国，春来发几枝。', '愿君多采撷，此物最相思。'],
    'meihua': ['墙角数枝梅，凌寒独自开。', '遥知不是雪，为有暗香来。'],
    'xiaoerchuidiao': ['蓬头稚子学垂纶，侧坐莓苔草映身。', '路人借问遥招手，怕得鱼惊不应人。'],
    'dengguanquelou': ['白日依山尽，黄河入海流。', '欲穷千里目，更上一层楼。'],
    'wanglushanpubu': ['日照香炉生紫烟，遥看瀑布挂前川。', '飞流直下三千尺，疑是银河落九天。'],
    'jiangxue': ['千山鸟飞绝，万径人踪灭。', '孤舟蓑笠翁，独钓寒江雪。'],
    'yesushansi': ['危楼高百尺，手可摘星辰。', '不敢高声语，恐惊天上人。'],
    'chilege': ['敕勒川，阴山下。', '天似穹庐，笼盖四野。', '天苍苍，野茫茫，', '风吹草低见牛羊。'],
    'cunju': ['草长莺飞二月天，拂堤杨柳醉春烟。', '儿童散学归来早，忙趁东风放纸鸢。'],
    'yongliu': ['碧玉妆成一树高，万条垂下绿丝绦。', '不知细叶谁裁出，二月春风似剪刀。'],
    'guyuancao': ['离离原上草，一岁一枯荣。', '野火烧不尽，春风吹又生。', '远芳侵古道，晴翠接荒城。', '又送王孙去，萋萋满别情。'],
    'jingcisi': ['毕竟西湖六月中，风光不与四时同。', '接天莲叶无穷碧，映日荷花别样红。'],
    'jueju-huangli': ['两个黄鹂鸣翠柳，一行白鹭上青天。', '窗含西岭千秋雪，门泊东吴万里船。'],
    'minnong1': ['春种一粒粟，秋收万颗子。', '四海无闲田，农夫犹饿死。'],
    'zhouyeshujian': ['月黑见渔灯，孤光一点萤。', '微微风簇浪，散作满河星。'],
    'suojian': ['牧童骑黄牛，歌声振林樾。', '意欲捕鸣蝉，忽然闭口立。'],
    'shanxing': ['远上寒山石径斜，白云生处有人家。', '停车坐爱枫林晚，霜叶红于二月花。'],
    'zengliujingwen': ['荷尽已无擎雨盖，菊残犹有傲霜枝。', '一年好景君须记，正是橙黄橘绿时。'],
    'yeshusuojian': ['萧萧梧叶送寒声，江上秋风动客情。', '知有儿童挑促织，夜深篱落一灯明。'],
    'wangtianmenshan': ['天门中断楚江开，碧水东流至此回。', '两岸青山相对出，孤帆一片日边来。'],
    'yinhushang': ['水光潋滟晴方好，山色空蒙雨亦奇。', '欲把西湖比西子，淡妆浓抹总相宜。'],
    'wangdongting': ['湖光秋月两相和，潭面无风镜未磨。', '遥望洞庭山水翠，白银盘里一青螺。'],
    'zaofabaidicheng': ['朝辞白帝彩云间，千里江陵一日还。', '两岸猿声啼不住，轻舟已过万重山。'],
    'cailianqu': ['荷叶罗裙一色裁，芙蓉向脸两边开。', '乱入池中看不见，闻歌始觉有人来。'],
    'jueju-chiri': ['迟日江山丽，春风花草香。', '泥融飞燕子，沙暖睡鸳鸯。'],
    'huichongchunjiang': ['竹外桃花三两枝，春江水暖鸭先知。', '蒌蒿满地芦芽短，正是河豚欲上时。'],
    'sanqudaozhong': ['梅子黄时日日晴，小溪泛尽却山行。', '绿阴不减来时路，添得黄鹂四五声。'],
    'yuanri': ['爆竹声中一岁除，春风送暖入屠苏。', '千门万户曈曈日，总把新桃换旧符。'],
    'qingming': ['清明时节雨纷纷，路上行人欲断魂。', '借问酒家何处有？牧童遥指杏花村。'],
    'jiuyuejiuri': ['独在异乡为异客，每逢佳节倍思亲。', '遥知兄弟登高处，遍插茱萸少一人。'],
    'chuzhouxijian': ['独怜幽草涧边生，上有黄鹂深树鸣。', '春潮带雨晚来急，野渡无人舟自横。'],
    'dalinsitaohua': ['人间四月芳菲尽，山寺桃花始盛开。', '长恨春归无觅处，不知转入此中来。'],
}

# 不规则字数说明（自行撰写）：这些篇目虽标五言/七言，但每联字数不是标准的
# 10/14 字。validate.py 会读这里的说明，把「已知不规则」与「疑似数据错误」区分开。
IRREGULAR_NOTE = {
    'yonge': '首句「鹅鹅鹅」为三字重叠，不足五言，故一联 8 字（传为五言古诗的变例）',
}

# 副标题（同名篇目消歧）
SUBTITLE = {
    'jueju-huangli': '两个黄鹂鸣翠柳',
    'jueju-chiri': '迟日江山丽',
    'minnong1': '其一',
    'minnong2': '其二',
}


def die(msg):
    print('[migrate] ERROR: ' + msg, file=sys.stderr)
    sys.exit(1)


def parse_poems_js(text):
    """从 poems.js 抽出 POEMS 数组。

    只取我们需要的字段，正则按 `{ id: '...' ... }` 的块匹配。
    """
    body = text[text.index('export const POEMS = ['):]
    body = body[:body.index('\n];')]
    poems = []
    # 以 "  { id: '" 为块起点
    blocks = re.split(r'\n(?=\s*\{ id: )', body)
    for blk in blocks:
        mid = re.search(r"\{ id: '([^']+)'", blk)
        if not mid:
            continue

        def field(name):
            # 值可能是 '引号字符串' 或裸数字；不能跨行匹配，否则会串到下一个字段
            m = re.search(r"\b%s:\s*(?:'([^']*)'|([^,\n]+))" % name, blk)
            if not m:
                return None
            return (m.group(1) if m.group(1) is not None
                    else m.group(2).strip())

        lines_blk = blk[blk.index('lines: ['):]
        lines_blk = lines_blk[:lines_blk.index(']')]
        lines = re.findall(r"'([^']*)'", lines_blk)

        # pairs 是 [[a, b], [c, d]]，切到第一个 ']' 会截断，必须按行取到结尾
        pm = re.search(r'pairs:\s*(\[\[.*?\]\])', blk)
        pairs = []
        if pm:
            pairs = [[int(a), int(b)] for a, b in
                     re.findall(r'\[(\d+),\s*(\d+)\]', pm.group(1))]

        poems.append(dict(
            id=mid.group(1),
            grade=int(field('grade')),
            title=field('title'),
            author=field('author'),
            dynasty=field('dynasty'),
            form=field('form'),
            lines=lines,
            pairs=pairs,
        ))
    return poems


# ---------------------------------------------------------------- 语义说明
#
# 【重要】游戏内 poems.js 的 lines是按逗号切开的**半句**，且pairs 只是把
# 同一个整句的两个半句配对（春晓 lines=['春眠不觉晓','处处闻啼鸟',...]，
# pairs=[[0,1],[2,3]] 表示 0/1 是同一整句的两半）。这不是"上下句"关系。
#
# 本仓采用**整句**为单位的正确模型：
#   lines  = 整句（游戏内半句按逗号合并回来）
#   pairs  = 联句配对（相邻两句构成一联，[[0,1],[2,3],...]）
#   render_split = 每整句在地面渲染时按逗号拆成几行（供游戏贴花层还原）
#
# 这样 canLink 查 pairs 才是真正的"联句"判定，而不是把半句当诗句。


def merge_halves(game_lines, punct_lines):
    """把游戏内的半句按标点版重新合并成整句，并记录渲染拆分份数。

    游戏内 lines 的切分规则不完全统一：多数诗按逗号切成半句，但有些诗
    （如《清明》）存的 4 行本身就不含逗号。先按标点版的逗号数优先匹配，
    匹配不上再退化为「按标点版句数均分」。

    返回 (整句列表, render_split 列表)，两者长度都等于 punct_lines。
    """
    n_game, n_poem = len(game_lines), len(punct_lines)
    if n_game == n_poem:
        return list(punct_lines), [1] * n_poem          # 游戏已按整句存
    if n_game < n_poem:
        die('游戏内 %d 行 < 数据层 %d 句，无法合并' % (n_game, n_poem))

    # 首选：按标点版的逗号段数分配
    split = []
    for pl in punct_lines:
        segs = len([x for x in pl.rstrip('。！？；').split('，') if x.strip()])
        split.append(max(1, segs))

    if sum(split) == n_game:
        return list(punct_lines), split

    # 退化：均分（游戏按另一种规则切分，如《清明》4 行不含逗号）
    base = n_game // n_poem
    rest = n_game - base * n_poem
    split = [base + (1 if i < rest else 0) for i in range(n_poem)]
    assert sum(split) == n_game
    return list(punct_lines), split


def derive_pairs(poem_lines):
    """联句配对：相邻两句为一联。

    [[0,1],[2,3],[4,5],...] —— 偶数首句起两两配对。
    奇数句时最后一句不配（留给玩家自由创作）。
    """
    pairs = []
    for i in range(0, len(poem_lines) - 1, 2):
        pairs.append([i, i + 1])
    return pairs


def fmt_list(xs):
    return '[' + ', '.join(xs) + ']'


def main():
    if not SRC.exists():
        die('找不到源文件 %s' % SRC)

    poems = parse_poems_js(SRC.read_text(encoding='utf-8'))
    print('[migrate] 解析到 %d 首' % len(poems))

    missing = [p['id'] for p in poems if p['id'] not in METADATA]
    if missing:
        die('以下 id 缺元数据：%s' % missing)
    missing_p = [p['id'] for p in poems if p['id'] not in PUNCT]
    if missing_p:
        die('以下 id 缺带标点正文：%s' % missing_p)

    CN = {1: '一', 2: '二', 3: '三'}
    written = 0
    split_notes = []

    for p in poems:
        m = METADATA[p['id']]
        punct = PUNCT[p['id']]

        # 把游戏内的半句合并回整句，并记录渲染拆分份数
        try:
            poem_lines, split = merge_halves(p['lines'], punct)
        except SystemExit:
            die('%s: 合并半句失败（游戏 %d 行 / 数据 %d 句）'
                % (p['title'], len(p['lines']), len(punct)))

        # 联句配对：按整句相邻两两配对
        pairs = derive_pairs(poem_lines)

        grade_cn = CN[p['grade']]
        dirname = POEMS_DIR / ('小学' if p['grade'] <= 6 else '初中') / m['volume']
        dirname.mkdir(parents=True, exist_ok=True)

        sub = SUBTITLE.get(p['id'])
        title_line = '# %s' % p['title']
        if sub:
            title_line = '# %s（%s）' % (p['title'], sub)

        fm = [
            '---',
            'id: %s' % p['id'],
            'title: %s' % p['title'],
            'subtitle: %s' % (sub if sub else 'null'),
            'author: %s' % p['author'],
            'dynasty: %s' % p['dynasty'],
            'form: %s' % p['form'],
            'stage: 小学',
            'grade: %d' % p['grade'],
            'volume: %s' % m['volume'],
            'textbooks: [统编]',
            'theme: %s' % fmt_list(m['theme']),
            'emotion: %s' % m['emotion'],
            'technique: %s' % fmt_list(m['technique']),
            'difficulty: %d' % m['difficulty'],
            'exam_freq: %s' % m['exam_freq'],
            'pairs: %s' % fmt_list(['%d-%d' % (a, b) for a, b in pairs]),
            'tags: [%s]' % ', '.join(m['theme'] + [p['dynasty'] + p['form']]),
            'source: S3+S1+S2',
            'license: public-domain',
            'copyright: { text: public-domain, annotations: cc-by-4.0 }',
            '---',
            '',
        ]
        if p['id'] in IRREGULAR_NOTE:
            fm.insert(-2, 'irregular: %s' % IRREGULAR_NOTE[p['id']])
        # 渲染层拆分提示：告诉贴花层每整句按逗号拆几行
        if any(x != 1 for x in split):
            fm.insert(-2, 'render_split: %s' % fmt_list([str(x) for x in split]))
            split_notes.append('%-10s %d 句 → 渲染 %d 行 %s'
                               % (p['title'], len(punct), len(p['lines']), split))

        body = [
            title_line,
            '',
            '> %s · %s · %s · %s'
            % (p['author'], p['dynasty'], p['form'],
               ('小学%s年级 · %s' % (grade_cn, m['volume']) if p['grade'] <= 6
                else m['volume'])),
            '',
        ]
        for ln in punct:
            body.append(ln)
            body.append('')
        body.append('## 注释')
        body.append('')
        body.append('- （待补：字词注释）')
        body.append('')
        body.append('## 译文')
        body.append('')
        body.append('（待补：白话译文）')
        body.append('')
        body.append('## 赏析')
        body.append('')
        body.append('（待补：文学常识与赏析）')
        body.append('')

        out = dirname / ('%s.md' % p['title'])
        out.write_text('\n'.join(fm + body), encoding='utf-8')
        written += 1
        print('  ✓ %s → %s' % (p['title'], out.relative_to(ROOT)))

    print('[migrate] 完成，写出 %d 篇' % written)
    if split_notes:
        print('\n[migrate] 以下篇目有渲染层拆分（供贴花层参考，请人工核对）：')
        for s in split_notes:
            print('  · %s' % s)
    print('\n[migrate] 注：注释/译文/赏析为占位，需后续人工撰写（CC BY 4.0）')


if __name__ == '__main__':
    main()