import path from "node:path";
import { pathToFileURL } from "node:url";

const tempRoot = process.env.TEMP ?? process.env.TMP ?? ".";
const mermaidRoot = path.join(
  tempRoot,
  "mermaid-parse",
  "node_modules",
  "mermaid",
  "dist",
  "mermaid.esm.mjs",
);
const jsdomRoot = path.join(
  tempRoot,
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

mermaid.initialize({ startOnLoad: false });

const diagram = `%%{init: {"theme": "base", "themeVariables": {"background": "#181A1F", "primaryColor": "#242933", "primaryTextColor": "#F5F7FA", "primaryBorderColor": "#6BA7FF", "lineColor": "#AAB4C0", "textColor": "#F5F7FA", "edgeLabelBackground": "#181A1F"}}}%%
flowchart LR
  classDef entity fill:#1F2633,stroke:#6BA7FF,color:#F5F7FA,stroke-width:1.5px
  classDef supporting fill:#191F29,stroke:#AAB4C0,color:#F5F7FA,stroke-width:1.2px

  USER["USER<br/>────────<br/>PK user_id<br/>status"]:::entity
  ORDER["ORDER<br/>────────<br/>PK order_id<br/>FK user_id<br/>order_status"]:::entity

  USER -->|owns 1:N| ORDER`;

await mermaid.parse(diagram);
console.log("data relation parse ok");
