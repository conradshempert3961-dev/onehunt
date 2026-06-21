window.HD = window.HD || {};

HD.formatPrice = (value) => {
    const num = Number(value) || 0;
    return `${num.toLocaleString("ru-RU")} ₽`;
};

HD.setBudget = (input, output) => {
    const el = document.getElementById(input);
    const out = document.getElementById(output);
    if (!el || !out) return;
    const sync = () => {
        out.textContent = HD.formatPrice(el.value);
    };
    el.addEventListener("input", sync);
    sync();
};

HD.bindChips = (selector) => {
    document.querySelectorAll(selector).forEach((chip) => {
        chip.addEventListener("click", () => {
            const group = chip.closest("[data-chip-group]");
            if (!group) return;
            const multi = group.dataset.multi === "true";
            if (!multi) {
                group.querySelectorAll(".chip").forEach((item) => item.classList.remove("is-active", "is-selected"));
                chip.classList.add("is-active");
                return;
            }
            chip.classList.toggle("is-selected");
        });
    });
};

document.addEventListener("DOMContentLoaded", () => {
    HD.bindChips(".chip-row[data-chip-group] .chip");
    HD.bindChips(".chip-grid[data-chip-group] .chip");
    HD.setBudget("budgetRange", "budgetValue");
});
