"use client";

import { ComingSoon } from "@/components/ui/coming-soon";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BookOpen } from "lucide-react";

export default function ManualDetailPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Manual Details</h1>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="pages">Pages</TabsTrigger>
          <TabsTrigger value="schematics">Schematics</TabsTrigger>
          <TabsTrigger value="specs">Specs</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          <ComingSoon
            icon={BookOpen}
            feature="Manual Overview"
            description="View manual metadata, classification breakdown, and processing timeline."
            phase={1}
          />
        </TabsContent>

        <TabsContent value="pages" className="mt-6">
          <ComingSoon
            icon={BookOpen}
            feature="Page Browser"
            description="Browse individual pages with OCR text, classification tags, and image preview."
            phase={1}
          />
        </TabsContent>

        <TabsContent value="schematics" className="mt-6">
          <ComingSoon
            icon={BookOpen}
            feature="Schematic Pages"
            description="View all hydraulic and electrical schematics detected in this manual."
            phase={5}
          />
        </TabsContent>

        <TabsContent value="specs" className="mt-6">
          <ComingSoon
            icon={BookOpen}
            feature="Extracted Specifications"
            description="Auto-extracted torque specs, pressures, and part numbers from this manual."
            phase={1}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
