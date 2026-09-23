import { describe, expect, it } from "vitest";
import { englishLabel, labelsFor } from "@/lib/i18n";
import { analysis } from "./fixtures";

const hindi = analysis({
  localized: {
    language_code: "hi",
    language_name: "Hindi",
    plain_summary: "",
    differentiation_suggestions: [],
    citation_claims: [],
    ui_labels: { novelty_verdict: "नवीनता निर्णय", based_on: "" },
  },
});

describe("labelsFor", () => {
  it("uses the report's language, falling back to English per missing or empty label", () => {
    const t = labelsFor(hindi, false);
    expect(t("novelty_verdict")).toBe("नवीनता निर्णय");
    expect(t("based_on")).toBe(englishLabel("based_on"));
    expect(t("apply_recheck")).toBe(englishLabel("apply_recheck"));
  });

  it("returns English when the reader flips the toggle, or the report isn't localized", () => {
    expect(labelsFor(hindi, true)("novelty_verdict")).toBe("Novelty verdict");
    expect(labelsFor(analysis(), false)("novelty_verdict")).toBe("Novelty verdict");
  });
});
