"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, X, FileText } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api-client";
import type { Manual } from "@/types";

const MAX_FILE_SIZE_MB = 100;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

const STAGE_LABELS: Record<string, string> = {
  uploading: "Uploading file…",
  processing: "Starting processing…",
  downloading: "Preparing PDF…",
  ocr: "Extracting text…",
  chunking: "Chunking pages…",
  embedding: "Generating embeddings…",
  ready: "Complete!",
  failed: "Processing failed",
};

interface UploadDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (manual: Manual) => void;
}

export function UploadDialog({ open, onClose, onSuccess }: UploadDialogProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [manualType, setManualType] = useState("service");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState("uploading");
  const inputRef = useRef<HTMLInputElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const reset = useCallback(() => {
    setFile(null);
    setTitle("");
    setMake("");
    setModel("");
    setManualType("service");
    setError("");
    setUploading(false);
    setProgress(0);
    setStage("uploading");
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const handleClose = useCallback(() => {
    if (!uploading) {
      reset();
      onClose();
    }
  }, [uploading, reset, onClose]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === "application/pdf") {
      if (dropped.size > MAX_FILE_SIZE_BYTES) {
        setError(`File too large. Maximum size is ${MAX_FILE_SIZE_MB} MB`);
        return;
      }
      setFile(dropped);
      setError("");
      if (!title) setTitle(dropped.name.replace(/\.pdf$/i, ""));
    } else {
      setError("Only PDF files are accepted");
    }
  }, [title]);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      if (selected) {
        if (selected.size > MAX_FILE_SIZE_BYTES) {
          setError(`File too large. Maximum size is ${MAX_FILE_SIZE_MB} MB`);
          return;
        }
        setFile(selected);
        if (!title) setTitle(selected.name.replace(/\.pdf$/i, ""));
        setError("");
      }
    },
    [title]
  );

  const subscribeToProgress = useCallback(
    (manualId: string, onDone: () => void) => {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const es = new EventSource(
        `${apiBase}/api/manuals/${manualId}/progress`,
        { withCredentials: true }
      );
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const { stage: s, page, total } = data;

          setStage(s);

          if (s === "ocr" && total > 0) {
            // Upload = 0-50%, OCR = 50-85%
            setProgress(50 + Math.round((page / total) * 35));
          } else if (s === "chunking") {
            setProgress(85);
          } else if (s === "embedding") {
            setProgress(92);
          } else if (s === "ready") {
            setProgress(100);
            es.close();
            onDone();
          } else if (s === "failed") {
            es.close();
            setError("Processing failed — please try again");
            setUploading(false);
          }
        } catch {
          // skip malformed events
        }
      };

      es.onerror = () => {
        // SSE connection lost — don't block the user, just close
        es.close();
        onDone();
      };
    },
    []
  );

  const handleSubmit = useCallback(async () => {
    if (!file || !title.trim()) return;

    setUploading(true);
    setError("");
    setProgress(0);
    setStage("uploading");

    try {
      const result = await api.uploadFile<Manual>(
        "/api/manuals/upload",
        file,
        {
          title: title.trim(),
          make: make.trim() || "",
          model: model.trim() || "",
          manual_type: manualType,
        },
        (pct) => {
          // Upload transfer is 0-50% of the overall bar
          setProgress(Math.round(pct * 0.5));
        }
      );

      // Upload done — now track processing via SSE
      setProgress(50);
      setStage("processing");

      subscribeToProgress(result.id, () => {
        toast.success("Manual uploaded and processed");
        const manual = result;
        reset();
        onSuccess(manual);
      });
    } catch (err: any) {
      setError(err.detail || err.message || "Upload failed");
      setUploading(false);
      setProgress(0);
    }
  }, [file, title, make, model, manualType, reset, onSuccess, subscribeToProgress]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={handleClose}
      />
      <div className="relative z-10 w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Upload Manual</h2>
          <button onClick={handleClose} disabled={uploading}>
            <X className="h-5 w-5 text-slate-400 hover:text-slate-600" />
          </button>
        </div>

        <div className="mt-4 space-y-4">
          {/* File drop zone */}
          <div
            className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition ${
              dragOver
                ? "border-emerald-500 bg-emerald-50"
                : file
                  ? "border-emerald-500 bg-emerald-50/50"
                  : "border-slate-300 hover:border-slate-400"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={handleFileSelect}
            />
            {file ? (
              <div className="flex items-center gap-3">
                <FileText className="h-8 w-8 text-emerald-600" />
                <div>
                  <p className="font-medium">{file.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                </div>
              </div>
            ) : (
              <>
                <Upload className="mb-2 h-8 w-8 text-slate-400" />
                <p className="text-sm font-medium">
                  Drop a PDF here or click to browse
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Supports PDFs up to 5,000+ pages
                </p>
              </>
            )}
          </div>

          {/* Metadata fields */}
          <div className="space-y-3">
            <div>
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., CAT 320 Excavator Service Manual"
                disabled={uploading}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="make">Make</Label>
                <Input
                  id="make"
                  value={make}
                  onChange={(e) => setMake(e.target.value)}
                  placeholder="e.g., Caterpillar"
                  disabled={uploading}
                />
              </div>
              <div>
                <Label htmlFor="model">Model</Label>
                <Input
                  id="model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="e.g., 320 GC"
                  disabled={uploading}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="type">Manual Type</Label>
              <select
                id="type"
                value={manualType}
                onChange={(e) => setManualType(e.target.value)}
                disabled={uploading}
                className="mt-1 w-full rounded-md border bg-white px-3 py-2 text-sm"
              >
                <option value="service">Service Manual</option>
                <option value="operator">Operator Manual</option>
                <option value="parts">Parts Manual</option>
              </select>
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          {uploading && (
            <div className="space-y-1">
              <Progress value={progress} className="h-2" />
              <p className="text-center text-xs text-muted-foreground">
                {STAGE_LABELS[stage] || "Processing…"}
                {stage === "uploading" && progress > 0 && ` ${progress * 2}%`}
              </p>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={uploading}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!file || !title.trim() || uploading}
            >
              {uploading ? "Uploading..." : "Upload Manual"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
