import React, { useRef, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Paperclip, X, DownloadSimple, Spinner } from "@phosphor-icons/react";

/**
 * Lightweight attachment widget for PMU tasks / DPR deliverables.
 * Props:
 *   value     — array of file ids
 *   onChange  — (newIds) => void
 *   disabled  — boolean
 */
export default function FileAttachments({ value = [], onChange, disabled }) {
  const inputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [metaCache, setMetaCache] = useState({});

  React.useEffect(() => {
    const missing = (value || []).filter((id) => !metaCache[id]);
    if (!missing.length) return;
    Promise.all(
      missing.map((id) =>
        api.get(`/files/${id}/meta`).then((r) => [id, r.data]).catch(() => [id, null])
      )
    ).then((pairs) => {
      setMetaCache((m) => {
        const next = { ...m };
        pairs.forEach(([id, meta]) => { if (meta) next[id] = meta; });
        return next;
      });
    });
  }, [value]);

  async function onPick(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    try {
      const ids = [];
      for (const f of files) {
        const fd = new FormData();
        fd.append("file", f);
        const r = await api.post("/files/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
        ids.push(r.data.id);
        setMetaCache((m) => ({ ...m, [r.data.id]: { original_filename: r.data.filename, size: r.data.size, content_type: r.data.content_type } }));
      }
      onChange([...(value || []), ...ids]);
      toast.success(`${files.length} file(s) uploaded`);
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Upload failed");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function remove(id) {
    onChange((value || []).filter((x) => x !== id));
  }

  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium mb-1">Evidence Attachments</div>
      <div className="space-y-1">
        {(value || []).map((id) => {
          const m = metaCache[id];
          return (
            <div key={id} className="flex items-center justify-between gap-2 border border-slate-200 rounded-sm px-2 py-1 bg-slate-50">
              <a
                href={`${process.env.REACT_APP_BACKEND_URL}/api/files/${id}`}
                target="_blank" rel="noreferrer"
                className="flex items-center gap-2 text-xs text-slate-700 hover:text-[#003B73] truncate min-w-0"
              >
                <DownloadSimple size={14} className="shrink-0" />
                <span className="truncate">{m?.original_filename || id}</span>
                {m?.size != null && <span className="text-slate-400 shrink-0">· {Math.round(m.size / 1024)} KB</span>}
              </a>
              {!disabled && (
                <button type="button" onClick={() => remove(id)} className="text-red-500 hover:text-red-700">
                  <X size={14} />
                </button>
              )}
            </div>
          );
        })}
      </div>
      {!disabled && (
        <label className="mt-2 inline-flex items-center gap-2 text-xs text-[#003B73] hover:text-[#002B54] cursor-pointer">
          {uploading ? <Spinner size={14} className="animate-spin" /> : <Paperclip size={14} />}
          <span className="underline">{uploading ? "Uploading…" : "Attach file(s)"}</span>
          <input ref={inputRef} type="file" multiple onChange={onPick} className="hidden" data-testid="tm-file-input"
                 accept=".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.xls,.xlsx,.csv,.txt" />
        </label>
      )}
      <div className="text-[10px] text-slate-400 mt-1">Max 10 MB · pdf, doc, xls, csv, png/jpg</div>
    </div>
  );
}
