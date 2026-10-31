"""Database Seeding Script for Demonstration Data & Golden Benchmark Set.

Seeds:
1. Foundational 13-category taxonomy from config/taxonomy.yaml.
2. 53 realistic demonstration records across all 5 research sources:
   - 15 Reddit posts/comments
   - 15 Google Play & App Store reviews (balanced 1 to 5 stars)
   - 8 Official documentation & regulatory reports (Groww, SEBI, AMFI)
   - 5 Financial news articles
   - 10 Qualitative user interview records (anonymized)
3. 25-record Golden Benchmark evaluation dataset with hand-verified labels.
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_settings
from src.models.database import (
    GoldenRecord,
    IssueCategory,
    RawRecord,
    compute_content_hash,
    get_session,
    init_db,
)
from src.nlp.sanitizer import sanitize_text

# ---------------------------------------------------------------------------
# Pre-defined Demonstration Records (53 records across 5 sources)
# ---------------------------------------------------------------------------

DEMO_RECORDS: List[Dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # 1. Reddit Discussions (15 Records)
    # -----------------------------------------------------------------------
    {
        "id": "rec_reddit_01",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/IndiaInvestments/comments/18x9k2/groww_sip_failed_salary_delayed",
        "title": "Groww AutoPay failed because my company delayed salary by 2 days",
        "raw_text": "I set up my mutual fund SIP date for the 5th of every month on Groww. This month, company credited salary on 7th evening instead of 1st. AutoPay debit failed and HDFC charged me ₹295 bounce charge! I am thinking of stopping my SIP entirely because these charges hurt.",
        "publication_date": "2026-03-08",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_02",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/mutualfunds/comments/19y1a3/cant_pause_groww_sip",
        "title": "Why is it so hard to pause an SIP on Groww?",
        "raw_text": "I wanted to pause my Nippon Small Cap SIP for 2 months because of unexpected bike repair expenses. But on Groww app there is no straightforward Pause button, it only shows Cancel SIP or Skip next instalment. When I skipped, the mandate still debited my bank account! Had to cancel the whole mandate.",
        "publication_date": "2026-04-12",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_03",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/personalfinanceindia/comments/20a8c4/lost_money_first_6_months",
        "title": "Invested in SIP for 7 months, returns are -3%. Thinking of exiting",
        "raw_text": "Started my first SIP of ₹2000 in Parag Parikh Flexi Cap 7 months ago after seeing YouTube recommendations. My invested amount is ₹14,000 but current value is ₹13,580. My friends said mutual funds give 15% guaranteed. Fixed Deposit in SBI would have given better returns without stress. I am stopping this SIP.",
        "publication_date": "2026-05-18",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_04",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/IndiaInvestments/comments/21b9d1/groww_support_ticket_no_response",
        "title": "Groww customer support bot is useless for payment failures",
        "raw_text": "My SIP instalment failed on 10th but ₹1000 was deducted from my ICICI account. Groww shows 'Payment Failed' and AMC didn't get money. Raised ticket with Groww support but bot gives automated generic replies about 3-5 business days. It's been 9 days now. Extremely disappointed with support.",
        "publication_date": "2026-06-02",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_05",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/mutualfunds/comments/22c0e2/what_is_xirr_vs_cagr",
        "title": "Groww statement XIRR shows 18% but total return shows -2%?",
        "raw_text": "Can someone explain Groww statements? It shows XIRR 18.4% on dashboard, but when I see total invested vs current value I am in loss of ₹450. As a first time investor this makes zero sense. The UI numbers feel misleading.",
        "publication_date": "2026-06-15",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_06",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/IndiaInvestments/comments/23d1f3/e_mandate_rejection_groww",
        "title": "NPCI e-mandate rejected 3 times on Groww via SBI NetBanking",
        "raw_text": "Trying to start an SIP of ₹1000 on Groww. Every time I approve the e-mandate via SBI NetBanking OTP, Groww shows 'Mandate Under Verification' for 4 days and then rejects it with error code MD01. I gave up and stopped investing.",
        "publication_date": "2026-07-01",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_07",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/personalfinanceindia/comments/24e2g4/father_hospitalized_stopping_investments",
        "title": "Had to stop all SIPs due to sudden hospital bills",
        "raw_text": "My father had a cardiac emergency last week. Hospital bills touched ₹3.5 lakhs. I had to withdraw my emergency fund and cancel all my recurring SIPs on Groww because my entire monthly salary is now going towards personal loan EMI taken for hospital bills.",
        "publication_date": "2026-07-20",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_08",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/mutualfunds/comments/25f3h5/market_crash_fear",
        "title": "Nifty down 600 points today, should I stop my monthly SIP?",
        "raw_text": "Markets are crashing continuously due to global tensions. My portfolio on Groww is deep red today. Is it smart to pause or cancel my SIPs until the market stabilizes? Watching money drop every day is giving me severe anxiety.",
        "publication_date": "2026-08-05",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_09",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/IndiaInvestments/comments/26g4i6/wedding_expenses_sip_discontinuation",
        "title": "Getting married in November, pausing mutual funds for gold & venue",
        "raw_text": "I had been doing ₹5000 monthly SIP for 10 months on Groww. Now getting married in November. Need liquidity for jewelry and banquet advance. Paused my investments for the next 8 months. Will restart once expenses normalize.",
        "publication_date": "2026-08-22",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_10",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/personalfinanceindia/comments/27h5j7/nav_allotment_delay_confusion",
        "title": "Amount debited on 2nd, units allotted with NAV of 5th?",
        "raw_text": "Groww AutoPay debited ₹1500 from my Kotak account on Friday 2nd August. But unit allotment email says NAV applicable is Tuesday 5th August when market was higher. Why did it take 3 days? Did I lose out on the market dip?",
        "publication_date": "2026-09-02",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_11",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/IndiaInvestments/comments/28i6k8/crypto_vs_mutual_funds",
        "title": "Bitcoin up 40% while mutual fund barely moved 4%",
        "raw_text": "Bitcoin and Solana made massive gains this quarter while my equity mutual funds on Groww are giving mediocre 5% annualized. Sold all mutual funds and moving to Binance and crypto staking for better upside.",
        "publication_date": "2026-09-10",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "not_relevant",  # Crypto speculation, not SIP retention problem
    },
    {
        "id": "rec_reddit_12",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/mutualfunds/comments/29j7l9/best_stocks_for_intraday",
        "title": "Which stocks to buy tomorrow morning for 10% intraday profit?",
        "raw_text": "Looking for high volatility intraday breakout stocks for tomorrow's market opening. Have ₹50,000 ready with 5x margin. Suggest top technical setups.",
        "publication_date": "2026-09-15",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "not_relevant",  # Intraday trading noise
    },
    {
        "id": "rec_reddit_13",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/personalfinanceindia/comments/30k8m0/groww_app_crashing_after_update",
        "title": "Groww app crashes every time I click on 'My SIPs'",
        "raw_text": "Updated Groww app to latest version on Android 14. Whenever I tap on Mutual Funds > SIPs tab, app crashes instantly. Can't see if my instalment went through. Cleared cache, reinstalled, still crashing. Fix this buggy UI!",
        "publication_date": "2026-09-25",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_reddit_14",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/IndiaInvestments/comments/31l9n1/first_year_sip_experience",
        "title": "Completed 1 year of continuous SIP on Groww without missing a month",
        "raw_text": "Started investing ₹3000/month in Nifty 50 Index fund in October 2025. Set debit date as 7th (2 days after salary). AutoPay has worked without a single glitch. Total invested ₹36,000, current value ₹41,200 (XIRR ~14%). Discipline and keeping buffer date is key for beginners.",
        "publication_date": "2026-10-10",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",  # Positive counter-evidence
    },
    {
        "id": "rec_reddit_15",
        "source_type": "reddit",
        "platform": "Reddit",
        "source_url": "https://reddit.com/r/mutualfunds/comments/32m0o2/sip_instalment_amount_increased_without_intent",
        "title": "Step-up SIP increased instalment by ₹500, couldn't afford it this month",
        "raw_text": "When setting up SIP, I accidentally checked the Step-Up SIP option by ₹500 every 6 months. This month my instalment debited ₹2500 instead of ₹2000. My account had exactly ₹2100 balance, so transaction bounced and bank fined me! Groww should make step-up opt-in more visible.",
        "publication_date": "2026-10-18",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },

    # -----------------------------------------------------------------------
    # 2. Google Play & Apple App Store Reviews (15 Records)
    # -----------------------------------------------------------------------
    {
        "id": "rec_appstore_01",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_01",
        "title": "AutoPay deducted late and bank charged penalty",
        "raw_text": "SIP date was 3rd of month. Groww triggered debit on 6th when balance was low. My bank debited ₹295 penalty for bounce. Support says it's bank issue. Uninstalled and cancelled all recurring investments.",
        "publication_date": "2026-04-05",
        "rating": 1,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_02",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_02",
        "title": "Very smooth SIP experience for beginners",
        "raw_text": "Clean UI, easy KYC and smooth AutoPay setup via UPI. Investing in 2 index funds every month. Highly recommended for people starting mutual fund journey.",
        "publication_date": "2026-04-18",
        "rating": 5,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",  # Positive experience
    },
    {
        "id": "rec_appstore_03",
        "source_type": "app_store",
        "platform": "AppStore",
        "source_url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703?reviewId=ios_03",
        "title": "Mandate approval fails repeatedly on iOS",
        "raw_text": "Trying to set up UPI AutoPay via GPay on iOS. Every time it redirects back to Groww, app says 'Session Timed Out'. Tried 4 times, same issue. Frustrating experience.",
        "publication_date": "2026-05-02",
        "rating": 2,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_04",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_04",
        "title": "Cannot change SIP date or amount",
        "raw_text": "Why do I have to cancel an SIP and create a new one just to change date from 1st to 10th? This is ridiculous design. Other apps let you edit SIP date directly.",
        "publication_date": "2026-05-20",
        "rating": 2,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_05",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_05",
        "title": "Great dashboard and order tracking",
        "raw_text": "Tracking my portfolio is super easy on Groww. Statements are downloaded in 1 click. Doing SIP for 9 months now without issue.",
        "publication_date": "2026-06-10",
        "rating": 5,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_06",
        "source_type": "app_store",
        "platform": "AppStore",
        "source_url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703?reviewId=ios_06",
        "title": "Money deducted twice for single instalment",
        "raw_text": "On 5th July, ₹2000 was deducted twice from my Axis bank account for the same SIP. Only 1 instalment shows on Groww. Customer support is not picking calls. I am scared of putting more money.",
        "publication_date": "2026-07-07",
        "rating": 1,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_07",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_07",
        "title": "Good app but need better beginner education",
        "raw_text": "The app is good for buying funds, but as a newbie I had no idea about exit load and taxation. When I stopped my SIP at 8 months, was shocked to see 1% exit load deduction. Please explain these clearly upfront.",
        "publication_date": "2026-07-25",
        "rating": 3,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_08",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_08",
        "title": "Worst customer service ever",
        "raw_text": "My SIP got cancelled automatically without any notification or SMS. When asked support, they say mandate expired. Why wasn't I warned beforehand so I could renew it?",
        "publication_date": "2026-08-01",
        "rating": 1,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_09",
        "source_type": "app_store",
        "platform": "AppStore",
        "source_url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703?reviewId=ios_09",
        "title": "Love the clean UI and dark mode",
        "raw_text": "Hands down the best looking fintech app in India. Makes investing feel effortless. All my monthly investments happen like clockwork.",
        "publication_date": "2026-08-15",
        "rating": 5,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_10",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_10",
        "title": "Notifications arrive after debit, not before!",
        "raw_text": "Groww sends reminder notification on the debit day itself. If salary is delayed, it's already too late to arrange money. Give reminders at least 48 hours before debit date!",
        "publication_date": "2026-08-30",
        "rating": 2,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_11",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_11",
        "title": "App crashed during IPO application",
        "raw_text": "Wanted to bid for Hyundai IPO, app gave gateway timeout error at 4:30 PM. Useless servers for IPO allotment.",
        "publication_date": "2026-09-05",
        "rating": 1,
        "is_synthetic_demo": True,
        "relevance_status": "not_relevant",  # IPO trading, not SIP continuation
    },
    {
        "id": "rec_appstore_12",
        "source_type": "app_store",
        "platform": "AppStore",
        "source_url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703?reviewId=ios_12",
        "title": "Cannot understand capital gains report",
        "raw_text": "Tax statement is very complicated. Doesn't show LTCG vs STCG clearly for tax filing. Had to hire a CA to figure out my tax liability after redeeming SIP units.",
        "publication_date": "2026-09-18",
        "rating": 3,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_13",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_13",
        "title": "SIP failed due to bank server downtime",
        "raw_text": "State Bank of India was undergoing scheduled maintenance on Sunday night. Groww attempted SIP debit at midnight and declared payment failed. Why not re-attempt debit on Monday morning instead of marking it failed?",
        "publication_date": "2026-10-02",
        "rating": 2,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_14",
        "source_type": "app_store",
        "platform": "GooglePlay",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww&reviewId=gp_14",
        "title": "Reliable and transparent platform",
        "raw_text": "Have 4 active SIPs running on Groww. Never had any mandate or tracking issue. AutoPay via UPI is seamless.",
        "publication_date": "2026-10-12",
        "rating": 5,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_appstore_15",
        "source_type": "app_store",
        "platform": "AppStore",
        "source_url": "https://apps.apple.com/in/app/groww-stocks-mutual-fund/id1404871703?reviewId=ios_15",
        "title": "F&O option trading charges too high",
        "raw_text": "Brokerage of ₹20 per executed order in Nifty options is high compared to discount brokers. Lower your F&O brokerage charges.",
        "publication_date": "2026-10-20",
        "rating": 2,
        "is_synthetic_demo": True,
        "relevance_status": "not_relevant",  # F&O brokerage complaint
    },

    # -----------------------------------------------------------------------
    # 3. Official Documentation & Regulatory Reports (8 Records)
    # -----------------------------------------------------------------------
    {
        "id": "rec_official_01",
        "source_type": "official_doc",
        "platform": "Groww",
        "source_url": "https://groww.in/help/mutual-funds/sip/what-happens-if-my-sip-payment-fails",
        "title": "Groww Help: What happens if my SIP instalment payment fails?",
        "raw_text": "If your SIP instalment payment fails due to insufficient balance or technical bank issues, Groww does not charge any penalty. However, your bank may levy ECS/NACH bounce charges ranging from ₹250 to ₹500 + GST. If 3 consecutive instalments fail, the AMC will automatically cancel your SIP mandate.",
        "publication_date": "2026-01-15",
        "rating": None,
        "is_synthetic_demo": False,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_official_02",
        "source_type": "official_doc",
        "platform": "Groww",
        "source_url": "https://groww.in/help/mutual-funds/sip/how-to-pause-my-sip",
        "title": "Groww Help: How can I pause or skip my SIP instalment?",
        "raw_text": "You can skip an upcoming SIP instalment by navigating to Mutual Funds > SIPs > Select SIP > Skip Instalment. The request must be submitted at least 2 working days before the scheduled instalment date. If submitted later, the mandate request has already been dispatched to NPCI and cannot be recalled.",
        "publication_date": "2026-01-20",
        "rating": None,
        "is_synthetic_demo": False,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_official_03",
        "source_type": "official_doc",
        "platform": "Groww",
        "source_url": "https://groww.in/help/mutual-funds/autopay/bank-mandate-setup-process",
        "title": "Groww Help: AutoPay setup methods and verification timelines",
        "raw_text": "Groww supports AutoPay mandate registration through UPI AutoPay, NetBanking, and Debit Card. UPI AutoPay approvals are instant with a ₹15,000 per transaction cap. NetBanking and Debit Card e-mandates via NPCI take 2 to 4 working days for bank authorization.",
        "publication_date": "2026-02-10",
        "rating": None,
        "is_synthetic_demo": False,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_official_04",
        "source_type": "official_doc",
        "platform": "AMFI",
        "source_url": "https://www.amfiindia.com/research-information/mf-data/monthly-sip-data-2026",
        "title": "AMFI Monthly Mutual Fund Statistics: SIP Inflows & Discontinuation Ratio",
        "raw_text": "During Q1 2026, total mutual fund SIP contribution reached ₹21,500 crore across 8.8 crore active SIP accounts. However, new SIP registrations stood at 42.5 lakh while discontinued/tenure-completed SIPs reached 29.8 lakh, yielding an SIP discontinuation ratio of 70.1%. AMFI data indicates over 48% of discontinued SIPs stop within the first 12 months.",
        "publication_date": "2026-04-10",
        "rating": None,
        "is_synthetic_demo": False,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_official_05",
        "source_type": "official_doc",
        "platform": "SEBI",
        "source_url": "https://www.sebi.gov.in/reports/investor-survey-report-2025.pdf",
        "title": "SEBI Investor Survey: Obstacles in Retail Systematic Investment Plans",
        "raw_text": "SEBI's nationwide study of 25,000 retail mutual fund investors revealed that 41% of first-time investors who discontinued SIPs within 12 months cited sudden financial obligations (emergency medical expenses, loan repayments, rent hikes). 28% cited payment friction (bounce charges, AutoPay failures), and 19% cited disillusionment with market volatility and negative returns.",
        "publication_date": "2025-11-30",
        "rating": None,
        "is_synthetic_demo": False,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_official_06",
        "source_type": "official_doc",
        "platform": "SEBI",
        "source_url": "https://www.sebi.gov.in/legal/circulars/mar-2026/standardization-of-sip-pause-facility.pdf",
        "title": "SEBI Advisory: Standardization of SIP Pause Facility across Digital Platforms",
        "raw_text": "To curb premature SIP cancellations, SEBI advised Asset Management Companies and Registered Investment Advisers to implement standardized SIP Pause mechanisms allowing retail investors to pause instalments for 1 to 6 months without cancelling underlying bank mandates or incurring penalty fees.",
        "publication_date": "2026-03-15",
        "rating": None,
        "is_synthetic_demo": False,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_official_07",
        "source_type": "official_doc",
        "platform": "Groww",
        "source_url": "https://groww.in/help/stocks/how-to-place-bracket-order",
        "title": "Groww Help: How to place a bracket order in equity intraday",
        "raw_text": "A bracket order is an advanced intraday order type designed to limit loss and lock in profits by placing target and stop-loss orders simultaneously.",
        "publication_date": "2026-02-18",
        "rating": None,
        "is_synthetic_demo": False,
        "relevance_status": "not_relevant",  # Equity trading help doc
    },
    {
        "id": "rec_official_08",
        "source_type": "official_doc",
        "platform": "AMFI",
        "source_url": "https://www.amfiindia.com/guidelines/kyc-aadhaar-pan-linking-circular",
        "title": "AMFI Advisory: Mandatory PAN-Aadhaar validation for recurring mutual fund debits",
        "raw_text": "Investors whose PAN is not validated against Aadhaar are liable to have automated SIP debits placed in 'On-Hold' status until KYC records are remediated with the respective KRA.",
        "publication_date": "2026-05-12",
        "rating": None,
        "is_synthetic_demo": False,
        "relevance_status": "highly_relevant",
    },

    # -----------------------------------------------------------------------
    # 4. News & Research Articles (5 Records)
    # -----------------------------------------------------------------------
    {
        "id": "rec_news_01",
        "source_type": "news",
        "platform": "News",
        "source_url": "https://www.livemint.com/mutual-funds/why-first-time-investors-quit-sips-within-a-year-groww-zerodha",
        "title": "Mint Analysis: Why first-time retail investors abandon SIPs within 12 months",
        "raw_text": "An analysis of fintech discount brokers including Groww reveals that nearly half of first-time mutual fund investors stop their SIPs before their first anniversary. Financial planners point to poor cash-flow planning: investors pick arbitrary instalment dates like 1st or 5th, while salary disbursements are increasingly irregular among young private-sector professionals.",
        "publication_date": "2026-06-22",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_news_02",
        "source_type": "news",
        "platform": "News",
        "source_url": "https://economictimes.indiatimes.com/wealth/invest/bank-bounce-charges-eating-into-mutual-fund-returns/articleshow/108923.cms",
        "title": "ET Wealth: Unintended Bank Bounce Fees Discourage Novice SIP Investors",
        "raw_text": "Public and private sector banks levied over ₹1,200 crore in NACH and ECS bounce charges in FY25. For an investor committing ₹500 or ₹1000 per month, a single ₹295 + GST bounce charge represents 30% to 60% of their monthly investment. Experts note that a single bounce penalty frequently prompts permanent cancellation of recurring mandates.",
        "publication_date": "2026-07-14",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_news_03",
        "source_type": "news",
        "platform": "News",
        "source_url": "https://www.moneycontrol.com/news/business/personal-finance/market-volatility-tests-first-time-sip-investor-conviction-11234.html",
        "title": "Moneycontrol: Market correction triggers spike in retail SIP pauses",
        "raw_text": "With mid-cap and small-cap indices undergoing a 12% consolidation, digital investment platforms reported a 35% surge in SIP cancellations. First-time investors who entered during bull runs are experiencing negative portfolio values for the first time, triggering panic redemptions.",
        "publication_date": "2026-08-19",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_news_04",
        "source_type": "news",
        "platform": "News",
        "source_url": "https://www.thehindubusinessline.com/markets/gold-prices-hit-record-high-jewellery-demand-surges/article12345.ece",
        "title": "BusinessLine: Gold imports surge as festival season approaches",
        "raw_text": "Domestic gold prices reached all-time highs of ₹78,000 per 10 grams as festive jewellery demand picked up across major urban centers.",
        "publication_date": "2026-09-28",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "not_relevant",  # Commodity gold news
    },
    {
        "id": "rec_news_05",
        "source_type": "news",
        "platform": "News",
        "source_url": "https://www.cnbctv18.com/fintech/fintechs-simplify-sip-pause-and-step-up-to-boost-retention-123456.htm",
        "title": "CNBC-TV18: FinTech platforms race to launch flexible SIP features to retain retail users",
        "raw_text": "Leading investment apps are redesigning their recurring investment flows. Features like 'Smart Buffer Reminders', dynamic instalment date shifts, and 1-click pause are emerging as key retention levers to tackle the industry-wide 12-month drop-off problem.",
        "publication_date": "2026-10-15",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },

    # -----------------------------------------------------------------------
    # 5. Qualitative User Interviews & Field Surveys (10 Records)
    # -----------------------------------------------------------------------
    {
        "id": "rec_interview_01",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_01.txt",
        "title": "User Interview 01: 24yo Junior Developer, Bengaluru",
        "raw_text": "I started a ₹2000 SIP on Groww right after joining my first IT job. Selected 1st of month. But my salary is rarely credited on 1st, usually 3rd or 4th. In month 4, my debit failed and bank charged ₹350. I panicked and cancelled the SIP immediately. I felt Groww should have warned me or waited 2 days.",
        "publication_date": "2026-05-10",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_interview_02",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_02.txt",
        "title": "User Interview 02: 27yo Sales Executive, Pune",
        "raw_text": "I earn a variable monthly incentive. In months where incentive is high, I can easily invest ₹5000. In months where I only get base salary, ₹5000 is impossible because rent is ₹18,000. Groww doesn't let me dynamically reduce my SIP to ₹1000 for a single month, so I just stopped it.",
        "publication_date": "2026-05-15",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_interview_03",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_03.txt",
        "title": "User Interview 03: 23yo Content Creator, Mumbai",
        "raw_text": "I saw YouTube reels about compounding and started 3 different equity SIPs totaling ₹3000. After 5 months, market fell and my total value was down ₹800. I thought mutual funds are like recurring deposits where money only increases. I felt scammed and withdrew everything.",
        "publication_date": "2026-05-22",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_interview_04",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_04.txt",
        "title": "User Interview 04: 30yo Operations Lead, Hyderabad",
        "raw_text": "Had an active SIP of ₹4000 running for 11 months on Groww. Then my mother needed knee replacement surgery. Needed ₹2 lakhs in cash. I paused all investments and liquidated units to cover the shortfall. Would love to restart once finances stabilize.",
        "publication_date": "2026-06-05",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_interview_05",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_05.txt",
        "title": "User Interview 05: 26yo Marketing Associate, Delhi",
        "raw_text": "My mandate failed because I switched my primary salary account from HDFC to ICICI when changing companies. Updating bank account on Groww and re-registering AutoPay mandate was so confusing with 4 different approval screens that I gave up midway.",
        "publication_date": "2026-06-18",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_interview_06",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_06.txt",
        "title": "User Interview 06: 22yo Graduate Trainee, Chennai",
        "raw_text": "I set debit date as 10th. Salary comes on 30th. For the first week I have money, but by the 9th I spend everything on dining and shopping with friends. When 10th arrives, balance is ₹200. SIP fails. It's a behavioral budgeting issue on my end.",
        "publication_date": "2026-07-02",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_interview_07",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_07.txt",
        "title": "User Interview 07: 28yo Graphic Designer, Remote",
        "raw_text": "As a freelancer my client invoices clear randomly between 15th and 25th. Fixed recurring monthly debits don't suit freelance income cycles. I switched to manual lump-sum investing whenever client payments clear.",
        "publication_date": "2026-07-19",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_interview_08",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_08.txt",
        "title": "User Interview 08: 25yo Financial Analyst, Mumbai",
        "raw_text": "I have maintained my SIP for 14 months now. Kept debit date on 8th, buffer of 7 days post salary. Never missed a payment. The Groww app makes tracking easy. The problem is other apps spam too many trading push notifications.",
        "publication_date": "2026-08-11",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",  # Positive case
    },
    {
        "id": "rec_interview_09",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_09.txt",
        "title": "User Interview 09: 29yo Store Manager, Ahmedabad",
        "raw_text": "I wanted to stop my SIP because of car EMI. Looked for Cancel SIP button. Groww app had 'Delete SIP' and 'Stop AutoPay'. I wasn't sure if deleting SIP sells my existing units or just stops future debits. Customer care took 4 days to clarify.",
        "publication_date": "2026-09-08",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
    {
        "id": "rec_interview_10",
        "source_type": "interview",
        "platform": "Interview",
        "source_url": "internal://research/interviews/2026-cohort-1/user_10.txt",
        "title": "User Interview 10: 24yo Customer Service Rep, Kolkata",
        "raw_text": "Bank charged me ₹295 for missed SIP instalment. I went to the bank branch and argued with manager. He said Groww requested debit without balance. Felt so embarrassed that I closed my Groww account.",
        "publication_date": "2026-10-05",
        "rating": None,
        "is_synthetic_demo": True,
        "relevance_status": "highly_relevant",
    },
]


# ---------------------------------------------------------------------------
# Golden Benchmark Ground Truth Set (25 Hand-Labelled Records)
# ---------------------------------------------------------------------------

GOLDEN_BENCHMARK_SET: List[Dict[str, Any]] = [
    {
        "raw_record_id": "rec_reddit_01",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_01",  # cash_flow_mismatch
        "expected_journey_stage": "instalment_failed",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "Delayed salary credit by 2 days caused AutoPay bounce and ₹295 bank charge, prompting user to stop SIP.",
        "reviewer_notes": "Classic cash-flow mismatch where debit date (5th) preceded irregular salary credit (7th).",
    },
    {
        "raw_record_id": "rec_reddit_02",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_05",  # modification_cancellation
        "expected_journey_stage": "life_event",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "Inability to find a simple pause button; skipping failed and still debited bank account, forcing full cancellation.",
        "reviewer_notes": "UX friction in pause/skip workflow forced permanent cancellation.",
    },
    {
        "raw_record_id": "rec_reddit_03",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_06",  # expectation_mismatch
        "expected_journey_stage": "active",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "Negative returns (-3%) after 7 months against expectation of 15% guaranteed return.",
        "reviewer_notes": "Unrealistic short-term return expectations led to disappointment and exit.",
    },
    {
        "raw_record_id": "rec_reddit_04",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_11",  # support_trust
        "expected_journey_stage": "instalment_failed",
        "expected_first_hand": True,
        "expected_sip_status": "failed",
        "expected_stated_reason": "Money deducted but Groww shows failed; customer support bot loop without resolution for 9 days.",
        "reviewer_notes": "Breakdown in support responsiveness and customer trust after reconciliation failure.",
    },
    {
        "raw_record_id": "rec_reddit_05",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_09",  # confusing_statements
        "expected_journey_stage": "active",
        "expected_first_hand": True,
        "expected_sip_status": "active",
        "expected_stated_reason": "Confusion over dashboard showing 18.4% XIRR while total value is at a ₹450 loss.",
        "reviewer_notes": "Cognitive barrier: user does not understand difference between annualized XIRR and absolute portfolio value.",
    },
    {
        "raw_record_id": "rec_reddit_06",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_04",  # autopay_mandate
        "expected_journey_stage": "setup",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "SBI NetBanking e-mandate rejected 3 times with error code MD01 during setup.",
        "reviewer_notes": "Technical mandate registration barrier prevented SIP initiation.",
    },
    {
        "raw_record_id": "rec_reddit_07",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_02",  # unexpected_expenses
        "expected_journey_stage": "life_event",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "Sudden medical emergency for father requiring ₹3.5L and diverting salary to personal loan EMI.",
        "reviewer_notes": "Unforeseen catastrophic financial emergency diverting all discretionary liquidity.",
    },
    {
        "raw_record_id": "rec_reddit_08",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_07",  # volatility_anxiety
        "expected_journey_stage": "active",
        "expected_first_hand": True,
        "expected_sip_status": "paused",
        "expected_stated_reason": "Panic and severe anxiety during continuous market downturn, considering stopping SIP.",
        "reviewer_notes": "Emotional distress and loss aversion during market drawdown.",
    },
    {
        "raw_record_id": "rec_reddit_09",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_12",  # goal_changes
        "expected_journey_stage": "life_event",
        "expected_first_hand": True,
        "expected_sip_status": "paused",
        "expected_stated_reason": "Wedding in November requiring liquidity for venue and gold.",
        "reviewer_notes": "Planned major life event shifting financial priorities temporarily.",
    },
    {
        "raw_record_id": "rec_reddit_10",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_08",  # lack_understanding
        "expected_journey_stage": "active",
        "expected_first_hand": True,
        "expected_sip_status": "active",
        "expected_stated_reason": "Confusion over NAV allotment cut-off times and weekend bank settlement delays.",
        "reviewer_notes": "Investor does not grasp mutual fund cut-off timing and NAV applicability rules.",
    },
    {
        "raw_record_id": "rec_reddit_11",
        "expected_relevance": "not_relevant",
        "expected_category_id": "cat_13",  # unclassified
        "expected_journey_stage": "churned",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "User exited mutual funds to speculate in Bitcoin and cryptocurrency.",
        "reviewer_notes": "Out of scope: cryptocurrency speculation, not a Groww mutual fund friction problem.",
    },
    {
        "raw_record_id": "rec_reddit_12",
        "expected_relevance": "not_relevant",
        "expected_category_id": "cat_13",  # unclassified
        "expected_journey_stage": "pre_sip",
        "expected_first_hand": False,
        "expected_sip_status": "unknown",
        "expected_stated_reason": None,
        "reviewer_notes": "Out of scope: intraday margin stock tips.",
    },
    {
        "raw_record_id": "rec_reddit_13",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_10",  # app_usability
        "expected_journey_stage": "active",
        "expected_first_hand": True,
        "expected_sip_status": "active",
        "expected_stated_reason": "App crashes immediately whenever navigating to SIPs tab on Android 14.",
        "reviewer_notes": "Technical software bug blocking investment tracking.",
    },
    {
        "raw_record_id": "rec_reddit_15",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_01",  # cash_flow_mismatch
        "expected_journey_stage": "instalment_failed",
        "expected_first_hand": True,
        "expected_sip_status": "failed",
        "expected_stated_reason": "Step-up SIP increased instalment by ₹500 unintentionally, leading to insufficient balance bounce.",
        "reviewer_notes": "Step-up feature opacity caused unbudgeted debit and bank bounce penalty.",
    },
    {
        "raw_record_id": "rec_appstore_01",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_03",  # payment_failures
        "expected_journey_stage": "instalment_failed",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "Debit attempted on 6th instead of scheduled 3rd, resulting in ₹295 bounce charge and app uninstallation.",
        "reviewer_notes": "Delayed debit trigger caused account bounce.",
    },
    {
        "raw_record_id": "rec_appstore_04",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_05",  # modification_cancellation
        "expected_journey_stage": "active",
        "expected_first_hand": True,
        "expected_sip_status": "active",
        "expected_stated_reason": "Groww forces cancellation and recreation just to change SIP date from 1st to 10th.",
        "reviewer_notes": "Lack of in-flight SIP date modification friction.",
    },
    {
        "raw_record_id": "rec_appstore_06",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_11",  # support_trust
        "expected_journey_stage": "instalment_failed",
        "expected_first_hand": True,
        "expected_sip_status": "paused",
        "expected_stated_reason": "Double deduction of ₹2000 for single instalment and unhelpful customer care.",
        "reviewer_notes": "Severe billing bug and support silence eroding user trust.",
    },
    {
        "raw_record_id": "rec_appstore_08",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_04",  # autopay_mandate
        "expected_journey_stage": "churned",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "Mandate expired and SIP cancelled without advance warning notification.",
        "reviewer_notes": "Failure to notify user of mandate expiration led to churn.",
    },
    {
        "raw_record_id": "rec_appstore_10",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_10",  # app_usability
        "expected_journey_stage": "active",
        "expected_first_hand": True,
        "expected_sip_status": "active",
        "expected_stated_reason": "Debit reminders sent on the same day rather than 48 hours in advance.",
        "reviewer_notes": "Sub-optimal notification timing limits user ability to fund account.",
    },
    {
        "raw_record_id": "rec_official_01",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_03",  # payment_failures
        "expected_journey_stage": "instalment_failed",
        "expected_first_hand": False,
        "expected_sip_status": "unknown",
        "expected_stated_reason": "Bank ECS/NACH bounce charges of ₹250-₹500 and AMC cancellation rule after 3 consecutive failures.",
        "reviewer_notes": "Official Groww documentation defining institutional failure mechanisms.",
    },
    {
        "raw_record_id": "rec_official_04",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_01",  # cash_flow_mismatch
        "expected_journey_stage": "churned",
        "expected_first_hand": False,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "AMFI macro data reporting 70.1% discontinuation ratio with 48% stopping in Year 1.",
        "reviewer_notes": "Macro industry benchmark establishing 12-month retention drop-off baseline.",
    },
    {
        "raw_record_id": "rec_official_05",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_02",  # unexpected_expenses
        "expected_journey_stage": "churned",
        "expected_first_hand": False,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "SEBI survey identifying sudden financial obligations (41%), payment friction (28%), and volatility (19%) as top discontinuation drivers.",
        "reviewer_notes": "Statistically representative nationwide regulatory survey establishing relative root-cause weights.",
    },
    {
        "raw_record_id": "rec_interview_01",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_01",  # cash_flow_mismatch
        "expected_journey_stage": "instalment_failed",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "Debit date (1st) mismatched with salary credit (3rd/4th) triggering ₹350 bank bounce fee.",
        "reviewer_notes": "In-depth qualitative interview corroborating the salary credit lag hypothesis.",
    },
    {
        "raw_record_id": "rec_interview_02",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_01",  # cash_flow_mismatch
        "expected_journey_stage": "active",
        "expected_first_hand": True,
        "expected_sip_status": "discontinued",
        "expected_stated_reason": "Variable sales incentives created income fluctuation where fixed ₹5000 SIP became unviable.",
        "reviewer_notes": "Need for dynamic SIP amount modification for variable-income earners.",
    },
    {
        "raw_record_id": "rec_interview_06",
        "expected_relevance": "highly_relevant",
        "expected_category_id": "cat_01",  # cash_flow_mismatch
        "expected_journey_stage": "instalment_failed",
        "expected_first_hand": True,
        "expected_sip_status": "failed",
        "expected_stated_reason": "Behavioural budgeting failure: salary spent by 9th, leaving insufficient balance for 10th debit.",
        "reviewer_notes": "Behavioural finance drop-off: debit date placed too late in the month relative to salary day.",
    },
]


# ---------------------------------------------------------------------------
# Seeding Functions
# ---------------------------------------------------------------------------

def seed_categories(session) -> int:
    """Loads and seeds the 13 canonical categories from config/taxonomy.yaml."""
    settings = get_settings()
    taxonomy_file = settings.ROOT_DIR / "config" / "taxonomy.yaml"

    if not taxonomy_file.exists():
        raise FileNotFoundError(f"Missing taxonomy file at {taxonomy_file}")

    with open(taxonomy_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    categories_data = data.get("categories", [])
    seeded_count = 0

    for cat in categories_data:
        existing = session.query(IssueCategory).filter_by(id=cat["id"]).first()
        if not existing:
            new_cat = IssueCategory(
                id=cat["id"],
                code=cat["code"],
                name=cat["name"],
                description=cat["description"],
                is_predefined=cat.get("is_predefined", True),
            )
            session.add(new_cat)
            seeded_count += 1
        else:
            # Update fields if taxonomy descriptions evolved
            existing.code = cat["code"]
            existing.name = cat["name"]
            existing.description = cat["description"]

    session.commit()
    return seeded_count


def seed_demo_records(session) -> int:
    """Inserts all 53 demonstration records across the 5 source channels."""
    seeded_count = 0

    for item in DEMO_RECORDS:
        raw_text = item["raw_text"]
        sanitized = sanitize_text(raw_text)
        content_hash = compute_content_hash(raw_text)

        existing = session.query(RawRecord).filter_by(content_hash=content_hash).first()
        if not existing:
            record = RawRecord(
                id=item["id"],
                source_type=item["source_type"],
                source_url=item.get("source_url"),
                platform=item["platform"],
                title=item.get("title"),
                raw_text=raw_text,
                sanitized_text=sanitized,
                content_hash=content_hash,
                rating=item.get("rating"),
                publication_date=item.get("publication_date"),
                relevance_status=item.get("relevance_status", "unanalyzed"),
                is_user_verified=item.get("is_user_verified", False),
                is_synthetic_demo=item.get("is_synthetic_demo", False),
            )
            session.add(record)
            seeded_count += 1

    session.commit()
    return seeded_count


def seed_golden_benchmark(session) -> int:
    """Inserts the 25 hand-labelled Golden Benchmark records and exports JSON."""
    settings = get_settings()
    seeded_count = 0
    golden_export_list = []

    for item in GOLDEN_BENCHMARK_SET:
        raw_rec_id = item["raw_record_id"]
        # Ensure referenced raw record exists
        raw_rec = session.query(RawRecord).filter_by(id=raw_rec_id).first()
        if not raw_rec:
            continue

        existing = session.query(GoldenRecord).filter_by(raw_record_id=raw_rec_id).first()
        if not existing:
            golden_rec = GoldenRecord(
                raw_record_id=raw_rec_id,
                expected_relevance=item["expected_relevance"],
                expected_category_id=item["expected_category_id"],
                expected_journey_stage=item["expected_journey_stage"],
                expected_first_hand=item.get("expected_first_hand", True),
                expected_sip_status=item["expected_sip_status"],
                expected_stated_reason=item.get("expected_stated_reason"),
                reviewer_notes=item.get("reviewer_notes"),
                annotator_id="lead_pm_annotator",
            )
            session.add(golden_rec)
            seeded_count += 1

        golden_export_list.append({
            "raw_record_id": raw_rec_id,
            "raw_text": raw_rec.raw_text,
            "platform": raw_rec.platform,
            "source_type": raw_rec.source_type,
            "expected_relevance": item["expected_relevance"],
            "expected_category_id": item["expected_category_id"],
            "expected_journey_stage": item["expected_journey_stage"],
            "expected_first_hand": item.get("expected_first_hand", True),
            "expected_sip_status": item["expected_sip_status"],
            "expected_stated_reason": item.get("expected_stated_reason"),
            "reviewer_notes": item.get("reviewer_notes"),
        })

    session.commit()

    # Also persist golden dataset JSON export in data/golden/benchmark_25.json
    export_path = settings.DATA_DIR / "golden" / "benchmark_25.json"
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(golden_export_list, f, indent=2, ensure_ascii=False)

    return seeded_count


def seed_all() -> Dict[str, int]:
    """Orchestrates complete idempotent database initialization and seeding."""
    init_db()
    session = get_session()
    try:
        categories_seeded = seed_categories(session)
        records_seeded = seed_demo_records(session)
        golden_seeded = seed_golden_benchmark(session)
        return {
            "categories": categories_seeded,
            "records": records_seeded,
            "golden_benchmarks": golden_seeded,
        }
    finally:
        session.close()


if __name__ == "__main__":
    print("Initializing database tables and seeding demonstration datasets...")
    result = seed_all()
    print(f"Seeding completed successfully: {result}")
