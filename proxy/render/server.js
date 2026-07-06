import express from "express";
import { createProxyMiddleware } from "http-proxy-middleware";

const ORIGIN = process.env.ONEHUNT_ORIGIN || "http://104.128.137.117";
const PORT = Number(process.env.PORT || 10000);

const app = express();

app.use(
  "/",
  createProxyMiddleware({
    target: ORIGIN,
    changeOrigin: true,
    xfwd: true,
    onProxyReq(proxyReq) {
      proxyReq.setHeader("Host", "104.128.137.117");
    },
  }),
);

app.listen(PORT, "0.0.0.0", () => {
  console.log(`ONEHUNT proxy -> ${ORIGIN} on :${PORT}`);
});
