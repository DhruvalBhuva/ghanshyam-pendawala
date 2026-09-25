const productGrid = document.querySelector("#product-grid");
const shopList = document.querySelector("#shop-list");
const categoryTabs = [...document.querySelectorAll(".category-tab")];
let products = [];
let settings;
let activeCategory = "All";

function whatsappUrl(productName) {
  const message = `Hello, I would like to enquire about ${productName}.`;
  return `https://wa.me/${settings.business.whatsappNumber}?text=${encodeURIComponent(message)}`;
}

function createWhatsAppLink(productName, className, label) {
  const link = document.createElement("a");
  link.className = className;
  link.href = whatsappUrl(productName);
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = label;
  return link;
}

function createProductCard(product, index) {
  const article = document.createElement("article");
  article.className = "product-card";

  const imageWrap = document.createElement("div");
  imageWrap.className = "product-image-wrap";
  const imageLink = document.createElement("a");
  imageLink.className = "product-image-link";
  imageLink.href = `./products/${encodeURIComponent(product.slug)}/`;
  imageLink.setAttribute("aria-label", `View ${product.name} product details`);
  const image = document.createElement("img");
  image.src = product.mainImage;
  image.alt = product.mainImageAlt || product.name;
  image.loading = index < 3 ? "eager" : "lazy";
  imageLink.append(image);
  imageWrap.append(imageLink);

  const category = document.createElement("span");
  category.className = "product-category";
  category.textContent = product.category;
  imageWrap.append(category);

  const details = document.createElement("div");
  details.className = "product-details";
  const title = document.createElement("h3");
  const titleLink = document.createElement("a");
  titleLink.href = `./products/${encodeURIComponent(product.slug)}/`;
  titleLink.textContent = product.name;
  title.append(titleLink);
  const description = document.createElement("p");
  description.textContent = product.description;
  details.append(title, description);

  if (product.ingredients) {
    const ingredients = document.createElement("p");
    ingredients.className = "product-ingredients";
    ingredients.textContent = `Ingredients: ${product.ingredients}`;
    details.append(ingredients);
  }

  const footer = document.createElement("div");
  footer.className = "product-footer";
  const price = document.createElement("span");
  price.className = "product-price";
  price.textContent = `${settings.site.currencySymbol}${Number(product.price).toLocaleString("en-IN")}`;
  const actions = document.createElement("div");
  actions.className = "product-actions";
  const detailLink = document.createElement("a");
  detailLink.className = "product-detail-link";
  detailLink.href = `./products/${encodeURIComponent(product.slug)}/`;
  detailLink.textContent = "View details →";
  const orderLink = createWhatsAppLink(
    product.name,
    "product-order",
    "WhatsApp ↗",
  );
  actions.append(detailLink, orderLink);
  footer.append(price, actions);
  details.append(footer);

  article.append(imageWrap, details);
  return article;
}

function renderProducts() {
  const visibleProducts =
    activeCategory === "All"
      ? products
      : products.filter((product) => product.category === activeCategory);

  productGrid.replaceChildren();
  if (visibleProducts.length === 0) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    const title = document.createElement("h3");
    title.textContent = `${activeCategory} availability`;
    const copy = document.createElement("p");
    copy.textContent =
      "Our online selection is being updated. Message the Rajkot shop to ask what is freshly available today.";
    const contact = document.createElement("a");
    contact.href = "#contact";
    contact.className = "text-link";
    contact.textContent = "Find our contact details →";
    emptyState.append(title, copy, contact);
    productGrid.append(emptyState);
    return;
  }

  visibleProducts.forEach((product, index) =>
    productGrid.append(createProductCard(product, index)),
  );
}

function renderShops() {
  shopList.replaceChildren();
  for (const shop of settings.business.locations) {
    const article = document.createElement("article");
    article.className = "shop-item";
    const title = document.createElement("h3");
    title.textContent = shop.name;
    const address = document.createElement("p");
    address.textContent = shop.address;
    const phone = document.createElement("a");
    phone.href = `tel:${shop.phone.replaceAll(" ", "")}`;
    phone.textContent = shop.phone;
    article.append(title, address, phone);
    if (shop.name === settings.business.primaryLocation) {
      article.append(
        createWhatsAppLink("your order", "shop-whatsapp", "WhatsApp Rajkot ↗"),
      );
    }
    shopList.append(article);
  }
}

function setCategory(category) {
  activeCategory = category;
  for (const tab of categoryTabs) {
    const isActive = tab.dataset.category === category;
    tab.classList.toggle("is-active", isActive);
    tab.setAttribute("aria-pressed", String(isActive));
  }
  renderProducts();
}

categoryTabs.forEach((tab) =>
  tab.addEventListener("click", () => setCategory(tab.dataset.category)),
);
document.querySelectorAll("[data-category-link]").forEach((link) => {
  link.addEventListener("click", () => setCategory(link.dataset.categoryLink));
});

document.querySelector("#year").textContent = new Date().getFullYear();

Promise.all([fetch("./products.json"), fetch("./settings.json")])
  .then(async ([productsResponse, settingsResponse]) => {
    if (!productsResponse.ok || !settingsResponse.ok) {
      throw new Error("Product catalog or settings could not be loaded.");
    }
    return [await productsResponse.json(), await settingsResponse.json()];
  })
  .then(([catalog, config]) => {
    products = catalog.products.filter((product) => product.live !== false);
    settings = config;
    renderProducts();
    renderShops();
  })
  .catch((error) => {
    productGrid.textContent =
      "The product list could not be loaded. Please refresh the page or contact us directly.";
    console.error(error);
  });
