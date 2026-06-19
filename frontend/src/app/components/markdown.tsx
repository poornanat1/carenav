import React from 'react';

// Minimal dependency-free markdown renderer for the internal KB docs (SBC plans and
// coverage explainers). These docs use a small, known subset: ATX headings, blank-line
// separated paragraphs (with soft-wrapped lines), unordered/ordered lists, GFM tables,
// and inline bold/italic/code. Not a general markdown engine — just enough for the corpus.

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Split on **bold**, *italic*, and `code`, keeping delimiters.
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith('**')) {
      nodes.push(<strong key={`${keyPrefix}-b${i}`}>{tok.slice(2, -2)}</strong>);
    } else if (tok.startsWith('`')) {
      nodes.push(
        <code key={`${keyPrefix}-c${i}`} style={{ fontFamily: 'var(--font-mono)', fontSize: '0.92em', background: 'var(--cn-card)', padding: '1px 4px', borderRadius: 3 }}>
          {tok.slice(1, -1)}
        </code>,
      );
    } else {
      nodes.push(<em key={`${keyPrefix}-i${i}`}>{tok.slice(1, -1)}</em>);
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function splitRow(line: string): string[] {
  return line.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
}

export function renderMarkdown(body: string): React.ReactNode {
  const lines = body.replace(/\r\n/g, '\n').split('\n');
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (line.trim() === '') {
      i++;
      continue;
    }

    // Headings
    const h = /^(#{1,4})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1].length;
      const size = level === 1 ? 18 : level === 2 ? 15 : 13;
      blocks.push(
        <div key={key++} style={{ fontWeight: 600, fontSize: size, color: 'var(--cn-text)', margin: level === 1 ? '4px 0 10px' : '16px 0 6px' }}>
          {renderInline(h[2], `h${key}`)}
        </div>,
      );
      i++;
      continue;
    }

    // Tables: a header row followed by a |---|---| separator.
    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('-')) {
      const header = splitRow(line);
      i += 2;
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        rows.push(splitRow(lines[i]));
        i++;
      }
      blocks.push(
        <table key={key++} style={{ borderCollapse: 'collapse', width: '100%', margin: '8px 0', fontSize: 12 }}>
          <thead>
            <tr>{header.map((c, j) => (
              <th key={j} style={{ textAlign: 'left', borderBottom: '1px solid var(--cn-border)', padding: '4px 8px', color: 'var(--cn-muted)', fontWeight: 600 }}>{renderInline(c, `th${key}-${j}`)}</th>
            ))}</tr>
          </thead>
          <tbody>{rows.map((r, ri) => (
            <tr key={ri}>{r.map((c, ci) => (
              <td key={ci} style={{ borderBottom: '1px solid var(--cn-border-soft)', padding: '4px 8px' }}>{renderInline(c, `td${key}-${ri}-${ci}`)}</td>
            ))}</tr>
          ))}</tbody>
        </table>,
      );
      continue;
    }

    // Lists (unordered - / * , ordered 1.)
    const isUl = /^\s*[-*]\s+/.test(line);
    const isOl = /^\s*\d+\.\s+/.test(line);
    if (isUl || isOl) {
      const items: React.ReactNode[] = [];
      while (i < lines.length && (/^\s*[-*]\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]))) {
        const item = lines[i].replace(/^\s*([-*]|\d+\.)\s+/, '');
        items.push(<li key={items.length} style={{ marginBottom: 4 }}>{renderInline(item, `li${key}-${items.length}`)}</li>);
        i++;
      }
      blocks.push(
        isOl
          ? <ol key={key++} style={{ paddingLeft: 20, margin: '6px 0' }}>{items}</ol>
          : <ul key={key++} style={{ paddingLeft: 20, margin: '6px 0' }}>{items}</ul>,
      );
      continue;
    }

    // Paragraph: gather soft-wrapped lines until a blank line or a block starter.
    const para: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !/^#{1,4}\s/.test(lines[i]) &&
      !/^\s*[-*]\s+/.test(lines[i]) &&
      !/^\s*\d+\.\s+/.test(lines[i])
    ) {
      para.push(lines[i].trim());
      i++;
    }
    blocks.push(
      <p key={key++} style={{ margin: '0 0 10px' }}>{renderInline(para.join(' '), `p${key}`)}</p>,
    );
  }

  return <div>{blocks}</div>;
}
