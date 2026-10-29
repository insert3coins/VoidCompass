/* About uses the same installed-version and update result as the deck. */
export function renderAbout(data = {}) {
  const text = (id, value) => {
    const node = document.getElementById(id);
    if (node && node.textContent !== value) node.textContent = value;
  };
  const version = data.app?.version || "DEV";
  text("about-version", `Version ${version}`);
  text("about-footer-version", `v${version}`);
  text("about-copyright", `Copyright © ${new Date().getFullYear()} insert3coins`);

  const update = data.update || {};
  let tone = "idle";
  let label = "Ready when you are";
  let detail = "Check for a newer version, or explore the release notes.";
  if (update.checking) {
    tone = "busy";
    label = "Checking for updates…";
    detail = "Asking GitHub for the latest release.";
  } else if (update.error && Number(update.failed_at || 0) >= Number(update.checked_at || 0)) {
    tone = "bad";
    label = "Couldn't check for updates";
    detail = `${update.error}. You can try again or open the release notes.`;
  } else if (update.available) {
    tone = "new";
    label = update.latest_version ? `Version ${update.latest_version} is available` : "An update is available";
    detail = `You have version ${version}. View the update for details.`;
  } else if (update.checked) {
    tone = "good";
    label = "You're up to date";
    detail = `Version ${version} is the latest release.`;
  }
  text("about-update-state", label);
  text("about-update-detail", detail);
  const section = document.querySelector(".about-release");
  if (!section) return;
  section.dataset.tone = tone;
  const check = section.querySelector("[data-update-check]");
  check.disabled = Boolean(update.checking);
  const checkLabel = update.checking ? "CHECKING…" : "CHECK FOR UPDATES";
  if (check.textContent !== checkLabel) check.textContent = checkLabel;
  section.querySelector("[data-update-view]").hidden = !update.available || !update.latest_version;
}
