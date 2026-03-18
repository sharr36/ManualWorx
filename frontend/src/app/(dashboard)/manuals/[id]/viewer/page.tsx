"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import {
  ChevronRight,
  Eye,
  EyeOff,
  Loader2,
  Maximize2,
  Minimize2,
  Minus,
  MousePointer,
  Move,
  Plus,
  RotateCcw,
  Search,
  ZapOff,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api-client";
import type {
  DiagramAnnotation,
  DiagramComponent,
  DiagramPageItem,
  OperatingState,
} from "@/types";

const HYDRAULIC_COLORS: Record<string, string> = {
  pressure: "#E53E3E",
  return: "#3182CE",
  pilot: "#ECC94B",
  drain: "#38A169",
  charge: "#ED8936",
  inactive: "#A0AEC0",
  electrical_signal: "#805AD5",
};

const ELECTRICAL_COLORS: Record<string, string> = {
  power_positive: "#E53E3E",
  ground_negative: "#1A202C",
  signal_data: "#3182CE",
  switched_power: "#ECC94B",
  can_bus: "#38A169",
  sensor_signal: "#ED8936",
  inactive: "#A0AEC0",
};

const COMPONENT_TYPE_ICONS: Record<string, string> = {
  valve: "V", pump: "P", motor: "M", cylinder: "C", filter: "F",
  accumulator: "A", gauge: "G", switch: "S", relay: "R", solenoid: "Sol",
  sensor: "Sn", connector: "X", fuse: "Fu", resistor: "Rs", battery: "B",
  alternator: "Alt", starter: "St", light: "L", other: "?",
};

const classificationLabels: Record<string, string> = {
  hydraulic_schematic: "Hydraulic",
  electrical_diagram: "Electrical",
  wiring_harness: "Wiring",
  diagnostic_flowchart: "Flowchart",
};

const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

type ViewerMode = "select" | "pan";

