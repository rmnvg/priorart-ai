import { describe, expect, it } from "vitest";
import { composeIdeaFromSketch, draftFromReading, nextPartId, removePart, type SketchDraft } from "@/lib/sketch";

function cooler(overrides: Partial<SketchDraft> = {}): SketchDraft {
  return {
    purpose: "keeps vegetables cool without electricity",
    parts: [
      { id: "C1", name: "Outer clay pot", description: "Unglazed, porous." },
      { id: "C2", name: "Inner pot", description: "" },
      { id: "C3", name: "Wet sand", description: "Fills the gap" },
    ],
    connections: [
      { source: "C2", target: "C1", relation: "sits inside" },
      { source: "C3", target: "C2", relation: "surrounds" },
    ],
    details: "",
    ...overrides,
  };
}

describe("composeIdeaFromSketch", () => {
  it("writes purpose, parts and connections as plain sentences", () => {
    expect(composeIdeaFromSketch(cooler())).toBe(
      "Keeps vegetables cool without electricity. " +
        "It is made up of: outer clay pot (unglazed, porous); inner pot; wet sand (fills the gap). " +
        "How the parts work together: the inner pot sits inside the outer clay pot; " +
        "the wet sand surrounds the inner pot."
    );
  });

  it("leaves out unnamed parts and the connections that use them", () => {
    const draft = cooler();
    draft.parts[2] = { ...draft.parts[2], name: "  " };
    const text = composeIdeaFromSketch(draft);
    expect(text).not.toContain("sand");
    expect(text).not.toContain("surrounds");
    expect(text).toContain("the inner pot sits inside the outer clay pot");
  });

  it("keeps acronyms and adds the inventor's details at the end", () => {
    const text = composeIdeaFromSketch(
      cooler({
        parts: [{ id: "C1", name: "LED strip", description: "" }],
        connections: [],
        details: "सुबह पानी डालें",
      })
    );
    expect(text).toContain("It is made up of: LED strip.");
    expect(text.endsWith("सुबह पानी डालें.")).toBe(true);
  });

  it("is empty for an empty draft", () => {
    expect(composeIdeaFromSketch({ purpose: "", parts: [], connections: [], details: "" })).toBe("");
  });
});

describe("editing a sketch draft", () => {
  it("removing a part removes its connections", () => {
    const draft = removePart(cooler(), "C2");
    expect(draft.parts.map((p) => p.id)).toEqual(["C1", "C3"]);
    expect(draft.connections).toEqual([]);
  });

  it("new parts get an id no existing part uses", () => {
    const parts = removePart(cooler(), "C2").parts; // C1, C3
    expect(nextPartId(parts)).toBe("C4");
    expect(nextPartId([])).toBe("C1");
  });

  it("a draft copies the reading rather than sharing it", () => {
    const reading = {
      purpose: "p",
      components: [{ id: "C1", name: "pot", description: "" }],
      relationships: [],
      uncertain: ["glazed?"],
    };
    const draft = draftFromReading(reading);
    draft.parts[0].name = "edited";
    expect(reading.components[0].name).toBe("pot");
    expect(draft.details).toBe("");
  });
});
