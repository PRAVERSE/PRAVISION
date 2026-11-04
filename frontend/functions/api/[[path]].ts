// Cloudflare Pages Function: Reverse Proxy for PRAVISION API
export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);
  const targetBackend = "https://april-currently-productive-justice.trycloudflare.com";
  const forwardUrl = new URL(url.pathname + url.search, targetBackend);

  // Copy incoming headers
  const headers = new Headers(context.request.headers);
  headers.set("Host", "april-currently-productive-justice.trycloudflare.com");
  headers.set("X-Forwarded-Host", url.host);
  headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

  const init: RequestInit = {
    method: context.request.method,
    headers: headers,
    redirect: "follow",
  };

  // Pass request body for non-GET/HEAD methods
  if (context.request.method !== "GET" && context.request.method !== "HEAD") {
    init.body = context.request.body;
    // @ts-ignore
    init.duplex = "half";
  }

  const response = await fetch(forwardUrl.toString(), init);

  // Strict CORS headers
  const newHeaders = new Headers(response.headers);
  const origin = context.request.headers.get("Origin");
  const allowedOrigins = ["https://pravision.pages.dev"];
  if (origin && allowedOrigins.includes(origin)) {
    newHeaders.set("Access-Control-Allow-Origin", origin);
    newHeaders.set("Access-Control-Allow-Credentials", "true");
  } else {
    newHeaders.delete("Access-Control-Allow-Origin");
    newHeaders.delete("Access-Control-Allow-Credentials");
  }
  newHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH");
  newHeaders.set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With");

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
};

