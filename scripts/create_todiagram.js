#!/usr/bin/env node
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');

const repoRoot = path.resolve(__dirname, '..');
const userMcp = path.join(process.env.HOME || '', '.config', 'Code', 'User', 'mcp.json');

async function readApiKey() {
  if (process.env.TODIAGRAM_API_KEY) return process.env.TODIAGRAM_API_KEY;
  try {
    const raw = await fsp.readFile(userMcp, 'utf8');
    const conf = JSON.parse(raw);
    const key = conf && conf.servers && conf.servers['todiagram-mcp'] && conf.servers['todiagram-mcp'].env && conf.servers['todiagram-mcp'].env.TODIAGRAM_API_KEY;
    if (key) return key;
  } catch (e) {
    // ignore
  }
  throw new Error('TODIAGRAM_API_KEY not found in env or VS Code MCP config. Set env var or add it to your mcp.json.');
}

async function listTopDirs(dir) {
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  return entries.filter(e => e.isDirectory()).map(e => e.name).filter(n => !['node_modules', '.git', 'dist', 'dist-electron'].includes(n));
}

async function main() {
  const apiKey = await readApiKey();
  const top = await listTopDirs(repoRoot);

  const nodes = [{ id: 'project', nodes: top.map(n => ({ id: n })) }];
  const edges = top.map(n => ({ from: 'project', to: n }));

  const content = { nodes, edges };

  const body = {
    name: 'Context Translator - Architecture',
    format: 'custom',
    content: JSON.stringify(content),
    private: true,
  };

  const fetch = require('node-fetch');
  const res = await fetch('https://todiagram.com/api/document', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: apiKey,
    },
    body: JSON.stringify(body),
  });

  const doc = await res.json();
  if (!res.ok) {
    throw new Error('ToDiagram API error: ' + (doc && doc.message ? doc.message : res.status));
  }

  const url = 'https://todiagram.com/editor?doc=' + doc.id;
  const outDir = path.join(repoRoot, 'diagrams');
  await fsp.mkdir(outDir, { recursive: true });
  const outFile = path.join(outDir, 'architecture.md');
  const md = '# Architecture diagram\n\nCreated: ' + new Date().toISOString() + '\n\nOpen in ToDiagram: ' + url + '\n';
  await fsp.writeFile(outFile, md, 'utf8');
  console.log('Diagram created:', url);
  console.log('Wrote', outFile);
}

main().catch(err => {
  console.error(err && err.message ? err.message : err);
  process.exit(1);
});
