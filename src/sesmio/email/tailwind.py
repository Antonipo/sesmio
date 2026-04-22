"""Embedded Tailwind CSS subset — ~250 utility classes mapped to inline CSS.

No Node, no build step. Unknown classes are silently ignored (logged at debug).
"""

from __future__ import annotations

import logging

_logger = logging.getLogger("sesmio")

# Spacing scale in rem: index → value
_SP = {
    "0": "0",
    "1": "0.25rem",
    "2": "0.5rem",
    "3": "0.75rem",
    "4": "1rem",
    "5": "1.25rem",
    "6": "1.5rem",
    "8": "2rem",
    "10": "2.5rem",
    "12": "3rem",
    "16": "4rem",
}

_SPACING_PROPS: dict[str, list[str]] = {
    "p": ["padding"],
    "px": ["padding-left", "padding-right"],
    "py": ["padding-top", "padding-bottom"],
    "pt": ["padding-top"],
    "pr": ["padding-right"],
    "pb": ["padding-bottom"],
    "pl": ["padding-left"],
    "m": ["margin"],
    "mx": ["margin-left", "margin-right"],
    "my": ["margin-top", "margin-bottom"],
    "mt": ["margin-top"],
    "mr": ["margin-right"],
    "mb": ["margin-bottom"],
    "ml": ["margin-left"],
}


def _build_spacing() -> dict[str, str]:
    result: dict[str, str] = {}
    for prefix, props in _SPACING_PROPS.items():
        for scale, value in _SP.items():
            declarations = "; ".join(f"{p}: {value}" for p in props)
            result[f"{prefix}-{scale}"] = declarations
    return result


# Gray palette (50–900)
_GRAY = {
    "50": "#f9fafb",
    "100": "#f3f4f6",
    "200": "#e5e7eb",
    "300": "#d1d5db",
    "400": "#9ca3af",
    "500": "#6b7280",
    "600": "#4b5563",
    "700": "#374151",
    "800": "#1f2937",
    "900": "#111827",
}

# Slate palette (50–900)
_SLATE = {
    "50": "#f8fafc",
    "100": "#f1f5f9",
    "200": "#e2e8f0",
    "300": "#cbd5e1",
    "400": "#94a3b8",
    "500": "#64748b",
    "600": "#475569",
    "700": "#334155",
    "800": "#1e293b",
    "900": "#0f172a",
}

# Reduced palettes for primary colours (min 500/600/700 per spec)
_RED = {"500": "#ef4444", "600": "#dc2626", "700": "#b91c1c"}
_BLUE = {"500": "#3b82f6", "600": "#2563eb", "700": "#1d4ed8"}
_GREEN = {"500": "#22c55e", "600": "#16a34a", "700": "#15803d"}
_AMBER = {"500": "#f59e0b", "600": "#d97706", "700": "#b45309"}

_PALETTES: dict[str, dict[str, str]] = {
    "gray": _GRAY,
    "slate": _SLATE,
    "red": _RED,
    "blue": _BLUE,
    "green": _GREEN,
    "amber": _AMBER,
}


def _build_colors() -> dict[str, str]:
    result: dict[str, str] = {}
    for name, shades in _PALETTES.items():
        for shade, hex_val in shades.items():
            result[f"text-{name}-{shade}"] = f"color: {hex_val}"
            result[f"bg-{name}-{shade}"] = f"background-color: {hex_val}"
    # Named colors
    result["bg-white"] = "background-color: #ffffff"
    result["bg-black"] = "background-color: #000000"
    result["bg-transparent"] = "background-color: transparent"
    result["text-white"] = "color: #ffffff"
    result["text-black"] = "color: #000000"
    return result


