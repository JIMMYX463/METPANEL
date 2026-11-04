// Intermediario para PANEL METEO (Cloudflare Workers).
// Pide en el momento los METAR y TAF a aviationweather.gov y los devuelve al panel.
// Uso: https://<tu-worker>.workers.dev/?ids=LEBZ,LPBJ,LEMO
const ORIGINS = ["https://jimmyx463.github.io"];
const API = "https://aviationweather.gov/api/data/";
const UA = "METPANEL dashboard (github.com/JIMMYX463/METPANEL)";

export default {
  async fetch(request) {
    const origin = request.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": ORIGINS.includes(origin) ? origin : ORIGINS[0],
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Vary": "Origin",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "GET") return new Response("Método no permitido", { status: 405, headers: cors });

    const url = new URL(request.url);
    // Solo indicativos OACI (4 letras), máximo 6 por petición
    const ids = [...new Set((url.searchParams.get("ids") || "").toUpperCase().split(",").filter(x => /^[A-Z]{4}$/.test(x)))].slice(0, 6);
    if (!ids.length) return new Response("Faltan indicativos: ?ids=LEBZ,LPBJ,LEMO", { status: 400, headers: cors });

    const get = async (path) => {
      const r = await fetch(API + path, { headers: { "User-Agent": UA }, cf: { cacheTtl: 30, cacheEverything: true } });
      if (!r.ok) throw new Error(path + " → " + r.status);
      return r.text();
    };
    try {
      const q = ids.join(",");
      const [metar, taf] = await Promise.all([get(`metar?ids=${q}&format=raw&hours=2`), get(`taf?ids=${q}&format=raw`)]);
      return new Response(JSON.stringify({ fetched: Math.floor(Date.now() / 1000), metar, taf }), {
        headers: { ...cors, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), { status: 502, headers: { ...cors, "Content-Type": "application/json" } });
    }
  },
};
