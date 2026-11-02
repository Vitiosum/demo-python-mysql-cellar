// The Herbarium: a little vanilla JS. Every page works without it.

// Presigned URL countdown on a specimen sheet
const expiry = document.querySelector("[data-expires]");
if (expiry) {
  const until = new Date(expiry.dataset.expires).getTime();
  const out = expiry.querySelector("[data-countdown]");
  const tick = () => {
    const left = Math.max(0, Math.round((until - Date.now()) / 1000));
    out.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
    if (left === 0) {
      expiry.classList.add("is-expired");
      out.textContent = "expired";
      return;
    }
    setTimeout(tick, 1000);
  };
  tick();
}

// A link ending in #packet opens the fragment packet
const packet = document.getElementById("packet");
if (packet && location.hash === "#packet") packet.open = true;

// Collection filters apply as soon as a value is picked
document.querySelectorAll("[data-autosubmit] select").forEach((select) => {
  select.addEventListener("change", () => select.form.submit());
});

// Press form
const form = document.querySelector(".press-form");
if (form) {
  const fields = ["latin_name", "common_name", "family"].map((n) => form.elements[n]);
  let autofilled = fields.every((f) => !f.value);

  // Picking a drawn plant writes its names on the label, unless you typed your own
  const fillFrom = (radio) => {
    if (!autofilled || !radio) return;
    form.elements.latin_name.value = radio.dataset.latin;
    form.elements.common_name.value = radio.dataset.common;
    form.elements.family.value = radio.dataset.family;
  };
  fields.forEach((f) => f.addEventListener("input", () => (autofilled = false)));
  form.querySelectorAll('input[name="drawn"]').forEach((radio) => {
    radio.addEventListener("change", () => fillFrom(radio));
  });
  form.querySelectorAll('input[name="source"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      if (radio.value === "drawn") fillFrom(form.querySelector('input[name="drawn"]:checked'));
    });
  });
  fillFrom(form.querySelector('input[name="drawn"]:checked'));

  // Same recipes, new seeds: every plant is drawn again
  const redraw = form.querySelector("[data-redraw]");
  redraw.hidden = false;
  redraw.addEventListener("click", () => {
    form.querySelectorAll('input[name="drawn"]').forEach((radio) => {
      const kind = radio.value.split(":")[0];
      const seed = Math.floor(Math.random() * 99999) + 1;
      radio.value = `${kind}:${seed}`;
      radio.parentElement.querySelector("img").src = `/draw/${kind}.svg?seed=${seed}`;
    });
  });

  // Today as the default collection date
  const day = form.elements.collected_on;
  const today = new Date().toISOString().slice(0, 10);
  day.max = today;
  if (!day.value) day.value = today;

  // Photo: preview it and check the size before sending
  const file = form.elements.photo;
  const preview = form.querySelector(".dropzone__preview");
  const error = form.querySelector("[data-photo-error]");
  file.addEventListener("change", () => {
    const chosen = file.files[0];
    error.hidden = true;
    if (!chosen) return;
    if (chosen.size > Number(file.dataset.max)) {
      error.textContent = "This photo is larger than 5 MB. Choose a smaller one.";
      error.hidden = false;
      file.value = "";
      return;
    }
    preview.src = URL.createObjectURL(chosen);
    preview.hidden = false;
  });
}
