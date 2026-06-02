"use client";

interface URLInputFormProps {
  youtubeUrl: string;
  instagramUrl: string;
  loading: boolean;
  onYoutubeChange: (value: string) => void;
  onInstagramChange: (value: string) => void;
  onSubmit: () => void;
}

export default function URLInputForm({
  youtubeUrl,
  instagramUrl,
  loading,
  onYoutubeChange,
  onInstagramChange,
  onSubmit,
}: URLInputFormProps) {
  return (
    <form
      className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="mb-3">
        <h1 className="text-lg font-semibold text-zinc-900">CreatorJoy RAG Analyst</h1>
        <p className="text-sm text-zinc-500">
          Compare a YouTube video (A) and Instagram Reel (B), then chat with grounded citations.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-medium text-zinc-700">YouTube URL (Video A)</span>
          <input
            value={youtubeUrl}
            onChange={(event) => onYoutubeChange(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
            required
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1 block font-medium text-zinc-700">Instagram Reel URL (Video B)</span>
          <input
            value={instagramUrl}
            onChange={(event) => onInstagramChange(event.target.value)}
            placeholder="https://www.instagram.com/reel/..."
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
            required
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={loading || !youtubeUrl || !instagramUrl}
        className="mt-4 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
      >
        {loading ? "Ingesting videos..." : "Ingest & Analyze"}
      </button>
    </form>
  );
}
