import * as path from 'path';
import { downloadAndUnzipVSCode, runTests } from '@vscode/test-electron';

async function main() {
  try {
    // The folder containing the Extension Manifest package.json
    const extensionPath = path.resolve(__dirname, '../../');

    // Download and unzip VS Code into a temp location
    const vscodeExecutablePath = await downloadAndUnzipVSCode();

    const extensionTestsPath = path.resolve(__dirname, './out/test/index.js');

    await runTests({
      vscodeExecutablePath,
      extensionTestsPath,
      // Launch with the extension development path set to this folder
      extensionDevelopmentPath: extensionPath,
      // Disable all other extensions for a clean test run
      launchArgs: ['--disable-extensions'],
    });
  } catch (err) {
    console.error('Failed to run tests', err);
    process.exit(1);
  }
}

void main();
