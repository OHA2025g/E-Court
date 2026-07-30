import React from "react";

/** Compact DoJ-style emblem for demo DoJ reports (decorative branding). */
export default function DojEmblem({ className = "" }) {
  return (
    <div className={`doj-emblem ${className}`.trim()} aria-hidden="true">
      <svg viewBox="0 0 64 64" width="48" height="48">
        <circle cx="32" cy="32" r="31" fill="#1a237e" />
        <circle cx="32" cy="32" r="26" fill="none" stroke="#c9a227" strokeWidth="2" />
        <g fill="#c9a227">
          <ellipse cx="32" cy="22" rx="7" ry="5" />
          <rect x="28" y="26" width="8" height="14" rx="1" />
          <path d="M18 40 L32 28 L46 40 Z" />
        </g>
        <text x="32" y="54" textAnchor="middle" fill="#c9a227" fontSize="6" fontFamily="serif">सत्यमेव जयते</text>
      </svg>
      <div className="doj-emblem-text">
        <div className="doj-emblem-hi">न्याय विभाग</div>
        <div className="doj-emblem-en">DEPARTMENT OF JUSTICE</div>
      </div>
      <style>{`
        .doj-emblem { display: flex; flex-direction: row; align-items: center; gap: 8px; justify-content: flex-end; }
        .doj-emblem-text { text-align: left; line-height: 1.15; }
        .doj-emblem-hi { font-size: 13px; font-weight: 700; color: #1a237e; }
        .doj-emblem-en { font-size: 8px; font-weight: 700; color: #1a237e; letter-spacing: 0.02em; }
      `}</style>
    </div>
  );
}
