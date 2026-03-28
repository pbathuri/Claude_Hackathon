// src/components/ImageViewer.tsx
// ──────────────────────────────────────────────────────────────
// Displays images that patients submitted via SMS/text message.
// Features:
//   - Thumbnail grid with SMS source badge
//   - Click to open a lightbox/modal for full-size view
//   - Graceful fallback for broken/placeholder URLs
// ──────────────────────────────────────────────────────────────

import { useState } from "react";

interface ImageViewerProps {
  imageUrls: string[];
  /** Channel through which the images were received */
  intakeChannel?: "VOICE" | "SMS" | "COMBINED";
}

export default function ImageViewer({ imageUrls, intakeChannel = "SMS" }: ImageViewerProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [failedUrls, setFailedUrls] = useState<Set<string>>(new Set());

  if (imageUrls.length === 0) return null;

  const channelLabel =
    intakeChannel === "SMS"
      ? "SMS Message"
      : intakeChannel === "COMBINED"
      ? "SMS / Voice"
      : "Patient Upload";

  const handleImageError = (url: string) => {
    setFailedUrls((prev) => new Set(prev).add(url));
  };

  const openModal = (index: number) => setActiveIndex(index);
  const closeModal = () => setActiveIndex(null);
  const prevImage = () =>
    setActiveIndex((i) => (i !== null ? Math.max(0, i - 1) : null));
  const nextImage = () =>
    setActiveIndex((i) => (i !== null ? Math.min(imageUrls.length - 1, i + 1) : null));

  return (
    <>
      {/* ── Thumbnail grid ─────────────────────────────────── */}
      <div style={styles.grid}>
        {imageUrls.map((url, i) => {
          const isFailed = failedUrls.has(url);
          const filename = url.split("/").pop() ?? `image-${i + 1}`;

          return (
            <div
              key={i}
              style={styles.thumbnailWrapper}
              onClick={() => openModal(i)}
              title={`View ${filename}`}
            >
              {/* Source badge */}
              <span style={styles.sourceBadge}>
                📱 {channelLabel}
              </span>

              {/* Image or fallback */}
              {!isFailed ? (
                <img
                  src={url}
                  alt={`Patient image ${i + 1}`}
                  style={styles.thumbnail}
                  onError={() => handleImageError(url)}
                />
              ) : (
                <div style={styles.fallback}>
                  <span style={styles.fallbackIcon}>📷</span>
                  <span style={styles.fallbackLabel}>Image {i + 1}</span>
                  <span style={styles.fallbackFilename}>{filename}</span>
                </div>
              )}

              {/* Hover overlay */}
              <div style={styles.hoverOverlay}>
                <span style={styles.zoomIcon}>🔍 View</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Lightbox modal ─────────────────────────────────── */}
      {activeIndex !== null && (
        <div style={styles.modalBackdrop} onClick={closeModal}>
          <div
            style={styles.modalContent}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div style={styles.modalHeader}>
              <div style={styles.modalMeta}>
                <span style={styles.modalSourceBadge}>📱 Received via {channelLabel}</span>
                <span style={styles.modalCounter}>
                  {activeIndex + 1} / {imageUrls.length}
                </span>
              </div>
              <button style={styles.closeBtn} onClick={closeModal}>✕</button>
            </div>

            {/* Image display */}
            <div style={styles.modalImageArea}>
              {!failedUrls.has(imageUrls[activeIndex]) ? (
                <img
                  src={imageUrls[activeIndex]}
                  alt={`Patient image ${activeIndex + 1}`}
                  style={styles.modalImage}
                  onError={() => handleImageError(imageUrls[activeIndex])}
                />
              ) : (
                <div style={styles.modalFallback}>
                  <span style={styles.modalFallbackIcon}>📷</span>
                  <p style={styles.modalFallbackText}>Image not available</p>
                  <p style={styles.modalFallbackUrl}>
                    {imageUrls[activeIndex].split("/").pop()}
                  </p>
                </div>
              )}
            </div>

            {/* Navigation */}
            <div style={styles.modalNav}>
              <button
                style={styles.navBtn}
                onClick={prevImage}
                disabled={activeIndex === 0}
              >
                ← Previous
              </button>
              <span style={styles.modalFilename}>
                {imageUrls[activeIndex].split("/").pop()}
              </span>
              <button
                style={styles.navBtn}
                onClick={nextImage}
                disabled={activeIndex === imageUrls.length - 1}
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Styles ────────────────────────────────────────────────────
const styles: Record<string, React.CSSProperties> = {
  // Thumbnail grid
  grid: {
    display: "flex",
    flexWrap: "wrap",
    gap: 10,
  },
  thumbnailWrapper: {
    position: "relative",
    width: 130,
    height: 110,
    borderRadius: 10,
    overflow: "hidden",
    border: "1.5px solid #e2e8f0",
    cursor: "pointer",
    backgroundColor: "#f8fafc",
    flexShrink: 0,
  },
  sourceBadge: {
    position: "absolute",
    top: 6,
    left: 6,
    backgroundColor: "rgba(0,0,0,0.6)",
    color: "#fff",
    fontSize: 9,
    fontWeight: 600,
    padding: "2px 6px",
    borderRadius: 999,
    zIndex: 2,
    backdropFilter: "blur(2px)",
    whiteSpace: "nowrap",
  },
  thumbnail: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    display: "block",
  },
  fallback: {
    width: "100%",
    height: "100%",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 3,
    padding: 8,
  },
  fallbackIcon: { fontSize: 24 },
  fallbackLabel: { fontSize: 11, fontWeight: 600, color: "#64748b" },
  fallbackFilename: { fontSize: 9, color: "#cbd5e1", wordBreak: "break-all", textAlign: "center" },
  hoverOverlay: {
    position: "absolute",
    inset: 0,
    backgroundColor: "rgba(0,119,182,0.75)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    opacity: 0,
    transition: "opacity 0.2s",
    // CSS hover handled via JS onMouseEnter/Leave or CSS class — use a simple hover trick
  },
  zoomIcon: { color: "#fff", fontSize: 13, fontWeight: 600 },

  // Modal
  modalBackdrop: {
    position: "fixed",
    inset: 0,
    backgroundColor: "rgba(0,0,0,0.8)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
    padding: 24,
  },
  modalContent: {
    backgroundColor: "#ffffff",
    borderRadius: 16,
    maxWidth: 720,
    width: "100%",
    maxHeight: "90vh",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    boxShadow: "0 32px 80px rgba(0,0,0,0.5)",
  },
  modalHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 20px",
    borderBottom: "1px solid #e2e8f0",
  },
  modalMeta: { display: "flex", alignItems: "center", gap: 12 },
  modalSourceBadge: {
    backgroundColor: "#E8F4FD",
    color: "#0077B6",
    borderRadius: 999,
    padding: "3px 10px",
    fontSize: 11,
    fontWeight: 600,
    border: "1px solid #0077B633",
  },
  modalCounter: { fontSize: 12, color: "#94a3b8", fontWeight: 600 },
  closeBtn: {
    background: "none",
    border: "1px solid #e2e8f0",
    borderRadius: 6,
    padding: "4px 10px",
    cursor: "pointer",
    fontSize: 13,
    color: "#64748b",
  },
  modalImageArea: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#f8fafc",
    minHeight: 300,
    overflow: "auto",
    padding: 16,
  },
  modalImage: {
    maxWidth: "100%",
    maxHeight: "60vh",
    objectFit: "contain",
    borderRadius: 8,
    boxShadow: "0 4px 16px rgba(0,0,0,0.15)",
  },
  modalFallback: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 8,
    padding: 40,
  },
  modalFallbackIcon: { fontSize: 48 },
  modalFallbackText: { fontSize: 14, color: "#64748b", margin: 0, fontWeight: 600 },
  modalFallbackUrl: { fontSize: 11, color: "#94a3b8", margin: 0, fontFamily: "monospace" },
  modalNav: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 20px",
    borderTop: "1px solid #e2e8f0",
  },
  navBtn: {
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 8,
    padding: "7px 14px",
    cursor: "pointer",
    fontSize: 13,
    color: "#475569",
    fontWeight: 500,
  },
  modalFilename: { fontSize: 11, color: "#94a3b8", fontFamily: "monospace" },
};
