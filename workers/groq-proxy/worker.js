const GROQ_ORIGIN = "https://api.groq.com";

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(request),
      });
    }

    if (request.method !== "POST") {
      return json({ error: { message: "Only POST is allowed" } }, 405, request);
    }

    const auth = request.headers.get("Authorization");
    if (!auth) {
      return json({ error: { message: "Authorization header is required" } }, 401, request);
    }

    const url = new URL(request.url);
    const targetPath = url.pathname.startsWith("/openai/")
      ? url.pathname
      : `/openai/v1${url.pathname === "/" ? "/chat/completions" : url.pathname}`;
    const targetUrl = `${GROQ_ORIGIN}${targetPath}${url.search}`;

    const headers = new Headers();
    headers.set("Authorization", auth);
    headers.set("Content-Type", request.headers.get("Content-Type") || "application/json");
    headers.set("Accept", "application/json");
    headers.set("User-Agent", "ONEHUNT-Groq-Proxy/1.0");

    const upstream = await fetch(targetUrl, {
      method: "POST",
      headers,
      body: request.body,
    });

    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        ...corsHeaders(request),
        "Content-Type": upstream.headers.get("Content-Type") || "application/json",
      },
    });
  },
};

function corsHeaders(request) {
  const origin = request.headers.get("Origin") || "*";
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
  };
}

function json(payload, status, request) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...corsHeaders(request),
      "Content-Type": "application/json",
    },
  });
}
