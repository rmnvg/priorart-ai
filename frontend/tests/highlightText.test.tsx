import { isValidElement, type ReactElement } from "react";
import { describe, expect, it } from "vitest";
import { highlightSpans, isSpanFindable } from "@/lib/highlightText";

type Mark = ReactElement<{ children: string; style: { backgroundColor: string } }>;

describe("isSpanFindable", () => {
  it("tolerates the typographic punctuation LLMs substitute when copying", () => {
    expect(isSpanFindable("a non-slip grip", "a non‑slip grip")).toBe(true); // U+2011
    expect(isSpanFindable('the "quick" release', "the “quick” release")).toBe(true);
  });

  it("is case-insensitive but rejects blank or absent spans", () => {
    expect(isSpanFindable("Hollow Segments", "hollow segments")).toBe(true);
    expect(isSpanFindable("hollow segments", "   ")).toBe(false);
    expect(isSpanFindable("hollow segments", "solid core")).toBe(false);
  });
});

describe("highlightSpans", () => {
  it("wraps matches in marks and keeps the original text untouched", () => {
    const nodes = highlightSpans("Four hollow, buoyant segments", [
      { text: "hollow, buoyant", color: "#fef08a", key: "a" },
    ]);
    expect(nodes[0]).toBe("Four ");
    const mark = nodes[1] as Mark;
    expect(isValidElement(mark)).toBe(true);
    expect(mark.props.children).toBe("hollow, buoyant");
    expect(mark.props.style.backgroundColor).toBe("#fef08a");
    expect(nodes[2]).toBe(" segments");
  });

  it("highlights the original characters even when the span used lookalikes", () => {
    const nodes = highlightSpans("a non-slip grip", [{ text: "non‑slip", color: "#fff", key: "a" }]);
    expect((nodes[1] as Mark).props.children).toBe("non-slip");
  });

  it("lets the first span win when two overlap, and skips unfindable spans", () => {
    const nodes = highlightSpans("interlocking hollow segments", [
      { text: "hollow segments", color: "#1", key: "a" },
      { text: "interlocking hollow", color: "#2", key: "b" },
      { text: "not in the text", color: "#3", key: "c" },
    ]);
    const marks = nodes.filter(isValidElement) as Mark[];
    expect(marks).toHaveLength(1);
    expect(marks[0].props.children).toBe("hollow segments");
  });
});
