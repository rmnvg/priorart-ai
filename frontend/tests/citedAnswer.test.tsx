import { isValidElement, type ReactElement } from "react";
import { describe, expect, it } from "vitest";
import { renderCitedAnswer } from "@/lib/citedAnswer";

const sources = [
  { key: "D7", id: "a", title: "Paddle shaft", link: "https://x/a" },
  { key: "D2", id: "b", title: "Inflatable paddle", link: "https://x/b" },
];

type Link = ReactElement<{ href: string; children: number }>;

describe("renderCitedAnswer", () => {
  it("numbers citations by first appearance and links each one", () => {
    const nodes = renderCitedAnswer("Closest [D7], also [D2] and again [D7].", sources);
    const links = nodes.filter(isValidElement) as Link[];
    expect(links.map((l) => l.props.children)).toEqual([1, 2, 1]);
    expect(links[1].props.href).toBe("https://x/b");
    expect(nodes[0]).toBe("Closest ");
  });

  it("drops keys that have no source", () => {
    const nodes = renderCitedAnswer("Unknown [D9] here.", sources);
    expect(nodes.filter(isValidElement)).toHaveLength(0);
    expect(nodes.filter((n) => typeof n === "string").join("")).toBe("Unknown  here.");
  });
});
