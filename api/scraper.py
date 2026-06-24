"""
刮削引擎 — JavSP 封装 + 内置后备刮削

从番号爬取 AV 影片元数据，支持多数据源并发抓取。
优先使用 JavSP 引擎，不可用时使用内置的简易刮削。
"""

import os
import sys
import json
import logging
import shutil
import tempfile
from typing import Optional

logger = logging.getLogger("av_provider.scraper")

# JavSP 路径
JAVSP_PATH = os.environ.get("JAVSP_PATH", "/app")


def scrape_number(number: str, data_dir: str = "/tmp/javsp_data") -> dict:
    """
    刮削指定番号，返回完整的元数据字典。

    Args:
        number: 番号，如 "ABW-005"
        data_dir: 临时工作目录

    Returns:
        dict: 包含完整元数据的字典
    """
    result = {
        "number": number.upper(),
        "success": False,
        "error": None,
    }

    # 尝试导入 JavSP，不依赖只检查文件是否存在（避免缺依赖时崩溃）
    javsp_ok = False
    if JAVSP_PATH not in sys.path:
        sys.path.insert(0, JAVSP_PATH)
    try:
        from javsp.config import Cfg
        javsp_ok = True
    except Exception as e:
        logger.warning(f"JavSP 引擎不可用 ({e})")

    if javsp_ok:
        return _scrape_javsp(number, data_dir, result)
    else:
        logger.warning(f"使用内置刮削 (fallback)")
        return _scrape_fallback(number, result)


