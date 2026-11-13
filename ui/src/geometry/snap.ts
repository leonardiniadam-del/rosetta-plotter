/** Snapping a dragged drawing to the paper: its edges, its margins and its center lines. */
import type { Box } from "./placement";

export interface SnapPaper {
  width: number;
  height: number;
  /** The margin guides, in mm; 0 for none. */
  margin: number;
}

/** How close, in screen pixels, an edge comes before it snaps. */
export const SNAP_PX = 8;

/** The nearest shift, within `tolerance`, that puts one of `edges` on one of `guides`; 0 if none is that close. */
function nearest(edges: number[], guides: number[], tolerance: number): number {
  let best = 0;
  let distance = tolerance;
  for (const edge of edges) {
    for (const guide of guides) {
      const off = Math.abs(guide - edge);
      if (off <= distance) {
        distance = off;
        best = guide - edge;
      }
    }
  }
  return best;
}

/**
 * A drag of (dx, dy) mm for a selection whose box started at `box`, adjusted so that an edge (or the
 * middle) of the box lands exactly on a paper edge, a margin guide or the paper's center line when it
 * comes within `tolerance` mm of one. Each axis snaps on its own. Box and paper are in paper mm.
 */
export function snapDrag(box: Box, dx: number, dy: number, paper: SnapPaper, tolerance: number): [number, number] {
  const guides = (size: number) => {
    const edges = [0, size];
    const margins = paper.margin > 0 && paper.margin * 2 < size ? [paper.margin, size - paper.margin] : [];
    return { edges: [...edges, ...margins], middle: [size / 2] };
  };
  const along = (start: number, length: number, size: number): number => {
    const g = guides(size);
    // Edges go to edges and margins; the middle goes to the center line. An edge wins a tie.
    const byEdge = nearest([start, start + length], g.edges, tolerance);
    if (byEdge !== 0 || [start, start + length].some((e) => g.edges.includes(e))) return byEdge;
    return nearest([start + length / 2], g.middle, tolerance);
  };
  return [dx + along(box.x + dx, box.width, paper.width), dy + along(box.y + dy, box.height, paper.height)];
}

export type PaperEdge = "left" | "right" | "top" | "bottom";

/** The move that puts the box flush against one paper edge (`inset` mm in from it). */
export function toEdge(box: Box, edge: PaperEdge, paper: SnapPaper, inset = 0): [number, number] {
  if (edge === "left") return [inset - box.x, 0];
  if (edge === "right") return [paper.width - inset - box.width - box.x, 0];
  if (edge === "top") return [0, inset - box.y];
  return [0, paper.height - inset - box.height - box.y];
}
