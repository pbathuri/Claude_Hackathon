// src/pages/LandingPage.tsx
// ──────────────────────────────────────────────────────────────
// Public landing page. White background, WHO branding.
// Entry point for the application before login.
// ──────────────────────────────────────────────────────────────

import { useNavigate } from "react-router-dom";

const FEATURES = [
  {
    icon: "🌐",
    title: "Global Triage Intelligence",
    desc: "AI-powered symptom analysis across 50+ countries, aligned with WHO ICD-11 classification standards.",
  },
  {
    icon: "📱",
    title: "SMS & Voice Intake",
    desc: "Patients submit symptoms and images via SMS or voice call — no smartphone app required.",
  },
  {
    icon: "⚖",
    title: "Jurisdiction-Aware Care",
    desc: "Tier-based decision support enforces WHO jurisdictional rules for safe cross-border telehealth.",
  },
  {
    icon: "🔴",
    title: "Real-Time Priority Queue",
    desc: "Cases are automatically ranked by urgency and country tier so critical patients are never missed.",
  },
];

const STATS = [
  { value: "50+", label: "Countries Covered" },
  { value: "4", label: "Jurisdiction Tiers" },
  { value: "ICD-11", label: "WHO Standard" },
  { value: "24/7", label: "AI Intake" },
];

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div style={styles.page}>
      {/* ── Top navigation bar ──────────────────────────────── */}
      <header style={styles.navbar}>
        <div style={styles.navLogo}>
          <span style={styles.navLogoMark}>✚</span>
          <span style={styles.navLogoText}>WHO Triage Intelligence</span>
        </div>
        <button style={styles.navSignInBtn} onClick={() => navigate("/login")}>
          Sign In
        </button>
      </header>

      {/* ── Hero section ────────────────────────────────────── */}
      <section style={styles.hero}>
        <div style={styles.whoRibbon}>
          <span style={styles.whoRibbonIcon}>✚</span>
          World Health Organization — Telehealth Triage Platform
        </div>
        <h1 style={styles.heroTitle}>
          AI-Powered Global<br />
          <span style={styles.heroAccent}>Health Triage</span>
        </h1>
        <p style={styles.heroSubtitle}>
          A WHO-aligned telehealth platform connecting remote patients to
          verified doctors through SMS, voice, and AI triage — wherever care
          is needed most.
        </p>
        <div style={styles.heroBtns}>
          <button style={styles.primaryBtn} onClick={() => navigate("/login")}>
            Sign In as a Doctor
          </button>
          <a style={styles.ghostBtn} href="#features">
            Learn More
          </a>
        </div>
      </section>

      {/* ── Stats strip ─────────────────────────────────────── */}
      <section style={styles.statsStrip}>
        {STATS.map((s) => (
          <div key={s.label} style={styles.statItem}>
            <span style={styles.statValue}>{s.value}</span>
            <span style={styles.statLabel}>{s.label}</span>
          </div>
        ))}
      </section>

      {/* ── Features section ────────────────────────────────── */}
      <section id="features" style={styles.featuresSection}>
        <h2 style={styles.sectionTitle}>Platform Capabilities</h2>
        <p style={styles.sectionSubtitle}>
          Built to the WHO's standards for safe, equitable, and scalable
          telehealth in low-resource settings.
        </p>
        <div style={styles.featuresGrid}>
          {FEATURES.map((f) => (
            <div key={f.title} style={styles.featureCard}>
              <span style={styles.featureIcon}>{f.icon}</span>
              <h3 style={styles.featureTitle}>{f.title}</h3>
              <p style={styles.featureDesc}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA section ─────────────────────────────────────── */}
      <section style={styles.ctaSection}>
        <div style={styles.ctaCard}>
          <h2 style={styles.ctaTitle}>Ready to access the portal?</h2>
          <p style={styles.ctaSubtitle}>
            Licensed WHO physicians can sign in using their WHO License Number
            to review and triage incoming patient cases.
          </p>
          <button style={styles.primaryBtn} onClick={() => navigate("/login")}>
            Sign In with WHO License →
          </button>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────── */}
      <footer style={styles.footer}>
        <span style={styles.footerLogoMark}>✚</span>
        <span style={styles.footerText}>
          WHO Triage Intelligence Platform · For licensed medical professionals only · Demo environment
        </span>
      </footer>
    </div>
  );
}

const WHO_BLUE = "#0077B6";
const WHO_BLUE_DARK = "#005F8A";
const WHO_BLUE_LIGHT = "#E8F4FD";

