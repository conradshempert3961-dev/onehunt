(function initWolfLoader() {
    const VIDEO_SRC = "/assets/wolf-loader.mp4";
    const SVG_SRC = "/assets/wolf-run.svg";
    let pending = 0;
    let root = null;
    let videoReady = null;

    function createRunner() {
        const runner = document.createElement("div");
        runner.className = "wolf-runner";

        const video = document.createElement("video");
        video.className = "wolf-runner-media wolf-runner-video hidden";
        video.src = VIDEO_SRC;
        video.muted = true;
        video.loop = true;
        video.playsInline = true;
        video.setAttribute("aria-hidden", "true");

        const image = document.createElement("img");
        image.className = "wolf-runner-media wolf-runner-svg";
        image.src = SVG_SRC;
        image.alt = "";

        video.addEventListener("error", () => {
            video.classList.add("hidden");
            image.classList.remove("hidden");
        });

        video.addEventListener("loadeddata", () => {
            videoReady = true;
            image.classList.add("hidden");
            video.classList.remove("hidden");
            video.play().catch(() => {
                video.classList.add("hidden");
                image.classList.remove("hidden");
            });
        });

        runner.appendChild(video);
        runner.appendChild(image);
        return runner;
    }

    function ensureDom() {
        if (root) {
            return root;
        }

        root = document.createElement("div");
        root.id = "wolfLoader";
        root.className = "wolf-loader hidden";
        root.setAttribute("aria-hidden", "true");

        for (let lane = 1; lane <= 3; lane += 1) {
            const laneNode = document.createElement("div");
            laneNode.className = `wolf-loader-lane wolf-loader-lane-${lane}`;
            laneNode.appendChild(createRunner());
            root.appendChild(laneNode);
        }

        document.body.appendChild(root);
        return root;
    }

    function setActive(active) {
        const node = ensureDom();
        node.classList.toggle("hidden", !active);
        node.setAttribute("aria-hidden", active ? "false" : "true");

        if (active && videoReady) {
            node.querySelectorAll(".wolf-runner-video").forEach((video) => {
                if (video.paused) {
                    video.play().catch(() => {});
                }
            });
        }
    }

    window.wolfLoader = {
        start() {
            pending += 1;
            setActive(true);
        },
        stop() {
            pending = Math.max(0, pending - 1);
            if (pending === 0) {
                setActive(false);
            }
        },
        reset() {
            pending = 0;
            setActive(false);
        },
    };
})();
