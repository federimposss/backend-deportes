import streamlit as st
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import base64
import re
import json

def obtener_agenda_real():
    url_base = "https://pelotaalibre.st/inicio.php"
    partidos_dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
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

                    bloques = soup.find_all(["div", "tr", "li", "section", "article"])
                    
                    for bloque in bloques:
                        texto_bloque = bloque.get_text(separator=" ", strip=True)
                        
                        tiene_hora = bool(re.search(r'\d{2}:\d{2}', texto_bloque))
                        tiene_vs = " vs " in texto_bloque.lower() or " - " in texto_bloque
                        
                        if tiene_hora and tiene_vs:
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

        except Exception as e:
            st.error(f"Error al analizar la agenda: {e}")
        finally:
            browser.close()

    lista_final = []
    for partido, canales in partidos_dict.items():
        lista_final.append({
            "partido": partido,
            "canales": canales
        })

    return lista_final


def interceptar_m3u8(url_reproductor):
    m3u8_link = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--disable-web-security",
                "--mute-audio"
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720},
            extra_http_headers={"Referer": "https://pelotaalibre.st/"}
        )
        page = context.new_page()

        def manejar_peticion(request):
            nonlocal m3u8_link
            if ".m3u8" in request.url and not m3u8_link:
                m3u8_link = request.url

        page.on("request", manejar_peticion)

        try:
            page.goto(url_reproductor, wait_until="domcontentloaded", timeout=15000)
            
            page.evaluate("""
                setInterval(() => {
                    document.querySelectorAll('div').forEach(d => {
                        if(d.style.zIndex > 100) d.remove();
                    });
                    document.querySelectorAll('video').forEach(v => {
                        v.muted = true;
                        v.play().catch(e => {});
                    });
                }, 500);
            """)

            for _ in range(3):
                if m3u8_link: break
                try: page.mouse.click(640, 360)
                except: pass
                page.wait_for_timeout(300)

            for _ in range(80):
                if m3u8_link: break
                page.wait_for_timeout(100)

        except Exception:
            pass 
        finally:
            browser.close()
            
    return m3u8_link


# --- SOPORTE PARA API JSON (Para la APK) ---
# Si abres la URL con el parámetro ?api=true, Streamlit devolverá el JSON puro en lugar de la web
query_params = st.query_params
if "api" in query_params:
    st.json(obtener_agenda_real())
    st.stop()


# --- INTERFAZ STREAMLIT (Para la Web) ---
st.set_page_config(page_title="Agenda Deportiva", page_icon="⚽", layout="centered")

st.markdown("""
<style>
    .stButton button { width: 100%; }
    .canal-calidad { color: #888; font-size: 0.95em; text-align: center; margin-top: 8px;}
</style>
""", unsafe_allow_html=True)

st.title("⚽ Agenda de Partidos")

# Aviso útil para ti en la web
st.info("💡 **Consejo:** Tu APK debe conectarse a: `https://backend-deportes-55vi.onrender.com/?api=true`")

if "agenda" not in st.session_state:
    st.session_state.agenda = []

if st.button("🔄 Cargar Partidos de Hoy"):
    with st.spinner("Escaneando la agenda..."):
        st.session_state.agenda = obtener_agenda_real()
    if st.session_state.agenda:
        st.success(f"¡Se encontraron {len(st.session_state.agenda)} partidos!")
    else:
        st.warning("No se encontraron partidos activos.")

for i, evento in enumerate(st.session_state.agenda):
    with st.expander(f"🏅 {evento['partido']}"):
        for j, canal in enumerate(evento['canales']):
            
            col1, col2, col3 = st.columns([3, 2, 3])
            
            with col1:
                st.markdown(f"**▶ {canal['nombre']}**")
                if canal['servidor'] != "Desconocido":
                    st.caption(f"Servidor: {canal['servidor']}")
            
            with col2:
                st.markdown(f"<div class='canal-calidad'><i>{canal['calidad']}</i></div>", unsafe_allow_html=True)
            
            with col3:
                if st.button(f"🔍 Extraer .m3u8", key=f"btn_m3u8_{i}_{j}"):
                    with st.spinner("Interceptando enlace..."):
                        m3u8_url = interceptar_m3u8(canal['url_original'])
                        
                        if m3u8_url:
                            st.success("✅ Enlace capturado")
                            st.code(m3u8_url, language="text")
                            reproductor_prueba = f"https://hlsjs.video-dev.org/demo/?src={quote(m3u8_url)}"
                            st.markdown(f"[▶️ Probar el m3u8 en reproductor web]({reproductor_prueba})")
                        else:
                            st.error("No se pudo interceptar el enlace.")
            
            st.divider()