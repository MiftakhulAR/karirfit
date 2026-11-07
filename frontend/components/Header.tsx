"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useApp } from "./AppProvider";
import type { Lang } from "@/lib/types";

export function Header() {
  const { lang, setLang, user, signOut, t } = useApp();
  const path = usePathname();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [path]);   // close the mobile menu after navigating

  const links: [string, string][] = user
    ? [["/", t.nav_home], ["/tes", t.nav_test], ["/karier", t.nav_careers], ["/riwayat", t.nav_history]]
    : [["/", t.nav_home], ["/karier", t.nav_careers]];
  const isOn = (href: string) => (href === "/" ? path === "/" : path?.startsWith(href));

  const langSwitch = (
    <div className="lang" role="group" aria-label="Language">
      {(["id", "en"] as Lang[]).map(l => (
        <button key={l} aria-pressed={lang === l} onClick={() => setLang(l)}>{l.toUpperCase()}</button>
      ))}
    </div>
  );

  return (
    <header className={"top" + (open ? " open" : "")}>
      <div className="top-in">
        <Link className="brand" href="/" aria-label="KarirFit">Karir<b>Fit</b></Link>
        <nav className="top-links" aria-label="Main">
          {links.map(([href, label]) => (
            <Link key={href} href={href} aria-current={isOn(href) ? "page" : undefined}>{label}</Link>
          ))}
        </nav>
        <div className="top-right">
          {langSwitch}
          {user ? (
            <div className="account">
              <span className="avatar" aria-hidden="true">{(user.name || user.email).trim().charAt(0).toUpperCase()}</span>
              <span className="who">{user.name || user.email}</span>
              <button className="linkbtn" onClick={() => signOut()}>{t.nav_logout}</button>
            </div>
          ) : (
            <Link className="btn primary small" href="/masuk">{t.nav_login}</Link>
          )}
        </div>
        <button className="burger" aria-expanded={open} aria-controls="mobile-menu" onClick={() => setOpen(v => !v)}>
          <span className="sr">{open ? t.nav_close : t.nav_menu}</span>
          <i /><i /><i />
        </button>
      </div>
      {open && (
        <div className="mobile-menu" id="mobile-menu">
          {user && <p className="mm-user">{user.name || user.email}</p>}
          <nav aria-label="Mobile">
            {links.map(([href, label]) => (
              <Link key={href} href={href} aria-current={isOn(href) ? "page" : undefined}>{label}</Link>
            ))}
          </nav>
          <div className="mm-foot">
            {langSwitch}
            {user
              ? <button className="btn ghost" onClick={() => { setOpen(false); signOut(); }}>{t.nav_logout}</button>
              : <Link className="btn primary" href="/masuk">{t.nav_login}</Link>}
          </div>
        </div>
      )}
    </header>
  );
}

export function Footer() {
  const { t } = useApp();
  return <footer className="foot"><p>{t.footer}</p></footer>;
}

export function ServerError() {
  const { modelError, reloadModel, waking, t } = useApp();
  if (waking) return <p className="notice" role="status">{t.waking}</p>;
  if (!modelError) return null;
  return (
    <div className="notice error" role="alert">
      <p>{modelError}</p>
      <button className="btn" onClick={reloadModel}>{t.retry}</button>
    </div>
  );
}
