interface Props {
  tone: "warning" | "info";
  title: string;
  children: React.ReactNode;
}

export default function Banner({ tone, title, children }: Props) {
  return (
    <div className={`banner banner--${tone}`} role="note">
      <span className="banner__icon" aria-hidden="true">{tone === "warning" ? "⚠" : "ℹ"}</span>
      <div>
        <p className="banner__title">{title}</p>
        <p className="banner__body">{children}</p>
      </div>
    </div>
  );
}
