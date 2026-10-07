import { describe, expect, it } from "vitest";
import { Client } from "./client";
import { FakeApi } from "./fake";

function setup() {
  const fake = new FakeApi();
  return { fake, client: new Client(fake) };
}

describe("FakeApi", () => {
  it("connects on a scan and needs Home before moving", async () => {
    const { client } = setup();
    expect((await client.call("plotter_scan")).machine.state).toBe("not_homed");
    await expect(client.call("plotter_jog", 10, 0)).rejects.toThrow("HOME label");
    await client.call("plotter_set_home");
    const moved = await client.call("plotter_jog", 10, 5);
    expect(moved.machine.position).toEqual([10, 5]);
    const far = (await client.call("plotter_goto", 5000, 5000)).machine.position ?? [0, 0];
    expect(far[0]).toBeCloseTo(863.108);
    expect(far[1]).toBeCloseTo(593.106);
  });

  it("reports a plotter whose model isn't known, and learns it", async () => {
    const { fake, client } = setup();
    fake.model = null;
    expect((await client.call("plotter_scan")).machine.state).toBe("needs_model");
    expect((await client.call("plotter_identify", 2, 1, "Lab")).machine.model_name).toBe("AxiDraw V3/A3 or SE/A3");
  });

  it("imports, places, lists and removes jobs", async () => {
    const { fake, client } = setup();
    const { job } = await client.call("job_import", "C:\\art\\site.svg", 0);
    expect(job).toMatchObject({ id: "job-1", name: "site", width_mm: 120, height_mm: 80 });
    const { piece } = await client.call("job_place", job.id, 6.35, 6.35);
    expect(piece.placement).toEqual({ x: 6.35, y: 6.35, scale: 1, scale_y: 1, rotation: 0 });
    expect((await client.call("job_colors")).colors.map((c) => c.name)).toEqual(["black", "red"]);
    expect((await client.call("job_remove", job.id)).removed_pieces).toEqual([piece.id]);
    expect(fake.called("job_remove")).toEqual([["job-1"]]);
    await expect(client.call("job_import", "C:\\art\\plan.afdesign", 0)).rejects.toThrow("In Affinity");
  });

  it("turns the paper and what's on it", async () => {
    const { client } = setup();
    const { job } = await client.call("job_import", "C:\\art\\site.svg", 0);
    await client.call("job_place", job.id, 10, 20);
    const reply = await client.call("paper_rotate");
    expect([reply.material.width, reply.material.height]).toEqual([215.9, 279.4]);
    expect(reply.paper.orientation).toBe("portrait");
    expect(reply.pieces[0].placement).toMatchObject({ x: 215.9 - 20 - 80, y: 10, rotation: 90 });
  });

  it("numbers only the visible pens", async () => {
    const { client } = setup();
    const { job } = await client.call("job_import", "C:\\art\\site.svg", 0);
    await client.call("job_place", job.id, 0, 0);
    await client.call("set_pen_visible", "#000000", false);
    const { colors } = await client.call("job_colors");
    expect(colors.map((c) => [c.layer, c.name, c.visible])).toEqual([
      [null, "black", false],
      [1, "red", true],
    ]);
  });
});
