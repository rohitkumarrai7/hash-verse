"use client";

function YoutubeIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-youtube" aria-hidden="true">
      <path
        fill="currentColor"
        d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8ZM9.6 15.6V8.4L15.8 12 9.6 15.6Z"
      />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 text-instagram" aria-hidden="true">
      <path
        fill="currentColor"
        d="M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5Zm10 2H7a3 3 0 0 0-3 3v10a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3V7a3 3 0 0 0-3-3Zm-5 3.5A5.5 5.5 0 1 1 6.5 13 5.5 5.5 0 0 1 12 7.5Zm0 2A3.5 3.5 0 1 0 15.5 13 3.5 3.5 0 0 0 12 9.5ZM17.8 6.3a1.3 1.3 0 1 1-1.3 1.3 1.3 1.3 0 0 1 1.3-1.3Z"
      />
    </svg>
  );
}

function Spinner() {
  return (
    <svg className="spinner h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

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
      className="card p-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1.5 flex items-center gap-2 font-medium text-foreground">
            <YoutubeIcon />
            YouTube URL (Video A)
          </span>
          <input
            value={youtubeUrl}
            onChange={(event) => onYoutubeChange(event.target.value)}
            placeholder="https://www.youtube.com/watch?v=..."
            className="input"
            required
          />
        </label>

        <label className="block text-sm">
          <span className="mb-1.5 flex items-center gap-2 font-medium text-foreground">
            <InstagramIcon />
            Instagram Reel URL (Video B)
          </span>
          <input
            value={instagramUrl}
            onChange={(event) => onInstagramChange(event.target.value)}
            placeholder="https://www.instagram.com/reel/..."
            className="input"
            required
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={loading || !youtubeUrl || !instagramUrl}
        className="btn-primary mt-4"
      >
        {loading && <Spinner />}
        {loading ? "Ingesting videos..." : "Ingest & Analyze"}
      </button>
    </form>
  );
}
