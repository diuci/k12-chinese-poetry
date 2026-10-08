#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量生成篇目 Markdown —— 初中剩余篇目（八年级上/下册为主）。

与 gen-middle.py 分批的原因：单文件太长不便审阅，拆成两批。
第一批（gen-middle.py）收了七年级与九年级共 37 篇；
本文件收八年级与初中剩余篇目。

**只收真正缺失的篇目**——已在第一批或小学批次收录的一律不重复收录。
文言文一律名句化：`lines` 只放课标要求背诵的名句，多为对举，
与诗词完全同构；全文另存正文供学习。

用法：
    python tools/gen-middle2.py
    python tools/gen-middle2.py --dry
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POEMS_DIR = ROOT / 'poems' / '初中'

DATA = [
    # ==================== 八年级上册 · 文言 ====================
    dict(id='sanxia', grade=8, volume='八年级上册', title='三峡', author='郦道元', dyn='北魏',
         form='文言', theme=['山水', '写景'], emo='三峡四时之景的雄奇',
         tech=['白描', '对比'], diff=4, freq=0.9, recite='section',
         lines=['自三峡七百里中，两岸连山，略无阙处。',
                '重岩叠嶂，隐天蔽日。',
                '虽乘奔御风，不以疾也。']),

    dict(id='daxiezhongshu', grade=8, volume='八年级上册', title='答谢中书书',
         author='陶弘景', dyn='南朝', form='文言', theme=['山水', '抒情'],
         emo='沉醉山水的愉悦与归隐之志', tech=['白描', '对比'],
         diff=4, freq=0.9, recite='section',
         lines=['山川之美，古来共谈。', '高峰入云，清流见底。',
                '两岸石壁，五色交辉。', '青林翠竹，四时俱备。']),

    dict(id='jichengtiansi', grade=8, volume='八年级上册', title='记承天寺夜游',
         author='苏轼', dyn='宋', form='文言', theme=['贬谪', '闲适'],
         emo='赏月的欣喜与贬谪的清闲', tech=['比喻', '侧面描写'],
         diff=4, freq=1.0, recite='section',
         lines=['庭下如积水空明，水中藻、荇交横，盖竹柏影也。',
                '何夜无月？何处无竹柏？但少闲人如吾两人者耳。']),

    dict(id='yuzhusianshu', grade=8, volume='八年级上册', title='与朱元思书',
         author='吴均', dyn='南朝', form='文言', theme=['山水', '抱负'],
         emo='寄情山水的高洁志趣', tech=['白描', '侧面描写'],
         diff=4, freq=0.9, recite='section',
         lines=['风烟俱净，天山共色。', '泉水激石，泠泠作响。',
                '任意东西，怡然自乐。']),

    # ==================== 八年级下册 · 文言 ====================
    dict(id='taohuayuanji', grade=8, volume='八年级下册', title='桃花源记',
         author='陶潜', dyn='晋', form='文言', theme=['田园', '避世'],
         emo='避世桃源的神秘与向往', tech=['白描', '虚实结合'],
         diff=5, freq=1.0, recite='section',
         lines=['土地平旷，屋舍俨然。', '阡陌交通，鸡犬相闻。',
                '其中往来种作，男女衣着，悉如外人。',
                '黄发垂髫，并怡然自乐。']),

    dict(id='xiaoshitan', grade=8, volume='八年级下册', title='小石潭记',
         author='柳宗元', dyn='唐', form='文言', theme=['山水', '游记'],
         emo='赏潭乐的愉悦与失意的悲慨', tech=['比喻', '情景交融'],
         diff=4, freq=0.9, recite='section',
         lines=['小石潭水清见底。', '闻水声，如鸣珮环。',
                '青树翠蔓，蒙络摇缀。', '日光下澈，影布石上。',
                '俶尔远逝，往来翕忽。']),

    dict(id='beimingyouyu', grade=8, volume='八年级下册', title='北冥有鱼',
         author='庄子', dyn='战国', form='文言', theme=['神话', '哲理'],
         emo='宇宙无边的想象与追求', tech=['比喻', '想象'],
         diff=4, freq=0.8, recite='section',
         lines=['北冥有鱼，其名为鲲。', '鲲之大，不知其几千里也。',
                '化而为鸟，其名为鹏。', '鹏之背，不知其几千里也。']),

    dict(id='suoyoujiayao', grade=8, volume='八年级下册', title='虽有嘉肴',
         author='佚名', dyn='先秦', form='文言', theme=['修身', '哲理'],
         emo='重视学习与朋友的价值', tech=['比喻', '对比'],
         diff=4, freq=0.9, recite='full',
         lines=['虽有嘉肴，弗食，不知其旨也。', '虽有至道，弗学，不知其善也。',
                '是故无冥明之察。', '善哉，答是。']),

    dict(id='dadaozhixing', grade=8, volume='八年级下册', title='大道之行也',
         author='佚名', dyn='先秦', form='文言', theme=['礼制', '理想'],
         emo='对大同世界的向往', tech=['排比', '铺陈'],
         diff=4, freq=0.9, recite='section',
         lines=['大道之行也，天下为公。', '选贤与能，讲信修睦。',
                '故人不独亲其亲，不独子其子。', '是谓大同。']),

    dict(id='masuo', grade=8, volume='八年级下册', title='马说', author='韩愈', dyn='唐',
         form='文言', theme=['讽喻', '人才'], emo='对人才被埋没的愤慨',
         tech=['托物言志', '比喻'], diff=4, freq=0.9, recite='section',
         lines=['千里马常有，而伯乐不常有。',
                '其真无马邪？其真不知马也！']),

    dict(id='shihaoli', grade=8, volume='八年级下册', title='石壕吏', author='杜甫', dyn='唐',
         form='文言', theme=['民生', '战乱'], emo='对安史之乱中百姓苦难的悲悯',
         tech=['对话', '细节'], diff=5, freq=0.7, recite='none',
         lines=['暮投石壕村，有吏夜捉人。',
                '老翁逾墙走，老妇出门看。']),

    # ==================== 课外古诗词诵读（初中） ====================
    dict(id='songshaoshu-wai', grade=8, volume='八年级下册课外诵读', title='送杜少府之任蜀州',
         author='王勃', dyn='唐', form='五言', theme=['送别', '友情'],
         emo='豁达乐观的送别', tech=['对偶', '直抒胸臆'],
         diff=4, freq=0.9, recite='full',
         lines=['城阙辅三秦，风烟望五津。', '与君离别意，同是宦游人。',
                '海内存知己，天涯若比邻。', '无为在歧路，儿女共沾巾。']),

    dict(id='zhuliguan', grade=7, volume='七年级课外诵读', title='竹里馆', author='王维', dyn='唐',
         form='五言', theme=['隐逸', '月亮'], emo='独居幽谷的清寂',
         tech=['拟人', '意象'], diff=3, freq=0.5, recite='full',
         lines=['独坐幽篁里，弹琴复长啸。', '深林人不知，明月来相照。']),

    dict(id='chunyeluocheng', grade=7, volume='七年级课外诵读', title='春夜洛城闻笛',
         author='李白', dyn='唐', form='七言', theme=['思乡', '音乐'],
         emo='客洛阳的思乡之愁', tech=['想象', '对比'],
         diff=4, freq=0.6, recite='full',
         lines=['谁家玉笛暗飞声，散入春风满洛城。',
                '此夜曲中闻折柳，何人不起故园情。']),

    dict(id='fengrujinshi', grade=7, volume='七年级课外诵读', title='逢入京使',
         author='岑参', dyn='唐', form='七言', theme=['思乡', '边塞'],
         emo='远赴边塞的思乡', tech=['对比', '细节'],
         diff=4, freq=0.6, recite='full',
         lines=['故园东望路漫漫，双袖龙钟泪不干。',
                '马上相逢无纸笔，凭君传语报平安。']),

    dict(id='wanchun', grade=7, volume='七年级课外诵读', title='晚春', author='韩愈', dyn='唐',
         form='七言', theme=['春天', '哲理'], emo='爱春惜春的情怀',
         tech=['拟人', '议论'], diff=4, freq=0.6, recite='full',
         lines=['草树知春不久归，百般红紫斗芳菲。',
                '杨花榆荚无才思，惟解漫天作雪飞。']),

    dict(id='yewang', grade=8, volume='八年级上册课外诵读', title='野望', author='王绩', dyn='唐',
         form='五言', theme=['田园', '孤独'], emo='独居山中的闲适与孤独',
         tech=['白描', '对偶'], diff=4, freq=0.7, recite='full',
         lines=['东皋薄暮望，徙倚欲何依。', '树树皆秋色，山山唯落晖。',
                '牧人驱犊返，猎马带禽归。', '相顾无相识，长歌怀采薇。']),

    dict(id='shiwei', grade=8, volume='八年级下册课外诵读', title='式微', author='佚名', dyn='先秦',
         form='诗经', theme=['挽歌', '哀叹'], emo='对国家衰败的哀叹',
         tech=['比兴', '重章叠句'], diff=4, freq=0.5, recite='line',
         lines=['式微，式微，胡不归？', '微君之故，胡为乎中露？']),

    dict(id='zijin', grade=8, volume='八年级下册课外诵读', title='子衿', author='佚名', dyn='先秦',
         form='诗经', theme=['爱情', '思念'], emo='对爱人的思念与愁苦',
         tech=['重章叠句', '比兴'], diff=3, freq=0.5, recite='line',
         lines=['青青子衿，悠悠我心。', '纵我不往，子宁不嗣音？']),
]


