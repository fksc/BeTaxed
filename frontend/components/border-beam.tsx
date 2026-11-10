"use client";

import {
  createElement,
  forwardRef,
  type ButtonHTMLAttributes,
  type CSSProperties,
  type ReactNode,
} from "react";

type BorderBeamProps = {
  children: ReactNode;
  as?: "button" | "div";
  className?: string;
  innerClassName?: string;
  borderRadius?: string | number;
  duration?: number;
  borderWidth?: number;
  style?: CSSProperties;
} & Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "className" | "style">;

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
