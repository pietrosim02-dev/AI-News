"""
AI Pulse — fetch_news.py
Viene eseguito da GitHub Actions ogni mattina.
Usa l'SDK Anthropic + web_search per raccogliere notizie,
poi genera un file HTML statico in ./output/index.html
"""

import anthropic
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Config ────────────────────────────────────────────────
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

# Ora italiana (UTC+2 ora legale, UTC+1 ora solare)
# GitHub Actions gira in UTC, aggiungiamo offset manuale
now_utc = datetime.now(timezone.utc)
now_it  = now_utc + timedelta(hours=2)
TODAY   = now_it.strftime("%d/%m/%Y")
TODAY_LONG = now_it.strftime("%A %d %B %Y")

SOURCES = [
    {
        "cat": "anthropic",
        "icon": "🤖",
        "label": "Anthropic / Claude",
        "query": f"Cerca le ultime notizie su Anthropic e Claude (nuovi modelli, API updates, annunci ufficiali) di oggi o questa settimana. Data: {TODAY}.",
    },
    {
        "cat": "github",
        "icon": "⭐",
        "label": "GitHub Trending AI",
        "query": f"Cerca i repository GitHub più trending nel campo AI e LLM in questo momento ({TODAY}). Includi stelle se disponibili.",
    },
    {
        "cat": "news",
        "icon": "📰",
        "label": "Notizie AI generali",
        "query": f"Cerca le principali notizie AI di oggi {TODAY}: nuovi modelli, aziende, prodotti, ricerche importanti.",
    },
    {
        "cat": "papers",
        "icon": "📄",
        "label": "Paper & Ricerca",
        "query": f"Cerca i paper AI/ML più recenti e rilevanti pubblicati questa settimana su arxiv o simili.",
    },
]

SYSTEM_PROMPT = """Sei un aggregatore di notizie AI.
Quando cerchi notizie, rispondi SOLO con un array JSON valido.
Niente markdown, niente backtick, niente testo aggiuntivo prima o dopo.
Ogni oggetto ha:
- title: titolo (stringa)
- summary: riassunto in italiano, max 130 caratteri (stringa)
- url: URL diretto (stringa, usa "#" se non disponibile)
- time: quando pubblicato (es. "oggi", "ieri", "2 giorni fa")
- stars: stelle GitHub (solo per repo, es. "23k", altrimenti null)"""


def fetch_category(source: dict) -> list[dict]:
    """Chiama Claude con web_search per una categoria di notizie."""
    print(f"  → Fetching: {source['label']}...")
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{
                "role": "user",
                "content": f"{source['query']}\n\nRestituisci 5-6 risultati come array JSON."
            }]
        )

        # Estrai il testo dalla risposta
        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        # Trova e parsa l'array JSON
        text_clean = re.sub(r"```json|```", "", text).strip()
        match = re.search(r"\[[\s\S]*?\]", text_clean)
        if not match:
            print(f"    ⚠ Nessun JSON trovato per {source['label']}")
            return []

        items = json.loads(match.group(0))
        result = []
        for i, item in enumerate(items[:6]):
            result.append({
                "id": f"{source['cat']}-{i}",
                "cat": source["cat"],
                "icon": source["icon"],
                "title": item.get("title", "Senza titolo"),
                "summary": item.get("summary", ""),
                "url": item.get("url", "#"),
                "time": item.get("time", "oggi"),
                "stars": item.get("stars"),
            })
        print(f"    ✓ {len(result)} notizie trovate")
        return result

    except Exception as e:
        print(f"    ✗ Errore: {e}")
        return []


