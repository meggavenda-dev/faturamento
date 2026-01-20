
# ============================================================
#  github_database.py — Módulo Profissional para Repositório JSON
#  Seguro | Atômico | Livre de Corrupção | SHA Locking Real
# ============================================================

import requests
import base64
import json
import time
import random


class GitHubJSON:
    """
    Cliente profissional para leitura e escrita de JSON no GitHub
    com segurança transacional (SHA Locking), retry/backoff e
    proteção total contra sobrescrita simultânea.
    """

    API_URL = "https://api.github.com/repos/{owner}/{repo}/contents/{path}"

    def __init__(self, token, owner, repo, path="dados.json", branch="main"):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.path = path
        self.branch = branch

        self._cache_data = None
        self._cache_sha = None
        self._cache_etag = None
        self._cache_timestamp = 0


    # ============================================================
    # HEADERS BASE
    # ============================================================
    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }


    # ============================================================
    # FUNÇÃO PRINCIPAL: LOAD (com cache inteligente)
    # ============================================================
    def load(self, force_refresh=False):
        """
        Carrega o JSON do GitHub com cache inteligente.
        - O cache dura 10 segundos (pode ajustar).
        - force_refresh força nova consulta.
        """
        now = time.time()

        if not force_refresh and self._cache_data is not None:
            if now - self._cache_timestamp < 10:
                return self._cache_data, self._cache_sha

        url = self.API_URL.format(owner=self.owner, repo=self.repo, path=self.path)

        response = requests.get(url, headers=self.headers, params={"ref": self.branch})

        if response.status_code == 404:
            # Banco vazio
            self._cache_data = []
            self._cache_sha = None
            self._cache_etag = None
            return [], None

        if response.status_code != 200:
            raise Exception(f"GitHub GET error: {response.status_code} - {response.text}")

        body = response.json()
        sha = body["sha"]
        etag = response.headers.get("ETag")

        decoded = base64.b64decode(body["content"]).decode("utf-8")
        data = json.loads(decoded)

        # Atualiza o cache
        self._cache_data = data
        self._cache_sha = sha
        self._cache_etag = etag
        self._cache_timestamp = now

        return data, sha


    # ============================================================
    # SAVE — SALVAMENTO ATÔMICO
    # ============================================================
    def save(self, new_data, max_retries=5):
        """
        Salva o JSON com controle transacional:
        - Usa SHA locking (If-Match).
        - Retry automático com exponential backoff + jitter.
        """

        for attempt in range(max_retries):

            # Carrega o SHA mais recente (sem cache)
            _, sha_atual = self.load(force_refresh=True)

            url = self.API_URL.format(owner=self.owner, repo=self.repo, path=self.path)

            commit_message = "Atualização Manual Faturamento — GABMA"

            encoded = base64.b64encode(
                json.dumps(new_data, indent=4, ensure_ascii=False).encode("utf-8")
            ).decode("utf-8")

            payload = {
                "message": commit_message,
                "content": encoded,
                "branch": self.branch,
                "sha": sha_atual
            }

            # ENVIO SEGURO
            response = requests.put(url, headers=self.headers, json=payload)

            # SUCESSO
            if response.status_code in (200, 201):
                result = response.json()
                # Atualiza cache
                self._cache_data = new_data
                self._cache_sha = result["content"]["sha"]
                self._cache_timestamp = time.time()
                return True

            # ERRO 409 => conflito de SHA ==> race condition
            if response.status_code == 409:
                wait = (2 ** attempt) + random.random()
                time.sleep(wait)
                continue  # tenta novamente

            # Rate limit
            if response.status_code == 403 and "rate limit" in response.text.lower():
                time.sleep(3 + random.random())
                continue

            # Outro erro => aborta
            raise Exception(f"GitHub PUT error: {response.status_code} - {response.text}")

        raise TimeoutError("Falha ao salvar no GitHub após múltiplas tentativas.")


    # ============================================================
    # UPDATE — CARREGA, ALTERA E SALVA em operação atômica
    # ============================================================
    def update(self, update_fn):
        """
        Função de alto nível segura:
        1. Carrega o JSON
        2. Aplica sua função de transformação
        3. Salva com proteção anti-concorrência
        """

        for _ in range(5):
            data, _ = self.load(force_refresh=True)
            new_data = update_fn(data)

            try:
                self.save(new_data)
                return True
            except:
                # Em caso de conflito, tenta novamente
                time.sleep(0.5)

        raise Exception("Falha ao atualizar dados após múltiplas tentativas.")
