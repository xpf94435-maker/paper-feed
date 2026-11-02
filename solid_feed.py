"""Solid-electrolyte RSS configuration and reading page."""
import datetime
import html
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
import get_RSS as rss

KEYWORDS = '''solid electrolyt
solid-state electrolyt
solid state electrolyt
solid-electrolyte
solid polymer electrolyt
solid-state batter
solid state batter
all-solid-state
all solid state
superionic conductor
sulfide electrolyt
sulphide electrolyt
halide electrolyt
argyrodite
NASICON
LISICON
LLZO
LAGP
LATP
Li6PS5
polymer AND ionic conduct
oxide AND ionic conduct
halide AND ionic conduct
sulfide AND ionic conduct
sodium AND ionic conduct
lithium AND ionic conduct
'''
SOURCES = '''https://www.nature.com/nenergy.rss
https://www.nature.com/nmat.rss
https://www.nature.com/ncomms.rss
https://www.nature.com/nchem.rss
https://www.nature.com/natrevmats.rss
https://www.nature.com/commsmat.rss
https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=aelccp
https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=jacsat
https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=cmatex
https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=acsami
https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=acssce
https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=jpclcd
https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=jpccck
https://advanced.onlinelibrary.wiley.com/feed/15214095/most-recent
https://advanced.onlinelibrary.wiley.com/feed/16163028/most-recent
https://onlinelibrary.wiley.com/feed/16146840/most-recent
https://onlinelibrary.wiley.com/feed/15213773/most-recent
https://advanced.onlinelibrary.wiley.com/feed/21983844/most-recent
https://onlinelibrary.wiley.com/feed/16136829/most-recent
https://feeds.rsc.org/rss/ee
https://feeds.rsc.org/rss/ta
https://feeds.rsc.org/rss/sc
https://rss.sciencedirect.com/publication/science/01672738
https://rss.sciencedirect.com/publication/science/03787753
https://rss.sciencedirect.com/publication/science/24058297
https://rss.sciencedirect.com/publication/science/22112855
https://rss.sciencedirect.com/publication/science/25424351
https://rss.sciencedirect.com/publication/science/25902385
'''
TITLE = '固态电解质文献追踪'

def abstract(entry):
    for key in ('summary', 'description', 'dc_description'):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value
    for part in entry.get('content', []):
        if part.get('value', '').strip():
            return part['value']
    return ''

def fetch():
    Path('keywords.dat').write_text(KEYWORDS, encoding='utf-8')
    Path('journals.dat').write_text(SOURCES, encoding='utf-8')
    os.environ.pop('RSS_KEYWORDS', None)
    os.environ.pop('RSS_JOURNALS', None)
    original_parse = rss.feedparser.parse
    def parse(*args, **kwargs):
        result = original_parse(*args, **kwargs)
        for entry in result.entries:
            entry['summary'] = abstract(entry)
        return result
    rss.feedparser.parse = parse
    original_existing = rss.get_existing_items
    queries = KEYWORDS.splitlines()
    rss.get_existing_items = lambda: [e for e in original_existing() if rss.match_entry(e, queries)]
    rss.main()
    tree = ET.parse('filtered_feed.xml')
    channel = tree.getroot().find('channel')
    channel.find('title').text = TITLE
    channel.find('link').text = 'https://xpf94435-maker.github.io/paper-feed/'
    channel.find('description').text = 'Solid electrolytes, ion transport, interfaces and low-temperature performance. Original publisher abstracts are preserved when available.'
    tree.write('filtered_feed.xml', encoding='utf-8', xml_declaration=True)

def build():
    site = Path('_site')
    site.mkdir(exist_ok=True)
    items = ET.parse('filtered_feed.xml').findall('./channel/item')
    status = json.loads(Path('fetch_status.json').read_text())
    cards = []
    for item in items[:100]:
        title = html.escape(item.findtext('title', ''))
        url = item.findtext('link', '')
        if urlsplit(url).scheme not in ('https', 'http'):
            url = '#'
        url = html.escape(url, quote=True)
        journal = html.escape(item.findtext('{http://purl.org/dc/elements/1.1/}source', ''))
        text = item.findtext('description', '')
        detail = '<details><summary>原文摘要</summary><div>' + html.escape(text) + '</div></details>' if text else '<p>期刊 RSS 未提供摘要。</p>'
        cards.append(f'<article><small>{journal}</small><h2><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></h2>{detail}</article>')
    failures = ''.join('<li>' + html.escape(s['url']) + ': ' + html.escape(s.get('error') or '') + '</li>' for s in status['sources'] if not s['ok'])
    body = ''.join(cards) or '<p>本轮没有匹配条目。</p>'
    page = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{TITLE}</title><link rel="alternate" type="application/rss+xml" href="filtered_feed.xml"><style>body{{font:16px/1.7 system-ui;max-width:920px;margin:32px auto;padding:0 20px;background:#f7fafb;color:#16313d}}article{{background:white;padding:18px;border:1px solid #dae5e9;border-radius:12px;margin:14px 0}}h2{{font-size:19px}}a{{color:#12617b}}details{{overflow-wrap:anywhere}}small{{color:#596f79}}</style><h1>{TITLE}</h1><p>硫化物 · 氧化物 · 聚合物 · 卤化物 · 离子传导 · 界面稳定性 · 低温性能</p><p><a href="filtered_feed.xml">Zotero RSS 订阅链接</a> · <a href="https://github.com/xpf94435-maker/paper-feed/actions">自动更新状态</a></p><p>每8小时计划更新。最近抓取：{html.escape(status['updated_at'])}（UTC）。成功 {status['successful_sources']}/{status['total_sources']} 个来源，共 {len(items)} 篇。</p><p>保留出版社提供的原文摘要，未提供时标明缺失，不以AI生成内容替代。RSS筛选不能替代完整文献检索。</p><details><summary>未成功抓取的来源</summary><ul>{failures}</ul></details>{body}<footer>基于 Jarvis-Towne/paper-feed；最多保留1000篇。</footer></html>'''
    (site / 'index.html').write_text(page, encoding='utf-8')
    (site / '.nojekyll').touch()
    for name in ('filtered_feed.xml', 'fetch_status.json'):
        (site / name).write_bytes(Path(name).read_bytes())
    print(f'Built solid-electrolyte page: {len(items)} papers')

if __name__ == '__main__':
    build() if '--build' in sys.argv else fetch()
