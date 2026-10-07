from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _configured(name: str) -> bool:
    return bool((os.getenv(name) or "").strip())


def _path_status(name: str) -> dict[str, object]:
    raw=(os.getenv(name) or "").strip()
    if not raw:
        return {"configured":False,"exists":False,"kind":None}
    path=Path(raw)
    return {
        "configured":True,
        "exists":path.exists(),
        "kind":"dir" if path.is_dir() else ("file" if path.is_file() else "missing"),
    }


def build_probe() -> dict[str, object]:
    return {
        "schema_version":"WF9_ENVIRONMENT_PROBE_V1",
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "pit_universe":{
            "alphavantage_api_key":_configured("ALPHAVANTAGE_API_KEY"),
            "massive_api_key":_configured("MASSIVE_API_KEY"),
        },
        "canonical_adjusted_prices":{
            "massive_api_key":_configured("MASSIVE_API_KEY"),
            "marketparquet_root":_path_status("MARKETPARQUET_ROOT"),
            "simfin_price_bulk_path":_path_status("SIMFIN_PRICE_BULK_PATH"),
        },
        "code_signing":{
            "pfx_base64":_configured("WINDOWS_CODESIGN_PFX_BASE64"),
            "password":_configured("WINDOWS_CODESIGN_PASSWORD"),
        },
    }


def main() -> int:
    payload=build_probe()
    output=Path(os.getenv("WF9_PROBE_OUTPUT") or "wf9_environment_probe.json")
    output.parent.mkdir(parents=True,exist_ok=True)
    rendered=json.dumps(payload,indent=2,sort_keys=True)
    output.write_text(rendered+"\n",encoding="utf-8")
    print(rendered)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
