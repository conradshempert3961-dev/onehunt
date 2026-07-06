/** Stable HTTPS proxy to ONEHUNT VDS (no ephemeral trycloudflare URL). */
const ORIGIN = "http://104.128.137.117";

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    const incoming = new URL(request.url);
    const target = new URL(`${incoming.pathname}${incoming.search}`, ORIGIN);

    const headers = new Headers(request.headers);
    headers.set("Host", "104.128.137.117");
    headers.set("X-Forwarded-Proto", "https");
    headers.set("X-Forwarded-Host", incoming.host);
    headers.delete("cf-connecting-ip");

    const init = {
      method: request.method,
      headers,
      redirect: "manual",
    };
    if (request.method !== "GET" && request.method !== "HEAD") {
      init.body = request.body;
    }

    const upstream = await fetch(target.toString(), init);
    const responseHeaders = new Headers(upstream.headers);
    Object.entries(corsHeaders(request)).forEach(([key, value]) => {
      responseHeaders.set(key, value);
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  },
};

function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Telegram-Init-Data",
  };
}
