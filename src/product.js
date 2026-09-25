const mainImage = document.querySelector("#pdp-main-image");

document.querySelectorAll("[data-gallery-src]").forEach((thumbnail) => {
  thumbnail.addEventListener("click", () => {
    mainImage.src = thumbnail.dataset.gallerySrc;
    mainImage.alt = thumbnail.dataset.galleryAlt;
    document.querySelectorAll("[data-gallery-src]").forEach((item) => {
      const isSelected = item === thumbnail;
      item.classList.toggle("is-selected", isSelected);
      item.setAttribute("aria-pressed", String(isSelected));
    });
  });
});
