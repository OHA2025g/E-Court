import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { Toaster } from "sonner";
import "@/index.css";
import App from "@/App";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import i18n from "@/lib/i18n";
import { injectRagCssVars } from "@/lib/ragColors";

injectRagCssVars();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    const swUrl = `${process.env.PUBLIC_URL || ""}/sw.js`;
    navigator.serviceWorker.register(swUrl).catch(() => undefined);
  });
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 } },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <QueryClientProvider client={queryClient}>
    <I18nextProvider i18n={i18n}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <App />
            <Toaster position="top-right" closeButton />
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </I18nextProvider>
  </QueryClientProvider>,
);