def _scrape_javsp(number: str, data_dir: str, result: dict) -> dict:
    """使用 JavSP 引擎刮削"""
    # 加入 JavSP 路径
    if JAVSP_PATH not in sys.path:
        sys.path.insert(0, JAVSP_PATH)

    try:
        from javsp.config import Cfg
        from javsp.datatype import Movie, MovieInfo
        from javsp.nfo import write_nfo
        from javsp.func import import_crawlers, parallel_crawler, summarize_data
    except ImportError as e:
        result["error"] = f"JavSP 导入失败: {e}"
        return result

    work_dir = os.path.join(data_dir, number)
    os.makedirs(work_dir, exist_ok=True)

    try:
        # 创建占位文件（JavSP 需要真实文件来检测番号）
        dummy = os.path.join(work_dir, f"{number}.mp4")
        if not os.path.isfile(dummy):
            with open(dummy, "wb") as f:
                f.seek(244 * 1024 * 1024 - 1)
                f.write(b"\0")

        import_crawlers()
        movie = Movie(dummy)
        info = MovieInfo(movie)
        parallel_crawler(movie, info, retry=3)

        if info.title is None:
            result["error"] = "所有刮削源均未返回数据"
            return result

        summarize_data(info)

        # 生成 nfo
        nfo_path = os.path.join(work_dir, f"{number}.nfo")
        write_nfo(info, nfo_path)
        nfo_content = open(nfo_path, "rt", encoding="utf-8").read()

        # 下载封面
        cover_bytes = None
        if info.cover:
            try:
                import requests
                resp = requests.get(info.cover, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                if resp.status_code == 200:
                    cover_bytes = resp.content
            except Exception as e:
                logger.warning(f"封面下载失败: {e}")

        result.update({
            "title": info.title,
            "original_title": info.ori_title,
            "actress": info.actress or [],
            "studio": info.producer,
            "publisher": info.publisher,
            "release_date": info.publish_date,
            "runtime": info.duration,
            "plot": info.plot,
            "genre": info.genre_norm or info.genre or [],
            "score": info.score,
            "cover_url": info.cover,
            "cover_bytes": cover_bytes,
            "nfo": nfo_content,
            "nfo_filename": f"{number}.nfo",
            "success": True,
        })

    except Exception as e:
        logger.exception(f"JavSP 刮削失败 [{number}]: {e}")
        result["error"] = str(e)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    return result



def _scrape_fallback(number: str, result: dict) -> dict:
    """R内置后备刮削 — 多源并发尝试"""
    import requests
    from lxml import html

    sources = [
        ("javdb", f"https://javdb.com/v/{number}"),
        ("avsox", f"https://avsox.click/{number.upper()}"),
        ("javbus", f"https://javbus.com/{number}"),
    ]

    for name, url in sources:
        try:
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code != 200:
                continue

            tree = html.fromstring(resp.text)
            title = None
            actress = []
            date = None
            studio = None
            cover_url = None
            genre = []

            if name == "avsox":
                title_el = tree.xpath('//h3/text()')
                title = title_el[0].strip() if title_el else None
                actress_el = tree.xpath('//a[contains(@href, "/actress/")]/text()')
                actress = [a.strip() for a in actress_el if a.strip()]
                date_el = tree.xpath("//p[contains(text(), '\u65e5\u671f')]/following-sibling::p[1]/text()")
                date = date_el[0].strip() if date_el else None
                studio_el = tree.xpath("//p[contains(text(), '\u5236\u9020\u5546')]/following-sibling::p[1]/a/text()")
                studio = studio_el[0].strip() if studio_el else None
                cover_el = tree.xpath('//a[@class="bigImage"]/img/@src')
                cover_url = cover_el[0] if cover_el else None
                genre_el = tree.xpath('//span[@class="genre"]/a/text()')
                genre = [g.strip() for g in genre_el if g.strip()]

            elif name == "javdb":
                title_el = tree.xpath('//h2[@class="title"]/text() | //div[@class="title"]/a/text()')
                title = title_el[0].strip() if title_el else None
                actress_el = tree.xpath('//span[@class="actor"]/a/text() | //a[contains(@href, "/actors/")]/text()')
                actress = [a.strip() for a in actress_el if a.strip()]
                date_el = tree.xpath("//div[@class='meta']//span[contains(text(), '\u65e5\u671f')]/following-sibling::text()")
                if not date_el:
                    date_el = tree.xpath("//div[@class='meta']/text()")
                date = None
                for d in date_el:
                    d = d.strip()
                    if d and d[0].isdigit() and "-" in d:
                        date = d
                        break
                cover_el = tree.xpath('//img[@class="video-cover"]/@src | //img[contains(@class, "cover")]/@src')
                cover_url = cover_el[0] if cover_el else None
                genre_el = tree.xpath('//div[@class="tags"]/a/text() | //span[@class="tag"]/a/text()')
                genre = [g.strip() for g in genre_el if g.strip()]

            elif name == "javbus":
                title_el = tree.xpath('//h3/text()')
                title = title_el[0].strip() if title_el else None
                actress_el = tree.xpath('//a[contains(@href, "/actress/")]/text()')
                actress = [a.strip() for a in actress_el if a.strip()]
                date_el = tree.xpath("//p[contains(text(), '\u53d1\u884c\u65e5\u671f')]/following-sibling::text()")
                date = date_el[0].strip() if date_el else None
                cover_el = tree.xpath('//a[@class="bigImage"]/img/@src | //img[@class="bigImage"]/@src')
                cover_url = cover_el[0] if cover_el else None
                genre_el = tree.xpath('//span[@class="genre"]/a/text()')
                genre = [g.strip() for g in genre_el if g.strip()]

            if not title:
                continue

            nfo_lines = [
                '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>',
                "<movie>",
                f"  <title>{title}</title>",
                f"  <originaltitle>{number}</originaltitle>",
                f"  <studio>{studio or ''}</studio>",
                f"  <premiered>{date or ''}</premiered>",
                "  <mpaa>NC-17</mpaa>",
                "  <country>\u65e5\u672c</country>",
            ]
            for a in actress:
                nfo_lines.append(f"  <actor><name>{a}</name></actor>")
            for g in genre:
                nfo_lines.append(f"  <genre>{g}</genre>")
            nfo_lines.append(f"  <uniqueid type='num' default='true'>{number}</uniqueid>")
            nfo_lines.append("</movie>")

            result.update({
                "title": title or number,
                "actress": actress,
                "studio": studio,
                "release_date": date,
                "genre": genre,
                "cover_url": cover_url,
                "nfo": "\n".join(nfo_lines),
                "nfo_filename": f"{number}.nfo",
                "success": True,
            })
            return result

        except Exception as e:
            logger.warning(f"{name} \u6293\u53d6\u5931\u8d25: {e}")
            continue

    result["error"] = "\u6240\u6709\u6307\u5b9a\u6e90\u5747\u4e0d\u53ef\u7528"
    return result

