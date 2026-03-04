"use client";

import { useState } from "react";
import { Check, Copy, FileDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { ConfidenceBar } from "@/components/ui/confidence-bar";
import { Button } from "@/components/ui/button";
import type { ConfidenceLevel } from "@/types";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  confidence?: number;
  confidenceLevel?: ConfidenceLevel;
  sources?: string[];
  latency_ms?: number;
  className?: string;
  onGenerateDoc?: (docType: string) => void;
}

function renderMarkdown(text: string) {
  if (!text) return null;

  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeLines: string[] = [];
  let codeKey = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block toggle
    if (line.startsWith("```")) {
      if (inCodeBlock) {
        elements.push(
          <pre
            key={`code-${codeKey++}`}
            className="my-2 overflow-x-auto rounded bg-slate-100 p-3 text-xs font-mono"
          >
            {codeLines.join("\n")}
          </pre>
        );
        codeLines = [];
        inCodeBlock = false;
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    // Headers
    if (line.startsWith("### ")) {
      elements.push(
        <h4 key={i} className="mt-3 mb-1 text-sm font-semibold">
          {formatInline(line.slice(4))}
        </h4>
      );
      continue;
    }
    if (line.startsWith("## ")) {
      elements.push(
        <h3 key={i} className="mt-3 mb-1 text-sm font-bold">
          {formatInline(line.slice(3))}
        </h3>
      );
      continue;
    }

    // Numbered list
    const numberedMatch = line.match(/^(\d+)\.\s+(.+)/);
    if (numberedMatch) {
      elements.push(
        <div key={i} className="flex gap-2 pl-1">
          <span className="shrink-0 text-muted-foreground">
            {numberedMatch[1]}.
          </span>
          <span>{formatInline(numberedMatch[2])}</span>
        </div>
      );
      continue;
    }

    // Bullet list
    if (line.startsWith("- ") || line.startsWith("* ")) {
      elements.push(
        <div key={i} className="flex gap-2 pl-1">
          <span className="shrink-0 text-muted-foreground">&bull;</span>
          <span>{formatInline(line.slice(2))}</span>
        </div>
      );
      continue;
    }

    // Warning line
    if (line.includes("\u26A0\uFE0F") || line.includes("WARNING") || line.includes("CAUTION")) {
      elements.push(
        <p key={i} className="rounded bg-amber-50 px-2 py-1 text-amber-800">
          {formatInline(line)}
        </p>
      );
      continue;
    }

    // Empty line = spacing
    if (line.trim() === "") {
      elements.push(<div key={i} className="h-2" />);
      continue;
    }

    // Regular paragraph
    elements.push(
      <p key={i}>{formatInline(line)}</p>
    );
  }

  return <>{elements}</>;
}

function formatInline(text: string): React.ReactNode {
  // Bold
  const parts: React.ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <strong key={match.index} className="font-semibold">
        {match[1]}
      </strong>
    );
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? <>{parts}</> : text;
}

const DOC_OPTIONS = [
  { value: "troubleshooting_guide", label: "Troubleshooting Guide" },
  { value: "service_procedure", label: "Service Procedure" },
  { value: "quick_reference", label: "Quick Reference" },
  { value: "parts_reference", label: "Parts Reference" },
];

export function ChatMessage({
  role,
  content,
  confidence,
  confidenceLevel,
  sources,
  latency_ms,
  className,
  onGenerateDoc,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [showDocMenu, setShowDocMenu] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (role === "user") {
    return (
      <div className={cn("flex justify-end", className)}>
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-slate-900 px-4 py-3 text-sm text-white">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex justify-start", className)}>
      <div className="max-w-[80%] space-y-3 rounded-2xl rounded-bl-md border bg-white px-4 py-3">
        <div className="text-sm text-slate-900">
          {renderMarkdown(content)}
        </div>

        {confidence !== undefined && (
          <ConfidenceBar
            score={confidence}
            level={confidenceLevel}
            sources={sources}
          />
        )}

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-xs"
            onClick={handleCopy}
          >
            {copied ? (
              <Check className="mr-1 h-3 w-3" />
            ) : (
              <Copy className="mr-1 h-3 w-3" />
            )}
            {copied ? "Copied" : "Copy"}
          </Button>
          {onGenerateDoc && (
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="text-xs"
                onClick={() => setShowDocMenu(!showDocMenu)}
              >
                <FileDown className="mr-1 h-3 w-3" />
                Generate Doc
              </Button>
              {showDocMenu && (
                <div className="absolute bottom-full left-0 z-10 mb-1 rounded-md border bg-white shadow-lg">
                  {DOC_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      className="block w-full whitespace-nowrap px-3 py-1.5 text-left text-xs hover:bg-slate-50"
                      onClick={() => {
                        onGenerateDoc(opt.value);
                        setShowDocMenu(false);
                      }}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {latency_ms !== undefined && (
            <span className="text-xs text-muted-foreground">
              {latency_ms < 1000
                ? `${latency_ms}ms`
                : `${(latency_ms / 1000).toFixed(1)}s`}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
