/**
 * The plate (spec §2.4): Rhino's Top view, with the grid and axes from Home, the reach, the paper, the
 * placed drawings, selection handles and the pen crosshair. No numbers or labels are drawn here.
 */
import { css, html, nothing, svg } from "lit";
import { repeat } from "lit/directives/repeat.js";
import type { ViewRequest } from "../app/app";
import type { PieceInfo, PlacementData } from "../bridge/contract";
import { angleAt, GRID, gridLines, handleAt, hitPiece, JOB_MIME, linesToPath, marqueeHits, rectFrom, snapAngle, type IdBox } from "../canvas/interaction";
import { cameraMatrix, fitCamera, panBy, toMachine, toScreen, zoomAt, type Camera, type Size } from "../geometry/camera";
import { neighbours, orientMatrix, type Corner, type OrientationCode } from "../geometry/orientation";
import { pointAt, routeOf, routePath, timeAtPendown } from "../geometry/route";
import { SNAP_PX, snapDrag } from "../geometry/snap";
import { pieceMatrix, rotateAboutCenter, scaleFromHandle, type Box, type Handle, type Point } from "../geometry/placement";
import { disabledReason } from "../state/reasons";
import { jobOf, pieceBoxOnPaper, plotRunning, reachOf, selectionBox } from "../state/selectors";
import { StoreController, type Tool } from "../state/store";
import { AppElement } from "./base";
import { controls } from "./styles";

const MIN_GRID_PX = 6;
const HANDLE_PX = 7;
const CROSS_PX = 9;
const WHEEL_ZOOM = 0.0015;
const MARQUEE_MIN_PX = 3;
const ONE_DRAWING = "Select one drawing to resize or turn it.";

type Drag =
  | { kind: "pan"; last: Point }
  | { kind: "move"; start: Point; originals: Map<string, PlacementData>; box: Box | null }
  | { kind: "scale"; id: string; handle: Handle; original: PlacementData; offset: Point }
  | { kind: "rotate"; id: string; center: Point; startAngle: number; original: PlacementData }
  | { kind: "marquee"; start: Point; end: Point; additive: boolean };

function samePlacement(a: PlacementData, b: PlacementData): boolean {
  return a.x === b.x && a.y === b.y && a.scale === b.scale && a.scale_y === b.scale_y && a.rotation === b.rotation;
}

function inkColor(color: string): string {
  return color === "#000000" ? "var(--ink-black)" : color;
}

/** Set plotter orientation's corner markers: their size, and how near a click must be. */
const PICK_PX = 12;
const PICK_RADIUS_PX = 12;