def die(msg):
    print('[gen] ERROR: ' + msg, file=sys.stderr)
    sys.exit(1)


def main():
    dry = '--dry' in sys.argv
    ids = [d['id'] for d in DATA]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        die('id 重复：%s' % dup)

    if dry:
        print('[gen] --dry：%d 篇待生成' % len(DATA))
        return

    written = 0
    for d in DATA:
        lines = d['lines']
        n = len(lines)
        pairs = ['%d-%d' % (i, i + 1) for i in range(0, n - 1, 2)]
        split = [max(1, len([x for x in l.rstrip('。！？；').split('，') if x.strip()]))
                 for l in lines]

        sub = d.get('sub')
        fm = [
            '---',
            'id: %s' % d['id'],
            'title: %s' % d['title'],
            'subtitle: %s' % (sub if sub else 'null'),
            'author: %s' % d['author'],
            'dynasty: %s' % d['dyn'],
            'form: %s' % d['form'],
            'stage: 初中',
            'grade: %d' % d['grade'],
            'volume: %s' % d['volume'],
            'textbooks: [统编]',
            'recite: %s' % d.get('recite', 'line'),
            'theme: [%s]' % ', '.join(d['theme']),
            'emotion: %s' % d['emo'],
            'technique: [%s]' % ', '.join(d['tech']),
            'difficulty: %d' % d['diff'],
            'exam_freq: %s' % d['freq'],
            'pairs: [%s]' % ', '.join(pairs),
            'tags: [%s]' % ', '.join(d['theme'] + [d['dyn'] + d['form']]),
            'source: S3+S1+S2',
            'license: public-domain',
            'copyright: { text: public-domain, annotations: cc-by-4.0 }',
            '---',
            '',
        ]
        if any(x != 1 for x in split):
            fm.insert(-2, 'render_split: [%s]' % ', '.join(str(x) for x in split))

        head = '# %s%s' % (d['title'], ('（%s）' % sub) if sub else '')
        body = [
            head, '',
            '> %s · %s · %s · 初中 · %s' % (d['author'], d['dyn'], d['form'], d['volume']),
            '',
            '## 必背%s' % ('全文' if d.get('recite') == 'full' else '名句'),
            '',
        ]
        for l in lines:
            body.append(l)
            body.append('')
        body += [
            '## 注释', '', '- （待补：字词注释）', '',
            '## 译文', '', '（待补：白话译文）', '',
            '## 赏析', '', '（待补：文学常识与赏析）', '',
        ]

        out = POEMS_DIR / d['volume'] / ('%s.md' % d['title'])
        if out.exists():
            print('  ! 跳过（已存在）%s' % out.relative_to(ROOT))
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text('\n'.join(fm + body), encoding='utf-8')
        written += 1
        print('  ✓ %s %s' % (d['volume'], d['title']))

    print('[gen] 写出 %d 篇' % written)


if __name__ == '__main__':
    main()