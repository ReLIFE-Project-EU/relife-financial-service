import os

import uvicorn


def main() -> None:
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 9090))
    # Dynamically determine the module path
    module_name = __name__.split(".")[0]
    uvicorn.run(f"{module_name}.app:app", host=host, port=port)
