// src/pages/LandingPage.tsx
// ──────────────────────────────────────────────────────────────
// Public-facing hospital landing page.
// Aesthetic: white + soft blue (#0ea5e9 family), spacious, clean.
// ──────────────────────────────────────────────────────────────

import { type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";

const BLUE = "#0ea5e9";
const BLUE_DARK = "#0284c7";
const BLUE_LIGHT = "#e0f2fe";
const BLUE_MID = "#38bdf8";
const SLATE = "#0f172a";
const SLATE_MID = "#334155";
const SLATE_LIGHT = "#64748b";
const WHITE = "#ffffff";
const GRAY_BG = "#f8fafc";

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div style={styles.root}>
      {/* ── Navigation ─────────────────────────────────────── */}
      <nav style={styles.nav}>
        <div style={styles.navInner}>
          <div style={styles.logoGroup}>
            <div style={styles.logoIcon}>✚</div>
            <span style={styles.logoText}>TeleHealth</span>
          </div>
          <div style={styles.navLinks}>
            <a href="#services" style={styles.navLink}>Services</a>
            <a href="#why" style={styles.navLink}>Why Us</a>
            <a href="#stats" style={styles.navLink}>Reach</a>
            <button style={styles.loginBtn} onClick={() => navigate("/login")}>
              Doctor Login
            </button>
          </div>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────────── */}
      <section style={styles.hero}>
        <div style={styles.heroContent}>
          <div style={styles.heroBadge}>WHO-Affiliated Telehealth Network</div>
          <h1 style={styles.heroTitle}>
            Quality Healthcare,<br />
            <span style={styles.heroAccent}>Wherever You Are</span>
          </h1>
          <p style={styles.heroSubtitle}>
            Connecting patients in underserved regions with licensed physicians
            through AI-assisted intake and real-time remote consultation.
          </p>
          <div style={styles.heroActions}>
            <button style={styles.ctaBtn} onClick={() => navigate("/login")}>
              Book Appointment
              <span style={styles.ctaArrow}>→</span>
            </button>
            <a href="#services" style={styles.learnMoreBtn}>
              Learn more
            </a>
          </div>
          <div style={styles.heroTrust}>
            <TrustBadge icon="🌍" label="140+ Countries" />
            <TrustBadge icon="👨‍⚕️" label="2,400+ Physicians" />
            <TrustBadge icon="⚡" label="24/7 Intake" />
          </div>
        </div>
        <div style={styles.heroIllustration}>
          <HeroCard />
        </div>
      </section>

      {/* ── Stats strip ────────────────────────────────────── */}
      <section id="stats" style={styles.statsStrip}>
        <StatItem value="98%" label="Patient Satisfaction" />
        <StatItem value="<4 min" label="Avg. Intake Time" />
        <StatItem value="140+" label="Countries Served" />
        <StatItem value="ISO 27001" label="Data Security" />
      </section>

      {/* ── Services ───────────────────────────────────────── */}
      <section id="services" style={styles.section}>
        <SectionHeader
          tag="Services"
          title="Comprehensive Remote Care"
          subtitle="AI-powered triage meets licensed medical expertise — available in any language, any timezone."
        />
        <div style={styles.serviceGrid}>
          <ServiceCard
            icon="📞"
            title="Phone Intake"
            description="Patients call in and receive AI-guided symptom collection before a physician reviews their case."
          />
          <ServiceCard
            icon="💬"
            title="SMS Consultation"
            description="Text-based intake for regions with limited voice infrastructure. Automatic language detection."
          />
          <ServiceCard
            icon="🩺"
            title="Physician Review"
            description="Board-certified doctors review cases within hours, providing treatment plans or referrals."
          />
          <ServiceCard
            icon="🔒"
            title="Privacy First"
            description="End-to-end encryption, jurisdiction-aware data residency, and full WHO compliance."
          />
        </div>
      </section>

      {/* ── Why Us ─────────────────────────────────────────── */}
      <section id="why" style={{ ...styles.section, backgroundColor: GRAY_BG }}>
        <SectionHeader
          tag="Why TeleHealth"
          title="Built for the World's Hardest Problems"
          subtitle="Most telehealth platforms are built for wealthy cities. We built ours for everyone else."
        />
        <div style={styles.whyGrid}>
          <WhyItem
            number="01"
            title="Tier-Aware Care"
            description="Our platform automatically adjusts treatment options based on local healthcare infrastructure — from full prescriptions in Tier 1 to guidance-only in Tier 4 regions."
          />
          <WhyItem
            number="02"
            title="AI Triage at Scale"
            description="LangGraph-powered intake workflows handle thousands of concurrent calls, extracting structured symptom data for physician review."
          />
          <WhyItem
            number="03"
            title="WHO-Verified Physicians"
            description="Every doctor on our platform holds a verified WHO license number. No exceptions."
          />
          <WhyItem
            number="04"
            title="Multilingual Support"
            description="Intake flows run in 60+ languages. Patients describe symptoms in their native tongue."
          />
        </div>
      </section>

      {/* ── CTA Banner ─────────────────────────────────────── */}
      <section style={styles.ctaBanner}>
        <h2 style={styles.ctaBannerTitle}>Ready to Provide Care Without Borders?</h2>
        <p style={styles.ctaBannerSub}>Join 2,400+ physicians already on the platform.</p>
        <button
          style={styles.ctaBannerBtn}
          onClick={() => navigate("/login")}
        >
          Access Doctor Portal
        </button>
      </section>

      {/* ── Footer ─────────────────────────────────────────── */}
      <footer style={styles.footer}>
        <div style={styles.footerInner}>
          <div style={styles.footerLogo}>
            <div style={styles.footerLogoIcon}>✚</div>
            <span style={styles.footerLogoText}>TeleHealth</span>
          </div>
          <p style={styles.footerText}>
            WHO-affiliated telehealth network serving patients in 140+ countries.
          </p>
          <p style={styles.footerDisclaimer}>
            This platform is for licensed medical professionals. Patient data is handled in accordance with applicable jurisdiction laws.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────