export class RpPlate extends AppElement {
  static styles = [
    controls,
    css`
      :host {
        display: block;
        position: relative;
        overflow: hidden;
        background: var(--canvas);
        outline: none;
      }
      :host(:focus-visible) {
        outline: 1px solid var(--accent);
        outline-offset: -1px;
      }
      :host([data-tool="hand"]) {
        cursor: grab;
      }
      :host([data-tool="zoom"]) {
        cursor: zoom-in;
      }
      :host([data-tool="pen"]),
      :host([data-tool="rotate"]) {
        cursor: crosshair;
      }
      svg {
        display: block;
        width: 100%;
        height: 100%;
      }
      line,
      rect,
      path {
        vector-effect: non-scaling-stroke;
      }
      .minor {
        stroke: var(--grid-minor);
        stroke-width: 1px;
      }
      .major {
        stroke: var(--grid-major);
        stroke-width: 1px;
      }
      .reach {
        fill: none;
        stroke: var(--text-faint);
        stroke-width: 1px;
        stroke-dasharray: 6 4;
      }
      .paper {
        fill: var(--paper);
      }
      .unreachable {
        fill: rgba(0, 0, 0, 0.35);
      }
      .margin {
        fill: none;
        stroke: #b9b6ad;
        stroke-width: 1px;
        stroke-dasharray: 3 3;
      }
      .axis-x {
        stroke: var(--axis-x);
        stroke-width: 1.5px;
      }
      .axis-y {
        stroke: var(--axis-y);
        stroke-width: 1.5px;
      }
      .off,
      .ink {
        fill: none;
        stroke-width: 1.5px;
        stroke-linejoin: round;
        stroke-linecap: round;
      }
      .off {
        stroke: var(--danger);
      }
      .ink.hidden {
        opacity: 0.2;
      }
      svg.previewing .ink {
        opacity: 0.25;
      }
      .route-down {
        fill: none;
        stroke-width: 1.5px;
        vector-effect: non-scaling-stroke;
      }
      .route-up {
        fill: none;
        stroke: var(--text-faint);
        stroke-width: 1px;
        stroke-dasharray: 3 3;
        vector-effect: non-scaling-stroke;
      }
      .route-dot {
        fill: var(--pen-cross);
        stroke: #fff;
        stroke-width: 1px;
      }
      .selection {
        fill: none;
        stroke: var(--accent);
        stroke-width: 1px;
      }
      .pick {
        fill: var(--accent);
        stroke: var(--panel);
        stroke-width: 1px;
      }
      .pick.chosen {
        fill: var(--panel);
        stroke: var(--accent);
        stroke-width: 2px;
      }
      .handle {
        fill: var(--panel);
        stroke: var(--accent);
        stroke-width: 1px;
      }
      .marquee {
        fill: rgba(59, 142, 234, 0.12);
        stroke: var(--accent);
        stroke-width: 1px;
        stroke-dasharray: 4 3;
      }
      .cross {
        stroke: var(--pen-cross);
        stroke-width: 2px;
      }
      .cross-box {
        fill: none;
        stroke: var(--pen-cross);
        stroke-width: 1px;
      }
      .drawn {
        fill: none;
        stroke-width: 2.5px;
        vector-effect: non-scaling-stroke;
        stroke-linecap: round;
        stroke-linejoin: round;
      }
    `,
  ];

  private camera: Camera = { scale: 1, x: 0, y: 0, orient: orientMatrix("nw-h") };
  /** The orientation the camera is turned for. */
  private turnedFor: OrientationCode = "nw-h";
  private size: Size = { width: 800, height: 600 };
  private drag: Drag | null = null;
  private spaceHeld = false;
  private fitted = false;
  private observer: ResizeObserver | null = null;
  private readonly paths = new Map<string, string>();

  constructor() {
    super();
    // The pen's live position arrives about 10 times a second, in its own store.
    new StoreController(this, this.app.progress);
    new StoreController(this, this.app.previewClock);
  }

  /** The current camera (for tests and the status bar's future use). */
  get view(): Camera {
    return this.camera;
  }

  connectedCallback(): void {
    super.connectedCallback();
    this.tabIndex = 0;
    this.app.viewRequests.addEventListener("view", this.onViewRequest);
    window.addEventListener("keydown", this.onSpace);
    window.addEventListener("keyup", this.onSpace);
    window.addEventListener("blur", this.releaseSpace);
    if (typeof ResizeObserver !== "undefined") {
      this.observer = new ResizeObserver(() => this.measure());
      this.observer.observe(this);
    }
  }

  disconnectedCallback(): void {
    this.app.viewRequests.removeEventListener("view", this.onViewRequest);
    window.removeEventListener("keydown", this.onSpace);
    window.removeEventListener("keyup", this.onSpace);
    window.removeEventListener("blur", this.releaseSpace);
    this.observer?.disconnect();
    this.observer = null;
    super.disconnectedCallback();
  }

  protected firstUpdated(): void {
    this.measure();
  }

  protected willUpdate(): void {
    // The plotter's orientation changed (picked, or a plotter with its own came along): turn the view and fit again.
    if (this.s.orientation !== this.turnedFor) {
      this.turnedFor = this.s.orientation;
      this.camera = { ...this.camera, orient: orientMatrix(this.turnedFor) };
      if (this.fitted) this.fit("paper");
    }
    // Drop the cached paths of drawings that are gone.
    const jobs = new Set(this.s.jobs.map((j) => j.id));
    for (const key of this.paths.keys()) if (!jobs.has(key.split("|")[0])) this.paths.delete(key);
  }

