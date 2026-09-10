import * as THREE from "three";
import type { Point } from "./data";

/** Metre-scale relief for the street-facing walls of mapped ordinary buildings. */
export class FacadeRelief {
  private positions: number[] = [];
  private uvs: number[] = [];
  private indices: number[] = [];
  private box(
    x: number,
    y: number,
    z: number,
    w: number,
    h: number,
    depth: number,
    angle: number,
  ) {
    const co = Math.cos(angle),
      si = Math.sin(angle);
    const corners = [
      [-1, -1, -1],
      [1, -1, -1],
      [1, 1, -1],
      [-1, 1, -1],
      [-1, -1, 1],
      [1, -1, 1],
      [1, 1, 1],
      [-1, 1, 1],
    ];
    // Separate vertices at each face give crisp stone edges and simple metre UVs.
    for (const face of [
      [0, 3, 2, 1],
      [4, 5, 6, 7],
      [0, 1, 5, 4],
      [1, 2, 6, 5],
      [2, 3, 7, 6],
      [3, 0, 4, 7],
    ]) {
      const base = this.positions.length / 3;
      face.forEach((index, i) => {
        const a = corners[index],
          px = (a[0] * w) / 2,
          pz = (a[2] * depth) / 2;
        this.positions.push(
          x + px * co - pz * si,
          y + (a[1] * h) / 2,
          z + px * si + pz * co,
        );
        this.uvs.push(i === 1 || i === 2 ? w / 2 : 0, i > 1 ? h / 2 : 0);
      });
      this.indices.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
  }
  add(points: Point[], height: number, routes: Point[]) {
    if (height > 95 || height < 8) return;
    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i],
        b = points[i + 1],
        dx = b[0] - a[0],
        dz = b[1] - a[1],
        len = Math.hypot(dx, dz);
      if (len < 6 || len > 160) continue;
      const mx = (a[0] + b[0]) / 2,
        mz = (a[1] + b[1]) / 2;
      const near = routes.reduce(
        (best, p) =>
          Math.hypot(p[0] - mx, p[1] - mz) <
          Math.hypot(best[0] - mx, best[1] - mz)
            ? p
            : best,
        routes[0],
      );
      if (Math.hypot(near[0] - mx, near[1] - mz) > 75) continue;
      const angle = Math.atan2(dz, dx),
        nx = -dz / len,
        nz = dx / len;
      const side = (near[0] - mx) * nx + (near[1] - mz) * nz > 0 ? 1 : -1;
      const center = (
        u: number,
        y: number,
        width: number,
        h: number,
        depth: number,
        offset: number,
      ) =>
        this.box(
          a[0] + dx * u + nx * side * offset,
          y,
          a[1] + dz * u + nz * side * offset,
          width,
          h,
          depth,
          angle,
        );
      for (let y = 3.4; y < height - 0.4; y += 3.4)
        center(0.5, y, len, 0.13, 0.34, 0.11);
      center(0.5, 0.46, len, 0.78, 0.26, 0.1);
      center(0.5, height - 0.22, len + 0.25, 0.22, 0.5, 0.13);
      center(0.5, height + 0.12, len + 0.38, 0.2, 0.64, 0.17);
      const major = Math.abs(nx) > 0.7 ? 1 : 0;
      const from = a[major],
        to = b[major];
      if (Math.abs(to - from) < 1) continue;
      for (
        let value = Math.ceil(Math.min(from, to) / 3.4) * 3.4;
        value < Math.max(from, to);
        value += 3.4
      ) {
        const u = (value - from) / (to - from);
        if (u < 0.025 || u > 0.975) continue;
        center(u, height / 2, 0.17, height - 0.7, 0.26, 0.1);
      }
    }
  }
  mesh(material: THREE.Material) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(this.positions, 3),
    );
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(this.uvs, 2));
    geometry.setIndex(this.indices);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  }
}
