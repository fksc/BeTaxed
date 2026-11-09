"use client";

import { createElement, forwardRef, type CSSProperties, type ElementType, type ReactNode } from "react";

type BorderBeamProps = {
  children: ReactNode;
  as?: ElementType;
  className?: string;
  innerClassName?: string;
  borderRadius?: string | number;
  duration?: number;
  borderWidth?: number;
  style?: CSSProperties;
} & Record<string, unknown>;

/** Burgundy hotspot that travels the border. Same treatment as the marketing pill. */
export const BorderBeam = forwardRef<HTMLElement, BorderBeamProps>(function BorderBeam(
  {
    children,
    as: Tag = "div",
    className = "",
    innerClassName = "",
    borderRadius = "inherit",
    duration = 2,
    borderWidth = 2,
    style,
    ...rest
  },
  ref,
) {
  const radius = typeof borderRadius === "number" ? `${borderRadius}px` : borderRadius;
  return createElement(
    Tag,
    {
      ref,
      className: `border-beam ${className}`.trim(),
      style: {
        borderRadius: radius,
        "--beam-duration": `${duration}s`,
        "--beam-width": `${borderWidth}px`,
        ...style,
      } as CSSProperties,
      ...rest,
    },
    createElement(
      "div",
      {
        className: `border-beam-inner ${innerClassName}`.trim(),
        style: { borderRadius: radius },
      },
      children,
    ),
  );
});
