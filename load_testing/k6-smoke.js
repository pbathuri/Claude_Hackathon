/**
 * Smoke script for k6 — install k6 locally, then:
 *   k6 run -e BASE_URL=https://your-api.example.com load_testing/k6-smoke.js
 */
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 2,
  duration: "30s",
};

const BASE = __ENV.BASE_URL || "http://localhost:8000";

export default function () {
  const res = http.get(`${BASE}/health-check`);
  check(res, { "health 200": (r) => r.status === 200 });
  sleep(1);
}
