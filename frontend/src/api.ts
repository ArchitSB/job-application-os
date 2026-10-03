export type Row = Record<string, unknown> & { id: string };
export type Page = {
  items: Row[];
  total: number;
  page: number;
  page_size: number;
};
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: Record<string, unknown>,
  ) {
    super(String(detail.message || detail.reason || "Request failed"));
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json", "X-Actor": "user" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      response.status,
      data.error || { message: "Request failed" },
    );
  return data as T;
}
export function label(value: unknown): string {
  return value === null || value === undefined
    ? "—"
    : String(value).replaceAll("_", " ");
}
export function date(value: unknown): string {
  return value
    ? new Date(String(value)).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "—";
}
