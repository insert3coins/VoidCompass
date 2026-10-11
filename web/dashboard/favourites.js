// Favourites on the Postcards and Screenshots pages (5.5.3.7): a star on
// each picture and in its full-size view, and a FAVOURITES filter. The stars
// are kept by the deck (keepsakes.json in Void Compass's own folder).

export function starButton(row, ui) {
  const on = Boolean(row.favourite);
  return `<button type="button" class="album-star${on ? " on" : ""}" data-star="${ui.escapeHtml(row.id)}" aria-pressed="${on}"
    title="${on ? "Remove from favourites" : "Add to favourites"}" aria-label="${on ? "Remove from favourites" : "Add to favourites"}">${on ? "★" : "☆"}</button>`;
}

export function favouritesFilter(id) {
  return `<button type="button" class="album-favs" id="${id}" data-favs aria-pressed="false" title="Show only your favourites">★ FAVOURITES <b></b></button>`;
}

// The filter's count and state.
export function showFavouritesFilter(button, rows, on) {
  if (!button) return;
  const count = rows.filter((row) => row.favourite).length;
  button.querySelector("b").textContent = count ? String(count) : "";
  button.classList.toggle("active", on);
  button.setAttribute("aria-pressed", String(on));
}

// The viewer's button for the picture on show.
export function showViewerStar(button, row) {
  if (!button || !row) return;
  button.textContent = row.favourite ? "★ FAVOURITE" : "☆ FAVOURITE";
  button.classList.toggle("on", Boolean(row.favourite));
  button.setAttribute("aria-pressed", String(Boolean(row.favourite)));
}

// Star or unstar at once on the page, then keep it; put back if it wasn't.
export async function toggleFavourite(row, page, ui, redraw) {
  row.favourite = !row.favourite;
  redraw();
  const done = await ui.command("workspace", {page, operation: "favourite", id: row.id, value: row.favourite});
  if (!done) {
    row.favourite = !row.favourite;
    redraw();
    ui.showToast("That favourite wasn't saved");
  }
  return done;
}
