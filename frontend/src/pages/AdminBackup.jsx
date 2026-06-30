import React, { useState } from "react";
import { api, formatApiError, BACKEND_URL } from "@/lib/api";
import { useAdminLabels } from "@/lib/useAdminLabels";
import Card from "@/components/Card";
import { toast } from "sonner";
import { Upload, Download } from "@phosphor-icons/react";
import { SelectField } from "@/pages/PhysicalTracker";

export default function AdminBackup() {
  const { backup: b } = useAdminLabels();
  const [mode, setMode] = useState("merge");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function onPick(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    const txt = await f.text();
    setText(txt);
    toast.success(b.loadedFile(Math.round(f.size / 1024)));
  }

  async function restore() {
    if (!text) { toast.error(b.pasteOrLoad); return; }
    let parsed;
    try { parsed = JSON.parse(text); }
    catch (e) { toast.error(b.invalidJson(e.message)); return; }
    if (!parsed.collections) { toast.error(b.missingCollections); return; }
    if (!window.confirm(b.restoreConfirm(mode, b.replaceHint, b.mergeHint))) return;
    setBusy(true); setResult(null);
    try {
      const r = await api.post("/admin/restore", { collections: parsed.collections, mode });
      setResult(r.data);
      toast.success(b.restoreComplete);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setBusy(false); }
  }

  return (
    <div className="space-y-6">
      <Card title={b.backupTitle} subtitle={b.backupSubtitle}>
        <div className="p-4 flex items-center gap-3">
          <a data-testid="backup-download-btn" href={`${BACKEND_URL}/api/admin/backup`} target="_blank" rel="noreferrer"
            className="bg-[#003B73] hover:bg-[#002B54] text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
            <Download size={14} /> {b.downloadBackup}
          </a>
          <span className="text-xs text-slate-500">{b.downloadHint}</span>
        </div>
      </Card>

      <Card title={b.restoreTitle} subtitle={b.restoreSubtitle}>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <SelectField label={b.fieldMode} value={mode} onChange={setMode}
              options={[{ label: b.modeMerge, value: "merge" }, { label: b.modeReplace, value: "replace" }]} />
            <label className="block sm:col-span-2">
              <span className="text-[10px] uppercase tracking-[0.2em] text-slate-600 font-medium">{b.loadJsonFile}</span>
              <input type="file" accept=".json" onChange={onPick} className="mt-1 text-sm" />
            </label>
          </div>
          <textarea
            data-testid="restore-json-textarea"
            value={text} onChange={(e) => setText(e.target.value)}
            placeholder={b.jsonPlaceholder}
            rows={10}
            className="w-full font-mono text-xs px-3 py-2 border border-slate-300 rounded-sm bg-white focus:outline-none focus:border-[#003B73]"
          />
          <button data-testid="restore-btn" disabled={busy || !text} onClick={restore}
            className="bg-amber-600 hover:bg-amber-700 disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center gap-2">
            <Upload size={14} /> {busy ? b.restoring : b.runRestore(mode)}
          </button>
          {result && (
            <div className="mt-3 bg-slate-50 border border-slate-200 rounded-sm p-3">
              <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-1">{b.result}</div>
              <pre className="text-xs font-mono text-slate-700 whitespace-pre-wrap">{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </div>
      </Card>

      <Card title={b.cautionTitle}>
        <div className="p-4 text-xs text-slate-600 space-y-2">
          <p>{b.caution1}</p>
          <p>{b.caution2}</p>
          <p>{b.caution3}</p>
          <p>{b.caution4}</p>
        </div>
      </Card>
    </div>
  );
}
