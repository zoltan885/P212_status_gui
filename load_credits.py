def parse_creds(creds_path):
    jwt, seed = None, None
    with open(creds_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if "-----BEGIN NATS USER JWT-----" in line:
            jwt = lines[i + 1].strip()
        elif "-----BEGIN USER NKEY SEED-----" in line:
            seed = lines[i + 1].strip()
    if not jwt or not seed:
        raise ValueError("Could not parse JWT or NKey seed from creds file.")
    return jwt, seed