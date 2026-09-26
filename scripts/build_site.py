import argparse
import html
import json
import math
import re
import shutil
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "src"
DATA = ROOT / "data"
CONFIG = ROOT / "config"
ASSETS = ROOT / "assets"
OUTPUT = ROOT / "dist"
PRODUCT_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FONT_FAMILIES = {
    "system": 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    "arial": "Arial, Helvetica, sans-serif",
    "verdana": "Verdana, Geneva, sans-serif",
    "trebuchet": '"Trebuchet MS", sans-serif',
    "georgia": "Georgia, serif",
}


def read_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def esc(value):
    return html.escape(str(value), quote=True)


def css_variable_name(value):
    return re.sub(r"(?<!^)(?=[A-Z])", "-", value).lower()


def image_path(value):
    relative = Path(value.removeprefix("./"))
    resolved = (ROOT / relative).resolve()
    if not resolved.is_relative_to(ROOT) or not resolved.is_file():
        raise ValueError(f"Product image does not exist inside the project: {value}")
    return relative.as_posix()


def validate_settings(settings):
    site_url = settings["site"]["url"]
    parsed_url = urlsplit(site_url)
    hostname = parsed_url.hostname or ""
    valid_hostname = all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in hostname.split(".")
    )
    if (
        parsed_url.scheme != "https"
        or not hostname
        or not valid_hostname
        or len(hostname) > 253
        or len(hostname.split(".")) < 2
        or parsed_url.username
        or parsed_url.password
        or parsed_url.port is not None
        or parsed_url.path not in ("", "/")
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ValueError(
            "site.url must be an HTTPS domain without a path, port, or credentials."
        )

    if not re.fullmatch(r"[0-9]{8,15}", settings["business"]["whatsappNumber"]):
        raise ValueError(
            "business.whatsappNumber must contain 8 to 15 digits, including country code."
        )

    for name, value in settings["theme"].items():
        if not re.fullmatch(
            r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{5})?", value
        ):
            raise ValueError(f"theme.{name} must be a 3, 6, or 8 digit hex color.")

    typography = settings.get("typography", {})
    for key in ("bodyFont", "headingFont"):
        if typography.get(key) not in FONT_FAMILIES:
            raise ValueError(
                f"typography.{key} must be one of: {', '.join(FONT_FAMILIES)}."
            )
    base_font_size = typography.get("baseFontSize")
    if (
        isinstance(base_font_size, bool)
        or not isinstance(base_font_size, int)
        or not 16 <= base_font_size <= 20
    ):
        raise ValueError(
            "typography.baseFontSize must be a whole number from 16 to 20."
        )

    return hostname.lower()


def whatsapp_link(number, product_name):
    message = quote(f"Hello, I would like to enquire about {product_name}.")
    return f"https://wa.me/{number}?text={message}"


def add_default_seo(product, site):
    brand_suffix = f" | {site['name']}"
    if not product.get("seoTitle"):
        name_limit = max(1, 60 - len(brand_suffix))
        product_name = product["name"]
        short_name = product_name
        if len(product_name) > name_limit:
            short_name = product_name[:name_limit].rsplit(" ", 1)[0]
            short_name = short_name or product_name[:name_limit]
        product["seoTitle"] = f"{short_name}{brand_suffix}"
    if not product.get("seoDescription"):
        description = " ".join(product["description"].split())
        if len(description) > 160:
            description = description[:157].rsplit(" ", 1)[0].rstrip(" ,.;:") + "..."
        product["seoDescription"] = description


def site_schema(settings):
    site = settings["site"]
    business = settings["business"]
    base_url = site["url"].rstrip("/")
    organization_id = f"{base_url}/#organization"
    organization = {
        "@type": "Organization",
        "@id": organization_id,
        "name": site["name"],
        "url": f"{base_url}/",
        "logo": f"{base_url}/assets/brand/ghanshyam_penda_wala_logo_icon-rbg.png",
        "sameAs": [url for url in settings.get("social", {}).values() if url],
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": business["whatsappDisplay"],
            "email": business["email"],
            "contactType": "customer service",
        },
        "department": [
            {
                "@type": "Store",
                "name": f"{site['name']} - {location['name']}",
                "telephone": location["phone"],
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": location["address"],
                    "addressLocality": location["name"],
                    "addressRegion": "Gujarat",
                    "addressCountry": "IN",
                },
            }
            for location in business["locations"]
        ],
    }
    website = {
        "@type": "WebSite",
        "@id": f"{base_url}/#website",
        "url": f"{base_url}/",
        "name": site["name"],
        "inLanguage": site.get("language", "en-IN"),
        "publisher": {"@id": organization_id},
    }
    return {
        "@context": "https://schema.org",
        "@graph": [organization, website],
    }


