window.wolfLoader?.start();

window.addEventListener(
    "load",
    () => {
        window.setTimeout(() => window.wolfLoader?.reset(), 900);
    },
    { once: true },
);

const reveals = document.querySelectorAll(".reveal");

const observer = new IntersectionObserver(
    (entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            }
        });
    },
    {
        threshold: 0.18,
    },
);

reveals.forEach((item) => observer.observe(item));
