import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(__dirname, "globals.css"), "utf8");

// Lấy nội dung khối `selector { ... }` ở cấp ngoài cùng.
function block(selector: string): string {
  const start = css.indexOf(`\n${selector} {`);
  if (start === -1) return "";
  const open = css.indexOf("{", start);
  const close = css.indexOf("\n}", open);
  return css.slice(open + 1, close);
}

function vars(selector: string): Set<string> {
  return new Set(
    [...block(selector).matchAll(/(--[\w-]+)\s*:/g)].map((m) => m[1]),
  );
}

function value(selector: string, name: string): string | undefined {
  const m = block(selector).match(new RegExp(`${name}\s*:\s*([^;]+);`));
  return m?.[1].trim();
}

describe("globals.css", () => {
  it("Kẹo ngọt khai báo đủ mọi biến màu như giao diện Sáng", () => {
    const candy = vars(".candy");
    expect(candy.size).toBeGreaterThan(0);
    for (const name of vars(":root")) {
      expect(candy.has(name), `thiếu ${name}`).toBe(true);
    }
  });

  it("cả ba giao diện đều có màu Pass/Fail/Khác cho đồ thị", () => {
    for (const sel of [":root", ".dark", ".candy"]) {
      for (const n of ["--chart-pass", "--chart-fail", "--chart-other"]) {
        expect(vars(sel).has(n), `${sel} thiếu ${n}`).toBe(true);
      }
    }
  });

  it("Kẹo ngọt dùng đúng bảng màu đã chốt", () => {
    const expected: Record<string, string> = {
      "--background": "#FFF7FB",
      "--card": "#FFFFFF",
      "--foreground": "#3A2350",
      "--primary": "#8F3FE0",
      "--chart-1": "#C4A1FF",
      "--chart-2": "#FF9FCB",
      "--chart-3": "#8BE3C9",
      "--border": "#F3DDF0",
      "--sidebar": "#FBE9F7",
    };
    for (const [k, v] of Object.entries(expected)) {
      expect(value(".candy", k)).toBe(v);
    }
  });
});
