import os
import yaml

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "routine_patterns.yaml"
)


def load_routine_config(path=None):
    """Load routine classification config from YAML."""
    path = path or DEFAULT_CONFIG_PATH
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("routine", {})