function TrustBadge({ icon, label }: { icon: string; label: string }) {
  return (
    <div style={styles.trustBadge}>
      <span style={styles.trustIcon}>{icon}</span>
      <span style={styles.trustLabel}>{label}</span>
    </div>
  );
}

function HeroCard() {
  return (
    <div style={styles.heroCard}>
      <div style={styles.heroCardHeader}>
        <div style={styles.heroCardDot} />
        <span style={styles.heroCardLabel}>Live Case Queue</span>
      </div>
      <CasePreview urgency="EMERGENCY" country="Kenya" time="Just now" />
      <CasePreview urgency="HIGH" country="Bangladesh" time="2 min ago" />
      <CasePreview urgency="MEDIUM" country="Bolivia" time="5 min ago" />
      <div style={styles.heroCardFooter}>
        <span style={styles.heroCardFooterText}>3 cases awaiting review</span>
        <button
          style={styles.heroCardFooterBtn}
          onClick={() => { /* demo */ }}
        >
          View Inbox
        </button>
      </div>
    </div>
  );
}

const URGENCY_COLORS: Record<string, { bg: string; text: string }> = {
  EMERGENCY: { bg: "#fee2e2", text: "#dc2626" },
  HIGH:      { bg: "#ffedd5", text: "#ea580c" },
  MEDIUM:    { bg: "#fef9c3", text: "#ca8a04" },
  LOW:       { bg: "#dcfce7", text: "#16a34a" },
};

function CasePreview({ urgency, country, time }: { urgency: string; country: string; time: string }) {
  const colors = URGENCY_COLORS[urgency] ?? URGENCY_COLORS["MEDIUM"]!;
  return (
    <div style={styles.casePreview}>
      <span style={{ ...styles.urgencyPill, backgroundColor: colors.bg, color: colors.text }}>
        {urgency}
      </span>
      <span style={styles.caseCountry}>{country}</span>
      <span style={styles.caseTime}>{time}</span>
    </div>
  );
}

function StatItem({ value, label }: { value: string; label: string }) {
  return (
    <div style={styles.statItem}>
      <div style={styles.statValue}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  );
}

function SectionHeader({ tag, title, subtitle }: { tag: string; title: string; subtitle: string }) {
  return (
    <div style={styles.sectionHeader}>
      <div style={styles.sectionTag}>{tag}</div>
      <h2 style={styles.sectionTitle}>{title}</h2>
      <p style={styles.sectionSubtitle}>{subtitle}</p>
    </div>
  );
}

function ServiceCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div style={styles.serviceCard}>
      <div style={styles.serviceIcon}>{icon}</div>
      <h3 style={styles.serviceTitle}>{title}</h3>
      <p style={styles.serviceDesc}>{description}</p>
    </div>
  );
}

