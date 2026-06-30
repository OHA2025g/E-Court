import React from "react";

/** Keyboard-focusable scroll container (WCAG 2.1.1 scrollable-region-focusable). */
export default function ScrollRegion({ className = "", label, children, ...props }) {
  return (
    <div
      tabIndex={0}
      role="region"
      aria-label={label}
      className={className}
      {...props}
    >
      {children}
    </div>
  );
}
