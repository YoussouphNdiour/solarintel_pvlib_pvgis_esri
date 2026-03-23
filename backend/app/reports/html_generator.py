"""Interactive HTML report generator for SolarIntel v2.

Generates a self-contained HTML file using Chart.js (CDN) with
interactive visualisations: monthly production bar chart, SENELEC
savings line chart, 25-year cash flow, and Monte Carlo confidence
band charts.  All data is embedded as JSON — no local assets.
"""

from __future__ import annotations

import json
from typing import Any

MONTHS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

_CSS = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #f3f4f6; color: #1f2937; }
    .container { max-width: 1100px; margin: 0 auto; padding: 24px; }
    .header { background: #1f2937; color: white; padding: 32px;
              border-radius: 8px; margin-bottom: 24px; }
    .header h1 { color: #f59e0b; font-size: 2rem; margin-bottom: 4px; }
    .header .subtitle { color: #9ca3af; font-size: 1rem; }
    .kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr);
                gap: 16px; margin-bottom: 24px; }
    .kpi-card { background: white; border-radius: 8px; padding: 20px;
                text-align: center; border-top: 4px solid #f59e0b;
                box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .kpi-card .value { font-size: 1.8rem; font-weight: bold; color: #f59e0b; }
    .kpi-card .label { font-size: 0.8rem; color: #6b7280; margin-top: 4px; }
    .card { background: white; border-radius: 8px; padding: 24px;
            margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
    .card h2 { font-size: 1.1rem; font-weight: bold; color: #1f2937;
               margin-bottom: 16px; border-left: 4px solid #f59e0b;
               padding-left: 12px; }
    .chart-container { position: relative; height: 300px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th { background: #1f2937; color: white; padding: 10px 12px; text-align: left; }
    td { padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }
    tr:nth-child(even) td { background: #f9fafb; }
    .text-center { text-align: center; } .text-right { text-align: right; }
    .text-xs { font-size: 0.75rem; } .font-bold { font-weight: bold; }
    .mb-3 { margin-bottom: 12px; }
    .badge-green { background: #d1fae5; color: #065f46; padding: 2px 8px;
                   border-radius: 9999px; font-size: 0.75rem; font-weight: bold; }
    .badge-red { background: #fee2e2; color: #991b1b; padding: 2px 8px;
                 border-radius: 9999px; font-size: 0.75rem; font-weight: bold; }
    .badge-gray { background: #f3f4f6; color: #6b7280; padding: 2px 8px;
                  border-radius: 9999px; font-size: 0.75rem; font-weight: bold; }
    a { color: #f59e0b; }
    @media (max-width: 600px) { .kpi-grid { grid-template-columns: repeat(2,1fr); } }
"""


def _sensitivity_rows(sensitivity: list[Any] | None) -> str:
    if not sensitivity:
        return "<tr><td colspan='4' class='text-center'>Non disponible</td></tr>"
    rows = ""
    for r in sensitivity:
        sign = "+" if r.price_change_pct > 0 else ""
        pb = f"{r.payback_years:.1f}" if r.payback_years != float("inf") else "∞"
        badge = "badge-green" if r.roi_25yr_pct > 0 else "badge-red"
        rows += (
            f"<tr><td class='text-center'>{sign}{r.price_change_pct:.0f}%</td>"
            f"<td class='text-right'>{r.annual_savings_xof:,.0f} FCFA</td>"
            f"<td class='text-center'>{pb} ans</td>"
            f"<td class='text-center'><span class='{badge}'>"
            f"{r.roi_25yr_pct:.1f}%</span></td></tr>\n"
        )
    return rows


def _qa_rows(qa_criteria: list[dict] | None) -> str:
    if not qa_criteria:
        return "<tr><td colspan='6' class='text-center'>Non disponible</td></tr>"
    rows = ""
    for c in qa_criteria:
        st = c.get("status", "NA")
        badge = "badge-green" if st == "PASS" else (
            "badge-red" if st == "FAIL" else "badge-gray"
        )
        rows += (
            f"<tr><td class='text-center font-bold'>{c.get('code','')}</td>"
            f"<td>{c.get('label','')}</td>"
            f"<td class='text-center'><span class='{badge}'>{st}</span></td>"
            f"<td class='text-center'>{c.get('value','—')}</td>"
            f"<td>{c.get('threshold','')}</td>"
            f"<td class='text-xs'>{c.get('comment','')}</td></tr>\n"
        )
    return rows


def generate_html_report(data: Any) -> str:
    """Generate a self-contained interactive HTML report.

    Args:
        data: A ``ReportData`` instance with all simulation and financial data.

    Returns:
        Complete HTML string ready to be saved as ``report.html`` or served
        directly over HTTP via FastAPI's ``HTMLResponse``.
    """
    monthly_kwh = data.monthly_kwh if data.monthly_kwh else [0.0] * 12
    monthly_savings = data.monthly_savings if data.monthly_savings else [0.0] * 12
    cf_years = list(range(26))
    cf_values = [
        -data.installation_cost_xof + data.annual_savings_xof * yr for yr in cf_years
    ]
    mc = data.monte_carlo
    mc_p10 = mc.monthly_p10 if mc else [0.0] * 12
    mc_p50 = mc.monthly_p50 if mc else monthly_kwh
    mc_p90 = mc.monthly_p90 if mc else [0.0] * 12

    narrative = ""
    if data.report_narrative:
        for para in data.report_narrative.split("\n\n"):
            if para.strip():
                narrative += f"<p class='mb-3'>{para.strip()}</p>\n"
    narrative = narrative or "<p>Analyse narrative non disponible.</p>"

    qr_section = ""
    if data.qr_code_url:
        qr_section = (
            f"<div class='card'><h2>Tableau de Bord Interactif</h2>"
            f"<p>Accédez au tableau de bord: "
            f"<a href='{data.qr_code_url}' target='_blank'>{data.qr_code_url}</a>"
            f"</p></div>"
        )

    loc = data.address or f"{data.latitude:.4f}°N, {data.longitude:.4f}°E"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SolarIntel v2 — Rapport {data.project_name}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <style>{_CSS}</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>SolarIntel v2 — Rapport PV</h1>
    <div class="subtitle">{data.project_name} &mdash; {loc} &mdash; {data.report_date}</div>
  </div>
  <div class="kpi-grid">
    <div class="kpi-card"><div class="value">{data.peak_kwc:.2f} kWc</div>
      <div class="label">Puissance crête</div></div>
    <div class="kpi-card"><div class="value">{data.annual_kwh:,.0f}</div>
      <div class="label">kWh produits/an</div></div>
    <div class="kpi-card"><div class="value">{data.payback_years:.1f} ans</div>
      <div class="label">Retour sur invest.</div></div>
    <div class="kpi-card"><div class="value">{data.roi_25yr_pct:.0f}%</div>
      <div class="label">ROI 25 ans</div></div>
  </div>
  <div class="card"><h2>Production Mensuelle (kWh)</h2>
    <div class="chart-container"><canvas id="productionChart"></canvas></div></div>
  <div class="card"><h2>Économies SENELEC Mensuelles (FCFA)</h2>
    <div class="chart-container"><canvas id="savingsChart"></canvas></div></div>
  <div class="card"><h2>Flux de Trésorerie Cumulé — 25 ans (FCFA)</h2>
    <div class="chart-container"><canvas id="cashflowChart"></canvas></div></div>
  <div class="card"><h2>Intervalles de Confiance Monte Carlo (P10/P50/P90)</h2>
    <div class="chart-container"><canvas id="monteCarloChart"></canvas></div></div>
  <div class="card"><h2>Analyse de Sensibilité — Prix de l'Électricité</h2>
    <table><thead><tr><th class="text-center">Variation Prix</th>
      <th class="text-right">Économies/an</th>
      <th class="text-center">Retour (ans)</th>
      <th class="text-center">ROI 25 ans</th></tr></thead>
    <tbody>{_sensitivity_rows(data.sensitivity)}</tbody></table></div>
  <div class="card"><h2>Matrice de Contrôle Qualité</h2>
    <table><thead><tr><th>Code</th><th>Critère</th><th>Statut</th>
      <th>Valeur</th><th>Seuil</th><th>Commentaire</th></tr></thead>
    <tbody>{_qa_rows(data.qa_criteria)}</tbody></table></div>
  <div class="card"><h2>Analyse Technique — Synthèse IA</h2>{narrative}</div>
  {qr_section}
</div>
<script>
const MONTHS = {json.dumps(MONTHS_FR)};
const MONTHLY_KWH = {json.dumps(monthly_kwh)};
const MONTHLY_SAVINGS = {json.dumps(monthly_savings)};
const CF_YEARS = {json.dumps(cf_years)};
const CF_VALUES = {json.dumps(cf_values)};
const MC_P10 = {json.dumps(mc_p10)};
const MC_P50 = {json.dumps(mc_p50)};
const MC_P90 = {json.dumps(mc_p90)};
const opts = {{responsive:true, maintainAspectRatio:false}};
new Chart(document.getElementById('productionChart'), {{type:'bar',
  data:{{labels:MONTHS,datasets:[{{label:'Production (kWh)',data:MONTHLY_KWH,
  backgroundColor:'#f59e0b',borderRadius:4}}]}},
  options:{{...opts,plugins:{{legend:{{display:false}}}}}}}});
new Chart(document.getElementById('savingsChart'), {{type:'line',
  data:{{labels:MONTHS,datasets:[{{label:'Économies (FCFA)',data:MONTHLY_SAVINGS,
  borderColor:'#10b981',backgroundColor:'rgba(16,185,129,.1)',fill:true,tension:.4}}]}},
  options:{{...opts,plugins:{{legend:{{display:false}}}}}}}});
new Chart(document.getElementById('cashflowChart'), {{type:'line',
  data:{{labels:CF_YEARS.map(y=>'An '+y),datasets:[{{label:'Flux cumulé (FCFA)',
  data:CF_VALUES,borderColor:'#3b82f6',fill:true,tension:.3,pointRadius:3}}]}},
  options:{{...opts,plugins:{{legend:{{display:false}}}}}}}});
new Chart(document.getElementById('monteCarloChart'), {{type:'line',
  data:{{labels:MONTHS,datasets:[
    {{label:'P10',data:MC_P10,borderColor:'#ef4444',borderDash:[4,2],
     borderWidth:1.5,pointRadius:0,fill:false}},
    {{label:'P50 (médiane)',data:MC_P50,borderColor:'#f59e0b',
     borderWidth:2,pointRadius:3,fill:false}},
    {{label:'P90',data:MC_P90,borderColor:'#10b981',borderDash:[4,2],
     borderWidth:1.5,pointRadius:0,fill:false}}]}},
  options:{{...opts,plugins:{{legend:{{display:true,position:'top'}}}}}}}});
</script>
</body>
</html>"""
