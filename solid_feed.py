"""Solid-electrolyte RSS configuration and reading page."""
import datetime
import html
import json
import os
import re
import urllib.request
import urllib.parse
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor
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

def plain_text(value):
    return ' '.join(re.sub(r'<[^>]+>', ' ', html.unescape(value)).split())

def has_abstract(value):
    text = plain_text(value)
    if text.startswith('[原文摘要未提供]'):
        return False
    if 'Publication date:' in text and 'Author(s):' in text and 'Abstract' not in text:
        return False
    return len(text) > 100

def supplement_abstract(item):
    description = item.find('description')
    if description is None:
        description = ET.SubElement(item, 'description')
    value = description.text or ''
    if has_abstract(value):
        return
    title = item.findtext('title', '')
    try:
        query = urllib.parse.urlencode({'query.title': title, 'rows': 1, 'select': 'DOI,title,abstract'})
        identifier = item.findtext('guid', '') + ' ' + item.findtext('link', '')
        doi_match = re.search(r'10\.\d{4,9}/[^\s?<#]+', identifier)
        endpoint = 'https://api.crossref.org/works/' + urllib.parse.quote(doi_match.group(), safe='/') if doi_match else 'https://api.crossref.org/works?' + query
        request = urllib.request.Request(endpoint, headers={'User-Agent': 'PaperFeedSolidElectrolytes/1.0'})
        with urllib.request.urlopen(request, timeout=12) as response:
            message = json.load(response)['message']
        matches = message.get('items', [message])
        if matches:
            match = matches[0]
            other_title = match.get('title', [''])[0]
            normalize = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
            same = SequenceMatcher(None, normalize(title), normalize(other_title)).ratio() >= 0.92
            original = match.get('abstract', '')
            if same and not original and match.get('DOI') and not doi_match:
                endpoint = 'https://api.crossref.org/works/' + urllib.parse.quote(match['DOI'], safe='/')
                with urllib.request.urlopen(endpoint, timeout=12) as response:
                    original = json.load(response)['message'].get('abstract', '')
            if same and not has_abstract(original) and match.get('DOI'):
                try:
                    endpoint = 'https://api.openalex.org/works/https://doi.org/' + urllib.parse.quote(match['DOI'], safe='/')
                    with urllib.request.urlopen(endpoint, timeout=12) as response:
                        record = json.load(response)
                    index = record.get('abstract_inverted_index') or {}
                    words = {position: word for word, positions in index.items() for position in positions}
                    original = ' '.join(words[p] for p in sorted(words))
                except Exception:
                    pass
            if same and has_abstract(original):
                description.text = plain_text(original)
                return
    except Exception as error:
        print('Abstract metadata unavailable:', title[:60], type(error).__name__)
    if not value.startswith('[原文摘要未提供]'):
        description.text = '[原文摘要未提供] 出版社RSS及可用DOI元数据未提供论文摘要。' + plain_text(value)

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
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(supplement_abstract, tree.findall('./channel/item')))
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
        detail = '<details><summary>原文摘要</summary><div>' + html.escape(plain_text(text)) + '</div></details>' if has_abstract(text) else '<p>原文摘要未提供；请打开论文页面查看。</p>'
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