def product_page(product, settings, live_products):
    site = settings["site"]
    business = settings["business"]
    slug = product["slug"]
    canonical = f"{site['url'].rstrip('/')}/products/{slug}/"
    images = [image_path(product["mainImage"])] + [
        image_path(image) for image in product.get("gallery", [])
    ]
    absolute_images = [f"{site['url'].rstrip('/')}/{image}" for image in images]
    description = product["description"]
    schema = {
        "@type": "Product",
        "name": product["name"],
        "description": description,
        "image": absolute_images,
        "brand": {"@type": "Brand", "name": site["name"]},
        "category": product["category"],
        "sku": slug,
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
    }
    breadcrumb_schema = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": f"{site['url'].rstrip('/')}/",
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": product["category"],
                "item": f"{site['url'].rstrip('/')}/#products",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": product["name"],
                "item": canonical,
            },
        ],
    }
    schema_json = json.dumps(
        {
            "@context": "https://schema.org",
            "@graph": [schema, breadcrumb_schema],
        },
        ensure_ascii=True,
    ).replace("<", "\\u003c")
    gallery = "\n".join(
        f"""<button class="pdp-thumb{' is-selected' if index == 0 else ''}" type="button" data-gallery-src="../../{esc(image)}" data-gallery-alt="{esc(product['name'])} image {index + 1}" aria-label="Show product image {index + 1}" aria-pressed="{'true' if index == 0 else 'false'}">
          <img src="../../{esc(image)}" alt="" loading="lazy">
        </button>"""
        for index, image in enumerate(images)
    )
    highlights = "\n".join(
        f"<li>{esc(item)}</li>" for item in product.get("highlights", [])
    )
    related = "\n".join(
        f"""<a class="pdp-related-link" href="../{esc(item['slug'])}/">{esc(item['name'])}<span aria-hidden="true">↗</span></a>"""
        for item in live_products
        if item["slug"] != slug
    )
    order_url = whatsapp_link(business["whatsappNumber"], product["name"])
    footer_order_url = whatsapp_link(business["whatsappNumber"], "your order")
    price = f"{settings['site']['currencySymbol']}{product['price']:,}"
    main_alt = esc(product.get("mainImageAlt", product["name"]))
    return f"""<!doctype html>
<html lang="{esc(site.get('language', 'en-IN'))}">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'none'; font-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'self'; object-src 'none'; form-action 'self'; upgrade-insecure-requests">
    <meta name="referrer" content="strict-origin-when-cross-origin">
    <meta name="theme-color" content="{esc(settings['theme']['brown'])}">
    <link rel="icon" type="image/png" href="../../assets/brand/ghanshyam_penda_wala_logo_icon-rbg.png">
    <meta name="description" content="{esc(product['seoDescription'])}">
    <meta name="robots" content="index,follow,max-image-preview:large">
    <title>{esc(product['seoTitle'])}</title>
    <link rel="canonical" href="{esc(canonical)}">
    <meta property="og:type" content="product">
    <meta property="og:site_name" content="{esc(site['name'])}">
    <meta property="og:title" content="{esc(product['seoTitle'])}">
    <meta property="og:description" content="{esc(product['seoDescription'])}">
    <meta property="og:url" content="{esc(canonical)}">
    <meta property="og:image" content="{esc(absolute_images[0])}">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="stylesheet" href="../../styles.css">
    <link rel="stylesheet" href="../../theme.css">
    <script type="application/ld+json">{schema_json}</script>
    <script src="../../product.js" defer></script>
  </head>
  <body class="pdp-page">
    <a class="skip-link" href="#main">Skip to content</a>
    <div class="announcement">Tradition, crafted fresh since 1973 <span aria-hidden="true">·</span> Made for sharing</div>
    <header class="site-header">
      <a class="brand" href="../../index.html" aria-label="{esc(site['name'])} home">
        <img src="../../assets/brand/ghanshyam_penda_wala_logo_icon-rbg.png" alt="" width="52" height="52">
        <span><strong>Ghanshyam</strong><small>Penda Wala</small></span>
      </a>
      <nav class="main-nav" aria-label="Main navigation">
        <a href="../../index.html#products">Penda &amp; sweets</a>
        <a href="../../index.html#story">Our story</a>
        <a href="../../index.html#contact">Contact</a>
      </nav>
    <a class="header-order" href="{esc(order_url)}" target="_blank" rel="noopener noreferrer">WhatsApp <span aria-hidden="true">↗</span></a>
    </header>
    <main id="main" class="pdp-main">
      <nav class="breadcrumbs" aria-label="Breadcrumb">
        <a href="../../index.html">Home</a><span aria-hidden="true">/</span>
        <a href="../../index.html#products">{esc(product['category'])}</a><span aria-hidden="true">/</span>
        <span aria-current="page">{esc(product['name'])}</span>
      </nav>
      <section class="pdp-layout" aria-labelledby="product-title">
        <div class="pdp-gallery">
          <div class="pdp-main-image-wrap">
            <img id="pdp-main-image" src="../../{esc(images[0])}" alt="{main_alt}" fetchpriority="high">
            <span class="product-category">{esc(product['category'])}</span>
          </div>
          <div class="pdp-thumbnails" aria-label="More product photos">{gallery}</div>
        </div>
        <div class="pdp-copy">
          <p class="eyebrow"><span></span> Handcrafted in Gujarat</p>
          <h1 id="product-title">{esc(product['name'])}</h1>
          <p class="pdp-description">{esc(description)}</p>
          <div class="pdp-price-row"><span class="pdp-price">{esc(price)}</span><span>{esc(product.get('priceNote', 'Please confirm the current price with our shop.'))}</span></div>
          <a class="button button-dark pdp-order" href="{esc(order_url)}" target="_blank" rel="noopener noreferrer">Enquire on WhatsApp <span aria-hidden="true">↗</span></a>
          <p class="pdp-contact-note">Send your enquiry directly on WhatsApp.</p>
          <div class="pdp-highlights"><h2>Why you’ll love it</h2><ul>{highlights}</ul></div>
          <dl class="pdp-facts">
            <div><dt>Ingredients</dt><dd>{esc(product.get('ingredients', 'Please contact the shop to confirm.'))}</dd></div>
            <div><dt>Shelf life</dt><dd>{esc(product.get('shelfLife', 'Please confirm with the shop.'))}</dd></div>
            <div><dt>Storage</dt><dd>{esc(product.get('storage', 'Follow the guidance provided with your order.'))}</dd></div>
          </dl>
        </div>
      </section>
      <section class="pdp-story" aria-labelledby="pdp-story-title">
        <p class="eyebrow"><span></span> A sweet with a story</p>
        <h2 id="pdp-story-title">Tradition, made for <em>sharing.</em></h2>
        <p>Ghanshyam Penda Wala has been making traditional sweets since 1973. For product availability, pack sizes, ingredients, and delivery details, get in touch with us before placing your order.</p>
      </section>
      <section class="pdp-related" aria-labelledby="related-title">
        <div><p class="eyebrow"><span></span> Discover more</p><h2 id="related-title">More from <em>our kitchen.</em></h2></div>
        <div class="pdp-related-links">{related}</div>
      </section>
    </main>
        <!-- Keep this wave directly above the footer; both use the --berry theme token. -->
        <div class="footer-wave" aria-hidden="true">
            <svg viewBox="0 0 1440 160" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
                <path fill="var(--berry)" fill-opacity="0.15" d="M0,32L60,42.7C120,53,240,75,360,69.3C480,64,600,32,720,32C840,32,960,64,1080,69.3C1200,75,1320,53,1380,42.7L1440,32L1440,160L0,160Z"></path>
                <path fill="var(--berry)" d="M0,64L60,80C120,96,240,128,360,122.7C480,117,600,75,720,64C840,53,960,75,1080,90.7C1200,107,1320,117,1380,122.7L1440,128L1440,160L0,160Z"></path>
            </svg>
        </div>
        <footer class="site-footer">
            <div class="footer-inner">
                <div class="footer-brand-group">
                    <a class="brand footer-brand" href="../../index.html">
                        <img src="../../assets/brand/ghanshyam_penda_wala_logo_icon-rbg.png" alt="" width="44" height="44" loading="lazy">
                        <span><strong>Ghanshyam</strong><small>Penda Wala</small></span>
                    </a>
                    <p>Traditional sweets, made with care since 1973.</p>
                </div>
                <nav class="footer-links" aria-label="Footer navigation">
                    <a href="../../index.html#products">Our sweets</a>
                    <a href="../../index.html#contact">Contact</a>
                    <a href="../../index.html#policies">Policies</a>
                    <a href="mailto:{esc(settings['business']['email'])}">Email</a>
                </nav>
                <div class="footer-social">
                    <p>Follow along</p>
                    <nav class="social-links" aria-label="Social media">
                        <a class="social-link" href="{esc(settings['social']['instagram'])}" target="_blank" rel="noopener noreferrer">Instagram</a>
                        <a class="social-link" href="{esc(settings['social']['facebook'])}" target="_blank" rel="noopener noreferrer">Facebook</a>
                        <a class="social-link" href="{esc(settings['social']['youtube'])}" target="_blank" rel="noopener noreferrer">YouTube</a>
                        <a class="social-link" href="{esc(footer_order_url)}" target="_blank" rel="noopener noreferrer">WhatsApp</a>
                    </nav>
                </div>
                <small class="copyright">© {time.localtime().tm_year} {esc(site['name'])}</small>
            </div>
    </footer>
  </body>
</html>
"""