def build_html(items: list[dict]) -> str:
    """Genera l'HTML statico con le notizie del giorno."""

    def card_html(item, idx):
        stars_html = f'<span class="stars">★ {item["stars"]}</span>' if item.get("stars") else ""
        summary_html = f'<div class="card-summary">{item["summary"]}</div>' if item.get("summary") else ""
        url_display = item["url"].replace("https://", "")[:52] if item["url"] != "#" else "— link non disponibile"
        delay = idx * 0.04

        return f"""
    <div class="card" data-cat="{item['cat']}" style="animation-delay:{delay}s" onclick="openUrl('{item['url']}')">
      <div class="card-header">
        <span class="card-icon">{item['icon']}</span>
        <div class="card-title">{item['title']}</div>
      </div>
      <div class="card-meta">
        <span class="cat-tag {item['cat']}">{item['cat']}</span>
        <span class="card-time">{item['time']}</span>
      </div>
      {summary_html}
      <div class="card-footer">
        <a class="card-link" href="{item['url']}" target="_blank" onclick="event.stopPropagation()">{url_display}</a>
        {stars_html}
      </div>
    </div>"""

    cards = "\n".join(card_html(item, i) for i, item in enumerate(items))
    items_json = json.dumps(items, ensure_ascii=False)

    n_anthropic = sum(1 for i in items if i["cat"] == "anthropic")
    n_github    = sum(1 for i in items if i["cat"] == "github")
    n_other     = sum(1 for i in items if i["cat"] in ("news", "papers"))
    generated_at = now_it.strftime("%H:%M")

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Pulse — {TODAY}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap');
  :root{{--bg:#080c10;--surface:#0d1219;--card:#111822;--border:#1e2d3d;--accent:#00e5ff;--accent2:#ff6b35;--accent3:#a259ff;--text:#e2eaf3;--muted:#5a7a99;--success:#00ff9d;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:var(--bg);color:var(--text);font-family:'Syne',sans-serif;min-height:100vh;overflow-x:hidden;}}
  body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,229,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,229,255,0.03) 1px,transparent 1px);background-size:40px 40px;pointer-events:none;z-index:0;}}
  .orb{{position:fixed;border-radius:50%;filter:blur(80px);pointer-events:none;z-index:0;}}
  .orb1{{width:400px;height:400px;background:rgba(0,229,255,0.06);top:-100px;right:-100px;animation:drift 12s ease-in-out infinite;}}
  .orb2{{width:300px;height:300px;background:rgba(162,89,255,0.06);bottom:100px;left:-80px;animation:drift 15s ease-in-out infinite reverse;}}
  @keyframes drift{{0%,100%{{transform:translate(0,0)}}50%{{transform:translate(30px,30px)}}}}
  .container{{position:relative;z-index:1;max-width:1200px;margin:0 auto;padding:0 24px;}}
  header{{border-bottom:1px solid var(--border);padding:20px 0;position:sticky;top:0;background:rgba(8,12,16,0.94);backdrop-filter:blur(16px);z-index:100;}}
  .header-inner{{display:flex;align-items:center;gap:16px;flex-wrap:wrap;}}
  .logo{{font-family:'Space Mono',monospace;font-size:1.1rem;font-weight:700;display:flex;align-items:center;gap:10px;}}
  .logo-dot{{width:10px;height:10px;border-radius:50%;background:var(--accent);box-shadow:0 0 12px var(--accent);}}
  .date-badge{{font-family:'Space Mono',monospace;font-size:0.7rem;color:var(--accent);border:1px solid rgba(0,229,255,0.3);padding:4px 10px;border-radius:2px;}}
  .gen-badge{{margin-left:auto;font-family:'Space Mono',monospace;font-size:0.68rem;color:var(--muted);}}
  .gen-badge span{{color:var(--success);}}
  .day-banner{{margin:28px 0 20px;padding:20px 24px;background:linear-gradient(135deg,rgba(0,229,255,0.05),rgba(162,89,255,0.05));border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:6px;}}
  .day-title{{font-size:1.3rem;font-weight:800;}}
  .day-subtitle{{font-family:'Space Mono',monospace;font-size:0.72rem;color:var(--muted);margin-top:4px;}}
  .stats-bar{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--border);border:1px solid var(--border);margin-bottom:24px;border-radius:6px;overflow:hidden;}}
  .stat{{background:var(--surface);padding:14px 18px;}}
  .stat-label{{font-family:'Space Mono',monospace;font-size:0.62rem;color:var(--muted);letter-spacing:0.08em;text-transform:uppercase;margin-bottom:5px;}}
  .stat-value{{font-size:1.5rem;font-weight:800;line-height:1;}}
  .cyan{{color:var(--accent);text-shadow:0 0 20px rgba(0,229,255,0.3);}}
  .orange{{color:var(--accent2);text-shadow:0 0 20px rgba(255,107,53,0.3);}}
  .purple{{color:var(--accent3);text-shadow:0 0 20px rgba(162,89,255,0.3);}}
  .green{{color:var(--success);text-shadow:0 0 20px rgba(0,255,157,0.3);}}
  .controls{{display:flex;gap:10px;margin-bottom:24px;flex-wrap:wrap;align-items:center;}}
  .search-box{{flex:1;min-width:200px;background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:10px 16px;color:var(--text);font-family:'Space Mono',monospace;font-size:0.8rem;outline:none;transition:border-color 0.2s;}}
  .search-box:focus{{border-color:var(--accent);}}
  .search-box::placeholder{{color:var(--muted);}}
  .filter-btn{{background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:10px 14px;border-radius:4px;cursor:pointer;font-family:'Space Mono',monospace;font-size:0.72rem;transition:all 0.2s;white-space:nowrap;}}
  .filter-btn.active[data-cat="all"]{{border-color:var(--text);color:var(--text);background:rgba(255,255,255,0.05);}}
  .filter-btn.active[data-cat="anthropic"]{{border-color:var(--accent);color:var(--accent);background:rgba(0,229,255,0.07);}}
  .filter-btn.active[data-cat="github"]{{border-color:var(--accent2);color:var(--accent2);background:rgba(255,107,53,0.07);}}
  .filter-btn.active[data-cat="news"]{{border-color:var(--accent3);color:var(--accent3);background:rgba(162,89,255,0.07);}}
  .filter-btn.active[data-cat="papers"]{{border-color:var(--success);color:var(--success);background:rgba(0,255,157,0.07);}}
  .feed-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;padding-bottom:48px;}}
  .card{{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:20px;transition:all 0.25s;cursor:pointer;position:relative;overflow:hidden;animation:fadeUp 0.35s ease both;}}
  @keyframes fadeUp{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
  .card:hover{{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,229,255,0.07);}}
  .card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;}}
  .card[data-cat="anthropic"]::before{{background:var(--accent);}}
  .card[data-cat="github"]::before{{background:var(--accent2);}}
  .card[data-cat="news"]::before{{background:var(--accent3);}}
  .card[data-cat="papers"]::before{{background:var(--success);}}
  .card-header{{display:flex;gap:12px;margin-bottom:12px;align-items:flex-start;}}
  .card-icon{{font-size:1.1rem;flex-shrink:0;margin-top:2px;}}
  .card-title{{font-size:0.93rem;font-weight:700;line-height:1.4;}}
  .card-meta{{display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap;}}
  .cat-tag{{font-family:'Space Mono',monospace;font-size:0.6rem;letter-spacing:0.08em;text-transform:uppercase;padding:3px 8px;border-radius:2px;font-weight:700;}}
  .cat-tag.anthropic{{color:var(--accent);background:rgba(0,229,255,0.1);border:1px solid rgba(0,229,255,0.2);}}
  .cat-tag.github{{color:var(--accent2);background:rgba(255,107,53,0.1);border:1px solid rgba(255,107,53,0.2);}}
  .cat-tag.news{{color:var(--accent3);background:rgba(162,89,255,0.1);border:1px solid rgba(162,89,255,0.2);}}
  .cat-tag.papers{{color:var(--success);background:rgba(0,255,157,0.1);border:1px solid rgba(0,255,157,0.2);}}
  .card-time{{font-family:'Space Mono',monospace;font-size:0.65rem;color:var(--muted);}}
  .card-summary{{font-size:0.82rem;color:#8aaccc;line-height:1.6;}}
  .card-footer{{margin-top:14px;display:flex;gap:8px;align-items:center;}}
  .card-link{{font-family:'Space Mono',monospace;font-size:0.65rem;color:var(--muted);text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;transition:color 0.2s;}}
  .card-link:hover{{color:var(--accent);}}
  .stars{{margin-left:auto;font-family:'Space Mono',monospace;font-size:0.7rem;color:#f0a500;white-space:nowrap;}}
  .empty{{grid-column:1/-1;text-align:center;padding:60px;color:var(--muted);font-family:'Space Mono',monospace;font-size:0.8rem;}}
  ::-webkit-scrollbar{{width:5px;}} ::-webkit-scrollbar-track{{background:var(--bg);}} ::-webkit-scrollbar-thumb{{background:var(--border);border-radius:3px;}}
  @media(max-width:600px){{.stats-bar{{grid-template-columns:repeat(2,1fr)}}.feed-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<div class="orb orb1"></div>
<div class="orb orb2"></div>

<header>
  <div class="container">
    <div class="header-inner">
      <div class="logo"><span class="logo-dot"></span>AI_PULSE</div>
      <div class="date-badge">{TODAY}</div>
      <div class="gen-badge">generato alle <span>{generated_at}</span></div>
    </div>
  </div>
</header>

<div class="container">
  <div class="day-banner">
    <div class="day-title">Notizie AI — {TODAY_LONG}</div>
    <div class="day-subtitle">{len(items)} notizie raccolte · aggiornato alle {generated_at} · prossimo aggiornamento domani mattina</div>
  </div>

  <div class="stats-bar">
    <div class="stat"><div class="stat-label">Totale</div><div class="stat-value cyan">{len(items)}</div></div>
    <div class="stat"><div class="stat-label">Anthropic</div><div class="stat-value orange">{n_anthropic}</div></div>
    <div class="stat"><div class="stat-label">GitHub</div><div class="stat-value purple">{n_github}</div></div>
    <div class="stat"><div class="stat-label">News + Paper</div><div class="stat-value green">{n_other}</div></div>
  </div>

  <div class="controls">
    <input class="search-box" id="searchBox" type="text" placeholder="Cerca tra le notizie di oggi...">
    <button class="filter-btn active" data-cat="all">Tutto</button>
    <button class="filter-btn" data-cat="anthropic">🤖 Anthropic</button>
    <button class="filter-btn" data-cat="github">⭐ GitHub</button>
    <button class="filter-btn" data-cat="news">📰 Notizie</button>
    <button class="filter-btn" data-cat="papers">📄 Paper</button>
  </div>

  <div class="feed-grid" id="feedGrid">{cards}</div>
</div>

<script>
const ALL_ITEMS = {items_json};
let activeFilter = 'all', searchQuery = '';

function render() {{
  let items = [...ALL_ITEMS];
  if (activeFilter !== 'all') items = items.filter(i => i.cat === activeFilter);
  if (searchQuery) {{
    const q = searchQuery.toLowerCase();
    items = items.filter(i => i.title.toLowerCase().includes(q) || i.summary.toLowerCase().includes(q));
  }}
  const grid = document.getElementById('feedGrid');
  if (!items.length) {{ grid.innerHTML = '<div class="empty">🔍 Nessun risultato</div>'; return; }}
  grid.innerHTML = items.map((item, idx) => `
    <div class="card" data-cat="${{item.cat}}" style="animation-delay:${{idx*0.04}}s" onclick="openUrl('${{item.url}}')">
      <div class="card-header"><span class="card-icon">${{item.icon}}</span><div class="card-title">${{item.title}}</div></div>
      <div class="card-meta"><span class="cat-tag ${{item.cat}}">${{item.cat}}</span><span class="card-time">${{item.time}}</span></div>
      ${{item.summary ? '<div class="card-summary">'+item.summary+'</div>' : ''}}
      <div class="card-footer">
        <a class="card-link" href="${{item.url}}" target="_blank" onclick="event.stopPropagation()">${{item.url==='#'?'—':item.url.replace('https://','').slice(0,52)}}</a>
        ${{item.stars ? '<span class="stars">★ '+item.stars+'</span>' : ''}}
      </div>
    </div>`).join('');
}}

document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active'); activeFilter = btn.dataset.cat; render();
  }});
}});
document.getElementById('searchBox').addEventListener('input', e => {{ searchQuery = e.target.value.trim(); render(); }});
function openUrl(u) {{ if (u && u !== '#') window.open(u, '_blank'); }}
</script>
</body>
</html>"""


def main():
    print(f"\n🚀 AI Pulse — fetch notizie del {TODAY}")
    print("=" * 50)

    all_items = []
    for source in SOURCES:
        items = fetch_category(source)
        all_items.extend(items)

    print(f"\n✅ Totale: {len(all_items)} notizie raccolte")
    print("📄 Generazione HTML...")

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    html = build_html(all_items)
    (output_dir / "index.html").write_text(html, encoding="utf-8")

    # Salva anche il JSON grezzo per debug
    (output_dir / "data.json").write_text(
        json.dumps({"date": TODAY, "generated_at": now_it.isoformat(), "items": all_items}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"✅ output/index.html generato ({len(html):,} bytes)")
    print("🎉 Fatto!")


if __name__ == "__main__":
    main()
