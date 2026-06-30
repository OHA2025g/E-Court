import React from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Component name with optional description on hover (Financial Tracker).
 */
export default function ComponentNameCell({ name, description, children }) {
  const tip = (description || "").trim();
  const label = (
    <span className="inline-flex items-center gap-1">
      <span className={tip ? "cursor-help border-b border-dotted border-slate-400/70" : undefined}>
        {name}
      </span>
      {children}
    </span>
  );

  if (!tip) return label;

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        {label}
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="max-w-xs sm:max-w-sm whitespace-normal text-left leading-relaxed bg-slate-900 text-white border-slate-800 px-3 py-2"
      >
        {tip}
      </TooltipContent>
    </Tooltip>
  );
}
