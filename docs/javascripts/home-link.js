// The theme links only the header logo to `extra.homepage`; the site name
// beside it is plain text. Link it to the same place the logo goes.
const logo = document.querySelector(".md-header .md-logo");
const name = document.querySelector(".md-header__topic:first-child .md-ellipsis");
if (logo && name) {
  const link = document.createElement("a");
  link.href = logo.href;
  link.className = "md-ellipsis sg-home-link";
  link.textContent = name.textContent.trim();
  name.replaceWith(link);
}