# Static tailwind map — module-level, immutable after build.
TAILWIND_MAP: dict[str, str] = {
    # ── Sizing ──────────────────────────────────────────────────────────
    "w-full": "width: 100%",
    "w-auto": "width: auto",
    "w-1/2": "width: 50%",
    "w-1/3": "width: 33.333333%",
    "w-2/3": "width: 66.666667%",
    "w-1/4": "width: 25%",
    "w-3/4": "width: 75%",
    "h-full": "height: 100%",
    "h-auto": "height: auto",
    "h-screen": "height: 100vh",
    "max-w-sm": "max-width: 24rem",
    "max-w-md": "max-width: 28rem",
    "max-w-lg": "max-width: 32rem",
    "max-w-xl": "max-width: 36rem",
    "max-w-2xl": "max-width: 42rem",
    "max-w-full": "max-width: 100%",
    "min-h-screen": "min-height: 100vh",
    # ── Typography ───────────────────────────────────────────────────────
    "text-xs": "font-size: 0.75rem; line-height: 1rem",
    "text-sm": "font-size: 0.875rem; line-height: 1.25rem",
    "text-base": "font-size: 1rem; line-height: 1.5rem",
    "text-lg": "font-size: 1.125rem; line-height: 1.75rem",
    "text-xl": "font-size: 1.25rem; line-height: 1.75rem",
    "text-2xl": "font-size: 1.5rem; line-height: 2rem",
    "text-3xl": "font-size: 1.875rem; line-height: 2.25rem",
    "text-4xl": "font-size: 2.25rem; line-height: 2.5rem",
    "font-normal": "font-weight: 400",
    "font-medium": "font-weight: 500",
    "font-semibold": "font-weight: 600",
    "font-bold": "font-weight: 700",
    "italic": "font-style: italic",
    "underline": "text-decoration: underline",
    "no-underline": "text-decoration: none",
    "text-left": "text-align: left",
    "text-center": "text-align: center",
    "text-right": "text-align: right",
    "leading-none": "line-height: 1",
    "leading-tight": "line-height: 1.25",
    "leading-normal": "line-height: 1.5",
    "leading-relaxed": "line-height: 1.625",
    "tracking-tight": "letter-spacing: -0.05em",
    "tracking-normal": "letter-spacing: 0em",
    "tracking-wide": "letter-spacing: 0.05em",
    # ── Layout ───────────────────────────────────────────────────────────
    "block": "display: block",
    "inline-block": "display: inline-block",
    "inline": "display: inline",
    "hidden": "display: none",
    # Margin auto helpers
    "mx-auto": "margin-left: auto; margin-right: auto",
    "my-auto": "margin-top: auto; margin-bottom: auto",
    "m-auto": "margin: auto",
    # ── Borders ──────────────────────────────────────────────────────────
    "border": "border-width: 1px; border-style: solid",
    "border-0": "border-width: 0",
    "border-2": "border-width: 2px; border-style: solid",
    "border-4": "border-width: 4px; border-style: solid",
    "border-gray-200": "border-color: #e5e7eb",
    "border-gray-300": "border-color: #d1d5db",
    "border-gray-400": "border-color: #9ca3af",
    "border-transparent": "border-color: transparent",
    "rounded-none": "border-radius: 0",
    "rounded-sm": "border-radius: 0.125rem",
    "rounded": "border-radius: 0.25rem",
    "rounded-md": "border-radius: 0.375rem",
    "rounded-lg": "border-radius: 0.5rem",
    "rounded-xl": "border-radius: 0.75rem",
    "rounded-full": "border-radius: 9999px",
    # ── Effects (email-safe shadows) ─────────────────────────────────────
    "shadow-sm": "box-shadow: 0 1px 2px 0 rgba(0,0,0,0.05)",
    "shadow-md": "box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)",
    "shadow-lg": "box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05)",
    # ── Overflow ─────────────────────────────────────────────────────────
    "overflow-hidden": "overflow: hidden",
    "overflow-auto": "overflow: auto",
    # ── Opacity ──────────────────────────────────────────────────────────
    "opacity-0": "opacity: 0",
    "opacity-50": "opacity: 0.5",
    "opacity-100": "opacity: 1",
}

# Merge in generated entries (spacing + colors override nothing; add new keys).
TAILWIND_MAP.update(_build_spacing())
TAILWIND_MAP.update(_build_colors())

# Freeze by not exposing the dict as mutable (callers should not mutate it).
# Module-level dicts are thread-safe for reads; writes are not expected.


def resolve_classes(class_string: str) -> str:
    """Translate a space-separated Tailwind class string to CSS declarations.

    Args:
        class_string: Space-separated Tailwind utility classes
            (e.g. ``"max-w-lg mx-auto p-6 bg-white"``).

    Returns:
        Semicolon-joined CSS declarations ready for a ``style=`` attribute
        (e.g. ``"max-width: 32rem; margin-left: auto; margin-right: auto; ...``).
        Empty string if no classes resolve.
    """
    parts: list[str] = []
    for cls in class_string.split():
        css = TAILWIND_MAP.get(cls)
        if css is None:
            _logger.debug("tailwind: unknown class %r — ignored", cls)
        else:
            parts.append(css)
    return "; ".join(parts)