const styles: Record<string, React.CSSProperties> = {
  page: {
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
    backgroundColor: "#ffffff",
    color: "#0f172a",
    minHeight: "100vh",
  },

  // Navbar
  navbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 48px",
    borderBottom: "1px solid #e2e8f0",
    backgroundColor: "#ffffff",
    position: "sticky" as const,
    top: 0,
    zIndex: 100,
  },
  navLogo: { display: "flex", alignItems: "center", gap: 10 },
  navLogoMark: { fontSize: 22, color: WHO_BLUE },
  navLogoText: { fontSize: 16, fontWeight: 700, color: "#0f172a", letterSpacing: "0.02em" },
  navSignInBtn: {
    backgroundColor: WHO_BLUE,
    color: "#ffffff",
    border: "none",
    borderRadius: 8,
    padding: "9px 20px",
    fontWeight: 600,
    fontSize: 14,
    cursor: "pointer",
  },

  // Hero
  hero: {
    textAlign: "center" as const,
    padding: "80px 24px 60px",
    maxWidth: 740,
    margin: "0 auto",
  },
  whoRibbon: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    backgroundColor: WHO_BLUE_LIGHT,
    color: WHO_BLUE_DARK,
    border: `1px solid ${WHO_BLUE}33`,
    borderRadius: 999,
    padding: "6px 16px",
    fontSize: 12,
    fontWeight: 600,
    marginBottom: 28,
    letterSpacing: "0.03em",
  },
  whoRibbonIcon: { fontSize: 14 },
  heroTitle: {
    fontSize: 52,
    fontWeight: 800,
    lineHeight: 1.15,
    color: "#0f172a",
    margin: "0 0 20px",
  },
  heroAccent: { color: WHO_BLUE },
  heroSubtitle: {
    fontSize: 18,
    color: "#475569",
    lineHeight: 1.7,
    margin: "0 0 36px",
    maxWidth: 560,
    marginLeft: "auto",
    marginRight: "auto",
  },
  heroBtns: { display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" as const },
  primaryBtn: {
    backgroundColor: WHO_BLUE,
    color: "#ffffff",
    border: "none",
    borderRadius: 10,
    padding: "14px 28px",
    fontWeight: 700,
    fontSize: 15,
    cursor: "pointer",
  },
  ghostBtn: {
    backgroundColor: "transparent",
    color: WHO_BLUE,
    border: `2px solid ${WHO_BLUE}`,
    borderRadius: 10,
    padding: "12px 28px",
    fontWeight: 600,
    fontSize: 15,
    cursor: "pointer",
    textDecoration: "none",
    display: "inline-flex",
    alignItems: "center",
  },

  // Stats strip
  statsStrip: {
    display: "flex",
    justifyContent: "center",
    flexWrap: "wrap" as const,
    gap: 0,
    backgroundColor: WHO_BLUE,
    padding: "32px 48px",
  },
  statItem: {
    textAlign: "center" as const,
    padding: "8px 48px",
    borderRight: "1px solid rgba(255,255,255,0.2)",
  },
  statValue: { display: "block", fontSize: 32, fontWeight: 800, color: "#ffffff" },
  statLabel: { display: "block", fontSize: 12, color: "rgba(255,255,255,0.75)", marginTop: 4, letterSpacing: "0.05em" },

  // Features
  featuresSection: {
    padding: "80px 48px",
    maxWidth: 1000,
    margin: "0 auto",
    textAlign: "center" as const,
  },
  sectionTitle: { fontSize: 32, fontWeight: 800, color: "#0f172a", margin: "0 0 12px" },
  sectionSubtitle: {
    fontSize: 16, color: "#64748b", maxWidth: 560, margin: "0 auto 48px",
    lineHeight: 1.6,
  },
  featuresGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: 24,
    textAlign: "left" as const,
  },
  featureCard: {
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 14,
    padding: "28px 24px",
  },
  featureIcon: { fontSize: 28, display: "block", marginBottom: 14 },
  featureTitle: { fontSize: 16, fontWeight: 700, color: "#0f172a", margin: "0 0 8px" },
  featureDesc: { fontSize: 13, color: "#64748b", lineHeight: 1.6, margin: 0 },

  // CTA
  ctaSection: {
    padding: "60px 24px",
    backgroundColor: "#f8fafc",
    borderTop: "1px solid #e2e8f0",
    borderBottom: "1px solid #e2e8f0",
  },
  ctaCard: {
    maxWidth: 600,
    margin: "0 auto",
    textAlign: "center" as const,
  },
  ctaTitle: { fontSize: 28, fontWeight: 800, color: "#0f172a", margin: "0 0 12px" },
  ctaSubtitle: { fontSize: 15, color: "#64748b", lineHeight: 1.7, margin: "0 0 28px" },

  // Footer
  footer: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    padding: "20px 48px",
    borderTop: "1px solid #e2e8f0",
    backgroundColor: "#ffffff",
  },
  footerLogoMark: { fontSize: 16, color: WHO_BLUE },
  footerText: { fontSize: 12, color: "#94a3b8" },
};
