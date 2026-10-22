import os, json, sqlite3, base64
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st

APP_TITLE = "Duperman Services | AI Smart Estimate"
DB_PATH = os.getenv("ESTIMATOR_DB_PATH", "estimates.db")
SERVICE_TYPES = [
    "Plumbing repair / fixture replacement", "Drywall patching / repair", "Painting / touch-ups",
    "Flooring / tile", "Carpentry / trim / baseboards", "Doors / windows / hardware",
    "Cabinets / shelving / installation", "Caulking / sealing", "Appliance / furniture assembly",
    "Rental turnover / punch list", "General handyman repair", "Landscaping / yard work",
    "Concrete / masonry repair", "Cleanup / debris removal", "Other (describe)"
]
LENGTH_TO_FEET = {"inches": 1/12, "feet": 1, "centimeters": 1/30.48, "meters": 3.280839895, "yards": 3}
AREA_TO_SQFT = {"sq ft": 1, "sq m": 10.7639104167, "sq yd": 9, "acres": 43560}

st.set_page_config(page_title=APP_TITLE, page_icon="🧰", layout="wide")

def db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""CREATE TABLE IF NOT EXISTS estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
        customer TEXT, job_address TEXT, service_type TEXT, description TEXT,
        hours REAL, crew_size INTEGER, labor_rate REAL, labor_total REAL,
        materials_total REAL, other_costs REAL, overhead_pct REAL, contingency_pct REAL,
        target_margin_pct REAL, bid_total REAL, actual_hours REAL, actual_materials REAL,
        actual_other_costs REAL, actual_revenue REAL, notes TEXT)""")
    conn.commit()
    return conn

def save_estimate(d):
    conn = db_conn()
    conn.execute("""INSERT INTO estimates (
        created_at, customer, job_address, service_type, description, hours, crew_size,
        labor_rate, labor_total, materials_total, other_costs, overhead_pct, contingency_pct,
        target_margin_pct, bid_total, actual_hours, actual_materials, actual_other_costs,
        actual_revenue, notes
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        datetime.now().isoformat(timespec="seconds"), d["customer"], d["address"], d["service"],
        d["description"], d["hours"], d["crew"], d["rate"], d["labor"], d["materials"],
        d["other"], d["overhead_pct"], d["contingency_pct"], d["margin_pct"], d["bid"],
        None, None, None, None, d["notes"]))
    conn.commit()
    conn.close()

def load_estimates():
    conn = db_conn()
    df = pd.read_sql_query("SELECT * FROM estimates ORDER BY id DESC", conn)
    conn.close()
    return df

def update_actuals(eid, hours, materials, other, revenue):
    conn = db_conn()
    conn.execute("UPDATE estimates SET actual_hours=?, actual_materials=?, actual_other_costs=?, actual_revenue=? WHERE id=?",
                 (hours, materials, other, revenue, int(eid)))
    conn.commit()
    conn.close()

def get_client(api_key):
    from openai import OpenAI
    return OpenAI(api_key=api_key)

def call_ai(api_key, model, prompt, images=None):
    try:
        client = get_client(api_key)
        content = [{"type": "text", "text": prompt}]
        if images:
            for img_bytes, mime in images:
                data = base64.b64encode(img_bytes).decode("utf-8")
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": """You are an estimating assistant for residential handyman, home-repair, and rental-property maintenance work in Utah.
Create cautious, preliminary drafts only. Never claim to know live local prices. Do not invent supplier prices.
Separate known facts from assumptions and ask questions when important information is missing.
Consider setup, access, occupied vs. vacant property, tenant coordination, protection, disposal, cleanup, travel, and return visits when relevant.
Electrical work is strictly out of scope; recommend a properly licensed electrician. For plumbing, HVAC, structural, gas, or other regulated/specialized work, flag licensing/permit/specialist checks where appropriate.
The worker is a W-2 employee; distinguish estimated worker-hours and internal job costs from the employer's customer price. Return valid JSON only."""},
                {"role": "user", "content": content}
            ],
            temperature=0.2
        )
        return json.loads(response.choices[0].message.content), None
    except Exception as e:
        return None, f"AI request failed: {e}"

