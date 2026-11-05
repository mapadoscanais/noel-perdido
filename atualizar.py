#!/usr/bin/env python3
"""Regenera dados.json a partir dos comentarios-*.json e episodios/epNN/ep.json e publica (git push).
Uso: python3 site/atualizar.py [--sem-push]. Regras: só cidade (nunca endereço), só @, quem comentou SAIR sai."""
import json, glob, os, re, subprocess, sys, time, urllib.request, urllib.parse
AQUI = os.path.dirname(os.path.abspath(__file__)); RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(RAIZ, "molde"))
from cidades import achar, chave

CACHE = os.path.join(AQUI, "cidades_exterior.json")
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
_ult = [0.0]
def exterior(cidade, pais):
    """(lat, lon, país, código) de cidade fora do Brasil; cache em cidades_exterior.json, Nominatim a 1 consulta/s."""
    k = chave(cidade) + "|" + chave(pais)
    if k not in cache:
        time.sleep(max(0, 1.1 - (time.time() - _ult[0]))); _ult[0] = time.time()
        q = urllib.parse.urlencode(dict(format="json", limit=1, addressdetails=1, q=f"{cidade}, {pais}" if pais else cidade))
        rq = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q, headers={"User-Agent": "noel-perdido-mapa/1.0 (mapadoscanais.github.io/noel-perdido)"})
        try: r = json.load(urllib.request.urlopen(rq, timeout=20))
        except Exception as e: print("falhou", cidade, pais, e); return None
        if not r: print("não achei", cidade, pais); return None
        ad = r[0].get("address", {})
        cache[k] = [round(float(r[0]["lat"]), 2), round(float(r[0]["lon"]), 2), ad.get("country", pais), ad.get("country_code", "").upper()]
        json.dump(cache, open(CACHE, "w"), ensure_ascii=False, indent=0)
    return cache[k]
def separa_exterior(cidade, uf, pais):
    # fora do Brasil: campo "pais", ou cidade "Lisboa, Portugal" sem UF
    if pais and chave(pais) not in ("brasil", "brazil", "br"): return cidade, pais
    if not uf and not pais and "," in cidade: c, _, p = cidade.rpartition(","); return c.strip(), p.strip()
    return None

pessoas, sair, segue_arr, segue_cid = {}, set(), {}, set()
def ep_de(caminho):
    m = re.search(r"ep(\d+)", caminho); return int(m.group(1)) if m else 0

# 1) quem segue, pelos ep.json (@ exato; nome sem @ vale pela cidade+UF)
for f in sorted(glob.glob(os.path.join(RAIZ, "episodios", "ep[0-9]*", "ep.json"))):
    for p in json.load(open(f)).get("pessoas", []):
        n, ok = p["nome"], bool(p.get("segue"))
        if n.startswith("@"):
            segue_arr[n.lower()] = ok
            if p.get("cidade"): pessoas.setdefault(n.lower(), dict(arroba=n, rede="Instagram", cidade=p["cidade"], uf=p.get("uf", ""), ep=ep_de(f)))
        elif ok: segue_cid.add((chave(p["cidade"]), p.get("uf", "")))

# 2) comentários (cidade vem do comentário; sem cidade não entra)
for f in sorted(glob.glob(os.path.join(RAIZ, "comentarios-*.json")) + glob.glob(os.path.join(RAIZ, "episodios", "ep[0-9]*", "comentarios*.json"))):
    ep = ep_de(os.path.basename(f)) if "comentarios-ep" in f else ep_de(f)
    for c in json.load(open(f))["comentarios"]:
        a = c["nome"].lower()
        if re.search(r"\bsair\b", c.get("texto", ""), re.I): sair.add(a); continue
        if c.get("cidade"): pessoas.setdefault(a, dict(arroba=c["nome"], rede=c["rede"], cidade=c["cidade"], uf=c.get("uf") or "", pais=c.get("pais") or "", ep=ep))

out = []
for a, p in pessoas.items():
    if a in sair: continue
    ex = separa_exterior(p["cidade"], p["uf"], p.get("pais", ""))
    if ex:
        g = exterior(*ex)
        if not g: continue  # sem coordenada: fica de fora até o próximo rodada
        out.append(dict(arroba=p["arroba"], rede=p["rede"], cidade=ex[0], uf="", pais=g[2], cc=g[3], lat=g[0], lon=g[1], ep=p["ep"], segue=segue_arr.get(a, False)))
        continue
    nome, uf, la, lo, _ = achar(p["cidade"], p["uf"])
    ok = segue_arr.get(a, p["rede"] == "Instagram" and (chave(p["cidade"]), p["uf"]) in segue_cid)
    out.append(dict(arroba=p["arroba"], rede=p["rede"], cidade=nome or p["cidade"], uf=uf, lat=la, lon=lo, ep=p["ep"], segue=ok))
json.dump(out, open(os.path.join(AQUI, "dados.json"), "w"), ensure_ascii=False, indent=0)
assert separa_exterior("Lisboa, Portugal", "", "") == ("Lisboa", "Portugal") and separa_exterior("Fortaleza", "CE", "") is None
print(len({o.get("pais") for o in out if o.get("pais")}), "países;", len(out), "pessoas,", sum(o["segue"] for o in out), "acesas,", len({(o["cidade"], o["uf"]) for o in out}), "cidades")
if "--sem-push" not in sys.argv:
    sh = lambda *c: subprocess.run(c, cwd=AQUI, check=False)
    sh("git", "add", "-A"); sh("git", "commit", "-m", "atualiza mapa"); sh("git", "push")
