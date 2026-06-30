import React from "react";
import { render, screen } from "@testing-library/react";
import BulkUploadPanel from "./BulkUploadPanel";

jest.mock("@/lib/api", () => ({
  api: { post: jest.fn() },
  formatApiError: (d) => d || "error",
}));

describe("BulkUploadPanel", () => {
  it("shows upload label when idle", () => {
    render(
      <BulkUploadPanel
        tracker="physical"
        period="2026-06"
        canEdit
        templateUrl="http://example/template"
        onComplete={() => {}}
      />
    );
    expect(screen.getByText(/Upload & preview/i)).toBeInTheDocument();
  });

  it("disables upload when period is missing", () => {
    const { container } = render(
      <BulkUploadPanel
        tracker="physical"
        period=""
        canEdit
        templateUrl="http://example/template"
      />
    );
    const input = container.querySelector('input[type="file"]');
    expect(input).toBeDisabled();
  });
});
