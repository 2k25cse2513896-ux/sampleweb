type BrandLogoProps = { name: string; footer?: boolean };

export default function BrandLogo({ name, footer = false }: BrandLogoProps) {
  return <span className={`brand-logo ${footer ? "brand-logo-footer" : ""}`} aria-label={name}><span className="brand-mark"><svg viewBox="0 0 32 32" role="img" aria-hidden="true"><path d="M7 8h18v4h-7v12h-4V12H7z" fill="currentColor"/><path d="M20 16h5v8h-5z" fill="currentColor" opacity=".55"/></svg></span><span>{name}</span></span>;
}