function WhyItem({ number, title, description }: { number: string; title: string; description: string }) {
  return (
    <div style={styles.whyItem}>
      <div style={styles.whyNumber}>{number}</div>
      <h3 style={styles.whyTitle}>{title}</h3>
      <p style={styles.whyDesc}>{description}</p>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────
const styles: Record<string, CSSProperties> = {
  root: {
    fontFamily: "'Segoe UI', system-ui, -apple-system, sans-serif",
    backgroundColor: WHITE,
    color: SLATE,
    minHeight: "100vh",
    overflowX: "hidden",
  },

  // Nav
  nav: {
    position: "sticky",
    top: 0,
    zIndex: 100,
    backgroundColor: "rgba(255,255,255,0.95)",
    backdropFilter: "blur(8px)",
    borderBottom: "1px solid #e2e8f0",
    padding: "0 24px",
  },
  navInner: {
    maxWidth: 1140,
    margin: "0 auto",
    height: 64,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  logoGroup: { display: "flex", alignItems: "center", gap: 10 },
  logoIcon: {
    width: 36, height: 36, borderRadius: 10,
    backgroundColor: BLUE, color: WHITE,
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 18, fontWeight: 700,
  },
  logoText: { fontSize: 18, fontWeight: 700, color: SLATE, letterSpacing: "-0.01em" },
  navLinks: { display: "flex", alignItems: "center", gap: 32 },
  navLink: {
    color: SLATE_MID, textDecoration: "none", fontSize: 14,
    fontWeight: 500,
  },
  loginBtn: {
    backgroundColor: BLUE, color: WHITE, border: "none",
    borderRadius: 8, padding: "8px 18px", fontSize: 14,
    fontWeight: 600, cursor: "pointer",
  },

  // Hero
  hero: {
    maxWidth: 1140,
    margin: "0 auto",
    padding: "80px 24px 100px",
    display: "flex",
    alignItems: "center",
    gap: 60,
  },
  heroContent: { flex: 1 },
  heroBadge: {
    display: "inline-block",
    backgroundColor: BLUE_LIGHT,
    color: BLUE_DARK,
    borderRadius: 999,
    padding: "5px 14px",
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: "0.03em",
    marginBottom: 24,
  },
  heroTitle: {
    fontSize: 52,
    fontWeight: 800,
    lineHeight: 1.1,
    letterSpacing: "-0.03em",
    color: SLATE,
    margin: "0 0 20px",
  },
  heroAccent: { color: BLUE },
  heroSubtitle: {
    fontSize: 17,
    color: SLATE_LIGHT,
    lineHeight: 1.7,
    maxWidth: 480,
    margin: "0 0 36px",
  },
  heroActions: { display: "flex", alignItems: "center", gap: 20, marginBottom: 40 },
  ctaBtn: {
    backgroundColor: BLUE,
    color: WHITE,
    border: "none",
    borderRadius: 10,
    padding: "14px 28px",
    fontSize: 15,
    fontWeight: 700,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: 8,
    boxShadow: `0 4px 20px ${BLUE}44`,
  },
  ctaArrow: { fontSize: 18 },
  learnMoreBtn: {
    color: BLUE_DARK,
    textDecoration: "none",
    fontSize: 14,
    fontWeight: 600,
    borderBottom: `2px solid ${BLUE_MID}`,
    paddingBottom: 2,
  },
  heroTrust: { display: "flex", gap: 24 },
  trustBadge: { display: "flex", alignItems: "center", gap: 7 },
  trustIcon: { fontSize: 18 },
  trustLabel: { fontSize: 13, fontWeight: 600, color: SLATE_MID },

  // Hero card
  heroIllustration: { flex: "0 0 380px" },
  heroCard: {
    backgroundColor: WHITE,
    borderRadius: 18,
    border: "1px solid #e2e8f0",
    padding: 24,
    boxShadow: "0 20px 60px rgba(14,165,233,0.10), 0 2px 8px rgba(0,0,0,0.06)",
  },
  heroCardHeader: {
    display: "flex", alignItems: "center", gap: 8,
    marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid #f1f5f9",
  },
  heroCardDot: {
    width: 10, height: 10, borderRadius: "50%",
    backgroundColor: "#22c55e",
    boxShadow: "0 0 6px #22c55e88",
  },
  heroCardLabel: { fontSize: 13, fontWeight: 600, color: SLATE_MID },
  casePreview: {
    display: "flex", alignItems: "center", gap: 10,
    padding: "10px 0", borderBottom: "1px solid #f8fafc",
  },
  urgencyPill: {
    borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 700,
    minWidth: 80, textAlign: "center",
  },
  caseCountry: { flex: 1, fontSize: 13, color: SLATE_MID, fontWeight: 500 },
  caseTime: { fontSize: 12, color: SLATE_LIGHT },
  heroCardFooter: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    paddingTop: 16, marginTop: 4,
  },
  heroCardFooterText: { fontSize: 12, color: SLATE_LIGHT },
  heroCardFooterBtn: {
    backgroundColor: BLUE_LIGHT, color: BLUE_DARK,
    border: "none", borderRadius: 6, padding: "6px 12px",
    fontSize: 12, fontWeight: 600, cursor: "pointer",
  },

  // Stats strip
  statsStrip: {
    backgroundColor: SLATE,
    padding: "40px 24px",
    display: "flex",
    justifyContent: "center",
    gap: 80,
    flexWrap: "wrap",
  },
  statItem: { textAlign: "center" },
  statValue: { fontSize: 32, fontWeight: 800, color: WHITE, letterSpacing: "-0.02em" },
  statLabel: { fontSize: 13, color: "#94a3b8", marginTop: 4, fontWeight: 500 },

  // Section
  section: {
    padding: "88px 24px",
    backgroundColor: WHITE,
  },
  sectionHeader: { textAlign: "center", maxWidth: 600, margin: "0 auto 56px" },
  sectionTag: {
    display: "inline-block",
    color: BLUE,
    fontWeight: 700,
    fontSize: 12,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 36, fontWeight: 800, color: SLATE,
    letterSpacing: "-0.02em", lineHeight: 1.2, margin: "0 0 16px",
  },
  sectionSubtitle: { fontSize: 16, color: SLATE_LIGHT, lineHeight: 1.7, margin: 0 },

  // Service cards
  serviceGrid: {
    maxWidth: 1140,
    margin: "0 auto",
    display: "grid",
    gridTemplateColumns: "repeat(4, 1fr)",
    gap: 24,
  },
  serviceCard: {
    backgroundColor: WHITE,
    border: "1px solid #e2e8f0",
    borderRadius: 14,
    padding: "28px 24px",
    transition: "box-shadow 0.2s",
  },
  serviceIcon: { fontSize: 28, marginBottom: 16 },
  serviceTitle: { fontSize: 15, fontWeight: 700, color: SLATE, margin: "0 0 10px" },
  serviceDesc: { fontSize: 13, color: SLATE_LIGHT, lineHeight: 1.6, margin: 0 },

  // Why grid
  whyGrid: {
    maxWidth: 1140,
    margin: "0 auto",
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: 40,
  },
  whyItem: { paddingLeft: 24, borderLeft: `3px solid ${BLUE_LIGHT}` },
  whyNumber: {
    fontSize: 11, fontWeight: 800, color: BLUE,
    letterSpacing: "0.1em", marginBottom: 8,
  },
  whyTitle: { fontSize: 16, fontWeight: 700, color: SLATE, margin: "0 0 10px" },
  whyDesc: { fontSize: 14, color: SLATE_LIGHT, lineHeight: 1.7, margin: 0 },

  // CTA Banner
  ctaBanner: {
    backgroundColor: BLUE,
    padding: "72px 24px",
    textAlign: "center",
  },
  ctaBannerTitle: {
    fontSize: 34, fontWeight: 800, color: WHITE,
    letterSpacing: "-0.02em", margin: "0 0 12px",
  },
  ctaBannerSub: { fontSize: 16, color: "#bae6fd", margin: "0 0 32px" },
  ctaBannerBtn: {
    backgroundColor: WHITE,
    color: BLUE_DARK,
    border: "none",
    borderRadius: 10,
    padding: "14px 32px",
    fontSize: 15,
    fontWeight: 700,
    cursor: "pointer",
    boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
  },

  // Footer
  footer: {
    backgroundColor: SLATE,
    padding: "48px 24px",
  },
  footerInner: { maxWidth: 1140, margin: "0 auto" },
  footerLogo: { display: "flex", alignItems: "center", gap: 10, marginBottom: 16 },
  footerLogoIcon: {
    width: 32, height: 32, borderRadius: 8,
    backgroundColor: BLUE, color: WHITE,
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 16, fontWeight: 700,
  },
  footerLogoText: { fontSize: 16, fontWeight: 700, color: WHITE },
  footerText: { fontSize: 14, color: "#94a3b8", margin: "0 0 8px" },
  footerDisclaimer: { fontSize: 12, color: "#475569", margin: 0, maxWidth: 560, lineHeight: 1.6 },
};