export default function ManualViewerPage() {
  const params = useParams();
  const manualId = params.id as string;

  const [diagramPages, setDiagramPages] = useState<DiagramPageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPage, setSelectedPage] = useState<DiagramPageItem | null>(null);
  const [annotation, setAnnotation] = useState<DiagramAnnotation | null>(null);
  const [annotating, setAnnotating] = useState(false);
  const [annotationError, setAnnotationError] = useState<string | null>(null);
  const [selectedComponent, setSelectedComponent] = useState<DiagramComponent | null>(null);
  const [selectedState, setSelectedState] = useState<OperatingState | null>(null);
  const [mode, setMode] = useState<ViewerMode>("select");
  const [zoom, setZoom] = useState(100);
  const [searchTerm, setSearchTerm] = useState("");
  const [activeLayer, setActiveLayer] = useState("");
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [showOverlay, setShowOverlay] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [typeFilter, setTypeFilter] = useState("");
  const [spaceHeld, setSpaceHeld] = useState(false);
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const canvasRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Load diagram pages for this manual
  useEffect(() => {
    api
      .get<DiagramPageItem[]>(`/api/viewer/diagrams?manual_id=${manualId}`)
      .then(setDiagramPages)
      .catch(() => setDiagramPages([]))
      .finally(() => setLoading(false));
  }, [manualId]);

  const loadAnnotation = useCallback(async (page: DiagramPageItem) => {
    setSelectedComponent(null);
    setSelectedState(null);
    setAnnotation(null);
    setAnnotationError(null);
    if (page.annotated) {
      try {
        const ann = await api.get<DiagramAnnotation>(`/api/viewer/annotations/${page.page_id}`);
        setAnnotation(ann);
      } catch { /* not annotated */ }
    }
  }, []);

  const fitToWidth = useCallback(() => {
    if (canvasRef.current && imgRef.current) {
      const containerW = canvasRef.current.clientWidth;
      const fitZoom = Math.min((containerW / imgRef.current.naturalWidth) * 100, 100);
      setZoom(Math.round(fitZoom));
      setPan({ x: 0, y: 0 });
    }
  }, []);

  const handleSelectPage = useCallback((page: DiagramPageItem) => {
    setSelectedPage(page);
    setZoom(100);
    setPan({ x: 0, y: 0 });
    loadAnnotation(page);
  }, [loadAnnotation]);

  const handleAnnotate = async (force = false) => {
    if (!selectedPage) return;
    setAnnotation(null);
    setAnnotating(true);
    setAnnotationError(null);
    try {
      const result = await api.post<DiagramAnnotation>("/api/viewer/annotate", {
        page_id: selectedPage.page_id,
        ...(force ? { force: true } : {}),
      }, { timeout: 180_000, retries: 0 });
      setAnnotation(result);
      setDiagramPages((prev) =>
        prev.map((p) =>
          p.page_id === selectedPage.page_id
            ? { ...p, annotated: true, component_count: result.component_count }
            : p
        )
      );
    } catch (e) {
      setAnnotationError(e instanceof Error ? e.message : "Annotation failed");
    } finally {
      setAnnotating(false);
    }
  };

  const centerOnComponent = useCallback((comp: DiagramComponent) => {
    if (!canvasRef.current || !imgRef.current) return;
    const container = canvasRef.current;
    const img = imgRef.current;
    const scale = zoom / 100;
    const cx = (comp.bbox_pct[0] + comp.bbox_pct[2] / 2) / 100 * img.naturalWidth * scale;
    const cy = (comp.bbox_pct[1] + comp.bbox_pct[3] / 2) / 100 * img.naturalHeight * scale;
    setPan({ x: container.clientWidth / 2 - cx, y: container.clientHeight / 2 - cy });
  }, [zoom]);

  const canPan = mode === "pan" || spaceHeld;

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 1 || canPan) {
      e.preventDefault();
      setIsPanning(true);
      panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
    }
  };
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;
    setPan({
      x: panStart.current.panX + (e.clientX - panStart.current.x),
      y: panStart.current.panY + (e.clientY - panStart.current.y),
    });
  };
  const handleMouseUp = () => setIsPanning(false);

  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const container = canvasRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const delta = e.deltaY > 0 ? -10 : 10;
    const newZoom = Math.max(10, Math.min(500, zoom + delta));
    const scaleFactor = newZoom / zoom;
    setPan({ x: mouseX - (mouseX - pan.x) * scaleFactor, y: mouseY - (mouseY - pan.y) * scaleFactor });
    setZoom(newZoom);
  }, [zoom, pan]);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    c.addEventListener("wheel", handleWheel, { passive: false });
    return () => c.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      switch (e.key) {
        case "Escape": setSelectedComponent(null); setSelectedState(null); break;
        case "+": case "=": e.preventDefault(); setZoom((z) => Math.min(500, z + 25)); break;
        case "-": e.preventDefault(); setZoom((z) => Math.max(10, z - 25)); break;
        case "0": e.preventDefault(); fitToWidth(); break;
        case "f": case "F": e.preventDefault(); toggleFullscreen(); break;
        case "o": case "O": e.preventDefault(); setShowOverlay((v) => !v); break;
        case " ": e.preventDefault(); setSpaceHeld(true); break;
      }
    };
    const up = (e: KeyboardEvent) => { if (e.key === " ") { setSpaceHeld(false); setIsPanning(false); } };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => { window.removeEventListener("keydown", down); window.removeEventListener("keyup", up); };
  }, [fitToWidth]);

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (document.fullscreenElement) { document.exitFullscreen(); setIsFullscreen(false); }
    else { containerRef.current.requestFullscreen(); setIsFullscreen(true); }
  };

  useEffect(() => {
    const h = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", h);
    return () => document.removeEventListener("fullscreenchange", h);
  }, []);

  const getLineColor = (lineType: string) => {
    const elec = annotation?.diagram_type === "electrical" || annotation?.diagram_type === "wiring";
    return (elec ? ELECTRICAL_COLORS : HYDRAULIC_COLORS)[lineType] || "#A0AEC0";
  };

  const filteredComponents = annotation?.annotation_data?.components?.filter(
    (c) =>
      (!searchTerm || c.name.toLowerCase().includes(searchTerm.toLowerCase()) || c.designator.toLowerCase().includes(searchTerm.toLowerCase())) &&
      (!typeFilter || c.type === typeFilter)
  );
  const visibleConnections = annotation?.annotation_data?.connections?.filter(
    (c) => !activeLayer || c.line_type === activeLayer
  );
  const activeComponentIds = new Set(selectedState?.active_components || []);
  const componentTypes = annotation
    ? [...new Set(annotation.annotation_data.components.map((c) => c.type))].sort()
    : [];

  const isElectrical = annotation?.diagram_type === "electrical" || annotation?.diagram_type === "wiring";
  const layerOptions = isElectrical
    ? [{ value: "", label: "All Layers" }, { value: "power_positive", label: "Power (+)" }, { value: "ground_negative", label: "Ground (-)" }, { value: "signal_data", label: "Signal" }, { value: "can_bus", label: "CAN Bus" }]
    : [{ value: "", label: "All Layers" }, { value: "pressure", label: "Pressure" }, { value: "return", label: "Return" }, { value: "pilot", label: "Pilot" }, { value: "drain", label: "Drain" }];

  const cursorStyle = isPanning ? "grabbing" : canPan ? "grab" : mode === "select" ? "crosshair" : "default";

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (diagramPages.length === 0) {
    return (
      <div className="py-12 text-center">
        <Eye className="mx-auto h-10 w-10 text-muted-foreground/50" />
        <p className="mt-3 text-sm text-muted-foreground">
          No diagram pages found in this manual. Pages classified as schematics, diagrams, or wiring will appear here.
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`space-y-2 ${isFullscreen ? "bg-white p-2" : ""}`}>
      {/* Toolbar */}
      <div className="flex items-center gap-2 rounded-lg border bg-white p-2 flex-wrap">
        <div className="flex items-center gap-1 border-r pr-2">
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => setZoom((z) => Math.max(10, z - 25))} title="Zoom out (-)">
            <Minus className="h-3.5 w-3.5" />
          </Button>
          <button className="w-12 text-center text-xs font-medium tabular-nums hover:bg-slate-100 rounded px-1 py-0.5" onClick={fitToWidth} title="Fit to width (0)">
            {zoom}%
          </button>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => setZoom((z) => Math.min(500, z + 25))} title="Zoom in (+)">
            <Plus className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => { setZoom(100); setPan({ x: 0, y: 0 }); }} title="Reset view">
            <RotateCcw className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="flex rounded-md border">
          <Button variant={mode === "select" ? "default" : "ghost"} size="sm" className="h-7 px-2" onClick={() => setMode("select")} title="Select (hold Space to pan)">
            <MousePointer className="h-3.5 w-3.5" />
          </Button>
          <Button variant={mode === "pan" ? "default" : "ghost"} size="sm" className="h-7 px-2" onClick={() => setMode("pan")} title="Pan">
            <Move className="h-3.5 w-3.5" />
          </Button>
        </div>
        <Button variant={showOverlay ? "default" : "outline"} size="sm" className="h-7 px-2" onClick={() => setShowOverlay((v) => !v)} title={`${showOverlay ? "Hide" : "Show"} annotations (O)`} disabled={!annotation}>
          {showOverlay ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
        </Button>
        <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={toggleFullscreen} title="Fullscreen (F)">
          {isFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
        </Button>
        <div className="h-5 w-px bg-border" />
        <select className="rounded-md border px-2 py-1 text-xs h-7" value={activeLayer} onChange={(e) => setActiveLayer(e.target.value)} disabled={!annotation}>
          {layerOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select className="rounded-md border px-2 py-1 text-xs h-7" value={selectedState?.id || ""} onChange={(e) => setSelectedState(annotation?.operating_states?.find((s) => s.id === e.target.value) || null)} disabled={!annotation?.operating_states?.length}>
          <option value="">All states</option>
          {annotation?.operating_states?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        {componentTypes.length > 0 && (
          <select className="rounded-md border px-2 py-1 text-xs h-7" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">All types</option>
            {componentTypes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        <div className="flex-1" />
        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground" />
          <input placeholder="Find component..." className="rounded-md border py-1 pl-7 pr-2 text-xs h-7" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} disabled={!annotation} />
        </div>
        <div className="hidden lg:flex items-center gap-1 text-[10px] text-muted-foreground border-l pl-2">
          <kbd className="rounded border bg-slate-50 px-1">Scroll</kbd><span>zoom</span>
          <kbd className="rounded border bg-slate-50 px-1 ml-1">Space</kbd><span>pan</span>
          <kbd className="rounded border bg-slate-50 px-1 ml-1">Esc</kbd><span>deselect</span>
        </div>
      </div>

      <div className="flex gap-3">
        {/* Diagram sidebar */}
        <div className="w-48 shrink-0 space-y-1.5 overflow-y-auto" style={{ maxHeight: isFullscreen ? "calc(100vh - 80px)" : "calc(100vh - 280px)" }}>
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Diagrams</h3>
          {diagramPages.map((page) => (
            <button
              key={page.page_id}
              className={`w-full rounded-lg border p-2 text-left text-xs transition-colors ${
                selectedPage?.page_id === page.page_id ? "border-emerald-500 bg-emerald-50" : "hover:bg-slate-50"
              }`}
              onClick={() => handleSelectPage(page)}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium truncate">p.{page.page_number + 1}</span>
                <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
              </div>
              <div className="mt-1 flex items-center gap-1">
                <Badge variant="outline" className="text-[10px]">
                  {classificationLabels[page.classification] || page.classification}
                </Badge>
                {page.annotated && <Badge className="bg-emerald-100 text-emerald-800 text-[10px]">AI</Badge>}
              </div>
            </button>
          ))}
        </div>

        {/* Canvas */}
        <div className="flex-1">
          {!selectedPage ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <Eye className="h-10 w-10 mb-3 opacity-50" />
              <p className="text-sm">Select a diagram from the sidebar</p>
            </div>
          ) : (
            <div
              ref={canvasRef}
              className="relative overflow-hidden rounded-lg border bg-slate-50"
              style={{ height: isFullscreen ? "calc(100vh - 80px)" : "calc(100vh - 280px)", cursor: cursorStyle }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
              onContextMenu={(e) => e.preventDefault()}
            >
              <div className="absolute" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom / 100})`, transformOrigin: "top left" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  ref={imgRef}
                  src={`${apiBase}/api/manuals/${selectedPage.manual_id}/pages/${selectedPage.page_number}/image`}
                  alt={`Page ${selectedPage.page_number + 1}`}
                  className="max-w-none"
                  draggable={false}
                  onLoad={() => fitToWidth()}
                />

                {annotation && showOverlay && (
                  <svg className="absolute inset-0" style={{ width: "100%", height: "100%", pointerEvents: "none" }} viewBox="0 0 100 100" preserveAspectRatio="none">
                    {visibleConnections?.map((conn, i) => {
                      const from = annotation.annotation_data.components.find((c) => c.id === conn.from_id);
                      const to = annotation.annotation_data.components.find((c) => c.id === conn.to_id);
                      if (!from || !to) return null;
                      const isSelConn = selectedComponent && (conn.from_id === selectedComponent.id || conn.to_id === selectedComponent.id);
                      const isActive = !selectedState || (activeComponentIds.has(conn.from_id) && activeComponentIds.has(conn.to_id));
                      const wp = conn.waypoints;
                      let d: string;
                      if (wp && wp.length >= 2) { d = `M ${wp[0][0]} ${wp[0][1]}`; for (let w = 1; w < wp.length; w++) d += ` L ${wp[w][0]} ${wp[w][1]}`; }
                      else { const fx = from.bbox_pct[0]+from.bbox_pct[2]/2, fy = from.bbox_pct[1]+from.bbox_pct[3]/2, tx = to.bbox_pct[0]+to.bbox_pct[2]/2, ty = to.bbox_pct[1]+to.bbox_pct[3]/2; d = `M ${fx} ${fy} L ${tx} ${ty}`; }
                      const color = getLineColor(conn.line_type);
                      const dashed = ["pilot","signal_data","can_bus"].includes(conn.line_type);
                      return (
                        <g key={`c-${i}`}>
                          <path d={d} stroke={color} strokeWidth={isSelConn ? 0.4 : 0.2} opacity={isSelConn ? 0.9 : isActive ? 0.35 : 0.1} fill="none" strokeDasharray={dashed ? "0.5 0.3" : undefined} strokeLinecap="round" strokeLinejoin="round" />
                          {isSelConn && conn.label && wp && wp.length >= 2 && (
                            <text x={wp[Math.floor(wp.length/2)][0]} y={wp[Math.floor(wp.length/2)][1]-0.4} textAnchor="middle" fontSize={0.6} fill={color} fontWeight="bold" fontFamily="system-ui" style={{ pointerEvents: "none" }}>{conn.label}</text>
                          )}
                        </g>
                      );
                    })}
                    {filteredComponents?.map((comp) => {
                      const isActive = !selectedState || activeComponentIds.has(comp.id);
                      const isSel = selectedComponent?.id === comp.id;
                      const isConn = selectedComponent && annotation.annotation_data.connections.some((c) => (c.from_id === selectedComponent.id && c.to_id === comp.id) || (c.to_id === selectedComponent.id && c.from_id === comp.id));
                      const isHl = searchTerm && (comp.name.toLowerCase().includes(searchTerm.toLowerCase()) || comp.designator.toLowerCase().includes(searchTerm.toLowerCase()));
                      let sc = "rgba(99,102,241,0.3)", fc = "rgba(99,102,241,0.04)", sw = 0.12, lb = "#475569";
                      if (isSel) { sc="#10B981"; fc="rgba(16,185,129,0.15)"; sw=0.3; lb="#10B981"; }
                      else if (isConn) { sc="#6366F1"; fc="rgba(99,102,241,0.12)"; sw=0.25; lb="#6366F1"; }
                      else if (isHl) { sc="#F59E0B"; fc="rgba(245,158,11,0.15)"; sw=0.25; lb="#F59E0B"; }
                      const lt = comp.designator, lw = Math.max(lt.length*0.45+0.5,1.8), lh = 1.0;
                      const lx = comp.bbox_pct[0]+comp.bbox_pct[2]/2, ly = comp.bbox_pct[1]-0.6;
                      return (
                        <g key={comp.id} style={{ pointerEvents: "all", cursor: "pointer" }} opacity={isActive ? 1 : 0.25} onClick={() => { if (mode === "select" || !canPan) setSelectedComponent(comp); }}>
                          <rect x={comp.bbox_pct[0]} y={comp.bbox_pct[1]} width={comp.bbox_pct[2]} height={comp.bbox_pct[3]} fill={fc} stroke={sc} strokeWidth={sw} rx={0.2} />
                          <rect x={lx-lw/2} y={ly-lh/2} width={lw} height={lh} rx={0.2} fill={lb} opacity={0.85} />
                          <text x={lx} y={ly+0.25} textAnchor="middle" fontSize={0.65} fill="white" fontWeight="bold" fontFamily="system-ui" style={{ pointerEvents: "none" }}>{lt}</text>
                        </g>
                      );
                    })}
                  </svg>
                )}
              </div>

              {!annotation && !annotating && !annotationError && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/5">
                  <Button onClick={() => handleAnnotate()} size="lg"><Zap className="mr-2 h-4 w-4" />Annotate with AI</Button>
                </div>
              )}
              {annotation && !annotating && (
                <div className="absolute top-3 right-3"><Button onClick={() => handleAnnotate(true)} size="sm" variant="outline" className="bg-white/90 shadow-sm text-xs"><RotateCcw className="mr-1.5 h-3 w-3" />Re-annotate</Button></div>
              )}
              {annotating && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/10">
                  <div className="flex items-center gap-3 rounded-lg bg-white px-6 py-4 shadow-lg"><Loader2 className="h-5 w-5 animate-spin" /><span className="text-sm font-medium">Analyzing diagram with AI...</span></div>
                </div>
              )}
              {annotationError && !annotating && !annotation && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/5">
                  <div className="flex flex-col items-center gap-3 rounded-lg bg-white px-6 py-4 shadow-lg max-w-sm">
                    <ZapOff className="h-5 w-5 text-red-500" />
                    <p className="text-sm text-red-600 text-center">{annotationError}</p>
                    <Button onClick={() => handleAnnotate(true)} size="sm" variant="outline">Retry</Button>
                  </div>
                </div>
              )}

              {selectedState && (
                <div className="absolute bottom-3 left-3 right-3 rounded-lg border bg-white/95 p-3 shadow-sm">
                  <div className="flex items-center gap-2"><Zap className="h-4 w-4 text-amber-500" /><span className="text-sm font-semibold">{selectedState.name}</span></div>
                  <p className="mt-1 text-xs text-muted-foreground">{selectedState.description}</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Side panel */}
        <div className="hidden w-60 shrink-0 space-y-3 xl:block overflow-y-auto" style={{ maxHeight: isFullscreen ? "calc(100vh - 80px)" : "calc(100vh - 280px)" }}>
          <Card>
            <CardContent className="p-3">
              <h3 className="mb-2 text-sm font-semibold">Component Info</h3>
              {selectedComponent ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-7 w-7 items-center justify-center rounded bg-slate-100 text-xs font-bold">{COMPONENT_TYPE_ICONS[selectedComponent.type] || "?"}</div>
                    <div>
                      <p className="text-xs font-medium">{selectedComponent.designator}</p>
                      <p className="text-[10px] text-muted-foreground">{selectedComponent.name}</p>
                    </div>
                  </div>
                  <Badge variant="secondary" className="capitalize text-[10px]">{selectedComponent.type}</Badge>
                  {Object.keys(selectedComponent.specs || {}).length > 0 && (
                    <div className="space-y-0.5">
                      {Object.entries(selectedComponent.specs).map(([k, v]) => (
                        <div key={k} className="flex justify-between text-[10px]"><span className="text-muted-foreground">{k}</span><span className="font-medium">{v}</span></div>
                      ))}
                    </div>
                  )}
                  {annotation && (
                    <div className="space-y-0.5 pt-1 border-t">
                      <p className="text-[10px] font-medium text-muted-foreground">Connections</p>
                      {annotation.annotation_data.connections
                        .filter((c) => c.from_id === selectedComponent.id || c.to_id === selectedComponent.id)
                        .map((conn, i) => {
                          const oid = conn.from_id === selectedComponent.id ? conn.to_id : conn.from_id;
                          const other = annotation.annotation_data.components.find((c) => c.id === oid);
                          return (
                            <div key={i} className="flex items-center gap-1 text-[10px]">
                              <div className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: getLineColor(conn.line_type) }} />
                              <span className="text-muted-foreground">{conn.line_type}</span>
                              {conn.label && <span className="text-muted-foreground font-mono text-[9px]">({conn.label})</span>}
                              <span>→</span>
                              <button className="font-medium text-emerald-600 hover:underline truncate" onClick={() => { if (other) { setSelectedComponent(other); centerOnComponent(other); } }}>{other?.designator || oid}</button>
                            </div>
                          );
                        })}
                    </div>
                  )}
                  <Button variant="outline" size="sm" className="w-full text-[10px] h-6" onClick={() => centerOnComponent(selectedComponent)}>Center on component</Button>
                </div>
              ) : (
                <p className="text-[10px] text-muted-foreground">Click a component on the diagram.</p>
              )}
            </CardContent>
          </Card>

          {annotation && (
            <Card>
              <CardContent className="p-3">
                <h3 className="mb-1 text-xs font-semibold">Summary</h3>
                <div className="space-y-0.5 text-[10px]">
                  <div className="flex justify-between"><span className="text-muted-foreground">Type</span><span className="capitalize">{annotation.diagram_type}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Components</span><span>{annotation.component_count}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Connections</span><span>{annotation.connection_count}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">States</span><span>{annotation.operating_states?.length || 0}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Confidence</span><span>{Math.round(annotation.confidence_overall * 100)}%</span></div>
                </div>
              </CardContent>
            </Card>
          )}

          {annotation && (
            <Card>
              <CardContent className="p-3">
                <h3 className="mb-1 text-xs font-semibold">Components ({filteredComponents?.length || 0})</h3>
                <div className="space-y-0.5 overflow-y-auto" style={{ maxHeight: "200px" }}>
                  {(filteredComponents || []).map((comp) => (
                    <button key={comp.id} className={`w-full rounded px-1.5 py-0.5 text-left text-[10px] flex items-center gap-1 ${selectedComponent?.id === comp.id ? "bg-emerald-50 text-emerald-800" : "hover:bg-slate-50"}`} onClick={() => { setSelectedComponent(comp); centerOnComponent(comp); }}>
                      <span className="shrink-0 w-4 h-4 flex items-center justify-center rounded bg-slate-100 text-[8px] font-bold">{COMPONENT_TYPE_ICONS[comp.type] || "?"}</span>
                      <span className="font-medium">{comp.designator}</span>
                      <span className="text-muted-foreground truncate">{comp.name}</span>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
