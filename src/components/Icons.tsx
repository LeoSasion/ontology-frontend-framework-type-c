type IconProps = {
  className?: string;
};

export function Icon({ name, className }: IconProps & { name: "source" | "dashboard" | "agent" | "evidence" | "query" | "lock" | "check" | "settings" | "copy" | "collapse" | "close" }) {
  const common = {
    className: className ?? "icon",
    viewBox: "0 0 24 24",
    width: 18,
    height: 18,
    "aria-hidden": true,
  };
  if (name === "source") {
    return (
      <svg {...common}>
        <path d="M5 5.5C5 3.6 8.1 2 12 2s7 1.6 7 3.5S15.9 9 12 9 5 7.4 5 5.5Z" />
        <path d="M5 5.5v6C5 13.4 8.1 15 12 15s7-1.6 7-3.5v-6" />
        <path d="M5 11.5v7C5 20.4 8.1 22 12 22s7-1.6 7-3.5v-7" />
      </svg>
    );
  }
  if (name === "dashboard") {
    return (
      <svg {...common}>
        <rect x="3" y="4" width="7" height="7" rx="1.5" />
        <rect x="14" y="4" width="7" height="4" rx="1.5" />
        <rect x="14" y="12" width="7" height="8" rx="1.5" />
        <rect x="3" y="15" width="7" height="5" rx="1.5" />
      </svg>
    );
  }
  if (name === "agent") {
    return (
      <svg {...common}>
        <path d="M12 3v3" />
        <rect x="5" y="6" width="14" height="12" rx="3" />
        <path d="M9 11h.01M15 11h.01M9 15h6" />
        <path d="M4 13H2M22 13h-2" />
      </svg>
    );
  }
  if (name === "evidence") {
    return (
      <svg {...common}>
        <path d="M7 3h7l4 4v14H7z" />
        <path d="M14 3v5h5" />
        <path d="M10 12h6M10 16h6" />
      </svg>
    );
  }
  if (name === "query") {
    return (
      <svg {...common}>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 5 5" />
      </svg>
    );
  }
  if (name === "check") {
    return (
      <svg {...common}>
        <path d="m5 12 4 4L19 6" />
      </svg>
    );
  }
  if (name === "settings") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a8 8 0 0 0 .1-2l2-1.5-2-3.4-2.4 1a8 8 0 0 0-1.7-1L15 5.5h-4l-.4 2.6a8 8 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.5a8 8 0 0 0 .1 2l-2.1 1.5 2 3.4 2.4-1a8 8 0 0 0 1.7 1l.4 2.6h4l.4-2.6a8 8 0 0 0 1.7-1l2.4 1 2-3.4Z" />
      </svg>
    );
  }
  if (name === "copy") {
    return (
      <svg {...common}>
        <rect x="8" y="8" width="11" height="11" rx="2" />
        <path d="M5 15H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v1" />
      </svg>
    );
  }
  if (name === "collapse") {
    return (
      <svg {...common}>
        <path d="M14 6 8 12l6 6" />
        <path d="M19 6v12" />
      </svg>
    );
  }
  if (name === "close") {
    return (
      <svg {...common}>
        <path d="M6 6 18 18" />
        <path d="M18 6 6 18" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <rect x="5" y="10" width="14" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}
