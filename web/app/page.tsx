"use client";
import { useRef } from "react";
import PtyTerminal, { type PtyTerminalHandle } from "../components/PtyTerminal";

export default function Home() {
  const termRef = useRef<PtyTerminalHandle>(null);

  return (
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100vh" }}>
      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          padding: "4px 8px",
          background: "#0d0d0d",
          borderBottom: "1px solid #1e1e1e",
          flexShrink: 0,
        }}
      >
        {/* TODO Phase 2: replace buffer scrape with GET /conversations/{session_id}/export
            from the FastAPI backend (see kube_q/cli/repl.py _save_conversation) once the
            backend exposes a session ID to the frontend. */}
        <button
          onClick={() => termRef.current?.downloadBuffer()}
          style={{
            background: "transparent",
            border: "1px solid #00e676",
            color: "#00e676",
            fontFamily: "var(--font-geist-mono), 'Cascadia Code', 'Fira Code', monospace",
            fontSize: "12px",
            padding: "3px 10px",
            cursor: "pointer",
            borderRadius: "3px",
            letterSpacing: "0.03em",
          }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLButtonElement).style.background = "#00e67622";
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
          }}
        >
          ⬇ Download
        </button>
      </div>

      {/* Terminal — takes remaining height */}
      <div style={{ flex: 1, minHeight: 0, overflow: "hidden", position: "relative" }}>
        <PtyTerminal ref={termRef} />
      </div>
    </div>
  );
}