  protected updated(): void {
    this.dataset.tool = this.activeTool();
  }

  private measure(): void {
    const rect = this.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    this.size = { width: rect.width, height: rect.height };
    if (this.fitted) this.requestUpdate();
    else this.fit("paper");
  }

  private fit(what: "paper" | "reach"): void {
    const { material } = this.s;
    const reach = reachOf(this.s);
    const box: Box =
      what === "reach" && reach
        ? { x: 0, y: 0, width: reach[0], height: reach[1] }
        : { x: material.x, y: material.y, width: material.width, height: material.height };
    this.camera = fitCamera(box, this.size, undefined, orientMatrix(this.s.orientation));
    this.fitted = true;
    this.requestUpdate();
  }

  private onViewRequest = (event: Event): void => {
    const request = (event as CustomEvent<ViewRequest>).detail;
    if (request.kind === "zoom") {
      this.camera = zoomAt(this.camera, request.factor, [this.size.width / 2, this.size.height / 2]);
      this.requestUpdate();
    } else {
      this.fit(request.kind === "fit-reach" ? "reach" : "paper");
    }
  };

  private onSpace = (event: KeyboardEvent): void => {
    if (event.code !== "Space" && event.key !== " ") return;
    const held = event.type === "keydown";
    if (held) {
      // Space pans only from the plate or the bare page: a focused button, field or menu, or an open dialog, keeps its Space.
      const target = event.composedPath()[0];
      const onPlateOrPage = target === this || target === document.body || target === document.documentElement || target === window;
      if (!onPlateOrPage || this.s.dialog) return;
      event.preventDefault();
    } else if (!this.spaceHeld) {
      return;
    }
    if (held !== this.spaceHeld) {
      this.spaceHeld = held;
      this.requestUpdate();
    }
  };

  /** Alt-Tab while holding Space: the keyup goes to the other window, so let go of the Hand here. */
  private releaseSpace = (): void => {
    if (!this.spaceHeld) return;
    this.spaceHeld = false;
    this.requestUpdate();
  };

  private activeTool(): Tool {
    return this.spaceHeld ? "hand" : this.s.tool;
  }

  private screenPoint(event: MouseEvent): Point {
    const rect = this.getBoundingClientRect();
    return [event.clientX - rect.left, event.clientY - rect.top];
  }

  private paperPoint(screen: Point): Point {
    const [x, y] = toMachine(this.camera, screen);
    return [x - this.s.material.x, y - this.s.material.y];
  }

  private boxes(): IdBox[] {
    return this.s.pieces.map((piece) => ({ id: piece.id, box: pieceBoxOnPaper(this.s, piece) }));
  }

  private selectedOne(): PieceInfo | null {
    return this.s.selection.length === 1 ? (this.s.pieces.find((p) => p.id === this.s.selection[0]) ?? null) : null;
  }

  /** Screen positions of the one selected drawing's corner handles. */
  private handles(): Record<Handle, Point> | null {
    const piece = this.selectedOne();
    if (!piece) return null;
    const box = pieceBoxOnPaper(this.s, piece);
    const { x, y } = this.s.material;
    const corner = (cx: number, cy: number) => toScreen(this.camera, [x + cx, y + cy]);
    return {
      nw: corner(box.x, box.y),
      ne: corner(box.x + box.width, box.y),
      se: corner(box.x + box.width, box.y + box.height),
      sw: corner(box.x, box.y + box.height),
    };
  }

  private capture(event: PointerEvent): void {
    try {
      (event.currentTarget as Element | null)?.setPointerCapture?.(event.pointerId);
    } catch {
      // Not every pointer can be captured; dragging still works without it.
    }
  }

