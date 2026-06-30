import { api } from "@/lib/api";

/** Normalise paginated tracker list responses from GET /physical|financial|outcome */
export function unwrapTrackerResponse(data) {
  if (Array.isArray(data)) {
    return { items: data, total: data.length, page: 1, page_size: data.length };
  }
  return {
    items: data?.items || [],
    total: data?.total ?? 0,
    page: data?.page ?? 1,
    page_size: data?.page_size ?? 500,
  };
}

export function fetchTrackerList(path, params) {
  return api.get(path, { params }).then((r) => unwrapTrackerResponse(r.data));
}
