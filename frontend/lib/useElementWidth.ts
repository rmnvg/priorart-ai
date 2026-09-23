import { useEffect, useRef, useState } from "react";

/** Tracks an element's rendered width, so SVG charts can draw at true pixel
 * size (a scaled viewBox would stretch text and stroke widths). */
export function useElementWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return [ref, width] as const;
}
