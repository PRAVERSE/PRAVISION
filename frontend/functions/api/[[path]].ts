// Cloudflare Pages Function: Production Reverse Proxy for PRAVISION API

interface Fetcher {
  fetch: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
}

interface PagesFunctionEnv {
  PRAVISION_BACKEND?: Fetcher;
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

function isValidIpv4(ip: string): boolean {
  const parts = ip.split(".");
  if (parts.length !== 4) return false;
  for (const part of parts) {
    if (!/^\d{1,3}$/.test(part)) return false;
    const n = parseInt(part, 10);
    if (n < 0 || n > 255) return false;
    if (part.length > 1 && part.startsWith("0")) return false;
  }
  return true;
}

function isValidIpv6(ip: string): boolean {
  const ipv6Regex = /^(([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))$/;
  return ipv6Regex.test(ip);
}

function isValidIpAddress(ip: string): boolean {
  if (!ip || typeof ip !== "string") return false;
  const trimmed = ip.trim();
  return isValidIpv4(trimmed) || isValidIpv6(trimmed);
}

export const onRequest: PagesFunction = async (context) => {
  const url = new URL(context.request.url);
  const origin = context.request.headers.get("Origin");
  const allowedOrigins = ["https://pravision.pages.dev"];

  // Handle CORS preflight early with HTTP 204
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

  // Determine backend destination (VPC Service binding or explicitly configured environment URL)
  const vpcService = context.env.PRAVISION_BACKEND;
  const envBackendUrl = (context.env.PRAVISION_BACKEND_URL as string) || "";

  // Copy incoming headers and validate authoritative Cloudflare edge client IP
  const headers = new Headers(context.request.headers);
  const rawEdgeClientIp = context.request.headers.get("CF-Connecting-IP") || context.request.headers.get("cf-connecting-ip");
  const edgeClientIp = rawEdgeClientIp ? rawEdgeClientIp.trim() : "";

  if (edgeClientIp && isValidIpAddress(edgeClientIp)) {
    headers.set("CF-Connecting-IP", edgeClientIp);
    headers.set("X-Forwarded-For", edgeClientIp);
  } else {
    // Strip both headers completely so no untrusted visitor-supplied XFF reaches upstream
    headers.delete("CF-Connecting-IP");
    headers.delete("cf-connecting-ip");
    headers.delete("X-Forwarded-For");
    headers.delete("x-forwarded-for");
  }
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

  let response: Response;

  try {
    if (vpcService && typeof vpcService.fetch === "function") {
      // Route through permanent Cloudflare Tunnel via VPC Service Binding
      const forwardPath = url.pathname + url.search;
      headers.set("Host", "127.0.0.1:8000");
      response = await vpcService.fetch(new URL(forwardPath, "http://127.0.0.1:8000").toString(), init);
    } else if (envBackendUrl) {
      // Route through explicitly configured persistent backend URL
      const backendUrl = new URL(envBackendUrl);
      headers.set("Host", backendUrl.host);
      const forwardUrl = new URL(url.pathname + url.search, envBackendUrl);

      // Handle WebSocket upgrade
      if (context.request.headers.get("Upgrade")?.toLowerCase() === "websocket") {
        return fetch(forwardUrl.toString(), context.request);
      }

      response = await fetch(forwardUrl.toString(), init);
    } else {
      const correlationId = crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Math.random().toString(36).substring(2, 10);
      console.error(`[GATEWAY-CONFIG-${correlationId}] Upstream gateway misconfigured: Neither PRAVISION_BACKEND nor PRAVISION_BACKEND_URL available.`);
      return new Response(
        JSON.stringify({
          detail: "Bad Gateway: Upstream service temporarily unavailable.",
          correlation_id: correlationId,
          status: "gateway_error"
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json" }
        }
      );
    }
  } catch (err: unknown) {
    const correlationId = crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Math.random().toString(36).substring(2, 10);
    const errorMsg = err instanceof Error ? err.message : String(err);
    console.error(`[GATEWAY-ERR-${correlationId}] Upstream connection failure:`, errorMsg);
    return new Response(
      JSON.stringify({
        detail: "Bad Gateway: Upstream service temporarily unavailable.",
        correlation_id: correlationId,
        status: "gateway_error"
      }),
      {
        status: 502,
        headers: { "Content-Type": "application/json" }
      }
    );
  }

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