  private onDown = (event: PointerEvent): void => {
    const screen = this.screenPoint(event);
    const tool = this.activeTool();
    if (event.button === 1 || tool === "hand") {
      this.drag = { kind: "pan", last: screen };
      this.capture(event);
      return;
    }
    if (event.button !== 0) return;
    this.focus();
    const s = this.s;
    if (s.orienting) {
      // Picking the orientation: only the corner markers answer a click.
      const corner = this.pickAt(screen);
      if (corner) void this.app.pickCorner(corner);
      return;
    }
    if (tool === "zoom") {
      this.camera = zoomAt(this.camera, event.altKey ? 1 / 1.5 : 1.5, screen);
      this.requestUpdate();
      return;
    }
    if (tool === "pen") {
      void this.app.movePenTo(toMachine(this.camera, screen));
      return;
    }
    const paper = this.paperPoint(screen);
    const locked = plotRunning(s);
    if (tool === "rotate") {
      const piece = this.selectedOne();
      const reason = disabledReason("arrange", s) ?? (piece ? null : ONE_DRAWING);
      if (reason || !piece) {
        this.app.explain(reason ?? ONE_DRAWING);
        return;
      }
      const box = pieceBoxOnPaper(s, piece);
      const center: Point = [box.x + box.width / 2, box.y + box.height / 2];
      this.drag = { kind: "rotate", id: piece.id, center, startAngle: angleAt(center, paper), original: piece.placement };
      this.capture(event);
      return;
    }
    const handles = locked ? null : this.handles();
    const handle = handles ? handleAt(screen, handles) : null;
    const one = this.selectedOne();
    if (handle && one && handles) {
      const corner = this.paperPoint(handles[handle]);
      this.drag = { kind: "scale", id: one.id, handle, original: one.placement, offset: [corner[0] - paper[0], corner[1] - paper[1]] };
      this.capture(event);
      return;
    }
    const hit = hitPiece(this.boxes(), paper);
    if (hit) {
      if (event.shiftKey) {
        this.app.toggleSelect(hit);
        return;
      }
      if (!s.selection.includes(hit)) this.app.select([hit]);
      if (locked) return;
      const selected = this.s.pieces.filter((p) => this.s.selection.includes(p.id));
      this.drag = { kind: "move", start: paper, originals: new Map(selected.map((p) => [p.id, p.placement])), box: selectionBox(this.s) };
      this.capture(event);
      return;
    }
    if (!event.shiftKey) this.app.deselect();
    this.drag = { kind: "marquee", start: screen, end: screen, additive: event.shiftKey };
    this.capture(event);
  };

  private onMove = (event: PointerEvent): void => {
    const screen = this.screenPoint(event);
    this.app.cursor.update({ point: toMachine(this.camera, screen) });
    const drag = this.drag;
    if (!drag) return;
    if (drag.kind === "pan") {
      this.camera = panBy(this.camera, screen[0] - drag.last[0], screen[1] - drag.last[1]);
      drag.last = screen;
      this.requestUpdate();
      return;
    }
    if (drag.kind === "marquee") {
      drag.end = screen;
      this.requestUpdate();
      return;
    }
    const paper = this.paperPoint(screen);
    if (drag.kind === "move") {
      let dx = paper[0] - drag.start[0];
      let dy = paper[1] - drag.start[1];
      if (event.shiftKey) {
        if (Math.abs(dx) >= Math.abs(dy)) dy = 0;
        else dx = 0;
      }
      // Snap to the paper's edges, margins and center (Alt drags freely).
      if (drag.box && this.s.view.snap && !event.altKey) {
        const { width, height } = this.s.material;
        const paperGuides = { width, height, margin: this.s.view.margins ? this.s.margin : 0 };
        const [sx, sy] = snapDrag(drag.box, dx, dy, paperGuides, SNAP_PX / this.camera.scale);
        // Shift keeps the drag on one axis: the axis it holds still doesn't snap away.
        const holdX = event.shiftKey && dx === 0;
        const holdY = event.shiftKey && dy === 0;
        if (!holdX) dx = sx;
        if (!holdY) dy = sy;
      }
      for (const [id, original] of drag.originals) this.app.previewPlacement(id, { ...original, x: original.x + dx, y: original.y + dy });
      return;
    }
    const piece = this.s.pieces.find((p) => p.id === drag.id);
    const job = piece ? jobOf(this.s, piece) : undefined;
    if (!job) return;
    if (drag.kind === "scale") {
      const corner: Point = [paper[0] + drag.offset[0], paper[1] + drag.offset[1]];
      this.app.previewPlacement(drag.id, scaleFromHandle(job.width_mm, job.height_mm, drag.original, drag.handle, corner, event.shiftKey));
      return;
    }
    const turned = drag.original.rotation + angleAt(drag.center, paper) - drag.startAngle;
    const angle = event.shiftKey ? snapAngle(turned, 15) : turned;
    this.app.previewPlacement(drag.id, rotateAboutCenter(job.width_mm, job.height_mm, drag.original, angle));
  };

