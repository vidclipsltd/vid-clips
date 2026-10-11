const fs = require("node:fs/promises");
const path = require("node:path");
const sharp = require("sharp");
const pngToIco = require("png-to-ico");

async function main() {
  const root = path.resolve(__dirname, "..");
  const svgPath = path.join(root, "assets", "vidclips.svg");
  const iconPath = path.join(root, "assets", "vidclips.ico");
  const svg = await fs.readFile(svgPath);
  const pngs = await Promise.all([16, 24, 32, 48, 64, 128, 256].map((size) =>
    sharp(svg).resize(size, size).png().toBuffer()
  ));
  await fs.mkdir(path.dirname(iconPath), { recursive: true });
  await fs.writeFile(iconPath, await pngToIco(pngs));
  console.log("Generated VidClips Windows icon:", iconPath);
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
