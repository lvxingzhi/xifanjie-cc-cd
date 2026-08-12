# UI 调整记录（v2：回归 LearnHub demo 语言）

> 参考站：https://ui-ux-pro-max-skill.nextlevelbuilder.io/demo/educational-platform
> 用户明确：模仿该站色系、色彩运用与占比；排版可自由改，data 展示好即可。

## 结论：之前方向错误

第一版把主色换成琥珀金是错误方向。用户喜欢的正是 demo 的**珊瑚粉 + 天蓝 + 绿 + 薄荷 + 淡紫**体系，
问题从来不在色相，而在**占比**——原站大面积奶油底 + 白卡，彩色只在小图标块/按钮/标签小面积出现。

## 最终色板（与 demo 一致）

```css
--primary: #FDBCB4        /* 珊瑚粉：logo 方块、lang 激活、表头、hover */
--primary-dark: #F5A69D
--primary-soft: #FFF0EE   /* 表头底、hover 底 */
--secondary: #ADD8E6      /* 天蓝：次要按钮、汉堡 */
--cta: #22C55E            /* 绿：CTA、打断标签、BOSS */
--accent-purple: #E6E6FA  /* 淡紫：统计块 */
--accent-mint: #98FF98    /* 薄荷：统计块 */
--bg: #FFFFFF             /* 卡片底 */
--bg-cream: #FFF9F5       /* 页面底 */
--text: #2D3748           /* 深灰蓝（非纯黑） */
--text-muted: #64748B
--border: #E2E8F0
```

## clay 卡片（demo 同款）

```css
.clay-card {
  border-radius: 24px;
  border: 3px solid var(--text);
  box-shadow: 6px 6px 0 var(--text), inset 0 -4px rgba(0,0,0,.08);
}
.clay-hover:hover { box-shadow: 4px 4px 0; transform: translate(2px,2px); }
.btn-primary { 绿底白字 3px 边 4px 4px 0 硬阴影 }
```

## 排版（index.html）

1. 悬浮导航（clay-card 胶囊条）：logo 珊瑚粉方块 + 品牌 + 链接 + lang 切换 + 绿色 CTA
2. Hero 双栏：左 = 大标题 + 副标题 + 按钮组（绿 CTA/蓝卡片）+ 更新日期；
   右 = 统计 2×2（彩色小方块 icon + 大数字 + 小标签，demo 课程卡样式）
3. 工具栏 clay-card：赛季/副本/搜索/仅打断/仅魔法/列设置/计数
4. 表格 clay-card：表头淡珊瑚、斑马纹、hover 淡珊瑚；标签 pill 无边框，
   打断=实心绿白字，其余浅底深字
5. 页脚一行

## 删减（用户确认）

- 成就墙、等级徽章、进度条 → 已删（无解释成本的游戏化元素）
- emoji 图标块 → 换纯色小方块
- 格子纸背景 → 去掉（demo 无）

## 字体

- 标题：Fredoka（demo 同款，中文 fallback PingFang SC）
- 正文：Nunito（demo 同款）

## 待用户反馈

- hero 三个小有机 blob（薄荷/淡紫/天蓝）是否保留（用户曾说不想要气泡装饰）
- 语义标签色（加深版：蓝/橙/红/黄绿/灰橄榄/紫）是否 OK，还是想更接近 demo 淡色系
