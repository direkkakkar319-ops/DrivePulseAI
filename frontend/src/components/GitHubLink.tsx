"use client";

// Repository link with a verified initial count refreshed from GitHub on page load.
import { useEffect, useState } from "react";
import { Github, Star } from "lucide-react";

export default function GitHubLink() {
  // Verified on 2026-09-12; retained if GitHub is temporarily unavailable.
  const [stars, setStars] = useState(1);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    async function refreshStars() {
      try {
        const response = await fetch(
          "https://api.github.com/repos/direkkakkar319-ops/DrivePulseAI",
          {
            signal: controller.signal,
            headers: { Accept: "application/vnd.github+json" },
          },
        );
        if (!response.ok) return;
        const data = await response.json();
        if (
          Number.isSafeInteger(data.stargazers_count) &&
          data.stargazers_count >= 0
        ) {
          setStars(data.stargazers_count);
        }
      } catch {
        // Keep the last verified count on offline or rate-limited visits.
      } finally {
        clearTimeout(timeout);
      }
    }
    void refreshStars();
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  return (
    <a
      className="github-nav"
      href="https://github.com/direkkakkar319-ops/DrivePulseAI"
      aria-label={`DrivePulse AI on GitHub, ${stars} ${stars === 1 ? "star" : "stars"}`}
    >
      <Github size={18} aria-hidden="true" />
      <span>GitHub</span>
      <span className="github-star">
        <Star size={14} aria-hidden="true" />
        <span>{stars.toLocaleString("en-US")}</span>
      </span>
    </a>
  );
}