  private onUp = (): void => {
    const drag = this.drag;
    this.drag = null;
    if (!drag) return;
    if (drag.kind === "move") {
      for (const [id, original] of drag.originals) {
        const now = this.s.pieces.find((p) => p.id === id)?.placement;
        if (now && !samePlacement(now, original)) void this.app.commitPlacement(id);
      }
    } else if (drag.kind === "scale" || drag.kind === "rotate") {
      // A click on a handle, or with the Rotate tool, that changes nothing sends nothing.
      const now = this.s.pieces.find((p) => p.id === drag.id)?.placement;
      if (now && !samePlacement(now, drag.original)) void this.app.commitPlacement(drag.id);
    } else if (drag.kind === "marquee") {
      if (Math.hypot(drag.end[0] - drag.start[0], drag.end[1] - drag.start[1]) > MARQUEE_MIN_PX) {
        const hits = marqueeHits(this.boxes(), rectFrom(this.paperPoint(drag.start), this.paperPoint(drag.end)));
        this.app.select(drag.additive ? [...new Set([...this.s.selection, ...hits])] : hits);
      }
      this.requestUpdate();
    }
  };

  private onWheel = (event: WheelEvent): void => {
    event.preventDefault();
    this.camera = zoomAt(this.camera, Math.exp(-event.deltaY * WHEEL_ZOOM), this.screenPoint(event));
    this.requestUpdate();
  };

  private onDragOver = (event: DragEvent): void => {
    if (Array.from(event.dataTransfer?.types ?? []).includes(JOB_MIME)) {
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    }
  };

  private onDrop = (event: DragEvent): void => {
    const at = this.paperPoint(this.screenPoint(event));
    const jobId = event.dataTransfer?.getData(JOB_MIME);
    if (jobId) {
      event.preventDefault();
      void this.app.placeJob(jobId, at);
    } else if (Array.from(event.dataTransfer?.types ?? []).includes("Files")) {
      // pywebview hands Windows files to Python; its files_dropped event then places them here.
      this.app.lastFileDrop = { point: at, at: Date.now() };
    }
  };

