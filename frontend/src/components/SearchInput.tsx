interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
}

export default function SearchInput({
  value,
  onChange,
  placeholder = "Buscar…",
  ariaLabel = "Buscar",
}: SearchInputProps) {
  return (
    <div className="relative w-full max-w-md">
      <svg
        viewBox="0 0 20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-text-muted"
        aria-hidden
      >
        <circle cx="9" cy="9" r="6" />
        <path d="m14 14 4 4" />
      </svg>
      <input
        type="text"
        placeholder={placeholder}
        aria-label={ariaLabel}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="field-input pl-10 pr-10"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Limpar busca"
          className="absolute right-2.5 top-1/2 -translate-y-1/2 h-6 w-6 grid place-items-center rounded-md text-text-muted hover:text-text-primary hover:bg-surface-overlay transition-colors"
        >
          <svg
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.6}
            strokeLinecap="round"
            className="h-3.5 w-3.5"
            aria-hidden
          >
            <path d="m4 4 8 8M12 4l-8 8" />
          </svg>
        </button>
      )}
    </div>
  );
}
