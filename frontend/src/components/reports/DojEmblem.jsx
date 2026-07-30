import React from "react";

/**
 * Official Department of Justice wordmark (Ashoka Lion Capital + न्याय विभाग).
 * Used top-right on demo DoJ-style reports.
 */
export default function DojEmblem({ className = "", height = 56 }) {
  return (
    <div className={`doj-emblem ${className}`.trim()}>
      <img
        src="/doj-logo.png"
        alt="Department of Justice — न्याय विभाग"
        className="doj-emblem-img"
        style={{ height, width: "auto" }}
      />
      <style>{`
        .doj-emblem {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          flex-shrink: 0;
        }
        .doj-emblem-img {
          display: block;
          height: ${typeof height === "number" ? `${height}px` : height};
          width: auto;
          max-width: 220px;
          object-fit: contain;
        }
      `}</style>
    </div>
  );
}
