"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ChevronRight,
  Image,
  Loader2,
  MousePointer,
  Move,
  Search,
  ZapOff,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
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
  valve: "V",
  pump: "P",
  motor: "M",
  cylinder: "C",
  filter: "F",
  accumulator: "A",
  gauge: "G",
  switch: "S",
  relay: "R",
  solenoid: "Sol",
  sensor: "Sn",
  connector: "X",
  fuse: "Fu",
  resistor: "Rs",
  other: "?",
};

const classificationLabels: Record<string, string> = {
  hydraulic_schematic: "Hydraulic",
  electrical_diagram: "Electrical",
  wiring_harness: "Wiring",
  diagnostic_flowchart: "Flowchart",
};

const apiBase = process.env.NEXT_PUBLIC_API_URL || "";

type ViewerMode = "select" | "pan";

export default function ViewerPage() {
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
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });
  const canvasRef = useRef<HTMLDivElement>(null);

  // Load diagram pages
  useEffect(() => {
    async function load() {
      try {
        const pages = await api.get<DiagramPageItem[]>("/api/viewer/diagrams");
        setDiagramPages(pages);
      } catch {
        setDiagramPages([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Load annotations when page selected
  const loadAnnotation = useCallback(async (page: DiagramPageItem) => {
    setSelectedComponent(null);
    setSelectedState(null);
    setAnnotation(null);
    setAnnotationError(null);

    if (page.annotated) {
      try {
        const ann = await api.get<DiagramAnnotation>(
          `/api/viewer/annotations/${page.page_id}`
        );
        setAnnotation(ann);
      } catch {
        // Not annotated yet
      }
    }
  }, []);

  const handleSelectPage = useCallback(
    (page: DiagramPageItem) => {
      setSelectedPage(page);
      setZoom(100);
      setPan({ x: 0, y: 0 });
      loadAnnotation(page);
    },
    [loadAnnotation]
  );

  const handleAnnotate = async () => {
    if (!selectedPage) return;
    setAnnotating(true);
    setAnnotationError(null);
    try {
      const result = await api.post<DiagramAnnotation>("/api/viewer/annotate", {
        page_id: selectedPage.page_id,
      }, { timeout: 120_000 });
      setAnnotation(result);
      // Update the page list to show annotated
      setDiagramPages((prev) =>
        prev.map((p) =>
          p.page_id === selectedPage.page_id
            ? { ...p, annotated: true, component_count: result.component_count }
            : p
        )
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Annotation failed";
      setAnnotationError(msg);
    } finally {
      setAnnotating(false);
    }
  };

  // Pan handling
  const handleMouseDown = (e: React.MouseEvent) => {
    if (mode !== "pan") return;
    setIsPanning(true);
    panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;
    setPan({
      x: panStart.current.panX + (e.clientX - panStart.current.x),
      y: panStart.current.panY + (e.clientY - panStart.current.y),
    });
  };

  const handleMouseUp = () => setIsPanning(false);

  // Get line color based on type and diagram context
  const getLineColor = (lineType: string) => {
    const isElectrical = annotation?.diagram_type === "electrical" || annotation?.diagram_type === "wiring";
    const colors = isElectrical ? ELECTRICAL_COLORS : HYDRAULIC_COLORS;
    return colors[lineType] || "#A0AEC0";
  };

  // Filter components by search
  const filteredComponents = annotation?.annotation_data?.components?.filter(
    (c) =>
      !searchTerm ||
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.designator.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Filter connections by active layer
  const visibleConnections = annotation?.annotation_data?.connections?.filter(
    (c) => !activeLayer || c.line_type === activeLayer
  );

  // Determine which components are active in current state
  const activeComponentIds = new Set(selectedState?.active_components || []);

  // Layer options based on diagram type
  const isElectrical = annotation?.diagram_type === "electrical" || annotation?.diagram_type === "wiring";
  const layerOptions = isElectrical
    ? [
        { value: "", label: "All Layers" },
        { value: "power_positive", label: "Power (+)" },
        { value: "ground_negative", label: "Ground (-)" },
        { value: "signal_data", label: "Signal" },
        { value: "can_bus", label: "CAN Bus" },
      ]
    : [
        { value: "", label: "All Layers" },
        { value: "pressure", label: "Pressure" },
        { value: "return", label: "Return" },
        { value: "pilot", label: "Pilot" },
        { value: "drain", label: "Drain" },
      ];

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 rounded-lg border bg-white p-3">
        <div className="flex items-center gap-2">
          <label htmlFor="zoom-slider" className="text-xs text-muted-foreground">Zoom</label>
          <input
            id="zoom-slider"
            type="range"
            min="25"
            max="300"
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
            className="w-24"
            aria-label="Zoom level"
          />
          <span className="w-10 text-xs text-muted-foreground">{zoom}%</span>
        </div>

        <div className="flex rounded-md border">
          <Button
            variant={mode === "select" ? "default" : "ghost"}
            size="sm"
            onClick={() => setMode("select")}
            title="Select mode"
            aria-label="Select mode"
          >
            <MousePointer className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant={mode === "pan" ? "default" : "ghost"}
            size="sm"
            onClick={() => setMode("pan")}
            title="Pan mode"
            aria-label="Pan mode"
          >
            <Move className="h-3.5 w-3.5" />
          </Button>
        </div>

        <select
          className="rounded-md border px-2 py-1 text-sm"
          value={activeLayer}
          onChange={(e) => setActiveLayer(e.target.value)}
          disabled={!annotation}
        >
          {layerOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>

        <select
          className="rounded-md border px-2 py-1 text-sm"
          value={selectedState?.id || ""}
          onChange={(e) => {
            const state = annotation?.operating_states?.find(
              (s) => s.id === e.target.value
            );
            setSelectedState(state || null);
          }}
          disabled={!annotation?.operating_states?.length}
        >
          <option value="">All states</option>
          {annotation?.operating_states?.map((state) => (
            <option key={state.id} value={state.id}>
              {state.name}
            </option>
          ))}
        </select>

        <div className="flex-1" />

        <div className="relative">
          <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            placeholder="Find component..."
            aria-label="Search components"
            className="rounded-md border py-1 pl-7 pr-2 text-sm"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            disabled={!annotation}
          />
        </div>
      </div>

      <div className="flex gap-4">
        {/* Diagram selector sidebar */}
        <div className="w-56 shrink-0 space-y-2 overflow-y-auto" style={{ maxHeight: "calc(100vh - 220px)" }}>
          <h3 className="text-sm font-semibold">Diagrams</h3>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : diagramPages.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No diagram pages found. Upload a manual with schematics.
            </p>
          ) : (
            diagramPages.map((page) => (
              <button
                key={page.page_id}
                className={`w-full rounded-lg border p-2 text-left text-xs transition-colors ${
                  selectedPage?.page_id === page.page_id
                    ? "border-emerald-500 bg-emerald-50"
                    : "hover:bg-slate-50"
                }`}
                onClick={() => handleSelectPage(page)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium truncate">{page.manual_title}</span>
                  <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                </div>
                <div className="mt-1 flex items-center gap-1">
                  <Badge variant="secondary" className="text-[10px]">
                    p.{page.page_number + 1}
                  </Badge>
                  <Badge variant="outline" className="text-[10px]">
                    {classificationLabels[page.classification] || page.classification}
                  </Badge>
                  {page.annotated && (
                    <Badge className="bg-emerald-100 text-emerald-800 text-[10px]">
                      AI
                    </Badge>
                  )}
                </div>
              </button>
            ))
          )}
        </div>

        {/* Canvas area */}
        <div className="flex-1">
          {!selectedPage ? (
            <EmptyState
              icon={Image}
              title="Select a diagram"
              description="Choose a schematic or diagram from the sidebar to view and annotate it."
            />
          ) : (
            <div
              ref={canvasRef}
              className="relative overflow-hidden rounded-lg border bg-slate-50"
              style={{
                height: "calc(100vh - 220px)",
                cursor: mode === "pan" ? (isPanning ? "grabbing" : "grab") : "default",
              }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            >
              {/* Image + overlay container */}
              <div
                className="absolute"
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom / 100})`,
                  transformOrigin: "top left",
                }}
              >
                {/* Page image */}
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${apiBase}/api/manuals/${selectedPage.manual_id}/pages/${selectedPage.page_number}/image`}
                  alt={`Page ${selectedPage.page_number + 1}`}
                  className="max-w-none"
                  draggable={false}
                  onLoad={(e) => {
                    const img = e.target as HTMLImageElement;
                    // Auto-fit zoom on load
                    if (canvasRef.current) {
                      const containerW = canvasRef.current.clientWidth;
                      const fitZoom = Math.min(
                        (containerW / img.naturalWidth) * 100,
                        100
                      );
                      setZoom(Math.round(fitZoom));
                    }
                  }}
                />

                {/* SVG overlay for annotations */}
                {annotation && (
                  <svg
                    className="absolute inset-0"
                    style={{ width: "100%", height: "100%", pointerEvents: "none" }}
                    viewBox="0 0 100 100"
                    preserveAspectRatio="none"
                  >
                    {/* Connection lines — only show when a component is selected */}
                    {selectedComponent && visibleConnections?.filter(
                      (c) => c.from_id === selectedComponent.id || c.to_id === selectedComponent.id
                    ).map((conn, i) => {
                      const fromComp = annotation.annotation_data.components.find(
                        (c) => c.id === conn.from_id
                      );
                      const toComp = annotation.annotation_data.components.find(
                        (c) => c.id === conn.to_id
                      );
                      if (!fromComp || !toComp) return null;

                      const fromX = fromComp.bbox_pct[0] + fromComp.bbox_pct[2] / 2;
                      const fromY = fromComp.bbox_pct[1] + fromComp.bbox_pct[3] / 2;
                      const toX = toComp.bbox_pct[0] + toComp.bbox_pct[2] / 2;
                      const toY = toComp.bbox_pct[1] + toComp.bbox_pct[3] / 2;

                      return (
                        <line
                          key={`conn-${i}`}
                          x1={fromX}
                          y1={fromY}
                          x2={toX}
                          y2={toY}
                          stroke={getLineColor(conn.line_type)}
                          strokeWidth={0.25}
                          opacity={0.6}
                          strokeDasharray="0.5 0.3"
                        />
                      );
                    })}

                    {/* Component markers — small pin labels at center of bbox */}
                    {filteredComponents?.map((comp) => {
                      const isActive =
                        !selectedState || activeComponentIds.has(comp.id);
                      const isSelected = selectedComponent?.id === comp.id;
                      const isConnected = selectedComponent && annotation.annotation_data.connections.some(
                        (c) =>
                          (c.from_id === selectedComponent.id && c.to_id === comp.id) ||
                          (c.to_id === selectedComponent.id && c.from_id === comp.id)
                      );
                      const isHighlighted =
                        searchTerm &&
                        (comp.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          comp.designator
                            .toLowerCase()
                            .includes(searchTerm.toLowerCase()));

                      // Place marker at center of bbox
                      const cx = comp.bbox_pct[0] + comp.bbox_pct[2] / 2;
                      const cy = comp.bbox_pct[1] + comp.bbox_pct[3] / 2;
                      const labelText = comp.designator;
                      const labelWidth = Math.max(labelText.length * 0.52 + 0.6, 2);
                      const labelHeight = 1.3;

                      const fillColor = isSelected
                        ? "#10B981"
                        : isConnected
                          ? "#6366F1"
                          : isHighlighted
                            ? "#F59E0B"
                            : "#1E293B";

                      const bgOpacity = isSelected ? 0.95 : isConnected ? 0.9 : isHighlighted ? 0.9 : 0.75;

                      return (
                        <g
                          key={comp.id}
                          style={{ pointerEvents: "all", cursor: "pointer" }}
                          opacity={isActive ? 1 : 0.3}
                          onClick={() => {
                            if (mode === "select") setSelectedComponent(comp);
                          }}
                        >
                          {/* Small clickable area around the marker */}
                          <rect
                            x={cx - labelWidth / 2 - 0.3}
                            y={cy - labelHeight / 2 - 0.3}
                            width={labelWidth + 0.6}
                            height={labelHeight + 0.6}
                            fill="transparent"
                          />
                          {/* Pin background */}
                          <rect
                            x={cx - labelWidth / 2}
                            y={cy - labelHeight / 2}
                            width={labelWidth}
                            height={labelHeight}
                            rx={0.3}
                            fill={fillColor}
                            opacity={bgOpacity}
                          />
                          {/* Pin text */}
                          <text
                            x={cx}
                            y={cy + 0.35}
                            textAnchor="middle"
                            fontSize={0.8}
                            fill="white"
                            fontWeight="bold"
                            fontFamily="system-ui, sans-serif"
                            style={{ pointerEvents: "none" }}
                          >
                            {labelText}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                )}
              </div>

              {/* Annotate button overlay */}
              {!annotation && !annotating && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/5">
                  <Button onClick={handleAnnotate} size="lg">
                    <Zap className="mr-2 h-4 w-4" />
                    Annotate with AI
                  </Button>
                </div>
              )}
              {annotating && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/10">
                  <div className="flex items-center gap-3 rounded-lg bg-white px-6 py-4 shadow-lg">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span className="text-sm font-medium">
                      Analyzing diagram with AI...
                    </span>
                  </div>
                </div>
              )}
              {annotationError && !annotating && !annotation && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/5">
                  <div className="flex flex-col items-center gap-3 rounded-lg bg-white px-6 py-4 shadow-lg max-w-sm">
                    <ZapOff className="h-5 w-5 text-red-500" />
                    <p className="text-sm text-red-600 text-center">{annotationError}</p>
                    <Button onClick={handleAnnotate} size="sm" variant="outline">
                      Retry Annotation
                    </Button>
                  </div>
                </div>
              )}

              {/* State description banner */}
              {selectedState && (
                <div className="absolute bottom-3 left-3 right-3 rounded-lg border bg-white/95 p-3 shadow-sm">
                  <div className="flex items-center gap-2">
                    <Zap className="h-4 w-4 text-amber-500" />
                    <span className="text-sm font-semibold">{selectedState.name}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {selectedState.description}
                  </p>
                  {selectedState.flow_paths.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedState.flow_paths.map((fp, i) => (
                        <Badge
                          key={i}
                          style={{
                            backgroundColor: getLineColor(fp.line_type) + "20",
                            color: getLineColor(fp.line_type),
                            borderColor: getLineColor(fp.line_type),
                          }}
                          variant="outline"
                          className="text-[10px]"
                        >
                          {fp.line_type}: {fp.path.join(" → ")}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Component info side panel */}
        <div className="hidden w-64 shrink-0 space-y-4 xl:block">
          <Card>
            <CardContent className="p-4">
              <h3 className="mb-3 font-semibold">Component Info</h3>
              {selectedComponent ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded bg-slate-100 text-xs font-bold">
                      {COMPONENT_TYPE_ICONS[selectedComponent.type] || "?"}
                    </div>
                    <div>
                      <p className="text-sm font-medium">
                        {selectedComponent.designator}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {selectedComponent.name}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">Type</p>
                    <Badge variant="secondary" className="capitalize">
                      {selectedComponent.type}
                    </Badge>
                  </div>

                  {Object.keys(selectedComponent.specs || {}).length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-muted-foreground">Specs</p>
                      <div className="space-y-1">
                        {Object.entries(selectedComponent.specs).map(([k, v]) => (
                          <div key={k} className="flex justify-between text-xs">
                            <span className="text-muted-foreground">{k}</span>
                            <span className="font-medium">{v}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Show connections for this component */}
                  {annotation && (
                    <div className="space-y-1">
                      <p className="text-xs font-medium text-muted-foreground">
                        Connections
                      </p>
                      {annotation.annotation_data.connections
                        .filter(
                          (c) =>
                            c.from_id === selectedComponent.id ||
                            c.to_id === selectedComponent.id
                        )
                        .map((conn, i) => {
                          const otherId =
                            conn.from_id === selectedComponent.id
                              ? conn.to_id
                              : conn.from_id;
                          const other =
                            annotation.annotation_data.components.find(
                              (c) => c.id === otherId
                            );
                          return (
                            <div
                              key={i}
                              className="flex items-center gap-1 text-xs"
                            >
                              <div
                                className="h-2 w-2 rounded-full"
                                style={{
                                  backgroundColor: getLineColor(conn.line_type),
                                }}
                              />
                              <span className="text-muted-foreground">
                                {conn.line_type}
                              </span>
                              <span>→</span>
                              <button
                                className="font-medium text-emerald-600 hover:underline"
                                onClick={() => {
                                  if (other) setSelectedComponent(other);
                                }}
                              >
                                {other?.designator || otherId}
                              </button>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Click a component on the diagram to see its details.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Annotation summary */}
          {annotation && (
            <Card>
              <CardContent className="p-4">
                <h3 className="mb-2 text-sm font-semibold">Annotation Summary</h3>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Type</span>
                    <span className="capitalize">{annotation.diagram_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Components</span>
                    <span>{annotation.component_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Connections</span>
                    <span>{annotation.connection_count}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">States</span>
                    <span>{annotation.operating_states?.length || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Confidence</span>
                    <span>{Math.round(annotation.confidence_overall * 100)}%</span>
                  </div>
                  {annotation.verified && (
                    <Badge className="mt-1 bg-emerald-100 text-emerald-800 text-[10px]">
                      Human Verified
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Component list */}
          {annotation && (
            <Card>
              <CardContent className="p-4">
                <h3 className="mb-2 text-sm font-semibold">
                  Components ({annotation.component_count})
                </h3>
                <div
                  className="space-y-1 overflow-y-auto"
                  style={{ maxHeight: "200px" }}
                >
                  {annotation.annotation_data.components.map((comp) => (
                    <button
                      key={comp.id}
                      className={`w-full rounded px-2 py-1 text-left text-xs transition-colors ${
                        selectedComponent?.id === comp.id
                          ? "bg-emerald-50 text-emerald-800"
                          : "hover:bg-slate-50"
                      }`}
                      onClick={() => setSelectedComponent(comp)}
                    >
                      <span className="font-medium">{comp.designator}</span>
                      <span className="ml-1 text-muted-foreground">{comp.name}</span>
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
