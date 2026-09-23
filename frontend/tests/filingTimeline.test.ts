import { describe, expect, it } from "vitest";
import { filingsByYear } from "@/components/FilingTimeline";
import { patent } from "./fixtures";

describe("filingsByYear", () => {
  it("fills empty years with zero so the time axis stays honest", () => {
    const series = filingsByYear([
      patent({ id: "a", priority_date: "2010-05-01" }),
      patent({ id: "b", priority_date: "2013-01-01" }),
      patent({ id: "c", priority_date: "2013-09-09" }),
    ]);
    expect(series).toEqual([
      { year: 2010, count: 1 },
      { year: 2011, count: 0 },
      { year: 2012, count: 0 },
      { year: 2013, count: 2 },
    ]);
  });

  it("counts only dated patents", () => {
    expect(
      filingsByYear([
        patent({ priority_date: null }),
        patent({ source_type: "scholar", priority_date: "2010-01-01" }),
        patent({ priority_date: "garbage" }),
      ])
    ).toEqual([]);
  });
});
