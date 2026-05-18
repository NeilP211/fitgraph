"use client";

import { useCallback, useRef, useState } from "react";

const CATEGORIES = [
  { value: "", label: "Any category" },
  { value: "tops", label: "Tops" },
  { value: "bottoms", label: "Bottoms" },
  { value: "shoes", label: "Shoes" },
  { value: "bags", label: "Bags" },
  { value: "jewellery", label: "Jewellery" },
  { value: "outerwear", label: "Outerwear" },
  { value: "dresses", label: "Dresses" },
  { value: "accessories", label: "Accessories" },
];

interface UploadZoneProps {
  onSubmit: (file: File, category: string, text: string) => void;
  loading: boolean;
}

export default function UploadZone({ onSubmit, loading }: UploadZoneProps) {
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState("");
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = (f: File) => {
    setFile(f);
    const url = URL.createObjectURL(f);
    setPreview(url);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith("image/")) accept(f);
  }, []);

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  };
  const onDragLeave = () => setDragging(false);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) accept(f);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    onSubmit(file, category, text);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload a garment image"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 transition-all cursor-pointer select-none
          ${dragging ? "border-stone-500 bg-stone-100" : "border-stone-300 bg-stone-50 hover:border-stone-400 hover:bg-stone-100"}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={onFileChange}
          aria-label="File input"
        />

        {preview ? (
          <div className="relative">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={preview}
              alt="Preview of uploaded garment"
              className="h-52 w-52 object-cover rounded-xl shadow-md"
            />
            <button
              type="button"
              aria-label="Remove image"
              onClick={(e) => {
                e.stopPropagation();
                setPreview(null);
                setFile(null);
              }}
              className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center rounded-full bg-stone-900 text-white text-xs shadow hover:bg-stone-700 transition-colors"
            >
              ✕
            </button>
          </div>
        ) : (
          <>
            <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-stone-200 text-stone-400">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="h-7 w-7"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                />
              </svg>
            </div>
            <p className="text-sm font-medium text-stone-600">
              Drag & drop or{" "}
              <span className="text-stone-900 underline underline-offset-2">
                browse
              </span>
            </p>
            <p className="mt-1 text-xs text-stone-400">
              JPG, PNG, WEBP — any garment photo
            </p>
          </>
        )}
      </div>

      {/* Category + Description */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="category"
            className="text-xs font-medium text-stone-500 uppercase tracking-wide"
          >
            Category
          </label>
          <select
            id="category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-sm text-stone-800 shadow-sm focus:outline-none focus:ring-2 focus:ring-stone-400"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="description"
            className="text-xs font-medium text-stone-500 uppercase tracking-wide"
          >
            Description{" "}
            <span className="normal-case text-stone-400">(optional)</span>
          </label>
          <input
            id="description"
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. floral midi dress"
            className="rounded-xl border border-stone-300 bg-white px-4 py-2.5 text-sm text-stone-800 shadow-sm placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-400"
          />
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={!file || loading}
        className="w-full rounded-xl bg-stone-900 px-6 py-3 text-sm font-semibold text-white shadow transition-all hover:bg-stone-700 focus:outline-none focus:ring-2 focus:ring-stone-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg
              className="h-4 w-4 animate-spin"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              />
            </svg>
            Finding matches…
          </span>
        ) : (
          "Find Matching Pieces"
        )}
      </button>
    </form>
  );
}
