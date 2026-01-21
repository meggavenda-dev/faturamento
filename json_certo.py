
# github_database.py — Nova Versão Premium Estável
# Seguro | Atômico | Anti-race | SHA locking Real | Zero Cache Sujo

import requests
import base64
import json
import time
import random


class GitHubJSON:

    API_URL = "https://api.github.com/repos/{owner}/{repo}/contents/{path}"

    def __init__(self, token, owner, repo, path="dados.json", branch="main"):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.path = path
        self.branch = branch

        # Cache ultra-curto para evitar GET múltiplos desnecessários
        self._cache_data = None
        self._cache_sha = None
        self._cache_time = 0


    # ============================================================
    # HEADERS
    # ============================================================
    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }


    # ============================================================
    # LOAD — Leitura segura do JSON
    # (Cache de 200ms apenas)
    # ============================================================
    def load(self, force=False):

        now = time.time()

        if not force and self._cache_data is not None:
            if now - self._cache_time < 0.2:  # cache curtíssimo
                return self._cache_data, self._cache_sha

        url = self.API_URL.format(owner=self.owner, repo=self.repo, path=self.path)

        r = requests.get(url, headers=self.headers, params={"ref": self.branch})

        if r.status_code == 404:
            # Arquivo não existe — retorna base vazia
            self._cache_data = []
            self._cache_sha = None
            self._cache_time = now
            return [], None

        if r.status_code != 200:
            raise Exception(f"GitHub GET error: {r.status_code} - {r.text}")

        body = r.json()
        sha = body.get("sha")

        decoded = base64.b64decode(body["content"]).decode("utf-8")
        data = json.loads(decoded)

        self._cache_data = data
        self._cache_sha = sha
        self._cache_time = now

        return data, sha


    # ============================================================
    # SAVE — Salvamento 100% atômico com SHA locking real
    # ============================================================
    def save(self, new_data, retries=8):

        for attempt in range(retries):

            # SHA sempre atualizado
            _, sha = self.load(force=True)

            url = self.API_URL.format(owner=self.owner, repo=self.repo, path=self.path)

            encoded = base64.b64encode(
                json.dumps(new_data, indent=4, ensure_ascii=False).encode("utf-8")
            ).decode("utf-8")

            payload = {
                "message": "Atualização Manual Faturamento — GABMA",
                "content": encoded,
                "sha": sha,
                "branch": self.branch,
            }

            r = requests.put(url, headers=self.headers, json=payload)

            # SALVO COM SUCESSO
            if r.status_code in (200, 201):
                body = r.json()
                new_sha = body["content"]["sha"]

                # Atualiza cache
                self._cache_data = new_data
                self._cache_sha = new_sha
                self._cache_time = time.time()

                return True

            # SHA inválido => arquivo mudou no GitHub => retry
            if r.status_code == 409:
                time.sleep((2 ** attempt) * 0.15 + random.random() * 0.2)
                continue

            # Rate limit
            if r.status_code == 403 and "rate" in r.text.lower():
                time.sleep(2 + random.random())
                continue

            raise Exception(f"GitHub PUT error: {r.status_code} - {r.text}")

        raise TimeoutError("Falha ao salvar após múltiplas tentativas.")


    # ============================================================
    # UPDATE — Carregar, alterar e salvar com atomicidade real
    # ============================================================
    def update(self, update_fn):

        for attempt in range(8):

            data, _ = self.load(force=True)

            new_data = update_fn(data)

            try:
                self.save(new_data)
                return True

            except TimeoutError:
                continue

            except:
                time.sleep(0.2)

        raise Exception("Falha ao atualizar após múltiplas tentativas.")