  render() {
    const s = this.s;
    const cam = this.camera;
    const m = s.material;
    const reach = reachOf(s);
    const clipRight = reach ? Math.min(m.x + m.width, reach[0]) : m.x + m.width;
    const clipBottom = reach ? Math.min(m.y + m.height, reach[1]) : m.y + m.height;
    return html`<svg
      class=${s.preview ? "previewing" : ""}
      role="img"
      aria-label="The plotter's reach, the paper and the drawings on it"
      @pointerdown=${this.onDown}
      @pointermove=${this.onMove}
      @pointerup=${this.onUp}
      @pointercancel=${this.onUp}
      @pointerleave=${() => this.app.cursor.update({ point: null })}
      @wheel=${this.onWheel}
      @dragover=${this.onDragOver}
      @drop=${this.onDrop}
    >
      <defs>
        <clipPath id="printable" clipPathUnits="userSpaceOnUse">
          <rect x=${m.x} y=${m.y} width=${Math.max(0, clipRight - m.x)} height=${Math.max(0, clipBottom - m.y)} />
        </clipPath>
        <mask id="off-paper" maskUnits="userSpaceOnUse" x="-100000" y="-100000" width="200000" height="200000">
          <rect x="-100000" y="-100000" width="200000" height="200000" fill="white" />
          <rect x=${m.x} y=${m.y} width=${Math.max(0, clipRight - m.x)} height=${Math.max(0, clipBottom - m.y)} fill="black" />
        </mask>
      </defs>
      <g transform=${cameraMatrix(cam)}>
        ${s.view.grid ? this.grid() : nothing}
        ${reach ? svg`<rect class="reach" x="0" y="0" width=${reach[0]} height=${reach[1]} />` : nothing}
        <rect class="paper" x=${m.x} y=${m.y} width=${m.width} height=${m.height} />
        ${this.unreachable(reach)}
        ${s.view.margins
          ? svg`<rect class="margin" x=${m.x + s.margin} y=${m.y + s.margin} width=${Math.max(0, m.width - 2 * s.margin)} height=${Math.max(0, m.height - 2 * s.margin)} />`
          : nothing}
        ${this.axes(reach)}
        <g mask="url(#off-paper)">${repeat(s.pieces, (p) => p.id, (piece) => this.piece(piece, "off"))}</g>
        <g clip-path="url(#printable)">${repeat(s.pieces, (p) => p.id, (piece) => this.piece(piece, "ink"))}</g>
        ${this.drawnSoFar()} ${this.previewRoute()}
      </g>
      ${this.selection()} ${this.crosshair()} ${this.previewDot()} ${this.marquee()} ${this.picks()}
    </svg>`;
  }

  private grid() {
    const { minor, every } = GRID[this.s.units];
    // All four window corners: in a turned view the top-left corner isn't the smallest machine x and y.
    const { width, height } = this.size;
    const corners = ([[0, 0], [width, 0], [width, height], [0, height]] as Point[]).map((p) => toMachine(this.camera, p));
    const x0 = Math.min(...corners.map((c) => c[0]));
    const x1 = Math.max(...corners.map((c) => c[0]));
    const y0 = Math.min(...corners.map((c) => c[1]));
    const y1 = Math.max(...corners.map((c) => c[1]));
    const lines = (step: number, kind: string) => {
      if (step * this.camera.scale < MIN_GRID_PX) return nothing;
      return svg`${gridLines(x0, x1, step).map((x) => svg`<line class=${kind} x1=${x} y1=${y0} x2=${x} y2=${y1} />`)}${gridLines(y0, y1, step).map(
        (y) => svg`<line class=${kind} x1=${x0} y1=${y} x2=${x1} y2=${y} />`,
      )}`;
    };
    return svg`${lines(minor, "minor")}${lines(minor * every, "major")}`;
  }

  private unreachable(reach: [number, number] | null) {
    if (!reach) return nothing;
    const m = this.s.material;
    const right = m.x + m.width;
    const bottom = m.y + m.height;
    const parts: Box[] = [];
    if (right > reach[0]) parts.push({ x: Math.max(m.x, reach[0]), y: m.y, width: right - Math.max(m.x, reach[0]), height: m.height });
    if (bottom > reach[1]) {
      parts.push({ x: m.x, y: Math.max(m.y, reach[1]), width: Math.min(right, reach[0]) - m.x, height: bottom - Math.max(m.y, reach[1]) });
    }
    return parts
      .filter((b) => b.width > 0 && b.height > 0)
      .map((b) => svg`<rect class="unreachable" x=${b.x} y=${b.y} width=${b.width} height=${b.height} />`);
  }

