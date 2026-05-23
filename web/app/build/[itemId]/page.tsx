"use client";

import { use } from "react";
import TheShow from "@/components/show/TheShow";

export default function BuildPage({
  params,
}: {
  params: Promise<{ itemId: string }>;
}) {
  const { itemId } = use(params);
  return <TheShow itemId={decodeURIComponent(itemId)} />;
}