def build():
    settings = read_json(CONFIG / "settings.json")
    hostname = validate_settings(settings)
    catalog = read_json(DATA / "products.json")
    products = catalog.get("products", [])
    seen_slugs = set()
    live_products = []

    for product in products:
        slug = product.get("slug", "")
        if not PRODUCT_SLUG.fullmatch(slug) or slug in seen_slugs:
            raise ValueError(f"Invalid or duplicate product slug: {slug!r}")
        seen_slugs.add(slug)
        if not isinstance(product.get("live", False), bool):
            raise ValueError(f"Product {slug!r} live flag must be true or false.")
        if not product.get("live", False):
            continue
        for key in ("allOrder", "categoryOrder"):
            if key in product and (
                isinstance(product[key], bool)
                or not isinstance(product[key], int)
                or product[key] < 1
            ):
                raise ValueError(
                    f"Product {slug!r} {key} must be a positive whole number."
                )
        for key in ("name", "category", "description", "mainImage", "price"):
            if not product.get(key):
                raise ValueError(f"Live product {slug!r} is missing {key!r}")
        price = product["price"]
        if (
            isinstance(price, bool)
            or not isinstance(price, (int, float))
            or not math.isfinite(price)
            or price <= 0
        ):
            raise ValueError(
                f"Live product {slug!r} must have a positive numeric price."
            )
        add_default_seo(product, settings["site"])
        if product["category"] not in {"Penda", "Sweets", "Namkeen"}:
            raise ValueError(
                f"Unsupported category for {slug!r}: {product['category']}"
            )
        if len(product["seoTitle"]) > 60 or len(product["seoDescription"]) > 160:
            raise ValueError(f"SEO title/description is too long for {slug!r}")
        image_path(product["mainImage"])
        for image in product.get("gallery", []):
            image_path(image)
        live_products.append(product)

    if not live_products:
        raise ValueError("At least one product must be marked live.")

    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    for filename in ("app.js", "product.js", "styles.css"):
        source = SOURCE / filename
        if source.is_file():
            shutil.copy2(source, OUTPUT / filename)
    home = (SOURCE / "index.html").read_text(encoding="utf-8")
    replacements = {
        "__SITE_TITLE__": esc(settings["site"]["title"]),
        "__SITE_DESCRIPTION__": esc(settings["site"]["description"]),
        "__SITE_NAME__": esc(settings["site"]["name"]),
        "__SITE_LANGUAGE__": esc(settings["site"].get("language", "en-IN")),
        "__CANONICAL_URL__": esc(f"{settings['site']['url'].rstrip('/')}/"),
        "__OG_IMAGE__": esc(
            f"{settings['site']['url'].rstrip('/')}/assets/live/mava-penda-3.png"
        ),
        "__BUSINESS_EMAIL__": esc(settings["business"]["email"]),
        "__SITE_SCHEMA__": json.dumps(site_schema(settings), ensure_ascii=True).replace(
            "<", "\\u003c"
        ),
    }
    for token, value in replacements.items():
        home = home.replace(token, value)
    home = home.replace(
        "info@ghanshyampendawala.com", esc(settings["business"]["email"])
    )
    (OUTPUT / "index.html").write_text(home, encoding="utf-8")
    (OUTPUT / "CNAME").write_text(f"{hostname}\n", encoding="utf-8")
    shutil.copytree(ASSETS / "live", OUTPUT / "assets" / "live")
    logo = ASSETS / "brand" / "ghanshyam_penda_wala_logo_icon-rbg.png"
    brand_output = OUTPUT / "assets" / "brand"
    brand_output.mkdir(parents=True)
    shutil.copy2(logo, brand_output / logo.name)
    (OUTPUT / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUTPUT / "products.json").write_text(
        json.dumps({"products": live_products}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    typography = settings["typography"]
    theme_css = (
        ":root {\n"
        + "\n".join(
            f"  --{css_variable_name(key)}: {value};"
            for key, value in settings["theme"].items()
        )
        + "\n"
        + "\n".join(
            (
                f"  --sans: {FONT_FAMILIES[typography['bodyFont']]};",
                f"  --serif: {FONT_FAMILIES[typography['headingFont']]};",
                f"  --base-font-size: {typography['baseFontSize']}px;",
            )
        )
        + "\n}\n"
    )
    (OUTPUT / "theme.css").write_text(theme_css, encoding="utf-8")

    for product in live_products:
        page_dir = OUTPUT / "products" / product["slug"]
        page_dir.mkdir(parents=True)
        (page_dir / "index.html").write_text(
            product_page(product, settings, live_products), encoding="utf-8"
        )

    base_url = settings["site"]["url"].rstrip("/")
    sitemap_urls = [f"{base_url}/"] + [
        f"{base_url}/products/{product['slug']}/" for product in live_products
    ]
    sitemap = "\n".join(f"  <url><loc>{esc(url)}</loc></url>" for url in sitemap_urls)
    (OUTPUT / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sitemap}\n</urlset>\n',
        encoding="utf-8",
    )
    (OUTPUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n",
        encoding="utf-8",
    )
    print(f"Built {len(live_products)} live product pages in {OUTPUT}")
    return OUTPUT


def source_signature():
    watched_paths = [Path(__file__)]
    for directory in (SOURCE, DATA, CONFIG, ASSETS / "brand", ASSETS / "live"):
        if directory.exists():
            watched_paths.extend(
                path for path in directory.rglob("*") if path.is_file()
            )
    signature = []
    for path in sorted(watched_paths):
        try:
            file_stat = path.stat()
        except FileNotFoundError:
            continue
        signature.append((path, file_stat.st_mtime_ns, file_stat.st_size))
    return tuple(signature)


def watch_sources(stop_event):
    previous_signature = source_signature()
    changed_at = None
    while not stop_event.wait(0.5):
        current_signature = source_signature()
        if current_signature != previous_signature:
            previous_signature = current_signature
            changed_at = time.monotonic()
        elif changed_at is not None and time.monotonic() - changed_at >= 0.75:
            try:
                build()
            except Exception as error:
                print(f"Automatic rebuild failed: {error}")
            changed_at = None


def main():
    parser = argparse.ArgumentParser(
        description="Build or preview the static storefront."
    )
    parser.add_argument(
        "--serve", action="store_true", help="serve the built site locally"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="local preview port (default: 8000)"
    )
    args = parser.parse_args()
    output = build()
    if args.serve:
        handler = lambda *handler_args, **handler_kwargs: SimpleHTTPRequestHandler(
            *handler_args, directory=str(output), **handler_kwargs
        )
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        stop_watching = threading.Event()
        watcher = threading.Thread(
            target=watch_sources, args=(stop_watching,), daemon=True
        )
        watcher.start()
        print(f"Previewing at http://localhost:{args.port}/ (Ctrl+C to stop)")
        print("Watching source files; saved changes rebuild automatically.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nPreview server stopped.")
        finally:
            stop_watching.set()
            server.server_close()


if __name__ == "__main__":
    main()
