import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "@/locales/en.json";
import hi from "@/locales/hi.json";
import ur from "@/locales/ur.json";
import bn from "@/locales/bn.json";
import ta from "@/locales/ta.json";
import te from "@/locales/te.json";
import mr from "@/locales/mr.json";
import gu from "@/locales/gu.json";
import kn from "@/locales/kn.json";
import ml from "@/locales/ml.json";
import pa from "@/locales/pa.json";

const LANG_KEY = "pmis-lang";
const RTL_LANGS = new Set(["ur"]);

/** EN + HI + 8 regional languages + Urdu (RTL). */
export const SUPPORTED_LANGS = [
  { code: "en", label: "EN" },
  { code: "hi", label: "HI" },
  { code: "bn", label: "BN" },
  { code: "ta", label: "TA" },
  { code: "te", label: "TE" },
  { code: "mr", label: "MR" },
  { code: "gu", label: "GU" },
  { code: "kn", label: "KN" },
  { code: "ml", label: "ML" },
  { code: "pa", label: "PA" },
  { code: "ur", label: "UR" },
];

const LANG_CODES = new Set(SUPPORTED_LANGS.map((l) => l.code));

export function getStoredLang() {
  try {
    const v = localStorage.getItem(LANG_KEY);
    if (v && LANG_CODES.has(v)) return v;
  } catch {
    /* ignore */
  }
  return "en";
}

export function setStoredLang(lng) {
  try {
    localStorage.setItem(LANG_KEY, lng);
  } catch {
    /* ignore */
  }
  applyDocumentDirection(lng);
}

export function applyDocumentDirection(lng) {
  const code = LANG_CODES.has(lng) ? lng : "en";
  const dir = RTL_LANGS.has(code) ? "rtl" : "ltr";
  document.documentElement.setAttribute("dir", dir);
  document.documentElement.setAttribute("lang", code);
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    ur: { translation: ur },
    bn: { translation: bn },
    ta: { translation: ta },
    te: { translation: te },
    mr: { translation: mr },
    gu: { translation: gu },
    kn: { translation: kn },
    ml: { translation: ml },
    pa: { translation: pa },
  },
  lng: getStoredLang(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

applyDocumentDirection(getStoredLang());
i18n.on("languageChanged", applyDocumentDirection);

export default i18n;
