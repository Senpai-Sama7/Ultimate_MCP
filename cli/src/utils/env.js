import path from 'node:path';

import fs from 'fs-extra';

export async function readProjectEnv(projectDir) {
  const envPath = path.join(projectDir, '.env');
  try {
    const contents = await fs.readFile(envPath, 'utf-8');
    const result = {};
    for (const line of contents.split(/\r?\n/)) {
      if (!line || line.trim().startsWith('#')) {
        continue;
      }
      const separatorIndex = line.indexOf('=');
      if (separatorIndex === -1) {
        continue;
      }
      const key = line.slice(0, separatorIndex).trim();
      if (key.length === 0) {
        continue;
      }
      let value = line.slice(separatorIndex + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith('\'') && value.endsWith('\''))
      ) {
        value = value.slice(1, -1);
      }
      result[key] = value;
    }
    return result;
  } catch (error) {
    if (error.code === 'ENOENT') {
      return {};
    }
    throw error;
  }
}