def money(x): return f"${float(x):,.2f}"

def build_pdf_bytes(title, body):
    # Create a simple PDF using reportlab. Falls back to text if reportlab unavailable.
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=48)
        styles = getSampleStyleSheet()
        story = [Paragraph(title, styles["Title"]), Spacer(1, 14)]
        for line in body.splitlines():
            if not line.strip():
                story.append(Spacer(1, 7))
            else:
                safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Paragraph(safe, styles["BodyText"]))
                story.append(Spacer(1, 5))
        doc.build(story)
        return buf.getvalue()
    except Exception:
        return None

if "ai_result" not in st.session_state: st.session_state.ai_result = None
if "ai_error" not in st.session_state: st.session_state.ai_error = None
if "photo_result" not in st.session_state: st.session_state.photo_result = None
if "photo_error" not in st.session_state: st.session_state.photo_error = None

st.title("🧰 Duperman Services — AI Smart Estimate")
st.caption("AI-assisted estimating for home repairs and rental-property maintenance. Electrical work is excluded. Review all AI suggestions, quantities, costs, site conditions, and scope.")

with st.sidebar:
    st.header("Business pricing")
    labor_rate = st.number_input("Billable labor rate ($ / worker-hour)", 0.0, value=65.0, step=5.0)
    crew_size = st.number_input("Workers on this job", 1, 20, 1, step=1)
    minimum_charge = st.number_input("Minimum service charge ($)", 0.0, value=75.0, step=5.0)
    overhead_pct = st.number_input("Overhead allowance (%)", 0.0, 100.0, 10.0, step=1.0)
    contingency_pct = st.number_input("Contingency (%)", 0.0, 100.0, 10.0, step=1.0)
    target_margin_pct = st.number_input("Target gross profit margin (%)", 0.0, 80.0, 35.0, step=1.0)
    st.divider()
    st.header("AI settings")
    api_key = st.text_input("OpenAI API key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    model = st.text_input("Vision-capable model", value=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    st.caption("AI features require an OpenAI API key and API usage may cost extra. The key is not saved in the estimate database.")

tab_new, tab_history, tab_learning, tab_help = st.tabs(["➕ New estimate", "📚 Saved estimates", "📊 Learn from jobs", "ℹ️ Setup"])

with tab_new:
    st.subheader("1. Customer and job")
    col1, col2 = st.columns(2)
    with col1:
        customer = st.text_input("Customer name")
        address = st.text_input("Job address / area")
        service = st.selectbox("Service category", SERVICE_TYPES)
        property_type = st.selectbox("Property type", ["Customer's home", "Rental property / apartment"])
        purchase_responsibility = st.selectbox(
            "Who purchases materials for this job?",
            ["My husband buys them", "Boss buys them", "Depends on the job / decide later"]
        )
    with col2:
        description = st.text_area("Describe the job", placeholder="Example: Clean up front yard, trim four shrubs, remove leaves and branches, and spread two cubic yards of mulch.", height=120)
        notes = st.text_area("Access, slope, disposal, weather, or other notes", height=75)

    st.subheader("2. Measurements and materials")
    st.caption("Measurements are optional. Length and width are converted automatically.")
    a,b,c,d = st.columns(4)
    with a:
        length = st.number_input("Length", min_value=0.0, value=0.0, step=1.0)
        length_unit = st.selectbox("Length unit", list(LENGTH_TO_FEET), index=1)
    with b:
        width = st.number_input("Width", min_value=0.0, value=0.0, step=1.0)
        width_unit = st.selectbox("Width unit", list(LENGTH_TO_FEET), index=1)
    with c:
        area_unit = st.selectbox("Display area as", list(AREA_TO_SQFT), index=0)
        waste_pct = st.number_input("Extra material allowance (%)", 0.0, 100.0, 10.0, step=1.0)
    with d:
        material_price_per_unit = st.number_input("Optional material price per displayed area unit ($)", min_value=0.0, value=0.0, step=0.5)
    length_ft = length * LENGTH_TO_FEET[length_unit]
    width_ft = width * LENGTH_TO_FEET[width_unit]
    area_sqft = length_ft * width_ft if length > 0 and width > 0 else 0.0
    area_display = area_sqft / AREA_TO_SQFT[area_unit] if area_sqft else 0.0
    if area_sqft:
        st.info(f"Converted dimensions: **{length_ft:.2f} ft × {width_ft:.2f} ft** · Area: **{area_display:,.2f} {area_unit}** · With allowance: **{area_display*(1+waste_pct/100):,.2f} {area_unit}**")
    if area_sqft and material_price_per_unit:
        st.write(f"Calculated material allowance cost: **{money(area_display*(1+waste_pct/100)*material_price_per_unit)}** (verify supplier price and actual units).")

    dims = f"Length={length} {length_unit} ({length_ft:.2f} ft); width={width} {width_unit} ({width_ft:.2f} ft); area={area_sqft:.2f} sq ft; material allowance={waste_pct}%." if area_sqft else "No dimensions supplied."
    ai_context = f"""Service category: {service}
Property type: {property_type}
Materials purchasing responsibility: {purchase_responsibility}
Crew size: {crew_size}
Job description: {description}
Measurements: {dims}
Other notes: {notes}
Return JSON with keys summary, tasks (array of task, hours_low, hours_high, materials_or_equipment, quantity_or_assumption), questions (array), risks_and_exclusions (array), material_suggestions (array of item, quantity, unit, price_known_or_unknown). Use realistic ranges and say unknown prices are unknown. Do not provide a final customer price."""
    st.subheader("3. AI job analysis")
    if st.button("✨ Analyze job and suggest tasks / hours", type="primary"):
        if not api_key: st.session_state.ai_error = "Add your OpenAI API key in the sidebar to use AI."
        elif not description.strip(): st.session_state.ai_error = "Describe the job first."
        else:
            with st.spinner("Analyzing scope..."):
                st.session_state.ai_result, st.session_state.ai_error = call_ai(api_key, model, ai_context)
    if st.session_state.ai_error: st.warning(st.session_state.ai_error)
    ai = st.session_state.ai_result
    ai_hours_low = ai_hours_high = 0.0
    if ai:
        st.markdown(f"**Scope summary:** {ai.get('summary','')}")
        tasks = ai.get("tasks", [])
        if tasks:
            st.dataframe(pd.DataFrame(tasks), use_container_width=True, hide_index=True)
            ai_hours_low = sum(float(x.get("hours_low",0) or 0) for x in tasks)
            ai_hours_high = sum(float(x.get("hours_high",0) or 0) for x in tasks)
            st.metric("AI worker-hour range", f"{ai_hours_low:.1f}–{ai_hours_high:.1f}")
            if st.button("Use midpoint of AI hour range"):
                st.session_state.hours_input = round((ai_hours_low+ai_hours_high)/2, 2)
                st.rerun()
        for title, key in [("Questions to confirm","questions"),("Risks / exclusions","risks_and_exclusions"),("Suggested materials (verify quantities/prices)","material_suggestions")]:
            items = ai.get(key, [])
            if items:
                st.markdown(f"**{title}**")
                if isinstance(items[0], dict): st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
                else:
                    for item in items: st.write(f"• {item}")

    st.subheader("4. Optional photo assessment")
    st.write("Upload photos for AI to describe visible conditions and flag questions. Photos cannot reveal hidden conditions or guarantee quantities.")
    photos = st.file_uploader("Upload job photos", type=["jpg","jpeg","png","webp"], accept_multiple_files=True)
    if st.button("📷 Analyze photos with AI"):
        if not api_key: st.session_state.photo_error = "Add your OpenAI API key in the sidebar."
        elif not photos: st.session_state.photo_error = "Upload at least one photo first."
        else:
            imgs=[]
            for f in photos[:6]:
                mime = f.type if f.type in ["image/jpeg","image/png","image/webp"] else "image/jpeg"
                imgs.append((f.getvalue(), mime))
            prompt = f"""Review these job-site photos for a residential repair / rental-property maintenance estimate.
Job description: {description}
Service category: {service}
Property type: {property_type}
Electrical work is out of scope.
Return JSON with keys visible_observations (array), possible_tasks (array), questions (array), risks_and_exclusions (array), cannot_determine_from_photos (array).
Only describe visible evidence; don't infer hidden damage or guarantee measurements. Ask for scale or on-site verification when needed."""
            with st.spinner("Reviewing photos..."):
                st.session_state.photo_result, st.session_state.photo_error = call_ai(api_key, model, prompt, imgs)
    if st.session_state.photo_error: st.warning(st.session_state.photo_error)
    if st.session_state.photo_result:
        for key in ["visible_observations","possible_tasks","questions","risks_and_exclusions","cannot_determine_from_photos"]:
            vals = st.session_state.photo_result.get(key, [])
            if vals:
                st.markdown("**" + key.replace("_"," ").title() + "**")
                for val in vals: st.write(f"• {val}")

    st.subheader("5. Materials purchasing handoff")
    if purchase_responsibility == "My husband buys them":
        st.info("Purchasing plan: prepare a materials shopping list, verify quantities and prices, and keep receipts for reimbursement / job-cost tracking.")
    elif purchase_responsibility == "Boss buys them":
        st.info("Purchasing plan: prepare a clear materials list for the boss, including quantities, sizes, finish/color, and any compatibility details to confirm.")
    else:
        st.info("Purchasing plan: decide who is buying before the job starts. The materials list can be used either as a shopping list or as a request for the boss to purchase supplies.")

    st.subheader("6. Build the job cost estimate")
    x,y,z = st.columns(3)
    with x:
        hours = st.number_input("Estimated total worker-hours", min_value=0.0, value=float(st.session_state.get("hours_input",2.0)), step=0.25, key="hours_input")
        rate = st.number_input("Labor rate ($ / worker-hour)", min_value=0.0, value=float(labor_rate), step=5.0)
    with y:
        materials = st.number_input("Materials / supplies total ($)", min_value=0.0, value=0.0, step=10.0)
        equipment = st.number_input("Equipment, disposal, delivery, travel ($)", min_value=0.0, value=0.0, step=5.0)
    with z:
        other = st.number_input("Other direct costs ($)", min_value=0.0, value=0.0, step=5.0)
        strategy = st.selectbox("Pricing view (if boss needs a customer-price estimate)", ["Recommended profitable estimate","Competitive estimate","Premium / high-end defensible estimate"])

    labor = hours * rate
    direct = labor + materials + equipment + other
    overhead = direct * overhead_pct/100
    contingency = (direct + overhead) * contingency_pct/100
    margin = target_margin_pct/100
    if strategy == "Competitive estimate":
        used_margin = max(0.10, margin - 0.10); used_contingency = contingency * 0.5
    elif strategy == "Premium / high-end defensible estimate":
        used_margin = min(0.80, margin + 0.10); used_contingency = contingency
    else:
        used_margin = margin; used_contingency = contingency
    cost_basis = direct + overhead + used_contingency
    bid = max(minimum_charge, cost_basis/max(0.01, 1-used_margin))
    bid = max(minimum_charge, round(bid/5)*5)
    profit = bid - cost_basis
    realized_margin = profit/bid*100 if bid else 0

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Labor", money(labor))
    k2.metric("Materials", money(materials))
    k3.metric("Estimated cost + overhead", money(direct+overhead+used_contingency))
    k4.metric("Suggested bid", money(bid))
    st.caption(f"{strategy} · {hours:.2f} worker-hours · approx. {hours/int(crew_size):.2f} elapsed hours with {int(crew_size)} worker(s), if work can be split efficiently.")
    st.success(f"Illustrative gross profit before taxes and omitted costs: {money(profit)} ({realized_margin:.1f}% of estimated customer price). If your husband is only estimating labor/material needs for his boss, treat this price and margin as optional context—not his pay.")
    with st.expander("Internal cost breakdown"):
        st.json({"Labor":money(labor),"Materials":money(materials),"Equipment/disposal/travel":money(equipment),"Other direct costs":money(other),"Overhead":money(overhead),"Contingency used":money(used_contingency),"Cost basis":money(cost_basis),"Target margin used":f"{used_margin*100:.1f}%","Bid":money(bid),"Projected gross profit":money(profit)})

    customer_scope = st.text_area("Customer-facing scope", value=description, height=75)
    exclusions = st.text_area("Assumptions / exclusions", value="Price assumes the described scope and visible conditions. Hidden conditions, extra disposal, or changes in scope require customer approval and may change the price.", height=65)
    quote = f"""DUPERMAN SERVICES
ESTIMATE
Date: {date.today().isoformat()}
Estimate reference: Draft
Customer: {customer or '[Customer name]'}
Job address: {address or '[Job address]'}

SCOPE OF WORK
{customer_scope or '[Describe work included]'}

ESTIMATED SCHEDULE
Estimated labor: {hours:.2f} worker-hours
Approximate on-site duration: {hours/int(crew_size):.2f} hours with {int(crew_size)} worker(s), subject to site conditions.

TOTAL PROPOSED PRICE: {money(bid)}

ASSUMPTIONS / EXCLUSIONS
{exclusions}

This estimate is based on the scope and assumptions above. Additional work or concealed conditions should be discussed and approved before proceeding.
"""
    pdf = build_pdf_bytes("Duperman Services — Estimate", quote)
    if pdf:
        st.download_button("⬇️ Download customer estimate (PDF)", data=pdf, file_name=f"duperman_estimate_{date.today().isoformat()}.pdf", mime="application/pdf")
    st.download_button("⬇️ Download estimate (TXT)", data=quote, file_name=f"duperman_estimate_{date.today().isoformat()}.txt", mime="text/plain")
    if st.button("💾 Save estimate to history", type="primary"):
        save_estimate({"customer":customer,"address":address,"service":service,"description":customer_scope,
                       "hours":hours,"crew":int(crew_size),"rate":rate,"labor":labor,"materials":materials,
                       "other":equipment+other,"overhead_pct":overhead_pct,"contingency_pct":contingency_pct,
                       "margin_pct":used_margin*100,"bid":bid,"notes":notes})
        st.success("Saved to job history.")

with tab_history:
    st.subheader("Saved estimates")
    history = load_estimates()
    if history.empty:
        st.info("No estimates saved yet.")
    else:
        cols = ["id","created_at","customer","job_address","service_type","hours","labor_total","materials_total","bid_total","actual_hours","actual_materials","actual_revenue"]
        st.dataframe(history[cols], use_container_width=True, hide_index=True)
        st.download_button("Export estimate history (CSV)", history.to_csv(index=False).encode("utf-8"), "duperman_estimates.csv", "text/csv")
        chosen = st.selectbox("Choose estimate to update actual results", history["id"].tolist())
        row = history[history["id"]==chosen].iloc[0]
        st.write(f"**Estimate #{int(chosen)}:** {row['customer'] or 'Unnamed customer'} — proposed bid {money(row['bid_total'])}")
        with st.form("actuals_form"):
            actual_hours = st.number_input("Actual worker-hours", min_value=0.0, value=float(row["actual_hours"] or 0), step=0.25)
            actual_materials = st.number_input("Actual materials ($)", min_value=0.0, value=float(row["actual_materials"] or 0), step=5.0)
            actual_other = st.number_input("Actual other costs ($)", min_value=0.0, value=float(row["actual_other_costs"] or 0), step=5.0)
            actual_revenue = st.number_input("Actual revenue collected / final price ($)", min_value=0.0, value=float(row["actual_revenue"] or row["bid_total"] or 0), step=5.0)
            submitted = st.form_submit_button("Save actual job results")
        if submitted:
            update_actuals(chosen,actual_hours,actual_materials,actual_other,actual_revenue)
            st.success("Actual results saved. Open Learn from jobs to review patterns.")
            st.rerun()

with tab_learning:
    st.subheader("Learn from completed jobs")
    history = load_estimates()
    if history.empty:
        st.info("Save estimates and enter actual results to start building job history.")
    else:
        completed = history[history["actual_hours"].notna() & (history["actual_hours"] > 0)]
        if completed.empty:
            st.info("No completed-job actuals recorded yet. Enter actual hours and costs in Saved estimates.")
        else:
            completed["hours_variance"] = completed["actual_hours"] - completed["hours"]
            completed["materials_variance"] = completed["actual_materials"].fillna(0) - completed["materials_total"].fillna(0)
            completed["actual_direct_costs"] = completed["actual_hours"]*completed["labor_rate"] + completed["actual_materials"].fillna(0) + completed["actual_other_costs"].fillna(0)
            completed["actual_profit_estimate"] = completed["actual_revenue"].fillna(0) - completed["actual_direct_costs"]
            c1,c2,c3 = st.columns(3)
            c1.metric("Completed jobs tracked", len(completed))
            c2.metric("Average hour difference", f"{completed['hours_variance'].mean():+.2f} hrs")
            c3.metric("Average materials difference", money(completed["materials_variance"].mean()))
            st.dataframe(completed[["id","service_type","hours","actual_hours","hours_variance","materials_total","actual_materials","materials_variance","bid_total","actual_revenue","actual_profit_estimate"]], use_container_width=True, hide_index=True)
            service_summary = completed.groupby("service_type").agg(jobs=("id","count"), avg_estimated_hours=("hours","mean"), avg_actual_hours=("actual_hours","mean"), avg_estimated_materials=("materials_total","mean"), avg_actual_materials=("actual_materials","mean")).reset_index()
            st.markdown("**Suggested adjustments based on your recorded history**")
            st.dataframe(service_summary.round(2), use_container_width=True, hide_index=True)
            st.caption("Use these as guidance, not automatic price changes. Small samples and unusual jobs can skew averages.")

with tab_help:
    st.subheader("Setup and safe use")
    st.markdown("""
- Designed for customer homes and rental properties; select the property type for each job.
- Record whether your husband or his boss is buying materials so the app can provide the right purchasing handoff.
- This is a W-2 employee job-planning tool. Labor hours, quantities, and internal costs are the core outputs; any customer-price / margin estimate is optional context for the employer.
- Electrical work is excluded. Use a properly licensed electrician. Check local licensing, permits, and specialist requirements for other regulated work.
- Set pricing assumptions only if the boss wants a customer-price estimate and has approved the rates and margin assumptions.
- AI features require an OpenAI API key. API usage is separate from a ChatGPT subscription.
- Upload only photos and customer details you are comfortable sending to the configured AI service.
- This starter stores estimates in SQLite on the machine/server running it. It does not sync between devices automatically.
- For access from phone and computer, deploy it to a secure hosted service and configure authentication, backups, and privacy controls.
- AI suggestions are not guarantees. Confirm material quantities, site conditions, local requirements, prices, hours, and scope before relying on an estimate.
""")
