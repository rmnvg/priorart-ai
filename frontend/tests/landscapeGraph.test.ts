import { describe, expect, it } from "vitest";
import {
  buildLandscapeGraph,
  CLUSTER_COLORS,
  IDEA_NODE_COLOR,
  OTHER_CLUSTER_COLOR,
} from "@/lib/landscapeGraph";
import { analysis, patent } from "./fixtures";

describe("buildLandscapeGraph", () => {
  it("puts the idea at the center and links every result to it", () => {
    const graph = buildLandscapeGraph(
      analysis({ ranked_results: [patent({ id: "a" }), patent({ id: "b" })] })
    );
    const idea = graph.nodes.find((n) => n.isIdea)!;
    expect(idea.clusterColor).toBe(IDEA_NODE_COLOR);
    const toIdea = graph.links.filter((l) => l.source === idea.id);
    expect(toIdea.map((l) => l.target).sort()).toEqual(["a", "b"]);
  });

  it("pulls closer matches nearer the idea", () => {
    const graph = buildLandscapeGraph(
      analysis({
        ranked_results: [patent({ id: "close", relevance_score: 0.9 }), patent({ id: "far", relevance_score: 0.1 })],
      })
    );
    const distance = (id: string) => graph.links.find((l) => l.target === id)!.distance;
    expect(distance("close")).toBeLessThan(distance("far"));
  });

  it("colors only the three most common CPC subclasses; the rest fold into Other", () => {
    const results = [
      ...["a1", "a2", "a3", "a4"].map((id) => patent({ id, cpc_code: "A01B1/00" })),
      ...["b1", "b2", "b3"].map((id) => patent({ id, cpc_code: "B63H16/04" })),
      ...["c1", "c2"].map((id) => patent({ id, cpc_code: "C02F1/00" })),
      patent({ id: "d1", cpc_code: "D06F1/00" }),
      patent({ id: "scholar", source_type: "scholar", cpc_code: null }),
    ];
    const graph = buildLandscapeGraph(analysis({ ranked_results: results }));
    const color = (id: string) => graph.nodes.find((n) => n.id === id)!.clusterColor;
    expect(color("a1")).toBe(CLUSTER_COLORS[0]);
    expect(color("b1")).toBe(CLUSTER_COLORS[1]);
    expect(color("c1")).toBe(CLUSTER_COLORS[2]);
    expect(color("d1")).toBe(OTHER_CLUSTER_COLOR);
    expect(color("scholar")).toBe(OTHER_CLUSTER_COLOR);
  });

  it("draws citation edges only between nodes on the graph, and adds them to the legend", () => {
    const graph = buildLandscapeGraph(
      analysis({
        ranked_results: [patent({ id: "a" }), patent({ id: "b" })],
        citation_network: {
          discoveries: [],
          references_scanned: 2,
          edges: [
            { source: "a", target: "b" },
            { source: "a", target: "patent/NOT_ON_GRAPH/en" },
          ],
        },
      })
    );
    const citations = graph.links.filter((l) => l.kind === "citation");
    expect(citations).toHaveLength(1);
    expect(citations[0]).toMatchObject({ source: "a", target: "b" });
    expect(graph.legend.some((e) => e.shape === "arrow")).toBe(true);
  });

  it("leaves the citation legend entry out when there are no citation edges", () => {
    const graph = buildLandscapeGraph(analysis({ ranked_results: [patent()] }));
    expect(graph.legend.some((e) => e.shape === "arrow")).toBe(false);
  });
});
