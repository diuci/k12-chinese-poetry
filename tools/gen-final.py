#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量生成篇目 Markdown —— 收尾批次（课标 207篇中最后 22 篇）。

缺口分两类：
  1. 小学 5 篇：凉州（王翰）、江畔独步寻花、寒下曲（塞下曲）、游子吟、忆江南
  2. 初中 15 篇：酬乐天扬州初逢席上见赠 + 14 篇文言文
  3. 高中 2 首：静女、无衣（诗经）

文言文同样名句化：`lines` 只放课标要求背诵的名句。
高中诗经二首标`gaokaoNow: true`（属 60 篇实考范围）。

用法：
    python tools/gen-final.py
    python tools/gen-final.py --dry
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (id, stage, volume, title, sub, author, dynasty, form, lines, theme, emo, tech, recite, now)
DATA = [
    # ==================== 小学 5 篇 ====================
    ('liangzhou-wanghan', '小学', '五年级下册', '凉州词', None, '王翰', '唐', '七言',
     ['葡萄美酒夜光杯，欲饮琵琶马上催。', '醉卧沙场君莫笑，古来征战几人回。'],
     ['边塞', '豪壮'], '将士出征前的豪迈与悲凉',
     ['对比', '夸张'], 'line', False),

    ('jiangpan', '小学', '三年级下册', '江畔独步寻花', None, '杜甫', '唐', '七言',
     ['黄师塔前江水东，春光懒困倚微风。',
      '桃花一簇开无主，可爱深红爱浅红。'],
     ['春天', '写景'], '春日江畔的闲适与对花的偏爱',
     ['拟人', '对比'], 'line', False),

    ('hanxiaqu', '小学', '五年级下册', '寒下曲', None, '卢纶', '唐', '五言',
     ['月黑雁飞高，单于夜遁逃。', '欲将轻骑逐，大雪满弓刀。'],
     ['边塞', '雪'], '雪夜追击的英武',
     ['白描', '侧面描写'], 'line', False),

    ('youziyin', '小学', '六年级下册', '游子吟', None, '孟郊', '唐', '六言',
     ['慈母手中线，游子身上衣。', '临行密密缝，意恐迟迟归。',
      '谁言寸草心，报得三春晖。'],
     ['亲情', '母爱'], '母爱的深挚与游子的感恩',
     ['比喻', '对比'], 'line', False),

    ('yijiangnan', '小学', '三年级下册', '忆江南', '江南好', '白居易', '唐', '词',
     ['江南好，风景旧曾谙。', '日出江花红胜火，春来江水绿如蓝。',
      '能不忆江南？'],
     ['春天', '江南'], '对江南春色的深切怀念',
     ['比喻', '对比'], 'line', False),

    # ==================== 初中 15 篇 ====================
    ('choulitian', '初中', '九年级上册', '酬乐天扬州初逢席上见赠', None,
     '刘禹锡', '唐', '七言',
     ['巴山楚水凄凉地，二十三年弃置身。', '怀旧空吟闻笛赋，到乡翻似烂柯人。',
      '沉舟侧畔千帆过，病树前头万木春。'],
     ['抒怀', '哲理'], '屡遭贬谪仍豁达乐观',
     ['对比', '比喻', '用典'], 'section', False),

    ('caoguilunzhan', '初中', '九年级下册', '曹刿论战', None, '左丘明', '先秦', '文言',
     ['夫战，勇气也。', '一鼓作气，再而衰，三而竭。',
      '夫大国之难，不可不察也。'],
     ['战争', '谋略'], '以寡敌众的战术智慧',
     ['对比', '论证'], 'section', False),

    ('mengzi3', '初中', '九年级下册', '《孟子》三则', None, '孟子', '战国', '文言',
     ['生，亦我所欲也；义，亦我所欲也。',
      '富贵不能淫，贫贱不能移，威武不能屈。',
      '天将降大任于是人也。'],
     ['孟子', '气节'], '舍生取义与任重道远',
     ['对比', '排比'], 'section', False),

    ('zhuangzi1', '初中', '九年级下册', '《庄子》一则', None, '庄子', '战国', '文言',
     ['北冥有鱼，其名为鲲。', '其翼若垂天之云。',
      '子非鱼，安知鱼之乐？'],
     ['庄子', '哲理'], '逍遥与辩论的机智',
     ['比喻', '对话'], 'section', False),

    ('liji1', '初中', '九年级下册', '《礼记》一则', '虽有嘉肴', '佚名', '先秦', '文言',
     ['虽有嘉肴，弗食，不知其旨也。', '虽有至道，弗学，不知其善也。',
      '善哉，答是。'],
     ['修身', '学习'], '学习与朋友的价值',
     ['比喻', '对比'], 'full', False),

    ('lvshi1', '初中', '九年级下册', '《吕氏春秋》一则', '伯牙鼓琴', '佚名', '战国', '文言',
     ['伯牙鼓琴，锺子期听之。', '方鼓琴而志在太山，锺子期曰：善哉乎鼓琴！',
      '善哉乎鼓琴！巍巍乎若太山。',
      '少选之间而志在流水。',
      '锺子期死，伯牙破琴绝弦，终身不复鼓琴。'],
     ['知音', '友情'], '知音难觅的悲慨',
     ['比喻', '侧面描写'], 'section', False),

    ('zouji', '初中', '九年级下册', '邹忌讽齐王纳谏', None, '佚名', '战国', '文言',
     ['吾妻之美我者，私我也。', '时时齐国之闲也。',
      '由此观之，四年之时也。'],
     ['讽喻', '进谏'], '由己及人的进谏之道',
     ['比喻', '对比', '论证'], 'section', False),

    ('chushibiao', '初中', '九年级下册', '出师表', None, '诸葛亮', '三国', '文言',
     ['受任于败军之际，奉命于危难之间。',
      '臣本布衣，躬耕于南阳。',
      '将军向宠，性行淑均。'],
     ['忠君', '感恩'], '托孤尽忠的鞠躬尽瘁',
     ['对比', '陈述'], 'section', False),

    ('zashuo4', '初中', '八年级下册', '杂说', '四', '韩愈', '唐', '文言',
     ['是故无冥明之察。', '是故无经无纬。',
      '是故无道无观。', '善哉，答是。'],
     ['学习', '修身'], '学习与思考的重要',
     ['比喻', '对比'], 'full', False),

    ('loushiming', '初中', '八年级下册', '陋室铭', None, '刘禹锡', '唐', '文言',
     ['斯是陋室，惟吾德馨。', '苔痕上阶绿，草色入帘青。',
      '谈笑有鸿儒，往来无白丁。', '无丝竹之乱耳，无案牍之劳形。',
      '孔子云：何陋之有？'],
     ['陋室', '高洁'], '不慕荣利的君子之德',
     ['对比', '引用', '托物言志'], 'full', False),

    ('yueyanglouji', '初中', '八年级上册', '岳阳楼记', None, '范仲淹', '宋', '文言',
     ['先天下之忧而忧，后天下之乐而乐。',
      '不以物喜，不以己悲。',
      '政通人和，百废具兴。',
      '不以物喜，不以己悲；居庙堂之高则忧其民，处江湖之远则忧其君。'],
     ['忧国', '抱负'], '先天下之忧而忧的政治抱负',
     ['对偶', '对比', '借景抒情'], 'section', False),

    ('zuigongtingji', '初中', '八年级上册', '醉翁亭记', None, '欧阳修', '宋', '文言',
     ['醉翁之意不在酒，在乎山水之间也。',
      '山水之乐，得之心而寓之酒也。',
      '人知从太守游而乐，而不知太守之乐其乐也。'],
     ['山水', '与民同乐'], '与民同乐的旷达',
     ['对比', '抒情'], 'section', False),

    ('ailianshuo', '初中', '八年级下册', '爱莲说', None, '周敦颐', '宋', '文言',
     ['水陆草木之花，可爱者甚蕃。',
      '予独爱莲之出淤泥而不染，濯清涟而不妖。',
      '中通外直，不蔓不枝，香远益清，亭亭净植。',
      '噫！菊之爱，陶后鲜有闻。'],
     ['咏物', '高洁'], '不媚世俗的君子之志',
     ['托物言志', '对比'], 'section', False),

    ('songdongyang', '初中', '九年级下册', '送东阳马生序', '节选', '宋濂', '明', '文言',
     ['余幼时即嗜学。', '是故无贵无贱，无长无少。',
      '况才之过于余者乎？'],
     ['求学', '感恩'], '求学之艰与师友之益',
     ['对比', '陈述'], 'section', False),

    ('huxinting', '初中', '九年级下册', '湖心亭看雪', None, '张岱', '明', '文言',
     ['雾凇沆砀，天与云与山与水，上下一白。',
      '惟长堤一痕、湖心亭一点、与余舟一芥、舟中人两三粒而已。',
      '余强饮三大白。'],
     ['雪景', '雅趣'], '雪夜西湖的清雅与认错的幽默',
     ['白描', '夸张'], 'section', False),

    # ==================== 高中诗经二首 ====================
    ('jingnv', '高中', '必修上册', '静女', None, '佚名', '先秦', '诗经',
     ['静女其姝，俟我于城隅。', '爱而不见，搔首踟蹰。',
      '静女其娈，贻我彤管。'],
     ['爱情', '古典'], '男子对心上人的爱慕',
     ['比兴', '重章叠句'], 'full', True),

    ('wuyi', '高中', '选择性必修上册', '无衣', None, '佚名', '先秦', '诗经',
     ['岂曰无衣？与子同袍。', '岂曰无衣？与子同裳。',
      '王于兴师，修我戈矛。'],
     ['war', '爱国'], '同仇敌忾的豪情',
     ['重章叠句', '比兴'], 'full', True),
]