  private axes(reach: [number, number] | null) {
    const m = this.s.material;
    const xEnd = Math.max(reach?.[0] ?? 0, m.x + m.width);
    const yEnd = Math.max(reach?.[1] ?? 0, m.y + m.height);
    return svg`<line class="axis-x" x1="0" y1="0" x2=${xEnd} y2="0" /><line class="axis-y" x1="0" y1="0" x2="0" y2=${yEnd} />`;
  }

  private path(jobId: string, color: string, lines: number[][]): string {
    const key = `${jobId}|${color}`;
    let d = this.paths.get(key);
    if (d === undefined) {
      d = linesToPath(lines);
      this.paths.set(key, d);
    }
    return d;
  }

  /** One drawing: "off" draws every line red; "ink" draws them again in pen colors, clipped to what can be drawn. */
  private piece(piece: PieceInfo, pass: "off" | "ink") {
    const s = this.s;
    const job = jobOf(s, piece);
    if (!job) return nothing;
    const matrix = pieceMatrix(job.width_mm, job.height_mm, piece.placement, [s.material.x, s.material.y]);
    const hidden = new Set(s.colors.filter((c) => !c.visible).map((c) => c.color));
    const groups = job.groups.filter((g) => !g.white && (pass === "ink" || !hidden.has(g.color)));
    return svg`<g transform=${`matrix(${matrix.join(" ")})`}>
      ${pass === "ink" && s.view.original && job.preview
        ? svg`<image href=${job.preview} x="0" y="0" width=${job.width_mm} height=${job.height_mm} opacity="0.3" preserveAspectRatio="none" />`
        : nothing}
      ${groups.map((group) => {
        const d = this.path(job.id, group.color, group.lines);
        return pass === "off"
          ? svg`<path class="off" d=${d} />`
          : svg`<path class=${hidden.has(group.color) ? "ink hidden" : "ink"} d=${d} style=${`stroke: ${inkColor(group.color)}`} />`;
      })}
    </g>`;
  }

  private selection() {
    const s = this.s;
    const { x, y } = s.material;
    const outlines = s.pieces
      .filter((p) => s.selection.includes(p.id))
      .map((piece) => {
        const box = pieceBoxOnPaper(s, piece);
        const on = rectFrom(toScreen(this.camera, [x + box.x, y + box.y]), toScreen(this.camera, [x + box.x + box.width, y + box.y + box.height]));
        return svg`<rect class="selection" x=${on.x} y=${on.y} width=${on.width} height=${on.height} />`;
      });
    const handles = plotRunning(s) || s.tool === "rotate" ? null : this.handles();
    return svg`${outlines}${handles
      ? Object.values(handles).map(([hx, hy]) => svg`<rect class="handle" x=${hx - HANDLE_PX / 2} y=${hy - HANDLE_PX / 2} width=${HANDLE_PX} height=${HANDLE_PX} />`)
      : nothing}`;
  }

  /** While plotting: the lines already drawn, darker (spec §4.4). */
  private drawnSoFar() {
    const s = this.s;
    const progress = this.app.progress.state.value;
    if (!s.summary || !progress || !plotRunning(s)) return nothing;
    const route = routeOf(s.summary);
    const current = s.summary.layers[progress.layer];
    if (!current) return nothing;
    // Python reports the pen-down distance in this pen, so the dark line stays with the crosshair through pen-up travel.
    const until = timeAtPendown(route, progress.layer, progress.pendown_mm);
    return s.summary.layers.slice(0, progress.layer + 1).map(
      (layer, index) =>
        svg`<path class="drawn" d=${routePath(route, index, true, index < progress.layer ? Infinity : until)} style=${`stroke: ${inkColor(layer.color)}`} />`,
    );
  }

  private readonly routePaths = new WeakMap<object, { up: string[]; down: string[] }>();

