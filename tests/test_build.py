"""Tests for the free-genealogy-sources-directory.

Run with:  python3 -m unittest discover tests -v

Covers:
  1. Every source entry parses and carries required, well-formed fields
  2. Directory policy: https-only URLs, no affiliate domains, fresh verify dates
  3. Guide content files exist and contain the required sections
  4. The build script runs and every page renders (DOCTYPE, title, entries,
     verify dates, no broken tags, no leaked markdown syntax)
  5. The mini-markdown renderer handles headings, lists, tables, quotes,
     code blocks, inline styles, and escapes HTML
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build as build_mod  # noqa: E402

DATA_FILE = ROOT / "data" / "sources.json"
CONTENT_DIR = ROOT / "site-content"
REQUIRED_ENTRY_FIELDS = {"id", "title", "url", "category", "what", "how",
                         "requirements", "verify_date"}
VALID_REQUIREMENTS = {"fully-free", "free-account", "free-via-library"}
AFFILIATE_DOMAINS = ("amazon.com", "clickbank", "shareasale", "cj.com",
                     "impact.com", "awin", "hop.clickbank")
VERIFY_MAX_AGE_DAYS = 180


def load_data():
    with DATA_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


class TestSourceData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_data()
        cls.entries = cls.data["entries"]
        cls.categories = {c["id"] for c in cls.data["categories"]}

    def test_data_file_parses(self):
        self.assertIsInstance(self.data, dict)
        self.assertIn("entries", self.data)
        self.assertIn("categories", self.data)
        self.assertIn("_meta", self.data)

    def test_entry_count(self):
        self.assertGreaterEqual(len(self.entries), 20, "directory should stay substantive")

    def test_every_entry_has_required_fields(self):
        for entry in self.entries:
            with self.subTest(entry=entry.get("id", "UNKNOWN")):
                self.assertTrue(REQUIRED_ENTRY_FIELDS <= set(entry),
                                "missing fields: %s" % (REQUIRED_ENTRY_FIELDS - set(entry)))

    def test_required_fields_are_not_empty(self):
        for entry in self.entries:
            for field in ("id", "title", "url", "what", "how"):
                with self.subTest(entry=entry["id"], field=field):
                    self.assertTrue(str(entry[field]).strip(), "empty %s" % field)

    def test_entry_ids_unique_and_sluglike(self):
        ids = [e["id"] for e in self.entries]
        self.assertEqual(len(ids), len(set(ids)), "duplicate entry ids")
        for eid in ids:
            self.assertRegex(eid, r"^[a-z0-9][a-z0-9-]*$", "bad slug: %s" % eid)

    def test_categories_known(self):
        for entry in self.entries:
            self.assertIn(entry["category"], self.categories,
                          "%s: unknown category %r" % (entry["id"], entry["category"]))

    def test_every_category_has_entries(self):
        counts = {e["category"] for e in self.entries}
        for cat_id in self.categories:
            self.assertIn(cat_id, counts, "category has no entries: %s" % cat_id)

    def test_requirements_enum(self):
        for entry in self.entries:
            self.assertIn(entry["requirements"], VALID_REQUIREMENTS,
                          "%s: bad requirements %r" % (entry["id"], entry["requirements"]))

    def test_urls_are_https(self):
        for entry in self.entries:
            with self.subTest(entry=entry["id"]):
                self.assertTrue(entry["url"].startswith("https://"),
                                "non-https URL: %s" % entry["url"])

    def test_no_affiliate_urls(self):
        for entry in self.entries:
            lower = entry["url"].lower()
            for domain in AFFILIATE_DOMAINS:
                self.assertNotIn(domain, lower,
                                 "%s: possible affiliate/PAYWALL link" % entry["id"])

    def test_no_affiliate_wording_in_copy(self):
        banned = ("affiliate", "we earn a commission", "referral link",
                  "upgrade to premium", "start your free trial")
        for entry in self.entries:
            blob = (entry["title"] + " " + entry["what"] + " " + entry["how"]).lower()
            for phrase in banned:
                self.assertNotIn(phrase, blob,
                                 "%s: policy wording found: %s" % (entry["id"], phrase))

    def test_verify_dates_fresh_and_iso(self):
        today = date.today()
        for entry in self.entries:
            with self.subTest(entry=entry["id"]):
                vd = date.fromisoformat(entry["verify_date"])  # raises if not ISO
                age = (today - vd).days
                self.assertGreaterEqual(age, 0, "%s: verify_date in the future" % entry["id"])
                self.assertLessEqual(age, VERIFY_MAX_AGE_DAYS,
                                     "%s: verify_date %s is %d days old - re-verify this link"
                                     % (entry["id"], entry["verify_date"], age))

    def test_meta_last_reviewed_fresh(self):
        last = date.fromisoformat(self.data["_meta"]["last_reviewed"])
        self.assertLessEqual((date.today() - last).days, VERIFY_MAX_AGE_DAYS)

    def test_no_paywall_signal_in_entry_copy(self):
        paywords = ("subscription required", "membership required", "upgrade to premium")
        for entry in self.entries:
            blob = (entry["what"] + entry["how"]).lower()
            for w in paywords:
                self.assertNotIn(w, blob, "%s mentions paywall signals" % entry["id"])


class TestGuideContent(unittest.TestCase):
    def test_all_guides_exist_with_content(self):
        for slug in build_mod.GUIDE_ORDER:
            path = CONTENT_DIR / (slug + ".md")
            with self.subTest(guide=slug):
                self.assertTrue(path.exists(), "missing guide: %s" % path)
                text = path.read_text(encoding="utf-8")
                self.assertGreater(len(text), 800, "guide too thin: %s" % slug)
                self.assertTrue(text.startswith("# "), "%s must start with h1" % slug)
                self.assertRegex(text, r"^# .+")

    def test_guides_cover_goal_topics(self):
        all_md = "\n".join(p.read_text(encoding="utf-8") for p in CONTENT_DIR.glob("*.md"))
        self.assertIn("etiquette", all_md.lower())
        self.assertIn("citation", all_md.lower())
        self.assertIn("binder", all_md.lower())


class TestMarkdownRenderer(unittest.TestCase):
    def test_headings_lists_bold(self):
        html_text = build_mod.render_markdown(
            "# Title\n\n## Section\n\n- item one\n- item two\n\nA **bold** and *soft* `code` paragraph.\n")
        self.assertIn("<h2>Title</h2>", html_text)
        self.assertIn("<h3>Section</h3>", html_text)
        self.assertIn("<ul><li>item one</li><li>item two</li></ul>", html_text)
        self.assertIn("<strong>bold</strong>", html_text)
        self.assertIn("<em>soft</em>", html_text)
        self.assertIn("<code>code</code>", html_text)

    def test_table_rendered(self):
        html_text = build_mod.render_markdown(
            "| A | B |\n|---|---|\n| 1 | 2 |\n")
        self.assertIn("<table>", html_text)
        self.assertIn("<th>A</th>", html_text)
        self.assertIn("<td>2</td>", html_text)

    def test_blockquote_ordered_list_code_fence(self):
        html_text = build_mod.render_markdown(
            "> quoted line\n\n1. first\n2. second\n\n```\ncode\nline\n```\n")
        self.assertIn("<blockquote><p>quoted line</p></blockquote>", html_text)
        self.assertIn("<ol><li>first</li><li>second</li></ol>", html_text)
        self.assertIn("<pre><code>code\nline</code></pre>", html_text)

    def test_checkboxes(self):
        html_text = build_mod.render_markdown("- [ ] todo\n- [x] done\n")
        self.assertIn('<li class="checkbox">todo</li>', html_text)
        self.assertIn('<li class="checkbox done">done</li>', html_text)

    def test_html_is_escaped(self):
        html_text = build_mod.render_markdown("See <script>alert('x')</script> now.\n")
        self.assertNotIn("<script>", html_text)
        self.assertIn("&lt;script&gt;", html_text)

    def test_inline_links(self):
        html_text = build_mod.render_markdown("Visit [the archive](https://example.gov/) today.\n")
        self.assertIn('<a href="https://example.gov/">the archive</a>', html_text)


class TestBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / "site"
        result = subprocess.run(
            [sys.executable, str(ROOT / "build.py"), "--out", str(out)],
            capture_output=True, text=True, cwd=str(ROOT))
        cls.proc = result
        cls.out = out
        cls.pages = {p.name: p.read_text(encoding="utf-8")
                     for p in out.glob("*.html")}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_build_exits_zero_no_stderr(self):
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr)
        self.assertEqual(self.proc.stderr.strip(), "", "build should run clean")

    def test_all_expected_pages_rendered(self):
        expected = ["index.html", "sources.html"] + \
                   [s + ".html" for s in build_mod.GUIDE_ORDER]
        for name in expected:
            with self.subTest(page=name):
                self.assertIn(name, self.pages, "missing built page %s" % name)

    def test_pages_are_html_documents(self):
        for name, text in self.pages.items():
            with self.subTest(page=name):
                self.assertTrue(text.startswith("<!DOCTYPE html>"), name)
                self.assertIn("</html>", text)
                self.assertIn("<title>", text)
                self.assertIn("Free Genealogy Sources Directory", text)
                self.assertIn("Asdale Dynamics, LLC", text)

    def test_no_unrendered_markdown_syntax(self):
        heading = re.compile(r"^#{1,3} ", re.M)
        for name, text in self.pages.items():
            with self.subTest(page=name):
                self.assertNotIn("```", text, name)
                self.assertNotIn("<p>#", text, name)
                self.assertNotRegex(text, heading, "%s leaked markdown headings" % name)

    def test_every_entry_appears_with_verified_date(self):
        import html as html_mod
        sources_page = self.pages["sources.html"]
        data = load_data()
        for entry in data["entries"]:
            with self.subTest(entry=entry["id"]):
                self.assertIn(html_mod.escape(entry["title"]), sources_page)
                self.assertIn('id="%s"' % entry["id"], sources_page)
                self.assertIn(entry["verify_date"], sources_page)
                self.assertIn(entry["url"], sources_page)
        self.assertIn(str(len(data["entries"])), sources_page)

    def test_index_links_resolve_to_built_files(self):
        import html as html_mod
        hrefs = set()
        for text in self.pages.values():
            hrefs |= set(re.findall(r'href="([^"]+)"', text))
        for href in sorted(hrefs):
            if href.startswith("#"):
                # fragment must exist somewhere on its page (checked via targets below)
                continue
            if href.startswith("http"):
                continue
            self.assertIn(href, self.pages, "broken relative link %s" % href)
        # fragment anchors
        sources_page = self.pages["sources.html"]
        for frag in re.findall(r'href="#(cat-[a-z0-9-]+)"', sources_page):
            self.assertIn('id="%s"' % frag, sources_page)

    def test_pages_are_styled_inline_and_local_first(self):
        for name, text in self.pages.items():
            with self.subTest(page=name):
                self.assertIn("<style>", text)
                self.assertNotRegex(
                    text, r'src="http|href="https?://[^"]*\.(css|js|woff)',
                    "%s pulls remote assets" % name)

    def test_dictionary_pages_carry_all_four_goal_topics(self):
        blob = (self.pages["binder-checklist.html"] +
                self.pages["citing-sources.html"] +
                self.pages["findagrave-etiquette.html"]).lower()
        for topic in ("citation", "binder", "etiquette"):
            self.assertIn(topic, blob)

    def test_no_secrets_or_personal_data(self):
        for path in list(ROOT.rglob("*.md")) + [DATA_FILE]:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(
                text, r"\b\d{3}-\d{2}-\d{4}\b", "%s: possible SSN" % path.name)
            self.assertNotRegex(
                text, r"(api[_-]?key|secret|password)\s*[:=]", "%s: secret-like text" % path.name)


if __name__ == "__main__":
    unittest.main()
