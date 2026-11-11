# MIT Admissions Blogs Crawler

使用 **Playwright** 和 **DrissionPage** 两种浏览器引擎，分别访问 MIT Admissions 博客列表和文章详情，独立导出 CSV。共用字段解析逻辑，不复制某个引擎的结果来冒充另一个引擎的抓取。

## 当前交付状态

- 两个真实 Chromium 浏览器引擎均已通过本地 HTTP 测试页面的导航和内容提取验证。
- 5 项解析及 CSV 测试通过。
- **尚未完成 MIT 网站的真实抓取与 DOM 选择器验证，尚无真实结果 CSV。** 当前云环境未允许访问 `mitadmissions.org`，代理返回 CONNECT 403。两个引擎均在访问 robots.txt 时失败，抓取文章数为 0。
- 已保存添加该域名的环境配置草稿，需在环境设置中审核、保存并发布后重新运行。如真实 DOM 与当前兼容选择器不一致，需要调整 `parser.py` 后再次验证。
- `tests/fixtures/article.html` 是明确标注的合成测试数据，不是 MIT 文章，不作为抓取结果提交。

## 安装

需要 Python 3.10+ 和 Chrome/Chromium。

```bash
cd mit-blogs-crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows 激活虚拟环境使用 `.venv\Scripts\activate`。

可以直接指定已安装的 Chrome/Chromium 路径：

```bash
python crawl.py --engine both --browser /usr/bin/chromium
```

程序也会尝试从 `CHROME_PATH` 环境变量、PATH 中的 `chromium` 或 `google-chrome` 查找浏览器。Playwright 支持其自带 Chromium（安装命令 `python -m playwright install chromium`）；DrissionPage 需要本机浏览器，建议两个引擎统一使用 `--browser`。

## 抓取与输出

默认只抓取**博客首页列出的全部文章**，不是整个历史归档。要增加范围，显式指定列表页数。

```bash
# 分别运行两个引擎，抓取首页文章
python crawl.py --engine both

# 最多抓取 3 个列表页中的前 30 篇文章，每个引擎独立运行
python crawl.py --engine both --pages 3 --limit 30 --delay 2

# 单独运行某个引擎
python crawl.py --engine playwright
python crawl.py --engine drissionpage
```

`--limit 0` 表示不限制所选列表页中的文章数量（默认值）。`--headed` 可显示浏览器窗口。顺序访问，默认每次导航前等待至少 1.5 秒，并遵循 robots.txt 的访问规则及 Crawl-delay。无法验证 robots.txt 时停止抓取。

每个成功引擎的结果独立保存为：

```text
results/
├── playwright.csv
├── playwright.run.json
├── drissionpage.csv
└── drissionpage.run.json
```

CSV 列名严格为：

```text
Title,Author,Comment Count,Time,Article Content,Images In Article
```

| 列名 | 数据格式 |
| --- | --- |
| Title | 文章标题 |
| Author | 作者；多个作者以分号分隔 |
| Comment Count | 页面明确提供的评论数量；不可获取时留空并在运行记录中警告 |
| Time | 网站提供的发布时间，优先使用机器可读的发布时间，保留原始时区 |
| Article Content | 文章正文纯文本，保留换行，排除评论区和分享组件 |
| Images In Article | 正文中图片的绝对 URL，以 JSON 数组写入一个单元格；无图片为 `[]` |

图片仅保存链接，不下载图片文件。CSV 使用 UTF-8 BOM，便于 Excel 打开；逗号、引号和换行由 Python `csv` 模块正确转义。

运行记录包含抓取时间、实际访问的列表页、成功 CSV 行号对应的文章 URL、缺失字段警告及错误。如果有文章失败，会保存成功行并返回非零退出码；若没有成功行，则不会创建 CSV，也不会用空结果覆盖之前的 CSV。因此判断本次运行结果时应查看 `.run.json` 中的 `csv_written_this_run`、`rows` 和 `errors`。

`results/` 默认不提交到 Git。真实抓取及核验完成后，提交 CSV 可使用：

```bash
git add -f results/playwright.csv results/drissionpage.csv \
  results/playwright.run.json results/drissionpage.run.json
```

## 验证

```bash
# 本地解析、去重、CSV 转义、缺失字段及失败行为
python -m unittest discover -s tests -v

# 两个真实浏览器加载本地 HTTP 测试页面并提取字段
# 需要 Chrome/Chromium，必要时设置 CHROME_PATH
PYTHONPATH=. python tests/browser_smoke.py
```

## 实现

- `browsers.py`：Playwright 与 DrissionPage 独立浏览器适配器，支持环境代理。
- `parser.py`：发现文章链接、分页，解析结构化元数据及文章 DOM，提取正文图片并去重。
- `crawl.py`：robots.txt 检查、范围限制、请求间隔、错误记录、CSV 原子写入与运行记录。

遇到网络错误、HTTP 错误、缺少必要字段或页面结构不匹配时，会记录错误，不把错误页当作文章。此项目不处理登录、验证码或反爬绕过。
