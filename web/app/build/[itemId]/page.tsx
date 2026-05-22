"use client";

import { use } from "react";
import OutfitBuilder from "@/components/OutfitBuilder";

export default function BuildPage({
  params,
}: {
  params: Promise<{ itemId: string }>;
}) {
  const { itemId } = use(params);
  return <OutfitBuilder itemId={decodeURIComponent(itemId)} />;
}
