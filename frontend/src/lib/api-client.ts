const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface ApiError {
  detail: string;
  status: number;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;

    const res = await fetch(url, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: "Request failed" }));
      const error: ApiError = {
        detail: body.detail || "Request failed",
        status: res.status,
      };
      throw error;
    }

    if (res.status === 204) return undefined as T;
    return res.json();
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

    const res = await fetch(url, {
      method: "POST",
      credentials: "include",
      body: formData,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: "Upload failed" }));
      const error: ApiError = {
        detail: body.detail || "Upload failed",
        status: res.status,
      };
      throw error;
    }

    return res.json();
  }
}

export const api = new ApiClient(API_BASE);
