import type { SketchComponent, SketchReading, SketchRelationship } from "@/types/analysis";

// A hand-drawn-style pot-in-pot cooler, for trying sketch input without a
// camera. Read live by the vision model, so it needs a Groq key.
export const SAMPLE_SKETCH_URL = "/samples/clay-cooler-sketch.svg";

// The inventor's corrected version of what the vision model read from their
// sketch. It's what gets searched, via the description composed below —
// never the model's raw reading.
export interface SketchDraft {
  purpose: string;
  parts: SketchComponent[];
  connections: SketchRelationship[];
  details: string; // anything the drawing doesn't show
}

export function draftFromReading(reading: SketchReading): SketchDraft {
  return {
    purpose: reading.purpose,
    parts: reading.components.map((c) => ({ ...c })),
    connections: reading.relationships.map((r) => ({ ...r })),
    details: "",
  };
}

/** An id no current part uses, so connections stay attached to the right
 * part when parts are added and removed. */
export function nextPartId(parts: SketchComponent[]): string {
  const used = new Set(parts.map((p) => p.id));
  let n = parts.length + 1;
  while (used.has(`C${n}`)) n++;
  return `C${n}`;
}

/** Removing a part takes its connections with it. */
export function removePart(draft: SketchDraft, id: string): SketchDraft {
  return {
    ...draft,
    parts: draft.parts.filter((p) => p.id !== id),
    connections: draft.connections.filter((c) => c.source !== id && c.target !== id),
  };
}

// Lower-cases a name's first letter for use mid-sentence, unless it's an
// acronym ("LED strip" stays as written).
function inline(name: string): string {
  const trimmed = name.trim();
  if (trimmed.length > 1 && trimmed[1] === trimmed[1].toUpperCase() && /[A-Z]/.test(trimmed[1])) {
    return trimmed;
  }
  return trimmed.charAt(0).toLowerCase() + trimmed.slice(1);
}

function sentence(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (!trimmed) return "";
  const capitalized = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  return /[.!?।]$/.test(capitalized) ? capitalized : `${capitalized}.`;
}

/** The idea text searched for a sketch: purpose, parts, how they work
 * together, then anything the inventor added. Plain enough to read back
 * and edit, specific enough for the query generator. Parts without a name
 * (and their connections) are left out. */
export function composeIdeaFromSketch(draft: SketchDraft): string {
  const named = new Map(
    draft.parts.filter((p) => p.name.trim()).map((p) => [p.id, p] as const)
  );
  const pieces: string[] = [];

  const purpose = sentence(draft.purpose);
  if (purpose) pieces.push(purpose);

  const parts = [...named.values()].map((p) => {
    const description = p.description.trim().replace(/[.\s]+$/, "");
    return description ? `${inline(p.name)} (${inline(description)})` : inline(p.name);
  });
  if (parts.length) pieces.push(`It is made up of: ${parts.join("; ")}.`);

  const connections = draft.connections
    .filter((c) => named.has(c.source) && named.has(c.target) && c.relation.trim())
    .map(
      (c) =>
        `the ${inline(named.get(c.source)!.name)} ${c.relation.trim()} the ${inline(named.get(c.target)!.name)}`
    );
  if (connections.length) pieces.push(sentence(`How the parts work together: ${connections.join("; ")}`));

  const details = sentence(draft.details);
  if (details) pieces.push(details);

  return pieces.join(" ");
}
