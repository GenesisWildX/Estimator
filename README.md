# Duperman Services — AI Smart Estimate (Version 2)

Includes A–F requested features:
A. AI turns a job description into a draft scope, task list, labor-hour range, materials suggestions, questions, and risks.
B. Three bid strategies: competitive, recommended profitable, and premium/high-end defensible.
C. Customer-facing estimate as PDF and TXT.
D. Browser-based interface for phone, tablet, and computer (once hosted or on the same network).
E. Completed-job actuals and summary statistics to help tune future estimates.
F. Measurement conversion and basic area-based material allowance calculator.

Also includes optional AI photo assessment for visible observations and questions.

## Run on a computer
1. Install Python 3.10+.
2. Extract the ZIP and open a terminal in this folder.
3. Create and activate a virtual environment:
   - Windows: `python -m venv .venv` then `.venv\\Scripts\\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run: `streamlit run app.py`
6. Open the local address printed in the terminal, usually `http://localhost:8501`.

## Enable AI
- Add an OpenAI API key in the sidebar. You can set `OPENAI_API_KEY` before starting the app instead.
- The default model is `gpt-4.1-mini`; change it in the sidebar if needed for a vision-capable model available to your API account.
- API usage may incur separate charges. Never publish your API key in source code or share it.
- Manual pricing and estimate generation work without AI.

## Phone and computer
This is a browser app, so it can work on a phone and computer after deployment to a secure host. Running it locally only makes it available on the computer unless you configure network access. For real business use, add authentication, HTTPS, backups, and multi-user storage before exposing it to the internet.

## Before sending bids
Pricing defaults are placeholders. Update rates and cost assumptions to reflect the business. AI-generated task lists, labor hours, material suggestions, and photo observations are drafts, not guarantees. Confirm scope, quantities, supplier prices, local rules, and site conditions. The premium bid is a pricing strategy, not a guarantee of winning a job or a statement of market maximum.


## Tailored for your husband's workflow
- Job categories include common home repairs, handyman work, rental turnovers, and yard work.
- Each job can be marked as a customer home or rental property.
- Materials purchasing can be assigned to the employee, the boss, or decided per job, with a purchasing handoff reminder.
- Electrical work is excluded.
- Because he is a W-2 employee, the app emphasizes labor hours, material quantities, and internal job planning. Customer price / profit calculations are optional context for the employer.
