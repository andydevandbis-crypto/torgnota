"""
scrapa_allt.py - Scrapar alla butiker och sparar ratt material.
Kor: python scrapa_allt.py
"""
import os, sys, json, time, re
import requests

BAS = os.path.dirname(os.path.abspath(__file__))
UT = os.path.join(BAS, "scraping_test", "scrapingv01")
os.makedirs(UT, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def spara(namn, data, mapp):
    väg = os.path.join(UT, mapp, namn)
    with open(väg, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Sparad: {mapp}/{namn} ({len(data) if hasattr(data, '__len__') else '?'})")


def spara_text(namn, text, mapp):
    väg = os.path.join(UT, mapp, namn)
    with open(väg, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  Sparad: {mapp}/{namn} ({len(text)} tecken)")


# ============================================================
# COOP
# ============================================================
def scrapa_coop():
    print("\n=== COOP ===")
    NYCKEL = "3becf0ce306f41a1ae94077c16798187"
    STORE = "105760"  # Coop Lund
    url = f"https://external.api.coop.se/dke/offers/sorting-groups/{STORE}?api-version=v3&clustered=true&grouped=true"
    headers = {**HEADERS, "Ocp-Apim-Subscription-Key": NYCKEL}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            spara("erbjudanden.json", r.json(), "coop")
        else:
            print(f"  Status: {r.status_code}")
    except Exception as e:
        print(f"  Fel: {e}")


# ============================================================
# WILLYS
# ============================================================
def scrapa_willys():
    print("\n=== WILLYS ===")
    from playwright.sync_api import sync_playwright
    url = "https://reklamblad.willys.se/willys/2863-next/"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(user_agent=HEADERS["User-Agent"]).new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)
            settings = page.evaluate("() => window.staticSettings")
            browser.close()

        if not settings:
            print("  Kunde inte hitta window.staticSettings")
            return

        sidor = settings.get("pageTexts", [])
        text = ""
        for i, s in enumerate(sidor, 1):
            text += f"--- Sida {i} ---\n{s}\n\n"
        spara_text("text.txt", text, "willys")
    except Exception as e:
        print(f"  Fel: {e}")


# ============================================================
# LIDL
# ============================================================
def scrapa_lidl():
    print("\n=== LIDL ===")
    url = "https://endpoints.leaflets.schwarz/v4/overview?client_locale=lidl/sv-SE"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        data = r.json()
    except Exception as e:
        print(f"  Fel vid overview: {e}")
        return

    # Valj senaste flyer per unikt flyer_identifier
    valda = {}
    for kat in data.get("categories", []):
        for sub in kat.get("subcategories", []):
            for flyer in sub.get("flyers", []):
                fid = flyer.get("flyerJson")
                if fid and fid not in valda:
                    valda[fid] = flyer

    print(f"  Hittade {len(valda)} unika flyers")
    for i, (fid, flyer) in enumerate(valda.items(), 1):
        namn = flyer.get("name", f"flyer_{i}")
        print(f"  [{i}] {namn}")
        # Hämta flyerJson for att fa sid-URL:er
        try:
            r = requests.get(fid, headers=HEADERS, timeout=30)
            fj = r.json()
        except Exception as e:
            print(f"     Fel: {e}")
            continue

        sidor = fj.get("flyer", {}).get("pages", [])
        mapp = os.path.join(UT, "lidl", f"flyer_{i:02d}")
        os.makedirs(mapp, exist_ok=True)
        for j, sida in enumerate(sidor, 1):
            bild_url = sida.get("zoom") or sida.get("image")
            if not bild_url:
                continue
            try:
                rb = requests.get(bild_url, headers=HEADERS, timeout=30)
                with open(os.path.join(mapp, f"sida_{j:02d}.jpg"), "wb") as f:
                    f.write(rb.content)
            except Exception as e:
                print(f"     Sida {j}: {e}")
        print(f"     {len(sidor)} sidor sparade")


# ============================================================
# ICA
# ============================================================
def scrapa_ica():
    print("\n=== ICA ===")
    from playwright.sync_api import sync_playwright

    butiker = [
        "https://www.ica.se/butiker/kvantum/lund/ica-kvantum-brunnshog-1086002/",
        "https://www.ica.se/butiker/supermarket/lund/ica-supermarket-faladstorget-1004223/",
        "https://www.ica.se/butiker/nara/lund/ica-nara-jagaren-lund-1004475/",
        "https://www.ica.se/butiker/maxi/lund/maxi-ica-stormarknad-gunnesbo-lund-1088004/",
        "https://www.ica.se/butiker/supermarket/kavlinge/ica-supermarket-kavlinge-1003379/",
        "https://www.ica.se/butiker/supermarket/lund/ica-supermarket-linero-torg-1004598/",
        "https://www.ica.se/butiker/kvantum/lund/ica-kvantum-malmborgs-clemenstorget-1004409/",
        "https://www.ica.se/butiker/kvantum/lund/ica-kvantum-malmborgs-tuna-1003391/",
        "https://www.ica.se/butiker/nara/lund/ica-nara-satelliten-1003508/",
        "https://www.ica.se/butiker/kvantum/lund/ica-kvantum-sodra-sandby-1003452/",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=HEADERS["User-Agent"]).new_page()

        for url in butiker:
            namn = url.split("/")[-2]
            print(f"  {namn}")
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(2)

                emagin = None
                lankar = page.eval_on_selector_all("a", "els => els.map(e => e.href)")
                for l in lankar:
                    if "e-magin.se" in l and "latestpaper" in l:
                        emagin = l
                        break
                if not emagin:
                    content = page.content()
                    m = re.search(r'https://www\.e-magin\.se/latestpaper/[a-z0-9]+/paper/1', content)
                    if m:
                        emagin = m.group(0)
                if not emagin:
                    print(f"     Ingen e-magin-lank")
                    continue

                page.goto(emagin, wait_until="networkidle", timeout=60000)
                time.sleep(2)
                with page.expect_download() as dl:
                    page.click("button:has-text('Ladda ner PDF')", timeout=30000)
                download = dl.value
                utfil = os.path.join(UT, "ica", download.suggested_filename)
                download.save_as(utfil)
                print(f"     Sparad: {download.suggested_filename}")
            except Exception as e:
                print(f"     Fel: {str(e)[:80]}")

        browser.close()


# ============================================================
if __name__ == "__main__":
    print(f"Sparar allt i: {UT}")
    scrapa_coop()
    scrapa_willys()
    scrapa_lidl()
    scrapa_ica()
    print("\nKlart!")
