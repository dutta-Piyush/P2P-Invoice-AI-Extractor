
const BASE = "http://localhost:8000/api/v1";

// Cache for idempotency keys: { [filename]: { key, ts } }
const _idemKeyCache = {};
const _IDEM_KEY_TTL = 2 * 60 * 1000; // 2 minutes in ms

function getIdemKeyForFile(filename) {
  const now = Date.now();
  const cached = _idemKeyCache[filename];
  if (cached && now - cached.ts < _IDEM_KEY_TTL) return cached.key;
  const key = crypto.randomUUID();
  _idemKeyCache[filename] = { key, ts: now };
  return key;
}

async function parseError(res, fallback) {
  try {
    const body = await res.json();
    if (body.detail) {
      if (Array.isArray(body.detail)) return body.detail.map((e) => e.msg).join("; ");
      return body.detail;
    }
  } catch { /* no json body */ }
  return fallback;
}

export const extract = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  // Use the same idempotency key for the same file name within 2 minutes
  const idemKey = getIdemKeyForFile(file.name);

  const res = await fetch(`${BASE}/extract`, {
    method: "POST",
    headers: { "Idempotency-Key": idemKey },
    body: formData,
  });

  if (!res.ok) throw new Error(await parseError(res, "Extraction failed"));
  return res.json();
};

export async function getRequests(skip = 0, limit = 50) {
  const res = await fetch(`${BASE}/requests?skip=${skip}&limit=${limit}`);
  if (!res.ok) throw new Error(await parseError(res, "Failed to load requests"));
  return res.json();
}

export async function createRequest(payload) {
  const res = await fetch(`${BASE}/requests`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res, "Failed to create request"));
  return res.json();
}

export async function updateRequestStatus(id, status, note = "") {
  const res = await fetch(`${BASE}/requests/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note }),
  });
  if (!res.ok) throw new Error(await parseError(res, "Failed to update status"));
  return res.json();
}
