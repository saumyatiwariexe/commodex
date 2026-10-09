export const MOCK_SPREAD_DATA = Array.from({ length: 60 }).map((_, i) => {
  const date = new Date(2026, 0, i + 1);
  const basePx = 6000 + Math.sin(i / 5) * 50;
  const spread = Math.cos(i / 3) * 15 + (i > 40 && i < 45 ? 40 : 0); // spike at day 40
  const zScore = (spread - 5) / 10;
  
  return {
    date: date.toISOString().split('T')[0],
    px_a: basePx + spread,
    px_b: basePx,
    raw_spread: spread,
    carry_adj_spread: spread * 0.8,
    z_score: zScore,
    is_tender: i > 55,
    is_thin: i > 20 && i < 25,
  };
});
