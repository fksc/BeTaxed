import type { CSSProperties, MouseEventHandler, ReactNode } from "react";

type SpecularButtonProps = {
  children?: ReactNode;
  size?: string;
  radius?: number;
  tint?: string;
  tintOpacity?: number;
  blur?: number;
  textColor?: string;
  lineColor?: string;
  baseColor?: string;
  intensity?: number;
  idleIntensity?: number;
  shineSize?: number;
  shineFade?: number;
  thickness?: number;
  glow?: number;
  speed?: number;
  followMouse?: boolean;
  proximity?: number;
  autoAnimate?: boolean;
  disabled?: boolean;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  className?: string;
  type?: "button" | "submit" | "reset";
  style?: CSSProperties;
};

declare function SpecularButton(props: SpecularButtonProps): React.ReactElement;

export default SpecularButton;
