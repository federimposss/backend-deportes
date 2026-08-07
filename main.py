import os
from flask import Flask, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import base64
import re

app = Flask(__name__)

def obtener_agenda_real():
    url_base = "https://pelotaalibre.st/inicio.php"
    partidos_dict = {}

    # AQUÍ ESTABA EL ERROR: Se agregaron los argumentos de seguridad para Docker
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page.route("**/*.{css,woff,woff2,png,jpg,jpeg,gif}", lambda route: route.abort())

        try:
            page.goto(url_base, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(5000)

            marcos = [page] + page.frames

            for marco in marcos:
                try:
                    html = marco.content()
                    soup = BeautifulSoup(html, "html.parser")

                    bloques = soup.find_all(["div", "tr", "li", "section", "article", "p"])
                    
                    for bloque in bloques:
                        texto_bloque = bloque.get_text(separator=" ", strip=True)
                        
                        horas_en_bloque = re.findall(r'\d{2}:\d{2}', texto_bloque)
                        if len(horas_en_bloque) != 1:
                            continue
                        
                        if " vs " not in texto_bloque.lower() and " - " not in texto_bloque:
                            continue

                        lineas = [l.strip() for l in texto_bloque.split('\n') if len(l.strip()) > 5]
                        titulo_partido = ""
                        for l in lineas:
                            if (re.search(r'\d{2}:\d{2}', l) and ("vs" in l.lower() or " - " in l)) or ":" in l:
                                titulo_partido = l
                                break
                        if not titulo_partido:
                            titulo_partido = lineas[0] if lineas else ""

                        titulo_partido = re.sub(r'(Calidad \d+p|720p|1080p|HD|SD)', '', titulo_partido, flags=re.IGNORECASE)
                        titulo_partido = " ".join(titulo_partido.split()).strip()

                        if len(titulo_partido) > 8:
                            enlaces_bloque = bloque.find_all("a", href=True)
                            canales_partido = []
                            
                            for a in enlaces_bloque:
                                href = a["href"]
                                if "inicio.php" in href or href.startswith("#") or "javascript" in href or not href.strip():
                                    continue
                                    
                                calidad = "SD"
                                etiquetas_texto = a.find_all(["span", "div", "b", "strong"])
                                for etiqueta in etiquetas_texto:
                                    txt_eti = etiqueta.get_text(strip=True).lower()
                                    if any(x in txt_eti for x in ["720p", "1080p", "hd", "4k", "calidad"]):
                                        calidad = etiqueta.get_text(strip=True)
                                        etiqueta.decompose()
                                
                                texto_canal = a.get_text(separator=" ", strip=True)
                                if not texto_canal:
                                    img = a.find("img")
                                    texto_canal = (img.get("alt") or img.get("title") or "Ver Canal") if img else "Ver Canal"
                                
                                texto_canal = " ".join(texto_canal.split())
                                if len(texto_canal) < 2 or "ver enlace" in texto_canal.lower():
                                    continue
                                    
                                url_completa = urljoin(url_base, href)
                                
                                servidor_real = "Desconocido"
                                if "?r=" in url_completa:
                                    try:
                                        codigo_b64 = url_completa.split("?r=")[1].split("&")[0]
                                        codigo_b64 += "=" * ((4 - len(codigo_b64) % 4) % 4)
                                        servidor_real = base64.b64decode(codigo_b64).decode('utf-8')
                                    except Exception:
                                        pass

                                if not any(c["url_original"] == url_completa for c in canales_partido):
                                    canales_partido.append({
                                        "nombre": texto_canal,
                                        "url_original": url_completa,
                                        "servidor": servidor_real,
                                        "calidad": calidad
                                    })
                                    
                            if canales_partido:
                                if titulo_partido not in partidos_dict:
                                    partidos_dict[titulo_partido] = canales_partido
                                else:
                                    for c in canales_partido:
                                        if not any(ex["url_original"] == c["url_original"] for ex in partidos_dict[titulo_partido]):
                                            partidos_dict[titulo_partido].append(c)

                except Exception:
                    continue

        except Exception:
            pass
        finally:
            browser.close()

    lista_final = []
    for partido, canales in partidos_dict.items():
        lista_final.append({
            "partido": partido,
            "canales": canales
        })

    return lista_final

@app.route("/")
def api_agenda():
    try:
        return jsonify(obtener_agenda_real())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
