from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class AgentClient(Protocol):
    def complete_json(
        self,
        *,
        instructions: str,
        input_payload: dict[str, Any],
        schema_name: str,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return structured JSON for an agent task."""


@dataclass(frozen=True)
class DeterministicAgentClient:
    """Local fallback used until Azure Agent/OpenAI wiring is configured."""

    name: str = "deterministic_fallback"

    def complete_json(
        self,
        *,
        instructions: str,
        input_payload: dict[str, Any],
        schema_name: str,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fallback_output = input_payload.get("fallback_output")
        if isinstance(fallback_output, dict):
            return fallback_output
        fallback_tables = input_payload.get("fallback_tables")
        if isinstance(fallback_tables, dict):
            return {
                "tables": fallback_tables,
                "diagnostics": [
                    {
                        "kind": "deterministic_mock",
                        "severity": "info",
                        "description": (
                            "Deterministic mock returned structured proposal tables "
                            "for offline/debug execution."
                        ),
                    }
                ],
                "metadata": {
                    "client": self.name,
                    "schema_name": schema_name,
                    "response_schema": response_schema,
                },
            }
        return {
            "client": self.name,
            "schema_name": schema_name,
            "response_schema": response_schema,
            "instructions": instructions,
            "input_keys": sorted(input_payload.keys()),
        }


@dataclass(frozen=True)
class AzureFoundryAgentConfig:
    project_endpoint: str
    agent_id: str
    api_version: str
    bearer_token: str
    tenant_id: str
    client_id: str
    client_secret: str
    use_managed_identity: bool

    @classmethod
    def from_env(cls) -> "AzureFoundryAgentConfig | None":
        load_local_env()
        project_endpoint = os.getenv("AZURE_FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/")
        agent_id = os.getenv("AZURE_FOUNDRY_AGENT_ID", "")
        if not (project_endpoint and agent_id):
            return None
        bearer_token = os.getenv("AZURE_FOUNDRY_BEARER_TOKEN", "")
        tenant_id = os.getenv("AZURE_TENANT_ID", "")
        client_id = os.getenv("AZURE_CLIENT_ID", "")
        client_secret = os.getenv("AZURE_CLIENT_SECRET", "")
        use_managed_identity = os.getenv(
            "AZURE_FOUNDRY_USE_MANAGED_IDENTITY", ""
        ).strip().lower() in {"1", "true", "yes"}
        has_client_credentials = bool(tenant_id and client_id and client_secret)
        has_bearer_token = bool(bearer_token)
        if not (has_bearer_token or has_client_credentials or use_managed_identity):
            return None
        return cls(
            project_endpoint=project_endpoint,
            agent_id=agent_id,
            api_version=os.getenv("AZURE_FOUNDRY_API_VERSION", "v1"),
            bearer_token=bearer_token,
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            use_managed_identity=use_managed_identity,
        )


@dataclass(frozen=True)
class AzureFoundryAgentClient:
    config: AzureFoundryAgentConfig

    def complete_json(
        self,
        *,
        instructions: str,
        input_payload: dict[str, Any],
        schema_name: str,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        input_text = json.dumps(
            {
                "schema_name": schema_name,
                "instructions": instructions,
                "input": input_payload,
            },
            ensure_ascii=False,
        )
        body: dict[str, Any] = {
            "input": [
                {
                    "type": "message",
                    "role": "system",
                    "content": instructions,
                },
                {
                    "type": "message",
                    "role": "user",
                    "content": input_text,
                },
            ],
            "store": False,
        }
        response = post_json(
            self.responses_url(),
            body,
            headers={
                "Authorization": f"Bearer {self.access_token()}",
                "Foundry-Features": "HostedAgents=V1Preview",
            },
        )
        status = str(response.get("status", ""))
        if status != "completed":
            raise RuntimeError(f"Foundry response did not complete: {response}")
        return json.loads(extract_json_object(response_output_text(response)))

    def responses_url(self) -> str:
        path = f"agents/{self.config.agent_id}/endpoint/protocols/openai/responses"
        query = urlencode({"api-version": self.config.api_version})
        return f"{self.config.project_endpoint}/{path}?{query}"

    def access_token(self) -> str:
        if self.config.bearer_token:
            return self.config.bearer_token
        if self.config.tenant_id and self.config.client_id and self.config.client_secret:
            return client_credentials_token(
                tenant_id=self.config.tenant_id,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                scope="https://ai.azure.com/.default",
            )
        if not self.config.use_managed_identity:
            raise RuntimeError(
                "Foundry authentication is not configured. Set "
                "AZURE_FOUNDRY_BEARER_TOKEN, or AZURE_TENANT_ID/AZURE_CLIENT_ID/"
                "AZURE_CLIENT_SECRET, or explicitly enable managed identity with "
                "AZURE_FOUNDRY_USE_MANAGED_IDENTITY=true."
            )
        return managed_identity_token(client_id=self.config.client_id)


def default_agent_client() -> AgentClient:
    foundry_config = AzureFoundryAgentConfig.from_env()
    if foundry_config is not None:
        return AzureFoundryAgentClient(foundry_config)
    return DeterministicAgentClient()


def post_json(
    url: str,
    body: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: int = 90,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "content-type": "application/json",
            **headers,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure request failed: {exc.code} {detail}") from exc


def get_json(url: str, *, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure request failed: {exc.code} {detail}") from exc


def post_form(url: str, body: dict[str, str], *, headers: dict[str, str]) -> dict[str, Any]:
    request = Request(
        url,
        data=urlencode(body).encode("utf-8"),
        headers={
            "content-type": "application/x-www-form-urlencoded",
            **headers,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure token request failed: {exc.code} {detail}") from exc


def client_credentials_token(
    *,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    scope: str,
) -> str:
    response = post_form(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        },
        headers={},
    )
    return str(response["access_token"])


def managed_identity_token(client_id: str = "") -> str:
    resource = quote("https://ai.azure.com/", safe="")
    url = (
        "http://169.254.169.254/metadata/identity/oauth2/token"
        f"?api-version=2018-02-01&resource={resource}"
    )
    if client_id:
        url += f"&client_id={quote(client_id)}"
    try:
        response = get_json(url, headers={"Metadata": "true"})
    except URLError as exc:
        raise RuntimeError(
            "Foundry authentication is not configured. Set "
            "AZURE_FOUNDRY_BEARER_TOKEN, or AZURE_TENANT_ID/AZURE_CLIENT_ID/"
            "AZURE_CLIENT_SECRET, or run on Azure with managed identity."
        ) from exc
    return str(response["access_token"])


def response_output_text(response: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in ("output_text", "text"):
                text = content.get("text", "")
                if isinstance(text, str) and text:
                    parts.append(text)
    if not parts:
        raise RuntimeError(f"No message output found in response: {response}")
    return "\n".join(parts)


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"Foundry response did not contain JSON: {text}")
    return stripped[start : end + 1]


_ENV_LOADED = False


def load_local_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    for path in env_file_candidates():
        if path.exists():
            load_env_file(path)


def env_file_candidates() -> list[Path]:
    project_root = Path(__file__).resolve().parents[4]
    return [
        Path.cwd() / ".env",
        project_root / ".env",
    ]


def load_env_file(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
