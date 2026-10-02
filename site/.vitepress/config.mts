import { defineConfig } from 'vitepress'

// 部署到 GitHub Pages 项目页时 base 为 /<repo>/；
// 若绑定了自定义域名 k12.diuci.com，则改为 '/'。
const base = process.env.SITE_BASE || '/k12-chinese-poetry/'

export default defineConfig({
  base,
  lang: 'zh-CN',
  title: 'K12 中文古诗文',
  titleTemplate: ':title | K12 中文古诗文',
  description: '小学到高中必背古诗文，按义务教育与高中课程标准收录。原文公有领域，注释译文赏析 CC BY 4.0。',

  // 搜索：内置 minisearch，中文按字切分，无需额外分词库
  themeConfig: {
    nav: [
      { text: '总览', link: '/' },
      { text: '按学段', link: '/poems/小学/一年级上册/春晓' },
      { text: '打印版', link: '/print' },
      { text: '家长指南', link: '/guide' },
      { text: '数据来源', link: '/sources' },
    ],

    sidebar: [
      {
        text: '开始',
        items: [
          { text: '总览', link: '/' },
          { text: '打印版', link: '/print' },
          { text: '家长指南', link: '/guide' },
          { text: '数据来源与版权', link: '/sources' },
        ],
      },
      {
        text: '小学',
        collapsed: false,
        items: [
          { text: '一年级上册', link: '/poems/小学/一年级上册/春晓' },
          { text: '一年级下册', link: '/poems/小学/一年级下册/静夜思' },
          { text: '二年级上册', link: '/poems/小学/二年级上册/敕勒歌' },
          { text: '二年级下册', link: '/poems/小学/二年级下册/咏柳' },
          { text: '三年级上册', link: '/poems/小学/三年级上册/望天门山' },
          { text: '三年级下册', link: '/poems/小学/三年级下册/元日' },
          { text: '四年级上册', link: '/poems/小学/四年级上册/鹿柴' },
          { text: '四年级下册', link: '/poems/小学/四年级下册/芙蓉楼送辛渐' },
          { text: '五年级上册', link: '/poems/小学/五年级上册/山居秋暝' },
          { text: '五年级下册', link: '/poems/小学/五年级下册/凉州词' },
          { text: '六年级上册', link: '/poems/小学/六年级上册/宿建德江' },
          { text: '六年级下册', link: '/poems/小学/六年级下册/竹石' },
        ],
      },
      {
        text: '初中',
        collapsed: true,
        items: [
          { text: '七年级', link: '/poems/初中/七年级上册/观沧海' },
          { text: '八年级', link: '/poems/初中/八年级上册/三峡' },
          { text: '九年级', link: '/poems/初中/九年级上册/沁园春' },
        ],
      },
      {
        text: '高中',
        collapsed: true,
        items: [
          { text: '必修上册', link: '/poems/高中/必修上册/劝学' },
          { text: '必修下册', link: '/poems/高中/必修下册/赤壁赋' },
          { text: '选择性必修', link: '/poems/高中/选择性必修上册/过秦论' },
        ],
      },
    ],

    search: {
      provider: 'local',
      options: {
        detailedView: true,
        miniSearch: {
          searchOptions: {
            fuzzy: 0.2,
            prefix: true,
            boost: { title: 4, author: 2, lines: 2 },
          },
        },
      },
    },

    outline: { level: [2, 3], label: '本页目录' },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/diuci/k12-chinese-poetry' },
    ],

    footer: {
      message: '诗文原文属公有领域；注释、译文、赏析与选篇编排 © 丢词大作战，采用 CC BY 4.0。',
      copyright: '内容来源与授权说明见「数据来源与版权」。',
    },

    lastUpdated: true,
    docFooter: { prev: '上一篇', next: '下一篇' },
  },
})
