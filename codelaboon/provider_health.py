"""Credential presence and optional live catalogue checks, without printing secrets."""


def inspect(providers, live=False):
    rows = []
    for name, provider in providers.items():
        row = {"provider": name, "configured": False, "catalogue": "not checked",
               "inference": "not checked"}
        try:
            row["configured"] = bool(provider.validate_api_key())
            if row["configured"] and live:
                models = provider.list_models()
                row["models"] = len(models)
                row["catalogue"] = "listed (provider may use an offline fallback)" if models else "empty"
        except Exception as error:
            # Provider/network exception strings can include request URLs or headers.
            row["catalogue"] = "failed"
            row["error"] = type(error).__name__
        rows.append(row)
    return rows
