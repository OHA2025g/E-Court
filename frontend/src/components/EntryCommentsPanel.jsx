import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, formatApiError } from "@/lib/api";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatCircle, PaperPlaneTilt } from "@phosphor-icons/react";
import { toast } from "sonner";

export default function EntryCommentsPanel({ tracker, entryId, open, onOpenChange, entryLabel }) {
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  const comments = useQuery({
    queryKey: ["comments", tracker, entryId],
    queryFn: () => api.get("/comments", { params: { tracker, entry_id: entryId } }).then((r) => r.data),
    enabled: open && !!tracker && !!entryId,
  });

  async function submit(e) {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    try {
      await api.post("/comments", { tracker, entry_id: entryId, body: body.trim() });
      setBody("");
      qc.invalidateQueries({ queryKey: ["comments", tracker, entryId] });
      toast.success("Comment added");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md flex flex-col p-0">
        <SheetHeader className="px-6 py-4 border-b border-slate-200">
          <SheetTitle className="flex items-center gap-2 text-base">
            <ChatCircle size={18} className="text-[#003B73]" />
            Comments
          </SheetTitle>
          {entryLabel && <p className="text-xs text-slate-500 truncate">{entryLabel}</p>}
        </SheetHeader>
        <ScrollArea className="flex-1 px-6 py-4">
          <ul className="space-y-3">
            {(comments.data || []).map((c) => (
              <li key={c.id} className="border border-slate-100 rounded-sm p-3 bg-slate-50/80">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-medium text-slate-700 truncate">{c.author}</span>
                  <span className="text-[10px] font-mono text-slate-400 shrink-0">{c.ts?.slice(0, 16)}</span>
                </div>
                <p className="text-sm text-slate-800 whitespace-pre-wrap break-words">{c.body}</p>
              </li>
            ))}
            {!comments.isLoading && (comments.data?.length || 0) === 0 && (
              <li className="text-sm text-slate-400 text-center py-8">No comments yet.</li>
            )}
          </ul>
        </ScrollArea>
        <form onSubmit={submit} className="border-t border-slate-200 p-4 space-y-2">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={3}
            placeholder="Add a comment… Use @email to mention"
            className="w-full px-3 py-2 border border-slate-300 rounded-sm text-sm focus:outline-none focus:border-[#003B73] resize-none"
          />
          <button
            type="submit"
            disabled={busy || !body.trim()}
            className="w-full bg-[#003B73] hover:bg-[#002B54] disabled:bg-slate-400 text-white px-4 py-2 rounded-sm text-sm uppercase tracking-wider inline-flex items-center justify-center gap-2"
          >
            <PaperPlaneTilt size={14} /> {busy ? "Posting…" : "Post comment"}
          </button>
        </form>
      </SheetContent>
    </Sheet>
  );
}

export function CommentsButton({ onClick, count }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onClick?.(e); }}
      className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-[#003B73] hover:underline"
    >
      <ChatCircle size={12} />
      {count != null && count > 0 ? count : "Comments"}
    </button>
  );
}
