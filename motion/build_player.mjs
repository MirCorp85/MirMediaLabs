// Builds dist/mir-motion-player.js (React + @remotion/player + all scenes) for the Motion Studio page,
// and dist/schema.json (scene catalog + inspector fields) for the Python API and the AI prop writer.
import {build} from 'esbuild';
import fs from 'node:fs';
await build({entryPoints: ['src/player.tsx'], bundle: true, minify: true, format: 'iife', target: 'es2020', outfile: 'dist/mir-motion-player.js', define: {'process.env.NODE_ENV': '"production"'}, jsx: 'automatic', logLevel: 'warning'});
await build({stdin: {contents: "import {schema} from './src/scenes'; import {TEXT_ANIMS, TRANSITIONS} from './src/lib'; module.exports = {scenes: schema(), textAnims: TEXT_ANIMS, transitions: TRANSITIONS};", resolveDir: '.', loader: 'ts'}, bundle: true, platform: 'node', format: 'cjs', outfile: 'dist/schema.cjs', jsx: 'automatic', logLevel: 'warning'});
const {createRequire} = await import('node:module');
const s = createRequire(import.meta.url)('./dist/schema.cjs');
fs.writeFileSync('dist/schema.json', JSON.stringify(s, null, 1));
console.log('built dist/mir-motion-player.js + dist/schema.json', Object.keys(s.scenes).length, 'scenes');