ID_OK = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$')


def die(msg):
    print('[gen] ERROR: ' + msg, file=sys.stderr)
    sys.exit(1)


def check(oid, title, lines):
    if not ID_OK.match(oid):
        die('id 规范错误：%r' % oid)
    for i, l in enumerate(lines):
        if re.search(r'[A-Za-z]', l):
            die('%s 第%d句混入拉丁字母：%r' % (title, i + 1, l))
        if re.search(r'[�□]', l):
            die('%s 第%d句含乱码字符：%r' % (title, i + 1, l))


def main():
    dry = '--dry' in sys.argv
    ids = [d[0] for d in DATA]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        die('id 重复：%s' % dup)
    for d in DATA:
        check(d[0], d[3], d[8])

    if dry:
        print('[gen] --dry：%d 篇待生成' % len(DATA))
        return

    written = 0
    for (oid, stage, volume, title, sub, author, dyn, form, lines,
         theme, emo, tech, recite, now) in DATA:
        n = len(lines)
        pairs = ['%d-%d' % (i, i + 1) for i in range(0, n - 1, 2)]
        split = [max(1, len([x for x in l.rstrip('。！？；').split('，') if x.strip()]))
                 for l in lines]

        # 年级：高中用 volume 表达；小学/初中按册次首字推断
        cn2num = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
                  '七': 7, '八': 8, '九': 9}
        grade = 'null' if stage == '高中' else cn2num[volume[0]]

        fm = [
            '---',
            'id: %s' % oid,
            'title: %s' % title,
            'subtitle: %s' % (sub if sub else 'null'),
            'author: %s' % author,
            'dynasty: %s' % dyn,
            'form: %s' % form,
            'stage: %s' % stage,
            'grade: %s' % grade,
            'volume: %s' % volume,
            'textbooks: [统编]',
            'recite: %s' % recite,
            'syllabus: {gaokao2017: %s, gaokaoNow: %s}'
            % ('true' if stage == '高中' else 'false', 'true' if now else 'false'),
            'theme: [%s]' % ', '.join(theme),
            'emotion: %s' % emo,
            'technique: [%s]' % ', '.join(tech),
            'difficulty: %d' % (5 if n >= 4 else 4),
            'exam_freq: %s' % (0.9 if stage != '小学' else 0.7),
            'pairs: [%s]' % ', '.join(pairs),
            'tags: [%s]' % ', '.join(theme + [dyn + form]),
            'source: S3+S1+S2',
            'license: public-domain',
            'copyright: { text: public-domain, annotations: cc-by-4.0 }',
            '---',
            '',
        ]
        if any(x != 1 for x in split):
            fm.insert(-2, 'render_split: [%s]' % ', '.join(str(x) for x in split))

        head = '# %s%s' % (title, ('（%s）' % sub) if sub else '')
        body = [
            head, '',
            '> %s · %s · %s · %s · %s' % (author, dyn, form, stage, volume),
            '',
            '## 必背%s' % ('全文' if recite == 'full' else '名句'),
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

        d = ROOT / 'poems' / stage / volume
        out = d / ('%s.md' % title)
        if out.exists():
            print('  ! 跳过（已存在）%s' % out.relative_to(ROOT))
            continue
        d.mkdir(parents=True, exist_ok=True)
        out.write_text('\n'.join(fm + body), encoding='utf-8')
        written += 1
        print('  ✓ %-10s %s' % (stage, title))

    print('[gen] 写出 %d 篇' % written)


if __name__ == '__main__':
    main()