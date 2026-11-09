"use strict";

(() => {
    const dialog = document.getElementById("reference-picker-dialog");
    if (!dialog) return;
    const search = document.getElementById("reference-picker-search");
    const query = document.getElementById("reference-picker-query");
    const title = document.getElementById("reference-picker-title");
    const status = document.getElementById("reference-picker-status");
    const results = document.getElementById("reference-picker-results");
    const previous = document.getElementById("reference-picker-previous");
    const next = document.getElementById("reference-picker-next");
    let picker, page = 1, controller, serial = 0, opener;

    async function load(number) {
        controller?.abort();
        controller = new AbortController();
        const request = ++serial;
        const target = picker;
        status.textContent = "Загрузка…";
        results.replaceChildren();
        previous.disabled = next.disabled = true;
        const url = new URL(target.dataset.pickerUrl, window.location.origin);
        url.searchParams.set("q", query.value.trim());
        url.searchParams.set("page", number);
        try {
            const response = await fetch(url, {
                headers: {"Accept": "application/json"}, signal: controller.signal,
            });
            if (!response.ok || response.redirected) throw new Error("request failed");
            const data = await response.json();
            if (request !== serial || !dialog.open) return;
            page = data.page;
            status.textContent = data.count ?
                `Найдено: ${data.count}. Страница ${page}.` : "Ничего не найдено.";
            previous.disabled = !data.has_previous;
            next.disabled = !data.has_next;
            for (const item of data.results) {
                const row = document.createElement("tr");
                for (const text of [item.label, item.code || "—"]) {
                    const cell = document.createElement("td");
                    cell.textContent = text;
                    row.append(cell);
                }
                const cell = document.createElement("td");
                const choose = document.createElement("button");
                choose.type = "button";
                choose.className = "btn btn-small";
                choose.textContent = "Выбрать";
                choose.setAttribute("aria-label", `Выбрать ${item.label}`);
                choose.addEventListener("click", () => {
                    const field = target.querySelector('input[type="hidden"]');
                    field.value = item.id;
                    target.querySelector(".reference-picker-value").value = item.label;
                    field.dispatchEvent(new Event("change", {bubbles: true}));
                    dialog.close();
                });
                cell.append(choose);
                row.append(cell);
                results.append(row);
            }
        } catch (error) {
            if (error.name !== "AbortError" && request === serial && dialog.open) {
                status.textContent = "Не удалось загрузить записи. Проверьте доступ и повторите поиск.";
            }
        }
    }
    document.addEventListener("click", (event) => {
        const clear = event.target.closest(".reference-picker-clear");
        if (clear) {
            const target = clear.closest(".reference-picker");
            const field = target.querySelector('input[type="hidden"]');
            field.value = "";
            target.querySelector(".reference-picker-value").value = target.dataset.pickerEmptyLabel;
            field.dispatchEvent(new Event("change", {bubbles: true}));
            return;
        }
        const button = event.target.closest(".reference-picker-open");
        if (!button) return;
        opener = button;
        picker = button.closest(".reference-picker");
        title.textContent = picker.dataset.pickerTitle;
        query.value = "";
        dialog.showModal();
        query.focus();
        load(1);
    });
    search.addEventListener("submit", (event) => {
        event.preventDefault();
        load(1);
    });
    previous.addEventListener("click", () => load(page - 1));
    next.addEventListener("click", () => load(page + 1));
    document.getElementById("reference-picker-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
        ++serial;
        controller?.abort();
        results.replaceChildren();
        opener?.focus();
    });
})();
