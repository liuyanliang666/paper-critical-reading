"use strict";

(() => {
  const $ = id => document.getElementById(id);
  const parts = location.pathname.split("/").filter(Boolean);
  const paperId = parts[3];
  const base = "/" + parts.slice(0, 2).join("/");
  const api = `${base}/api/papers/${encodeURIComponent(paperId)}`;
  const pages = $("pages");
  let metadata, target, currentPage = 1, pendingScroll = false;

  async function getJSON(url) {
    const response = await fetch(url, {credentials: "same-origin"});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not load this paper.");
    return result;
  }

  function setStatus(message, error = false) {
    $("status").textContent = message;
    $("status").classList.toggle("error", error);
  }

  function setCurrentPage(number) {
    currentPage = number;
    $("page-number").value = number;
    $("previous").disabled = number <= 1;
    $("next").disabled = number >= metadata.page_count;
    for (const button of $("target-pages").children) {
      button.setAttribute("aria-current", +button.dataset.page === number ? "page" : "false");
    }
  }

  function goToPage(number, rect) {
    number = Math.min(metadata.page_count, Math.max(1, Math.trunc(number) || 1));
    const element = document.getElementById(`pdf-page-${number}`);
    const top = element.getBoundingClientRect().top - pages.getBoundingClientRect().top + pages.scrollTop;
    pages.scrollTo({top: Math.max(0, top + (rect ? rect[1] * element.clientHeight - 100 : -20)),
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth"});
    setCurrentPage(number);
  }

  function resizePages() {
    if (!metadata) return;
    const width = Math.max(180, Math.min(pages.clientWidth - (innerWidth <= 800 ? 24 : 56), 1040));
    pages.style.setProperty("--page-width", `${width * Number($("zoom").value)}px`);
  }

  function buildPages() {
    for (const page of metadata.pages) {
      const element = document.createElement("div");
      element.className = "pdf-page";
      element.id = `pdf-page-${page.number}`;
      element.dataset.page = page.number;
      element.style.aspectRatio = `${page.width} / ${page.height}`;
      const image = document.createElement("img");
      image.src = `${api}/pages/${page.number}.png?scale=2`;
      image.loading = "lazy";
      image.decoding = "async";
      image.alt = `Original PDF, page ${page.number}`;
      image.width = Math.round(page.width * 2);
      image.height = Math.round(page.height * 2);
      image.addEventListener("error", () => setStatus(`Page ${page.number} could not be rendered. Try downloading the PDF.`, true));
      const caption = document.createElement("span");
      caption.className = "page-caption";
      caption.textContent = `PDF ${page.number}`;
      element.append(image, caption);
      pages.append(element);
    }
    resizePages();
  }

  async function showTarget() {
    for (const mark of pages.querySelectorAll(".highlight")) mark.remove();
    $("target-pages").replaceChildren();
    $("quote").hidden = $("copy-link").hidden = $("return-evidence").hidden = true;
    target = null;
    const query = new URLSearchParams(location.search);
    const citation = query.get("cite"), passage = query.get("passage");
    if (!citation && !passage) {
      setStatus("Open an original-text link from your chat to highlight its source.");
      goToPage(Number(query.get("page")) || 1);
      return;
    }
    target = await getJSON(`${api}/${citation ? "citations" : "passages"}/${encodeURIComponent(citation || passage)}`);
    $("evidence-label").textContent = citation ? "Original evidence" : "Original passage";
    $("quote").textContent = target.quote;
    $("quote").hidden = $("copy-link").hidden = $("return-evidence").hidden = false;
    setStatus(`${citation ? "Exact text located" : "Full passage located"} · PDF page ${target.pages.join(", ")}`);
    for (const box of target.boxes) {
      const mark = document.createElement("div");
      mark.className = "highlight";
      mark.setAttribute("aria-hidden", "true");
      const [x0, y0, x1, y1] = box.rect;
      mark.style.left = `${x0 * 100}%`;
      mark.style.top = `${y0 * 100}%`;
      mark.style.width = `${(x1 - x0) * 100}%`;
      mark.style.height = `${(y1 - y0) * 100}%`;
      document.getElementById(`pdf-page-${box.page}`).append(mark);
    }
    for (const number of target.pages) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button";
      button.dataset.page = number;
      button.textContent = `Page ${number}`;
      button.addEventListener("click", () => goToPage(number, target.boxes.find(box => box.page === number).rect));
      $("target-pages").append(button);
    }
    goToPage(target.boxes[0].page, target.boxes[0].rect);
  }

  async function initialize() {
    metadata = await getJSON(api);
    document.title = `${metadata.title} · Paper reader`;
    $("paper-title").textContent = metadata.title;
    $("download").href = `${api}/source.pdf`;
    $("download").hidden = false;
    $("page-total").textContent = `/ ${metadata.page_count}`;
    $("page-number").max = metadata.page_count;
    if (metadata.low_text_pages.length) {
      $("coverage-warning").hidden = false;
      $("coverage-warning").textContent = `Limited extractable text on PDF pages ${metadata.low_text_pages.join(", ")}. Their original page images remain available.`;
    }
    for (const section of metadata.outline) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = section.title;
      button.style.paddingLeft = `${Math.min(section.level - 1, 3) * 10}px`;
      button.addEventListener("click", () => goToPage(section.page));
      $("outline").append(button);
    }
    $("outline-section").hidden = !metadata.outline.length;
    buildPages();
    $("previous").addEventListener("click", () => goToPage(currentPage - 1));
    $("next").addEventListener("click", () => goToPage(currentPage + 1));
    $("page-number").addEventListener("change", event => goToPage(Number(event.target.value)));
    $("zoom").addEventListener("change", () => { resizePages(); goToPage(currentPage); });
    $("return-evidence").addEventListener("click", () => goToPage(target.boxes[0].page, target.boxes[0].rect));
    $("copy-link").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(location.href); setStatus("Citation link copied."); }
      catch { setStatus("Copy this page's address from your browser to share the citation locally."); }
    });
    pages.addEventListener("scroll", () => {
      if (pendingScroll) return;
      pendingScroll = true;
      requestAnimationFrame(() => {
        const edge = pages.getBoundingClientRect().top + Math.min(160, pages.clientHeight / 3);
        let active = 1;
        for (const page of pages.children) {
          if (page.getBoundingClientRect().top > edge) break;
          active = Number(page.dataset.page);
        }
        setCurrentPage(active);
        pendingScroll = false;
      });
    }, {passive: true});
    new ResizeObserver(resizePages).observe(pages);
    window.addEventListener("popstate", () => showTarget().catch(error => setStatus(error.message, true)));
    await showTarget();
  }

  initialize().catch(error => setStatus(error.message, true));
})();
