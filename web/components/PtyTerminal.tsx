"use client";

/**
 * PtyTerminal.tsx — xterm.js terminal connected to the PTY WebSocket server.
 *
 * Pure byte relay: browser keystrokes → PTY stdin, PTY stdout → browser.
 * All readline, history, slash commands, markdown rendering are handled by
 * the Python `kq` process — nothing is reimplemented here.
 *
 * WebSocket path: /pty-ws (same host+port as the page — no extra port needed).
 * Requires the custom Next.js server:  npm run dev:pty
 */

import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

// Dev: set NEXT_PUBLIC_PTY_PORT=3001 (separate pty-server.mjs port).
// Production: leave unset → connect to /pty-ws on the same origin (server.mjs).
const PTY_PORT = process.env.NEXT_PUBLIC_PTY_PORT ?? "";

function ptyWsUrl(cols: number, rows: number): string {
  const qs = `?cols=${cols}&rows=${rows}`;
  if (typeof window === "undefined") {
    return PTY_PORT
      ? `ws://localhost:${PTY_PORT}${qs}`
      : `ws://localhost:3000/pty-ws${qs}`;
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  if (PTY_PORT) {
    return `${proto}//${window.location.hostname}:${PTY_PORT}${qs}`;
  }
  return `${proto}//${window.location.host}/pty-ws${qs}`;
}

export interface PtyTerminalHandle {
  downloadBuffer(): void;
}

const PtyTerminal = forwardRef<PtyTerminalHandle>((_, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<import("@xterm/xterm").Terminal | null>(null);

  useImperativeHandle(ref, () => ({
    downloadBuffer() {
      const term = termRef.current;
      if (!term) return;

      const buf = term.buffer.active;
      const lines: string[] = [];
      for (let i = 0; i < buf.length; i++) {
        const line = buf.getLine(i);
        lines.push(line ? line.translateToString(true) : "");
      }

      // Trim leading/trailing blank lines
      let start = 0;
      while (start < lines.length && lines[start].trim() === "") start++;
      let end = lines.length - 1;
      while (end > start && lines[end].trim() === "") end--;
      const body = lines.slice(start, end + 1).join("\n");

      const ts = new Date().toISOString();
      const md = `# kube-q Session\n\n*Downloaded: ${ts}*\n\n\`\`\`\n${body}\n\`\`\`\n`;

      const blob = new Blob([md], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `kube-q-${ts.replace(/[:.]/g, "-")}.md`;
      a.click();
      URL.revokeObjectURL(url);
    },
  }));

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    let destroyed = false;
    let ws: WebSocket | null = null;

    async function init() {
      const { Terminal } = await import("@xterm/xterm");
      const { FitAddon } = await import("@xterm/addon-fit");
      if (destroyed) return;

      const term = new Terminal({
        cursorBlink:  true,
        cursorStyle:  "block",
        theme: {
          background:          "#0d0d0d",
          foreground:          "#d4d4d4",
          cursor:              "#d4d4d4",
          selectionBackground: "#ffffff33",
        },
        fontFamily:   "var(--font-geist-mono), 'Cascadia Code', 'Fira Code', monospace",
        fontSize:     13,
        lineHeight:   1.4,
        scrollback:   10_000,
        allowProposedApi: true,
      });

      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(el);
      fit.fit();
      requestAnimationFrame(() => { if (!destroyed) fit.fit(); });

      termRef.current = term;

      const ro = new ResizeObserver(() => {
        fit.fit();
        if (ws?.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
        }
      });
      ro.observe(el);

      // Show connecting status
      term.write("\x1b[2mConnecting to kq…\x1b[0m");

      // Connect WebSocket — same host/port as Next.js, path /pty-ws
      const wsUrl = ptyWsUrl(term.cols, term.rows);
      ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";

      ws.onopen = () => {
        if (destroyed) return;
        term.write("\r\x1b[K"); // clear "Connecting…" line
      };

      ws.onmessage = ({ data }) => {
        if (destroyed) return;
        if (data instanceof ArrayBuffer) {
          term.write(new Uint8Array(data));
        } else {
          term.write(data as string);
        }
      };

      ws.onerror = () => {
        if (destroyed) return;
        term.write("\r\x1b[K"); // clear "Connecting…"
        term.write(`\r\n\x1b[31m✗  Could not connect to PTY server.\x1b[0m\r\n`);
        term.write("\x1b[2m  Start it in a second terminal:\x1b[0m\r\n\r\n");
        term.write("\x1b[33m    npm run dev:pty\x1b[0m\r\n");
      };

      ws.onclose = ({ code, reason }) => {
        if (destroyed) return;
        const msg = reason || String(code);
        term.write(`\r\n\x1b[2m[session ended: ${msg}]\x1b[0m\r\n`);
      };

      // Raw keystrokes → PTY
      term.onData(data => {
        if (ws?.readyState === WebSocket.OPEN) ws.send(data);
      });

      return { term, ro };
    }

    let cleanup: { term: import("@xterm/xterm").Terminal; ro: ResizeObserver } | undefined;

    init()
      .then(r => { cleanup = r; })
      .catch(err => {
        // xterm failed to load — show plain-text error in the container
        console.error("[PtyTerminal] init failed:", err);
        el.innerHTML =
          `<pre style="color:#f88;padding:16px;font-family:monospace">` +
          `✗  Terminal failed to initialise:\n${err}\n\n` +
          `Check the browser console for details.</pre>`;
      });

    return () => {
      destroyed = true;
      ws?.close();
      termRef.current?.dispose();
      termRef.current = null;
      if (cleanup) cleanup.ro.disconnect();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="w-full h-full bg-[#0d0d0d]"
      style={{ padding: "4px" }}
    />
  );
});

PtyTerminal.displayName = "PtyTerminal";

export default PtyTerminal;
