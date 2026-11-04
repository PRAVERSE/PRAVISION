// Cloudflare Pages Function: Reverse Proxy for PRAVISION API

interface PagesFunctionEnv {
  PRAVISION_BACKEND_URL?: string;
  [key: string]: unknown;
}

interface EventContext<Env, P extends string, Data> {
  request: Request;
  functionPath: string;
  waitUntil: (promise: Promise<unknown>) => void;
  next: (input?: Request | string, init?: RequestInit) => Promise<Response>;
  env: Env;
  params: Record<P, string | string[]>;
  data: Data;
}

type PagesFunction<
  Env = PagesFunctionEnv,
  P extends string = string,
  Data extends Record<string, unknown> = Record<string, unknown>
> = (context: EventContext<Env, P, Data>) => Response | Promise<Response>;

interface CustomRequestInit extends RequestInit {
  duplex?: "half";
}

interface HeadersWithSetCookie extends Headers {
  getSetCookie?: () => string[];
}

export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);
  const targetBackend = (context.env.PRAVISION_BACKEND_URL as string) || "https://lets-bracket-imaging-muslim.trycloudflare.com";
  const backendUrl = new URL(targetBackend);
  const forwardUrl = new URL(url.pathname + url.search, targetBackend);

  const origin = context.request.headers.get("Origin");
  const allowedOrigins = ["https://pravision.pages.dev"];

  // Handle CORS preflight early
  if (context.request.method === "OPTIONS") {
    const preflightHeaders = new Headers();
    if (origin && allowedOrigins.includes(origin)) {
      preflightHeaders.set("Access-Control-Allow-Origin", origin);
      preflightHeaders.set("Access-Control-Allow-Credentials", "true");
    }
    preflightHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH");
    preflightHeaders.set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With");
    preflightHeaders.set("Access-Control-Max-Age", "86400");
    return new Response(null, { status: 204, headers: preflightHeaders });
  }

  // Handle WebSocket upgrade
  if (context.request.headers.get("Upgrade")?.toLowerCase() === "websocket") {
    return fetch(forwardUrl.toString(), context.request);
  }

  // Copy incoming headers
  const headers = new Headers(context.request.headers);
  headers.set("Host", backendUrl.host);
  headers.set("X-Forwarded-Host", url.host);
  headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

  const init: CustomRequestInit = {
    method: context.request.method,
    headers: headers,
    redirect: "follow",
  };

  // Pass request body for non-GET/HEAD methods
  if (context.request.method !== "GET" && context.request.method !== "HEAD") {
    init.body = context.request.body;
    init.duplex = "half";
  }

  const response = await fetch(forwardUrl.toString(), init);

  // Strict CORS headers
  const newHeaders = new Headers(response.headers);
  if (origin && allowedOrigins.includes(origin)) {
    newHeaders.set("Access-Control-Allow-Origin", origin);
    newHeaders.set("Access-Control-Allow-Credentials", "true");
  } else {
    newHeaders.delete("Access-Control-Allow-Origin");
    newHeaders.delete("Access-Control-Allow-Credentials");
  }
  newHeaders.set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH");
  newHeaders.set("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With");

  // Preserve Set-Cookie headers explicitly for authentication session cookies
  const respHeaders = response.headers as HeadersWithSetCookie;
  if (typeof respHeaders.getSetCookie === "function") {
    const cookies: string[] = respHeaders.getSetCookie();
    if (cookies && cookies.length > 0) {
      newHeaders.delete("set-cookie");
      for (const cookie of cookies) {
        newHeaders.append("set-cookie", cookie);
      }
    }
  } else {
    const singleCookie = response.headers.get("set-cookie");
    if (singleCookie) {
      newHeaders.set("set-cookie", singleCookie);
    }
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: newHeaders,
  });
};
