# Ghanshyam Penda Wala

Live storefront: [ghanshyampendawala.com](https://ghanshyampendawala.com). This is a static product catalogue; customers enquire by WhatsApp, phone, or email. There is no online checkout.

## Local preview

Requires Python 3. From the project root:

```powershell
python scripts/build_site.py --serve
```

Open <http://localhost:8000>. The server rebuilds the site when source, product, settings, or published image files change; refresh the browser to see updates. Press Ctrl+C to stop. To build once without starting a server, run `python scripts/build_site.py`.

## Products and images

- Edit the `products` array in `data/products.json`.
- Set `live` to `false` while preparing an item and `true` to publish it.
- Use a unique lowercase `slug`, one of `Penda`, `Sweets`, or `Namkeen`, and a positive numeric `price`.
- Set `allOrder` to rank a product in **All favourites** and `categoryOrder` to rank it inside its category. Use positive whole numbers; lower numbers appear first. If ranks tie, catalog order breaks the tie. Products without a rank stay after ranked products in catalog order.
- Add the main product image and optional gallery images to `assets/live/`. Set `mainImage`, `mainImageAlt`, and `gallery` to their paths. The main image is included in the gallery automatically.
- Add accurate `description`, `highlights`, `ingredients`, `shelfLife`, and `storage`. Product SEO fields are `seoTitle` (maximum 60 characters) and `seoDescription` (maximum 160 characters).
- Use [reference/prompt.json](reference/prompt.json) for image-generation and product-copy prompts. Verify generated product facts before publishing.

The builder validates live product data and images, then generates each product page and updates the sitemap. Do not edit `dist/`; it is regenerated on every build.

## Site settings

Edit `config/settings.json` to update site metadata, the announcement, Gujarati tagline and transliteration, WhatsApp inquiry messages, the default WhatsApp number, branch names and phone numbers, social profile URLs, currency, colors, and typography. Inquiry message templates support `{product}` and `{branch}` placeholders. The default WhatsApp number uses country code and digits only. Branch phone numbers are listed separately in `business.locations`.

## Publish changes

The live site is deployed through the existing Cloudflare Pages Git integration. Before publishing, run `python scripts/build_site.py` and check the local preview. Commit and push changes to the repository’s configured production branch; Cloudflare builds and deploys that branch. Check the deployment status in Cloudflare Pages, then verify the live site.

## Main files

```text
src/                  Homepage, styles, and browser scripts
data/products.json    Product catalogue
config/settings.json  Site, branch, social, and theme settings
assets/live/          Images published with the site
reference/prompt.json Image and product-copy prompts
scripts/build_site.py Build, validate, and serve the site
dist/                 Generated output; do not edit
```
