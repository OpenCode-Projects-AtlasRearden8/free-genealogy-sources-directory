# Free Genealogy Sources Directory

A curated, hand-maintained directory of **free** genealogy sources and routes:
FamilySearch, state and county archives, census lookups, free-via-library
newspaper routes, Find A Grave (and the etiquette of using it graciously), a
citing-a-source starter card, and a checklist for copying findings into an
offline research binder.

Every entry lists whether you need nothing, a free account, or just your
library card - and every entry carries a **verify date**: the last day a human
checked that the link worked and was still free.

**The house rules: no paywalls, no affiliate links, ever.** If a route costs
money (outside a free account or a library card you already own), it does not
go in this directory.

Made by Asdale Dynamics, LLC.

## How to use it

Open `site/index.html` in any browser. The site is fully static - no server,
no JavaScript, no external assets - so you can keep a copy on a USB stick next
to your research binder.

| Page | What it is |
|------|------------|
| `index.html` | Directory overview by category |
| `sources.html` | All entries with verify dates and requirement tags |
| `start-here.html` | A one-hour first research session, step by step |
| `findagrave-etiquette.html` | How to use Find A Grave without stepping on volunteers |
| `citing-sources.html` | The five-fact citation starter card |
| `binder-checklist.html` | Copy every finding into an offline research binder |

## What this project is (and is not)

- **Is:** a hand-curated directory + static HTML site, tested to build. All
  entries live in `data/sources.json`; guide pages are hand-written markdown in
  `site-content/`.
- **Is not:** a paid-genealogy sales funnel, an automation script, or family
  history advice-giver. It points at free archives and teaches the habits
  (cite, verify, back up on paper) that make free research actually work.

It is deliberately distinct from its sibling projects: the family-history
manual (guided writing process), the oral-history kit (interview cards), and
the official-help directory (government agencies). This project is only about
*free sources*.

## Build the site

Requires only Python 3.8+ (no third-party packages):

```bash
python3 build.py               # writes site/
python3 build.py --out /tmp/x  # write elsewhere
```

Output is committed in `site/` so it can be served as-is (e.g. GitHub Pages),
but you can always rebuild it locally.

## Run the tests

```bash
python3 -m unittest discover tests -v
```

The tests verify that:

- every entry in `data/sources.json` parses and has required fields
- entry ids are unique slugs; categories exist and are populated
- URLs are HTTPS and none match known affiliate domains
- verify dates are ISO dates and less than 180 days old (so the suite fails
  when a link check goes stale - that is intentional)
- nothing in the copy promises paywalls, subscriptions, or trials
- `build.py` runs clean and renders every page: DOCTYPE, stylesheet inline,
  every entry present with its verify date, no unrendered markdown syntax,
  no broken internal links, no remote assets

## Keeping it maintained

1. Check a link, then update its `verify_date` in `data/sources.json` (and
   `_meta.last_reviewed`).
2. Add new entries the same way; tests will enforce the format.
3. Re-run `python3 build.py` and the test suite.

## License

MIT - see [LICENSE](LICENSE). Copyright (c) 2026 Asdale Dynamics, LLC.
