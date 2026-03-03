// =============================================================================
// UGC AI Demo - Utility Functions
// =============================================================================

import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with conflict resolution
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Generate a unique ID
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Format date for display
 */
export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

/**
 * Parse SSE stream
 */
export async function* parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<string> {
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        yield line.slice(6);
      }
    }
  }
}

/**
 * Build complete HTML document from site parts
 */
export function buildHtmlDocument(
  html: string,
  css: string,
  javascript?: string
): string {
  // Check if html is already a complete document
  const isCompleteDocument = html.trim().toLowerCase().startsWith('<!doctype') ||
                             html.trim().toLowerCase().startsWith('<html');

  if (isCompleteDocument) {
    // If it's a complete document, process it to inline CSS and JS
    let result = html;

    // Remove external stylesheet links and replace with inline styles
    result = result.replace(/<link[^>]*rel=["']stylesheet["'][^>]*href=["'][^"']*\.css["'][^>]*\/?>/gi, '');
    result = result.replace(/<link[^>]*href=["'][^"']*\.css["'][^>]*rel=["']stylesheet["'][^>]*\/?>/gi, '');

    // Remove external script tags
    result = result.replace(/<script[^>]*src=["'][^"']*\.js["'][^>]*><\/script>/gi, '');
    result = result.replace(/<script[^>]*src=["'][^"']*\.js["'][^>]*\/>/gi, '');

    // Remove existing inline styles to avoid duplication
    result = result.replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '');

    // Inject CSS - try multiple locations
    if (css && css.trim()) {
      const styleTag = `<style>${css}</style>`;
      if (result.includes('</head>')) {
        result = result.replace('</head>', `${styleTag}</head>`);
      } else if (result.toLowerCase().includes('<head>')) {
        result = result.replace(/<head>/i, `<head>${styleTag}`);
      } else if (result.toLowerCase().includes('<body')) {
        result = result.replace(/<body/i, `<head>${styleTag}</head><body`);
      } else if (result.toLowerCase().includes('<html>')) {
        result = result.replace(/<html>/i, `<html><head>${styleTag}</head>`);
      } else {
        // Prepend style tag if nothing else works
        result = `<style>${css}</style>${result}`;
      }
    }

    // Inject JavaScript before </body> if provided
    if (javascript && javascript.trim()) {
      const scriptTag = `<script>${javascript}</script>`;
      if (result.includes('</body>')) {
        result = result.replace('</body>', `${scriptTag}</body>`);
      } else if (result.includes('</html>')) {
        result = result.replace('</html>', `${scriptTag}</html>`);
      } else {
        result += `<script>${javascript}</script>`;
      }
    }

    return result;
  }

  // Otherwise, build a complete document
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>${css}</style>
</head>
<body>
${html}
${javascript ? `<script>${javascript}</script>` : ''}
</body>
</html>`;
}

/**
 * Extract element selector path
 */
export function getElementSelector(element: Element): string {
  const path: string[] = [];
  const elements: Element[] = [];

  // First, collect all elements in the path
  let node: Element | null = element;
  while (node !== null && node !== document.body) {
    elements.push(node);
    node = node.parentElement;
  }

  // Then, build selectors for each element
  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    const tagName = el.tagName.toLowerCase();
    let selector = tagName;

    if (el.id) {
      selector += `#${el.id}`;
      path.unshift(selector);
      break;
    }

    if (el.className && typeof el.className === 'string') {
      const classes = el.className.trim().split(/\s+/).slice(0, 2);
      if (classes.length > 0 && classes[0]) {
        selector += `.${classes.join('.')}`;
      }
    }

    const parent = elements[i + 1];
    if (parent) {
      const elTagName = el.tagName;
      const siblings = Array.from(parent.children).filter(
        (sibling) => sibling.tagName === elTagName
      );
      if (siblings.length > 1) {
        const index = siblings.indexOf(el) + 1;
        selector += `:nth-of-type(${index})`;
      }
    }

    path.unshift(selector);
  }

  return path.join(' > ');
}
