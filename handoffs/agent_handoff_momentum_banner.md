# AGENT HANDOFF SPECIFICATION
**Component:** Momentum Breadth & Market Health Banner  
**Target Location:** Empty sub-header slot (directly beneath the SPY/QQQ/IWM index ticker line and above the "LIVE GAINER SCREENER" section)  
**Parent Application:** TradeJournal Dashboard  

---

## 1. Context & Objectives
The goal is to populate the blank `flex` row space in the dashboard header with high-utility, real-time macro-momentum data. Because this dashboard serves a low-float, high-velocity momentum strategy (Ross Cameron style), broad market indexes (SPY/QQQ) are insufficient indicators of small-cap liquidity and retail participation. 

This new component must aggregate live data from the underlying PostgreSQL database to give the trader an instant, 3-second read on whether small-cap momentum has "juice" today.

---

## 2. UI & Aesthetic Requirements (Matching image_3b9d44.png)
* **Layout:** A single horizontal `flex` container matching the width of the main content cards. Divide the space into 4 evenly spaced KPI grid blocks or borderless micro-cards.
* **Typography:** Maintain the existing clean sans-serif stack. Use the crisp white styling for primary metrics and the muted gray/blue for labels.
* **Color-Coding (Badges):** * Match the bright green (`#22c55e` or similar active green seen on the "Market Open" badge) for bullish momentum triggers.
    * Use the existing warm orange/yellow tint (seen in the `RR` and `NNP` badges) for high-alert volatility metrics like active halts.
* **Responsiveness:** Elements should scale down gracefully or wrap on smaller viewports, though primary focus is a widescreen desktop dashboard.

---

## 3. Data Requirements & Backend Logic
The agent should implement four distinct data components within that row. Source these metrics by filtering the active market data stream using the criteria from the global **$2-$25 Filter** toggled in the UI.

### Block 1: Small-Cap Market Breadth (Advance/Decline)
* **Label:** Small-Cap A/D Ratio
* **Logic:** Query active tickers where Price is between $2 and $25 and Volume > 0.
* **Primary Stat:** Ratio format (e.g., `4.1 : 1` or `78 G / 19 R`).
* **Color Logic:** Text color turns bright green if the ratio is $> 3:1$ (indicating high systemic small-cap long interest).

### Block 2: Aggregated Relative Volume (RVOL) Factor
* **Label:** Top-5 Avg RVOL
* **Logic:** Take the top 5 gainers by `% Change` currently in the database, calculate their individual RVOL (Current Volume / Avg Historical Volume at this time of day), and average them.
* **Primary Stat:** Multiplier format (e.g., `6.4x`).
* **Subtext:** "High Liquidity Active" or "Low Liquidity/Dry" based on a threshold of $3.0x$.

### Block 3: Float Theme Identifier
* **Label:** Dominant Float Theme
* **Logic:** Look at the top 5 leading gainers. Determine if the majority of the float types fall under `Small (<2M)`, `Medium (2M-20M)`, or `Large (>20M)`. *(Matches the existing tag system in column 6 of the gainer screener).*
* **Primary Stat:** Dynamic Badge text (e.g., `MICRO-FLOAT (<2M)` or `MID-FLOAT`).
* **Value:** Instantly informs the trader if micro-floats are coiling or if the market is favoring slightly higher liquidity names.

### Block 4: Volatility & Circuit Breaker (Halt Tracker)
* **Label:** Active Volatility Halts
* **Logic:** Count the total number of LUDP (Limit Up/Limit Down) trading halts triggered in the last 60 minutes across the watch list / universe.
* **Primary Stat:** Count integer (e.g., `2 Halts Active`).
* **Subtext:** Ticker names of active halts in an inline micro-badge (e.g., `[DXST] [BJDX]`).

---

## 4. Implementation Instructions for the Agent
1.  Open the dashboard layout file containing the header structure.
2.  Locate the wrapper container sitting immediately under the `SPY / QQQ / IWM` ticker row.
3.  Inject a new component `<MomentumBreadthBanner/>`.
4.  Ensure state hooks tie directly into the existing web socket / live polling frequency (`auto-refresh 1m` or 15s interval as shown in **image_3b9d44.png**).
5.  Optimize the database queries running on the PostgreSQL backend to calculate these aggregates efficiently without blocking the primary live gainer table execution loop.
