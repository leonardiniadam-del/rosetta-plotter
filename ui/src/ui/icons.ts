/** Tabler Icons (MIT, outline), bundled into the app so nothing loads from the internet. */
import { unsafeHTML } from "lit/directives/unsafe-html.js";
import alert from "@tabler/icons/outline/alert-triangle.svg?raw";
import arrowDown from "@tabler/icons/outline/arrow-down.svg?raw";
import arrowLeft from "@tabler/icons/outline/arrow-left.svg?raw";
import arrowRight from "@tabler/icons/outline/arrow-right.svg?raw";
import arrowUp from "@tabler/icons/outline/arrow-up.svg?raw";
import center from "@tabler/icons/outline/focus-centered.svg?raw";
import check from "@tabler/icons/outline/check.svg?raw";
import chevronDown from "@tabler/icons/outline/chevron-down.svg?raw";
import crosshair from "@tabler/icons/outline/crosshair.svg?raw";
import duplicate from "@tabler/icons/outline/copy.svg?raw";
import eye from "@tabler/icons/outline/eye.svg?raw";
import eyeOff from "@tabler/icons/outline/eye-off.svg?raw";
import file from "@tabler/icons/outline/file.svg?raw";
import filePdf from "@tabler/icons/outline/file-type-pdf.svg?raw";
import fileVector from "@tabler/icons/outline/file-vector.svg?raw";
import hand from "@tabler/icons/outline/hand-stop.svg?raw";
import home from "@tabler/icons/outline/home.svg?raw";
import info from "@tabler/icons/outline/info-circle.svg?raw";
import returnHome from "@tabler/icons/outline/arrow-back-up.svg?raw";
import release from "@tabler/icons/outline/lock-open.svg?raw";
import link from "@tabler/icons/outline/link.svg?raw";
import mark from "@tabler/icons/outline/pencil.svg?raw";
import orient from "@tabler/icons/outline/axis-x.svg?raw";
import penDown from "@tabler/icons/outline/arrow-bar-to-down.svg?raw";
import penUp from "@tabler/icons/outline/arrow-bar-to-up.svg?raw";
import plug from "@tabler/icons/outline/plug-connected.svg?raw";
import plugOff from "@tabler/icons/outline/plug-connected-x.svg?raw";
import plus from "@tabler/icons/outline/plus.svg?raw";
import pause from "@tabler/icons/outline/player-pause.svg?raw";
import play from "@tabler/icons/outline/player-play.svg?raw";
import stop from "@tabler/icons/outline/player-stop.svg?raw";
import pointer from "@tabler/icons/outline/pointer.svg?raw";
import rotate from "@tabler/icons/outline/rotate-clockwise.svg?raw";
import rotatePaper from "@tabler/icons/outline/rotate-rectangle.svg?raw";
import route from "@tabler/icons/outline/route.svg?raw";
import settings from "@tabler/icons/outline/settings.svg?raw";
import trace from "@tabler/icons/outline/border-outer.svg?raw";
import trash from "@tabler/icons/outline/trash.svg?raw";
import unlink from "@tabler/icons/outline/unlink.svg?raw";
import x from "@tabler/icons/outline/x.svg?raw";
import zoom from "@tabler/icons/outline/zoom-in.svg?raw";

const ICONS = {
  alert, arrowDown, arrowLeft, arrowRight, arrowUp, center, check, chevronDown, crosshair, duplicate, eye, eyeOff,
  file, filePdf, fileVector, hand, home, info, link, mark, orient, pause, penDown, penUp, play, plug, plugOff, plus, pointer,
  release, returnHome, rotate, rotatePaper, route, settings, stop, trace, trash, unlink, x, zoom,
};

export type IconName = keyof typeof ICONS;
export const ICON_NAMES = Object.keys(ICONS) as IconName[];

export function iconSvg(name: IconName): string {
  return ICONS[name]
    .trim()
    .replace(/\s+class="[^"]*"/, "")
    .replace(/^<svg/, '<svg class="icon" aria-hidden="true" focusable="false"');
}

/** An icon for a Lit template. Decorative: the button around it carries the accessible name. */
export function icon(name: IconName) {
  return unsafeHTML(iconSvg(name));
}
