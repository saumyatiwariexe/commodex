export const MOCK_TERM_STRUCTURE = Array.from({ length: 60 }).map((_, dateIndex) => {
  const date = new Date(2026, 0, dateIndex + 1);
  const basePrice = 6000 + Math.sin(dateIndex / 10) * 100;
  
  // Curve shape: typically contango (upward sloping), occasionally backwardation
  const isBackwardation = dateIndex > 30 && dateIndex < 40;
  
  const curve = Array.from({ length: 6 }).map((_, expiryIndex) => {
    const daysToExpiry = (expiryIndex + 1) * 30;
    // Base cost of carry is ~5% annualized -> ~0.013% per day
    const carryAmount = daysToExpiry * basePrice * 0.00013;
    const curveValue = isBackwardation ? -carryAmount * 0.5 : carryAmount;
    
    return {
      expiry_months: expiryIndex + 1,
      name: `Month ${expiryIndex + 1}`,
      GOLDM: basePrice + curveValue,
      GOLDPETAL: basePrice + curveValue + (Math.random() * 5 - 2.5),
      GOLDGUINEA: basePrice + curveValue + (Math.random() * 8 - 4),
    };
  });
  
  return {
    date: date.toISOString().split('T')[0],
    curve
  };
});
