# Rudi Makes Site

Simple static site + Python editor script for:
- project build logs
- repair/troubleshooting logs
- the shop (gear, synth parts, and mod kits)
- site profile content (about/contact)

## Files
- `index.html` – main builds page (generated)
- `repairs.html` – troubleshooting page (generated)
- `shop.html` – shop landing page, collection grid (generated)
- `projects/*.html` – per-project detail pages (generated)
- `shop/*.html` – per-collection and per-item shop pages (generated)
- `template.html` – template used to rebuild `index.html`
- `repairs_template.html` – template used to rebuild `repairs.html`
- `project_template.html` – template used to rebuild per-project pages
- `shop_template.html` – template used to rebuild `shop.html`
- `shop_collection_template.html` – template for `shop/<collection>.html`
- `shop_item_template.html` – template for `shop/<item>.html`
- `projects.json` – build entries
- `repairs.json` – repair entries
- `shop.json` – shop collections + items + the next part number
- `site.json` – profile, contact, and about tags
- `manage.py` – interactive editor script

## Run
From this folder:

```bash
python3 manage.py
```

Then choose a command:
- `input-project` – add a new build
- `edit-project` – edit build details (title, status, cover, gallery, tags, links, text)
- `edit-story` – edit build story sections (photos + text)
- `input-repair` – add a new repair log
- `edit-repair` – edit an existing repair entry
- `delete-project` – remove a build and its generated project page
- `delete-repair` – remove a repair entry
- `undo-last` – restore the latest JSON backup
- `list-backups` – show available backups
- `restore-backup` – choose and restore a specific backup
- `publish-github` – stage all, commit, and push changes to your GitHub repo
- `web-ui` – launch a local browser-based admin menu
- `edit-site` – update name, about text, links, tags
- `list-projects` – list builds
- `list-repairs` – list repairs
- `rebuild` – regenerate every page from JSON + templates (builds, repairs, shop)

Shop commands:
- `list-items` – show inventory with stock, price, and any missing buy links
- `input-item` – add gear, a synth part, or a mod kit
- `edit-item` – edit a listing, paste in payment links, publish a draft
- `mark-sold` – someone bought it; drops stock and rebuilds
- `set-stock` – restock a part or kit
- `delete-item` – remove a listing and its generated page
- `edit-collections` – add/edit/remove shop collections

## Typical flow
1. Add or edit content with `manage.py`.
2. Run `rebuild` (or use commands that rebuild automatically).
3. Open `index.html` in a browser and verify.

`manage.py` now runs in a loop until you choose `q` to quit.

## Web Admin UI
From `manage.py`, choose `web-ui` (menu option `16`).

Default URL:
- `http://127.0.0.1:8081`

The web UI lets you:
- rebuild and publish
- edit site settings
- add/delete builds and repairs
- manage build story sections
- run the shop: add/edit listings, mark things sold, restock, delete

## The Shop

Payments run on **Stripe Payment Links** and **PayPal hosted buttons**. Both are free to keep
open and only charge per sale (Stripe 2.9% + $0.30, PayPal 3.49% + $0.49). Nothing is hosted
here — each listing just stores a link, so the site stays plain static HTML on GitHub Pages.

### Part numbers
Every item gets a sequential `RM-####` on creation, tracked by `next_sku` in `shop.json`.
Numbers are never reused, including after a delete. Customers can search the shop by part
number, by manufacturer part number (e.g. `80017A`), or by a model it fits (e.g. `Juno-106`).

### Stock
`stock` drives everything. At 0 an item shows **Sold** (gear) or **Sold out** (parts/kits) with
the buy buttons removed; at 1–2 a part shows "Only N left". `status: "draft"` keeps an item out
of the generated site entirely — that's the default until it has a payment link.

### Shipping
Priced per item. Box it, weigh it, get a UPS quote from Indianapolis to a west-coast ZIP
(Zone 8, the worst case), and enter that number — `manage.py` applies the 1.2x markup
(`SHIP_MARKUP`) so you never lose money on a far-away buyer. Local pickup is always free.

### Listing something
1. Photograph it, box it, weigh it, get the Zone 8 quote.
2. `input-item` (or the Add Item tab) — it saves as a draft.
3. Create the Stripe Payment Link and PayPal button at those prices. Cap Stripe at 1 payment
   and set PayPal inventory to 1 for one-of-a-kind gear.
4. `edit-item` — paste both in and publish.
5. `publish-github`.

### When it sells
`mark-sold`, then **deactivate the other processor's button**. Stripe and PayPal can't see each
other's inventory, so a one-off can technically sell twice until you kill the second link. Then
pack it, ship it, and email the tracking number.

## Notes
- Images are copied into `images/` when you add entries with photos
  (shop photos go to `images/shop/`, collection covers to `images/shop/collections/`).
- `manage.py` now escapes text before writing HTML, so special characters in descriptions/tags won’t break page markup.
- Backups are stored in `.backups/` before content-editing commands.
- `publish-github` uses local git config/credentials (SSH key or token) and pushes current branch to `origin`.
