import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const mermaidRoot = path.join(
  process.env.TEMP ?? process.env.TMP ?? ".",
  "mermaid-parse",
  "node_modules",
  "mermaid",
  "dist",
  "mermaid.esm.mjs",
);
const jsdomRoot = path.join(
  process.env.TEMP ?? process.env.TMP ?? ".",
  "mermaid-parse",
  "node_modules",
  "jsdom",
  "lib",
  "api.js",
);

const { JSDOM } = await import(pathToFileURL(jsdomRoot).href);
const { window } = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = window;
globalThis.document = window.document;
Object.defineProperty(globalThis, "navigator", {
  value: window.navigator,
  configurable: true,
});

const { default: mermaid } = await import(pathToFileURL(mermaidRoot).href);
const markdown = await fs.readFile(
  "dev-pipeline/tasks/diagram-er-dark-colors/diagram.md",
  "utf8",
);
const blocks = [...markdown.matchAll(/```mermaid\n([\s\S]*?)```/g)].map(
  (match) => match[1].trim(),
);

if (blocks.length !== 4) {
  throw new Error(`expected 4 mermaid blocks, got ${blocks.length}`);
}

mermaid.initialize({
  startOnLoad: false,
});

for (const [index, block] of blocks.entries()) {
  await mermaid.parse(block);
  console.log(`diagram block ${index + 1} parse ok`);
}
