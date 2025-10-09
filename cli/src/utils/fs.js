import path from 'node:path';
import fs from 'fs-extra';

export async function ensureProjectDirectory(targetDir, { force = false } = {}) {
  const exists = await fs.pathExists(targetDir);
  if (exists) {
    const files = await fs.readdir(targetDir);
    const meaningfulFiles = files.filter((name) => name !== '.git' && name !== '.DS_Store');
    if (meaningfulFiles.length > 0 && !force) {
      throw new Error(`Directory ${targetDir} is not empty. Use --force to overwrite.`);
    }
  }

  await fs.ensureDir(targetDir);
}

export async function writeFile(targetDir, filename, contents, { mode } = {}) {
  const filePath = path.join(targetDir, filename);
  await fs.ensureDir(path.dirname(filePath));
  await fs.writeFile(filePath, contents, { mode });
}

export async function pathExists(targetDir, filename) {
  return fs.pathExists(path.join(targetDir, filename));
}
