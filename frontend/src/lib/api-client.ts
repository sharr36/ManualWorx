const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const DEFAULT_TIMEOUT_MS = 30_000;
const MAX_RETRIES = 2;
const RETRY_BACKOFF_MS = 1000;

interface ApiError {
  detail: string;
  status: number;
  message: string;
}

function createApiError(detail: string, status: number): ApiError {
  const err = new Error(detail) as Error & ApiError;
  err.detail = detail;
  err.status = status;
  return err;
}

function isRetryable(status: number): boolean {
  return status >= 500 || status === 0; // 5xx or network error
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {},
    config: { timeout?: number; retries?: number } = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const timeout = config.timeout ?? DEFAULT_TIMEOUT_MS;
    const maxRetries = config.retries ?? MAX_RETRIES;

    let lastError: ApiError | null = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      try {
        const res = await fetch(url, {
          ...options,
          credentials: "include",
          signal: controller.signal,
          headers: {
            "Content-Type": "application/json",
            ...options.headers,
          },
        });

        clearTimeout(timeoutId);

        // Handle 401 — redirect to login
        if (res.status === 401) {
          if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
            window.location.href = "/login";
          }
          throw createApiError("Session expired. Please log in again.", 401);
        }

        // Handle 429 — rate limited
        if (res.status === 429) {
          const retryAfter = res.headers.get("Retry-After");
          const waitMs = retryAfter ? parseInt(retryAfter, 10) * 1000 : RETRY_BACKOFF_MS * (attempt + 1);
          if (attempt < maxRetries) {
            await new Promise((r) => setTimeout(r, waitMs));
            continue;
          }
          const body = await res.json().catch(() => ({ detail: "Rate limit exceeded" }));
          throw createApiError(body.detail || "Rate limit exceeded", 429);
        }

        if (!res.ok) {
          const body = await res.json().catch(() => ({ detail: "Request failed" }));
          const err = createApiError(body.detail || "Request failed", res.status);

          // Retry on 5xx
          if (isRetryable(res.status) && attempt < maxRetries) {
            lastError = err;
            await new Promise((r) => setTimeout(r, RETRY_BACKOFF_MS * Math.pow(2, attempt)));
            continue;
          }

          throw err;
        }

        if (res.status === 204) return undefined as T;
        return res.json();
      } catch (e) {
        clearTimeout(timeoutId);

        // AbortError means timeout
        if (e instanceof DOMException && e.name === "AbortError") {
          const err = createApiError("Request timed out", 0);
          if (attempt < maxRetries) {
            lastError = err;
            await new Promise((r) => setTimeout(r, RETRY_BACKOFF_MS * Math.pow(2, attempt)));
            continue;
          }
          throw err;
        }

        // Network errors — retry
        if (e instanceof TypeError && attempt < maxRetries) {
          lastError = createApiError("Network error", 0);
          await new Promise((r) => setTimeout(r, RETRY_BACKOFF_MS * Math.pow(2, attempt)));
          continue;
        }

        throw e;
      }
    }

    throw lastError || createApiError("Request failed after retries", 0);
  }

  get<T>(path: string) {
    return this.request<T>(path, { method: "GET" });
  }

  post<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  patch<T>(path: string, body?: unknown) {
    return this.request<T>(path, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: "DELETE" });
  }

  async uploadFile<T>(
    path: string,
    file: File,
    metadata: Record<string, string> = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const formData = new FormData();
    formData.append("file", file);
    for (const [key, value] of Object.entries(metadata)) {
      if (value !== undefined && value !== null) {
        formData.append(key, value);
      }
    }

    // Upload: longer timeout, no retries (large body)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300_000); // 5 min for uploads

    try {
      const res = await fetch(url, {
        method: "POST",
        credentials: "include",
        body: formData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (res.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        throw createApiError("Session expired", 401);
      }

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: "Upload failed" }));
        throw createApiError(body.detail || "Upload failed", res.status);
      }

      return res.json();
    } catch (e) {
      clearTimeout(timeoutId);
      if (e instanceof DOMException && e.name === "AbortError") {
        throw createApiError("Upload timed out", 0);
      }
      throw e;
    }
  }

  async stream(
    path: string,
    body: unknown,
    onToken: (text: string) => void,
    onDone: (data: Record<string, unknown>) => void,
    onError?: (error: string) => void,
    onClaims?: (data: Record<string, unknown>) => void
  ): Promise<void> {
    const url = `${this.baseUrl}${path}`;

    const controller = new AbortController();
    // Longer timeout for streaming — 2 minutes
    const timeoutId = setTimeout(() => controller.abort(), 120_000);

    try {
      const res = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (res.status === 401) {
        if (typeof window !== "undefined") window.location.href = "/login";
        onError?.("Session expired. Please log in again.");
        return;
      }

      if (!res.ok) {
        const errBody = await res
          .json()
          .catch(() => ({ detail: "Stream failed" }));
        onError?.(errBody.detail || "Stream failed");
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        onError?.("No response stream");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === "token") {
              onToken(data.text);
            } else if (data.type === "done") {
              onDone(data);
            } else if (data.type === "claims") {
              onClaims?.(data);
            }
          } catch {
            // skip malformed events
          }
        }
      }
    } catch (e) {
      clearTimeout(timeoutId);
      if (e instanceof DOMException && e.name === "AbortError") {
        onError?.("Request timed out");
        return;
      }
      onError?.(e instanceof Error ? e.message : "Stream failed");
    }
  }
}

export const api = new ApiClient(API_BASE);
