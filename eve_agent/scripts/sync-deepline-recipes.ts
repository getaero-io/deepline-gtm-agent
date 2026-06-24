import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const source = process.env.DEEPLINE_RECIPES_JSON_URL ?? process.env.DEEPLINE_RECIPES_JSON_PATH;
if (!source) {
  throw new Error(
    "Set DEEPLINE_RECIPES_JSON_URL or DEEPLINE_RECIPES_JSON_PATH to refresh the recipe snapshot.",
  );
}
const targetPath = resolve(process.cwd(), "agent/lib/deepline-recipes.ts");

const parsed = JSON.parse(await readSource(source)) as {
  skipSuffix?: unknown;
  recipes?: Array<{ id?: unknown; title?: unknown; promptTemplate?: unknown }>;
};

if (typeof parsed.skipSuffix !== "string" || !Array.isArray(parsed.recipes)) {
  throw new Error(`Invalid Deepline recipes file: ${source}`);
}

for (const recipe of parsed.recipes) {
  if (
    typeof recipe.id !== "string" ||
    typeof recipe.title !== "string" ||
    typeof recipe.promptTemplate !== "string"
  ) {
    throw new Error(`Invalid Deepline recipe entry in ${source}`);
  }
}

mkdirSync(dirname(targetPath), { recursive: true });
writeFileSync(
  targetPath,
  [
    "// AUTO-GENERATED FILE. DO NOT EDIT.",
    `// Source: ${source}`,
    `export default ${JSON.stringify(parsed, null, 2)} as const;`,
    "",
  ].join("\n"),
);
console.log(`Synced ${parsed.recipes.length} Deepline recipes from ${source}`);

async function readSource(value: string): Promise<string> {
  if (value.startsWith("http://") || value.startsWith("https://")) {
    const response = await fetch(value);
    if (!response.ok) {
      throw new Error(`Failed to fetch ${value}: HTTP ${response.status}`);
    }
    return await response.text();
  }
  return readFileSync(resolve(value), "utf8");
}
