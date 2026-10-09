 Commodity Derivatives Intelligence
Problem Statement
Build a data product using India’s public commodity futures data to identify and analyze relative pricing differences between contracts representing the same underlying metal.

MCX lists gold futures in multiple contract sizes, including GOLDM, GOLDTEN, GOLDGUINEA, and GOLDPETAL. Because these contracts represent the same underlying metal, their normalized prices should be closely related. The challenge is to understand, measure, and responsibly analyze the differences between them.

Possible Directions
Cross-Contract Relative Value
Normalize contract size, quotation base, and purity.
Identify when one contract appears unusually cheap or expensive relative to another.
Term Structure & Carry Analytics
Analyze the futures curve.
Separate mechanical roll-down toward expiry from genuine changes in the curve.
Walk-Forward Backtesting
Replay historical contracts day by day without look-ahead bias.
Account for transaction costs and thin-day liquidity.
Trader-Facing Intelligence
Build dashboards or alerts that highlight meaningful opportunities.
Keep alerts quiet when there is no meaningful signal.
Attribute performance to the strategy rather than simply to gold-price movement.
Contract Lifecycle Planning
Track listing dates, liquidity development, tender periods, and expiry.
Place every intended entry and exit inside the relevant contract calendar.
Data Sources
MCX Daily Bhavcopy: https://www.mcxindia.com/market-data/bhavcopy

MCX Gold Contract Specifications: https://www.mcxindia.com/products/bullion/gold

The daily Bhavcopy provides Symbol, Date, ExpiryDate, Open, High, Low, Close, Volume, and OpenInterest. The data is publicly available and does not require an API key.

Important Data Considerations
Validate the returned Date against the requested date. MCX may return the most recent available trading day for an unrecognized, holiday, malformed, or future date.
Requests use DD/MM/YYYY, while the response Date uses MM/DD/YYYY. ExpiryDate uses a compact format such as 04SEP2026, and Symbol values may be space-padded.
Track contracts by expiry_date rather than using a continuous near-month series. A near-month series changes contracts at expiry and can create artificial price jumps.
Settlement prices are official exchange settlement values and should not automatically be treated as executable fill prices, particularly for thin contracts.
Volume is not the same as market depth or available liquidity.
GOLDTEN is available only from its 2025 listing period onward; comparisons involving GOLDTEN therefore have a shorter history.
Contract Mechanics
Contract

Trading Unit

Price Quoted Per

Purity

Expiry Window

GOLDM

100 g

10 g

995

3rd–5th

GOLDTEN

10 g

10 g

999

27th–31st

GOLDGUINEA

8 g

8 g

999

27th–31st

GOLDPETAL

1 g

1 g

999

27th–31st

Challenge
Create a functional prototype that transforms exchange settlement data into a defensible analytical signal or intelligence product and validates the approach using unseen historical data. Where a strategy or signal is presented, report performance after relevant costs using the prices of the contracts actually held, and clearly separate strategy performance from the impact of the underlying gold price.

A rigorous demonstration that no persistent edge survives costs is also a valid analytical outcome. The objective is analytical rigor rather than generating a signal every day.