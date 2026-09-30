// Browser-only: turns an uploaded photo (or the bundled sample SVG) into a
// small JPEG data URL for the sketch reader. Phone photos run to several
// megabytes; the vision model reads a 1280px image just as well, and the
// upload stays fast on a mobile connection.

const MAX_SIDE = 1280;
const JPEG_QUALITY = 0.85;

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("That file couldn't be opened as an image."));
    img.src = src;
  });
}

async function rasterize(src: string): Promise<string> {
  const img = await loadImage(src);
  const width = img.naturalWidth || img.width;
  const height = img.naturalHeight || img.height;
  if (!width || !height) throw new Error("That image has no size.");
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Your browser couldn't process the image.");
  // JPEG has no transparency: a transparent drawing would turn black.
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", JPEG_QUALITY);
}

export async function fileToSketchDataUrl(file: File): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    return await rasterize(url);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function urlToSketchDataUrl(url: string): Promise<string> {
  return rasterize(url);
}
