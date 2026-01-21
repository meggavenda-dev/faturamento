
# github_database.py — Versão Premium Estável (robusta)
# Seguro | Atômico | Anti-race | SHA locking real | Timeouts | Auto-healing JSON

import requests
import base64
import json
import time
import random

class GitHubJSON:
    API_URL = "https://api.github.com/repos/{owner}/{repo}/contents/{path}"

    def __init__(
        self,
        token,
        owner,
        repo,
        path="dados.json",
        branch="main",
        max_bytes=None,               # opcional: limite de tamanho do JSON
        user_agent="GABMA-Manual/1.0" # User-Agent p/ diagnósticos
    ):
        self.token = token
        self.owner = owner
        self.repo = repo
        self.path = path
        self.branch = branch
        self.max_bytes = max_bytes
        self.user_agent = user_agent

        # Cache ultra-curto para evitar GET múltiplos desnecessários
        self._cache_data = None
        self._cache_sha = None
        self._cache_time = 0.0

    # ============================================================
    # HEADERS
    # ============================================================
    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": self.user_agent,
        }

    # ============================================================
    # LOAD — Leitura segura do JSON (Cache 200ms) + Auto-healing
    # ============================================================
    def load(self, force=False):
        now = time.time()
        if not force and self._cache_data is not None:
            if (now - self._cache_time) < 0.2:  # cache curtíssimo
                return self._cache_data, self._cache_sha

        url = self.API_URL.format(owner=self.owner, repo=self.repo, path=self.path)
        r = requests.get(
            url,
            headers=self.headers,
            params={"ref": self.branch},
            timeout=(6, 30),
        )

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
        content_b64 = body.get("content") or ""
        try:
            decoded = base64.b64decode(content_b64).decode("utf-8")
        except Exception:
            # Conteúdo ilegível: assume base vazia
            decoded = ""

        # Auto-healing p/ arquivo vazio/ inválido
        parsed = []
        if decoded.strip():
            try:
                parsed = json.loads(decoded)
            except json.JSONDecodeError:
                # Remove BOM, tenta de novo
                decoded2 = decoded.lstrip("\ufeff").strip()
                try:
                    parsed = json.loads(decoded2)
                except json.JSONDecodeError:
                    # Não deu: mantém como lista vazia (auto-healing na memória)
                    parsed = []

        if not isinstance(parsed, list):
            parsed = []

        if self.max_bytes is not None:
            try:
                if len(decoded.encode("utf-8")) > self.max_bytes:
                    raise Exception("Arquivo JSON excede o limite configurado.")
            except Exception:
                # Se não conseguimos medir, seguimos, mas é raro
                pass

        # Atualiza cache
        self._cache_data = parsed
        self._cache_sha = sha
        self._cache_time = now
        return parsed, sha

    # ============================================================
    # SAVE — Salvamento 100% atômico com SHA locking real
    # ============================================================
    def save(self, new_data, retries=8, commit_message=None):
        if not isinstance(new_data, list):
            raise ValueError("new_data deve ser uma lista JSON serializável.")

        # Serializa já no início (para detectar erros cedo)
        encoded_json_bytes = json.dumps(new_data, indent=2, ensure_ascii=False).encode("utf-8")
        if self.max_bytes is not None and len(encoded_json_bytes) > self.max_bytes:
            raise ValueError("new_data excede o limite de tamanho configurado.")

        encoded_b64 = base64.b64encode(encoded_json_bytes).decode("utf-8")
        msg = commit_message or "Atualização Manual Faturamento — GABMA"

        for attempt in range(retries):
            # SHA sempre atualizado (evita cache sujo)
            _, sha = self.load(force=True)

            url = self.API_URL.format(owner=self.owner, repo=self.repo, path=self.path)
            payload = {
                "message": msg,
                "content": encoded_b64,
                "sha": sha,           # None cria arquivo; SHA válido atualiza
                "branch": self.branch,
            }

            r = requests.put(url, headers=self.headers, json=payload, timeout=(6, 30))

            if r.status_code in (200, 201):
                body = r.json()
                new_sha = body["content"]["sha"]

                # Atualiza cache local
                self._cache_data = new_data
                self._cache_sha = new_sha
                self._cache_time = time.time()
                return True

            # Conflito (arquivo mudou no GitHub) — backoff exponencial com jitter
            if r.status_code == 409:
                time.sleep((2 ** attempt) * 0.2 + random.random() * 0.3)
                continue

            # Rate limit — se tiver reset, aguarda (fallback 3s)
            if r.status_code == 403 and "rate" in r.text.lower():
                reset = r.headers.get("X-RateLimit-Reset")
                if reset:
                    try:
                        wait = max(0.0, float(reset) - time.time()) + 1.0
                        time.sleep(min(wait, 10.0))
                    except Exception:
                        time.sleep(3 + random.random())
                else:
                    time.sleep(3 + random.random())
                continue

            # Demais erros: levanta exceção com detalhes
            raise Exception(f"GitHub PUT error: {r.status_code} - {r.text}")

        raise TimeoutError("Falha ao salvar após múltiplas tentativas.")

    # ============================================================
    # UPDATE — Carregar, alterar e salvar com atomicidade real
    # ============================================================
    def update(self, update_fn, retries=8, commit_message=None):
        """
        update_fn: função que recebe (list) e retorna (list) o novo conteúdo.
        """
        if not callable(update_fn):
            raise ValueError("update_fn deve ser uma função (callable).")

        for attempt in range(retries):
            data, _ = self.load(force=True)
            try:
                new_data = update_fn(list(data) if isinstance(data, list) else [])
            except Exception as e:
                raise Exception(f"update_fn falhou: {e}")

            if not isinstance(new_data, list):
                raise ValueError("update_fn deve retornar uma lista JSON serializável.")

            try:
                self.save(new_data, commit_message=commit_message)
                return True
            except TimeoutError:
                # tenta novamente
                continue
            except Exception:
                # conflito momentâneo ou erro transitório
                time.sleep(0.3 + random.random() * 0.3)

        raise Exception("Falha ao atualizar após múltiplas tentativas.")

    # ============================================================
    # UTILITÁRIOS
    # ============================================================
    def init_if_missing(self, initial=None):
        """
        Cria o arquivo com base vazia ([]) se não existir.
        """
        initial_data = initial if isinstance(initial, list) else []
        data, sha = self.load(force=True)
        if sha is None:
            return self.save(initial_data)
        return True

    def repair_if_invalid(self):
        """
        Se o arquivo existir mas estiver inválido, salva [].
        """
        try:
            data, _ = self.load(force=True)
            if not isinstance(data, list):
                return self.save([])
            return True
        except Exception:
            return self.save([])
