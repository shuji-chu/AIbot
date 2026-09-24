# -*- coding: utf-8 -*-
"""多源免费搜索引擎"""
import requests, re, json, html
from urllib.parse import quote, unquote


def _clean(s):
    """清理 HTML"""
    if not s: return ""
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    return s.strip()


def search_duckduckgo(query, limit=5):
    """DuckDuckGo HTML 搜索（免费无 Key）"""
    try:
        url = "https://html.duckduckgo.com/html/"
        r = requests.post(url, data={"q": query}, 
                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                         timeout=20)
        text = r.text
        # 解析结果
        results = []
        # 找 result__a 和 result__snippet
        items = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', 
                          text, re.DOTALL)
        for url_raw, title, snippet in items[:limit]:
            # 解码 DuckDuckGo 的重定向链接
            if 'uddg=' in url_raw:
                m = re.search(r'uddg=([^&]+)', url_raw)
                if m:
                    url_raw = unquote(m.group(1))
            results.append({
                "title": _clean(title),
                "url": url_raw,
                "snippet": _clean(snippet)[:200]
            })
        return results
    except Exception as e:
        print("[搜索] DuckDuckGo 失败: " + str(e)[:80])
        return []


def search_wikipedia(query):
    """维基百科搜索（免费）"""
    try:
        r = requests.get("https://zh.wikipedia.org/w/api.php",
                        params={"action": "query", "format": "json", "list": "search",
                                "srsearch": query, "srlimit": 1, "utf8": 1},
                        headers={"User-Agent": "SAFW-AI/1.0"},
                        timeout=15)
        data = r.json()
        results = data.get("query", {}).get("search", [])
        if results:
            return {
                "title": results[0].get("title", ""),
                "snippet": _clean(results[0].get("snippet", ""))[:200],
                "url": "https://zh.wikipedia.org/wiki/" + quote(results[0].get("title", ""))
            }
        return None
    except Exception as e:
        print("[搜索] Wikipedia 失败: " + str(e)[:80])
        return None


def search_news(query):
    """HackerNews 搜索（科技新闻）"""
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search",
                        params={"query": query, "tags": "story", "hitsPerPage": 3},
                        timeout=15)
        hits = r.json().get("hits", [])
        return [{"title": h.get("title", ""), "url": h.get("url", "") or 
                 "https://news.ycombinator.com/item?id=" + str(h.get("objectID", "")),
                 "snippet": (h.get("story_text") or "")[:150]} for h in hits]
    except Exception as e:
        print("[搜索] HackerNews 失败: " + str(e)[:80])
        return []


def search_zhihu(query):
    """知乎搜索（通过 bing 的公开接口）"""
    try:
        # 用 bing 搜索 site:zhihu.com
        url = "https://www.bing.com/search"
        r = requests.get(url, params={"q": "site:zhihu.com " + query},
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=15)
        # 简单解析
        items = re.findall(r'<h2><a href="([^"]+)"[^>]*>(.*?)</a></h2>', r.text)
        results = []
        for url, title in items[:3]:
            results.append({"title": _clean(title), "url": url, "snippet": ""})
        return results
    except:
        return []


def search_all(query):
    """综合搜索：多源聚合"""
    all_results = []
    
    # 1. DuckDuckGo（主力）
    ddg = search_duckduckgo(query, limit=5)
    all_results.extend(ddg)
    
    # 2. Wikipedia（知识）
    wiki = search_wikipedia(query)
    if wiki:
        all_results.insert(0, wiki)  # 维基优先
    
    # 3. 科技新闻（如果查询含"新闻/最新/AI"等词）
    if any(k in query for k in ["新闻", "最新", "AI", "科技", "技术"]):
        news = search_news(query)
        all_results.extend(news[:2])
    
    return all_results


def format_results(results, query=""):
    """格式化搜索结果为文本"""
    if not results:
        return "❌ 未找到相关结果"
    text = "🔍 搜索结果：" + query + "\n"
    text += "━━━━━━━━━━━━━━\n\n"
    for i, r in enumerate(results[:6], 1):
        text += f"{i}. {r['title']}\n"
        if r.get('snippet'):
            text += f"   {r['snippet'][:100]}\n"
        text += f"   🔗 {r['url']}\n\n"
    text += "━━━━━━━━━━━━━━\n"
    text += "💡 用 /sum 链接 可总结网页内容"
    return text


def search_and_answer(query):
    """搜索 + AI 综合回答"""
    import ai_service
    results = search_all(query)
    if not results:
        return "❌ 未找到相关信息，试试换个关键词"
    
    # 构造上下文
    context = "以下是搜索到的相关信息：\n\n"
    for i, r in enumerate(results[:5], 1):
        context += f"[{i}] {r['title']}\n"
        if r.get('snippet'):
            context += f"{r['snippet']}\n"
        context += "\n"
    
    prompt = f"""用户问题：{query}

{context}

请根据以上信息，用简洁准确的中文回答用户问题。
要求：
1. 优先使用搜索到的信息
2. 如果信息不足，结合你自己的知识补充
3. 回答不超过300字
4. 不要编造不存在的信息
5. 最后附上主要来源"""
    
    answer = ai_service.stable_ai("你是智能搜索助手。综合搜索结果，准确回答用户问题。", prompt, 0.5)
    
    # 加来源
    sources = "\n\n━━━━━━━━━━━━━━\n📚 参考来源：\n"
    for i, r in enumerate(results[:3], 1):
        sources += f"{i}. {r['title'][:40]}\n   {r['url'][:80]}\n"
    
    return answer + sources


def smart_need_search(query):
    """智能判断是否需要搜索"""
    # 关键词触发
    keywords = [
        "今天", "今日", "现在", "当前", "最新", "实时", "刚刚", "最近",
        "新闻", "热搜", "行情", "股价", "币价", "价格", "天气",
        "谁是", "什么时候", "多少钱", "怎么样", "发生了什么",
        "2024", "2025", "2026",  # 年份
        "搜索", "查一下", "帮我查", "搜一下",
    ]
    if any(k in query for k in keywords):
        return True
    # 疑问句
    if query.endswith("?") or query.endswith("？"):
        if any(k in query for k in ["什么", "怎么", "为什么", "谁", "哪", "多少"]):
            return True
    return False
