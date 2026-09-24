/**
 * Copyright (c) 2026 HOOX · PYNE · hoox-sh
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

import { type ConceptDoc, loadConcepts, markdownLinkTargets, resolveBundleLink } from './lint';

export type Hit = {
  id: string;
  path: string;
  type: string;
  title: string;
  description: string;
  resource: string;
  score: number;
};

function field(fm: ConceptDoc['frontmatter'], key: string): string {
  const value = fm[key];
  return typeof value === 'string' ? value : '';
}

export function searchConcepts(concepts: ConceptDoc[], terms: string[]): Hit[] {
  const needles = terms.map((term) => term.toLowerCase()).filter(Boolean);
  const hits: Hit[] = [];
  for (const concept of concepts) {
    const title = field(concept.frontmatter, 'title') || concept.id;
    const description = field(concept.frontmatter, 'description');
    const resource = field(concept.frontmatter, 'resource');
    const tags = Array.isArray(concept.frontmatter.tags) ? concept.frontmatter.tags.join(' ') : '';
    const haystack = `${concept.id} ${title} ${description} ${resource} ${tags}`.toLowerCase();
    let score = 0;
    for (const needle of needles) {
      if (concept.id.toLowerCase() === needle || resource.toLowerCase() === needle) score += 8;
      else if (concept.id.toLowerCase().includes(needle) || resource.toLowerCase().includes(needle)) score += 4;
      else if (title.toLowerCase().includes(needle)) score += 3;
      else if (haystack.includes(needle)) score += 1;
      else score -= 2;
    }
    if (needles.length === 0 || score > 0) {
      hits.push({
        id: concept.id,
        path: concept.path,
        type: field(concept.frontmatter, 'type') || 'Concept',
        title,
        description,
        resource,
        score,
      });
    }
  }
  return hits.sort((a, b) => b.score - a.score || (a.id < b.id ? -1 : 1)).slice(0, 12);
}

export function formatHits(hits: Hit[]): string {
  if (hits.length === 0) return 'No matching concepts.';
  return hits
    .map((hit) => `${hit.id}\n  ${hit.type} — ${hit.description || hit.title}\n  resource: ${hit.resource || hit.path}`)
    .join('\n');
}

function conceptById(concepts: ConceptDoc[], idOrPath: string): ConceptDoc | undefined {
  const id = idOrPath.replace(/\.md$/, '').replace(/^\//, '');
  return concepts.find((concept) => concept.id === id || concept.path === idOrPath || field(concept.frontmatter, 'resource') === idOrPath);
}

export function renderContext(files: Map<string, string>, start: string, depth: number, maxChars: number): string {
  const concepts = loadConcepts(files);
  const names = new Set(files.keys());
  const root = conceptById(concepts, start) ?? searchConcepts(concepts, start.split(/[\s/]+/)).map((hit) => concepts.find((concept) => concept.id === hit.id))[0];
  if (!root) return `No concept for ${start}.`;
  const parts: string[] = [root.text.trim()];
  if (depth > 0) {
    const neighborIds: string[] = [];
    for (const target of markdownLinkTargets(root.body)) {
      const resolved = resolveBundleLink(root.path, target, names);
      if (!resolved || !names.has(resolved)) continue;
      const id = resolved.replace(/\.md$/, '');
      if (!neighborIds.includes(id)) neighborIds.push(id);
    }
    const blurbs: string[] = [];
    for (const id of neighborIds) {
      const neighbor = concepts.find((concept) => concept.id === id);
      if (!neighbor) continue;
      const title = field(neighbor.frontmatter, 'title') || id;
      const description = field(neighbor.frontmatter, 'description');
      blurbs.push(`* ${title} (\`/${neighbor.path}\`) — ${description}`);
    }
    if (blurbs.length > 0) {
      parts.push('', '# Linked concepts', '', ...blurbs);
    }
  }
  const text = parts.join('\n').trim();
  if (text.length <= maxChars) return `${text}\n`;
  return `${text.slice(0, maxChars).replace(/\s+\S*$/, '')}\n…\n`;
}

