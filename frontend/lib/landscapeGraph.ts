import type { AnalysisResult, RankedResult } from "@/types/analysis";

// Categorical palette: first 3 slots of the validated default 8-hue order
// (blue/orange/aqua). This graph is a bubble/scatter form where any two nodes
// can end up adjacent after the force simulation, so it falls under the
// "all-pairs" CVD rule, which only the first 3 slots of this palette clear in
// both light and dark mode — see the dataviz skill's color-formula.md. Past
// 3 distinct CPC clusters, everything else folds into a neutral "Other"
// bucket rather than adding a 4th/5th hue.
export const CLUSTER_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"] as const;
export const OTHER_CLUSTER_COLOR = "#c3c2b7"; // muted/baseline gray, not a categorical slot
export const IDEA_NODE_COLOR = "#0b0b0b"; // primary ink — the idea is UI chrome, not a data series

export interface GraphNode {
  id: string;
  label: string;
  isIdea: boolean;
  sourceType?: RankedResult["source_type"];
  cluster: string | null; // null = idea node or "Other" bucket
  clusterColor: string;
  relevanceScore?: number;
  verdict?: string | null;
  link?: string;
  val: number; // node size driver for react-force-graph
}

export interface GraphLink {
  source: string;
  target: string;
  distance: number;
  strength: number;
}

export interface LandscapeGraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  legend: { label: string; color: string }[];
}

const IDEA_NODE_ID = "__idea__";

function cpcCluster(cpc: string | null | undefined): string | null {
  if (!cpc) return null;
  const match = cpc.match(/^[A-Z]\d{2}[A-Z]/);
  return match ? match[0] : cpc.split("/")[0];
}

export function buildLandscapeGraph(result: AnalysisResult): LandscapeGraphData {
  const verdictByResultId = new Map(
    result.candidate_assessments.map((a) => [a.result_id, a.verdict])
  );

  // Pick the top 3 most frequent CPC clusters among the ranked results as the
  // colored buckets; everything else (rarer CPCs, and results with no CPC at
  // all — scholar/product entries) folds into "Other".
  const clusterCounts = new Map<string, number>();
  for (const r of result.ranked_results) {
    const cluster = cpcCluster(r.cpc_code);
    if (cluster) clusterCounts.set(cluster, (clusterCounts.get(cluster) ?? 0) + 1);
  }
  const topClusters = [...clusterCounts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, CLUSTER_COLORS.length)
    .map(([cluster]) => cluster);
  const clusterColorMap = new Map(topClusters.map((c, i) => [c, CLUSTER_COLORS[i]]));

  const nodes: GraphNode[] = [
    {
      id: IDEA_NODE_ID,
      label: result.idea_text.length > 80 ? result.idea_text.slice(0, 80) + "..." : result.idea_text,
      isIdea: true,
      cluster: null,
      clusterColor: IDEA_NODE_COLOR,
      val: 22,
    },
  ];

  for (const r of result.ranked_results) {
    const rawCluster = cpcCluster(r.cpc_code);
    const isKnownCluster = rawCluster !== null && clusterColorMap.has(rawCluster);
    nodes.push({
      id: r.id,
      label: r.title,
      isIdea: false,
      sourceType: r.source_type,
      cluster: isKnownCluster ? rawCluster : null,
      clusterColor: isKnownCluster ? clusterColorMap.get(rawCluster!)! : OTHER_CLUSTER_COLOR,
      relevanceScore: r.relevance_score,
      verdict: verdictByResultId.get(r.id) ?? null,
      link: r.link,
      val: 6 + r.relevance_score * 10,
    });
  }

  const links: GraphLink[] = result.ranked_results.map((r) => ({
    source: IDEA_NODE_ID,
    target: r.id,
    // Closer relevance -> shorter target distance -> settles nearer the idea node.
    distance: 60 + (1 - r.relevance_score) * 260,
    strength: 0.6,
  }));

  // Weak same-cluster links nudge same-color nodes together spatially,
  // reinforcing the color grouping without overpowering the idea-distance layout.
  for (const cluster of topClusters) {
    const members = result.ranked_results.filter((r) => cpcCluster(r.cpc_code) === cluster);
    for (let i = 1; i < members.length; i++) {
      links.push({
        source: members[0].id,
        target: members[i].id,
        distance: 50,
        strength: 0.15,
      });
    }
  }

  const legend = [
    { label: "Your idea", color: IDEA_NODE_COLOR },
    ...topClusters.map((cluster, i) => ({ label: cluster, color: CLUSTER_COLORS[i] })),
    { label: "Other / unclassified", color: OTHER_CLUSTER_COLOR },
  ];

  return { nodes, links, legend };
}
