"""5.5.3: Galnet dispatches carry their broadcast date from the Galnet page;
the RSS feed stamps every item with the time it was generated."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from voidcompass.services import galnet

PAGE = """<html><body><div class="right-content"><div>  </div>
<div class="article">        <h3 class="hiLite galnetNewsArticleTitle"><a href="/galnet/uid/aa11"><i class="fa fa-globe"></i> Relief Convoy Reaches Port</a></h3>
<div class="i_right" style="margin: 5px"><p class="small" style="color:#888;">01 OCT 3312</p></div>
<p>The convoy arrived on schedule.<br /><br />
&ldquo;We are grateful,&rdquo; said a spokesperson.</p>  </div>
<div class="article"><h3 class="hiLite galnetNewsArticleTitle"><a href="/galnet/uid/bb22"><i class="fa fa-globe"></i> Older Story</a></h3>
<div class="i_right" style="margin: 5px"><p class="small" style="color:#888;">22 SEP 3312</p></div>
<p>Text of the older story.</p>  </div>
</div><script>function hide_extra_filters(){ jQuery('.extra').hide(); }</script></body></html>"""

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Relief Convoy Reaches Port</title><description>From the feed.</description>
<guid isPermaLink="false">aa11</guid><pubDate>Thu, 08 Oct 2026 03:20:26 +0100</pubDate></item>
</channel></rss>"""


class GalnetPageTests(unittest.TestCase):
    def test_each_article_keeps_its_broadcast_date(self):
        articles = galnet.parse_galnet_page(PAGE)
        self.assertEqual([row["id"] for row in articles], ["aa11", "bb22"], "the RSS guid, so nothing reads as new")
        self.assertEqual([row["stamp"] for row in articles], ["01 OCT 3312", "22 SEP 3312"])
        self.assertEqual(articles[0]["published"], "2026-10-01T00:00:00Z", "3312 is 2026")
        self.assertEqual(articles[0]["title"], "Relief Convoy Reaches Port")
        self.assertEqual(articles[0]["body"], "The convoy arrived on schedule.\n\n“We are grateful,” said a spokesperson.")
        self.assertEqual(articles[1]["body"], "Text of the older story.", "stops at the article, not the page script")

    def test_the_page_comes_first_and_rss_is_the_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            service = galnet.GalnetFeedService(Path(folder) / "galnet.json", "test")
            fetched = []

            def get(url, accept):
                fetched.append(url)
                if url == galnet.GALNET_PAGE_URL:
                    return page
                return RSS

            page = PAGE.encode("utf-8")
            with mock.patch.object(service, "_get", side_effect=get):
                self.assertEqual(service._fetch_articles()[0]["stamp"], "01 OCT 3312")
                self.assertEqual(fetched, [galnet.GALNET_PAGE_URL])
                page = b"<html>redesigned</html>"
                self.assertEqual(service._fetch_articles()[0]["body"], "From the feed.")
                self.assertEqual(fetched[-1], galnet.GALNET_RSS_URL)


if __name__ == "__main__":
    unittest.main()