  /** Preview path: every pen's pen-down moves in its color and pen-up moves as faint dashes. */
  private previewRoute() {
    const s = this.s;
    if (!s.preview || !s.summary) return nothing;
    let paths = this.routePaths.get(s.summary);
    if (!paths) {
      // Cached per plan: the dot moves 30 times a second, the paths don't.
      const route = routeOf(s.summary);
      paths = {
        up: s.summary.layers.map((_, i) => routePath(route, i, false)),
        down: s.summary.layers.map((_, i) => routePath(route, i, true)),
      };
      this.routePaths.set(s.summary, paths);
    }
    const p = paths;
    return s.summary.layers.map(
      (layer, i) => svg`<path class="route-up" d=${p.up[i]} /><path class="route-down" d=${p.down[i]} style=${`stroke: ${inkColor(layer.color)}`} />`,
    );
  }

  private previewDot() {
    const s = this.s;
    if (!s.preview || !s.summary) return nothing;
    const at = pointAt(routeOf(s.summary), this.app.previewClock.state.t);
    if (!at) return nothing;
    const [cx, cy] = toScreen(this.camera, at);
    return svg`<circle class="route-dot" cx=${cx} cy=${cy} r="4" />`;
  }

  private crosshair() {
    const live = this.app.progress.state.value;
    const position = plotRunning(this.s) && live ? ([live.x, live.y] as Point) : this.s.machine.position;
    if (!position) return nothing;
    const [cx, cy] = toScreen(this.camera, position);
    const r = CROSS_PX + 6;
    return svg`<g>
      <line class="cross" x1=${cx - r} y1=${cy} x2=${cx - 3} y2=${cy} />
      <line class="cross" x1=${cx + 3} y1=${cy} x2=${cx + r} y2=${cy} />
      <line class="cross" x1=${cx} y1=${cy - r} x2=${cx} y2=${cy - 3} />
      <line class="cross" x1=${cx} y1=${cy + 3} x2=${cx} y2=${cy + r} />
      <rect class="cross-box" x=${cx - 3} y=${cy - 3} width="6" height="6" />
    </g>`;
  }

  /** The reach (or, with no model, the paper) as a box on screen, its corners named by where they are on screen. */
  private screenCorners(): Record<Corner, Point> {
    const reach = reachOf(this.s);
    const m = this.s.material;
    const [x0, y0, x1, y1] = reach ? [0, 0, reach[0], reach[1]] : [m.x, m.y, m.x + m.width, m.y + m.height];
    const box = rectFrom(toScreen(this.camera, [x0, y0]), toScreen(this.camera, [x1, y1]));
    const right = box.x + box.width;
    const bottom = box.y + box.height;
    return { nw: [box.x, box.y], ne: [right, box.y], se: [right, bottom], sw: [box.x, bottom] };
  }

  /** The corners a click can pick now: all four, then the two next to HOME's. */
  private pickable(): Corner[] {
    const home = this.s.orienting?.home;
    return home ? neighbours(home) : ["nw", "ne", "se", "sw"];
  }

  private pickAt(screen: Point): Corner | null {
    const corners = this.screenCorners();
    return this.pickable().find((c) => Math.hypot(screen[0] - corners[c][0], screen[1] - corners[c][1]) <= PICK_RADIUS_PX) ?? null;
  }

  private picks() {
    const picking = this.s.orienting;
    if (!picking) return nothing;
    const corners = this.screenCorners();
    const half = PICK_PX / 2;
    const marker = (corner: Corner, chosen: boolean) => {
      const [cx, cy] = corners[corner];
      return svg`<rect class=${chosen ? "pick chosen" : "pick"} data-corner=${corner} x=${cx - half} y=${cy - half} width=${PICK_PX} height=${PICK_PX} />`;
    };
    return svg`${picking.home ? marker(picking.home, true) : nothing}${this.pickable().map((c) => marker(c, false))}`;
  }

  private marquee() {
    const drag = this.drag;
    if (drag?.kind !== "marquee") return nothing;
    const box = rectFrom(drag.start, drag.end);
    return svg`<rect class="marquee" x=${box.x} y=${box.y} width=${box.width} height=${box.height} />`;
  }
}

customElements.define("rp-plate", RpPlate);
