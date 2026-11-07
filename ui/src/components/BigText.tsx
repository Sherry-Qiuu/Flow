import type { CSSProperties, ReactNode } from "react";

interface BigTextProps {
  children: ReactNode;
  className?: string;
  as?: "h1" | "h2" | "p" | "div";
  lines?: number;
}

export function BigText({
  children,
  className = "",
  as = "p",
  lines = 3,
}: BigTextProps) {
  const Tag = as;
  const style = {
    WebkitLineClamp: lines,
    lineClamp: lines,
  } as CSSProperties;
  return (
    <Tag className={`big-text ${className}`} style={style}>
      {children}
    </Tag>
  );
}
